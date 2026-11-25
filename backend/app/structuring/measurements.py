import re
from typing import List, Tuple, Dict, Any, Optional
from backend.app.schemas.structuring import MeasurementItem

# Physiological bounds for common ultrasound findings (min_val, max_val in cm or mm)
PHYSIOLOGICAL_BOUNDS = {
    "liver_span_cm": (8.0, 22.0),
    "kidney_length_cm": (5.0, 16.0),
    "spleen_length_cm": (5.0, 18.0),
    "prostate_axis_cm": (1.0, 9.0),
    "uterus_axis_cm": (2.0, 15.0),
    "endometrium_mm": (1.0, 25.0),
    "cyst_mm": (1.0, 150.0)
}

# Regex for 3D measurements: e.g., "7.2 x 3.5 x 4.1 cm", "7.2 by 3.5 by 4.1 centimeters", "7.2*3.5*4.1cm"
REGEX_3D = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(?:x|by|\*)\s*(\d+(?:\.\d+)?)\s*(?:x|by|\*)\s*(\d+(?:\.\d+)?)\s*(cm|centimeters?|mm|millimeters?|cc)?\b",
    re.IGNORECASE
)

# Regex for 2D measurements: e.g., "10.2 x 4.5 cm", "10.2 by 4.5 centimeters"
REGEX_2D = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(?:x|by|\*)\s*(\d+(?:\.\d+)?)\s*(cm|centimeters?|mm|millimeters?|cc)?\b",
    re.IGNORECASE
)

# Regex for 1D measurements: e.g., "10.2 cm", "11 centimeters", "6 mm", "25 cc"
REGEX_1D = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(cm|centimeters?|mm|millimeters?|cc|cubic\s+centimeters?)\b",
    re.IGNORECASE
)

# Regex for numbers followed by 'measures' but missing unit: e.g., "measures 10.2"
REGEX_MISSING_UNIT = re.compile(
    r"\b(?:measures?|measuring|size\s+of|thickness\s+of|is)\s+(\d+(?:\.\d+)?)(?!\s*(?:cm|centimeters?|mm|millimeters?|cc|years?|y|months?|am|pm))\b",
    re.IGNORECASE
)

def normalize_unit(raw_unit: Optional[str]) -> Optional[str]:
    if not raw_unit:
        return None
    u = raw_unit.lower().strip()
    if u in ["cm", "centimeter", "centimeters"]:
        return "cm"
    if u in ["mm", "millimeter", "millimeters"]:
        return "mm"
    if u in ["cc", "cubic centimeter", "cubic centimeters"]:
        return "cc"
    return u

def extract_measurements(text: str) -> List[MeasurementItem]:
    """
    Extracts all measurements (1D, 2D, 3D) from text, normalizes units,
    and flags missing units or anomalous physiological values.
    """
    items: List[MeasurementItem] = []
    text_masked = text

    # 1. Check 3D measurements first
    for match in REGEX_3D.finditer(text):
        d1, d2, d3, raw_unit = match.groups()
        unit = normalize_unit(raw_unit)
        vals = [float(d1), float(d2), float(d3)]
        is_missing_unit = (unit is None)
        
        # Check physiological plausibility (e.g. > 50 cm for an abdominal organ is unusual)
        unusual = any(v > 50.0 for v in vals) if unit == "cm" else False

        items.append(MeasurementItem(
            value=vals,
            unit=unit,
            dimension=3,
            raw_str=match.group(0),
            flag_missing_unit=is_missing_unit,
            flag_unusual_value=unusual
        ))
        # Mask out matched string so smaller sub-patterns don't match
        text_masked = text_masked.replace(match.group(0), " " * len(match.group(0)))

    # 2. Check 2D measurements
    for match in REGEX_2D.finditer(text_masked):
        d1, d2, raw_unit = match.groups()
        unit = normalize_unit(raw_unit)
        vals = [float(d1), float(d2)]
        is_missing_unit = (unit is None)
        unusual = any(v > 50.0 for v in vals) if unit == "cm" else False

        items.append(MeasurementItem(
            value=vals,
            unit=unit,
            dimension=2,
            raw_str=match.group(0),
            flag_missing_unit=is_missing_unit,
            flag_unusual_value=unusual
        ))
        text_masked = text_masked.replace(match.group(0), " " * len(match.group(0)))

    # 3. Check 1D measurements with units
    for match in REGEX_1D.finditer(text_masked):
        val_str, raw_unit = match.groups()
        val = float(val_str)
        unit = normalize_unit(raw_unit)
        
        # Unusual check (e.g., liver > 25 cm or kidney > 20 cm)
        unusual = (val > 30.0 and unit == "cm") or (val > 250.0 and unit == "mm")

        items.append(MeasurementItem(
            value=val,
            unit=unit,
            dimension=1,
            raw_str=match.group(0),
            flag_missing_unit=False,
            flag_unusual_value=unusual
        ))
        text_masked = text_masked.replace(match.group(0), " " * len(match.group(0)))

    # 4. Check for numbers likely missing units
    for match in REGEX_MISSING_UNIT.finditer(text_masked):
        val_str = match.group(1)
        val = float(val_str)
        items.append(MeasurementItem(
            value=val,
            unit=None,
            dimension=1,
            raw_str=match.group(0),
            flag_missing_unit=True,
            flag_unusual_value=False
        ))

    return items
