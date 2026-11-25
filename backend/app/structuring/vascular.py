import re
import uuid
from typing import List, Dict, Any, Optional, Tuple
from backend.app.schemas.structuring import IncompetentPerforatorItem, ArterialSegmentBiometry
from backend.app.structuring.templates import STANDARD_ARTERIAL_SEGMENTS

REGEX_PERFORATOR_NUM = re.compile(r"(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE)
REGEX_DISTANCE_CM = re.compile(r"(\d+(?:\.\d+)?)\s*cm", re.IGNORECASE)
REGEX_LANDMARK = re.compile(
    r"\b(above\s+ankle|below\s+knee|near\s+ankle|at\s+(?:the\s+level\s+of\s+)?ankle|in\s+mid-?calf(?: region)?|in\s+mid-?leg|mid-?calf|mid-?leg)\b",
    re.IGNORECASE
)
REGEX_ASPECT = re.compile(
    r"\b(medial|lateral|posterior|anterior|anteromedial|posteromedial|posterolateral)(?:\s+aspect)?\b",
    re.IGNORECASE
)
REGEX_LATERALITY = re.compile(r"\b(right|left|bilateral)\b", re.IGNORECASE)

ARTERY_KEY_ALIASES: Dict[str, List[str]] = {
    "cfa": ["common femoral artery", "common femoral", "cfa"],
    "sfa": ["superficial femoral artery", "superficial femoral", "sfa"],
    "dfa": ["deep femoral artery", "profunda femoris", "profunda", "dfa"],
    "popliteal": ["popliteal artery", "popliteal"],
    "ata": ["anterior tibial artery", "anterior tibial", "ata"],
    "pta": ["posterior tibial artery", "posterior tibial", "pta"],
    "dpa": ["dorsalis pedis artery", "dorsalis pedis", "dpa"]
}

WAVEFORM_REGEX = re.compile(r"\b(triphasic|biphasic|monophasic|absent|damped|aliasing)\b", re.IGNORECASE)
PSV_REGEX = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:cm\s*/\s*s(?:ec)?|cm\s+per\s+second|psv)?\b", re.IGNORECASE)


def parse_incompetent_perforators(
    clauses: List[str],
    default_laterality: Optional[str] = None,
    existing_perforators: Optional[List[Any]] = None
) -> List[IncompetentPerforatorItem]:
    """
    Extracts repeatable incompetent perforator entries from clauses.
    Handles compound sentences containing multiple perforators separated by conjunctions or commas.
    Captures diameter in mm, anatomical aspect, distance in cm, and reference landmark.
    Preserves existing perforators across multi-recording sessions.
    """
    perforators: List[IncompetentPerforatorItem] = []
    if existing_perforators:
        for p in existing_perforators:
            if isinstance(p, IncompetentPerforatorItem):
                perforators.append(p)
            elif isinstance(p, dict):
                perforators.append(IncompetentPerforatorItem(**p))

    current_side = default_laterality

    for clause in clauses:
        c_lower = clause.lower()

        # Track side context (e.g. "Left leg:", "Right leg:", "Left lower limb:")
        if "left leg" in c_lower or "left lower limb" in c_lower or "left:" in c_lower:
            current_side = "left"
        elif "right leg" in c_lower or "right lower limb" in c_lower or "right:" in c_lower:
            current_side = "right"

        # Check if clause relates to perforator or has caliber in mm with landmark
        is_perf_keyword = any(kw in c_lower for kw in ["perforator", "perforators", "gsv", "ssv", "aspect", "ankle", "knee", "leg", "calf"])
        all_mm_matches = list(REGEX_PERFORATOR_NUM.finditer(clause))

        if all_mm_matches and is_perf_keyword:
            # If multiple perforators are mentioned in a single clause, split into sub-segments
            if len(all_mm_matches) > 1:
                sub_segments = re.split(r"[,;]\s*(?:and\s+)?|\s+and\s+", clause)
            else:
                sub_segments = [clause]

            for seg in sub_segments:
                seg_lower = seg.lower()
                diam_match = REGEX_PERFORATOR_NUM.search(seg)
                if not diam_match:
                    continue

                diam_val = float(diam_match.group(1))
                # Only consider physiological perforator sizes (typically 1.0 mm - 20.0 mm)
                if 1.0 <= diam_val <= 20.0:
                    dist_match = REGEX_DISTANCE_CM.search(seg)
                    dist_val = float(dist_match.group(1)) if dist_match else None

                    lm_match = REGEX_LANDMARK.search(seg)
                    landmark = lm_match.group(0).strip() if lm_match else None

                    asp_match = REGEX_ASPECT.search(seg)
                    aspect = asp_match.group(1).lower() if asp_match else None

                    clause_lat = None
                    if re.search(r"\bright\b", seg_lower):
                        clause_lat = "right"
                    elif re.search(r"\bleft\b", seg_lower):
                        clause_lat = "left"
                    final_lat = clause_lat or current_side

                    item_id = str(uuid.uuid4())[:8]
                    perforators.append(IncompetentPerforatorItem(
                        id=item_id,
                        laterality=final_lat,
                        diameter_mm=diam_val,
                        aspect=aspect,
                        landmark=landmark,
                        distance_cm=dist_val,
                        raw_str=seg.strip()
                    ))

    return perforators


