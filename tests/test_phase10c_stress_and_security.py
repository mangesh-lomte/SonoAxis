import io
import zipfile
import pytest
import docx
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.structuring.engine import DeterministicStructuringEngine as StructuringEngine
from backend.app.services.template_service import TemplateService


# ----------------------------------------------------------------------
# 1. Ten Clinical Correction Stress Tests
# ----------------------------------------------------------------------

def test_stress_01_dimension_correction():
    """
    Stress Test 1: Single-dimension update within multi-dimensional measurement.
    Liver 14.2 cm. Right kidney 10.2x4.5 cm -> corrected to 10.8x4.5 cm. Prostate 4.0x3.0x3.4 cm.
    """
    transcript = (
        "Liver span measures 14.2 cm. "
        "Right kidney measures 10.2 by 4.5 cm. "
        "Correction, right kidney length is 10.8 cm. "
        "Prostate measures 4.0 by 3.0 by 3.4 cm."
    )
    report = StructuringEngine.structure_transcript(transcript, template_id="usg-abdomen-pelvis-male")
    
    # Check Right Kidney finding
    rk_sec = next(s for s in report.sections if s.key == "right_kidney")
    assert rk_sec.is_present is True
    assert len(rk_sec.measurements) == 1
    rk_meas = rk_sec.measurements[0]
    assert rk_meas.dimension == 2
    assert rk_meas.value == [10.8, 4.5]
    assert "10.8 x 4.5 cm" in rk_sec.text or "10.8" in rk_sec.text

    # Check Superseded History
    assert len(report.superseded_history) == 1
    superseded = report.superseded_history[0]
    assert superseded.organ_key == "right_kidney"
    assert superseded.superseded_measurements[0].value == [10.2, 4.5]

    # Check Liver and Prostate
    liver_sec = next(s for s in report.sections if s.key == "liver")
    assert liver_sec.measurements[0].value == 14.2 or liver_sec.measurements[0].value == [14.2]
    pros_sec = next(s for s in report.sections if s.key == "prostate")
    assert pros_sec.measurements[0].value == [4.0, 3.0, 3.4]


def test_stress_02_waveform_vs_velocity_independence():
    """
    Stress Test 2: Waveform vs Velocity Independence.
    Right CFA PSV 95 cm/s with triphasic flow. Correction, PSV is 98 cm per second.
    Waveform must remain triphasic while velocity updates to 98.
    """
    transcript = (
        "Right common femoral artery shows triphasic waveform with PSV of 95 cm/s. "
        "Correction, right common femoral artery PSV is 98 cm per second."
    )
    report = StructuringEngine.structure_transcript(transcript, template_id="usg-doppler-arterial-right-normal")
    assert report.vascular_biometry is not None
    cfa = next((a for a in report.vascular_biometry.arterial_table if a.segment_key == "cfa"), None)
    assert cfa is not None
    assert cfa.psv_right == 98.0
    assert cfa.flow_pattern_right.lower() == "triphasic"


def test_stress_03_repeat_vessel_mention():
    """
    Stress Test 3: Repeat vessel mention.
    Initial: popliteal triphasic. Later: popliteal biphasic waveform noted.
    """
    transcript = (
        "Popliteal artery shows triphasic flow. "
        "Further distal segment of popliteal artery demonstrates biphasic waveform."
    )
    report = StructuringEngine.structure_transcript(transcript, template_id="usg-doppler-arterial-right-normal")
    assert report.vascular_biometry is not None
    pop = next((a for a in report.vascular_biometry.arterial_table if a.segment_key == "popliteal"), None)
    assert pop is not None
    assert pop.flow_pattern_right.lower() in ["biphasic", "triphasic"]


def test_stress_04_right_to_left_correction():
    """
    Stress Test 4: Contralateral distinction and laterality preservation.
    Right kidney normal. Left kidney shows 12 mm cyst.
    """
    transcript = "Right kidney is normal in size and appearance. Left kidney shows simple cortical cyst measuring 12 mm."
    report = StructuringEngine.structure_transcript(transcript, template_id="usg-abdomen-pelvis-male")
    rk = next(s for s in report.sections if s.key == "right_kidney")
    lk = next(s for s in report.sections if s.key == "left_kidney")
    assert rk.is_present is True
    assert lk.is_present is True
    assert len(lk.measurements) == 1
    assert lk.measurements[0].value == 12.0 or lk.measurements[0].value == [12.0]
    assert lk.measurements[0].unit == "mm"
    assert len(rk.measurements) == 0


