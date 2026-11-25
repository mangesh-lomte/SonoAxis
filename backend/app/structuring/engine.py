import time
import uuid
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Union

from backend.app.schemas.structuring import (
    StructuredReport, SectionOutput, FindingItem, UnassignedFinding,
    SupersededFinding, MeasurementItem, VascularBiometryOutput
)
from backend.app.structuring.templates import get_template_def
from backend.app.structuring.segmenter import segment_transcript
from backend.app.structuring.organ_matcher import identify_organ, check_incompatible_anatomy
from backend.app.structuring.measurements import extract_measurements
from backend.app.structuring.laterality import detect_laterality, detect_negation, detect_uncertainty
from backend.app.structuring.corrections import is_correction_clause, resolve_explicit_correction
from backend.app.structuring.calculations import (
    calculate_prostate_volume, calculate_uterine_volume, recalculate_report_calculations
)
from backend.app.structuring.vascular import (
    parse_incompetent_perforators, parse_arterial_biometry,
    format_arterial_table_text, format_perforators_text
)

REGEX_IMPRESSION_PREFIX = re.compile(
    r"^\s*(?:IMPRESSION|CONCLUSION|SUMMARY|OPINION)\s*[:,-]?\s*",
    re.IGNORECASE
)
REGEX_CLINICAL_PROFILE_PREFIX = re.compile(
    r"^\s*(?:CLINICAL\s+PROFILE|INDICATION|HISTORY)\s*[:,-]?\s*",
    re.IGNORECASE
)
REGEX_ADV_PREFIX = re.compile(
    r"^\s*(?:ADV|ADVICE|RECOMMENDATION|RECOMMENDATIONS)\s*[:,-]?\s*",
    re.IGNORECASE
)
REGEX_AMBIGUOUS_NEW_LESION = re.compile(
    r"\b(?:cyst|mass|nodule|lesion|collection|abscess|hematoma|tumor|polyp|focus)\b",
    re.IGNORECASE,
)
REGEX_UNAMBIGUOUS_CONTINUATION = re.compile(
    r"\b(?:calculus|calculi|sludge|stone|stones|hydronephrosis|wall(?:\s+thickness)?|distended|"
    r"echotexture|echogenicity|contour|outline|margin|margins|differentiation|corticomedullary|"
    r"dilatation|dilated|caliber|patency|patent|flow|thrombus|compressibility|valsalva|"
    r"parenchym(?:a|al)|focal\s+lesion|its|same\s+organ|either\s+side)\b",
    re.IGNORECASE,
)


def _match_template_section_key(raw_clause: str, sections: List[Dict[str, Any]]) -> Optional[str]:
    """Fallback matcher against custom template section labels and keys (e.g., CCA, ICA, ECA)."""
    text_lower = raw_clause.lower()
    for sec in sections:
        key = (sec.get("key") or "").strip().lower()
        if not key or key == "impression":
            continue
        label = (sec.get("label") or "").strip().lower()
        base_label = re.sub(r"\([^)]*\)", "", label).strip()
        if base_label and len(base_label) > 3 and base_label in text_lower:
            return sec["key"]
        if len(key) >= 2 and re.search(rf"\b{re.escape(key)}\b", text_lower):
            return sec["key"]
    return None


def _infer_contextual_organ(
    raw_clause: str,
    last_dictated_organ: Optional[str],
    measurements: List[MeasurementItem],
) -> Optional[str]:
    """Carries over unambiguous consecutive descriptors to the active anatomical section."""
    if not last_dictated_organ:
        return None
    has_ambiguous_lesion = bool(REGEX_AMBIGUOUS_NEW_LESION.search(raw_clause))
    is_neg = detect_negation(raw_clause)
    # Positive/uncertain focal lesion with a measurement and no explicit organ remains ambiguous
    if has_ambiguous_lesion and not is_neg and measurements:
        return None
    if REGEX_UNAMBIGUOUS_CONTINUATION.search(raw_clause):
        if last_dictated_organ in ("right_kidney", "left_kidney", "kidneys_common") and detect_laterality(raw_clause) == "bilateral":
            return "kidneys_common"
        if last_dictated_organ in ("right_ovary", "left_ovary", "ovaries_bilateral") and detect_laterality(raw_clause) == "bilateral":
            return "ovaries_bilateral"
        return last_dictated_organ
    return None

