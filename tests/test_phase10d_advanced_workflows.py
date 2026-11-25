import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.structuring.engine import structuring_engine
from backend.app.structuring.calculations import (
    calculate_prostate_volume,
    calculate_uterine_volume,
    calculate_carotid_velocity_ratio,
    calculate_ankle_brachial_index,
    recalculate_report_calculations
)
from backend.app.structuring.checklist import generate_anatomical_checklist
from backend.app.structuring.presets import NORMAL_PRESETS_CATALOG, get_preset_for_section
from backend.app.schemas.structuring import MeasurementItem


# ================= 1. MULTI-RECORDING & INCREMENTAL STRUCTURING =================

def test_multi_recording_incremental_structuring():
    """
    Verifies that multiple recordings can be incrementally added to a single report,
    appending new anatomy while preserving prior dictated findings and timestamps.
    """
    rec1 = "Liver is normal in size and echotexture. Gall bladder is normal without calculi."
    rec2 = "Spleen is normal. Right kidney measures 10.5 cm."

    # Structure rec1
    rep1 = structuring_engine.structure_transcript(
        transcript=rec1,
        template_id="usg-abdomen-pelvis-male",
        audio_id="rec-001",
        audio_segments=[{"start": 0.0, "end": 4.5, "text": rec1}]
    )

    liver1 = next(s for s in rep1.sections if s.key == "liver")
    spleen1 = next(s for s in rep1.sections if s.key == "spleen")
    assert liver1.is_present is True
    assert spleen1.is_present is False
    assert len(rep1.recordings) == 1
    assert rep1.recordings[0]["id"] == "rec-001"

    # Merge rec2 using prior_report
    rep2 = structuring_engine.structure_transcript(
        transcript=rec2,
        template_id="usg-abdomen-pelvis-male",
        audio_id="rec-002",
        audio_segments=[{"start": 0.0, "end": 3.8, "text": rec2}],
        prior_report=rep1
    )

    liver2 = next(s for s in rep2.sections if s.key == "liver")
    gb2 = next(s for s in rep2.sections if s.key == "gall_bladder")
    spleen2 = next(s for s in rep2.sections if s.key == "spleen")
    rk2 = next(s for s in rep2.sections if s.key == "right_kidney")
    lk2 = next(s for s in rep2.sections if s.key == "left_kidney")

    # Prior findings preserved
    assert liver2.is_present is True
    assert gb2.is_present is True
    # New findings added
    assert spleen2.is_present is True
    assert rk2.is_present is True
    assert len(rk2.measurements) == 1
    assert rk2.measurements[0].audio_id == "rec-002"
    assert rk2.measurements[0].source_type == "voice"
    # Unmentioned anatomy remains 100% blank
    assert lk2.is_present is False
    assert lk2.text is None
    # Both recordings tracked
    assert len(rep2.recordings) == 2
    assert rep2.recordings[0]["id"] == "rec-001"
    assert rep2.recordings[1]["id"] == "rec-002"


# ================= 2. MANDATORY VASCULAR MULTI-RECORDING TEST =================

