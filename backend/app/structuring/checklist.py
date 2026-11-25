from typing import List, Dict, Any

ANATOMICAL_TAXONOMY: Dict[str, List[Dict[str, str]]] = {
    "abdomen_pelvis": [
        {"key": "liver", "label": "Liver", "description": "Size, contour, parenchymal echogenicity, focal lesions"},
        {"key": "gall_bladder", "label": "Gall Bladder", "description": "Distension, wall thickness, lumen calculi"},
        {"key": "cbd", "label": "Common Bile Duct", "description": "Luminal calibre, obstruction"},
        {"key": "pancreas", "label": "Pancreas", "description": "Parenchyma, main pancreatic duct, mass lesions"},
        {"key": "retroperitoneum", "label": "Aorta & Retroperitoneum", "description": "Aortic calibre, lymphadenopathy"},
        {"key": "spleen", "label": "Spleen", "description": "Splenic span, parenchymal texture"},
        {"key": "right_kidney", "label": "Right Kidney", "description": "Dimensions, CMD, calculi, hydronephrosis"},
        {"key": "left_kidney", "label": "Left Kidney", "description": "Dimensions, CMD, calculi, hydronephrosis"},
        {"key": "kidneys_common", "label": "Kidneys (Summary)", "description": "Bilateral CMD, renal calculi, hydronephrosis"},
        {"key": "urinary_bladder", "label": "Urinary Bladder", "description": "Distension, wall thickness, PVR, intraluminal lesions"},
        {"key": "prostate", "label": "Prostate (Male)", "description": "3D dimensions, calculated volume, capsule"},
        {"key": "uterus", "label": "Uterus (Female)", "description": "3D dimensions, volume, myometrial architecture"},
        {"key": "endometrium", "label": "Endometrium (Female)", "description": "Double-layer thickness in mm, regularity"},
        {"key": "right_ovary", "label": "Right Ovary (Female)", "description": "Dimensions, stroma, follicular activity"},
        {"key": "left_ovary", "label": "Left Ovary (Female)", "description": "Dimensions, stroma, follicular activity"},
        {"key": "ovaries_bilateral", "label": "Bilateral Ovaries (Female)", "description": "Combined adnexal evaluation"},
        {"key": "bowel", "label": "Bowel Loops", "description": "Caliber, wall thickness, peristalsis"},
        {"key": "peritoneal_cavity", "label": "Peritoneal Cavity", "description": "Free ascites, localized collections"}
    ],
    "venous_doppler": [
        {"key": "deep_venous_thigh", "label": "Femoral & Popliteal Veins", "description": "Compressibility, respiratory phasicity, DVT"},
        {"key": "deep_venous_calf", "label": "Calf Veins (Peroneal, PTV, ATV)", "description": "Compressibility, augmentation, calf thrombosis"},
        {"key": "junctions", "label": "SFJ & SPJ Junctions", "description": "Valvular competence, reflux duration (>0.5s)"},
        {"key": "gsv", "label": "Great Saphenous Vein", "description": "Thigh/calf caliber, superficial insufficiency"},
        {"key": "ssv", "label": "Small Saphenous Vein", "description": "Caliber, popliteal junction competence"},
        {"key": "perforators", "label": "Incompetent Perforators", "description": "Caliber in mm, anatomical location/distance"},
        {"key": "varicosities", "label": "Superficial Varicosities", "description": "Tributary distribution, subcutaneous clusters"},
        {"key": "edema", "label": "Subcutaneous Edema", "description": "Dermal thickening, interstitial fluid"}
    ],
    "arterial_doppler": [
        {"key": "cfa", "label": "Common Femoral Artery (CFA)", "description": "Peak systolic velocity (PSV), triphasic waveform"},
        {"key": "sfa", "label": "Superficial Femoral Artery (SFA)", "description": "PSV, flow pattern, plaque/calcification"},
        {"key": "dfa", "label": "Deep Femoral Artery (DFA)", "description": "PSV, flow pattern, ostial patency"},
        {"key": "popliteal", "label": "Popliteal Artery", "description": "PSV, flow pattern, aneurysm/stenosis"},
        {"key": "ata", "label": "Anterior Tibial Artery (ATA)", "description": "Distal flow, monophasic vs triphasic"},
        {"key": "pta", "label": "Posterior Tibial Artery (PTA)", "description": "Ankle velocity, flow pattern, occlusion"},
        {"key": "dpa", "label": "Dorsalis Pedis Artery (DPA)", "description": "Pedal flow, distal perfusion"}
    ],
    "arteriovenous_doppler": [
        {"key": "arterial_findings", "label": "Arterial Tree (CFA, SFA, PopA)", "description": "Velocities, waveforms, arterial stenosis"},
        {"key": "deep_venous_thigh", "label": "Deep Veins (CFV, SFV, PopV)", "description": "Luminal compressibility, DVT evaluation"},
        {"key": "deep_venous_calf", "label": "Calf Veins", "description": "Calf DVT, augmentation"},
        {"key": "junctions", "label": "Saphenous Junctions", "description": "Venous reflux, insufficiency"}
    ]
}

