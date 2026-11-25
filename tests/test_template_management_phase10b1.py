import pytest
import os
import docx

FICTIONAL_TEMPLATE_PATH = r"D:\sovoice\references\fictional_templates\carotid-doppler-test.docx"

def test_template_management_lifecycle_phase10b1(admin_client, client):
    assert os.path.exists(FICTIONAL_TEMPLATE_PATH), "Fictional template docx must exist"

    # 1. Import Template (Administrator)
    with open(FICTIONAL_TEMPLATE_PATH, "rb") as f:
        res = admin_client.post(
            "/api/templates/import",
            files={"file": ("carotid-doppler-test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
    assert res.status_code in [200, 201]
    data = res.json()
    tmpl_id = data["id"]
    assert data["status"] == "DRAFT_CONFIG"
    assert "carotid" in data["file_name"].lower()

    # 2. Extract Structure (Administrator)
    with open(FICTIONAL_TEMPLATE_PATH, "rb") as f:
        res_struct = admin_client.post(
            "/api/templates/extract-structure",
            files={"file": ("carotid-doppler-test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
    assert res_struct.status_code == 200
    struct_info = res_struct.json()
    assert struct_info["tables_count"] >= 1
    assert any("[PSV]" in p for p in struct_info["detected_placeholders"])

    # 3. Configure Template (Administrator)
    config_payload = {
        "name": "Bilateral Carotid and Vertebral Doppler (Pytest Dynamic)",
        "category": "arterial_doppler",
        "laterality": "bilateral",
        "table_type": "five_col_bilateral",
        "sections": [
            {"order": 1, "key": "cca", "label": "Common Carotid Artery (CCA)", "heading": "Common Carotid Artery (CCA): "},
            {"order": 2, "key": "ica", "label": "Internal Carotid Artery (ICA)", "heading": "Internal Carotid Artery (ICA): "},
            {"order": 3, "key": "eca", "label": "External Carotid Artery (ECA)", "heading": "External Carotid Artery (ECA): "},
            {"order": 4, "key": "vertebral", "label": "Vertebral Artery", "heading": "Vertebral Artery: "},
            {"order": 5, "key": "impression", "label": "Impression", "heading": "IMPRESSION: "}
        ]
    }
    res_cfg = admin_client.put(f"/api/templates/{tmpl_id}", json=config_payload)
    assert res_cfg.status_code == 200
    cfg_data = res_cfg.json()
    assert cfg_data["table_type"] == "five_col_bilateral"
    assert len(cfg_data["sections"]) == 5

    # 4. Approve Template (Administrator)
    res_app = admin_client.post(f"/api/templates/{tmpl_id}/approve", json={"approved_by": "Pytest Administrator"})
    assert res_app.status_code == 200
    assert res_app.json()["status"] == "APPROVED"
    assert res_app.json()["approved_by"] == "Pytest Administrator"

    # 5. Create Report with Approved Fictional Template (Radiologist)
    res_rep = client.post("/api/reports", json={
        "template_id": tmpl_id,
        "referral_doctor": "Dr. Pytest Neurologist"
    })
    assert res_rep.status_code in [200, 201]
    rep_id = res_rep.json()["id"]

    # 6. Structure Findings (Radiologist)
    res_st = client.post(f"/api/reports/{rep_id}/structure", json={
        "transcript_text": "Internal carotid artery PSV on right is 75 cm per second and on left is 78 cm per second. Impression: Normal bilateral carotid Doppler study.",
        "auto_save": True
    })
    assert res_st.status_code == 200
    st_data = res_st.json()
    assert "normal bilateral carotid" in (st_data.get("impression") or "").lower()

    # 7. Review and Sign-Off (Radiologist)
    res_rev = client.post(f"/api/reports/{rep_id}/review", json={
        "reviewed_by": "Dr. Pytest Radiologist",
        "acknowledge_unresolved": True
    })
    assert res_rev.status_code == 200
    assert res_rev.json()["status"] == "REVIEWED"

    # 8. Export to Word (DOCX) and Verify Zero Forbidden Placeholders
    res_docx = client.get(f"/api/reports/{rep_id}/export/docx")
    assert res_docx.status_code == 200
    assert len(res_docx.content) > 1000

    out_docx_path = os.path.join(r"D:\sovoice\references\fictional_templates", "pytest_carotid_export.docx")
    with open(out_docx_path, "wb") as f:
        f.write(res_docx.content)

    doc_obj = docx.Document(out_docx_path)
    full_text = " ".join(p.text for p in doc_obj.paragraphs)
    for t in doc_obj.tables:
        for r in t.rows:
            for c in r.cells:
                full_text += " " + c.text

    forbidden = ["[PSV]", "[INCOMPETENT PERFORATOR]", "[BLANK - CLINICAL IMPRESSION TO BE DICTATED]"]
    for fb in forbidden:
        assert fb not in full_text, f"Forbidden token '{fb}' leaked into exported document!"

    # 9. Test Versioning (Administrator)
    res_ver = admin_client.post(f"/api/templates/{tmpl_id}/version", json={"comment": "Version 2 revision"})
    assert res_ver.status_code == 200
    v2_data = res_ver.json()
    assert v2_data["version"] == 2
    assert v2_data["status"] == "DRAFT_CONFIG"

    # 10. Test Archiving (Administrator)
    res_arc = admin_client.post(f"/api/templates/{tmpl_id}/archive")
    assert res_arc.status_code == 200
    assert res_arc.json()["status"] == "ARCHIVED"
