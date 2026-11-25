import os
import sys
import time
import docx
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.schema import init_db
from backend.app.services.report_service import ReportService
from backend.app.services.patient_service import PatientService
from backend.app.export.word_service import WordExportService
from backend.app.export.pdf_service import PDFExportService


def test_full_e2e_male_workflow(client):
    """
    Executes the mandatory 18-step clinical workflow for Male Abdomen & Pelvis.
    """
    # 1. Open Dashboard & check metrics
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    initial_stats = res.json()
    assert "total_reports" in initial_stats

    # 2. Register a fictional patient: Ramesh Chandra, 54 yrs, Male
    pat_res = client.post("/api/patients", json={
        "patient_id": f"PT-E2E-{int(time.time())}",
        "full_name": "Ramesh Chandra",
        "gender": "Male",
        "age_years": 54,
        "referral_doctor": "Dr. A. K. Sharma, MD"
    })
    assert pat_res.status_code == 201
    patient = pat_res.json()
    patient_id = patient["id"]

    # 3. Create a Male Report
    rep_res = client.post("/api/reports", json={
        "template_id": "usg-abdomen-pelvis-male",
        "patient_id": patient_id,
        "referral_doctor": "Dr. A. K. Sharma, MD"
    })
    assert rep_res.status_code == 201
    rep = rep_res.json()
    report_id = rep["id"]
    assert rep["status"] == "DRAFT"
    assert rep["revision_number"] == 1
    assert rep["impression"] is None

    # 4 & 5. Upload audio and transcribe locally
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "test_b_correction.wav")
    assert os.path.exists(fixture_path), f"Audio fixture missing: {fixture_path}"
    with open(fixture_path, "rb") as f:
        audio_res = client.post(
            f"/api/reports/{report_id}/audio",
            files={"file": ("test_b_correction.wav", f, "audio/wav")},
            data={"model_name": "small.en"}
        )
    assert audio_res.status_code == 200
    audio_rep = audio_res.json()
    transcript = audio_rep["edited_transcript"]
    assert len(transcript) > 10, "Transcription must not be empty"

    # 6. Inspect and edit transcript if needed
    edited_transcript = (
        "Right kidney measures 10.2 cm. Liver is normal in size. "
        "Correction: right kidney measures 10.8 cm. Urinary bladder is well distended."
    )
    edit_res = client.put(f"/api/reports/{report_id}", json={
        "edited_transcript": edited_transcript,
        "expected_revision_number": audio_rep["revision_number"]
    })
    assert edit_res.status_code == 200

    # 7. Generate structured findings
    struct_res = client.post(f"/api/reports/{report_id}/structure", json={
        "transcript_text": edited_transcript,
        "force_regenerate": True
    })
    assert struct_res.status_code == 200
    structured = struct_res.json()
    sec_map = {s["key"]: s for s in structured["structured_findings"]["sections"]}

    # 8. Verify explicit corrections
    assert sec_map["right_kidney"]["is_present"] is True
    assert "10.8" in sec_map["right_kidney"]["text"]
    assert "10.2" not in sec_map["right_kidney"]["text"]
    assert sec_map["left_kidney"]["is_present"] is False
    assert sec_map["gall_bladder"]["is_present"] is False
    assert len(structured["structured_findings"]["superseded_history"]) >= 1

    # 9. Manually edit a measurement (e.g. adjust to 10.9 cm)
    sec_map["right_kidney"]["text"] = "Right kidney measures 10.9 cm. Normal cortical thickness."
    updated_sections = list(sec_map.values())
    
    # 10. Save the report
    save_res = client.put(f"/api/reports/{report_id}", json={
        "structured_findings": {
            "template_id": structured["structured_findings"]["template_id"],
            "sections": updated_sections,
            "unassigned_findings": structured["structured_findings"]["unassigned_findings"],
            "superseded_history": structured["structured_findings"]["superseded_history"],
            "impression": None
        },
        "expected_revision_number": structured["revision_number"]
    })
    assert save_res.status_code == 200
    saved = save_res.json()
    assert saved["revision_number"] > structured["revision_number"]

    # 11. Preview report
    prev_res = client.get(f"/api/reports/{report_id}/preview")
    assert prev_res.status_code == 200
    assert "ULTRASOUND ABDOMEN AND PELVIS" in prev_res.text
    assert "DRAFT" in prev_res.text

    # 12. Download Word (.docx)
    docx_res = client.get(f"/api/reports/{report_id}/export/docx")
    assert docx_res.status_code == 200
    assert len(docx_res.content) > 1000

    # 13. Download PDF (.pdf)
    pdf_res = client.get(f"/api/reports/{report_id}/export/pdf")
    assert pdf_res.status_code == 200
    assert len(pdf_res.content) > 5000

    # 14. Mark report as reviewed
    review_res = client.post(f"/api/reports/{report_id}/review", json={
        "reviewed_by": "Dr. Aarav Sharma",
        "acknowledge_unresolved": True
    })
    assert review_res.status_code == 200
    reviewed = review_res.json()
    assert reviewed["status"] == "REVIEWED"
    assert reviewed["is_reviewed"] is True

    # 15. Edit report again
    re_edit_res = client.put(f"/api/reports/{report_id}", json={
        "referral_doctor": "Dr. A. K. Sharma, MD (Verified)",
        "expected_revision_number": reviewed["revision_number"]
    })
    assert re_edit_res.status_code == 200
    re_edited = re_edit_res.json()

    # 16. Verify draft status is restored
    assert re_edited["status"] == "DRAFT"
    assert re_edited["is_reviewed"] is False

    # 17. Reopen from report registry
    list_res = client.get("/api/reports")
    assert list_res.status_code == 200
    reports_list = list_res.json()
    found = next((r for r in reports_list if r["id"] == report_id), None)
    assert found is not None
    assert found["status"] == "DRAFT"

    # 18. Confirm report persistence
    persisted_res = client.get(f"/api/reports/{report_id}")
    assert persisted_res.status_code == 200
    assert persisted_res.json()["id"] == report_id

