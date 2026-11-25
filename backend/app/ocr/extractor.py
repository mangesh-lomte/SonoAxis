import json
import os
import re
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from backend.app.schemas.ocr import OCRCandidateMeasurement, BoundingBox, OCRAssignableField

ALIASES_CONFIG_PATH = Path("D:/sovoice/data/config/ocr_aliases.json")

# Standard unit aliases (also matches unit glued onto digits like 14.2cm, 6.4mm)
UNIT_PATTERNS = {
    "cm/s": re.compile(r"(?:\d\s*)?(cm/s|cm/sec|cms/s|cm\s*/\s*s)\b", re.IGNORECASE),
    "m/s": re.compile(r"(?:\d\s*)?(m/s|m/sec|meters/s|meter/sec)\b", re.IGNORECASE),
    "mm": re.compile(r"(?:\d\s*)?(mm|millimeter|millimeters)\b", re.IGNORECASE),
    "cm": re.compile(r"(?:\d\s*)?(cm|centimeter|centimeters)\b", re.IGNORECASE),
    "cc": re.compile(r"(?:\d\s*)?(cc|cm3|cm\^3|cubic\s*cm)\b", re.IGNORECASE),
    "ml": re.compile(r"(?:\d\s*)?(ml|milliliter|milliliters)\b", re.IGNORECASE),
    "mmhg": re.compile(r"(?:\d\s*)?(mmhg|mm\s*hg)\b", re.IGNORECASE),
    "%": re.compile(r"%", re.IGNORECASE),
}

# Non-clinical ultrasound machine telemetry, headers, depth scale, and UI controls to exclude
NOISE_LINE_PATTERNS = [
    re.compile(r"\bSYNTHETIC\s+ULTRASOUND\s+WORKSHEET\b", re.IGNORECASE),
    re.compile(r"\b(?:UT-\d+|TP-\d+|MRN[-:\s]\w+|Image\s+\d+\s*/\s*\d+)\b", re.IGNORECASE),
    re.compile(r"\b(?:MI\s*\d+(?:\.\d+)?|TI[BS]?\s*\d+(?:\.\d+)?|FR\s*\d+|DR\s*\d+|G\s*\d+|\d+\s*Hz|C\d+-\d+)\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}[-/](?:Nov|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Dec|\d{2})[-/]\d{2,4}\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b"),
    re.compile(r"\bAge\s*[:;]?\s*\d+\s*[YM]?\b", re.IGNORECASE),
    re.compile(r"^\s*(?:1|2|3|4|5|6|7|8)\s+(?:Liver|GB|CBD|RK|LK|Spleen|Prostate|PVR)\b", re.IGNORECASE),
    re.compile(r"\b7\s*Prostate\b|\b8\s*PVR\b|\bProstate\s*[:;]?\s*8\b", re.IGNORECASE),
    re.compile(r"^\s*(?:D\s*)?15\.0\s*cm(?:\s+\d+\s*Hz)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*Worksheet\s*[:\-]?\s*(?:Abdomen|Pelvis|Completed|Report|Calc).*$", re.IGNORECASE),
    re.compile(r"^\s*Parameter\s+Value\s*$", re.IGNORECASE),
    re.compile(r"^\s*Measurements?\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:Add|Update|Edit|Delete|Clear|Measure|Calc|Report|Export|Review|Compare)\b", re.IGNORECASE),
    re.compile(r"^\s*[-=~+|.,_*\s\d]{1,12}\s*$"),
    re.compile(r"^\s*(?:1\s+)?Liver\s*[,;]?\s*2\s+GB\b", re.IGNORECASE),
]

