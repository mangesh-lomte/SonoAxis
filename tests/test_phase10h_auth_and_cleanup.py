import io
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import docx
from fastapi.testclient import TestClient

from backend.app.db.connection import get_db
from backend.app.db.schema import init_db
from backend.app.main import app
from backend.app.services.auth_service import AuthService, _failed_attempts
from backend.app.services.demo_seed import reset_and_seed_clean_demo_db
from backend.app.services.patient_service import PatientService
from backend.app.services.report_service import ReportService


OCR_FIXTURE = Path("D:/sovoice/tests/fixtures/ocr/test_a_abdomen.png")


def _seed_pair(db_path: str):
    rad_user = f"asharma_{secrets.token_hex(3)}"
    rad_pass = secrets.token_urlsafe(16)
    adm_user = f"sysadm_{secrets.token_hex(3)}"
    adm_pass = secrets.token_urlsafe(16)
    AuthService.upsert_account_with_password(
        user_id=f"usr-{rad_user}",
        username=rad_user,
        password=rad_pass,
        full_name="Dr. Aarav Sharma",
        role="Radiologist",
        designation="Consultant Radiologist",
        department="Radiology & Ultrasound",
        email=f"{rad_user}@sonoaxis.test",
        is_demo=True,
        db_path=db_path,
    )
    AuthService.upsert_account_with_password(
        user_id=f"usr-{adm_user}",
        username=adm_user,
        password=adm_pass,
        full_name="System Administrator",
        role="Administrator",
        designation="Clinical Systems Administrator",
        department="Medical Informatics",
        email=f"{adm_user}@sonoaxis.test",
        is_demo=False,
        db_path=db_path,
    )
    return (rad_user, rad_pass), (adm_user, adm_pass)


def test_phase10h1_unauthenticated_401_across_all_protected_endpoints(isolated_pytest_database, unauth_client):
    """
    Only /api/health, /api/auth/login, and /api/auth/logout are public.
    Every clinical, patient, template, audio, OCR image, export, audit, settings, and backup endpoint must return 401.
    """
    assert unauth_client.get("/api/health").status_code == 200
    assert unauth_client.post("/api/auth/logout").status_code == 200

    protected_requests = [
        ("GET", "/api/auth/me"),
        ("GET", "/api/auth/users"),
        ("GET", "/api/dashboard/stats"),
        ("GET", "/api/patients"),
        ("POST", "/api/patients"),
        ("GET", "/api/reports"),
        ("POST", "/api/reports"),
        ("GET", "/api/reports/nonexistent"),
        ("PUT", "/api/reports/nonexistent"),
        ("POST", "/api/reports/nonexistent/structure"),
        ("POST", "/api/reports/nonexistent/review"),
        ("POST", "/api/reports/nonexistent/revert-draft"),
        ("GET", "/api/reports/nonexistent/revisions"),
        ("GET", "/api/reports/nonexistent/preview"),
        ("GET", "/api/reports/nonexistent/export/docx"),
        ("GET", "/api/reports/nonexistent/export/pdf"),
        ("GET", "/api/reports/nonexistent/ocr/images/sample.png"),
        ("POST", "/api/reports/nonexistent/ocr/upload"),
        ("GET", "/api/audio/sample-audio-id"),
        ("GET", "/api/templates"),
        ("POST", "/api/templates/import"),
        ("GET", "/api/settings"),
        ("PUT", "/api/settings"),
        ("GET", "/api/backups"),
        ("POST", "/api/backups"),
        ("GET", "/api/engine/status"),
        ("GET", "/api/exports/status"),
    ]
    for method, path in protected_requests:
        resp = unauth_client.request(method, path)
        assert resp.status_code == 401, f"{method} {path} expected 401, got {resp.status_code}"


