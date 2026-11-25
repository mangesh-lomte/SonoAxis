import uuid
import sqlite3
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

class AudioRepository:
    @staticmethod
    def create(conn: sqlite3.Connection, data: Dict[str, Any]) -> Dict[str, Any]:
        audio_uuid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO audio_recordings (
                id, report_id, file_path, filename, mime_type, file_size,
                duration_seconds, recorded_at, transcription_model, transcription_status, retention_policy
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audio_uuid,
                data.get("report_id"),
                data["file_path"],
                data["filename"],
                data.get("mime_type", "audio/wav"),
                data.get("file_size"),
                data.get("duration_seconds"),
                now,
                data.get("transcription_model", "small.en"),
                data.get("transcription_status", "completed"),
                data.get("retention_policy", "retain")
            )
        )
        return AudioRepository.get_by_id(conn, audio_uuid)

    @staticmethod
    def get_by_id(conn: sqlite3.Connection, audio_uuid: str) -> Optional[Dict[str, Any]]:
        row = conn.execute("SELECT * FROM audio_recordings WHERE id = ?", (audio_uuid,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_by_report_id(conn: sqlite3.Connection, report_id: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            "SELECT * FROM audio_recordings WHERE report_id = ? ORDER BY recorded_at DESC",
            (report_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def delete(conn: sqlite3.Connection, audio_uuid: str) -> bool:
        res = conn.execute("DELETE FROM audio_recordings WHERE id = ?", (audio_uuid,))
        return res.rowcount > 0