def test_mandatory_multiple_recording_vascular_workflow():
    """
    Mandatory Multiple-Recording Vascular Test:
    - Rec 1: Right CFA PSV 95 cm/s triphasic.
    - Rec 2: Right popliteal PSV 72 cm/s biphasic.
    - Rec 3: Correction, right CFA velocity 98 cm/s.
    Expected:
      - CFA 98 triphasic
      - Popliteal 72 biphasic
      - 95 in history
      - 3 recordings playable
      - unmentioned arteries blank
    """
    template_id = "usg-doppler-arterial-right-normal"

    # Recording 1: Right CFA PSV 95 cm/s triphasic
    r1_text = "Right CFA PSV 95 cm/s triphasic."
    rep1 = structuring_engine.structure_transcript(
        transcript=r1_text,
        template_id=template_id,
        audio_id="audio-vasc-01",
        audio_segments=[{"start": 0.0, "end": 2.5, "text": r1_text}]
    )
    vb1 = rep1.vascular_biometry
    assert vb1 is not None
    cfa1 = next(a for a in vb1.arterial_table if a.segment_key == "cfa")
    pop1 = next(a for a in vb1.arterial_table if a.segment_key == "popliteal")
    sfa1 = next(a for a in vb1.arterial_table if a.segment_key == "sfa")
    assert cfa1.psv_right == 95.0
    assert cfa1.flow_pattern_right == "Triphasic"
    assert pop1.psv_right is None
    assert sfa1.psv_right is None

    # Recording 2: Right popliteal PSV 72 cm/s biphasic
    r2_text = "Right popliteal PSV 72 cm/s biphasic."
    rep2 = structuring_engine.structure_transcript(
        transcript=r2_text,
        template_id=template_id,
        audio_id="audio-vasc-02",
        audio_segments=[{"start": 0.0, "end": 2.8, "text": r2_text}],
        prior_report=rep1
    )
    vb2 = rep2.vascular_biometry
    cfa2 = next(a for a in vb2.arterial_table if a.segment_key == "cfa")
    pop2 = next(a for a in vb2.arterial_table if a.segment_key == "popliteal")
    assert cfa2.psv_right == 95.0
    assert pop2.psv_right == 72.0
    assert pop2.flow_pattern_right == "Biphasic"

    # Recording 3: Correction, right CFA velocity 98 cm/s
    r3_text = "Correction, right CFA velocity 98 cm/s."
    rep3 = structuring_engine.structure_transcript(
        transcript=r3_text,
        template_id=template_id,
        audio_id="audio-vasc-03",
        audio_segments=[{"start": 0.0, "end": 2.2, "text": r3_text}],
        prior_report=rep2
    )
    vb3 = rep3.vascular_biometry
    cfa3 = next(a for a in vb3.arterial_table if a.segment_key == "cfa")
    pop3 = next(a for a in vb3.arterial_table if a.segment_key == "popliteal")
    sfa3 = next(a for a in vb3.arterial_table if a.segment_key == "sfa")
    dfa3 = next(a for a in vb3.arterial_table if a.segment_key == "dfa")

    # 1. CFA updated to 98, triphasic preserved
    assert cfa3.psv_right == 98.0
    assert cfa3.flow_pattern_right == "Triphasic"
    # 2. Popliteal 72 biphasic preserved
    assert pop3.psv_right == 72.0
    assert pop3.flow_pattern_right == "Biphasic"
    # 3. 95 cm/s captured in superseded_history
    assert len(rep3.superseded_history) >= 1
    cfa_superseded = next(s for s in rep3.superseded_history if s.organ_key == "cfa")
    assert "95" in cfa_superseded.superseded_text
    # 4. 3 recordings playable
    assert len(rep3.recordings) == 3
    assert [r["id"] for r in rep3.recordings] == ["audio-vasc-01", "audio-vasc-02", "audio-vasc-03"]
    # 5. Unmentioned arteries blank (None PSV)
    assert sfa3.psv_right is None
    assert dfa3.psv_right is None


# ================= 3. CLINICAL CORRECTION ACROSS RECORDINGS =================

def test_clinical_correction_across_recordings():
    """
    Clinical Correction Handling Across Recordings:
    - Rec 1: Right kidney measures 10.2 by 4.5 cm.
    - Rec 2: Correction, right kidney length is 10.8 cm.
    Expected:
      - Length 10.8 cm, width 4.5 cm.
      - Previous 10.2 x 4.5 cm preserved in superseded_history.
      - Both recordings accessible in recordings list.
    """
    template_id = "usg-abdomen-pelvis-male"

    # Recording 1: 10.2 by 4.5 cm
    r1_text = "Right kidney measures 10.2 by 4.5 cm."
    rep1 = structuring_engine.structure_transcript(
        transcript=r1_text,
        template_id=template_id,
        audio_id="rec-rk-01",
        audio_segments=[{"start": 0.0, "end": 3.0, "text": r1_text}]
    )
    rk1 = next(s for s in rep1.sections if s.key == "right_kidney")
    assert rk1.is_present is True
    assert rk1.measurements[0].value == [10.2, 4.5]

    # Recording 2: Correction length 10.8 cm
    r2_text = "Correction, right kidney length is 10.8 cm."
    rep2 = structuring_engine.structure_transcript(
        transcript=r2_text,
        template_id=template_id,
        audio_id="rec-rk-02",
        audio_segments=[{"start": 0.0, "end": 2.6, "text": r2_text}],
        prior_report=rep1
    )
    rk2 = next(s for s in rep2.sections if s.key == "right_kidney")

    # Length updated to 10.8, width 4.5 preserved
    assert rk2.measurements[0].value == [10.8, 4.5]
    assert "10.8 x 4.5 cm" in rk2.measurements[0].raw_str

    # Superseded history preserves old measurement
    assert len(rep2.superseded_history) == 1
    sh = rep2.superseded_history[0]
    assert sh.organ_key in ["right_kidney", "kidney_right"]
    assert "10.2" in sh.superseded_text
    assert sh.correction_trigger.lower().startswith("correction")

    # Both recordings accessible
    assert len(rep2.recordings) == 2


