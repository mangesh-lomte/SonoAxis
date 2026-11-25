import re
from typing import Optional, Tuple, List, Dict, Any
from backend.app.schemas.structuring import FindingItem, SupersededFinding, MeasurementItem
from backend.app.structuring.organ_matcher import identify_organ
from backend.app.structuring.measurements import extract_measurements

# Correction triggers
REGEX_CORRECTION_TRIGGER = re.compile(
    r"\b(correction:?|corrected:?|correct\s+(?:that|this|and)?|sorry:?,?|scratch\s+that:?,?|replace\s+with|make\s+that|I\s+mean|rather|not\s+(?:\d+(?:\.\d+)?))\b",
    re.IGNORECASE
)

# Inline negation of previous number: e.g. "measures 10.8 cm, not 10.2 cm"
REGEX_INLINE_NOT = re.compile(
    r"(.*?)(?:,\s*)?\bnot\s+(\d+(?:\.\d+)?\s*(?:cm|mm)?)\b",
    re.IGNORECASE
)

def is_correction_clause(text: str) -> Tuple[bool, Optional[str], str]:
    """
    Checks if a clause is an explicit correction.
    Returns (is_corr, trigger_str, stripped_content).
    """
    match = REGEX_CORRECTION_TRIGGER.search(text)
    if not match:
        return False, None, text

    trigger = match.group(0)
    # Strip the trigger from the content
    # e.g. "correction, right kidney measures 10.8 cm" -> "right kidney measures 10.8 cm"
    clean_text = REGEX_CORRECTION_TRIGGER.sub("", text).strip(" ,:.-")
    return True, trigger, clean_text

def resolve_explicit_correction(
    correction_clause: str,
    trigger_str: str,
    active_findings: Dict[str, List[FindingItem]],
    last_dictated_organ: Optional[str],
    audio_id: Optional[str] = None,
    t_start: Optional[float] = None,
    t_end: Optional[float] = None,
    transcript_source: str = "voice"
) -> Tuple[Optional[str], Optional[FindingItem], Optional[SupersededFinding], bool]:
    """
    Resolves an explicit correction.
    Determines the target organ, extracts corrected finding, supersedes the old measurement/finding,
    and returns:
      (target_organ_key, new_finding, superseded_audit_item, is_ambiguous)

    Safety Rules:
    - If the correction clause explicitly names an organ, that organ is the target.
    - If the correction clause does NOT name an organ:
      - If active_findings has exactly one organ with findings, resolve to that organ.
      - If active_findings has multiple organs (or zero), the target is ambiguous;
        flag for clinical review to prevent silent overwriting of unrelated findings.
    """
    if not correction_clause.strip():
        return None, None, None, True

    # 1. Determine target organ
    target_organ, matched_term = identify_organ(correction_clause)
    if not target_organ:
        active_organs_with_findings = [k for k, v in active_findings.items() if v]
        if len(active_organs_with_findings) == 1:
            target_organ = active_organs_with_findings[0]
        else:
            # Ambiguous correction target: multiple candidates or no context
            # Do NOT guess or overwrite. Flag for clinical review.
            return None, None, None, True

    # 2. Extract new measurements from the correction clause
    new_measurements = extract_measurements(correction_clause)
    
    # Check if there is an existing finding for target_organ that has measurements
    superseded_item = None
    existing_list = active_findings.get(target_organ, [])
    resolved_text = correction_clause
    
    if new_measurements and existing_list:
        # We find an existing finding on this organ that had measurements
        for i, existing in enumerate(existing_list):
            if existing.measurements:
                old_meas = existing.measurements[0]
                new_meas = new_measurements[0]

                # Check for single-dimension update on multi-dimensional measurement
                # e.g. old was 10.2 x 4.5 cm (2D) and new is 10.8 cm (1D)
                new_v0 = new_meas.value if isinstance(new_meas.value, (int, float)) else new_meas.value[0]
                if old_meas.dimension == 2 and new_meas.dimension == 1:
                    old_v1 = old_meas.value[1] if isinstance(old_meas.value, list) and len(old_meas.value) > 1 else 0.0
                    merged_vals = [new_v0, old_v1]
                    merged_unit = new_meas.unit or old_meas.unit
                    merged_str = f"{merged_vals[0]} x {merged_vals[1]} {merged_unit}"
                    new_meas_item = MeasurementItem(
                        value=merged_vals,
                        unit=merged_unit,
                        dimension=2,
                        raw_str=merged_str,
                        flag_missing_unit=False,
                        flag_unusual_value=False
                    )
                    new_measurements = [new_meas_item]
                    resolved_text = f"{target_organ.replace('_', ' ').title()} measures {merged_str}"
                elif old_meas.dimension == 3 and new_meas.dimension == 1:
                    old_v1 = old_meas.value[1] if isinstance(old_meas.value, list) and len(old_meas.value) > 1 else 0.0
                    old_v2 = old_meas.value[2] if isinstance(old_meas.value, list) and len(old_meas.value) > 2 else 0.0
                    merged_vals = [new_v0, old_v1, old_v2]
                    merged_unit = new_meas.unit or old_meas.unit
                    merged_str = f"{merged_vals[0]} x {merged_vals[1]} x {merged_vals[2]} {merged_unit}"
                    new_meas_item = MeasurementItem(
                        value=merged_vals,
                        unit=merged_unit,
                        dimension=3,
                        raw_str=merged_str,
                        flag_missing_unit=False,
                        flag_unusual_value=False
                    )
                    new_measurements = [new_meas_item]
                    resolved_text = f"{target_organ.replace('_', ' ').title()} measures {merged_str}"

                # This existing finding is superseded by the new measurement
                superseded_item = SupersededFinding(
                    organ_key=target_organ,
                    superseded_text=existing.current_text,
                    superseded_measurements=existing.measurements,
                    active_text=resolved_text,
                    active_measurements=new_measurements,
                    correction_trigger=trigger_str,
                    reason=f"Measurement superseded by '{correction_clause}'"
                )
                # Remove or replace the measurement finding
                existing_list.pop(i)
                break
    elif existing_list and not new_measurements:
        # Non-measurement correction: supersedes the latest finding for that organ
        latest = existing_list.pop()
        superseded_item = SupersededFinding(
            organ_key=target_organ,
            superseded_text=latest.current_text,
            superseded_measurements=latest.measurements,
            active_text=resolved_text,
            active_measurements=[],
            correction_trigger=trigger_str,
            reason=f"Finding superseded by '{correction_clause}'"
        )

    # 3. Create the corrected finding
    import uuid
    for m in new_measurements:
        m.audio_id = audio_id
        m.audio_timestamp_start = t_start
        m.audio_timestamp_end = t_end
        m.source_type = transcript_source

    new_finding = FindingItem(
        id=str(uuid.uuid4()),
        organ_key=target_organ,
        source_text=correction_clause,
        current_text=resolved_text,
        measurements=new_measurements,
        audio_id=audio_id,
        audio_timestamp_start=t_start,
        audio_timestamp_end=t_end,
        assignment_status="confidently_assigned",
        review_flags=["explicitly_corrected"],
        source_type=transcript_source
    )

    return target_organ, new_finding, superseded_item, False
