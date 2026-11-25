import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional, Dict, Any

class SettingsRepository:
    @staticmethod
    def get_all(conn: sqlite3.Connection) -> Dict[str, Any]:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
        res = {}
        for r in rows:
            try:
                res[r["key"]] = json.loads(r["value"])
            except Exception:
                res[r["key"]] = r["value"]
        return res

    @staticmethod
    def get(conn: sqlite3.Connection, key: str, default: Any = None) -> Any:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except Exception:
            return row["value"]

    @staticmethod
    def set(conn: sqlite3.Connection, key: str, value: Any, description: Optional[str] = None):
        now = datetime.now(timezone.utc).isoformat()
        val_str = json.dumps(value)
        conn.execute(
            """
            INSERT INTO app_settings (key, value, description, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                description = COALESCE(excluded.description, app_settings.description),
                updated_at = excluded.updated_at
            """,
            (key, val_str, description, now)
        )