def generate_anatomical_checklist(
    category: str,
    sections: List[Dict[str, Any]],
    template_gender: str = "Any"
) -> List[Dict[str, Any]]:
    """
    Generates a structured anatomical checklist for the current examination.
    Evaluates documentation status for each anatomical structure without auto-populating normal findings:
    - not_documented: Structure has not been dictated or documented
    - dictated: Recorded voice / audio-dictated findings present
    - typed_transcript: Manually typed/pasted transcript processed with structuring engine
    - uploaded_audio: Uploaded audio file transcribed via Whisper
    - manually_entered: Manually entered or edited section content present
    - preset_applied: Clinician applied an institutional normal preset
    - ocr_verified: Local OCR machine printout measurements confirmed
    - requires_review: Discrepancy, unassigned finding, or explicit flag present
    """
    base_taxonomy = ANATOMICAL_TAXONOMY.get(category, ANATOMICAL_TAXONOMY["abdomen_pelvis"])
    sections_map = {s.get("key"): s for s in sections}

    checklist = []
    for item in base_taxonomy:
        key = item["key"]

        # Gender filtering
        if template_gender == "Male" and key in ["uterus", "endometrium", "right_ovary", "left_ovary", "ovaries_bilateral"]:
            continue
        if template_gender == "Female" and key == "prostate":
            continue

        sec_data = sections_map.get(key)
        status = "not_documented"
        findings_count = 0
        measurements_count = 0
        review_flags: List[str] = []
        dominant_source: str | None = None
        summary_text: str | None = None

        if sec_data and sec_data.get("is_present") and sec_data.get("text"):
            findings_count = 1
            summary_text = sec_data.get("text")
            dominant_source = sec_data.get("source_type")
            if not dominant_source and sec_data.get("preset_name"):
                dominant_source = "preset"

            raw_findings = sec_data.get("findings") or []
            if raw_findings:
                findings_count = len(raw_findings)
                for f in raw_findings:
                    st = f.get("source_type") if isinstance(f, dict) else getattr(f, "source_type", None)
                    if st and not dominant_source:
                        dominant_source = st
                    elif st in ("preset", "manual", "ocr_verified", "ocr_manually_corrected"):
                        dominant_source = st

                    flags = f.get("review_flags") if isinstance(f, dict) else getattr(f, "review_flags", [])
                    if flags:
                        review_flags.extend(flags)

            measurements = sec_data.get("measurements") or []
            measurements_count = len(measurements)

            if review_flags or sec_data.get("review_flags"):
                status = "requires_review"
            elif dominant_source == "preset" or sec_data.get("preset_name"):
                status = "preset_applied"
            elif dominant_source == "manual":
                status = "manually_entered"
            elif dominant_source in ("ocr_verified", "ocr_manually_corrected", "ocr_extracted"):
                status = "ocr_verified"
            elif dominant_source == "typed_transcript":
                status = "typed_transcript"
            elif dominant_source == "uploaded_audio":
                status = "uploaded_audio"
            else:
                status = "dictated"

        checklist.append({
            "key": key,
            "label": item["label"],
            "description": item["description"],
            "status": status,
            "is_present": (status != "not_documented"),
            "source_type": dominant_source,
            "summary_text": summary_text,
            "findings_count": findings_count,
            "measurements_count": measurements_count,
            "review_flags": review_flags
        })

    return checklist