def parse_arterial_biometry(
    clauses: List[str],
    laterality: str = "bilateral",
    existing_biometry: Optional[List[Any]] = None
) -> List[ArterialSegmentBiometry]:
    """
    Parses segment-by-segment and batch arterial waveforms and peak systolic velocities (PSV).
    Maintains the standard 7-segment lower limb arterial tree.
    Preserves and updates existing biometry across multi-recording sessions.
    """
    biometry_map: Dict[str, Dict[str, Any]] = {}
    for seg in STANDARD_ARTERIAL_SEGMENTS:
        biometry_map[seg["key"]] = {
            "key": seg["key"],
            "name": seg["name"],
            "psv_right": None,
            "psv_left": None,
            "flow_pattern_right": "Triphasic",
            "flow_pattern_left": "Triphasic"
        }

    if existing_biometry:
        for item in existing_biometry:
            k = item.segment_key if hasattr(item, "segment_key") else item.get("segment_key")
            if k in biometry_map:
                p_r = item.psv_right if hasattr(item, "psv_right") else item.get("psv_right")
                p_l = item.psv_left if hasattr(item, "psv_left") else item.get("psv_left")
                f_r = item.flow_pattern_right if hasattr(item, "flow_pattern_right") else item.get("flow_pattern_right")
                f_l = item.flow_pattern_left if hasattr(item, "flow_pattern_left") else item.get("flow_pattern_left")
                if p_r is not None:
                    biometry_map[k]["psv_right"] = p_r
                if p_l is not None:
                    biometry_map[k]["psv_left"] = p_l
                if f_r is not None:
                    biometry_map[k]["flow_pattern_right"] = f_r
                if f_l is not None:
                    biometry_map[k]["flow_pattern_left"] = f_l

    # Macro wave check: "all arteries show normal triphasic flow pattern"
    for clause in clauses:
        c_lower = clause.lower()
        if "all" in c_lower and ("arteries" in c_lower or "artery" in c_lower):
            wave_match = WAVEFORM_REGEX.search(clause)
            if wave_match:
                wave_val = wave_match.group(1).capitalize()
                for seg_key in biometry_map:
                    biometry_map[seg_key]["flow_pattern_right"] = wave_val
                    biometry_map[seg_key]["flow_pattern_left"] = wave_val

    # Granular segment check
    current_side = "right" if laterality == "right" else ("left" if laterality == "left" else None)

    for clause in clauses:
        c_lower = clause.lower()
        if "right leg" in c_lower or "right lower limb" in c_lower:
            current_side = "right"
        elif "left leg" in c_lower or "left lower limb" in c_lower:
            current_side = "left"

        matched_seg_key = None
        for key, aliases in ARTERY_KEY_ALIASES.items():
            if any(re.search(r"\b" + re.escape(alias) + r"\b", c_lower) for alias in aliases):
                matched_seg_key = key
                break

        if not matched_seg_key:
            continue

        # Extract waveform
        raw_wave_matches = WAVEFORM_REGEX.findall(clause)
        primary_waves = [w.capitalize() for w in raw_wave_matches if w.lower() in ["triphasic", "biphasic", "monophasic", "absent"]]
        if not primary_waves and raw_wave_matches:
            primary_waves = [w.capitalize() for w in raw_wave_matches]

        # Extract PSV numeric values
        psv_matches = re.findall(r"\b(\d+(?:\.\d+)?)\b", clause)
        plausible_psvs = [float(v) for v in psv_matches if 15.0 <= float(v) <= 500.0]

        is_right = "right" in c_lower or (current_side == "right")
        is_left = "left" in c_lower or (current_side == "left")

        # Handle velocities
        if "right" in c_lower and "left" in c_lower and len(plausible_psvs) >= 2:
            biometry_map[matched_seg_key]["psv_right"] = plausible_psvs[0]
            biometry_map[matched_seg_key]["psv_left"] = plausible_psvs[1]
        elif len(plausible_psvs) >= 2 and not is_left and not is_right:
            biometry_map[matched_seg_key]["psv_right"] = plausible_psvs[0]
            biometry_map[matched_seg_key]["psv_left"] = plausible_psvs[1]
        elif len(plausible_psvs) >= 1:
            val = plausible_psvs[0]
            if is_left and not is_right:
                biometry_map[matched_seg_key]["psv_left"] = val
            elif is_right and not is_left:
                biometry_map[matched_seg_key]["psv_right"] = val
            else:
                if laterality == "left":
                    biometry_map[matched_seg_key]["psv_left"] = val
                else:
                    biometry_map[matched_seg_key]["psv_right"] = val

        # Handle waveforms
        if "right" in c_lower and "left" in c_lower and len(primary_waves) >= 2:
            biometry_map[matched_seg_key]["flow_pattern_right"] = primary_waves[0]
            biometry_map[matched_seg_key]["flow_pattern_left"] = primary_waves[1]
        elif len(primary_waves) >= 1:
            w_val = primary_waves[0]
            if is_left and not is_right:
                biometry_map[matched_seg_key]["flow_pattern_left"] = w_val
            elif is_right and not is_left:
                biometry_map[matched_seg_key]["flow_pattern_right"] = w_val
            else:
                if laterality == "left":
                    biometry_map[matched_seg_key]["flow_pattern_left"] = w_val
                elif laterality == "right":
                    biometry_map[matched_seg_key]["flow_pattern_right"] = w_val
                else:
                    biometry_map[matched_seg_key]["flow_pattern_right"] = w_val
                    biometry_map[matched_seg_key]["flow_pattern_left"] = w_val

    output: List[ArterialSegmentBiometry] = []
    for seg in STANDARD_ARTERIAL_SEGMENTS:
        d = biometry_map[seg["key"]]
        output.append(ArterialSegmentBiometry(
            segment_key=d["key"],
            segment_name=d["name"],
            psv_right=d["psv_right"],
            psv_left=d["psv_left"],
            flow_pattern_right=d["flow_pattern_right"],
            flow_pattern_left=d["flow_pattern_left"]
        ))
    return output