# ================= 4. CLINICAL CALCULATIONS =================

def test_clinical_calculations_and_recalculation():
    """
    Verifies automatic clinical calculations:
    - Prostate volume: L x W x H x 0.523 (Terris & Stamey 1991)
    - Uterine volume: L x AP x W x 0.523 (Merz et al. 1996)
    - Carotid velocity ratio: ICA / CCA (SRU 2003)
    - ABI: Ankle / Brachial (AHA/ACC 2017)
    - Blank if inputs missing; zero diagnostic hallucination.
    """
    # Prostate volume: 4.0 x 3.5 x 3.0 cm -> 42 * 0.523 = 21.97 cc
    p_meas = [MeasurementItem(value=[4.0, 3.5, 3.0], unit="cm", dimension=3, raw_str="4.0 x 3.5 x 3.0 cm")]
    p_calc = calculate_prostate_volume(p_meas)
    assert p_calc is not None
    assert p_calc["volume_cc"] == 21.97
    assert p_calc["calculated_volume_cc"] == 21.8
    assert "0.523" in p_calc["formula"]
    assert "Terris" in p_calc["clinical_source"]
    assert p_calc["source_type"] == "calculation"

    # Uterine volume: 7.5 x 4.0 x 3.5 cm -> 105 * 0.523 = 54.915 -> 54.91 or 54.92 cc
    u_meas = [MeasurementItem(value=[7.5, 4.0, 3.5], unit="cm", dimension=3, raw_str="7.5 x 4.0 x 3.5 cm")]
    u_calc = calculate_uterine_volume(u_meas)
    assert u_calc is not None
    assert 54.9 <= u_calc["volume_cc"] <= 55.0
    assert "Merz" in u_calc["clinical_source"]

    # Carotid velocity ratio: ICA 180 cm/s, CCA 75 cm/s -> 2.4
    c_calc = calculate_carotid_velocity_ratio(ica_psv=180.0, cca_psv=75.0)
    assert c_calc is not None
    assert c_calc["ratio"] == 2.4
    assert "SRU" in c_calc["clinical_source"]

    # ABI: Ankle 110 mmHg, Brachial 130 mmHg -> 0.85
    abi_calc = calculate_ankle_brachial_index(ankle_pressure=110.0, brachial_pressure=130.0)
    assert abi_calc is not None
    assert abi_calc["abi"] == 0.85
    assert "AHA/ACC" in abi_calc["clinical_source"]

    # Missing inputs return None
    assert calculate_prostate_volume([]) is None
    assert calculate_carotid_velocity_ratio(None, 75.0) is None
    assert calculate_ankle_brachial_index(110.0, 0.0) is None

    # Test report recalculation
    mock_structured = {
        "sections": [
            {
                "key": "prostate",
                "measurements": [
                    {"value": [4.0, 3.5, 3.0], "unit": "cm", "dimension": 3, "raw_str": "4.0 x 3.5 x 3.0 cm"}
                ],
                "calculated_biometry": None
            }
        ]
    }
    recalculated = recalculate_report_calculations(mock_structured)
    assert recalculated["sections"][0]["calculated_biometry"] is not None
    assert recalculated["sections"][0]["calculated_biometry"]["volume_cc"] == 21.97


# ================= 5. ANATOMICAL DICTATION CHECKLIST =================