# Configurable default anatomical mappings & clinical specificity rules
DEFAULT_ANATOMICAL_MAPPINGS: List[Dict[str, Any]] = [
    # Abdomen & Pelvis — Specific sub-dimensions first where distinct
    {
        "field": "gall_bladder",
        "canonical": "Gall Bladder Wall Thickness",
        "specificity": "wall_thickness",
        "patterns": [r"\b(gb\s*wall(?:\s*thickness)?|gall\s*bladder\s*wall(?:\s*thickness)?)\b"],
        "default_unit": "mm",
        "expected_dim": 1,
    },
    {
        "field": "gall_bladder",
        "canonical": "Gall Bladder",
        "patterns": [r"\b(gall\s*bladder|gb)\b"],
        "default_unit": "mm",
        "expected_dim": 1,
    },
    {
        "field": "cbd",
        "canonical": "Common Bile Duct",
        "specificity": "diameter",
        "patterns": [r"\b(cbd(?:\s*(?:diameter|caliber))?|common\s*bile\s*duct)\b"],
        "default_unit": "mm",
        "expected_dim": 1,
    },
    {
        "field": "liver",
        "canonical": "Liver",
        "specificity": "length",
        "patterns": [r"\b(liver(?:\s*length|\s*span)?|hepatic\s*span)\b"],
        "default_unit": "cm",
        "expected_dim": 1,
    },
    {
        "field": "right_kidney",
        "canonical": "Right Kidney Length",
        "specificity": "length",
        "patterns": [r"\b(?:right\s*kidney|rt\s*kidney|r\s*kidney|rk)\s+length\b"],
        "laterality": "right",
        "default_unit": "cm",
        "expected_dim": 1,
    },
    {
        "field": "right_kidney",
        "canonical": "Right Kidney AP Dimension",
        "specificity": "ap_dimension",
        "patterns": [r"\b(?:right\s*kidney|rt\s*kidney|r\s*kidney|rk)\s+ap(?:\s*dim(?:ension)?)?\b"],
        "laterality": "right",
        "default_unit": "cm",
        "expected_dim": 1,
    },
    {
        "field": "right_kidney",
        "canonical": "Right Kidney",
        "patterns": [r"\b(right\s*kidney|rt\s*kidney|r\s*kidney|rk(?:\s*width)?)\b"],
        "laterality": "right",
        "default_unit": "cm",
        "expected_dim": 2,
    },
    {
        "field": "left_kidney",
        "canonical": "Left Kidney Length",
        "specificity": "length",
        "patterns": [r"\b(?:left\s*kidney|lt\s*kidney|l\s*kidney|lk)\s+length\b"],
        "laterality": "left",
        "default_unit": "cm",
        "expected_dim": 1,
    },
    {
        "field": "left_kidney",
        "canonical": "Left Kidney AP Dimension",
        "specificity": "ap_dimension",
        "patterns": [r"\b(?:left\s*kidney|lt\s*kidney|l\s*kidney|lk)\s+ap(?:\s*dim(?:ension)?)?\b"],
        "laterality": "left",
        "default_unit": "cm",
        "expected_dim": 1,
    },
    {
        "field": "left_kidney",
        "canonical": "Left Kidney",
        "patterns": [r"\b(left\s*kidney|lt\s*kidney|l\s*kidney|lk(?:\s*width)?)\b"],
        "laterality": "left",
        "default_unit": "cm",
        "expected_dim": 2,
    },
    {
        "field": "kidneys_ambiguous",
        "canonical": "Kidney (Laterality Unspecified)",
        "patterns": [r"\b(kidney|renal\s*bipolar\s*length)\b"],
        "is_uncertain": True,
        "uncertainty_reason": "Unspecified kidney laterality (Right vs Left)",
        "default_unit": "cm",
    },
    {
        "field": "spleen",
        "canonical": "Spleen",
        "specificity": "length",
        "patterns": [r"\b(spleen(?:\s*length|\s*span)?|splenic\s*span|splenic\s*length)\b"],
        "default_unit": "cm",
        "expected_dim": 1,
    },
    {
        "field": "prostate",
        "canonical": "Prostate Volume",
        "specificity": "volume",
        "patterns": [r"\b(prostate\s*vol(?:ume)?|prostatic\s*vol(?:ume)?)\b"],
        "default_unit": "cc",
        "expected_dim": 1,
    },
    {
        "field": "prostate",
        "canonical": "Prostate",
        "specificity": "dimensions_3d",
        "patterns": [r"\b(prostate(?:\s*(?:size|dimensions))?)\b"],
        "default_unit": "cm",
        "expected_dim": 3,
    },
    {
        "field": "urinary_bladder",
        "canonical": "Post Void Residual",
        "specificity": "post_void_residual",
        "patterns": [r"\b((?:post\s*)?void\s*residual|pvr|post-void(?:\s*residual)?)\b"],
        "default_unit": "ml",
        "expected_dim": 1,
    },
    {
        "field": "urinary_bladder",
        "canonical": "Urinary Bladder",
        "patterns": [r"\b(urinary\s*bladder|bladder\s*wall|pre-void)\b"],
        "default_unit": "ml",
    },
    {
        "field": "pancreas",
        "canonical": "Pancreas",
        "patterns": [r"\b(pancreas|pancreatic\s*(?:head|body|tail|duct))\b"],
        "default_unit": "mm",
        "expected_dim": 1,
    },
    # Female Abdomen & Pelvis
    {
        "field": "uterus",
        "canonical": "Uterus",
        "patterns": [r"\b(uterus|uterine\s*dimensions|uterine\s*size)\b"],
        "default_unit": "cm",
        "expected_dim": 3,
    },
    {
        "field": "endometrium",
        "canonical": "Endometrial Thickness",
        "specificity": "thickness",
        "patterns": [r"\b(endometrial\s*thickness|endometrium|et)\b"],
        "default_unit": "mm",
        "expected_dim": 1,
    },
    {
        "field": "right_ovary",
        "canonical": "Right Ovary",
        "patterns": [r"\b(right\s*ovary|rt\s*ovary|r\s*ovary|ro)\b"],
        "laterality": "right",
        "default_unit": "cm",
        "expected_dim": 2,
    },
    {
        "field": "left_ovary",
        "canonical": "Left Ovary",
        "patterns": [r"\b(left\s*ovary|lt\s*ovary|l\s*ovary|lo)\b"],
        "laterality": "left",
        "default_unit": "cm",
        "expected_dim": 2,
    },
    # Lower Limb Arterial Doppler
    {
        "field": "arterial_cfa",
        "canonical": "Common Femoral Artery (CFA)",
        "patterns": [r"\b(common\s*femoral\s*artery|cfa|common\s*femoral)\b"],
        "is_arterial": True,
        "default_unit": "cm/s",
    },
    {
        "field": "arterial_sfa",
        "canonical": "Superficial Femoral Artery (SFA)",
        "patterns": [r"\b(superficial\s*femoral\s*artery|sfa|superficial\s*femoral)\b"],
        "is_arterial": True,
        "default_unit": "cm/s",
    },
    {
        "field": "arterial_popliteal",
        "canonical": "Popliteal Artery",
        "patterns": [r"\b(popliteal\s*artery|popliteal|pop\s*a)\b"],
        "is_arterial": True,
        "default_unit": "cm/s",
    },
    {
        "field": "arterial_ata",
        "canonical": "Anterior Tibial Artery (ATA)",
        "patterns": [r"\b(anterior\s*tibial\s*artery|anterior\s*tibial|ata)\b"],
        "is_arterial": True,
        "default_unit": "cm/s",
    },
    {
        "field": "arterial_pta",
        "canonical": "Posterior Tibial Artery (PTA)",
        "patterns": [r"\b(posterior\s*tibial\s*artery|posterior\s*tibial|pta)\b"],
        "is_arterial": True,
        "default_unit": "cm/s",
    },
    {
        "field": "arterial_peroneal",
        "canonical": "Peroneal Artery",
        "patterns": [r"\b(peroneal\s*artery|peroneal|per\s*a)\b"],
        "is_arterial": True,
        "default_unit": "cm/s",
    },
    # Lower Limb Venous Doppler
    {
        "field": "venous_gsv",
        "canonical": "Great Saphenous Vein (GSV)",
        "patterns": [r"(?:great\s*saphenous\s*vein|gs[v¥]|long\s*saphenous)(?:\b|(?=\W|$))"],
        "is_venous": True,
        "default_unit": "mm",
    },
    {
        "field": "venous_ssv",
        "canonical": "Small Saphenous Vein (SSV)",
        "patterns": [r"(?:small\s*saphenous\s*vein|ssv|short\s*saphenous)\b"],
        "is_venous": True,
        "default_unit": "mm",
    },
    {
        "field": "venous_perforator",
        "canonical": "Incompetent Perforator",
        "patterns": [r"\b(perforator|incompetent\s*perforator|cockett|boyd|dodd)\b"],
        "is_venous": True,
        "default_unit": "mm",
    },
]


