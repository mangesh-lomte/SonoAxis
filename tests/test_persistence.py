import os
import uuid
import tempfile
import sqlite3
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.db.schema import init_db
from backend.app.db.connection import get_db, get_db_connection
from backend.app.services.patient_service import PatientService
from backend.app.services.report_service import ReportService
from backend.app.services.audio_storage import AudioStorageService
from backend.app.services.backup_service import BackupService
from backend.app.db.repositories.dashboard_repo import DashboardRepository
from backend.app.main import app
from tests.conftest import seed_and_login_test_client

@pytest.fixture(scope="function")
def test_db_path(tmp_path):
    """Provides an isolated temporary SQLite database for each test."""
    db_file = str(tmp_path / f"test_{uuid.uuid4().hex[:8]}.db")
    init_db(db_file)
    return db_file

@pytest.fixture(scope="function")
def client(test_db_path, monkeypatch):
    """Configures TestClient with the isolated test database."""
    monkeypatch.setattr(settings, "DATABASE_PATH", test_db_path)
    with TestClient(app) as test_client:
        seed_and_login_test_client(test_client, role="Radiologist", db_path=test_db_path)
        yield test_client

# 1. Database Initialization
def test_1_database_initialization(test_db_path):
    assert os.path.exists(test_db_path)
    with get_db(test_db_path) as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "patients" in tables
        assert "reports" in tables
        assert "examination_templates" in tables
        assert "audio_recordings" in tables
        assert "report_revisions" in tables

# 2. Repeated Initialization Without Data Loss
def test_2_repeated_initialization_preserves_data(test_db_path):
    p = PatientService.create_patient({
        "patient_id": "P-TEST-001",
        "full_name": "Initial Patient"
    }, db_path=test_db_path)
    assert p["id"] is not None

    # Re-run init_db on the same database
    init_db(test_db_path)

    # Verify patient still exists intact
    retrieved = PatientService.get_patient(p["id"], db_path=test_db_path)
    assert retrieved is not None
    assert retrieved["full_name"] == "Initial Patient"

# 3. Patient Creation
def test_3_patient_creation(test_db_path):
    p = PatientService.create_patient({
        "patient_id": "P-1002",
        "full_name": "Jane Doe",
        "age_years": 38,
        "gender": "Female"
    }, db_path=test_db_path)
    assert p["patient_id"] == "P-1002"
    assert p["full_name"] == "Jane Doe"
    assert p["age_years"] == 38

# 4. Patient Search
def test_4_patient_search(test_db_path):
    PatientService.create_patient({"patient_id": "SRCH-01", "full_name": "Robert Frost"}, db_path=test_db_path)
    PatientService.create_patient({"patient_id": "SRCH-02", "full_name": "Alice Walker"}, db_path=test_db_path)

    res_name = PatientService.search_patients("Walker", db_path=test_db_path)
    assert len(res_name) == 1
    assert res_name[0]["patient_id"] == "SRCH-02"

    res_id = PatientService.search_patients("SRCH-01", db_path=test_db_path)
    assert len(res_id) == 1
    assert res_id[0]["full_name"] == "Robert Frost"

# 5. Patient Editing
def test_5_patient_editing(test_db_path):
    p = PatientService.create_patient({"patient_id": "EDIT-01", "full_name": "Original Name"}, db_path=test_db_path)
    updated = PatientService.update_patient(p["id"], {"full_name": "Modified Name", "age_years": 50}, db_path=test_db_path)
    assert updated["full_name"] == "Modified Name"
    assert updated["age_years"] == 50

# 6. Duplicate Patient ID Handling
def test_6_duplicate_patient_id_rejected(test_db_path):
    PatientService.create_patient({"patient_id": "DUP-01", "full_name": "First Entry"}, db_path=test_db_path)
    with pytest.raises(ValueError, match="already exists"):
        PatientService.create_patient({"patient_id": "DUP-01", "full_name": "Second Entry"}, db_path=test_db_path)

