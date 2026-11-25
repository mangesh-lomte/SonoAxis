import os
import re
import time
import uuid
import shutil
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from PIL import Image, ImageEnhance, ImageOps
import numpy as np

import pytesseract
from backend.app.schemas.ocr import OCRUploadResponse, OCRRegionBox
from backend.app.ocr.preprocessing import (
    validate_image_file,
    preprocess_ultrasound_image,
    detect_measurement_worksheet_region,
    remove_table_borders_inverted,
)
from backend.app.ocr.extractor import (
    extract_candidates_from_text_lines,
    get_assignable_target_fields,
)

OCR_STORAGE_DIR = Path("D:/sovoice/data/ocr_uploads")
OCR_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

TESSERACT_CANDIDATE_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"D:\tools\tesseract\tesseract.exe",
    r"D:\Tesseract-OCR\tesseract.exe",
]


def find_tesseract_binary() -> Optional[str]:
    """Checks if a valid tesseract binary exists in PATH or standard local directories."""
    cmd = shutil.which("tesseract")
    if cmd:
        return cmd
    for p in TESSERACT_CANDIDATE_PATHS:
        if os.path.isfile(p):
            return p
    return None


def _is_border_glyph(token: str) -> bool:
    return bool(re.match(r"^[|~_=—\-.\[\]]{1,3}$", token))


def _ocr_single_cell(
    preprocessed_crop: Image.Image,
    cell_box: Tuple[int, int, int, int],
) -> str:
    """
    Runs targeted single-line cell OCR (--psm 7, 4x LANCZOS/BICUBIC upscaling)
    on an already dark-mode-inverted & border-cleaned worksheet crop.
    """
    x1, y1, x2, y2 = cell_box
    cw, ch = preprocessed_crop.size
    x1 = max(0, min(x1, cw - 2))
    y1 = max(0, min(y1, ch - 2))
    x2 = max(x1 + 2, min(x2, cw))
    y2 = max(y1 + 2, min(y2, ch))
    cell = preprocessed_crop.crop((x1, y1, x2, y2))
    cell_4x = cell.resize((cell.size[0] * 4, cell.size[1] * 4), Image.Resampling.BICUBIC)
    txt = pytesseract.image_to_string(cell_4x, config="--psm 7").strip()
    return re.sub(r"^[|¦\s]+|[|¦\s]+$", "", txt).strip()