def load_anatomical_mappings() -> List[Dict[str, Any]]:
    """
    Loads configurable anatomical alias mappings. Allows custom institutional aliases in
    D:/sovoice/data/config/ocr_aliases.json to prepend or extend DEFAULT_ANATOMICAL_MAPPINGS.
    """
    if ALIASES_CONFIG_PATH.is_file():
        try:
            custom = json.loads(ALIASES_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(custom, list):
                valid_custom = [
                    m for m in custom
                    if isinstance(m, dict) and m.get("field") and m.get("canonical") and m.get("patterns")
                ]
                return valid_custom + DEFAULT_ANATOMICAL_MAPPINGS
        except Exception:
            pass
    return DEFAULT_ANATOMICAL_MAPPINGS


# Backwards-compatible alias reference
ANATOMICAL_MAPPINGS = DEFAULT_ANATOMICAL_MAPPINGS


def get_assignable_target_fields() -> List[OCRAssignableField]:
    """
    Returns clean anatomical field options for manual mapping / reassignment in Clinical Review.
    """
    return [
        OCRAssignableField(field_key="liver", section_key="liver", label="Liver", default_unit="cm"),
        OCRAssignableField(field_key="gb_wall", section_key="gall_bladder", label="Gall Bladder Wall Thickness", default_unit="mm"),
        OCRAssignableField(field_key="gall_bladder", section_key="gall_bladder", label="Gall Bladder", default_unit="mm"),
        OCRAssignableField(field_key="cbd", section_key="cbd", label="Common Bile Duct", default_unit="mm"),
        OCRAssignableField(field_key="rk_length", section_key="right_kidney", label="Right Kidney Length", laterality="right", default_unit="cm"),
        OCRAssignableField(field_key="rk_ap", section_key="right_kidney", label="Right Kidney AP Dimension", laterality="right", default_unit="cm"),
        OCRAssignableField(field_key="right_kidney", section_key="right_kidney", label="Right Kidney (2D)", laterality="right", default_unit="cm"),
        OCRAssignableField(field_key="lk_length", section_key="left_kidney", label="Left Kidney Length", laterality="left", default_unit="cm"),
        OCRAssignableField(field_key="lk_ap", section_key="left_kidney", label="Left Kidney AP Dimension", laterality="left", default_unit="cm"),
        OCRAssignableField(field_key="left_kidney", section_key="left_kidney", label="Left Kidney (2D)", laterality="left", default_unit="cm"),
        OCRAssignableField(field_key="spleen", section_key="spleen", label="Spleen", default_unit="cm"),
        OCRAssignableField(field_key="prostate", section_key="prostate", label="Prostate (3D Dimensions)", default_unit="cm"),
        OCRAssignableField(field_key="prostate_volume", section_key="prostate", label="Prostate Volume", default_unit="cc"),
        OCRAssignableField(field_key="pvr", section_key="urinary_bladder", label="Post Void Residual", default_unit="ml"),
        OCRAssignableField(field_key="urinary_bladder", section_key="urinary_bladder", label="Urinary Bladder", default_unit="ml"),
        OCRAssignableField(field_key="pancreas", section_key="pancreas", label="Pancreas", default_unit="mm"),
        OCRAssignableField(field_key="uterus", section_key="uterus", label="Uterus", default_unit="cm"),
        OCRAssignableField(field_key="endometrium", section_key="endometrium", label="Endometrial Thickness", default_unit="mm"),
        OCRAssignableField(field_key="right_ovary", section_key="right_ovary", label="Right Ovary", laterality="right", default_unit="cm"),
        OCRAssignableField(field_key="left_ovary", section_key="left_ovary", label="Left Ovary", laterality="left", default_unit="cm"),
        OCRAssignableField(field_key="arterial_right_cfa", section_key="measurement_table", label="Right CFA PSV", laterality="right", default_unit="cm/s"),
        OCRAssignableField(field_key="arterial_left_cfa", section_key="measurement_table", label="Left CFA PSV", laterality="left", default_unit="cm/s"),
        OCRAssignableField(field_key="arterial_right_popliteal", section_key="measurement_table", label="Right Popliteal PSV", laterality="right", default_unit="cm/s"),
        OCRAssignableField(field_key="arterial_left_popliteal", section_key="measurement_table", label="Left Popliteal PSV", laterality="left", default_unit="cm/s"),
        OCRAssignableField(field_key="venous_right_gsv", section_key="gsv", label="Right Great Saphenous Vein (GSV)", laterality="right", default_unit="mm"),
        OCRAssignableField(field_key="venous_left_gsv", section_key="gsv", label="Left Great Saphenous Vein (GSV)", laterality="left", default_unit="mm"),
        OCRAssignableField(field_key="venous_perforator", section_key="perforators", label="Incompetent Perforator", default_unit="mm"),
    ]


WAVEFORM_PATTERNS = {
    "triphasic": re.compile(r"\b(triphasic|tri-phasic)\b", re.IGNORECASE),
    "biphasic": re.compile(r"\b(biphasic|bi-phasic)\b", re.IGNORECASE),
    "monophasic": re.compile(r"\b(monophasic|mono-phasic)\b", re.IGNORECASE),
}


def _is_noise_line(text: str) -> bool:
    for pat in NOISE_LINE_PATTERNS:
        if pat.search(text):
            return True
    return False


def _clean_ocr_text_fragment(raw_text: str) -> str:
    """Strips stray border pipe glyphs / leading dashes without altering decimal values or anatomical tokens."""
    cleaned = re.sub(r"[|¦]+", " ", raw_text)
    cleaned = re.sub(r"^\s*[-=~_*•]+\s*", "", cleaned)
    cleaned = re.sub(r"\s*[-=~_*]+\s*$", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def parse_extracted_numbers(
    text: str,
    value_segment: Optional[str] = None,
) -> Tuple[Optional[Union[float, List[float]]], int]:
    """
    Parses single numbers, 2D (L x W), or 3D (L x W x H) dimensions.
    Prioritizes numbers inside value_segment (text after anatomical label) and
    explicitly rejects ratio/timestamp fragments immediately preceded by ':' (like '2:1 mm').
    """
    target = value_segment if (value_segment and re.search(r"\d", value_segment)) else text

    # 3D pattern: e.g. 4.0 x 3.0 x 3.4 or 4.0x3.0x3.4cm
    m3 = re.search(
        r"(?<![:\d])(\d+(?:\.\d+)?)\s*(?:x|×|by|\*)\s*(\d+(?:\.\d+)?)\s*(?:x|×|by|\*)\s*(\d+(?:\.\d+)?)",
        target,
        re.IGNORECASE,
    )
    if not m3:
        m3 = re.search(
            r"(?<![:\d])(\d+\.\d+)(?:\s*[x×by*]\s*|\s+)(\d+\.\d+)(?:\s*[x×by*]\s*|\s+)(\d+\.\d+)(?=\s*(?:cm|mm|ml|cc|$))",
            target,
            re.IGNORECASE,
        )
    if m3:
        try:
            vals = [float(m3.group(1)), float(m3.group(2)), float(m3.group(3))]
            return vals, 3
        except ValueError:
            pass

    # 2D pattern: e.g. 10.8 x 4.5
    m2 = re.search(r"(?<![:\d])(\d+(?:\.\d+)?)\s*(?:x|×|by|\*)\s*(\d+(?:\.\d+)?)", target, re.IGNORECASE)
    if not m2:
        m2 = re.search(r"(?<![:\d])(\d+\.\d+)(?:\s*[x×by*]\s*|\s+)(\d+\.\d+)(?=\s*(?:cm|mm|ml|cc|$))", target, re.IGNORECASE)
    if m2:
        try:
            vals = [float(m2.group(1)), float(m2.group(2))]
            return vals, 2
        except ValueError:
            pass

    # 1D number right before an explicit measurement unit (guard against ':1 mm' clock/caliper glitches)
    m1_unit = re.search(
        r"(?<![:\d.])(\d+(?:\.\d+)?)\s*(?:cm/s|m/s|cm|mm|cc|ml|mmhg|%)\b",
        target,
        re.IGNORECASE,
    )
    if m1_unit:
        try:
            return float(m1_unit.group(1)), 1
        except ValueError:
            pass

    m1 = re.search(r"(?<![:\d.])(\d+(?:\.\d+)?)(?![:\d])", target)
    if m1:
        try:
            return float(m1.group(1)), 1
        except ValueError:
            pass

    return None, 1


def parse_unit(text: str, default_unit: str = "cm") -> Tuple[str, str]:
    """
    Extracts printed unit and returns (original_unit, normalized_unit).
    Performs dimensionally safe conversion (m/s -> cm/s).
    """
    for std_unit, pattern in UNIT_PATTERNS.items():
        if pattern.search(text):
            if std_unit == "m/s":
                return "m/s", "cm/s"
            return std_unit, std_unit
    return "", default_unit


def detect_laterality(text: str) -> Optional[str]:
    clean = text.lower()
    if re.search(r"\b(?:right|rt|rk)\b|^right(?=[a-z])|\br\s+kidney\b", clean):
        return "right"
    if re.search(r"\b(?:left|lt|lk)\b|^left(?=[a-z])|\bl\s+kidney\b", clean):
        return "left"
    if re.search(r"\b(bilateral|both)\b", clean):
        return "bilateral"
    return None


def _values_equal(v1: Any, v2: Any) -> bool:
    if isinstance(v1, list) and isinstance(v2, list):
        return len(v1) == len(v2) and all(abs(float(a) - float(b)) <= 0.05 for a, b in zip(v1, v2))
    if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
        return abs(float(v1) - float(v2)) <= 0.05
    return False


def _filter_annotation_duplicates(
    candidates: List[OCRCandidateMeasurement],
) -> Tuple[List[OCRCandidateMeasurement], int]:
    """
    Removes duplicate ultrasound B-mode annotation extractions when the corresponding
    measurement is already captured cleanly inside the worksheet table, while strictly
    preserving all genuine repeated worksheet/table measurements (e.g. multiple perforators,
    left vs right organ values).
    """
    table_cands = [c for c in candidates if c.source_zone == "worksheet_table" and c.proposed_destination_field != "unassigned"]
    if not table_cands:
        return candidates, 0

    kept: List[OCRCandidateMeasurement] = []
    filtered_count = 0

    for c in candidates:
        if c.source_zone == "ultrasound_annotation":
            is_dup = any(
                _values_equal(c.value, tc.value)
                and c.normalized_unit.lower() == tc.normalized_unit.lower()
                and (
                    c.proposed_destination_field == "unassigned"
                    or c.proposed_destination_field == tc.proposed_destination_field
                )
                for tc in table_cands
            )
            if is_dup:
                filtered_count += 1
                continue
        kept.append(c)

    return kept, filtered_count


def extract_candidates_from_text_lines(
    lines: List[Dict[str, Any]],
    source_document_id: str,
    existing_sections: Optional[List[Dict[str, Any]]] = None,
    worksheet_box: Optional[Dict[str, int]] = None,
    stats_out: Optional[Dict[str, int]] = None,
) -> List[OCRCandidateMeasurement]:
    """
    Scans OCR-recognized spatial rows/lines, maps them using configurable aliases with
    clinical specificity (wall thickness, length, AP dimension, laterality), filters noise
    & annotation duplicates, and always initializes candidates as 'pending'.
    """
    mappings = load_anatomical_mappings()
    candidates: List[OCRCandidateMeasurement] = []
    perforator_counter = 0

    existing_map: Dict[str, Any] = {}
    if existing_sections:
        for sec in existing_sections:
            sec_key = sec.get("key")
            raw_meas = sec.get("measurements") or []
            if raw_meas:
                first_m = raw_meas[0]
                existing_map[sec_key] = (
                    first_m.get("value") if isinstance(first_m, dict) else getattr(first_m, "value", None)
                )

    for line_item in lines:
        raw_text_orig = line_item.get("text", "").strip()
        raw_text = _clean_ocr_text_fragment(raw_text_orig)
        if not raw_text or len(raw_text) < 3:
            continue
        if _is_noise_line(raw_text):
            continue

        bbox_data = line_item.get("bbox")
        bbox = BoundingBox(**bbox_data) if bbox_data else None
        confidence = float(line_item.get("confidence", 0.95))

        # Determine zone if worksheet_box provided
        source_zone = line_item.get("source_zone")
        if not source_zone:
            if worksheet_box and bbox:
                cx = bbox.x + bbox.width / 2.0
                cy = bbox.y + bbox.height / 2.0
                inside = (
                    worksheet_box["x1"] - 10 <= cx <= worksheet_box["x2"] + 10
                    and worksheet_box["y1"] - 10 <= cy <= worksheet_box["y2"] + 10
                )
                source_zone = "worksheet_table" if inside else "ultrasound_annotation"
            else:
                source_zone = "worksheet_table"

        # Match against configurable anatomical mappings
        matched_mapping = None
        value_seg = None
        for mapping in mappings:
            for pat in mapping["patterns"]:
                m_anat = re.search(pat, raw_text, re.IGNORECASE)
                if m_anat:
                    matched_mapping = mapping
                    value_seg = raw_text[m_anat.end():]
                    break
            if matched_mapping:
                break

        val, dim = parse_extracted_numbers(raw_text, value_seg)
        if val is None:
            continue

        lat = detect_laterality(raw_text)

        waveform = None
        for wf_name, wf_pat in WAVEFORM_PATTERNS.items():
            if wf_pat.search(raw_text):
                waveform = wf_name
                break

        if not matched_mapping:
            orig_u, norm_u = parse_unit(raw_text, "unspecified")
            if orig_u == "":
                continue
            candidates.append(
                OCRCandidateMeasurement(
                    measurement_id=f"ocr-meas-{uuid.uuid4().hex[:8]}",
                    source_document_id=source_document_id,
                    raw_text=raw_text,
                    anatomical_label="Unassigned Measurement",
                    specificity=None,
                    value=val,
                    dimension=dim,
                    original_unit=orig_u,
                    normalized_unit=norm_u,
                    laterality=lat,
                    proposed_destination_field="unassigned",
                    bounding_box=bbox,
                    ocr_confidence=round(confidence, 2),
                    mapping_confidence=0.25,
                    is_uncertain=True,
                    uncertainty_reason="Unknown or unconfigured anatomical label — requires manual mapping",
                    source_zone=source_zone,
                    verification_status="pending",
                )
            )
            continue

        orig_unit, norm_unit = parse_unit(raw_text, matched_mapping.get("default_unit", "cm"))
        is_missing_unit = orig_unit == ""

        final_val = val
        if orig_unit == "m/s" and norm_unit == "cm/s" and isinstance(val, (int, float)):
            final_val = round(val * 100.0, 1)

        anat_label = matched_mapping["canonical"]
        specificity = matched_mapping.get("specificity")
        dest_field = matched_mapping["field"]

        # Refine volume / wall specificity if detected from value unit or modifier
        if dest_field == "prostate" and (norm_unit == "cc" or re.search(r"\bvol(?:ume)?\b", raw_text, re.IGNORECASE)):
            anat_label = "Prostate Volume"
            specificity = "volume"
        elif dest_field == "urinary_bladder" and re.search(r"\b(pvr|void\s*residual)\b", raw_text, re.IGNORECASE):
            anat_label = "Post Void Residual"
            specificity = "post_void_residual"

        final_lat = lat or matched_mapping.get("laterality")

        if matched_mapping.get("is_arterial"):
            segment = dest_field.replace("arterial_", "")
            dest_field = f"arterial_{final_lat or 'right'}_{segment}"
        elif matched_mapping.get("is_venous"):
            if dest_field == "venous_perforator":
                perforator_counter += 1
                dest_field = f"incompetent_perforator_{perforator_counter}"
            else:
                vessel = dest_field.replace("venous_", "")
                dest_field = f"venous_{final_lat or 'right'}_{vessel}"

        is_uncertain = False
        uncertainty_reasons = []
        if confidence < 0.70:
            is_uncertain = True
            uncertainty_reasons.append("Low OCR character confidence")
        if matched_mapping.get("is_uncertain"):
            is_uncertain = True
            uncertainty_reasons.append(matched_mapping.get("uncertainty_reason", "Ambiguous structure"))
        if is_missing_unit:
            is_uncertain = True
            uncertainty_reasons.append("Missing measurement unit")

        has_conflict = False
        existing_val = existing_map.get(matched_mapping["field"])
        if existing_val is not None:
            has_conflict = not _values_equal(existing_val, final_val)

        candidates.append(
            OCRCandidateMeasurement(
                measurement_id=f"ocr-meas-{uuid.uuid4().hex[:8]}",
                source_document_id=source_document_id,
                raw_text=raw_text,
                anatomical_label=anat_label,
                specificity=specificity,
                value=final_val,
                dimension=dim,
                original_unit=orig_unit or matched_mapping.get("default_unit", "cm"),
                normalized_unit=norm_unit,
                laterality=final_lat,
                proposed_destination_field=dest_field,
                bounding_box=bbox,
                ocr_confidence=round(confidence, 2),
                mapping_confidence=0.96 if not is_uncertain else 0.60,
                is_uncertain=is_uncertain,
                uncertainty_reason="; ".join(uncertainty_reasons) if uncertainty_reasons else None,
                existing_value=existing_val,
                has_conflict=has_conflict,
                waveform=waveform,
                source_zone=source_zone,
                verification_status="pending",
            )
        )

    deduped, filtered_dups = _filter_annotation_duplicates(candidates)
    if stats_out is not None:
        stats_out["filtered_duplicate_count"] = filtered_dups
    return deduped
