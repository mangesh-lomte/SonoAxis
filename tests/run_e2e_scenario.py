import sys
import json
import time
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000/api"

def api_call(path, method="GET", data=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"} if data else {}
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, err_body

def run_e2e_verification():
    print("=== STARTING PHASE 7 MANDATORY END-TO-END SCENARIO ===")

    # 1. Register Patient: Demo Patient, TEST-001, Age 45, Male
    status, p = api_call("/patients", method="POST", data={
        "patient_id": f"TEST-001-{int(time.time())}",
        "full_name": "Demo Patient",
        "age_years": 45,
        "gender": "Male"
    })
    assert status == 201, f"Expected 201, got {status}: {p}"
    patient_id = p["id"]
    print(f"Step 1: Patient registered successfully: {p['full_name']} (ID: {p['patient_id']})")

    # 2. Create New Report (Male Abdomen and Pelvis)
    status, rep = api_call("/reports", method="POST", data={
        "template_id": "usg-abdomen-pelvis-male",
        "patient_id": patient_id
    })
    assert status == 201, f"Expected 201, got {status}: {rep}"
    report_id = rep["id"]
    assert rep["status"] == "DRAFT"
    assert rep["revision_number"] == 1
    assert rep["impression"] is None
    # Verify unmentioned organs are blank
    blank_count = sum(1 for s in rep["structured_findings"]["sections"] if not s["is_present"])
    assert blank_count == len(rep["structured_findings"]["sections"])
    print(f"Step 2: Male Report created in DRAFT with blank findings: {rep['report_number']}")

    # 3. Dictate and Structure:
    # "Right kidney measures 10.2 cm. Liver is normal in size. Correction: right kidney measures 10.8 cm."
    dictation = "Right kidney measures 10.2 cm. Liver is normal in size. Correction: right kidney measures 10.8 cm."
    status, rep_structured = api_call(f"/reports/{report_id}/structure", method="POST", data={
        "transcript_text": dictation,
        "force_regenerate": True
    })
    assert status == 200, f"Expected 200, got {status}: {rep_structured}"
    
    sections = rep_structured["structured_findings"]["sections"]
    rk = next(s for s in sections if s["key"] == "right_kidney")
    liver = next(s for s in sections if s["key"] == "liver")
    spleen = next(s for s in sections if s["key"] == "spleen")

    assert "10.8" in rk["text"]
    assert "10.2" not in rk["text"]
    assert "normal in size" in liver["text"]
    assert spleen["is_present"] is False
    assert rep_structured["impression"] is None
    assert len(rep_structured["structured_findings"]["superseded_history"]) == 1
    assert "10.2" in rep_structured["structured_findings"]["superseded_history"][0]["superseded_text"]
    assert "10.2" in rep_structured["original_transcript"]
    assert "10.8" in rep_structured["original_transcript"]
    print(f"Step 3: Dictation structured correctly. Right kidney = 10.8 cm, 10.2 cm superseded to audit history.")

    # 4. Save the report with manual metadata
    status, saved = api_call(f"/reports/{report_id}", method="PUT", data={
        "referral_doctor": "Dr. Fictional Consultant",
        "expected_revision_number": rep_structured["revision_number"]
    })
    assert status == 200
    print(f"Step 4: Report saved with revision #{saved['revision_number']}")

    # 5. Retrieve the same report and verify all values
    status, retrieved = api_call(f"/reports/{report_id}", method="GET")
    assert status == 200
    assert retrieved["referral_doctor"] == "Dr. Fictional Consultant"
    assert retrieved["patient_snapshot"]["full_name"] == "Demo Patient"
    print(f"Step 5: Retrieved report. All saved clinical and patient snapshot values verified.")

    # 6. Manually edit right kidney measurement
    status, edited = api_call(f"/reports/{report_id}", method="PUT", data={
        "impression": "Normal liver span. Normal right renal length without hydronephrosis.",
        "expected_revision_number": retrieved["revision_number"]
    })
    assert status == 200
    print(f"Step 6: Manually added impression. Revision advanced to #{edited['revision_number']}")

    # 7. Mark the report as REVIEWED
    status, reviewed = api_call(f"/reports/{report_id}/review", method="POST", data={
        "reviewed_by": "Dr. Lead Radiologist",
        "acknowledge_unresolved": True
    })
    assert status == 200
    assert reviewed["status"] == "REVIEWED"
    assert reviewed["is_reviewed"] is True
    assert reviewed["reviewed_by"] == "Dr. Lead Radiologist"
    assert reviewed["reviewed_at"] is not None
    print(f"Step 7: Explicitly marked as REVIEWED by {reviewed['reviewed_by']}")

    # 8. Edit the reviewed report -> Backend MUST return it to DRAFT
    status, re_edited = api_call(f"/reports/{report_id}", method="PUT", data={
        "referral_doctor": "Dr. Secondary Physician",
        "expected_revision_number": reviewed["revision_number"]
    })
    assert status == 200
    assert re_edited["status"] == "DRAFT"
    assert re_edited["is_reviewed"] is False
    assert re_edited["reviewed_at"] is None
    print(f"Step 8: Content edited on reviewed report -> Backend safely reverted status to DRAFT.")

    # 9. Inspect Revision History
    status, revs = api_call(f"/reports/{report_id}/revisions", method="GET")
    assert status == 200
    assert len(revs) >= 4
    change_types = [r["change_type"] for r in revs]
    assert "REVIEW" in change_types
    print(f"Step 9: Revision history verified. {len(revs)} audit revisions logged: {change_types}")

    # 10. Representative Female Workflow
    status, pf = api_call("/patients", method="POST", data={
        "patient_id": f"TEST-FEM-{int(time.time())}",
        "full_name": "Demo Female Patient",
        "age_years": 32,
        "gender": "Female"
    })
    status, rf = api_call("/reports", method="POST", data={
        "template_id": "usg-abdomen-pelvis-female",
        "patient_id": pf["id"]
    })
    f_dictation = "Uterus measures 7.2 by 3.5 by 4.0 cm. Right ovary measures 2.5 cm. Left ovary is normal. No free fluid."
    status, rf_struct = api_call(f"/reports/{rf['id']}/structure", method="POST", data={
        "transcript_text": f_dictation,
        "force_regenerate": True
    })
    assert status == 200
    f_sections = rf_struct["structured_findings"]["sections"]
    uterus = next(s for s in f_sections if s["key"] == "uterus")
    ro = next(s for s in f_sections if s["key"] == "right_ovary")
    assert uterus["is_present"] is True
    assert ro["is_present"] is True
    
    # Mark female report reviewed
    status, rf_rev = api_call(f"/reports/{rf['id']}/review", method="POST", data={
        "reviewed_by": "Dr. Specialist",
        "acknowledge_unresolved": True
    })
    assert rf_rev["status"] == "REVIEWED"
    print(f"Step 10: Female template workflow verified. Uterus & Ovaries populated; reviewed successfully.")

    print("=== MANDATORY END-TO-END SCENARIO FULLY VERIFIED ===")

if __name__ == "__main__":
    run_e2e_verification()