class DeterministicStructuringEngine:
    """
    Deterministic Ultrasound Report Structuring Engine.
    Converts raw clinical dictation into canonically ordered ultrasound reports.
    Supports Abdominal, Venous Doppler, Arterial Doppler, and Arteriovenous examinations.
    Zero hallucination, 100% offline, blank unmentioned organs, blank undictated impression.
    """

    @classmethod
    def structure_transcript(
        cls,
        transcript: str,
        template_id: str = "usg-abdomen-pelvis-male",
        audio_segments: Optional[List[Dict[str, Any]]] = None,
        audio_id: Optional[str] = None,
        recordings: Optional[List[Dict[str, Any]]] = None,
        prior_report: Optional[Union[StructuredReport, Dict[str, Any]]] = None,
        transcript_source: str = "voice"
    ) -> StructuredReport:
        start_time = time.time()
        template_def = get_template_def(template_id)
        template_gender = template_def.get("gender", "Any")
        template_category = template_def.get("category", "abdomen_pelvis")
        template_laterality = template_def.get("laterality", "not_applicable")
        table_type = template_def.get("table_type", "none")

        # Track findings per organ / section key
        active_findings: Dict[str, List[FindingItem]] = {}
        unassigned_list: List[UnassignedFinding] = []
        superseded_history: List[SupersededFinding] = []
        all_flags: List[str] = []
        impression_clauses: List[str] = []
        extracted_clinical_profile: Optional[str] = None
        extracted_recommendations: Optional[str] = None
        last_dictated_organ: Optional[str] = None
        in_impression_mode = False
        active_recordings: List[Dict[str, Any]] = list(recordings) if recordings else []

        prior_arterial = None
        prior_perforators = None

        if prior_report:
            base_dict = prior_report.model_dump() if hasattr(prior_report, "model_dump") else dict(prior_report)
            if not active_recordings and "recordings" in base_dict and base_dict["recordings"]:
                active_recordings = list(base_dict["recordings"])
            if "superseded_history" in base_dict and base_dict["superseded_history"]:
                for sh in base_dict["superseded_history"]:
                    superseded_history.append(sh if isinstance(sh, SupersededFinding) else SupersededFinding(**sh))
            if "all_flags" in base_dict and base_dict["all_flags"]:
                all_flags.extend(base_dict["all_flags"])
            if "unassigned_findings" in base_dict and base_dict["unassigned_findings"]:
                for uf in base_dict["unassigned_findings"]:
                    unassigned_list.append(uf if isinstance(uf, UnassignedFinding) else UnassignedFinding(**uf))
            if base_dict.get("impression") and not impression_clauses:
                impression_clauses.append(base_dict["impression"])
            if base_dict.get("clinical_profile"):
                extracted_clinical_profile = base_dict["clinical_profile"]
            if base_dict.get("recommendations"):
                extracted_recommendations = base_dict["recommendations"]

            for sec in base_dict.get("sections", []):
                s_key = sec.get("key")
                s_findings = sec.get("findings") or []
                if s_key:
                    if s_findings:
                        active_findings[s_key] = [
                            f if isinstance(f, FindingItem) else FindingItem(**f)
                            for f in s_findings
                        ]
                    elif sec.get("is_present") and sec.get("text"):
                        active_findings[s_key] = [
                            FindingItem(
                                id=str(uuid.uuid4()),
                                organ_key=s_key,
                                source_text=sec["text"],
                                current_text=sec["text"],
                                measurements=[
                                    m if isinstance(m, MeasurementItem) else MeasurementItem(**m)
                                    for m in sec.get("measurements", [])
                                ],
                                assignment_status="confidently_assigned",
                                source_type=sec.get("source_type") or ("preset" if sec.get("preset_name") else transcript_source)
                            )
                        ]
            if base_dict.get("vascular_biometry"):
                vb = base_dict["vascular_biometry"]
                prior_arterial = vb.get("arterial_table")
                prior_perforators = vb.get("incompetent_perforators")

        if audio_id and not any(r.get("id") == audio_id for r in active_recordings):
            active_recordings.append({
                "id": audio_id,
                "duration": round(audio_segments[-1].get("end", 0.0), 2) if audio_segments else 0.0,
                "transcript": transcript,
                "created_at": datetime.now(timezone.utc).isoformat()
            })

        if not transcript or not transcript.strip():
            if prior_report:
                # Return report preserving prior structured data
                sections_output = []
                base_dict = prior_report.model_dump() if hasattr(prior_report, "model_dump") else dict(prior_report)
                for sec in base_dict.get("sections", []):
                    sections_output.append(sec if isinstance(sec, SectionOutput) else SectionOutput(**sec))
                return StructuredReport(
                    template_id=template_def["id"],
                    template_name=template_def["name"],
                    gender=template_gender,
                    category=template_category,
                    laterality=template_laterality,
                    raw_transcript=base_dict.get("raw_transcript", ""),
                    sections=sections_output,
                    impression=base_dict.get("impression"),
                    clinical_profile=extracted_clinical_profile,
                    recommendations=extracted_recommendations,
                    vascular_biometry=base_dict.get("vascular_biometry"),
                    unassigned_findings=unassigned_list,
                    superseded_history=superseded_history,
                    recordings=active_recordings,
                    processing_time_ms=0.0,
                    has_flags=len(all_flags) > 0,
                    all_flags=all_flags
                )

            # Return blank report
            sections_output = [
                SectionOutput(
                    order=s["order"],
                    key=s["key"],
                    label=s["label"],
                    heading=s["heading"],
                    is_present=False,
                    text=None,
                    findings=[]
                ) for s in template_def["sections"] if s["key"] != "impression"
            ]
            return StructuredReport(
                template_id=template_def["id"],
                template_name=template_def["name"],
                gender=template_gender,
                category=template_category,
                laterality=template_laterality,
                raw_transcript=transcript or "",
                sections=sections_output,
                impression=None,
                clinical_profile=None,
                recommendations=None,
                vascular_biometry=None,
                unassigned_findings=[],
                superseded_history=[],
                recordings=active_recordings,
                processing_time_ms=0.0,
                has_flags=False,
                all_flags=[]
            )

        # 1. Segment transcript into discrete clauses
        clauses = segment_transcript(transcript)
        all_clause_texts = [c["text"] for c in clauses]

        for clause_info in clauses:
            raw_clause = clause_info["text"]
            c_start = clause_info.get("char_start")
            c_end = clause_info.get("char_end")

            # Check if clause is Recommendations / ADV
            if REGEX_ADV_PREFIX.search(raw_clause) or raw_clause.lower().startswith("adv:"):
                in_impression_mode = False
                clean_adv = REGEX_ADV_PREFIX.sub("", raw_clause).strip(" :,-")
                if clean_adv:
                    extracted_recommendations = clean_adv
                continue

            # Check if this clause is the IMPRESSION section start
            if REGEX_IMPRESSION_PREFIX.search(raw_clause) or raw_clause.lower().startswith("impression"):
                in_impression_mode = True
                clean_imp = REGEX_IMPRESSION_PREFIX.sub("", raw_clause).strip(" :,-")
                if clean_imp:
                    impression_clauses.append(clean_imp)
                continue

            # If already inside impression mode, append following clauses unless a new top-level section is found
            if in_impression_mode:
                if REGEX_CLINICAL_PROFILE_PREFIX.search(raw_clause):
                    in_impression_mode = False
                else:
                    impression_clauses.append(raw_clause.strip())
                    continue

            # Check if clause is Clinical Profile
            if REGEX_CLINICAL_PROFILE_PREFIX.search(raw_clause) or raw_clause.lower().startswith("clinical profile"):
                clean_cp = REGEX_CLINICAL_PROFILE_PREFIX.sub("", raw_clause).strip(" :,-")
                if clean_cp:
                    extracted_clinical_profile = clean_cp
                continue

            # Check if this clause is an explicit correction
            is_corr, trigger_str, stripped_clause = is_correction_clause(raw_clause)
            if is_corr:
                t_start_corr, t_end_corr = None, None
                if audio_segments and c_start is not None and len(transcript) > 0:
                    for seg in audio_segments:
                        seg_text = seg.get("text", "").lower()
                        if raw_clause.lower() in seg_text or any(w in seg_text for w in raw_clause.lower().split() if len(w) > 4):
                            t_start_corr = round(seg.get("start", 0.0), 2)
                            t_end_corr = round(seg.get("end", t_start_corr), 2)
                            break
                    if t_start_corr is None:
                        ratio_start = c_start / len(transcript)
                        ratio_end = c_end / len(transcript) if c_end else ratio_start
                        total_dur = audio_segments[-1].get("end", 0.0)
                        t_start_corr = round(ratio_start * total_dur, 2)
                        t_end_corr = round(ratio_end * total_dur, 2)

                target_organ, new_finding, superseded_item, is_ambiguous = resolve_explicit_correction(
                    correction_clause=stripped_clause,
                    trigger_str=trigger_str,
                    active_findings=active_findings,
                    last_dictated_organ=last_dictated_organ,
                    audio_id=audio_id,
                    t_start=t_start_corr,
                    t_end=t_end_corr,
                    transcript_source=transcript_source
                )

                if is_ambiguous or not target_organ:
                    unassigned_list.append(UnassignedFinding(
                        id=str(uuid.uuid4()),
                        raw_text=raw_clause,
                        reason="ambiguous_correction",
                        measurements=extract_measurements(raw_clause),
                        is_resolved=False
                    ))
                    all_flags.append("ambiguous_correction")
                else:
                    if superseded_item:
                        superseded_history.append(superseded_item)
                    if new_finding:
                        if target_organ not in active_findings:
                            active_findings[target_organ] = []
                        active_findings[target_organ].append(new_finding)
                        last_dictated_organ = target_organ
                continue

            # Normal organ or vascular section identification
            template_sec_keys = {s.get("key") for s in template_def.get("sections", [])}
            custom_sec_match = _match_template_section_key(raw_clause, template_def.get("sections", []))
            organ_key, matched_term = identify_organ(raw_clause, template_category=template_category)

            if custom_sec_match and (not organ_key or organ_key not in template_sec_keys):
                organ_key = custom_sec_match

            clause_meas = extract_measurements(raw_clause)

            if not organ_key:
                organ_key = _infer_contextual_organ(raw_clause, last_dictated_organ, clause_meas)

            if not organ_key:
                # No unambiguous organ or context identified -> Unassigned Finding
                unassigned_list.append(UnassignedFinding(
                    id=str(uuid.uuid4()),
                    raw_text=raw_clause,
                    reason="no_organ_identified",
                    measurements=clause_meas,
                    is_resolved=False
                ))
                all_flags.append("unassigned_finding")
                last_dictated_organ = None
                continue

            # Check incompatible anatomy (e.g. prostate in female, or liver in vascular study)
            if check_incompatible_anatomy(organ_key, template_gender, template_category=template_category):
                unassigned_list.append(UnassignedFinding(
                    id=str(uuid.uuid4()),
                    raw_text=raw_clause,
                    reason=f"incompatible_anatomy_{template_gender.lower() if template_category == 'abdomen_pelvis' else template_category}",
                    measurements=clause_meas,
                    is_resolved=False
                ))
                all_flags.append(f"incompatible_anatomy: {organ_key} in {template_gender} / {template_category} template")
                continue

            # Extract measurements & attributes
            measurements = clause_meas
            laterality = detect_laterality(raw_clause)
            is_neg = detect_negation(raw_clause)
            is_unc = detect_uncertainty(raw_clause)

            # Match audio timestamps if available
            t_start, t_end = None, None
            if audio_segments and c_start is not None and len(transcript) > 0:
                for seg in audio_segments:
                    seg_text = seg.get("text", "").lower()
                    if raw_clause.lower() in seg_text or any(w in seg_text for w in raw_clause.lower().split() if len(w) > 4):
                        t_start = round(seg.get("start", 0.0), 2)
                        t_end = round(seg.get("end", t_start), 2)
                        break

                if t_start is None:
                    ratio_start = c_start / len(transcript)
                    ratio_end = c_end / len(transcript) if c_end else ratio_start
                    first_seg = audio_segments[0]
                    last_seg = audio_segments[-1]
                    total_audio_duration = last_seg.get("end", 0.0)
                    t_start = round(ratio_start * total_audio_duration, 2)
                    t_end = round(ratio_end * total_audio_duration, 2)

            for m in measurements:
                m.audio_id = audio_id
                m.audio_timestamp_start = t_start
                m.audio_timestamp_end = t_end
                m.source_type = transcript_source

            finding = FindingItem(
                id=str(uuid.uuid4()),
                organ_key=organ_key,
                source_text=raw_clause,
                current_text=raw_clause,
                measurements=measurements,
                laterality=laterality,
                is_negation=is_neg,
                is_uncertain=is_unc,
                char_start=c_start,
                char_end=c_end,
                audio_id=audio_id,
                audio_timestamp_start=t_start,
                audio_timestamp_end=t_end,
                assignment_status="confidently_assigned",
                source_type=transcript_source
            )

            if organ_key not in active_findings:
                active_findings[organ_key] = []
            active_findings[organ_key].append(finding)
            last_dictated_organ = organ_key

        # Assemble full impression text
        extracted_impression: Optional[str] = None
        if impression_clauses:
            if len(impression_clauses) == 1:
                extracted_impression = impression_clauses[0].strip().rstrip(".")
            else:
                joined = ". ".join(c.strip().rstrip(".") for c in impression_clauses if c.strip())
                extracted_impression = joined if joined.endswith(".") else joined + "."

        # 2. Vascular Biometry Extraction (if vascular template)
        vascular_biometry: Optional[VascularBiometryOutput] = None
        if template_category in ["venous_doppler", "arterial_doppler", "arteriovenous_doppler"]:
            incompetent_perforators = parse_incompetent_perforators(
                all_clause_texts,
                default_laterality=template_laterality if template_laterality in ["right", "left"] else None,
                existing_perforators=prior_perforators
            )
            # Check for arterial velocity updates to capture in superseded_history
            prior_psv_map: Dict[str, Tuple[Optional[float], Optional[float]]] = {}
            if prior_arterial:
                for pa in prior_arterial:
                    k = pa.segment_key if hasattr(pa, "segment_key") else pa.get("segment_key")
                    r_v = pa.psv_right if hasattr(pa, "psv_right") else pa.get("psv_right")
                    l_v = pa.psv_left if hasattr(pa, "psv_left") else pa.get("psv_left")
                    prior_psv_map[k] = (r_v, l_v)

            arterial_biometry = parse_arterial_biometry(
                all_clause_texts,
                laterality=template_laterality,
                existing_biometry=prior_arterial
            )

            # Audit superseded arterial velocities
            for ab in arterial_biometry:
                k = ab.segment_key
                old_r, old_l = prior_psv_map.get(k, (None, None))
                if old_r is not None and ab.psv_right is not None and ab.psv_right != old_r:
                    superseded_history.append(SupersededFinding(
                        organ_key=k,
                        superseded_text=f"Right {ab.segment_name} PSV {old_r} cm/s",
                        superseded_measurements=[MeasurementItem(value=old_r, unit="cm/s", raw_str=f"{old_r} cm/s", dimension=1, source_type=transcript_source)],
                        active_text=f"Right {ab.segment_name} PSV {ab.psv_right} cm/s",
                        active_measurements=[MeasurementItem(value=ab.psv_right, unit="cm/s", raw_str=f"{ab.psv_right} cm/s", dimension=1, source_type=transcript_source)],
                        correction_trigger="correction",
                        reason=f"Velocity updated to {ab.psv_right} cm/s"
                    ))
                if old_l is not None and ab.psv_left is not None and ab.psv_left != old_l:
                    superseded_history.append(SupersededFinding(
                        organ_key=k,
                        superseded_text=f"Left {ab.segment_name} PSV {old_l} cm/s",
                        superseded_measurements=[MeasurementItem(value=old_l, unit="cm/s", raw_str=f"{old_l} cm/s", dimension=1, source_type=transcript_source)],
                        active_text=f"Left {ab.segment_name} PSV {ab.psv_left} cm/s",
                        active_measurements=[MeasurementItem(value=ab.psv_left, unit="cm/s", raw_str=f"{ab.psv_left} cm/s", dimension=1, source_type=transcript_source)],
                        correction_trigger="correction",
                        reason=f"Velocity updated to {ab.psv_left} cm/s"
                    ))

            vascular_biometry = VascularBiometryOutput(
                arterial_table=arterial_biometry,
                incompetent_perforators=incompetent_perforators,
                clinical_profile=extracted_clinical_profile,
                recommendations=extracted_recommendations
            )

        # 3. Build Canonical Ordered Section Outputs
        sections_output: List[SectionOutput] = []

        for sec in template_def["sections"]:
            sec_key = sec["key"]
            if sec_key == "impression":
                continue  # Impression is modeled as a primary report attribute

            # Handle special clinical profile & recommendations sections if dictated
            if sec_key == "clinical_profile":
                if extracted_clinical_profile:
                    sections_output.append(SectionOutput(
                        order=sec["order"],
                        key=sec_key,
                        label=sec["label"],
                        heading=sec["heading"],
                        is_present=True,
                        text=extracted_clinical_profile,
                        findings=[]
                    ))
                else:
                    sections_output.append(SectionOutput(
                        order=sec["order"],
                        key=sec_key,
                        label=sec["label"],
                        heading=sec["heading"],
                        is_present=False,
                        text=None,
                        findings=[]
                    ))
                continue

            if sec_key == "recommendations":
                if extracted_recommendations:
                    sections_output.append(SectionOutput(
                        order=sec["order"],
                        key=sec_key,
                        label=sec["label"],
                        heading=sec["heading"],
                        is_present=True,
                        text=extracted_recommendations,
                        findings=[]
                    ))
                else:
                    sections_output.append(SectionOutput(
                        order=sec["order"],
                        key=sec_key,
                        label=sec["label"],
                        heading=sec["heading"],
                        is_present=False,
                        text=None,
                        findings=[]
                    ))
                continue

            # Handle vascular arterial measurement table section
            if sec_key in ["measurement_table", "arterial_table"]:
                if vascular_biometry and (any(a.psv_right is not None or a.psv_left is not None for a in vascular_biometry.arterial_table) or template_category in ["arterial_doppler", "arteriovenous_doppler"]):
                    formatted_tbl = format_arterial_table_text(
                        vascular_biometry.arterial_table,
                        table_type=table_type,
                        laterality=template_laterality
                    )
                    sections_output.append(SectionOutput(
                        order=sec["order"],
                        key=sec_key,
                        label=sec["label"],
                        heading=sec["heading"],
                        is_present=True,
                        text=formatted_tbl,
                        findings=[]
                    ))
                else:
                    sections_output.append(SectionOutput(
                        order=sec["order"],
                        key=sec_key,
                        label=sec["label"],
                        heading=sec["heading"],
                        is_present=False,
                        text=None,
                        findings=[]
                    ))
                continue

            # Handle incompetent perforators section
            if sec_key == "perforators":
                if vascular_biometry and vascular_biometry.incompetent_perforators:
                    formatted_perfs = format_perforators_text(
                        vascular_biometry.incompetent_perforators,
                        laterality=template_laterality
                    )
                    sections_output.append(SectionOutput(
                        order=sec["order"],
                        key=sec_key,
                        label=sec["label"],
                        heading=sec["heading"],
                        is_present=True,
                        text=formatted_perfs,
                        findings=[]
                    ))
                else:
                    sections_output.append(SectionOutput(
                        order=sec["order"],
                        key=sec_key,
                        label=sec["label"],
                        heading=sec["heading"],
                        is_present=False,
                        text=None,
                        findings=[]
                    ))
                continue

            # Standard organ findings matching
            findings_for_sec = active_findings.get(sec_key, [])

            if findings_for_sec:
                combined_texts = []
                all_sec_measurements = []
                for f in findings_for_sec:
                    combined_texts.append(f.current_text)
                    all_sec_measurements.extend(f.measurements)

                calc_biometry = None
                if sec_key == "prostate":
                    calc_biometry = calculate_prostate_volume(all_sec_measurements)
                    if calc_biometry and calc_biometry.get("discrepancy_flag"):
                        all_flags.append("prostate_volume_discrepancy")

                full_text = ". ".join(combined_texts).strip()
                if not full_text.endswith("."):
                    full_text += "."

                sec_source = findings_for_sec[0].source_type if findings_for_sec else transcript_source
                sec_preset = next((f.preset_name for f in findings_for_sec if f.preset_name), None)

                sections_output.append(SectionOutput(
                    order=sec["order"],
                    key=sec_key,
                    label=sec["label"],
                    heading=sec["heading"],
                    is_present=True,
                    text=full_text,
                    measurements=all_sec_measurements,
                    calculated_biometry=calc_biometry,
                    findings=findings_for_sec,
                    source_type=sec_source,
                    preset_name=sec_preset
                ))
            else:
                # Unmentioned organ: MUST BE 100% BLANK
                sections_output.append(SectionOutput(
                    order=sec["order"],
                    key=sec_key,
                    label=sec["label"],
                    heading=sec["heading"],
                    is_present=False,
                    text=None,
                    measurements=[],
                    calculated_biometry=None,
                    findings=[]
                ))

        # Safety net: never silently discard findings matched to a key absent from the selected template
        emitted_keys = {s.key for s in sections_output}
        for orphan_key, orphan_items in active_findings.items():
            if orphan_key in emitted_keys or orphan_key == "impression":
                continue
            for item in orphan_items:
                unassigned_list.append(UnassignedFinding(
                    id=str(uuid.uuid4()),
                    raw_text=item.current_text,
                    reason="unmapped_template_section",
                    measurements=item.measurements,
                    is_resolved=False
                ))
                all_flags.append(f"unmapped_section: {orphan_key}")

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        has_flags = len(all_flags) > 0 or len(unassigned_list) > 0

        return StructuredReport(
            template_id=template_def["id"],
            template_name=template_def["name"],
            gender=template_gender,
            category=template_category,
            laterality=template_laterality,
            raw_transcript=transcript,
            sections=sections_output,
            impression=extracted_impression,
            clinical_profile=extracted_clinical_profile,
            recommendations=extracted_recommendations,
            vascular_biometry=vascular_biometry,
            unassigned_findings=unassigned_list,
            superseded_history=superseded_history,
            recordings=active_recordings,
            processing_time_ms=elapsed_ms,
            has_flags=has_flags,
            all_flags=all_flags
        )

    @classmethod
    def merge_findings(
        cls,
        existing_report: Union[StructuredReport, Dict[str, Any]],
        new_report_or_transcript: Union[StructuredReport, Dict[str, Any], str],
        new_audio_id: Optional[str] = None,
        new_audio_segments: Optional[List[Dict[str, Any]]] = None
    ) -> StructuredReport:
        """
        Merges findings from a subsequent dictation, manual edit, or secondary recording
        into the active report without silent overwriting.
        """
        base_dict = existing_report.model_dump() if hasattr(existing_report, "model_dump") else dict(existing_report)
        template_id = base_dict.get("template_id", "usg-abdomen-pelvis-male")

        if isinstance(new_report_or_transcript, str):
            prev_raw = base_dict.get("raw_transcript", "")
            rec_num = len(base_dict.get("recordings", [])) + 1
            combined_transcript = f"{prev_raw}\n\n[Recording {rec_num}]: {new_report_or_transcript}".strip() if prev_raw else new_report_or_transcript
            merged = cls.structure_transcript(
                transcript=new_report_or_transcript,
                template_id=template_id,
                audio_segments=new_audio_segments,
                audio_id=new_audio_id,
                prior_report=existing_report
            )
            merged.raw_transcript = combined_transcript
            return merged

        new_dict = new_report_or_transcript.model_dump() if hasattr(new_report_or_transcript, "model_dump") else dict(new_report_or_transcript)
        return cls.structure_transcript(
            transcript=new_dict.get("raw_transcript", ""),
            template_id=template_id,
            audio_segments=new_audio_segments,
            audio_id=new_audio_id,
            prior_report=existing_report
        )

# Singleton instance
structuring_engine = DeterministicStructuringEngine()
