import io
from typing import Tuple, Optional, List, Dict, Any
from PIL import Image, ImageEnhance, ImageOps
import numpy as np

# Safety limits: Decompression bomb protection (25 million pixels)
Image.MAX_IMAGE_PIXELS = 25_000_000
MAX_ALLOWED_FILE_SIZE = 15 * 1024 * 1024  # 15 MB

ALLOWED_IMAGE_FORMATS = {"JPEG", "JPG", "PNG", "WEBP", "BMP", "TIFF"}


def validate_image_file(file_bytes: bytes, filename: str) -> Image.Image:
    """
    Validates file size, integrity, and image format to ensure security.
    Rejects oversized payloads and corrupted files safely.
    """
    if len(file_bytes) > MAX_ALLOWED_FILE_SIZE:
        raise ValueError(f"Image file exceeds maximum permitted size of 15 MB ({len(file_bytes)} bytes)")

    if len(file_bytes) < 16:
        raise ValueError("Image file payload is too small or empty")

    try:
        img = Image.open(io.BytesIO(file_bytes))
        img_format = (img.format or "").upper()
        if img_format not in ALLOWED_IMAGE_FORMATS:
            ext = filename.rsplit(".", 1)[-1].upper() if "." in filename else ""
            if ext not in ALLOWED_IMAGE_FORMATS:
                raise ValueError(
                    f"Unsupported image format: {img_format or ext}. Supported formats: JPEG, PNG, WebP, BMP, TIFF."
                )
        img.verify()
        img = Image.open(io.BytesIO(file_bytes))
        return img
    except Exception as e:
        if isinstance(e, ValueError):
            raise e
        raise ValueError(f"Corrupted or invalid image data: {str(e)}")


def _compute_otsu_threshold(np_img: np.ndarray) -> int:
    """Computes optimal Otsu threshold without destroying small decimal points in upscaled grayscale."""
    hist, _ = np.histogram(np_img, bins=256, range=(0, 256))
    total = np_img.size
    current_max = 0.0
    threshold = 128
    sum_total = float(np.dot(np.arange(256), hist))
    sum_b = 0.0
    w_b = 0

    for i in range(256):
        w_b += int(hist[i])
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += float(i * hist[i])
        m_b = sum_b / w_b
        m_f = (sum_total - sum_b) / w_f
        between_class_var = float(w_b) * float(w_f) * ((m_b - m_f) ** 2)
        if between_class_var > current_max:
            current_max = between_class_var
            threshold = i
    return threshold