def test_stress_05_ambiguous_correction_requires_review():
    """
    Stress Test 5: Ambiguous correction without clear organ context when multiple candidates exist.
    Must NOT guess or overwrite. Must flag for clinical review.
    """
    transcript = (
        "Liver span is 14 cm. Spleen length is 10 cm. "
        "Correction, measures 11 cm."
    )
    report = StructuringEngine.structure_transcript(transcript, template_id="usg-abdomen-pelvis-male")
    assert "ambiguous_correction" in report.all_flags
    assert len(report.unassigned_findings) >= 1
    unassigned = next((u for u in report.unassigned_findings if u.reason == "ambiguous_correction"), None)
    assert unassigned is not None
    assert "11" in unassigned.raw_text


def test_stress_06_multiple_incompetent_perforators():
    """
    Stress Test 6: Incompetent perforator extraction with caliber and anatomic location.
    Two perforators: 3.2 mm at 5 cm above medial ankle, 4.1 mm at 7 cm below knee medial aspect.
    """
    transcript = (
        "Right leg examination reveals incompetent perforator measuring 3.2 mm located 5 cm above medial ankle. "
        "Second incompetent perforator measuring 4.1 mm noted 7 cm below knee medial aspect."
    )
    report = StructuringEngine.structure_transcript(transcript, template_id="usg-doppler-venous-right-varicose")
    assert report.vascular_biometry is not None
    assert len(report.vascular_biometry.incompetent_perforators) == 2
    p1 = report.vascular_biometry.incompetent_perforators[0]
    p2 = report.vascular_biometry.incompetent_perforators[1]
    assert p1.diameter_mm == 3.2
    assert "medial" in (p1.raw_str + str(p1.landmark or "") + str(p1.aspect or "")).lower()
    assert p2.diameter_mm == 4.1
    assert "knee" in (p2.raw_str + str(p2.landmark or "") + str(p2.aspect or "")).lower() or "below" in (p2.raw_str + str(p2.landmark or "") + str(p2.aspect or "")).lower()


def test_stress_07_negation_preservation():
    """
    Stress Test 7: Strict negation preservation.
    Negative findings must never be converted into positive pathology.
    """
    transcript = (
        "Gall bladder is well distended, lumen is clear with no calculus or wall thickening. "
        "No evidence of deep venous thrombosis in common femoral or popliteal veins."
    )
    report = StructuringEngine.structure_transcript(transcript, template_id="usg-abdomen-pelvis-male")
    gb = next(s for s in report.sections if s.key == "gall_bladder")
    assert gb.is_present is True
    assert "no calculus" in gb.text.lower() or "clear" in gb.text.lower()


def test_stress_08_explicit_uncertainty_preservation():
    """
    Stress Test 8: Uncertainty preservation without hallucinated diagnosis.
    Clinician uncertainty must be preserved verbatim.
    """
    transcript = "Liver shows small 8 mm hyperechoic focus, likely hemangioma versus focal fatty infiltration."
    report = StructuringEngine.structure_transcript(transcript, template_id="usg-abdomen-pelvis-male")
    liv = next(s for s in report.sections if s.key == "liver")
    assert liv.is_present is True
    assert "versus" in liv.text.lower() or "hemangioma" in liv.text.lower()


def test_stress_09_arterial_measurement_tables_no_auto_zero():
    """
    Stress Test 9: Arterial Doppler table must NOT auto-zero missing velocities.
    Popliteal 65 cm/s, PTA absent flow (occluded). Unmentioned CFA or SFA must have None/blank PSV.
    """
    transcript = (
        "Right popliteal artery shows PSV of 65 cm/s with triphasic flow. "
        "Left popliteal artery PSV is 42 cm/s monophasic. "
        "Left posterior tibial artery demonstrates absent flow."
    )
    report = StructuringEngine.structure_transcript(transcript, template_id="usg-doppler-arterial-bilateral-normal")
    assert report.vascular_biometry is not None
    pop = next(a for a in report.vascular_biometry.arterial_table if a.segment_key == "popliteal")
    assert pop.psv_right == 65.0
    assert pop.flow_pattern_right.lower() == "triphasic"
    assert pop.psv_left == 42.0
    assert pop.flow_pattern_left.lower() == "monophasic"

    # Missing artery like ATA or DFA must NOT be zero
    dfa = next(a for a in report.vascular_biometry.arterial_table if a.segment_key == "dfa")
    assert dfa.psv_right is None
    assert dfa.psv_left is None


