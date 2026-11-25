import math
from typing import Optional, List, Dict, Any
from backend.app.schemas.structuring import MeasurementItem

PROSTATE_ELLIPSOID_COEFFICIENT = 0.523  # pi / 6
UTERINE_ELLIPSOID_COEFFICIENT = 0.523   # pi / 6

def calculate_prostate_volume(measurements: List[MeasurementItem]) -> Optional[Dict[str, Any]]:
    """
    Computes prostate volume using the validated prolate ellipsoid formula:
    Volume (cc) = Length (cm) * Width (cm) * Height (cm) * 0.523
    Clinical Reference: Terris MK, Stamey TA. Determination of prostate volume by transrectal ultrasound. J Urol. 1991.
    """
    three_d_item = None
    dictated_volume_cc = None

    for m in measurements:
        if m.dimension == 3:
            vals = m.value if isinstance(m.value, list) else []
            if len(vals) == 3:
                three_d_item = m
        elif m.dimension == 1 and (m.unit or "").lower() == "cc":
            v = m.value if isinstance(m.value, (int, float)) else (m.value[0] if isinstance(m.value, list) and m.value else None)
            if v is not None:
                dictated_volume_cc = float(v)

    if not three_d_item:
        return None

    l, w, h = three_d_item.value
    unit = (three_d_item.unit or "cm").lower()
    factor = 0.1 if unit in ["mm", "millimeter", "millimeters"] else 1.0
    l_cm, w_cm, h_cm = l * factor, w * factor, h * factor

    vol_052 = round(l_cm * w_cm * h_cm * 0.52, 1)
    vol_0523 = round(l_cm * w_cm * h_cm * PROSTATE_ELLIPSOID_COEFFICIENT, 2)

    res = {
        "volume_cc": vol_0523,
        "calculated_volume_cc": vol_052,
        "formula": "Volume (cc) = Length * Width * Height * 0.523",
        "clinical_source": "Terris & Stamey (1991)",
        "dimensions_cm": [round(l_cm, 2), round(w_cm, 2), round(h_cm, 2)],
        "input_dimensions_cm": [round(l_cm, 2), round(w_cm, 2), round(h_cm, 2)],
        "is_calculated": True,
        "discrepancy_flag": False,
        "source_type": "calculation"
    }

    if dictated_volume_cc is not None:
        res["dictated_volume_cc"] = dictated_volume_cc
        diff_pct = abs(vol_0523 - dictated_volume_cc) / max(vol_0523, dictated_volume_cc, 1.0)
        if diff_pct > 0.20:
            res["discrepancy_flag"] = True
            res["discrepancy_note"] = f"Calculated volume ({vol_0523} cc) differs from dictated volume ({dictated_volume_cc} cc)"

    return res

def calculate_uterine_volume(measurements: List[MeasurementItem]) -> Optional[Dict[str, Any]]:
    """
    Computes uterine volume using the validated prolate ellipsoid formula:
    Volume (cc) = Length (cm) * Anteroposterior (cm) * Transverse (cm) * 0.523
    Clinical Reference: Merz E et al. Sonographic size of uterus and ovaries. Ultrasound Obstet Gynecol. 1996.
    """
    three_d_item = None
    dictated_volume_cc = None

    for m in measurements:
        if m.dimension == 3:
            vals = m.value if isinstance(m.value, list) else []
            if len(vals) == 3:
                three_d_item = m
        elif m.dimension == 1 and (m.unit or "").lower() == "cc":
            v = m.value if isinstance(m.value, (int, float)) else (m.value[0] if isinstance(m.value, list) and m.value else None)
            if v is not None:
                dictated_volume_cc = float(v)

    if not three_d_item:
        return None

    l, ap, tr = three_d_item.value
    unit = (three_d_item.unit or "cm").lower()
    factor = 0.1 if unit in ["mm", "millimeter", "millimeters"] else 1.0
    l_cm, ap_cm, tr_cm = l * factor, ap * factor, tr * factor

    vol_052 = round(l_cm * ap_cm * tr_cm * 0.52, 1)
    vol_0523 = round(l_cm * ap_cm * tr_cm * UTERINE_ELLIPSOID_COEFFICIENT, 2)

    res = {
        "volume_cc": vol_0523,
        "calculated_volume_cc": vol_052,
        "formula": "Volume (cc) = Length * AP * Transverse * 0.523",
        "clinical_source": "Merz et al. (1996)",
        "dimensions_cm": [round(l_cm, 2), round(ap_cm, 2), round(tr_cm, 2)],
        "input_dimensions_cm": [round(l_cm, 2), round(ap_cm, 2), round(tr_cm, 2)],
        "is_calculated": True,
        "discrepancy_flag": False,
        "source_type": "calculation"
    }

    if dictated_volume_cc is not None:
        res["dictated_volume_cc"] = dictated_volume_cc
        diff_pct = abs(vol_0523 - dictated_volume_cc) / max(vol_0523, dictated_volume_cc, 1.0)
        if diff_pct > 0.20:
            res["discrepancy_flag"] = True
            res["discrepancy_note"] = f"Calculated volume ({vol_0523} cc) differs from dictated volume ({dictated_volume_cc} cc)"

    return res

