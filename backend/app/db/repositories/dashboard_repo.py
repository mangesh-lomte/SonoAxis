import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List

class DashboardRepository:
    @staticmethod
    def get_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
        today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        total_reports = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        total_patients = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        today_reports = conn.execute(
            "SELECT COUNT(*) FROM reports WHERE report_date = ? OR date(created_at) = ?",
            (today_date, today_date)
        ).fetchone()[0]
        draft_reports = conn.execute("SELECT COUNT(*) FROM reports WHERE status = 'DRAFT'").fetchone()[0]
        reviewed_reports = conn.execute("SELECT COUNT(*) FROM reports WHERE status = 'REVIEWED'").fetchone()[0]

        # Recent Reports
        recent_rows = conn.execute(
            """
            SELECT r.id, r.report_number, r.patient_id, p.full_name AS patient_name,
                   p.patient_id AS patient_identifier, r.template_id, t.name AS template_name,
                   r.report_date, r.status, r.is_reviewed, r.revision_number,
                   r.created_at, r.updated_at
            FROM reports r
            LEFT JOIN patients p ON r.patient_id = p.id
            LEFT JOIN examination_templates t ON r.template_id = t.id
            ORDER BY r.updated_at DESC
            LIMIT 5
            """
        ).fetchall()
        recent_reports = [dict(r) for r in recent_rows]

        # Recent Patients
        recent_patient_rows = conn.execute(
            """
            SELECT p.id, p.patient_id, p.full_name, p.age_years, p.gender, p.created_at,
                   (SELECT COUNT(*) FROM reports WHERE patient_id = p.id) AS report_count
            FROM patients p
            ORDER BY p.updated_at DESC
            LIMIT 5
            """
        ).fetchall()
        recent_patients = [dict(r) for r in recent_patient_rows]

        # Template Distribution
        dist_rows = conn.execute(
            "SELECT template_id, COUNT(*) FROM reports GROUP BY template_id"
        ).fetchall()
        template_distribution = {r[0]: r[1] for r in dist_rows}

        return {
            "today_reports": today_reports,
            "total_reports": total_reports,
            "draft_reports": draft_reports,
            "reviewed_reports": reviewed_reports,
            "total_patients": total_patients,
            "recent_reports": recent_reports,
            "recent_patients": recent_patients,
            "template_distribution": template_distribution
        }
