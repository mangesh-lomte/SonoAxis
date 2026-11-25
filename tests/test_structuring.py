import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.structuring.engine import structuring_engine
from backend.app.structuring.templates import get_template_def
from backend.app.schemas.structuring import StructuringRequest, ManualAssignmentRequest


# 1. Male template initialization
def test_male_template_initialization():
    t = get_template_def("usg-abdomen-pelvis-male")
    assert t["gender"] == "Male"
    keys = [s["key"] for s in t["sections"]]
    assert "prostate" in keys
    assert "uterus" not in keys

# 2. Female template initialization
def test_female_template_initialization():
    t = get_template_def("usg-abdomen-pelvis-female")
    assert t["gender"] == "Female"
    keys = [s["key"] for s in t["sections"]]
    assert "uterus" in keys
    assert "endometrium" in keys
    assert "ovaries_bilateral" in keys
    assert "prostate" not in keys

# 3 & 4. Blank initialization & blank findings
def test_blank_report_initialization():
    res = structuring_engine.structure_transcript("", template_id="usg-abdomen-pelvis-male")
    assert res.impression is None
    assert len(res.unassigned_findings) == 0
    for s in res.sections:
        assert s.is_present is False
        assert s.text is None
        assert len(s.measurements) == 0

# 5 & 6. Correct anatomical ordering with out-of-order findings
def test_out_of_order_findings_and_canonical_order():
    dictation = "Right kidney measures 10.2 cm. Spleen measures 11 cm. Liver is normal in size."
    res = structuring_engine.structure_transcript(dictation, template_id="usg-abdomen-pelvis-male")
    active_keys = [s.key for s in res.sections if s.is_present]
    # Liver (order 1) must come before Spleen (order 6) which must come before Right Kidney (order 7)
    assert active_keys == ["liver", "spleen", "right_kidney"]
    # Check that other organs are blank
    left_kidney = next(s for s in res.sections if s.key == "left_kidney")
    assert left_kidney.is_present is False
    assert left_kidney.text is None

# 7. Organ synonyms recognition
def test_organ_synonyms():
    dictation = "Hepatic parenchyma unremarkable. GB shows no calculus. Splenic vein normal. UB well distended."
    res = structuring_engine.structure_transcript(dictation, template_id="usg-abdomen-pelvis-male")
    active = {s.key for s in res.sections if s.is_present}
    assert "liver" in active
    assert "gall_bladder" in active
    assert "spleen" in active
    assert "urinary_bladder" in active

# 8. Decimal measurement preservation
def test_decimal_measurements():
    dictation = "Liver span 14.5 cm. Right renal length 10.2 cm."
    res = structuring_engine.structure_transcript(dictation)
    liver = next(s for s in res.sections if s.key == "liver")
    rk = next(s for s in res.sections if s.key == "right_kidney")
    assert any(m.raw_str == "14.5 cm" for m in liver.measurements)
    assert any(m.raw_str == "10.2 cm" for m in rk.measurements)

# 9. Multiple measurement dimensions (1D, 2D, 3D)
def test_multidimensional_measurements():
    dictation = "Right kidney measures 10.2 by 4.5 cm. Uterus measures 7.2 x 3.5 x 4.1 cm. Endometrium measures 6 mm."
    res = structuring_engine.structure_transcript(dictation, template_id="usg-abdomen-pelvis-female")
    rk = next(s for s in res.sections if s.key == "right_kidney")
    uterus = next(s for s in res.sections if s.key == "uterus")
    endo = next(s for s in res.sections if s.key == "endometrium")
    assert rk.measurements[0].dimension == 2
    assert uterus.measurements[0].dimension == 3
    assert endo.measurements[0].dimension == 1

# 10. Missing units detection
def test_missing_units_detection():
    dictation = "A focal lesion measuring 15 is noted."
    res = structuring_engine.structure_transcript(dictation)
    assert len(res.unassigned_findings) > 0
    unassigned = res.unassigned_findings[0]
    assert any(m.flag_missing_unit for m in unassigned.measurements)

# 11. Right and left kidney separation
def test_kidney_separation():
    dictation = "Right kidney measures 10.2 cm and left kidney measures 9.8 cm."
    res = structuring_engine.structure_transcript(dictation)
    rk = next(s for s in res.sections if s.key == "right_kidney")
    lk = next(s for s in res.sections if s.key == "left_kidney")
    assert rk.is_present and "10.2" in rk.text
    assert lk.is_present and "9.8" in lk.text