def detect_measurement_worksheet_region(img: Image.Image) -> Optional[Dict[str, Any]]:
    """
    Automatically detects a multi-row ultrasound measurement worksheet / table panel
    on multi-pane scanner captures by identifying stacked horizontal table rule lines
    with uniform spacing (16..95px) sharing a column span.

    Returns dict {x1, y1, x2, y2, confidence, detection_method, row_rules} in image pixel
    coordinates, or None if the image is already a compact single-panel worksheet.
    """
    gray = img.convert("L") if img.mode != "L" else img
    arr = np.array(gray, dtype=np.float32)
    h, w = arr.shape
    if w < 800 or h < 480:
        return None

    dx = np.abs(arr[:, 1:] - arr[:, :-1])
    dy_up = np.pad(np.abs(arr[2:, :-1] - arr[:-2, :-1]), ((1, 1), (0, 0)), mode="constant")
    dy_lo = np.pad(np.abs(arr[4:, :-1] - arr[:-4, :-1]), ((2, 2), (0, 0)), mode="constant")
    on_rule = (dx < 8.0) & (np.maximum(dy_up, dy_lo) >= 8.0)

    min_run = max(120, int(w * 0.12))
    rule_segments: List[Tuple[int, int, int]] = []
    for y in range(int(h * 0.08), int(h * 0.85)):
        row = on_rule[y]
        if int(row.sum()) < min_run:
            continue
        r = row.copy()
        # Bridge narrow vertical border intersections up to 14px wide
        for shift in range(1, 15):
            r[:-shift] |= (row[:-shift] & row[shift:])
        padded = np.concatenate(([False], r, [False]))
        diffs = np.diff(padded.astype(np.int8))
        starts = np.where(diffs == 1)[0]
        ends = np.where(diffs == -1)[0]
        for s, e in zip(starts, ends):
            if e - s >= min_run:
                rule_segments.append((y, int(s), int(e)))

    if len(rule_segments) < 5:
        return None

    # Merge multi-pixel vertical thickness of the same horizontal rule
    merged_rules: List[Tuple[int, int, int]] = []
    for y, s, e in rule_segments:
        if (
            merged_rules
            and y - merged_rules[-1][0] <= 4
            and abs(s - merged_rules[-1][1]) < 40
            and abs(e - merged_rules[-1][2]) < 40
        ):
            py, ps, pe = merged_rules[-1]
            merged_rules[-1] = (y, min(ps, s), max(pe, e))
        else:
            merged_rules.append((y, s, e))

    # Find dominant cluster of horizontal table rules sharing overlapping X span
    best_cluster: List[Tuple[int, int, int]] = []
    best_score = 0.0
    for _, ax1, ax2 in merged_rules:
        cluster = [
            (y, x1, x2)
            for (y, x1, x2) in merged_rules
            if min(ax2, x2) - max(ax1, x1) >= 0.65 * min(ax2 - ax1, x2 - x1)
            and abs(x1 - ax1) < w * 0.15
            and abs(x2 - ax2) < w * 0.15
        ]
        ys_u: List[int] = []
        for c in sorted(cluster):
            if not ys_u or c[0] - ys_u[-1] >= 14:
                ys_u.append(c[0])
        if len(ys_u) >= 5:
            score = float(len(ys_u) * (ax2 - ax1))
            if score > best_score:
                best_score = score
                best_cluster = cluster

    if not best_cluster:
        return None

    best_cluster.sort(key=lambda r: r[0])
    row_ys: List[int] = []
    for y, _, _ in best_cluster:
        if not row_ys or y - row_ys[-1] >= 15:
            row_ys.append(y)

    dys = [row_ys[i + 1] - row_ys[i] for i in range(len(row_ys) - 1)]
    row_dys = [d for d in dys if 16 <= d <= 90]
    if len(row_dys) < 4:
        return None
    med_dy = float(np.median(row_dys))

    chains: List[List[int]] = [[row_ys[0]]]
    for ry in row_ys[1:]:
        if ry - chains[-1][-1] <= min(85.0, max(28.0, 1.5 * med_dy)):
            chains[-1].append(ry)
        else:
            chains.append([ry])
    dense_ys = max(chains, key=len)
    if len(dense_ys) < 4:
        return None

    # Recompute tight row height strictly inside the dense table body
    body_dys = [dense_ys[i + 1] - dense_ys[i] for i in range(len(dense_ys) - 1)]
    med_body_dy = float(np.median(body_dys)) if body_dys else med_dy

    # Expand across adjacent column rule segments on the same row Y coordinates
    anchor_x1 = int(np.median([x1 for y, x1, x2 in best_cluster if y in dense_ys]))
    anchor_x2 = int(np.median([x2 for y, x1, x2 in best_cluster if y in dense_ys]))
    expanded_x1s, expanded_x2s = [anchor_x1], [anchor_x2]
    for ry in dense_ys:
        segs_at_y = [(x1, x2) for y, x1, x2 in rule_segments if abs(y - ry) <= 3]
        cx1, cx2 = anchor_x1, anchor_x2
        changed = True
        while changed:
            changed = False
            for sx1, sx2 in segs_at_y:
                if sx1 <= cx2 + 30 and sx2 >= cx1 - 30:
                    if sx1 < cx1:
                        cx1 = sx1
                        changed = True
                    if sx2 > cx2:
                        cx2 = sx2
                        changed = True
        expanded_x1s.append(cx1)
        expanded_x2s.append(cx2)

    tx1 = max(0, int(np.percentile(expanded_x1s, 20)) - 10)
    tx2 = min(w, int(np.percentile(expanded_x2s, 80)) + 10)
    ty1 = max(0, dense_ys[0] - int(med_body_dy * 1.15))
    ty2 = min(h, dense_ys[-1] + int(med_body_dy * 1.10))

    area_ratio = ((tx2 - tx1) * (ty2 - ty1)) / float(w * h)
    if area_ratio > 0.72 or (tx2 - tx1) < 200 or (ty2 - ty1) < 150:
        return None

    return {
        "x1": tx1,
        "y1": ty1,
        "x2": tx2,
        "y2": ty2,
        "confidence": min(0.99, round(0.75 + 0.02 * len(dense_ys), 2)),
        "detection_method": "auto_table_grid",
        "row_rules": dense_ys,
    }


