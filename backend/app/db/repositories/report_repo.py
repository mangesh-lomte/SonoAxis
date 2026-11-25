import uuid
import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from backend.app.structuring.templates import TEMPLATES_CATALOG, get_template_def

class ReportRepository:
    @staticmethod
    def create(conn: sqlite3.Connection, data: Dict[str, Any]) -> Dict[str, Any]:
        report_uuid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        report_date = data.get("report_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        template_id = data["template_id"]
        t_def = get_template_def(template_id)
        if not t_def:
            raise ValueError(f"Unsupported template_id '{template_id}'")
        if t_def.get("status") != "APPROVED":
            raise ValueError(f"Cannot initialize clinical report with unapproved template '{template_id}' (status: {t_def.get('status')}). Template must be APPROVED before clinical use.")

        # Patient Snapshot: freeze current patient info into the report
        patient_snapshot = None
        patient_id = data.get("patient_id")
        if patient_id:
            p_row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
            if p_row:
                patient_snapshot = {
                    "id": p_row["id"],
                    "patient_id": p_row["patient_id"],
                    "full_name": p_row["full_name"],
                    "age_years": p_row["age_years"],
                    "gender": p_row["gender"],
                    "contact_number": p_row["contact_number"]
                }

        # Generate human-readable report number (e.g. RPT-YYYYMMDD-XXXX)
        short_id = report_uuid[:6].upper()
        date_str = datetime.now(timezone.utc).strftime("%y%m%d")
        report_number = f"RPT-{date_str}-{short_id}"

        # Initialize blank structured report schema
        initial_structured = {
            "template_id": template_id,
            "template_name": t_def.get("name", template_id),
            "gender": t_def.get("gender", "Any"),
            "category": t_def.get("category", "custom"),
            "laterality": t_def.get("laterality", "not_applicable"),
            "sections": [
                {
                    "order": s["order"] if isinstance(s, dict) else s.order,
                    "key": s["key"] if isinstance(s, dict) else s.key,
                    "label": s["label"] if isinstance(s, dict) else s.label,
                    "heading": s.get("heading", "") if isinstance(s, dict) else getattr(s, "heading", ""),
                    "is_present": False,
                    "text": None,
                    "measurements": [],
                    "findings": []
                }
                for s in t_def.get("sections", [])
            ],
            "impression": None,
            "unassigned_findings": [],
            "superseded_history": [],
            "processing_time_ms": 0.0
        }

        conn.execute(
            """
            INSERT INTO reports (
                id, patient_id, template_id, report_number, report_date, referral_doctor,
                status, patient_snapshot, original_transcript, edited_transcript,
                structured_findings, impression, revision_number, is_reviewed,
                reviewed_by, reviewed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'DRAFT', ?, NULL, NULL, ?, NULL, 1, 0, NULL, NULL, ?, ?)
            """,
            (
                report_uuid,
                patient_id,
                template_id,
                report_number,
                report_date,
                data.get("referral_doctor"),
                json.dumps(patient_snapshot) if patient_snapshot else None,
                json.dumps(initial_structured),
                now,
                now
            )
        )

        # Create initial revision record
        created_report = ReportRepository.get_by_id(conn, report_uuid)
        ReportRepository._create_revision(
            conn, report_uuid, 1, "CREATE", created_report, is_reviewed=False
        )

        return created_report

    @staticmethod
    def get_by_id(conn: sqlite3.Connection, report_uuid: str) -> Optional[Dict[str, Any]]:
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_uuid,)).fetchone()
        if not row:
            return None
        res = dict(row)
        t_def = get_template_def(res["template_id"])
        res["template_name"] = t_def.get("name", res["template_id"]) if t_def else res["template_id"]
        res["patient_snapshot"] = json.loads(res["patient_snapshot"]) if res["patient_snapshot"] else None
        if res.get("patient_id"):
            p_row = conn.execute(
                "SELECT id, patient_id, full_name, age_years, gender, contact_number FROM patients WHERE id = ?",
                (res["patient_id"],),
            ).fetchone()
            if p_row:
                snap = dict(res.get("patient_snapshot") or {})
                if not snap:
                    snap = {
                        "id": p_row["id"],
                        "patient_id": p_row["patient_id"],
                        "full_name": p_row["full_name"],
                        "age_years": p_row["age_years"],
                        "gender": p_row["gender"],
                        "contact_number": p_row["contact_number"],
                    }
                else:
                    if snap.get("age_years") is None and p_row["age_years"] is not None:
                        snap["age_years"] = p_row["age_years"]
                    if not snap.get("gender") and p_row["gender"]:
                        snap["gender"] = p_row["gender"]
                res["patient_snapshot"] = snap
        res["structured_findings"] = json.loads(res["structured_findings"]) if res["structured_findings"] else None
        res["is_reviewed"] = bool(res["is_reviewed"])

        audio_rows = conn.execute(
            "SELECT id, filename, mime_type, file_size, duration_seconds, recorded_at, transcription_model FROM audio_recordings WHERE report_id = ? ORDER BY recorded_at ASC",
            (report_uuid,)
        ).fetchall()
        db_recs = [dict(r) for r in audio_rows]
        if db_recs:
            res["recordings"] = db_recs
        elif res.get("structured_findings") and res["structured_findings"].get("recordings"):
            res["recordings"] = res["structured_findings"]["recordings"]
        else:
            res["recordings"] = []
        return res

    @staticmethod
    def list_reports(
        conn: sqlite3.Connection,
        status: Optional[str] = None,
        template_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        where_clauses = []
        params = []

        if status:
            where_clauses.append("r.status = ?")
            params.append(status.upper())
        if template_id:
            where_clauses.append("r.template_id = ?")
            params.append(template_id)
        if patient_id:
            where_clauses.append("r.patient_id = ?")
            params.append(patient_id)
        if query and query.strip():
            param = f"%{query.strip()}%"
            where_clauses.append("(r.report_number LIKE ? OR p.full_name LIKE ? OR p.patient_id LIKE ?)")
            params.extend([param, param, param])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        sql = f"""
            SELECT r.id, r.report_number, r.patient_id, p.full_name AS patient_name,
                   p.patient_id AS patient_identifier, r.template_id, t.name AS template_name,
                   r.report_date, r.status, r.is_reviewed, r.revision_number,
                   r.created_at, r.updated_at
            FROM reports r
            LEFT JOIN patients p ON r.patient_id = p.id
            LEFT JOIN examination_templates t ON r.template_id = t.id
            {where_sql}
            ORDER BY r.updated_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        res = []
        for r in rows:
            d = dict(r)
            d["is_reviewed"] = bool(d["is_reviewed"])
            res.append(d)
        return res

    @staticmethod
    def update(
        conn: sqlite3.Connection,
        report_uuid: str,
        data: Dict[str, Any],
        change_type: str = "MANUAL_EDIT",
        changed_by: str = "clinician"
    ) -> Dict[str, Any]:
        existing = ReportRepository.get_by_id(conn, report_uuid)
        if not existing:
            raise ValueError(f"Report '{report_uuid}' not found.")

        # Optimistic Concurrency check
        expected_rev = data.get("expected_revision_number")
        if expected_rev is not None and expected_rev != existing["revision_number"]:
            raise ValueError(
                f"Concurrency conflict: Report has revision {existing['revision_number']}, but client provided {expected_rev}."
            )

        now = datetime.now(timezone.utc).isoformat()
        new_rev = existing["revision_number"] + 1

        # Check if content changes on a REVIEWED report -> reverts to DRAFT
        new_status = existing["status"]
        is_reviewed = existing["is_reviewed"]
        reviewed_by = existing["reviewed_by"]
        reviewed_at = existing["reviewed_at"]

        content_keys = ["structured_findings", "impression", "edited_transcript", "report_date", "referral_doctor"]
        has_content_change = any(k in data and data[k] != existing.get(k) for k in content_keys)

        if existing["status"] == "REVIEWED" and has_content_change:
            # Clinical safety rule: Any edit to a reviewed report invalidates review and reverts to DRAFT
            new_status = "DRAFT"
            is_reviewed = False
            reviewed_by = None
            reviewed_at = None

        fields = [
            "updated_at = ?",
            "revision_number = ?",
            "status = ?",
            "is_reviewed = ?",
            "reviewed_by = ?",
            "reviewed_at = ?"
        ]
        values = [now, new_rev, new_status, 1 if is_reviewed else 0, reviewed_by, reviewed_at]

        if "report_date" in data and data["report_date"] is not None:
            fields.append("report_date = ?")
            values.append(data["report_date"])
        if "referral_doctor" in data:
            fields.append("referral_doctor = ?")
            values.append(data["referral_doctor"])
        if "original_transcript" in data and data["original_transcript"] is not None:
            fields.append("original_transcript = ?")
            values.append(data["original_transcript"])
        if "edited_transcript" in data and data["edited_transcript"] is not None:
            fields.append("edited_transcript = ?")
            values.append(data["edited_transcript"])
        if "structured_findings" in data and data["structured_findings"] is not None:
            fields.append("structured_findings = ?")
            values.append(json.dumps(data["structured_findings"]) if isinstance(data["structured_findings"], dict) else data["structured_findings"])
        if "impression" in data:
            fields.append("impression = ?")
            values.append(data["impression"])
        if "patient_id" in data:
            fields.append("patient_id = ?")
            values.append(data["patient_id"])
            if data["patient_id"]:
                p_row = conn.execute("SELECT * FROM patients WHERE id = ?", (data["patient_id"],)).fetchone()
                if p_row:
                    snapshot = {
                        "id": p_row["id"], "patient_id": p_row["patient_id"],
                        "full_name": p_row["full_name"], "age_years": p_row["age_years"],
                        "gender": p_row["gender"], "contact_number": p_row["contact_number"]
                    }
                    fields.append("patient_snapshot = ?")
                    values.append(json.dumps(snapshot))

        values.append(report_uuid)
        conn.execute(f"UPDATE reports SET {', '.join(fields)} WHERE id = ?", values)

        updated_report = ReportRepository.get_by_id(conn, report_uuid)
        ReportRepository._create_revision(
            conn, report_uuid, new_rev, change_type, updated_report, is_reviewed=is_reviewed, changed_by=changed_by
        )
        return updated_report

    @staticmethod
    def mark_reviewed(
        conn: sqlite3.Connection,
        report_uuid: str,
        reviewed_by: str,
        acknowledge_unresolved: bool = False
    ) -> Dict[str, Any]:
        existing = ReportRepository.get_by_id(conn, report_uuid)
        if not existing:
            raise ValueError(f"Report '{report_uuid}' not found.")

        # Check for unresolved unassigned findings (must be resolved or explicitly excluded with reason)
        findings = existing.get("structured_findings") or {}
        unassigned = findings.get("unassigned_findings") or []
        unresolved = [
            u for u in unassigned
            if not (
                u.get("is_resolved", False)
                and (
                    u.get("resolved_organ_key")
                    or (u.get("is_excluded", False) and (u.get("exclusion_reason") or "").strip())
                )
            )
        ]
        if unresolved:
            raise ValueError(
                f"Report contains {len(unresolved)} unresolved clinical finding(s). "
                "Each finding must be assigned to an anatomical section or explicitly excluded with a documented reason before final review."
            )

        now = datetime.now(timezone.utc).isoformat()
        new_rev = existing["revision_number"] + 1

        conn.execute(
            """
            UPDATE reports SET
                status = 'REVIEWED',
                is_reviewed = 1,
                reviewed_by = ?,
                reviewed_at = ?,
                revision_number = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (reviewed_by.strip(), now, new_rev, now, report_uuid)
        )

        updated_report = ReportRepository.get_by_id(conn, report_uuid)
        ReportRepository._create_revision(
            conn, report_uuid, new_rev, "REVIEW", updated_report, is_reviewed=True, changed_by=reviewed_by.strip()
        )
        return updated_report

    @staticmethod
    def revert_to_draft(conn: sqlite3.Connection, report_uuid: str) -> Dict[str, Any]:
        existing = ReportRepository.get_by_id(conn, report_uuid)
        if not existing:
            raise ValueError(f"Report '{report_uuid}' not found.")

        now = datetime.now(timezone.utc).isoformat()
        new_rev = existing["revision_number"] + 1

        conn.execute(
            """
            UPDATE reports SET
                status = 'DRAFT',
                is_reviewed = 0,
                reviewed_by = NULL,
                reviewed_at = NULL,
                revision_number = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (new_rev, now, report_uuid)
        )

        updated_report = ReportRepository.get_by_id(conn, report_uuid)
        ReportRepository._create_revision(conn, report_uuid, new_rev, "UNREVIEW", updated_report, is_reviewed=False)
        return updated_report

    @staticmethod
    def delete(conn: sqlite3.Connection, report_uuid: str) -> bool:
        res = conn.execute("DELETE FROM reports WHERE id = ?", (report_uuid,))
        return res.rowcount > 0

    @staticmethod
    def get_revisions(conn: sqlite3.Connection, report_uuid: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT * FROM report_revisions
            WHERE report_id = ?
            ORDER BY revision_number DESC
            """,
            (report_uuid,)
        ).fetchall()
        res = []
        for r in rows:
            d = dict(r)
            d["report_snapshot"] = json.loads(d["report_snapshot"])
            d["is_reviewed"] = bool(d["is_reviewed"])
            res.append(d)
        return res

    @staticmethod
    def _create_revision(
        conn: sqlite3.Connection,
        report_uuid: str,
        revision_number: int,
        change_type: str,
        report_snapshot: Dict[str, Any],
        is_reviewed: bool = False,
        changed_by: str = "clinician"
    ):
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO report_revisions (
                id, report_id, revision_number, change_type, report_snapshot, changed_by, is_reviewed, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                report_uuid,
                revision_number,
                change_type,
                json.dumps(report_snapshot),
                changed_by or "clinician",
                1 if is_reviewed else 0,
                now
            )
        )