def format_arterial_table_text(
    biometry: List[ArterialSegmentBiometry],
    table_type: str = "arterial_5col_table",
    laterality: str = "bilateral"
) -> str:
    """
    Renders visual tab-stop text for arterial measurement tables.
    Used for preview and text fallback.
    """
    lines: List[str] = []
    if table_type in ["arterial_3col_tabs", "arterial_3col_table"] or laterality in ["right", "left"]:
        lines.append(f"{'ARTERY':<35} {'PSV (cm/sec)':<18} {'FLOW PATTERN'}")
        lines.append("-" * 68)
        for item in biometry:
            psv = item.psv_left if laterality == "left" else item.psv_right
            flow = item.flow_pattern_left if laterality == "left" else item.flow_pattern_right
            psv_str = f"{psv:.2f}" if psv is not None else "-"
            flow_str = flow or "Triphasic"
            lines.append(f"{item.segment_name:<35} {psv_str:<18} {flow_str}")
    else:
        # 5-column bilateral
        lines.append(f"{'ARTERY':<30} {'PSV Right':<12} {'PSV Left':<12} {'Flow Right':<14} {'Flow Left'}")
        lines.append("-" * 80)
        for item in biometry:
            psv_r = f"{item.psv_right:.2f}" if item.psv_right is not None else "-"
            psv_l = f"{item.psv_left:.2f}" if item.psv_left is not None else "-"
            flow_r = item.flow_pattern_right or "Triphasic"
            flow_l = item.flow_pattern_left or "Triphasic"
            lines.append(f"{item.segment_name:<30} {psv_r:<12} {psv_l:<12} {flow_r:<14} {flow_l}")
    return "\n".join(lines)


def format_perforators_text(
    perforators: List[IncompetentPerforatorItem],
    laterality: str = "bilateral"
) -> str:
    """
    Renders formatted incompetent perforator entries grouped by laterality.
    """
    if not perforators:
        return "No incompetent perforators identified."

    right_perfs = [p for p in perforators if p.laterality == "right"]
    left_perfs = [p for p in perforators if p.laterality == "left"]
    unspec_perfs = [p for p in perforators if p.laterality not in ["right", "left"]]

    def _format_item(p: IncompetentPerforatorItem) -> str:
        parts = [f"{p.diameter_mm:.1f} mm"]
        if p.distance_cm:
            parts.append(f"about {p.distance_cm:.0f} cm")
        if p.landmark:
            parts.append(p.landmark)
        if p.aspect:
            parts.append(f"on {p.aspect} aspect")
        return " - " + " ".join(parts) + "."

    lines: List[str] = []
    if right_perfs and (laterality in ["bilateral", "right"]):
        lines.append("Right Lower Limb:")
        for p in right_perfs:
            lines.append(_format_item(p))

    if left_perfs and (laterality in ["bilateral", "left"]):
        if lines:
            lines.append("")
        lines.append("Left Lower Limb:")
        for p in left_perfs:
            lines.append(_format_item(p))

    if unspec_perfs:
        if lines:
            lines.append("")
        for p in unspec_perfs:
            lines.append(_format_item(p))

    return "\n".join(lines)