# 12 & 13. Ovarian separation and bilateral findings
def test_ovary_separation():
    dictation = "Right ovary measures 3.0 by 2.0 cm. Left ovary measures 2.5 by 1.8 cm."
    res = structuring_engine.structure_transcript(dictation, template_id="usg-abdomen-pelvis-female")
    ro = next(s for s in res.sections if s.key == "right_ovary")
    lo = next(s for s in res.sections if s.key == "left_ovary")
    assert ro.is_present and "3.0" in ro.text
    assert lo.is_present and "2.5" in lo.text

def test_bilateral_ovaries():
    dictation = "Both ovaries are normal in size. No adnexal mass."
    res = structuring_engine.structure_transcript(dictation, template_id="usg-abdomen-pelvis-female")
    bo = next(s for s in res.sections if s.key == "ovaries_bilateral")
    assert bo.is_present
    assert "Both ovaries are normal" in bo.text

# 14 & 15. Negation and uncertainty preservation
def test_negation_and_uncertainty():
    dictation = "No gallstones are seen. Possible small cyst in left kidney. Cannot exclude a focal liver lesion."
    res = structuring_engine.structure_transcript(dictation)
    gb = next(s for s in res.sections if s.key == "gall_bladder")
    lk = next(s for s in res.sections if s.key == "left_kidney")
    liver = next(s for s in res.sections if s.key == "liver")
    assert gb.findings[0].is_negation is True
    assert lk.findings[0].is_uncertain is True
    assert liver.findings[0].is_uncertain is True

# 16 & 17. The Mandatory Explicit Correction Test
def test_mandatory_explicit_correction():
    dictation = "Right kidney measures 10.2 cm. Liver is normal in size. Correction: right kidney measures 10.8 cm."
    res = structuring_engine.structure_transcript(dictation)
    active_keys = [s.key for s in res.sections if s.is_present]
    assert "liver" in active_keys
    assert "right_kidney" in active_keys
    assert "left_kidney" not in active_keys
    
    rk = next(s for s in res.sections if s.key == "right_kidney")
    assert "10.8 cm" in rk.text
    assert "10.2 cm" not in rk.text
    assert any(m.raw_str == "10.8 cm" for m in rk.measurements)
    assert not any(m.raw_str == "10.2 cm" for m in rk.measurements)
    
    # Audit history check
    assert len(res.superseded_history) == 1
    assert res.superseded_history[0].organ_key == "right_kidney"
    assert "10.2 cm" in res.superseded_history[0].superseded_text

# 18. Ambiguous correction
def test_ambiguous_correction():
    dictation = "Liver is normal in size. Correction."
    res = structuring_engine.structure_transcript(dictation)
    assert len(res.unassigned_findings) > 0
    assert any(u.reason == "ambiguous_correction" for u in res.unassigned_findings)

# 19. Correction without deleting unrelated findings
def test_correction_preserves_unrelated_findings():
    dictation = "Right kidney measures 10.2 cm. No hydronephrosis in the right kidney. Correction: right kidney measures 10.8 cm."
    res = structuring_engine.structure_transcript(dictation)
    rk = next(s for s in res.sections if s.key == "right_kidney")
    assert "10.8 cm" in rk.text
    assert "No hydronephrosis" in rk.text
    assert "10.2 cm" not in rk.text

# 20 & 21. Comma-separated Whisper transcripts
def test_comma_separated_whisper_transcript():
    dictation = "Right kidney measures 10.2 cm, liver is normal in size, correction, right kidney measures 10.8 cm."
    res = structuring_engine.structure_transcript(dictation)
    rk = next(s for s in res.sections if s.key == "right_kidney")
    liver = next(s for s in res.sections if s.key == "liver")
    assert liver.is_present
    assert "10.8 cm" in rk.text
    assert "10.2 cm" not in rk.text