def _reconstruct_spatial_table_rows(
    crop_img: Image.Image,
    offset_x: int = 0,
    offset_y: int = 0,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Reconstructs worksheet table rows from Tesseract word bounding boxes inside a table region:
    1. Converts crop to grayscale, inverts dark-mode ultrasound UI, removes table border rules safely.
    2. Runs Tesseract --psm 11 at 3x LANCZOS resolution to obtain word coordinates.
    3. Rejects oversized outlier boxes so distinct rows never merge across headers.
    4. Groups words into horizontal Y-band rows and identifies column split (Parameter vs Value).
    5. Invokes cell-level --psm 7 verification when a row has a missing label/value cell, missing unit,
       suspicious missing decimal, or low OCR confidence.
    6. Translates all bounding boxes back to original full-image pixel coordinates (+offset_x, +offset_y).
    """
    steps: List[str] = ["grayscale"]
    gray_crop = crop_img.convert("L") if crop_img.mode != "L" else crop_img.copy()
    cw, ch = gray_crop.size

    np_gray = np.array(gray_crop)
    mean_lum = float(np.mean(np_gray))
    std_lum = float(np.std(np_gray))
    is_dark_mode = mean_lum < 120.0

    # Prepare clean inverted/light cell surface (without border erosion distorting decimal dots)
    raw_inverted = ImageOps.invert(gray_crop) if is_dark_mode else gray_crop
    if is_dark_mode:
        steps.append("dark_mode_inverted")

    cleaned_arr = remove_table_borders_inverted(np.array(raw_inverted))
    work_img = Image.fromarray(cleaned_arr)
    steps.append("table_borders_removed")

    contrast_factor = 1.5 if std_lum < 35.0 else 1.25
    work_img = ImageEnhance.Contrast(work_img).enhance(contrast_factor)
    cell_surface = ImageEnhance.Contrast(raw_inverted).enhance(contrast_factor)
    steps.append(f"contrast_boost_{contrast_factor}x")

    scale = 3.0 if cw < 1100 else 2.0
    up_img = work_img.resize((int(cw * scale), int(ch * scale)), Image.Resampling.LANCZOS)
    steps.append(f"upscale_{int(scale)}x_lanczos")

    data = pytesseract.image_to_data(up_img, config="--psm 11", output_type=pytesseract.Output.DICT)
    words: List[Dict[str, Any]] = []
    for i in range(len(data["text"])):
        t = data["text"][i].strip()
        conf = float(data["conf"][i])
        if not t or conf < 0 or _is_border_glyph(t):
            continue
        w_px = max(1.0, data["width"][i] / scale)
        h_px = max(1.0, data["height"][i] / scale)
        words.append({
            "text": t,
            "conf": conf / 100.0,
            "x": data["left"][i] / scale,
            "y": data["top"][i] / scale,
            "w": w_px,
            "h": h_px,
        })

    if not words:
        return [], steps

    # Reject tall bounding artifacts (> 2.2x median glyph height) that span across multiple rows
    med_h = float(np.median([z["h"] for z in words]))
    max_allowed_h = max(32.0, med_h * 2.2)
    filtered_words = [z for z in words if z["h"] <= max_allowed_h]
    if not filtered_words:
        filtered_words = words

    # Group words into horizontal rows using tight median-clamped vertical center overlap
    rows: List[List[Dict[str, Any]]] = []
    for w_box in sorted(filtered_words, key=lambda z: (z["y"], z["x"])):
        cy = w_box["y"] + w_box["h"] / 2.0
        placed = False
        for row in rows:
            rcy = sum(z["y"] + z["h"] / 2.0 for z in row) / len(row)
            rh = max(z["h"] for z in row)
            tol = min(max(rh, w_box["h"]), med_h * 1.45) * 0.65
            if abs(cy - rcy) <= tol:
                row.append(w_box)
                placed = True
                break
        if not placed:
            rows.append([w_box])

    # Discover column split between Parameter labels and Value column (from decimal/numeric tokens below header)
    value_xs = [
        w_box["x"]
        for r in rows
        for w_box in r
        if re.search(r"^\d+(?:\.\d+)?$", w_box["text"]) and w_box["x"] > cw * 0.35
    ]
    col_split_x = int(min(value_xs) - 14) if value_xs else int(cw * 0.48)
    col_split_x = max(int(cw * 0.35), min(int(cw * 0.70), col_split_x))

    reconstructed_lines: List[Dict[str, Any]] = []
    has_unit_re = re.compile(r"\b(?:cm|mm|ml|cc|cm/s|m/s|mmhg)\b", re.IGNORECASE)
    has_num_re = re.compile(r"\d+(?:\.\d+)?")
    suspect_int_re = re.compile(r"^\d{3,4}(?:[,.\s]|$)")  # e.g. missing dot in '2135, ce' or '45 cm'

    for row in rows:
        r_sorted = sorted(row, key=lambda z: z["x"])
        left_w = [z for z in r_sorted if (z["x"] + z["w"] / 2.0) < col_split_x]
        right_w = [z for z in r_sorted if (z["x"] + z["w"] / 2.0) >= col_split_x]

        l_txt = " ".join(z["text"] for z in left_w).strip()
        r_txt = " ".join(z["text"] for z in right_w).strip()

        ry1 = max(0, int(min(z["y"] for z in r_sorted) - 5))
        ry2 = min(ch, int(max(z["y"] + z["h"] for z in r_sorted) + 5))

        needs_left_cell = (bool(right_w) and not left_w) or (
            bool(left_w) and (min(z["conf"] for z in left_w) < 0.75 or len(re.sub(r"[^A-Za-z]", "", l_txt)) < 2)
        )
        needs_right_cell = (bool(left_w) and not right_w and ry1 > 40) or (
            bool(right_w) and (
                not has_unit_re.search(r_txt)
                or not has_num_re.search(r_txt)
                or bool(suspect_int_re.search(r_txt))
                or bool(re.search(r"\d+\.\d+\.\d+", r_txt))
                or min(z["conf"] for z in right_w) < 0.78
            )
        )

        if needs_left_cell and ry2 - ry1 >= 12:
            # Prefer clean border-preserving surface for cell crop (shrunk away from border edges)
            recovered_l = _ocr_single_cell(cell_surface, (10, ry1, col_split_x - 4, ry2))
            if recovered_l and len(re.sub(r"[^A-Za-z]", "", recovered_l)) >= 2:
                l_txt = recovered_l
                if "cell_psm7_recovery" not in steps:
                    steps.append("cell_psm7_recovery")

        if needs_right_cell and ry2 - ry1 >= 12:
            recovered_r = _ocr_single_cell(cell_surface, (max(0, col_split_x - 2), ry1, cw - 6, ry2))
            # Accept recovered cell if it repairs a missing unit, missing decimal, or merged multi-D separators
            dec_count_old = len(re.findall(r"\d+\.\d+", r_txt))
            dec_count_new = len(re.findall(r"\d+\.\d+", recovered_r))
            sep_count_old = len(re.findall(r"[x×]", r_txt, re.I))
            sep_count_new = len(re.findall(r"[x×]", recovered_r, re.I))
            if recovered_r and has_num_re.search(recovered_r) and (
                not has_num_re.search(r_txt)
                or (has_unit_re.search(recovered_r) and not has_unit_re.search(r_txt))
                or ("." in recovered_r and "." not in r_txt)
                or dec_count_new > dec_count_old
                or sep_count_new > sep_count_old
            ):
                r_txt = recovered_r
                if "cell_psm7_recovery" not in steps:
                    steps.append("cell_psm7_recovery")

        combined_text = f"{l_txt} {r_txt}".strip()
        if not combined_text:
            continue

        min_x = int(round(min(z["x"] for z in r_sorted)))
        max_x = int(round(max(z["x"] + z["w"] for z in r_sorted)))
        if not left_w and l_txt:
            min_x = 10
        if not right_w and r_txt:
            max_x = cw - 8

        reconstructed_lines.append({
            "text": combined_text,
            "confidence": sum(z["conf"] for z in r_sorted) / len(r_sorted),
            "source_zone": "worksheet_table",
            "bbox": {
                "x": offset_x + min_x,
                "y": offset_y + ry1,
                "width": max(8, max_x - min_x),
                "height": max(8, ry2 - ry1),
            },
        })

    return reconstructed_lines, steps


def _group_sparse_words_into_lines(
    words: List[Dict[str, Any]],
    img_w: int,
    img_h: int,
) -> List[Dict[str, Any]]:
    """
    Groups full-image Tesseract word boxes cleanly into horizontal table rows / lines
    for full-image scans where no explicit sub-region crop was requested.
    """
    if not words:
        return []

    sorted_words = sorted(words, key=lambda w: (w["y"], w["x"]))
    num_or_op = re.compile(r"^(?:\d+(?:\.\d+)?|[x×*]|cm|mm|ml|cc|cm/s|m/s|mmhg)$", re.IGNORECASE)
    phrases: List[List[Dict[str, Any]]] = []
    for w in sorted_words:
        cy = w["y"] + w["h"] / 2.0
        placed = False
        for ph in phrases:
            last = ph[-1]
            ph_cy = sum(x["y"] + x["h"] / 2.0 for x in ph) / len(ph)
            avg_h = sum(x["h"] for x in ph) / len(ph)
            horiz_gap = w["x"] - (last["x"] + last["w"])
            both_meas = bool(num_or_op.match(last["text"]) and num_or_op.match(w["text"]))
            max_gap = max(avg_h, w["h"]) * (3.8 if both_meas else 2.4)
            if abs(cy - ph_cy) <= max(avg_h, w["h"]) * 0.55 and -avg_h <= horiz_gap <= max_gap:
                ph.append(w)
                placed = True
                break
        if not placed:
            phrases.append([w])

    phrase_objs: List[Dict[str, Any]] = []
    for ph in phrases:
        ph_sorted = sorted(ph, key=lambda x: x["x"])
        txt = " ".join(x["text"] for x in ph_sorted).strip()
        if not txt:
            continue
        min_x = min(x["x"] for x in ph_sorted)
        min_y = min(x["y"] for x in ph_sorted)
        max_x = max(x["x"] + x["w"] for x in ph_sorted)
        max_y = max(x["y"] + x["h"] for x in ph_sorted)
        avg_conf = sum(x["conf"] for x in ph_sorted) / len(ph_sorted)
        phrase_objs.append({
            "text": txt,
            "confidence": avg_conf,
            "x": min_x,
            "y": min_y,
            "w": max_x - min_x,
            "h": max_y - min_y,
            "cy": (min_y + max_y) / 2.0,
            "used": False,
        })

    has_num_with_unit = re.compile(r"\d+(?:\.\d+)?\s*(?:cm|mm|ml|cc|cm/s|m/s|mmhg|%)", re.IGNORECASE)
    anat_keyword = re.compile(
        r"\b(?:liver|gall|gb|cbd|kidney|rk|lk|spleen|prostate|bladder|pvr|void|residual|uterus|endometri|ovary|cfa|sfa|popliteal|ata|pta|peroneal|gsv|ssv|perforator)\b",
        re.IGNORECASE,
    )

    merged_lines: List[Dict[str, Any]] = []
    phrase_objs.sort(key=lambda p: (p["cy"], p["x"]))

    for is_priority_pass in (True, False):
        for i, left_p in enumerate(phrase_objs):
            if left_p["used"] or has_num_with_unit.search(left_p["text"]):
                continue
            if is_priority_pass:
                if not anat_keyword.search(left_p["text"]):
                    continue
            else:
                clean_alpha = re.sub(r"[^A-Za-z]", "", left_p["text"])
                if len(clean_alpha) < 4:
                    continue

            best_j = None
            best_dx = float("inf")
            for j, right_p in enumerate(phrase_objs):
                if i == j or right_p["used"]:
                    continue
                if right_p["x"] > img_w * 0.55 and left_p["x"] < img_w * 0.45:
                    continue
                dx = right_p["x"] - (left_p["x"] + left_p["w"])
                dy = abs(right_p["cy"] - left_p["cy"])
                row_tol = max(left_p["h"], right_p["h"]) * 0.75
                if 0 <= dx <= img_w * 0.35 and dy <= row_tol:
                    if has_num_with_unit.search(right_p["text"]):
                        if dx < best_dx:
                            best_dx = dx
                            best_j = j

            if best_j is not None:
                rp = phrase_objs[best_j]
                left_p["used"] = True
                rp["used"] = True
                min_x = min(left_p["x"], rp["x"])
                min_y = min(left_p["y"], rp["y"])
                max_x = max(left_p["x"] + left_p["w"], rp["x"] + rp["w"])
                max_y = max(left_p["y"] + left_p["h"], rp["y"] + rp["h"])
                merged_lines.append({
                    "text": f"{left_p['text']} {rp['text']}".strip(),
                    "confidence": (left_p["confidence"] + rp["confidence"]) / 2.0,
                    "bbox": {"x": min_x, "y": min_y, "width": max_x - min_x, "height": max_y - min_y},
                })

    for p in phrase_objs:
        if not p["used"]:
            merged_lines.append({
                "text": p["text"],
                "confidence": p["confidence"],
                "bbox": {"x": p["x"], "y": p["y"], "width": p["w"], "height": p["h"]},
            })

    merged_lines.sort(key=lambda item: (item["bbox"]["y"], item["bbox"]["x"]))
    return merged_lines


class UltrasoundOCREngine:
    """
    Production-grade offline local ultrasound machine printout OCR engine.
    Combines automatic/manual worksheet region isolation, border removal,
    word bounding-box table reconstruction, cell-level --psm 7 recovery,
    configurable clinical alias mapping, and duplicate annotation filtering.
    """

    def __init__(self):
        self.tesseract_cmd = find_tesseract_binary()
        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

    def is_tesseract_available(self) -> bool:
        if not self.tesseract_cmd:
            self.tesseract_cmd = find_tesseract_binary()
            if self.tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
        return self.tesseract_cmd is not None

    def process_and_extract(
        self,
        report_id: str,
        filename: str,
        file_bytes: bytes,
        rotate_degrees: int = 0,
        crop_box: Optional[Tuple[int, int, int, int]] = None,
        existing_sections: Optional[List[Dict[str, Any]]] = None,
        ocr_mode: str = "auto",
    ) -> OCRUploadResponse:
        if not self.is_tesseract_available():
            raise RuntimeError(
                "Tesseract OCR executable not found on host system. Local image recognition requires Tesseract OCR."
            )

        start_time = time.perf_counter()

        raw_img = validate_image_file(file_bytes, filename)
        rot_img = raw_img.rotate(-rotate_degrees, expand=True) if rotate_degrees % 360 != 0 else raw_img
        orig_w, orig_h = rot_img.size

        report_dir = OCR_STORAGE_DIR / report_id
        report_dir.mkdir(parents=True, exist_ok=True)
        source_doc_id = f"doc-ocr-{uuid.uuid4().hex[:8]}"
        safe_filename = f"{source_doc_id}_{filename.replace(' ', '_')}"
        save_path = report_dir / safe_filename
        with open(save_path, "wb") as f:
            f.write(file_bytes)

        applied_steps: List[str] = []
        if rotate_degrees % 360 != 0:
            applied_steps.append(f"rotate_{rotate_degrees}deg")

        detected_region_info: Optional[Dict[str, Any]] = None
        active_box: Optional[Tuple[int, int, int, int]] = None

        if crop_box is not None:
            x1, y1, x2, y2 = crop_box
            x1 = max(0, min(int(x1), orig_w - 2))
            y1 = max(0, min(int(y1), orig_h - 2))
            x2 = max(x1 + 2, min(int(x2), orig_w))
            y2 = max(y1 + 2, min(int(y2), orig_h))
            active_box = (x1, y1, x2, y2)
            ocr_mode_used = "manual_region"
            detected_region_obj = OCRRegionBox(
                x1=x1, y1=y1, x2=x2, y2=y2, confidence=1.0, detection_method="manual_selection"
            )
            applied_steps.append(f"manual_region_{x1}_{y1}_{x2}_{y2}")
        elif ocr_mode != "full":
            detected_region_info = detect_measurement_worksheet_region(rot_img)
            if detected_region_info:
                active_box = (
                    detected_region_info["x1"],
                    detected_region_info["y1"],
                    detected_region_info["x2"],
                    detected_region_info["y2"],
                )
                ocr_mode_used = "auto_table_region"
                detected_region_obj = OCRRegionBox(
                    x1=active_box[0],
                    y1=active_box[1],
                    x2=active_box[2],
                    y2=active_box[3],
                    confidence=detected_region_info["confidence"],
                    detection_method="auto_table_grid",
                )
                applied_steps.append(
                    f"auto_worksheet_region_{active_box[0]}_{active_box[1]}_{active_box[2]}_{active_box[3]}"
                )
            else:
                ocr_mode_used = "full_image"
                detected_region_obj = None
        else:
            # Explicit full-image mode: still detect worksheet box (if present) for duplicate annotation filtering
            detected_region_info = detect_measurement_worksheet_region(rot_img)
            ocr_mode_used = "full_image"
            detected_region_obj = (
                OCRRegionBox(
                    x1=detected_region_info["x1"],
                    y1=detected_region_info["y1"],
                    x2=detected_region_info["x2"],
                    y2=detected_region_info["y2"],
                    confidence=detected_region_info["confidence"],
                    detection_method="auto_table_grid",
                )
                if detected_region_info
                else None
            )

        if active_box is not None:
            crop_img = rot_img.crop(active_box)
            recognized_lines, region_steps = _reconstruct_spatial_table_rows(
                crop_img=crop_img,
                offset_x=active_box[0],
                offset_y=active_box[1],
            )
            applied_steps.extend(region_steps)
            worksheet_box_dict = {
                "x1": active_box[0],
                "y1": active_box[1],
                "x2": active_box[2],
                "y2": active_box[3],
            }
        else:
            processed_img, full_steps = preprocess_ultrasound_image(rot_img)
            applied_steps.extend(full_steps)
            scale_factor = processed_img.size[0] / float(max(1, orig_w))
            full_lines = self._run_ocr_recognition(
                processed_img=processed_img,
                orig_w=orig_w,
                scale_factor=scale_factor,
            )
            if detected_region_info:
                worksheet_box_dict = {
                    "x1": detected_region_info["x1"],
                    "y1": detected_region_info["y1"],
                    "x2": detected_region_info["x2"],
                    "y2": detected_region_info["y2"],
                }
                table_crop = rot_img.crop((
                    worksheet_box_dict["x1"],
                    worksheet_box_dict["y1"],
                    worksheet_box_dict["x2"],
                    worksheet_box_dict["y2"],
                ))
                table_lines, region_steps = _reconstruct_spatial_table_rows(
                    crop_img=table_crop,
                    offset_x=worksheet_box_dict["x1"],
                    offset_y=worksheet_box_dict["y1"],
                )
                for st in region_steps:
                    if st not in applied_steps:
                        applied_steps.append(st)

                outside_lines = []
                for fl in full_lines:
                    bb = fl.get("bbox") or {}
                    cx = bb.get("x", 0) + bb.get("width", 0) / 2.0
                    cy = bb.get("y", 0) + bb.get("height", 0) / 2.0
                    inside_table = (
                        worksheet_box_dict["x1"] - 10 <= cx <= worksheet_box_dict["x2"] + 10
                        and worksheet_box_dict["y1"] - 10 <= cy <= worksheet_box_dict["y2"] + 10
                    )
                    if not inside_table:
                        fl["source_zone"] = "ultrasound_annotation"
                        outside_lines.append(fl)
                recognized_lines = table_lines + outside_lines
            else:
                recognized_lines = full_lines
                worksheet_box_dict = None

        raw_ocr_text = "\n".join(l["text"] for l in recognized_lines)
        stats: Dict[str, int] = {"filtered_duplicate_count": 0}
        candidates = extract_candidates_from_text_lines(
            lines=recognized_lines,
            source_document_id=source_doc_id,
            existing_sections=existing_sections,
            worksheet_box=worksheet_box_dict,
            stats_out=stats,
        )

        exec_time_ms = round((time.perf_counter() - start_time) * 1000.0, 1)

        return OCRUploadResponse(
            source_document_id=source_doc_id,
            filename=safe_filename,
            image_url=f"/api/reports/{report_id}/ocr/images/{safe_filename}",
            image_width=orig_w,
            image_height=orig_h,
            candidates=candidates,
            preprocessing_applied=applied_steps,
            execution_time_ms=exec_time_ms,
            raw_ocr_text=raw_ocr_text,
            ocr_mode_used=ocr_mode_used,
            detected_region=detected_region_obj,
            filtered_duplicate_count=stats.get("filtered_duplicate_count", 0),
            available_target_fields=get_assignable_target_fields(),
        )

    def _run_ocr_recognition(
        self,
        processed_img: Image.Image,
        orig_w: int = 700,
        scale_factor: float = 1.0,
    ) -> List[Dict[str, Any]]:
        if not self.is_tesseract_available():
            raise RuntimeError(
                "Tesseract OCR executable not found on host system. Local image recognition requires Tesseract OCR."
            )

        psm = "--psm 11" if orig_w > 900 else "--psm 6"
        data = pytesseract.image_to_data(processed_img, config=psm, output_type=pytesseract.Output.DICT)
        n_boxes = len(data["text"])

        if orig_w > 900:
            raw_words: List[Dict[str, Any]] = []
            for i in range(n_boxes):
                text = data["text"][i].strip()
                conf = float(data["conf"][i])
                if not text or conf < 0:
                    continue
                raw_words.append({
                    "text": text,
                    "conf": conf / 100.0,
                    "x": int(round(data["left"][i] / scale_factor)),
                    "y": int(round(data["top"][i] / scale_factor)),
                    "w": max(1, int(round(data["width"][i] / scale_factor))),
                    "h": max(1, int(round(data["height"][i] / scale_factor))),
                })
            return _group_sparse_words_into_lines(
                raw_words,
                img_w=orig_w,
                img_h=int(round(processed_img.size[1] / scale_factor)),
            )

        lines_dict: Dict[int, List[Dict[str, Any]]] = {}
        for i in range(n_boxes):
            text = data["text"][i].strip()
            conf = float(data["conf"][i])
            if not text or conf < 0:
                continue
            line_num = data["line_num"][i]
            lines_dict.setdefault(line_num, []).append({
                "text": text,
                "conf": conf / 100.0,
                "x": int(round(data["left"][i] / scale_factor)),
                "y": int(round(data["top"][i] / scale_factor)),
                "w": max(1, int(round(data["width"][i] / scale_factor))),
                "h": max(1, int(round(data["height"][i] / scale_factor))),
            })

        results = []
        for _, words in sorted(lines_dict.items()):
            full_text = " ".join(w["text"] for w in words)
            avg_conf = sum(w["conf"] for w in words) / len(words)
            min_x = min(w["x"] for w in words)
            min_y = min(w["y"] for w in words)
            max_x = max(w["x"] + w["w"] for w in words)
            max_y = max(w["y"] + w["h"] for w in words)
            results.append({
                "text": full_text,
                "confidence": avg_conf,
                "bbox": {"x": min_x, "y": min_y, "width": max_x - min_x, "height": max_y - min_y},
            })
        return results


ocr_engine = UltrasoundOCREngine()