def test_full_e2e_female_workflow(client):
    """
    Executes the clinical workflow for Female Abdomen & Pelvis.
    """
    # Register Female Patient
    pat_res = client.post("/api/patients", json={
        "patient_id": f"PT-FEM-{int(time.time())}",
        "full_name": "Pooja Sharma",
        "gender": "Female",
        "age_years": 32,
        "referral_doctor": "Dr. S. Mehta, MD"
    })
    patient = pat_res.json()

    # Create Female Report
    rep_res = client.post("/api/reports", json={
        "template_id": "usg-abdomen-pelvis-female",
        "patient_id": patient["id"],
        "referral_doctor": "Dr. S. Mehta, MD"
    })
    rep = rep_res.json()
    report_id = rep["id"]

    # Structure Female Findings
    f_dictation = (
        "Uterus measures 7.2 by 3.5 by 4.1 cm. Endometrium measures 6 mm. "
        "Right ovary shows a simple cyst measuring 2.4 cm. Left ovary is normal. No free fluid."
    )
    struct_res = client.post(f"/api/reports/{report_id}/structure", json={
        "transcript_text": f_dictation,
        "force_regenerate": True
    })
    assert struct_res.status_code == 200
    findings = struct_res.json()["structured_findings"]
    f_sections = {s["key"]: s for s in findings["sections"]}

    # Verify pelvic organs and prostate suppression
    assert "prostate" not in f_sections, "Prostate must never appear in female template"
    assert f_sections["uterus"]["is_present"] is True
    assert "7.2" in f_sections["uterus"]["text"]
    assert f_sections["endometrium"]["is_present"] is True
    assert "6" in f_sections["endometrium"]["text"]
    assert f_sections["right_ovary"]["is_present"] is True
    assert "2.4" in f_sections["right_ovary"]["text"]
    assert f_sections["left_ovary"]["is_present"] is True
    assert "normal" in f_sections["left_ovary"]["text"].lower()
    assert f_sections["peritoneal_cavity"]["is_present"] is True
    assert "no free fluid" in f_sections["peritoneal_cavity"]["text"].lower()
    assert f_sections["liver"]["is_present"] is False
    assert struct_res.json()["impression"] is None

    # Review sign-off
    rev_res = client.post(f"/api/reports/{report_id}/review", json={
        "reviewed_by": "Dr. Aarav Sharma",
        "acknowledge_unresolved": True
    })
    assert rev_res.status_code == 200
    assert rev_res.json()["status"] == "REVIEWED"