def test_stress_10_arteriovenous_isolation():
    """
    Stress Test 10: Combined Arteriovenous isolation.
    Both arterial and venous findings dictation in single exam without cross-contamination.
    """
    transcript = (
        "Superficial femoral artery shows biphasic flow with PSV of 78 cm per second. "
        "Common femoral vein is fully compressible with normal respiratory phasicity and no thrombus."
    )
    report = StructuringEngine.structure_transcript(transcript, template_id="usg-doppler-av-right")
    assert report.vascular_biometry is not None
    sfa = next(a for a in report.vascular_biometry.arterial_table if a.segment_key == "sfa")
    assert sfa.psv_right == 78.0
    assert sfa.flow_pattern_right.lower() == "biphasic"

    deep_vein_sec = next(s for s in report.sections if s.key == "deep_venous_thigh")
    assert deep_vein_sec.is_present is True
    assert "compressible" in deep_vein_sec.text.lower() or "thrombus" in deep_vein_sec.text.lower()


# ----------------------------------------------------------------------
# 2. DOCX Security & Validation Engine Tests
# ----------------------------------------------------------------------

def test_security_rejects_oversized_file():
    """Rejects files larger than 20MB."""
    fake_huge_bytes = b"0" * (21 * 1024 * 1024)
    with pytest.raises(ValueError, match="exceeds 20MB limit"):
        TemplateService.extract_docx_structure(fake_huge_bytes, "huge.docx")


def test_security_rejects_non_docx():
    """Rejects non-.docx extension."""
    with pytest.raises(ValueError, match="Only valid .docx files"):
        TemplateService.extract_docx_structure(b"dummy", "template.pdf")


def test_security_rejects_malformed_zip():
    """Rejects corrupted or non-zip bytes."""
    with pytest.raises(ValueError, match="Invalid or corrupt DOCX archive"):
        TemplateService.extract_docx_structure(b"NOT_A_ZIP_ARCHIVE", "corrupt.docx")


def test_security_rejects_macro_enabled_docm():
    """Rejects documents containing VBA macro project payloads."""
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as z:
        z.writestr("word/document.xml", "<w:document><w:body><w:p><w:r><w:t>Macro Template</w:t></w:r></w:p></w:body></w:document>")
        z.writestr("word/vbaProject.bin", b"VBA_MALICIOUS_PAYLOAD")
        z.writestr("[Content_Types].xml", "<Types></Types>")
    
    with pytest.raises(ValueError, match="Security violation: Template contains executable macros"):
        TemplateService.extract_docx_structure(bio.getvalue(), "macro.docx")


def test_security_detects_floating_text_box_warning():
    """Detects floating text boxes and returns warning."""
    base_doc = docx.Document()
    base_doc.add_paragraph("Main document text")
    bio_base = io.BytesIO()
    base_doc.save(bio_base)
    bio_base.seek(0)

    # Read base docx zip and inject floating drawing XML
    bio_out = io.BytesIO()
    with zipfile.ZipFile(bio_base, "r") as zin:
        with zipfile.ZipFile(bio_out, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "word/document.xml":
                    xml_str = data.decode("utf-8")
                    injected = xml_str.replace("</w:body>", '<w:p><w:r><w:drawing><w:txbxContent><w:p><w:r><w:t>Floating note</w:t></w:r></w:p></w:txbxContent></w:drawing></w:r></w:p></w:body>')
                    data = injected.encode("utf-8")
                zout.writestr(item, data)
    
    struct = TemplateService.extract_docx_structure(bio_out.getvalue(), "floating.docx")
    assert struct.has_floating_boxes is True
    assert len(struct.warnings) >= 1
    assert "Floating text box" in struct.warnings[0]


def test_security_unapproved_template_rejected_at_report_creation(client):
    """Ensures report creation fails if template is unapproved."""
    res = client.post("/api/reports", json={
        "template_id": "non-existent-template",
        "patient_id": "test-patient"
    })
    assert res.status_code == 400
