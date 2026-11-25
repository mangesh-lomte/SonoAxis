import os
import io
import json
import hashlib
import tempfile
import pytest
import docx
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.db.schema import init_db
from backend.app.services.report_service import ReportService
from backend.app.services.patient_service import PatientService
from backend.app.export.word_service import WordExportService, BASELINE_HASHES
from backend.app.export.pdf_service import PDFExportService
from backend.app.export.preview_service import PreviewService
from tests.conftest import seed_and_login_test_client

@pytest.fixture
def temp_db(tmp_path):
    db_file = os.path.join(tmp_path, "test_export.db")
    init_db(db_file)
    return db_file

@pytest.fixture
def test_client(temp_db, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_PATH", temp_db)
    with TestClient(app) as tc:
        seed_and_login_test_client(tc, role="Radiologist", db_path=temp_db)
        yield tc

@pytest.fixture
def sample_male_report_data():
    return {
        "id": "rep-male-001",
        "report_number": "REP-2026-M01",
        "template_id": "usg-abdomen-pelvis-male",
        "status": "DRAFT",
        "report_date": "2026-11-24",
        "referral_doctor": "Dr. Sameer Joshi",
        "patient_snapshot": {
            "full_name": "Ramesh Chandra",
            "age_years": 48,
            "gender": "Male",
            "patient_id": "P-9871"
        },
        "structured_findings": {
            "sections": [
                {"key": "liver", "label": "Liver", "is_present": True, "text": "Normal in size (13.2 cm) with normal echotexture."},
                {"key": "gall_bladder", "label": "Gall Bladder", "is_present": True, "text": "Physiologically distended. No calculus."},
                {"key": "right_kidney", "label": "Right Kidney", "is_present": True, "text": "Measures 10.8 cm. Normal parenchymal thickness."},
                {"key": "spleen", "label": "Spleen", "is_present": False, "text": ""},
                {"key": "prostate", "label": "Prostate", "is_present": False, "text": ""}
            ],
            "impression": "Normal ultrasound study of upper abdomen."
        }
    }

@pytest.fixture
def sample_female_report_data():
    return {
        "id": "rep-female-002",
        "report_number": "REP-2026-F02",
        "template_id": "usg-abdomen-pelvis-female",
        "status": "DRAFT",
        "report_date": "2026-11-24",
        "referral_doctor": "Dr. Sunita Rao",
        "patient_snapshot": {
            "full_name": "Pooja Hegde",
            "age_years": 32,
            "gender": "Female",
            "patient_id": "P-8842"
        },
        "structured_findings": {
            "sections": [
                {"key": "liver", "label": "Liver", "is_present": True, "text": "Normal in size. No focal lesion."},
                {"key": "uterus", "label": "Uterus", "is_present": True, "text": "Anteverted, normal in size (7.0 x 3.5 x 4.0 cm)."},
                {"key": "endometrium", "label": "Endometrium", "is_present": True, "text": "Thickness measures 6.2 mm."},
                {"key": "ovaries_bilateral", "label": "Bilateral Ovaries", "is_present": True, "text": "Both ovaries appear normal in size."},
                {"key": "pancreas", "label": "Pancreas", "is_present": False, "text": ""},
                {"key": "spleen", "label": "Spleen", "is_present": False, "text": ""}
            ],
            "impression": None
        }
    }

# ================= 1. TEMPLATE INTEGRITY TESTS =================

def test_01_male_template_sha256_hash_baseline():
    path = "references/male-abdomen-pelvis.docx"
    assert os.path.exists(path)
    with open(path, "rb") as f:
        actual_hash = hashlib.sha256(f.read()).hexdigest().upper()
    assert actual_hash == BASELINE_HASHES[path]

def test_02_female_template_sha256_hash_baseline():
    path = "references/female-abdomen-pelvis.docx"
    assert os.path.exists(path)
    with open(path, "rb") as f:
        actual_hash = hashlib.sha256(f.read()).hexdigest().upper()
    assert actual_hash == BASELINE_HASHES[path]

def test_03_word_export_never_modifies_disk_reference_male(sample_male_report_data):
    path = "references/male-abdomen-pelvis.docx"
    before_hash = hashlib.sha256(open(path, "rb").read()).hexdigest().upper()
    _ = WordExportService.generate_docx(sample_male_report_data)
    after_hash = hashlib.sha256(open(path, "rb").read()).hexdigest().upper()
    assert before_hash == after_hash

def test_04_word_export_never_modifies_disk_reference_female(sample_female_report_data):
    path = "references/female-abdomen-pelvis.docx"
    before_hash = hashlib.sha256(open(path, "rb").read()).hexdigest().upper()
    _ = WordExportService.generate_docx(sample_female_report_data)
    after_hash = hashlib.sha256(open(path, "rb").read()).hexdigest().upper()
    assert before_hash == after_hash

# ================= 2. WORD EXPORT STRUCTURE TESTS =================

def test_05_word_export_returns_valid_docx_bytes(sample_male_report_data):
    b = WordExportService.generate_docx(sample_male_report_data)
    assert isinstance(b, bytes)
    assert len(b) > 5000
    doc = docx.Document(io.BytesIO(b))
    assert len(doc.paragraphs) > 0

def test_06_word_export_table0_patient_mapping_male(sample_male_report_data):
    b = WordExportService.generate_docx(sample_male_report_data)
    doc = docx.Document(io.BytesIO(b))
    t0 = doc.tables[0]
    assert "Ramesh Chandra" in t0.rows[0].cells[0].text
    assert "48 years" in t0.rows[0].cells[1].text
    assert "Sex: Male" in t0.rows[0].cells[1].text
    assert "Age: Male" not in t0.rows[0].cells[1].text
    assert "P-9871" in t0.rows[1].cells[0].text
    assert "24.11.2026" in t0.rows[1].cells[1].text
    assert "Dr. Sameer Joshi" in t0.rows[2].cells[0].text

def test_07_word_export_table0_patient_mapping_female(sample_female_report_data):
    b = WordExportService.generate_docx(sample_female_report_data)
    doc = docx.Document(io.BytesIO(b))
    t0 = doc.tables[0]
    assert "Pooja Hegde" in t0.rows[0].cells[0].text
    assert "32 years" in t0.rows[0].cells[1].text
    assert "Sex: Female" in t0.rows[0].cells[1].text
    assert "Age: Female" not in t0.rows[0].cells[1].text
    assert "P-8842" in t0.rows[1].cells[0].text
    assert "24.11.2026" in t0.rows[1].cells[1].text
    assert "Dr. Sunita Rao" in t0.rows[2].cells[0].text

def test_08_word_export_draft_banners_present_on_draft(sample_male_report_data):
    sample_male_report_data["status"] = "DRAFT"
    b = WordExportService.generate_docx(sample_male_report_data)
    doc = docx.Document(io.BytesIO(b))
    all_text = "\n".join(p.text for p in doc.paragraphs)
    assert "*** DRAFT — REQUIRES RADIOLOGIST REVIEW ***" in all_text
    assert "*** DRAFT — REQUIRES RADIOLOGIST REVIEW — NOT FOR CLINICAL USE ***" in all_text

def test_09_word_export_draft_banners_absent_on_reviewed(sample_male_report_data):
    sample_male_report_data["status"] = "REVIEWED"
    sample_male_report_data["reviewed_by"] = "Dr. Aarav Sharma"
    sample_male_report_data["reviewed_at"] = "2026-11-24 17:00"
    b = WordExportService.generate_docx(sample_male_report_data)
    doc = docx.Document(io.BytesIO(b))
    all_text = "\n".join(p.text for p in doc.paragraphs)
    assert "*** DRAFT" not in all_text
    assert "NOT FOR CLINICAL USE" not in all_text
    assert "Reviewed and clinically verified by: Dr. Aarav Sharma on 2026-11-24 17:00" in all_text

def test_10_word_export_zero_fabrication_unmentioned_organs_blank(sample_male_report_data):
    # Only Liver, Gall Bladder and Right Kidney were dictated
    b = WordExportService.generate_docx(sample_male_report_data)
    doc = docx.Document(io.BytesIO(b))
    body_paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    body_str = " ".join(body_paragraphs)
    
    assert "Liver:" in body_str
    assert "Gall Bladder:" in body_str
    assert "Right Kidney:" in body_str
    
    # Spleen, Pancreas, Prostate were not dictated: must NOT have sample normal text
    assert "Spleen:" not in body_str
    assert "Pancreas:" not in body_str
    assert "Prostate:" not in body_str
    assert "21.5 cc" not in body_str  # Old template prostate measurement
    assert "9 cm" not in body_str     # Old template spleen measurement
    assert "14 cm" not in body_str    # Old template liver measurement

def test_11_word_export_undictated_impression_remains_blank(sample_female_report_data):
    sample_female_report_data["structured_findings"]["impression"] = None
    sample_female_report_data["impression"] = None
    b = WordExportService.generate_docx(sample_female_report_data)
    doc = docx.Document(io.BytesIO(b))
    all_text = "\n".join(p.text for p in doc.paragraphs)
    # Heading is preserved per approved template, but findings content remains strictly blank
    assert "IMPRESSION:" in all_text
    assert "No significant abnormality detected." not in all_text

def test_12_word_export_dictated_impression_rendered(sample_male_report_data):
    sample_male_report_data["structured_findings"]["impression"] = "Grade I fatty liver."
    b = WordExportService.generate_docx(sample_male_report_data)
    doc = docx.Document(io.BytesIO(b))
    all_text = "\n".join(p.text for p in doc.paragraphs)
    assert "IMPRESSION: Grade I fatty liver." in all_text

def test_13_word_export_female_organs_rendered(sample_female_report_data):
    b = WordExportService.generate_docx(sample_female_report_data)
    doc = docx.Document(io.BytesIO(b))
    all_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Uterus:" in all_text
    assert "Endometrium" in all_text
    assert "Both ovaries appear normal in size." in all_text
    assert "Prostate" not in all_text

def test_14_word_export_signature_block_preserved(sample_male_report_data):
    b = WordExportService.generate_docx(sample_male_report_data)
    doc = docx.Document(io.BytesIO(b))
    all_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Chief Radiologist" in all_text
    assert "Consultant Radiologist" in all_text

# ================= 3. HTML PREVIEW SERVICE TESTS =================

def test_15_preview_service_renders_html_string(sample_male_report_data):
    html_content = PreviewService.render_html(sample_male_report_data)
    assert "<!DOCTYPE html>" in html_content
    assert "ULTRASOUND ABDOMEN AND PELVIS" in html_content

def test_16_preview_service_draft_banner(sample_male_report_data):
    sample_male_report_data["status"] = "DRAFT"
    html_content = PreviewService.render_html(sample_male_report_data)
    assert "*** DRAFT — REQUIRES RADIOLOGIST REVIEW ***" in html_content
    assert "*** DRAFT — REQUIRES RADIOLOGIST REVIEW — NOT FOR CLINICAL USE ***" in html_content

def test_17_preview_service_reviewed_metadata(sample_male_report_data):
    sample_male_report_data["status"] = "REVIEWED"
    sample_male_report_data["reviewed_by"] = "Dr. Aarav Sharma"
    sample_male_report_data["reviewed_at"] = "2026-11-24"
    html_content = PreviewService.render_html(sample_male_report_data)
    assert "<div class='draft-banner-top'>" not in html_content
    assert "<div class='draft-banner-bottom'>" not in html_content
    assert "*** DRAFT" not in html_content
    assert "Reviewed and clinically verified by: Dr. Aarav Sharma on 2026-11-24" in html_content

def test_18_preview_service_patient_info_table(sample_male_report_data):
    html_content = PreviewService.render_html(sample_male_report_data)
    assert "Ramesh Chandra" in html_content
    assert "Age: 48 years" in html_content
    assert "Sex: Male" in html_content
    assert "Age: Male" not in html_content
    assert "P-9871" in html_content
    assert "Dr. Sameer Joshi" in html_content

def test_19_preview_service_blank_unmentioned_organs(sample_male_report_data):
    html_content = PreviewService.render_html(sample_male_report_data)
    assert "Liver" in html_content
    assert "Right Kidney" in html_content
    assert "Prostate" not in html_content
    assert "Spleen" not in html_content

def test_20_preview_service_css_letter_geometry(sample_male_report_data):
    html_content = PreviewService.render_html(sample_male_report_data)
    assert "size: letter portrait" in html_content
    assert "1.0in 1.125in 0.5in 1.25in" in html_content

# ================= 4. PDF EXPORT SERVICE TESTS =================

def test_21_pdf_export_is_available():
    assert PDFExportService.is_available() is True
    assert PDFExportService.get_edge_path() is not None

def test_22_pdf_export_generates_valid_pdf_male(sample_male_report_data):
    pdf_bytes = PDFExportService.generate_pdf(sample_male_report_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 20000
    assert pdf_bytes.startswith(b"%PDF-")

def test_23_pdf_export_generates_valid_pdf_female(sample_female_report_data):
    pdf_bytes = PDFExportService.generate_pdf(sample_female_report_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 20000
    assert pdf_bytes.startswith(b"%PDF-")

def test_24_pdf_export_reviewed_status(sample_male_report_data):
    sample_male_report_data["status"] = "REVIEWED"
    sample_male_report_data["reviewed_by"] = "Dr. Test Radiologist"
    sample_male_report_data["reviewed_at"] = "2026-11-24"
    pdf_bytes = PDFExportService.generate_pdf(sample_male_report_data)
    assert pdf_bytes.startswith(b"%PDF-")

# ================= 5. API ENDPOINTS TESTS =================

def test_25_api_exports_status(test_client):
    res = test_client.get("/api/exports/status")
    assert res.status_code == 200
    data = res.json()
    assert data["docx_export"] is True
    assert data["pdf_export"] is True
    assert "Microsoft Edge" in data["pdf_engine"]

def test_26_api_preview_endpoint_html(temp_db, test_client):
    p = PatientService.create_patient({"full_name": "Test Patient", "patient_id": "TP-01", "gender": "MALE", "age_years": 40}, db_path=temp_db)
    r = ReportService.create_report({"patient_id": p["id"], "template_id": "usg-abdomen-pelvis-male"}, db_path=temp_db)
    
    res = test_client.get(f"/api/reports/{r['id']}/preview")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "ULTRASOUND ABDOMEN AND PELVIS" in res.text

def test_27_api_preview_endpoint_json(temp_db, test_client):
    p = PatientService.create_patient({"full_name": "Test Patient", "patient_id": "TP-02", "gender": "FEMALE", "age_years": 30}, db_path=temp_db)
    r = ReportService.create_report({"patient_id": p["id"], "template_id": "usg-abdomen-pelvis-female"}, db_path=temp_db)
    
    res = test_client.get(f"/api/reports/{r['id']}/preview?format=json")
    assert res.status_code == 200
    data = res.json()
    assert "html" in data
    assert data["report_id"] == r["id"]

def test_28_api_export_docx_endpoint(temp_db, test_client):
    p = PatientService.create_patient({"full_name": "Docx User", "patient_id": "TP-03", "gender": "MALE", "age_years": 50}, db_path=temp_db)
    r = ReportService.create_report({"patient_id": p["id"], "template_id": "usg-abdomen-pelvis-male"}, db_path=temp_db)
    
    res = test_client.get(f"/api/reports/{r['id']}/export/docx")
    assert res.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in res.headers["content-type"]
    assert "attachment; filename=" in res.headers["content-disposition"]
    assert len(res.content) > 5000

def test_29_api_export_pdf_endpoint(temp_db, test_client):
    p = PatientService.create_patient({"full_name": "Pdf User", "patient_id": "TP-04", "gender": "FEMALE", "age_years": 25}, db_path=temp_db)
    r = ReportService.create_report({"patient_id": p["id"], "template_id": "usg-abdomen-pelvis-female"}, db_path=temp_db)
    
    res = test_client.get(f"/api/reports/{r['id']}/export/pdf")
    assert res.status_code == 200
    assert "application/pdf" in res.headers["content-type"]
    assert "attachment; filename=" in res.headers["content-disposition"]
    assert res.content.startswith(b"%PDF-")

def test_30_api_export_404_on_nonexistent_report(test_client):
    res = test_client.get("/api/reports/nonexistent-id/export/docx")
    assert res.status_code == 404
    res_pdf = test_client.get("/api/reports/nonexistent-id/export/pdf")
    assert res_pdf.status_code == 404

# ================= 6. DECOUPLED AUDIO WORKFLOW TESTS =================

def test_31_decoupled_audio_workflow(temp_db, test_client):
    """
    Verifies that uploading audio updates original_transcript and edited_transcript,
    but does NOT overwrite or auto-structure findings until explicit structuring action.
    """
    p = PatientService.create_patient({"full_name": "Decouple User", "patient_id": "TP-05", "gender": "MALE"}, db_path=temp_db)
    r = ReportService.create_report({"patient_id": p["id"], "template_id": "usg-abdomen-pelvis-male"}, db_path=temp_db)
    
    # Pre-structure or manual findings
    initial_findings = {
        "sections": [{"key": "liver", "label": "Liver", "is_present": True, "text": "Preserved manual note."}],
        "impression": None
    }
    ReportService.update_report(r["id"], {"structured_findings": initial_findings}, db_path=temp_db)
    
    # Audio upload endpoint decouples transcription from structuring
    audio_wav = os.path.abspath("tests/fixtures/test_a_basic.wav")
    assert os.path.exists(audio_wav)
    
    with open(audio_wav, "rb") as f:
        res = test_client.post(
            f"/api/reports/{r['id']}/audio",
            files={"file": ("test.wav", f, "audio/wav")},
            data={"model_name": "small.en"}
        )
    assert res.status_code == 200
    data = res.json()
    
    # Transcript updated
    assert "liver is normal" in data["edited_transcript"].lower()
    
    # Findings must NOT have been overwritten by auto-structuring
    fetched = ReportService.get_report(r["id"], db_path=temp_db)
    sections = fetched["structured_findings"]["sections"]
    liver_sec = next(s for s in sections if s["key"] == "liver")
    assert liver_sec["text"] == "Preserved manual note."

# ================= 7. MANDATORY MEASUREMENT CORRECTION & REVISION CYCLE =================

def test_32_mandatory_correction_cycle(temp_db):
    """
    Scenario:
    1. Dictation: 10.2 cm -> Correction: 10.8 cm
    2. Structuring: 10.8 cm active, 10.2 cm superseded
    3. Manual edit: Radiologist edits right kidney to 10.9 cm
    4. Draft export: 10.9 cm present, 10.2 cm absent, draft banner present
    5. Review: Marked REVIEWED by Dr. Radiologist
    6. Reviewed export: Reviewer attestation present, draft banner absent
    7. Edit: Re-edited -> Draft banner reappears
    """
    p = PatientService.create_patient({"full_name": "Vipul Mehta", "patient_id": "VM-901", "gender": "MALE", "age_years": 44}, db_path=temp_db)
    r = ReportService.create_report({"patient_id": p["id"], "template_id": "usg-abdomen-pelvis-male"}, db_path=temp_db)
    
    # 1. Structure dictation with correction
    dictation = "Right kidney measures 10.2 cm, liver is normal in size, correction, right kidney measures 10.8 cm."
    r_struct = ReportService.structure_and_save_report(r["id"], dictation, db_path=temp_db)
    
    rk = next(s for s in r_struct["structured_findings"]["sections"] if s["key"] == "right_kidney")
    assert "10.8" in rk["text"]
    assert "10.2" not in rk["text"]
    
    # 2. Manual edit to 10.9 cm
    for s in r_struct["structured_findings"]["sections"]:
        if s["key"] == "right_kidney":
            s["text"] = "Measures 10.9 cm in length. Normal echogenicity."
    
    r_edited = ReportService.update_report(
        r["id"],
        {"structured_findings": r_struct["structured_findings"]},
        change_type="MANUAL_EDIT",
        db_path=temp_db
    )
    
    # 3. Draft export
    docx_draft = WordExportService.generate_docx(r_edited)
    doc_d = docx.Document(io.BytesIO(docx_draft))
    draft_text = "\n".join(p.text for p in doc_d.paragraphs)
    assert "*** DRAFT — REQUIRES RADIOLOGIST REVIEW ***" in draft_text
    assert "10.9 cm" in draft_text
    assert "10.2 cm" not in draft_text
    
    # 4. Review
    r_reviewed = ReportService.mark_reviewed(r["id"], reviewed_by="Dr. Radiologist", db_path=temp_db)
    assert r_reviewed["status"] == "REVIEWED"
    
    # 5. Reviewed export
    docx_rev = WordExportService.generate_docx(r_reviewed)
    doc_r = docx.Document(io.BytesIO(docx_rev))
    rev_text = "\n".join(p.text for p in doc_r.paragraphs)
    assert "*** DRAFT" not in rev_text
    assert "Reviewed and clinically verified by: Dr. Radiologist" in rev_text
    assert "10.9 cm" in rev_text
    
    # 6. Revert / Edit back to draft
    r_revert = ReportService.revert_to_draft(r["id"], db_path=temp_db)
    assert r_revert["status"] == "DRAFT"
    
    docx_revert = WordExportService.generate_docx(r_revert)
    doc_rv = docx.Document(io.BytesIO(docx_revert))
    rv_text = "\n".join(p.text for p in doc_rv.paragraphs)
    assert "*** DRAFT — REQUIRES RADIOLOGIST REVIEW ***" in rv_text

# ================= 8. CORNER CASES & EDGE TESTS =================

def test_33_empty_findings_export_safe(sample_male_report_data):
    sample_male_report_data["structured_findings"] = {"sections": [], "impression": None}
    b = WordExportService.generate_docx(sample_male_report_data)
    assert len(b) > 5000
    pdf_b = PDFExportService.generate_pdf(sample_male_report_data)
    assert pdf_b.startswith(b"%PDF-")

def test_34_missing_patient_snapshot_defaults_safely(sample_male_report_data):
    sample_male_report_data["patient_snapshot"] = None
    b = WordExportService.generate_docx(sample_male_report_data)
    doc = docx.Document(io.BytesIO(b))
    assert len(doc.paragraphs) > 0

def test_35_long_clinical_findings_pagination_safe(sample_male_report_data):
    long_desc = "Normal in size. " * 80
    sample_male_report_data["structured_findings"]["sections"] = [
        {"key": "liver", "label": "Liver", "is_present": True, "text": long_desc}
    ]
    b = WordExportService.generate_docx(sample_male_report_data)
    doc = docx.Document(io.BytesIO(b))
    assert any("Normal in size." in p.text for p in doc.paragraphs)
    pdf_b = PDFExportService.generate_pdf(sample_male_report_data)
    assert len(pdf_b) > 20000

def test_36_special_characters_in_patient_and_findings(sample_male_report_data):
    sample_male_report_data["patient_snapshot"]["full_name"] = "O'Connor & Sons <Test> 'Clinical'"
    sample_male_report_data["structured_findings"]["sections"] = [
        {"key": "liver", "label": "Liver", "is_present": True, "text": "Findings with & < > ' \" characters."}
    ]
    html_content = PreviewService.render_html(sample_male_report_data)
    assert "&amp;" in html_content or "&lt;" in html_content
    pdf_b = PDFExportService.generate_pdf(sample_male_report_data)
    assert pdf_b.startswith(b"%PDF-")

def test_37_female_report_without_impression(sample_female_report_data):
    sample_female_report_data["structured_findings"]["impression"] = None
    b = WordExportService.generate_docx(sample_female_report_data)
    doc = docx.Document(io.BytesIO(b))
    all_text = "\n".join(p.text for p in doc.paragraphs)
    assert "IMPRESSION:" in all_text
    assert "No significant abnormality detected." not in all_text

def test_38_duplicate_organ_heading_stripping(sample_male_report_data):
    # If text already starts with "Liver: "
    sample_male_report_data["structured_findings"]["sections"] = [
        {"key": "liver", "label": "Liver", "is_present": True, "text": "Liver: Normal in size."}
    ]
    b = WordExportService.generate_docx(sample_male_report_data)
    doc = docx.Document(io.BytesIO(b))
    liver_p = next(p for p in doc.paragraphs if "Liver:" in p.text)
    # Ensure "Liver: Liver:" does not occur
    assert "Liver: Liver:" not in liver_p.text

def test_39_multiple_sequential_exports_same_session(sample_male_report_data):
    for _ in range(3):
        b1 = WordExportService.generate_docx(sample_male_report_data)
        assert len(b1) > 5000

def test_40_post_export_reference_template_integrity_final_check():
    for fn, expected_h in BASELINE_HASHES.items():
        with open(fn, "rb") as f:
            curr_h = hashlib.sha256(f.read()).hexdigest().upper()
        assert curr_h == expected_h