# 22 & 23. Repeated statements & multiple findings
def test_multiple_findings_in_one_organ():
    dictation = "Liver measures 14.5 cm. Liver shows increased echotexture. No focal liver lesion."
    res = structuring_engine.structure_transcript(dictation)
    liver = next(s for s in res.sections if s.key == "liver")
    assert len(liver.findings) == 3
    assert "14.5 cm" in liver.text
    assert "increased echotexture" in liver.text
    assert "No focal liver lesion" in liver.text

# 24 & 25. Unassigned findings & manual assignment
def test_unassigned_findings_and_manual_assignment(client):
    dictation = "A small cyst measuring 8 mm is noted."
    res = structuring_engine.structure_transcript(dictation)
    assert len(res.unassigned_findings) == 1
    unassigned = res.unassigned_findings[0]
    assert unassigned.reason == "no_organ_identified"
    assert "8 mm" in [m.raw_str for m in unassigned.measurements]

    # Test assignment API endpoint
    assign_req = ManualAssignmentRequest(
        unassigned_id=unassigned.id,
        target_organ_key="liver",
        custom_text="Simple hepatic cyst measuring 8 mm."
    )
    res_assign = client.post("/api/structuring/assign-unassigned", json={
        "req": assign_req.model_dump(),
        "report": res.model_dump()
    })
    assert res_assign.status_code == 200
    updated_report = res_assign.json()
    liver_sec = next(s for s in updated_report["sections"] if s["key"] == "liver")
    assert liver_sec["is_present"] is True
    assert "Simple hepatic cyst measuring 8 mm" in liver_sec["text"]

# 26 & 27. Impression handling
def test_impression_explicit_vs_undictated():
    # Undictated -> None
    res_undictated = structuring_engine.structure_transcript("Liver normal in size.")
    assert res_undictated.impression is None

    # Dictated -> captured
    res_dictated = structuring_engine.structure_transcript("Liver normal in size. Impression: mild fatty liver.")
    assert res_dictated.impression == "mild fatty liver"

# 28. Male-specific Prostate & Biometry
def test_male_prostate_biometry():
    dictation = "Prostate measures 4.0 by 3.5 by 3.0 cm."
    res = structuring_engine.structure_transcript(dictation, template_id="usg-abdomen-pelvis-male")
    prostate = next(s for s in res.sections if s.key == "prostate")
    assert prostate.is_present is True
    assert prostate.calculated_biometry is not None
    assert prostate.calculated_biometry["calculated_volume_cc"] == 21.8

# 29 & 30. Incompatible anatomy handling
def test_incompatible_anatomy():
    # Male report with uterine dictation
    res_male = structuring_engine.structure_transcript("Uterus measures 7.0 cm.", template_id="usg-abdomen-pelvis-male")
    assert len(res_male.unassigned_findings) == 1
    assert "incompatible_anatomy_male" in res_male.unassigned_findings[0].reason

    # Female report with prostate dictation
    res_female = structuring_engine.structure_transcript("Prostate measures 25 cc.", template_id="usg-abdomen-pelvis-female")
    assert len(res_female.unassigned_findings) == 1
    assert "incompatible_anatomy_female" in res_female.unassigned_findings[0].reason

# 31. Original transcript preservation & Source text references
def test_transcript_preservation():
    dictation = "Spleen is normal. Right kidney 10.2 cm."
    res = structuring_engine.structure_transcript(dictation)
    assert res.raw_transcript == dictation
    for s in res.sections:
        for f in s.findings:
            assert f.source_text in dictation

# 32. API endpoints validation
def test_api_structuring_endpoints(client):
    res = client.get("/api/structuring/templates")
    assert res.status_code == 200
    assert len(res.json()["templates"]) == 2

    res_post = client.post("/api/structuring/process", json={
        "transcript": "Liver is normal in size.",
        "template_id": "usg-abdomen-pelvis-male"
    })
    assert res_post.status_code == 200
    data = res_post.json()
    assert data["template_id"] == "usg-abdomen-pelvis-male"
    liver = next(s for s in data["sections"] if s["key"] == "liver")
    assert liver["is_present"] is True

# 33. Empty and Long transcripts
def test_empty_and_long_transcripts():
    res_empty = structuring_engine.structure_transcript("")
    assert res_empty.has_flags is False

    long_text = "Liver is normal. " * 50
    res_long = structuring_engine.structure_transcript(long_text)
    liver = next(s for s in res_long.sections if s.key == "liver")
    assert liver.is_present is True