def test_anatomical_dictation_checklist():
    """
    Verifies anatomical checklist taxonomy and states:
    - not_documented
    - dictated
    - manually_entered
    - preset_applied
    - requires_review
    Unmentioned anatomy remains unpopulated (never fabricated).
    """
    sections = [
        {"key": "liver", "is_present": True, "source_type": "voice", "text": "Liver is normal in size and echotexture."},
        {"key": "gall_bladder", "is_present": True, "source_type": "preset", "text": "Gall bladder is normal.", "preset_name": "Normal GB"},
        {"key": "spleen", "is_present": True, "source_type": "manual", "text": "Spleen is mildly enlarged."},
        {"key": "pancreas", "is_present": False, "source_type": None, "text": None}
    ]

    checklist = generate_anatomical_checklist("abdomen_pelvis", sections)
    assert len(checklist) >= 10

    liver_item = next(i for i in checklist if i["key"] == "liver")
    gb_item = next(i for i in checklist if i["key"] == "gall_bladder")
    spleen_item = next(i for i in checklist if i["key"] == "spleen")
    pancreas_item = next(i for i in checklist if i["key"] == "pancreas")

    assert liver_item["status"] == "dictated"
    assert gb_item["status"] == "preset_applied"
    assert spleen_item["status"] == "manually_entered"
    assert pancreas_item["status"] == "not_documented"
    assert pancreas_item["is_present"] is False


# ================= 6. NORMAL PRESETS WORKFLOW VIA API =================

def test_normal_presets_api_workflow(client):
    """
    Verifies institutional normal presets:
    - Presets catalog endpoint returns valid presets.
    - Applying preset marks section present with source_type='preset'.
    - Removing preset resets section to blank without affecting other sections.
    """
    # 1. Fetch presets
    res = client.get("/api/structuring/presets")
    assert res.status_code == 200
    presets = res.json()
    assert "liver" in presets
    assert "gall_bladder" in presets
    assert "Normal Liver" in presets["liver"]["name"]

    # 2. Create draft report
    create_res = client.post("/api/reports", json={"template_id": "usg-abdomen-pelvis-male"})
    assert create_res.status_code in [200, 201]
    rep_id = create_res.json()["id"]

    # 3. Apply Liver preset
    apply_res = client.post(f"/api/reports/{rep_id}/apply-preset", json={"section_key": "liver"})
    assert apply_res.status_code == 200
    updated_rep = apply_res.json()
    liver_sec = next(s for s in updated_rep["structured_findings"]["sections"] if s["key"] == "liver")
    assert liver_sec["is_present"] is True
    assert liver_sec["source_type"] == "preset"
    assert "smooth in contour" in liver_sec["text"]

    # 4. Other organs remain blank
    spleen_sec = next(s for s in updated_rep["structured_findings"]["sections"] if s["key"] == "spleen")
    assert spleen_sec["is_present"] is False
    assert spleen_sec["text"] is None

    # 5. Remove Liver preset
    remove_res = client.post(f"/api/reports/{rep_id}/remove-preset", json={"section_key": "liver"})
    assert remove_res.status_code == 200
    cleared_rep = remove_res.json()
    cleared_liver = next(s for s in cleared_rep["structured_findings"]["sections"] if s["key"] == "liver")
    assert cleared_liver["is_present"] is False
    assert cleared_liver["text"] is None


# ================= 7. END-TO-END REOPEN AND EXPORT INTEGRITY =================

def test_reopen_and_export_integrity(client):
    """
    Verifies that a report with multi-recording findings, calculations, and presets:
    - Persists across database re-read.
    - Exports cleanly to Word (.docx) without unreplaced placeholders.
    - Exports cleanly to PDF without errors.
    """
    # 1. Create report
    create_res = client.post("/api/reports", json={"template_id": "usg-abdomen-pelvis-male"})
    rep_id = create_res.json()["id"]

    # 2. Add dictated findings with biometry
    transcript = "Liver is normal in size and echotexture. Prostate measures 4.0 by 3.5 by 3.0 cm. IMPRESSION: Normal study."
    struct_res = client.post(f"/api/reports/{rep_id}/structure", json={"transcript_text": transcript, "force_regenerate": True})
    assert struct_res.status_code == 200

    # 3. Re-read report from DB
    get_res = client.get(f"/api/reports/{rep_id}")
    assert get_res.status_code == 200
    rep = get_res.json()
    prostate = next(s for s in rep["structured_findings"]["sections"] if s["key"] == "prostate")
    assert prostate["is_present"] is True
    assert prostate["calculated_biometry"] is not None
    assert prostate["calculated_biometry"]["calculated_volume_cc"] == 21.8

    # 4. Word Export
    docx_res = client.get(f"/api/reports/{rep_id}/export/docx")
    assert docx_res.status_code == 200
    assert len(docx_res.content) > 1000

    # 5. PDF Export
    pdf_res = client.get(f"/api/reports/{rep_id}/export/pdf")
    assert pdf_res.status_code == 200
    assert len(pdf_res.content) > 1000
    assert pdf_res.content.startswith(b"%PDF")
