import io
import time
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.structuring.templates import TEMPLATES_CATALOG
from backend.app.services.patient_service import PatientService


@pytest.fixture(scope="module")
def shared_test_patient():
    p = PatientService.create_patient({
        "patient_id": f"PT-ALL16-{int(time.time())}",
        "full_name": "Suresh K. Verma",
        "gender": "Male",
        "age_years": 52,
        "contact_number": "+91 98765 43210",
        "referral_doctor": "Dr. V. K. Gupta, MS"
    })
    return p

def test_verify_all_16_templates_catalog_complete():
    """Verify that all 16 expected templates exist in TEMPLATES_CATALOG."""
    assert len(TEMPLATES_CATALOG) == 16, f"Expected 16 templates, found {len(TEMPLATES_CATALOG)}"

@pytest.mark.parametrize("template_id", list(TEMPLATES_CATALOG.keys()))
def test_all_16_templates_lifecycle(template_id, shared_test_patient, client):
    """
    For each of the 16 original clinical templates:
    1. Initialize a new clinical report.
    2. Verify blank initial state (unmentioned organs are blank, undictated impression is None).
    3. Update findings and save.
    4. Reopen and verify data persistence.
    5. Verify Word (DOCX) export.
    6. Verify HTML preview and draft banner.
    """
    t_def = TEMPLATES_CATALOG[template_id]
    
    # 1. Create Report
    rep_res = client.post("/api/reports", json={
        "template_id": template_id,
        "patient_id": shared_test_patient["id"],
        "referral_doctor": "Dr. V. K. Gupta, MS"
    })
    assert rep_res.status_code == 201, f"Failed to create report for {template_id}: {rep_res.text}"
    report_data = rep_res.json()
    report_id = report_data["id"]
    assert report_data["template_id"] == template_id
    assert report_data["status"] == "DRAFT"

    # 2. Verify Blank Initial State
    struct = report_data.get("structured_findings") or {}
    assert report_data.get("impression") is None, f"Initial impression must be None in {template_id}"
    for sec in struct.get("sections", []):
        assert sec.get("is_present") is False, f"Section {sec.get('key')} must be blank initially in {template_id}"

    # 3. Save with a clinical finding
    updated_sections = list(struct.get("sections", []))
    if updated_sections:
        updated_sections[0]["is_present"] = True
        updated_sections[0]["text"] = "Evaluation complete, findings normal within physiological limits."

    save_res = client.put(f"/api/reports/{report_id}", json={
        "structured_findings": {
            **struct,
            "sections": updated_sections,
            "impression": "Normal clinical ultrasound study."
        },
        "impression": "Normal clinical ultrasound study.",
        "expected_revision_number": report_data["revision_number"]
    })
    assert save_res.status_code == 200, f"Failed to save report {report_id}: {save_res.text}"

    # 4. Reopen Report
    get_res = client.get(f"/api/reports/{report_id}")
    assert get_res.status_code == 200
    reopened = get_res.json()
    assert reopened["impression"] == "Normal clinical ultrasound study."
    assert reopened["status"] == "DRAFT"

    # 5. HTML Preview
    prev_res = client.get(f"/api/reports/{report_id}/preview")
    assert prev_res.status_code == 200
    html_text = prev_res.text
    assert len(html_text) > 100
    assert "DRAFT" in html_text or "UNOFFICIAL" in html_text

    # 6. Word (DOCX) Export
    docx_res = client.get(f"/api/reports/{report_id}/export/docx")
    assert docx_res.status_code == 200
    assert len(docx_res.content) > 1000
    assert "wordprocessingml" in docx_res.headers.get("content-type", "")

    # 7. PDF Export & Placeholder Validation
    pdf_res = client.get(f"/api/reports/{report_id}/export/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.content.startswith(b"%PDF-")
    assert len(pdf_res.content) > 5000
    assert "pdf" in pdf_res.headers.get("content-type", "")

    # Ensure no unresolved placeholders appear in HTML export preview
    for forbidden in ["[PSV]", "[INCOMPETENT PERFORATOR]", "[BLANK", "[INSERT"]:
        assert forbidden not in html_text, f"Forbidden placeholder '{forbidden}' found in HTML for {template_id}"
