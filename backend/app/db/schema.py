import json
import logging
from datetime import datetime, timezone
from typing import Optional
from backend.app.db.connection import get_db
from backend.app.structuring.templates import TEMPLATES_CATALOG

logger = logging.getLogger("sonovoice.db.schema")

CURRENT_SCHEMA_VERSION = 1

DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS patients (
        id TEXT PRIMARY KEY,
        patient_id TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        age_years INTEGER,
        gender TEXT,
        contact_number TEXT,
        clinical_notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS examination_templates (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        gender TEXT NOT NULL,
        examination_type TEXT NOT NULL,
        canonical_sections TEXT NOT NULL,
        version INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS reports (
        id TEXT PRIMARY KEY,
        patient_id TEXT REFERENCES patients(id) ON DELETE SET NULL,
        template_id TEXT NOT NULL REFERENCES examination_templates(id),
        report_number TEXT,
        report_date TEXT NOT NULL,
        referral_doctor TEXT,
        status TEXT NOT NULL DEFAULT 'DRAFT',
        patient_snapshot TEXT,
        original_transcript TEXT,
        edited_transcript TEXT,
        structured_findings TEXT,
        impression TEXT,
        revision_number INTEGER NOT NULL DEFAULT 1,
        is_reviewed INTEGER NOT NULL DEFAULT 0,
        reviewed_by TEXT,
        reviewed_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS audio_recordings (
        id TEXT PRIMARY KEY,
        report_id TEXT REFERENCES reports(id) ON DELETE CASCADE,
        file_path TEXT NOT NULL,
        filename TEXT NOT NULL,
        mime_type TEXT,
        file_size INTEGER,
        duration_seconds REAL,
        recorded_at TEXT NOT NULL,
        transcription_model TEXT,
        transcription_status TEXT DEFAULT 'completed',
        retention_policy TEXT DEFAULT 'retain'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS structured_findings (
        id TEXT PRIMARY KEY,
        report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
        organ_key TEXT NOT NULL,
        current_text TEXT NOT NULL,
        source_text TEXT,
        measurements_json TEXT,
        laterality TEXT,
        is_negation INTEGER DEFAULT 0,
        is_uncertain INTEGER DEFAULT 0,
        review_flags_json TEXT,
        char_start INTEGER,
        char_end INTEGER,
        audio_timestamp_start REAL,
        audio_timestamp_end REAL,
        is_superseded INTEGER DEFAULT 0,
        superseded_by_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS unassigned_findings (
        id TEXT PRIMARY KEY,
        report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
        raw_text TEXT NOT NULL,
        reason TEXT NOT NULL,
        suggested_organs_json TEXT,
        is_resolved INTEGER DEFAULT 0,
        resolved_organ_key TEXT,
        created_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS report_revisions (
        id TEXT PRIMARY KEY,
        report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
        revision_number INTEGER NOT NULL,
        change_type TEXT NOT NULL,
        report_snapshot TEXT NOT NULL,
        changed_by TEXT DEFAULT 'clinician',
        is_reviewed INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        description TEXT,
        updated_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        credentials TEXT,
        designation TEXT,
        role TEXT NOT NULL DEFAULT 'Radiologist',
        department TEXT,
        email TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        is_demo INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_login_at TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS user_sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash TEXT UNIQUE NOT NULL,
        csrf_token TEXT,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        revoked INTEGER NOT NULL DEFAULT 0
    );
    """
]

INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_patients_patient_id ON patients(patient_id);",
    "CREATE INDEX IF NOT EXISTS idx_patients_full_name ON patients(full_name);",
    "CREATE INDEX IF NOT EXISTS idx_reports_patient_id ON reports(patient_id);",
    "CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);",
    "CREATE INDEX IF NOT EXISTS idx_reports_template_id ON reports(template_id);",
    "CREATE INDEX IF NOT EXISTS idx_reports_report_date ON reports(report_date);",
    "CREATE INDEX IF NOT EXISTS idx_findings_report_organ ON structured_findings(report_id, organ_key);",
    "CREATE INDEX IF NOT EXISTS idx_revisions_report ON report_revisions(report_id, revision_number);",
    "CREATE INDEX IF NOT EXISTS idx_audio_report ON audio_recordings(report_id);",
    "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);",
    "CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(token_hash);"
]

def migrate_templates_table(conn):
    """Safely adds missing columns to examination_templates table for dynamic template management."""
    cursor = conn.execute("PRAGMA table_info(examination_templates)")
    existing_cols = {row["name"] for row in cursor.fetchall()}
    new_cols = [
        ("category", "TEXT DEFAULT 'abdomen_pelvis'"),
        ("laterality", "TEXT DEFAULT 'not_applicable'"),
        ("file_name", "TEXT"),
        ("file_path", "TEXT"),
        ("status", "TEXT DEFAULT 'APPROVED'"),
        ("table_type", "TEXT DEFAULT 'none'"),
        ("table_config_json", "TEXT"),
        ("repeatable_config_json", "TEXT"),
        ("approved_by", "TEXT"),
        ("approved_at", "TEXT"),
        ("is_built_in", "INTEGER DEFAULT 0"),
        ("is_shared", "INTEGER DEFAULT 0"),
        ("created_by_user_id", "TEXT"),
        ("created_by_name", "TEXT"),
        ("updated_at", "TEXT"),
        ("doc_structure_json", "TEXT")
    ]
    for col_name, col_def in new_cols:
        if col_name not in existing_cols:
            conn.execute(f"ALTER TABLE examination_templates ADD COLUMN {col_name} {col_def}")

def init_db(db_path: Optional[str] = None):
    """
    Initializes the SQLite database:
    - Enforces schema versioning.
    - Creates missing tables and indexes idempotently.
    - Migrates dynamic template management columns.
    - Seeds all 16 built-in examination templates across the 4 families.
    - Never destroys existing data on restart.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_db(db_path) as conn:
        for stmt in DDL_STATEMENTS:
            conn.execute(stmt)

        for idx_stmt in INDEX_STATEMENTS:
            conn.execute(idx_stmt)

        # Apply schema migrations for dynamic templates and auth columns
        migrate_templates_table(conn)

        u_cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "is_demo" not in u_cols:
            conn.execute("ALTER TABLE users ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0")

        s_cols = {row["name"] for row in conn.execute("PRAGMA table_info(user_sessions)").fetchall()}
        if "csrf_token" not in s_cols:
            conn.execute("ALTER TABLE user_sessions ADD COLUMN csrf_token TEXT")

        # Check and set schema version
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        current_v = row[0] if row and row[0] is not None else 0
        if current_v < CURRENT_SCHEMA_VERSION:
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (CURRENT_SCHEMA_VERSION, now)
            )
            logger.info(f"Initialized database schema to version {CURRENT_SCHEMA_VERSION}")

        # Seed All 16 Built-in Examination Templates
        for tid, tdata in TEMPLATES_CATALOG.items():
            existing = conn.execute("SELECT id FROM examination_templates WHERE id = ?", (tid,)).fetchone()
            sections_json = json.dumps([s.__dict__ if hasattr(s, "__dict__") else s for s in tdata["sections"]])
            if not existing:
                conn.execute(
                    """
                    INSERT INTO examination_templates (
                        id, name, gender, examination_type, canonical_sections, version, created_at,
                        category, laterality, file_name, status, table_type, is_built_in, is_shared, approved_by, approved_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tid,
                        tdata["name"],
                        tdata.get("gender", "Any"),
                        tdata.get("category", "abdomen_pelvis"),
                        sections_json,
                        1,
                        now,
                        tdata.get("category", "abdomen_pelvis"),
                        tdata.get("laterality", "not_applicable"),
                        tdata.get("file_name"),
                        "APPROVED",
                        tdata.get("table_type", "none"),
                        1,
                        1,
                        "System Initializer",
                        now
                    )
                )
            else:
                # Update metadata for existing built-in templates
                conn.execute(
                    """
                    UPDATE examination_templates
                    SET category = ?, laterality = ?, file_name = ?, status = 'APPROVED',
                        table_type = ?, is_built_in = 1, is_shared = 1, canonical_sections = ?
                    WHERE id = ?
                    """,
                    (
                        tdata.get("category", "abdomen_pelvis"),
                        tdata.get("laterality", "not_applicable"),
                        tdata.get("file_name"),
                        tdata.get("table_type", "none"),
                        sections_json,
                        tid
                    )
                )

        # Seed Default Settings
        default_settings = [
            ("stt_model", "small.en", "Primary speech recognition model"),
            ("device", "cpu", "Inference computing device (cpu/cuda)"),
            ("compute_type", "int8", "Whisper compute precision"),
            ("audio_retention_days", "30", "Days to retain uploaded audio files"),
            ("require_review_acknowledgment", "true", "Require confirmation of unassigned findings on review")
        ]
        for k, v, desc in default_settings:
            existing = conn.execute("SELECT key FROM app_settings WHERE key = ?", (k,)).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO app_settings (key, value, description, updated_at) VALUES (?, ?, ?, ?)",
                    (k, json.dumps(v), desc, now)
                )

    logger.info("Database schema verification and initialization complete.")