def calculate_carotid_velocity_ratio(ica_psv: Optional[float], cca_psv: Optional[float]) -> Optional[Dict[str, Any]]:
    """
    Computes the Internal Carotid Artery (ICA) to Common Carotid Artery (CCA) Peak Systolic Velocity Ratio:
    Ratio = PSV(ICA) / PSV(CCA)
    Clinical Reference: Society of Radiologists in Ultrasound (SRU) Consensus Criteria for Carotid Artery Stenosis. Radiology. 2003.
    """
    if ica_psv is not None and cca_psv is not None and cca_psv > 0:
        ratio = ica_psv / cca_psv
        return {
            "ratio": round(ratio, 2),
            "formula": "ICA/CCA Ratio = PSV(ICA) / PSV(CCA)",
            "clinical_source": "SRU Consensus Criteria (2003)",
            "input_velocities_cm_s": {"ica_psv": ica_psv, "cca_psv": cca_psv},
            "source_type": "calculation"
        }
    return None

def calculate_ankle_brachial_index(
    ankle_pressure: Optional[float] = None,
    brachial_pressure: Optional[float] = None,
    dorsalis_pedis_pressure: Optional[float] = None,
    posterior_tibial_pressure: Optional[float] = None,
    right_brachial_pressure: Optional[float] = None,
    left_brachial_pressure: Optional[float] = None,
    unit: str = "mmHg"
) -> Optional[Dict[str, Any]]:
    """
    Computes the Ankle-Brachial Index (ABI) per clinical guidelines:
    ABI = Highest Ankle Systolic Blood Pressure (mmHg) / Highest Brachial Systolic Blood Pressure (mmHg)
    
    Clinical Reference:
    2024 ACC/AHA Guideline for the Management of Lower Extremity Peripheral Artery Disease.
    Circulation. 2024;150:e1-e120. (https://www.ahajournals.org/doi/full/10.1161/CIR.0000000000001251)
    
    Clinical Safety Rules:
    - Must strictly use systolic blood pressure in mmHg (or compatible pressure units).
    - NEVER substitute Peak Systolic Velocity (PSV in cm/s or m/s) for blood pressure.
    - If inputs are missing, incompatible units, zero, or non-physiological, return None (leave blank).
    - Never infer a clinical diagnosis (e.g. ischemia or PAD severity) from the calculated ratio.
    """
    # Strict unit validation: reject any velocity or non-pressure units
    normalized_unit = (unit or "").strip().lower()
    if normalized_unit in ["cm/s", "m/s", "cm", "mm", "cc", "ml"]:
        # Incompatible unit: velocity or distance cannot be used for ABI
        return None

    # Determine highest ankle pressure (higher of DP or PT systolic pressure)
    effective_ankle: Optional[float] = None
    if dorsalis_pedis_pressure is not None or posterior_tibial_pressure is not None:
        valid_ankle_pressures = [
            p for p in [dorsalis_pedis_pressure, posterior_tibial_pressure]
            if p is not None and 20.0 <= p <= 320.0
        ]
        if valid_ankle_pressures:
            effective_ankle = max(valid_ankle_pressures)
    elif ankle_pressure is not None and 20.0 <= ankle_pressure <= 320.0:
        effective_ankle = float(ankle_pressure)

    # Determine highest brachial pressure (higher of right or left brachial systolic pressure)
    effective_brachial: Optional[float] = None
    if right_brachial_pressure is not None or left_brachial_pressure is not None:
        valid_brachial_pressures = [
            p for p in [right_brachial_pressure, left_brachial_pressure]
            if p is not None and 40.0 <= p <= 320.0
        ]
        if valid_brachial_pressures:
            effective_brachial = max(valid_brachial_pressures)
    elif brachial_pressure is not None and 40.0 <= brachial_pressure <= 320.0:
        effective_brachial = float(brachial_pressure)

    # Both valid pressures in mmHg are strictly required
    if effective_ankle is not None and effective_brachial is not None and effective_brachial > 0:
        abi_val = round(effective_ankle / effective_brachial, 2)
        return {
            "abi": abi_val,
            "formula": "ABI = Highest Ankle Systolic Pressure (mmHg) / Highest Brachial Systolic Pressure (mmHg)",
            "clinical_source": "2024 ACC/AHA / AHA/ACC Lower Extremity PAD Guideline",
            "input_pressures_mmhg": {
                "highest_ankle": effective_ankle,
                "highest_brachial": effective_brachial
            },
            "source_type": "calculation"
        }

    return None

def recalculate_report_calculations(structured_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scans structured sections and updates clinical calculated biometry.
    Recalculates when measurements change; clears calculated biometry if inputs missing.
    Never infers clinical diagnosis from calculated values.
    """
    sections = structured_data.get("sections") or []
    for sec in sections:
        sec_key = sec.get("key")
        raw_meas = sec.get("measurements") or []
        items = []
        for rm in raw_meas:
            if isinstance(rm, dict):
                items.append(MeasurementItem(**rm))
            elif isinstance(rm, MeasurementItem):
                items.append(rm)

        if sec_key == "prostate":
            sec["calculated_biometry"] = calculate_prostate_volume(items)
        elif sec_key == "uterus":
            sec["calculated_biometry"] = calculate_uterine_volume(items)

    return structured_data
