import uuid
import sqlite3
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

class PatientRepository:
    @staticmethod
    def create(conn: sqlite3.Connection, data: Dict[str, Any]) -> Dict[str, Any]:
        patient_uuid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # Check duplicate patient_id (e.g. MRN)
        existing = conn.execute(
            "SELECT id FROM patients WHERE patient_id = ?",
            (data["patient_id"],)
        ).fetchone()
        if existing:
            raise ValueError(f"Patient with ID '{data['patient_id']}' already exists.")

        conn.execute(
            """
            INSERT INTO patients (
                id, patient_id, full_name, age_years, gender, contact_number, clinical_notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient_uuid,
                data["patient_id"].strip(),
                data["full_name"].strip(),
                data.get("age_years"),
                data.get("gender"),
                data.get("contact_number"),
                data.get("clinical_notes"),
                now,
                now
            )
        )
        return PatientRepository.get_by_id(conn, patient_uuid)

    @staticmethod
    def get_by_id(conn: sqlite3.Connection, patient_uuid: str) -> Optional[Dict[str, Any]]:
        row = conn.execute(
            """
            SELECT p.*, (SELECT COUNT(*) FROM reports WHERE patient_id = p.id) AS report_count
            FROM patients p
            WHERE p.id = ?
            """,
            (patient_uuid,)
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_by_identifier(conn: sqlite3.Connection, patient_id: str) -> Optional[Dict[str, Any]]:
        row = conn.execute(
            """
            SELECT p.*, (SELECT COUNT(*) FROM reports WHERE patient_id = p.id) AS report_count
            FROM patients p
            WHERE p.patient_id = ?
            """,
            (patient_id,)
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def search(conn: sqlite3.Connection, query: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if query and query.strip():
            param = f"%{query.strip()}%"
            rows = conn.execute(
                """
                SELECT p.*, (SELECT COUNT(*) FROM reports WHERE patient_id = p.id) AS report_count
                FROM patients p
                WHERE p.patient_id LIKE ? OR p.full_name LIKE ?
                ORDER BY p.updated_at DESC
                LIMIT ?
                """,
                (param, param, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT p.*, (SELECT COUNT(*) FROM reports WHERE patient_id = p.id) AS report_count
                FROM patients p
                ORDER BY p.updated_at DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def update(conn: sqlite3.Connection, patient_uuid: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        existing = PatientRepository.get_by_id(conn, patient_uuid)
        if not existing:
            return None

        # If updating patient_id, verify uniqueness
        if "patient_id" in data and data["patient_id"] != existing["patient_id"]:
            dup = conn.execute(
                "SELECT id FROM patients WHERE patient_id = ? AND id != ?",
                (data["patient_id"], patient_uuid)
            ).fetchone()
            if dup:
                raise ValueError(f"Patient ID '{data['patient_id']}' is already in use by another patient.")

        now = datetime.now(timezone.utc).isoformat()
        fields = []
        values = []
        for k in ["patient_id", "full_name", "age_years", "gender", "contact_number", "clinical_notes"]:
            if k in data and data[k] is not None:
                fields.append(f"{k} = ?")
                values.append(data[k])

        if fields:
            fields.append("updated_at = ?")
            values.append(now)
            values.append(patient_uuid)
            conn.execute(
                f"UPDATE patients SET {', '.join(fields)} WHERE id = ?",
                values
            )

        return PatientRepository.get_by_id(conn, patient_uuid)

    @staticmethod
    def delete(conn: sqlite3.Connection, patient_uuid: str, force: bool = False) -> bool:
        # Check associated reports to prevent accidental data loss
        count_row = conn.execute("SELECT COUNT(*) FROM reports WHERE patient_id = ?", (patient_uuid,)).fetchone()
        report_count = count_row[0] if count_row else 0
        if report_count > 0 and not force:
            raise ValueError(f"Cannot delete patient with {report_count} associated report(s). Remove or reassign reports first.")

        res = conn.execute("DELETE FROM patients WHERE id = ?", (patient_uuid,))
        return res.rowcount > 0