def remove_table_borders_inverted(inv_arr: np.ndarray) -> np.ndarray:
    """
    Removes long horizontal and vertical table borders (>= 42% of width/height) from inverted
    grayscale array while strictly protecting darker foreground character ink and decimal dots.
    """
    out = inv_arr.copy()
    h, w = out.shape
    bg = int(np.percentile(out, 85))

    def _max_1d_h(a: np.ndarray, k: int) -> np.ndarray:
        pad = k // 2
        padded = np.pad(a, ((0, 0), (pad, pad)), mode="edge")
        return np.maximum.reduce([padded[:, i : i + w] for i in range(0, k, 2)])

    def _max_1d_v(a: np.ndarray, k: int) -> np.ndarray:
        pad = k // 2
        padded = np.pad(a, ((pad, pad), (0, 0)), mode="edge")
        return np.maximum.reduce([padded[i : i + h, :] for i in range(0, k, 2)])

    hk = max(55, int(w * 0.42))
    vk = max(55, int(h * 0.45))
    h_mask = _max_1d_h(out, hk) < (bg - 18)
    v_mask = _max_1d_v(out, vk) < (bg - 18)
    border_mask = h_mask | v_mask

    # Only erase border-level pixels (medium gray lines > 75), leaving dark text strokes untouched
    safe_erase = border_mask & (out > 75)
    out[safe_erase] = bg
    return out


def preprocess_ultrasound_image(
    img: Image.Image,
    rotate_degrees: int = 0,
    crop_box: Optional[Tuple[int, int, int, int]] = None,
    remove_borders: bool = False,
    min_upscale: int = 1,
) -> Tuple[Image.Image, List[str]]:
    """
    Deterministic preprocessing pipeline for ultrasound machine printouts:
    1. Rotation correction
    2. Region of interest cropping (auto-detected worksheet or manual rectangle)
    3. Grayscale conversion
    4. Dark-mode auto-inversion (white text on black UI -> black text on light background)
    5. Optional intensity-safe table-border removal
    6. Adaptive contrast enhancement & Otsu analysis
    7. High-resolution upscaling preserving small decimal dots
    """
    applied_steps: List[str] = []
    processed = img.copy()

    if rotate_degrees % 360 != 0:
        processed = processed.rotate(-rotate_degrees, expand=True)
        applied_steps.append(f"rotate_{rotate_degrees}deg")

    if crop_box:
        x1, y1, x2, y2 = crop_box
        w, h = processed.size
        x1 = max(0, min(int(x1), w - 1))
        y1 = max(0, min(int(y1), h - 1))
        x2 = max(x1 + 1, min(int(x2), w))
        y2 = max(y1 + 1, min(int(y2), h))
        processed = processed.crop((x1, y1, x2, y2))
        applied_steps.append(f"crop_{x1}_{y1}_{x2}_{y2}")

    if processed.mode != "L":
        processed = processed.convert("L")
        applied_steps.append("grayscale")

    np_gray = np.array(processed)
    mean_lum = float(np.mean(np_gray))
    std_lum = float(np.std(np_gray))
    if mean_lum < 120.0:
        processed = ImageOps.invert(processed)
        applied_steps.append("dark_mode_inverted")

    if remove_borders:
        cleaned = remove_table_borders_inverted(np.array(processed))
        processed = Image.fromarray(cleaned)
        applied_steps.append("table_borders_removed")

    contrast_factor = 1.6 if std_lum < 35.0 else 1.25
    processed = ImageEnhance.Contrast(processed).enhance(contrast_factor)
    applied_steps.append(f"contrast_boost_{contrast_factor}x")

    threshold = _compute_otsu_threshold(np.array(processed))
    applied_steps.append(f"otsu_threshold_{threshold}")

    w, h = processed.size
    if w < 1000:
        scale, resample = max(min_upscale, 3 if crop_box else 4), Image.Resampling.LANCZOS if crop_box else Image.Resampling.BICUBIC
    elif w < 2200:
        scale, resample = max(min_upscale, 2), Image.Resampling.LANCZOS
    else:
        scale, resample = max(min_upscale, 1), Image.Resampling.LANCZOS

    if scale > 1:
        processed = processed.resize((w * scale, h * scale), resample)
        applied_steps.append(
            f"upscale_{scale}x_{'bicubic' if resample == Image.Resampling.BICUBIC else 'lanczos'}"
        )

    return processed, applied_steps