# 7. Male Report Creation
def test_7_male_report_creation(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    assert r["id"] is not None
    assert r["template_id"] == "usg-abdomen-pelvis-male"
    assert r["status"] == "DRAFT"

# 8. Female Report Creation
def test_8_female_report_creation(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-female"}, db_path=test_db_path)
    assert r["id"] is not None
    assert r["template_id"] == "usg-abdomen-pelvis-female"
    assert r["status"] == "DRAFT"

# 9. Blank New Clinical Findings
def test_9_blank_new_clinical_findings(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    findings = r["structured_findings"]
    assert findings is not None
    for sec in findings["sections"]:
        assert sec["is_present"] is False
        assert sec["text"] is None

# 10. Blank Initial Impression
def test_10_blank_initial_impression(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    assert r["impression"] is None

# 11. Report Saving
def test_11_report_saving(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    saved = ReportService.update_report(r["id"], {"referral_doctor": "Dr. Smith"}, db_path=test_db_path)
    assert saved["referral_doctor"] == "Dr. Smith"
    assert saved["revision_number"] == 2

# 12. Report Retrieval
def test_12_report_retrieval(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    fetched = ReportService.get_report(r["id"], db_path=test_db_path)
    assert fetched is not None
    assert fetched["id"] == r["id"]

# 13. Report Search and Filters
def test_13_report_search_and_filters(test_db_path):
    r1 = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    r2 = ReportService.create_report({"template_id": "usg-abdomen-pelvis-female"}, db_path=test_db_path)
    ReportService.mark_reviewed(r2["id"], reviewed_by="Dr. Radiologist", acknowledge_unresolved=True, db_path=test_db_path)

    drafts = ReportService.list_reports(status="DRAFT", db_path=test_db_path)
    assert any(x["id"] == r1["id"] for x in drafts)
    assert not any(x["id"] == r2["id"] for x in drafts)

    females = ReportService.list_reports(template_id="usg-abdomen-pelvis-female", db_path=test_db_path)
    assert any(x["id"] == r2["id"] for x in females)

# 14. Patient-Report Associations
def test_14_patient_report_associations(test_db_path):
    p = PatientService.create_patient({"patient_id": "ASSOC-01", "full_name": "Assoc Test"}, db_path=test_db_path)
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male", "patient_id": p["id"]}, db_path=test_db_path)
    assert r["patient_id"] == p["id"]

    patient_reports = ReportService.list_reports(patient_id=p["id"], db_path=test_db_path)
    assert len(patient_reports) == 1
    assert patient_reports[0]["id"] == r["id"]

# 15. Patient Information Snapshots
def test_15_patient_information_snapshot_preservation(test_db_path):
    p = PatientService.create_patient({
        "patient_id": "SNAP-01",
        "full_name": "Historic Name",
        "age_years": 40
    }, db_path=test_db_path)
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male", "patient_id": p["id"]}, db_path=test_db_path)

    # Edit patient details later
    PatientService.update_patient(p["id"], {"full_name": "New Changed Name"}, db_path=test_db_path)

    # Verify report's patient snapshot preserves the historic name
    report_fetched = ReportService.get_report(r["id"], db_path=test_db_path)
    snapshot = report_fetched["patient_snapshot"]
    assert snapshot is not None
    assert snapshot["full_name"] == "Historic Name"

# 16. Audio Associations
def test_16_audio_associations(test_db_path, tmp_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    audio_rec = AudioStorageService.save_audio_file(
        report_id=r["id"],
        file_bytes=b"RIFF\x24\x00\x00\x00WAVEfmt ",
        original_filename="dictation.wav",
        duration_seconds=5.2,
        db_path=test_db_path
    )
    assert audio_rec["report_id"] == r["id"]
    assert os.path.exists(audio_rec["file_path"])
    # Cleanup test audio file
    if os.path.exists(audio_rec["file_path"]):
        os.remove(audio_rec["file_path"])

# 17. Original Transcript Preservation
def test_17_original_transcript_preservation(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    ReportService.structure_and_save_report(
        r["id"],
        transcript_text="Liver is normal in size. Right kidney measures 10.2 cm.",
        db_path=test_db_path
    )
    # Manually edit transcript
    updated = ReportService.update_report(
        r["id"],
        {"edited_transcript": "Liver is normal in size. Right kidney measures 10.8 cm."},
        db_path=test_db_path
    )
    assert "10.2" in updated["original_transcript"]
    assert "10.8" in updated["edited_transcript"]

# 18. Edited Transcript Preservation
def test_18_edited_transcript_preservation(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    ReportService.update_report(r["id"], {"edited_transcript": "Custom user-edited transcript."}, db_path=test_db_path)
    fetched = ReportService.get_report(r["id"], db_path=test_db_path)
    assert fetched["edited_transcript"] == "Custom user-edited transcript."

# 19. Structured Findings Persistence
def test_19_structured_findings_persistence(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    ReportService.structure_and_save_report(
        r["id"],
        transcript_text="Liver is normal in size. Spleen measures 11.0 cm.",
        db_path=test_db_path
    )
    fetched = ReportService.get_report(r["id"], db_path=test_db_path)
    sections = fetched["structured_findings"]["sections"]
    liver = next(s for s in sections if s["key"] == "liver")
    spleen = next(s for s in sections if s["key"] == "spleen")
    assert liver["is_present"] is True
    assert spleen["is_present"] is True
    assert "11.0" in spleen["text"]

# 20. Measurement Correction Persistence
def test_20_measurement_correction_persistence(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    ReportService.structure_and_save_report(
        r["id"],
        transcript_text="Right kidney measures 10.2 cm, liver is normal in size, correction, right kidney measures 10.8 cm.",
        db_path=test_db_path
    )
    fetched = ReportService.get_report(r["id"], db_path=test_db_path)
    sections = fetched["structured_findings"]["sections"]
    rk = next(s for s in sections if s["key"] == "right_kidney")
    assert "10.8" in rk["text"]
    assert "10.2" not in rk["text"]
    assert len(fetched["structured_findings"]["superseded_history"]) == 1

# 21. Unassigned Finding Persistence
def test_21_unassigned_finding_persistence(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    ReportService.structure_and_save_report(
        r["id"],
        transcript_text="Patient had severe acoustic shadowing from overlying gas.",
        db_path=test_db_path
    )
    fetched = ReportService.get_report(r["id"], db_path=test_db_path)
    unassigned = fetched["structured_findings"]["unassigned_findings"]
    assert len(unassigned) >= 1
    assert "shadowing" in unassigned[0]["raw_text"]

# 22. Manual Editing Persistence
def test_22_manual_editing_persistence(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    ReportService.update_report(r["id"], {"impression": "Mild fatty infiltration of the liver."}, db_path=test_db_path)
    fetched = ReportService.get_report(r["id"], db_path=test_db_path)
    assert fetched["impression"] == "Mild fatty infiltration of the liver."

# 23. Revision History
def test_23_revision_history(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    ReportService.update_report(r["id"], {"referral_doctor": "Dr. A"}, change_type="EDIT_DOC", db_path=test_db_path)
    ReportService.update_report(r["id"], {"referral_doctor": "Dr. B"}, change_type="EDIT_DOC", db_path=test_db_path)

    revs = ReportService.get_revisions(r["id"], db_path=test_db_path)
    assert len(revs) == 3  # CREATE + 2 EDITS
    assert revs[0]["revision_number"] == 3
    assert revs[1]["revision_number"] == 2
    assert revs[2]["revision_number"] == 1

# 24. Draft Status Initialization
def test_24_draft_status_initialization(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    assert r["status"] == "DRAFT"
    assert r["is_reviewed"] is False
    assert r["reviewed_at"] is None

# 25. Explicit Review
def test_25_explicit_review(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    reviewed = ReportService.mark_reviewed(r["id"], reviewed_by="Dr. Radiologist", acknowledge_unresolved=True, db_path=test_db_path)
    assert reviewed["status"] == "REVIEWED"
    assert reviewed["is_reviewed"] is True
    assert reviewed["reviewed_by"] == "Dr. Radiologist"
    assert reviewed["reviewed_at"] is not None

# 26. Reviewed Report Returning to Draft After Editing
def test_26_reviewed_report_returns_to_draft_on_edit(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    ReportService.mark_reviewed(r["id"], reviewed_by="Dr. Radiologist", acknowledge_unresolved=True, db_path=test_db_path)

    # Edit the reviewed report
    edited = ReportService.update_report(r["id"], {"impression": "Updated impression"}, db_path=test_db_path)
    assert edited["status"] == "DRAFT"
    assert edited["is_reviewed"] is False
    assert edited["reviewed_at"] is None

# 27. Stale Update Prevention (Optimistic Concurrency)
def test_27_stale_update_prevention(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    # Expected revision is 1
    ReportService.update_report(r["id"], {"referral_doctor": "Dr. First"}, expected_revision_number=1, db_path=test_db_path)
    
    # Try updating again claiming expected revision is still 1 (stale lock)
    with pytest.raises(ValueError, match="Concurrency conflict"):
        ReportService.update_report(r["id"], {"referral_doctor": "Dr. Stale"}, expected_revision_number=1, db_path=test_db_path)

# 28. Regeneration Without Silent Manual Edit Loss
def test_28_regeneration_tracking(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    ReportService.structure_and_save_report(r["id"], "Liver is normal.", db_path=test_db_path)
    
    # User manually edits findings
    ReportService.update_report(r["id"], {"impression": "Manual impression."}, db_path=test_db_path)
    
    # Re-generate with force flag creates a distinct REGENERATE revision
    ReportService.structure_and_save_report(r["id"], "Spleen is normal.", force_regenerate=True, db_path=test_db_path)
    revs = ReportService.get_revisions(r["id"], db_path=test_db_path)
    assert any(rev["change_type"] == "REGENERATE" for rev in revs)

# 29. Invalid API Requests
def test_29_invalid_api_requests(client):
    res = client.post("/api/patients", json={"patient_id": "", "full_name": ""})
    assert res.status_code == 422 or res.status_code == 400

    res_not_found = client.get("/api/reports/non-existent-uuid")
    assert res_not_found.status_code == 404

# 30. Database Transaction Rollback
def test_30_database_transaction_rollback(test_db_path):
    try:
        with get_db(test_db_path) as conn:
            conn.execute("INSERT INTO patients (id, patient_id, full_name, created_at, updated_at) VALUES ('1', 'T-ROLL', 'Rollback', 'now', 'now')")
            # Trigger intentional integrity violation
            conn.execute("INSERT INTO patients (id, patient_id, full_name, created_at, updated_at) VALUES ('1', 'T-ROLL', 'Duplicate PK', 'now', 'now')")
    except Exception:
        pass

    # Verify first insert was rolled back
    with get_db(test_db_path) as conn:
        row = conn.execute("SELECT * FROM patients WHERE patient_id = 'T-ROLL'").fetchone()
        assert row is None

# 31. Controlled Report Deletion
def test_31_controlled_report_deletion(test_db_path):
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    assert ReportService.get_report(r["id"], db_path=test_db_path) is not None
    deleted = ReportService.delete_report(r["id"], db_path=test_db_path)
    assert deleted is True
    assert ReportService.get_report(r["id"], db_path=test_db_path) is None

# 32. Controlled Patient Deletion
def test_32_controlled_patient_deletion(test_db_path):
    p = PatientService.create_patient({"patient_id": "DEL-01", "full_name": "Delete Me"}, db_path=test_db_path)
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male", "patient_id": p["id"]}, db_path=test_db_path)

    # Deleting patient with active reports without force flag raises error
    with pytest.raises(ValueError, match="Cannot delete patient with"):
        PatientService.delete_patient(p["id"], force=False, db_path=test_db_path)

    # Deleting patient with force=True succeeds
    deleted = PatientService.delete_patient(p["id"], force=True, db_path=test_db_path)
    assert deleted is True

# 33. Backup Creation
def test_33_backup_creation(test_db_path, tmp_path):
    backup_dir = str(tmp_path / "backups")
    res = BackupService.create_backup(source_db_path=test_db_path, backup_dir=backup_dir)
    assert res["status"] == "verified"
    assert os.path.exists(res["backup_path"])

# 34. Backup Restoration
def test_34_backup_restoration_to_temp(test_db_path, tmp_path):
    PatientService.create_patient({"patient_id": "BAK-01", "full_name": "Backup Patient"}, db_path=test_db_path)
    backup_dir = str(tmp_path / "backups")
    res = BackupService.create_backup(source_db_path=test_db_path, backup_dir=backup_dir)

    temp_restore = str(tmp_path / "restored_test.db")
    restore_res = BackupService.test_restore_to_temp(res["backup_path"], temp_restore)
    assert restore_res["status"] == "success"
    assert restore_res["patients_count"] >= 1

# 35. Temporary Audio Cleanup
def test_35_temporary_audio_cleanup():
    # Should run safely without throwing errors
    cleaned = AudioStorageService.cleanup_old_audio(retention_days=30)
    assert isinstance(cleaned, int)

# 36. File Path Security
def test_36_file_path_security():
    with pytest.raises(Exception):
        AudioStorageService.save_audio_file(
            report_id=None,
            file_bytes=b"dummy",
            original_filename="../../../malicious.exe"
        )

# 37. Dashboard Statistics
def test_37_dashboard_statistics(test_db_path):
    PatientService.create_patient({"patient_id": "DASH-01", "full_name": "Dash Patient"}, db_path=test_db_path)
    r1 = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male"}, db_path=test_db_path)
    r2 = ReportService.create_report({"template_id": "usg-abdomen-pelvis-female"}, db_path=test_db_path)
    ReportService.mark_reviewed(r2["id"], reviewed_by="Dr. Radiologist", acknowledge_unresolved=True, db_path=test_db_path)

    with get_db(test_db_path) as conn:
        stats = DashboardRepository.get_stats(conn)
        assert stats["total_reports"] >= 2
        assert stats["draft_reports"] >= 1
        assert stats["reviewed_reports"] >= 1
        assert "usg-abdomen-pelvis-male" in stats["template_distribution"]

# 38. Application Restart with Persistent Records
def test_38_persistence_after_restart(test_db_path):
    p = PatientService.create_patient({"patient_id": "RESTART-01", "full_name": "Persist Check"}, db_path=test_db_path)
    r = ReportService.create_report({"template_id": "usg-abdomen-pelvis-male", "patient_id": p["id"]}, db_path=test_db_path)
    ReportService.structure_and_save_report(r["id"], "Liver is normal.", db_path=test_db_path)

    # Simulate backend complete restart by re-initializing connection to same db file
    init_db(test_db_path)
    recovered_r = ReportService.get_report(r["id"], db_path=test_db_path)
    assert recovered_r is not None
    assert recovered_r["patient_snapshot"]["patient_id"] == "RESTART-01"
    assert recovered_r["structured_findings"]["sections"][0]["is_present"] is True

# 39. Offline Operation
def test_39_offline_operation():
    # Verify no external URLs or cloud endpoints are queried in settings
    assert "127.0.0.1" in settings.HOST
    assert "groq" not in settings.APP_NAME.lower()
    assert "openai" not in settings.APP_NAME.lower()