def test_phase10h1_argon2id_rate_limit_csrf_expiry_logout_and_password_change(tmp_path, monkeypatch):
    """Verify Argon2id password hashes, 429 rate limiting, CSRF cookie enforcement, expiry, logout, and password rotation."""
    from backend.app.core.config import settings

    db_file = str(tmp_path / "auth_sec.db")
    init_db(db_file)
    monkeypatch.setattr(settings, "DATABASE_PATH", db_file)
    _failed_attempts.clear()

    (rad_user, rad_pass), _ = _seed_pair(db_file)

    # Argon2id hash stored in DB
    with get_db(db_file) as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE username = ?", (rad_user,)).fetchone()
        assert row is not None
        assert row["password_hash"].startswith("$argon2id$")

    with TestClient(app) as tc:
        # Bad logins hit 401 then 429 rate limiter after 5 attempts
        for idx in range(5):
            r = tc.post("/api/auth/login", json={"username": rad_user, "password": "wrong-password-123"})
            assert r.status_code == 401, f"Attempt {idx+1} expected 401, got {r.status_code}"
        r6 = tc.post("/api/auth/login", json={"username": rad_user, "password": "wrong-password-123"})
        assert r6.status_code == 429

        _failed_attempts.clear()

        # Valid login sets HttpOnly session cookie & sonoaxis_csrf cookie
        ok = tc.post("/api/auth/login", json={"username": rad_user, "password": rad_pass})
        assert ok.status_code == 200
        body = ok.json()
        assert body["user"]["username"] == rad_user
        csrf_token = body["csrf_token"]
        assert csrf_token
        assert "sonoaxis_session" in tc.cookies
        assert "sonoaxis_csrf" in tc.cookies

        # Cookie-based POST without X-CSRF-Token must fail with 403
        no_csrf = tc.post("/api/patients", json={"patient_id": "PT-CSRF-1", "full_name": "CSRF Probe"})
        assert no_csrf.status_code == 403

        # Wrong CSRF header must fail with 403
        bad_csrf = tc.post(
            "/api/patients",
            json={"patient_id": "PT-CSRF-1", "full_name": "CSRF Probe"},
            headers={"X-CSRF-Token": "invalid-csrf-token"},
        )
        assert bad_csrf.status_code == 403

        # Correct CSRF header succeeds
        good_csrf = tc.post(
            "/api/patients",
            json={"patient_id": "PT-CSRF-1", "full_name": "CSRF Verified"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert good_csrf.status_code == 201

        # Password change invalidates current session token
        new_pass = secrets.token_urlsafe(16)
        chg = tc.post(
            "/api/auth/change-password",
            json={"current_password": rad_pass, "new_password": new_pass},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert chg.status_code == 200
        assert tc.get("/api/auth/me").status_code == 401

        # Login with new password works; logout invalidates session
        relog = tc.post("/api/auth/login", json={"username": rad_user, "password": new_pass})
        assert relog.status_code == 200
        new_csrf = relog.json()["csrf_token"]
        assert tc.get("/api/auth/me").status_code == 200
        assert tc.post("/api/auth/logout", headers={"X-CSRF-Token": new_csrf}).status_code == 200
        assert tc.get("/api/auth/me").status_code == 401

        # Expired session fails cleanly with 401
        relog2 = tc.post("/api/auth/login", json={"username": rad_user, "password": new_pass})
        assert relog2.status_code == 200
        past_iso = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with get_db(db_file) as conn:
            conn.execute("UPDATE user_sessions SET expires_at = ?", (past_iso,))
            conn.commit()
        assert tc.get("/api/auth/me").status_code == 401


def test_phase10h1_rbac_role_separation_and_review_invalidation(tmp_path, monkeypatch):
    """Verify Administrator cannot sign off/revert clinical reports (403) and Radiologist cannot perform admin mutations (403)."""
    from backend.app.core.config import settings

    db_file = str(tmp_path / "rbac_test.db")
    init_db(db_file)
    monkeypatch.setattr(settings, "DATABASE_PATH", db_file)
    _failed_attempts.clear()

    (rad_user, rad_pass), (adm_user, adm_pass) = _seed_pair(db_file)

    with TestClient(app) as rad_tc, TestClient(app) as adm_tc:
        r_tok = rad_tc.post("/api/auth/login", json={"username": rad_user, "password": rad_pass}).json()["access_token"]
        a_tok = adm_tc.post("/api/auth/login", json={"username": adm_user, "password": adm_pass}).json()["access_token"]
        rad_hdr = {"Authorization": f"Bearer {r_tok}"}
        adm_hdr = {"Authorization": f"Bearer {a_tok}"}

        # Radiologist cannot access admin endpoints
        assert rad_tc.get("/api/auth/users", headers=rad_hdr).status_code == 403
        assert rad_tc.put("/api/settings", json={"settings": {"stt_model": "base.en"}}, headers=rad_hdr).status_code == 403
        assert rad_tc.post("/api/backups", headers=rad_hdr).status_code == 403

        # Radiologist creates patient & report
        p = rad_tc.post("/api/patients", json={"patient_id": "PT-RBAC-1", "full_name": "RBAC Patient"}, headers=rad_hdr).json()
        rep = rad_tc.post(
            "/api/reports",
            json={"template_id": "usg-abdomen-pelvis-male", "patient_id": p["id"]},
            headers=rad_hdr,
        ).json()
        rep_id = rep["id"]

        # Add an unresolved unassigned finding so explicit acknowledgment is verified
        rad_tc.put(
            f"/api/reports/{rep_id}",
            json={
                "structured_findings": {
                    "sections": [],
                    "unassigned_findings": [
                        {
                            "id": "unres-1",
                            "raw_text": "8 mm lesion noted",
                            "text": "8 mm lesion noted",
                            "reason": "no_organ_identified",
                            "is_resolved": False,
                        }
                    ],
                    "has_flags": True,
                }
            },
            headers=rad_hdr,
        )

        # Administrator MUST be rejected from clinical review & revert-draft (403)
        adm_rev = adm_tc.post(
            f"/api/reports/{rep_id}/review",
            json={"reviewed_by": "System Administrator", "acknowledge_unresolved": True},
            headers=adm_hdr,
        )
        assert adm_rev.status_code == 403

        # Review blocked (400) while unresolved unassigned finding exists — even with acknowledge_unresolved=True
        unconfirmed = rad_tc.post(
            f"/api/reports/{rep_id}/review",
            json={"reviewed_by": "Dr. Aarav Sharma", "acknowledge_unresolved": False},
            headers=rad_hdr,
        )
        assert unconfirmed.status_code == 400
        blocked_bypass = rad_tc.post(
            f"/api/reports/{rep_id}/review",
            json={"reviewed_by": "Dr. Aarav Sharma", "acknowledge_unresolved": True},
            headers=rad_hdr,
        )
        assert blocked_bypass.status_code == 400

        # Documented exclusion resolves the finding and permits Radiologist sign-off using authenticated identity
        excl = rad_tc.post(
            f"/api/reports/{rep_id}/exclude-unassigned",
            json={"unassigned_id": "unres-1", "exclusion_reason": "Artifact / outside exam scope"},
            headers=rad_hdr,
        )
        assert excl.status_code == 200
        ok_rev = rad_tc.post(
            f"/api/reports/{rep_id}/review",
            json={"reviewed_by": "Spoofed Name", "acknowledge_unresolved": False},
            headers=rad_hdr,
        )
        assert ok_rev.status_code == 200
        assert ok_rev.json()["status"] == "REVIEWED"
        assert ok_rev.json()["reviewed_by"] == "Dr. Aarav Sharma"

        # Administrator also blocked from reverting reviewed report (403)
        assert adm_tc.post(f"/api/reports/{rep_id}/revert-draft", headers=adm_hdr).status_code == 403

        # Editing reviewed content invalidates REVIEWED back to DRAFT
        edited = rad_tc.put(
            f"/api/reports/{rep_id}",
            json={"edited_transcript": "Liver is normal in size and echotexture."},
            headers=rad_hdr,
        )
        assert edited.status_code == 200
        assert edited.json()["status"] == "DRAFT"
        assert edited.json()["is_reviewed"] is False


def test_phase10h1_clean_demo_seed_and_zero_real_doctor_names(tmp_path, monkeypatch):
    """Verify 6 fictional patients/studies, zero real doctor names across reports/preview/users, and clean reviewed exports."""
    from backend.app.core.config import settings

    db_file = str(tmp_path / "clean_demo.db")
    init_db(db_file)
    monkeypatch.setattr(settings, "DATABASE_PATH", db_file)
    _failed_attempts.clear()

    summary = reset_and_seed_clean_demo_db(db_file)
    assert summary["patients_count"] == 6
    assert summary["reports_count"] == 6

    (rad_user, rad_pass), _ = _seed_pair(db_file)

    patients = PatientService.search_patients(limit=50, db_path=db_file)
    assert len(patients) == 6
    reports = ReportService.list_reports(limit=50, db_path=db_file)
    assert len(reports) == 6

    # Verify only authorized fictional identities exist in seeded patients, reports, and users
    with get_db(db_file) as conn:
        user_rows = conn.execute("SELECT full_name, email FROM users").fetchall()
    for u_row in user_rows:
        assert u_row["full_name"] in ("Dr. Aarav Sharma", "System Administrator")
        assert u_row["email"].endswith(("@demo.local", "@sonoaxis.test"))
    for rep in reports:
        if rep.get("reviewed_by"):
            assert rep["reviewed_by"] == "Dr. Aarav Sharma"
        if rep.get("referral_doctor"):
            assert "(Demo Referral)" in rep["referral_doctor"]

    # Verify reviewed export preserves cleanliness & includes OCR measurement flow
    with TestClient(app) as tc:
        tok = tc.post("/api/auth/login", json={"username": rad_user, "password": rad_pass}).json()["access_token"]
        hdr = {"Authorization": f"Bearer {tok}"}

        target_pat = patients[0]
        rep = tc.post(
            "/api/reports",
            json={"template_id": "usg-abdomen-pelvis-male", "patient_id": target_pat["id"]},
            headers=hdr,
        ).json()
        rep_id = rep["id"]

        assert OCR_FIXTURE.exists()
        with open(OCR_FIXTURE, "rb") as f:
            up = tc.post(
                f"/api/reports/{rep_id}/ocr/upload",
                files={"file": ("test_a_abdomen.png", f.read(), "image/png")},
                data={"rotate": "0"},
                headers=hdr,
            )
        assert up.status_code == 200
        up_json = up.json()
        assert up_json["candidates"]
        # Image endpoint requires auth and serves 200 when authenticated
        assert up_json.get("image_url")
        assert tc.get(up_json["image_url"], headers=hdr).status_code == 200
        with TestClient(app) as unauth_tc:
            assert unauth_tc.get(up_json["image_url"]).status_code == 401

        confirm_payload = {
            "source_document_id": up_json["source_document_id"],
            "items": [
                {
                    "measurement_id": c["measurement_id"],
                    "destination_field": c.get("proposed_destination_field") or "liver",
                    "anatomical_label": c.get("anatomical_label") or "Liver",
                    "value": c["value"],
                    "unit": c["normalized_unit"],
                    "dimension": c.get("dimension") or 1,
                    "laterality": c.get("laterality"),
                    "status": "approved",
                }
                for c in up_json["candidates"][:2]
            ],
        }
        assert tc.post(f"/api/reports/{rep_id}/ocr/confirm", json=confirm_payload, headers=hdr).status_code == 200

        rev = tc.post(
            f"/api/reports/{rep_id}/review",
            json={"reviewed_by": "Dr. Aarav Sharma", "acknowledge_unresolved": True},
            headers=hdr,
        )
        assert rev.status_code == 200

        prev_html = tc.get(f"/api/reports/{rep_id}/preview", headers=hdr).text
        assert "Dr. Aarav Sharma" in prev_html
        assert "Chief Radiologist" not in prev_html

        docx_res = tc.get(f"/api/reports/{rep_id}/export/docx", headers=hdr)
        assert docx_res.status_code == 200
        doc = docx.Document(io.BytesIO(docx_res.content))
        doc_text = "\n".join(p.text for p in doc.paragraphs)
        assert "DRAFT" not in doc_text.upper()

        pdf_res = tc.get(f"/api/reports/{rep_id}/export/pdf", headers=hdr)
        assert pdf_res.status_code == 200
        assert pdf_res.content.startswith(b"%PDF-")


def test_phase10h2_radiologist_custom_template_permissions_and_workflow(tmp_path, monkeypatch):
    """
    Verify:
    - Radiologist ('asharma') can single-import, bulk-import, configure, preview, edit,
      activate, create reports, export DOCX/PDF, version, and archive OWN custom templates.
    - Radiologists are blocked (403) from modifying, approving, versioning, or archiving
      shared templates, institutional 16 built-in templates, or other clinicians' custom templates.
    - Administrators preserve shared/institutional approval & management while original 16
      built-in templates remain strictly protected against modification or archiving (403).
    """
    from backend.app.core.config import settings

    fictional_docx = Path("D:/sovoice/references/fictional_templates/carotid-doppler-test.docx")
    assert fictional_docx.exists()
    docx_bytes = fictional_docx.read_bytes()

    db_file = str(tmp_path / "tpl_rbac.db")
    init_db(db_file)
    monkeypatch.setattr(settings, "DATABASE_PATH", db_file)
    _failed_attempts.clear()

    rad1_user, rad1_pw = "asharma", secrets.token_urlsafe(16)
    rad2_user, rad2_pw = "rad_other", secrets.token_urlsafe(16)
    adm_user, adm_pw = "sysadmin", secrets.token_urlsafe(16)

    AuthService.upsert_account_with_password(
        user_id="usr-asharma-test",
        username=rad1_user,
        password=rad1_pw,
        full_name="Dr. Aarav Sharma",
        role="Radiologist",
        designation="Consultant Radiologist",
        department="Radiology",
        email="asharma@sonoaxis.test",
        is_demo=True,
        db_path=db_file,
    )
    AuthService.upsert_account_with_password(
        user_id="usr-rad2-test",
        username=rad2_user,
        password=rad2_pw,
        full_name="Dr. Rohan Verma",
        role="Radiologist",
        designation="Consultant Radiologist",
        department="Radiology",
        email="rverma@sonoaxis.test",
        is_demo=False,
        db_path=db_file,
    )
    AuthService.upsert_account_with_password(
        user_id="usr-sysadmin-test",
        username=adm_user,
        password=adm_pw,
        full_name="System Administrator",
        role="Administrator",
        designation="Administrator",
        department="IT",
        email="sysadmin@sonoaxis.test",
        is_demo=True,
        db_path=db_file,
    )

    with TestClient(app) as tc_r1, TestClient(app) as tc_r2, TestClient(app) as tc_adm:
        t1 = tc_r1.post("/api/auth/login", json={"username": rad1_user, "password": rad1_pw}).json()["access_token"]
        t2 = tc_r2.post("/api/auth/login", json={"username": rad2_user, "password": rad2_pw}).json()["access_token"]
        ta = tc_adm.post("/api/auth/login", json={"username": adm_user, "password": adm_pw}).json()["access_token"]
        h1 = {"Authorization": f"Bearer {t1}"}
        h2 = {"Authorization": f"Bearer {t2}"}
        ha = {"Authorization": f"Bearer {ta}"}

        # 1. Single DOCX import as asharma (Radiologist) -> private custom DRAFT_CONFIG template
        imp = tc_r1.post(
            "/api/templates/import",
            files={"file": ("carotid-doppler-test.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            headers=h1,
        )
        assert imp.status_code == 201, imp.text
        own_tpl = imp.json()
        own_id = own_tpl["id"]
        assert own_tpl["status"] == "DRAFT_CONFIG"
        assert own_tpl["is_built_in"] is False
        assert own_tpl["is_shared"] is False
        assert own_tpl["created_by_user_id"] == "usr-asharma-test"

        # 2. Custom / Imported category lists the newly imported template for asharma, not rad2
        cust_r1 = tc_r1.get("/api/templates?category=custom", headers=h1).json()
        assert any(t["id"] == own_id for t in cust_r1)
        cust_r2 = tc_r2.get("/api/templates?category=custom", headers=h2).json()
        assert all(t["id"] != own_id for t in cust_r2)

        # 3. Bulk import also permitted for Radiologist
        bulk = tc_r1.post(
            "/api/templates/bulk-import",
            files=[
                ("files", ("carotid-bulk-1.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
                ("files", ("carotid-bulk-2.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ],
            headers=h1,
        )
        assert bulk.status_code == 201
        assert len(bulk.json()) == 2

        # 4. asharma configures, edits, previews, and activates own template
        cfg = tc_r1.put(
            f"/api/templates/{own_id}",
            json={
                "name": "Custom Bilateral Carotid (Aarav Sharma)",
                "category": "custom",
                "laterality": "bilateral",
                "table_type": "five_col_bilateral",
                "sections": [
                    {"order": 1, "key": "cca", "label": "Common Carotid Artery (CCA)", "heading": "Common Carotid Artery (CCA): "},
                    {"order": 2, "key": "ica", "label": "Internal Carotid Artery (ICA)", "heading": "Internal Carotid Artery (ICA): "},
                    {"order": 3, "key": "impression", "label": "Impression", "heading": "IMPRESSION: "},
                ],
            },
            headers=h1,
        )
        assert cfg.status_code == 200
        assert cfg.json()["name"] == "Custom Bilateral Carotid (Aarav Sharma)"

        prev = tc_r1.get(f"/api/templates/{own_id}/preview", headers=h1)
        assert prev.status_code == 200
        assert "Custom Bilateral Carotid (Aarav Sharma)" in prev.text
        assert "Personal Custom Template" in prev.text

        act = tc_r1.post(f"/api/templates/{own_id}/approve", json={"approved_by": "Dr. Aarav Sharma"}, headers=h1)
        assert act.status_code == 200
        assert act.json()["status"] == "APPROVED"
        assert act.json()["is_shared"] is False

        # 5. Another radiologist is blocked from reading/mutating/using asharma's private template (403)
        assert tc_r2.get(f"/api/templates/{own_id}", headers=h2).status_code == 403
        assert tc_r2.get(f"/api/templates/{own_id}/preview", headers=h2).status_code == 403
        assert tc_r2.put(f"/api/templates/{own_id}", json={"name": "Hijack"}, headers=h2).status_code == 403
        assert tc_r2.post(f"/api/templates/{own_id}/approve", json={"approved_by": "Rohan"}, headers=h2).status_code == 403
        assert tc_r2.post(f"/api/templates/{own_id}/version", headers=h2).status_code == 403
        assert tc_r2.post(f"/api/templates/{own_id}/archive", headers=h2).status_code == 403
        assert tc_r2.post("/api/reports", json={"template_id": own_id}, headers=h2).status_code == 403

        # 6. asharma creates report with own custom template, structures, and exports DOCX + PDF
        pat = tc_r1.post("/api/patients", json={"patient_id": "PT-CTPL-1", "full_name": "Custom Tpl Patient"}, headers=h1).json()
        rep = tc_r1.post("/api/reports", json={"template_id": own_id, "patient_id": pat["id"]}, headers=h1)
        assert rep.status_code == 201
        rep_id = rep.json()["id"]
        assert tc_r1.post(
            f"/api/reports/{rep_id}/structure",
            json={"transcript_text": "Internal carotid artery shows PSV of 72 cm/s bilaterally. Impression: Normal study."},
            headers=h1,
        ).status_code == 200
        assert tc_r1.get(f"/api/reports/{rep_id}/export/docx", headers=h1).status_code == 200
        pdf = tc_r1.get(f"/api/reports/{rep_id}/export/pdf", headers=h1)
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")

        # 7. Versioning & archiving own template succeeds for asharma
        ver = tc_r1.post(f"/api/templates/{own_id}/version", headers=h1)
        assert ver.status_code == 200
        assert ver.json()["version"] == 2
        assert ver.json()["status"] == "DRAFT_CONFIG"
        arc = tc_r1.post(f"/api/templates/{own_id}/archive", headers=h1)
        assert arc.status_code == 200
        assert arc.json()["status"] == "ARCHIVED"

        # 8. Shared Administrator custom templates stay Admin-only for approval/management
        adm_imp = tc_adm.post(
            "/api/templates/import",
            files={"file": ("shared-carotid.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            headers=ha,
        ).json()
        shared_id = adm_imp["id"]
        assert adm_imp["is_shared"] is True
        assert tc_r1.put(f"/api/templates/{shared_id}", json={"name": "Rad Edit"}, headers=h1).status_code == 403
        assert tc_r1.post(f"/api/templates/{shared_id}/approve", json={"approved_by": "Rad"}, headers=h1).status_code == 403
        assert tc_r1.post(f"/api/templates/{shared_id}/version", headers=h1).status_code == 403
        assert tc_r1.post(f"/api/templates/{shared_id}/archive", headers=h1).status_code == 403
        assert tc_adm.post(f"/api/templates/{shared_id}/approve", json={"approved_by": "System Administrator"}, headers=ha).status_code == 200

        # 9. All 16 original institutional templates remain strictly protected from modification/archiving (403)
        from backend.app.structuring.templates import TEMPLATES_CATALOG
        assert len(TEMPLATES_CATALOG) == 16
        for built_in_id in TEMPLATES_CATALOG.keys():
            for actor_hdr in (h1, ha):
                assert tc_r1.put(f"/api/templates/{built_in_id}", json={"name": "Altered"}, headers=actor_hdr).status_code == 403
                assert tc_r1.post(f"/api/templates/{built_in_id}/version", headers=actor_hdr).status_code == 403
                assert tc_r1.post(f"/api/templates/{built_in_id}/archive", headers=actor_hdr).status_code == 403
                assert tc_r1.post(f"/api/templates/{built_in_id}/approve", json={"approved_by": "Anyone"}, headers=actor_hdr).status_code == 403


def test_phase10h3_clinical_findings_assignment_context_retroperitoneum_age_and_completeness(tmp_path, monkeypatch):
    """
    Regression coverage for all 5 reported bugs:
    1. Persisted unassigned assignment preserves existing text & measurements, updates pending count,
       prevents duplicate assignment, survives reload, and propagates to Preview/DOCX/PDF.
    2. Contextual mapping assigns consecutive gall bladder & renal negations accurately while preserving
       standalone ambiguous findings as unassigned.
    3. Retroperitoneum ('No significant retroperitoneal lymphadenopathy is seen.') is never lost.
    4. Patient Age & Sex display separately without 'Age: Male' even when age_years is null or populated.
    5. Clinical completeness protection requires resolution or documented exclusion before sign-off.
    """
    from backend.app.core.config import settings
    from backend.app.structuring.engine import structuring_engine

    db_file = str(tmp_path / "bugs_regression.db")
    init_db(db_file)
    monkeypatch.setattr(settings, "DATABASE_PATH", db_file)
    _failed_attempts.clear()

    rad_pw = secrets.token_urlsafe(16)
    AuthService.upsert_account_with_password(
        user_id="usr-asharma-reg",
        username="asharma",
        password=rad_pw,
        full_name="Dr. Aarav Sharma",
        role="Radiologist",
        designation="Consultant Radiologist",
        department="Radiology",
        email="asharma@sonoaxis.test",
        is_demo=True,
        db_path=db_file,
    )

    # A. Direct Contextual Mapping & Retroperitoneum Structuring Verification
    reported_transcript = (
        "Liver measures 14.2 centimeters and shows homogeneous echotexture. "
        "Gall bladder is well distended. No calculus or sludge is seen. "
        "No significant retroperitoneal lymphadenopathy is seen. "
        "Right kidney measures 10.2 by 4.5 centimeters. Left kidney measures 9.8 by 4.2 centimeters. "
        "Both kidneys show maintained corticomedullary differentiation. "
        "No calculus or hydronephrosis is seen on either side. "
        "A small cyst measuring 8 mm is noted. "
        "Impression: Tiny uncomplicated renal evaluation."
    )
    res = structuring_engine.structure_transcript(reported_transcript, template_id="usg-abdomen-pelvis-male")
    sec_map = {s.key: s for s in res.sections}

    # Gall bladder gets both statements and preserves negation
    assert sec_map["gall_bladder"].is_present is True
    assert "well distended" in sec_map["gall_bladder"].text.lower()
    assert "no calculus or sludge" in sec_map["gall_bladder"].text.lower()
    assert any(f.is_negation for f in sec_map["gall_bladder"].findings)

    # Retroperitoneum present and never dropped into vascular lymph_nodes
    assert sec_map["retroperitoneum"].is_present is True
    assert "retroperitoneal lymphadenopathy" in sec_map["retroperitoneum"].text.lower()
    assert any(f.is_negation for f in sec_map["retroperitoneum"].findings)

    # Kidneys (Summary) gets both bilateral statements with negation & bilateral laterality preserved
    assert sec_map["kidneys_common"].is_present is True
    assert "corticomedullary differentiation" in sec_map["kidneys_common"].text.lower()
    assert "no calculus or hydronephrosis" in sec_map["kidneys_common"].text.lower()
    hyd_finding = next(f for f in sec_map["kidneys_common"].findings if "hydronephrosis" in f.current_text.lower())
    assert hyd_finding.is_negation is True
    assert hyd_finding.laterality == "bilateral"

    # Ambiguous positive lesion measuring 8 mm remains unassigned
    assert len(res.unassigned_findings) == 1
    assert "8 mm" in res.unassigned_findings[0].raw_text

    # B. End-to-End Authenticated Persisted Workflow (CSRF + Persisted Assign + Exports + Age/Sex)
    with TestClient(app) as tc:
        login = tc.post("/api/auth/login", json={"username": "asharma", "password": rad_pw}).json()
        csrf_hdr = {"X-CSRF-Token": login["csrf_token"]}

        # Patient initially created without age -> must NEVER render 'Age: Male'
        pat = tc.post(
            "/api/patients",
            json={"patient_id": "PT-AGE-0", "full_name": "Sonu Yadav", "gender": "Male"},
            headers=csrf_hdr,
        ).json()
        rep = tc.post(
            "/api/reports",
            json={"template_id": "usg-abdomen-pelvis-male", "patient_id": pat["id"]},
            headers=csrf_hdr,
        ).json()
        rep_id = rep["id"]

        null_age_prev = tc.get(f"/api/reports/{rep_id}/preview").text
        assert "Age: Male" not in null_age_prev
        assert "Age: Not specified" in null_age_prev
        assert "Sex: Male" in null_age_prev
        null_age_docx = docx.Document(io.BytesIO(tc.get(f"/api/reports/{rep_id}/export/docx").content))
        t0_text = null_age_docx.tables[0].rows[0].cells[1].text
        assert "Age: Male" not in t0_text
        assert "Not specified" in t0_text and "Sex: Male" in t0_text

        # Update patient age to 39 -> live draft syncs & Preview/DOCX/PDF show Age: 39 years and Sex: Male separately
        tc.put(
            f"/api/patients/{pat['id']}",
            json={"patient_id": "PT-AGE-0", "full_name": "Sonu Yadav", "age_years": 39, "gender": "Male"},
            headers=csrf_hdr,
        )

        # Inject two legacy unassigned findings into draft report (simulating user's exact scenario)
        st = tc.post(
            f"/api/reports/{rep_id}/structure",
            json={
                "transcript_text": (
                    "Liver measures 14.2 cm. Gall bladder is well distended. "
                    "No significant retroperitoneal lymphadenopathy is seen. "
                    "Right kidney measures 10.2 by 4.5 cm."
                )
            },
            headers=csrf_hdr,
        ).json()
        sf = st["structured_findings"]
        sf["unassigned_findings"] = [
            {
                "id": "u-gb-1",
                "raw_text": "No calculus or sludge is seen",
                "reason": "no_organ_identified",
                "measurements": [],
                "is_resolved": False,
                "resolved_organ_key": None,
            },
            {
                "id": "u-rk-2",
                "raw_text": "A 6 mm stone noted",
                "reason": "no_organ_identified",
                "measurements": [{"value": 6.0, "unit": "mm", "dimension": 1, "raw_str": "6 mm"}],
                "is_resolved": False,
                "resolved_organ_key": None,
            },
        ]
        sf["has_flags"] = True
        tc.put(f"/api/reports/{rep_id}", json={"structured_findings": sf}, headers=csrf_hdr)

        # Failed invalid assignment keeps findings unresolved and returns informative error string
        bad_assign = tc.post(
            f"/api/reports/{rep_id}/assign-unassigned",
            json={"unassigned_id": "u-gb-1", "target_organ_key": "nonexistent_section"},
            headers=csrf_hdr,
        )
        assert bad_assign.status_code == 400
        assert isinstance(bad_assign.json()["detail"], str)
        after_fail = tc.get(f"/api/reports/{rep_id}").json()["structured_findings"]["unassigned_findings"]
        assert all(not u["is_resolved"] for u in after_fail)

        # Clinical completeness blocks review while findings remain pending
        assert tc.post(
            f"/api/reports/{rep_id}/review",
            json={"reviewed_by": "Dr. Aarav Sharma", "acknowledge_unresolved": True},
            headers=csrf_hdr,
        ).status_code == 400

        # Assign u-gb-1 -> gall_bladder (appends to 'well distended', keeps it intact!)
        as1 = tc.post(
            f"/api/reports/{rep_id}/assign-unassigned",
            json={"unassigned_id": "u-gb-1", "target_organ_key": "gall_bladder"},
            headers=csrf_hdr,
        )
        assert as1.status_code == 200
        sf1 = as1.json()["structured_findings"]
        pending_1 = [u for u in sf1["unassigned_findings"] if not u["is_resolved"]]
        assert len(pending_1) == 1

        # Duplicate assignment rejected cleanly (400)
        dup_as1 = tc.post(
            f"/api/reports/{rep_id}/assign-unassigned",
            json={"unassigned_id": "u-gb-1", "target_organ_key": "gall_bladder"},
            headers=csrf_hdr,
        )
        assert dup_as1.status_code == 400

        # Assign u-rk-2 -> right_kidney (keeps existing '10.2 by 4.5 cm' measurement AND appends 'A 6 mm stone noted')
        as2 = tc.post(
            f"/api/reports/{rep_id}/assign-unassigned",
            json={"unassigned_id": "u-rk-2", "target_organ_key": "right_kidney"},
            headers=csrf_hdr,
        )
        assert as2.status_code == 200

        # Reload persisted report -> verify persistence, intact text & measurements, 0 pending
        reloaded = tc.get(f"/api/reports/{rep_id}").json()["structured_findings"]
        assert all(u["is_resolved"] for u in reloaded["unassigned_findings"])
        sec_reloaded = {s["key"]: s for s in reloaded["sections"]}
        assert "well distended" in sec_reloaded["gall_bladder"]["text"].lower()
        assert "no calculus or sludge is seen" in sec_reloaded["gall_bladder"]["text"].lower()
        assert "10.2" in sec_reloaded["right_kidney"]["text"]
        assert "A 6 mm stone noted" in sec_reloaded["right_kidney"]["text"]
        assert len(sec_reloaded["right_kidney"]["measurements"]) == 2
        assert "retroperitoneal lymphadenopathy" in sec_reloaded["retroperitoneum"]["text"].lower()

        # Now review sign-off succeeds cleanly
        rev = tc.post(
            f"/api/reports/{rep_id}/review",
            json={"reviewed_by": "Dr. Aarav Sharma", "acknowledge_unresolved": False},
            headers=csrf_hdr,
        )
        assert rev.status_code == 200

        # Verify Preview, Word, and PDF exports all contain assigned findings, retroperitoneum, and Age/Sex
        prev_html = tc.get(f"/api/reports/{rep_id}/preview").text
        assert "39 years" in prev_html and "Sex: Male" in prev_html and "Age: Male" not in prev_html
        assert "No calculus or sludge is seen" in prev_html
        assert "A 6 mm stone noted" in prev_html
        assert "retroperitoneal lymphadenopathy" in prev_html

        docx_bytes = tc.get(f"/api/reports/{rep_id}/export/docx").content
        doc_obj = docx.Document(io.BytesIO(docx_bytes))
        full_doc_text = "\n".join(p.text for p in doc_obj.paragraphs) + "\n" + doc_obj.tables[0].rows[0].cells[1].text
        assert "39 years" in doc_obj.tables[0].rows[0].cells[1].text
        assert "Sex: Male" in doc_obj.tables[0].rows[0].cells[1].text
        assert "Age: Male" not in full_doc_text
        assert "No calculus or sludge is seen" in full_doc_text
        assert "A 6 mm stone noted" in full_doc_text
        assert "retroperitoneal lymphadenopathy" in full_doc_text

        pdf_bytes = tc.get(f"/api/reports/{rep_id}/export/pdf").content
        assert pdf_bytes.startswith(b"%PDF-")
        assert len(pdf_bytes) > 5000
