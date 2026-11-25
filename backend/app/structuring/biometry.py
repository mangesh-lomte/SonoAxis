from typing import Optional, Dict, Any, List
from backend.app.schemas.structuring import MeasurementItem

def calculate_prostate_volume(measurements: List[MeasurementItem]) -> Optional[Dict[str, Any]]:
    """
    Computes prostate volume using the standard medical ellipsoidal formula:
    Volume (cc) = Length (cm) x Width (cm) x AP Height (cm) x 0.52
    
    Only computes when 3 dimensions in cm are explicitly available.
    Detects if a dictated volume exists and flags discrepancies.
    """
    three_d_item = None
    dictated_volume_cc = None

    for m in measurements:
        if m.dimension == 3 and isinstance(m.value, list) and len(m.value) == 3:
            if m.unit == "cm":
                three_d_item = m
        elif m.dimension == 1 and m.unit == "cc" and isinstance(m.value, (int, float)):
            dictated_volume_cc = float(m.value)

    if not three_d_item:
        return None

    l, w, ap = three_d_item.value
    calc_vol = round(l * w * ap * 0.52, 1)

    result = {
        "formula": "L (cm) x W (cm) x AP (cm) x 0.52",
        "dimensions_cm": [l, w, ap],
        "calculated_volume_cc": calc_vol,
        "is_calculated": True,
        "discrepancy_flag": False
    }

    if dictated_volume_cc is not None:
        result["dictated_volume_cc"] = dictated_volume_cc
        # Flag if difference is > 20%
        diff_pct = abs(calc_vol - dictated_volume_cc) / max(calc_vol, dictated_volume_cc, 1.0)
        if diff_pct > 0.20:
            result["discrepancy_flag"] = True
            result["discrepancy_note"] = f"Calculated volume ({calc_vol} cc) differs from dictated volume ({dictated_volume_cc} cc)"

    return result
