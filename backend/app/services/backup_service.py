import os
import sqlite3
import shutil
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from backend.app.core.config import settings
from backend.app.db.connection import get_db, configure_connection

logger = logging.getLogger("sonovoice.backup")

class BackupService:
    @staticmethod
    def create_backup(
        source_db_path: Optional[str] = None,
        backup_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates an online, transactional SQLite backup using SQLite's native backup API.
        Guarantees zero database locking or corruption during backup.
        """
        src_path = source_db_path or settings.DATABASE_PATH
        target_dir = backup_dir or settings.BACKUP_DIR
        os.makedirs(target_dir, exist_ok=True)

        if not os.path.exists(src_path):
            raise FileNotFoundError(f"Source database '{src_path}' does not exist.")

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_filename = f"sonovoice_backup_{timestamp_str}.db"
        backup_path = os.path.join(target_dir, backup_filename)

        # Execute native SQLite backup
        src_conn = sqlite3.connect(src_path)
        dest_conn = sqlite3.connect(backup_path)
        try:
            with dest_conn:
                src_conn.backup(dest_conn, pages=100)
        finally:
            dest_conn.close()
            src_conn.close()

        # Verify integrity of the newly created backup
        BackupService.verify_backup_integrity(backup_path)

        file_size = os.path.getsize(backup_path)
        return {
            "backup_filename": backup_filename,
            "backup_path": backup_path,
            "file_size": file_size,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "verified"
        }

    @staticmethod
    def verify_backup_integrity(backup_path: str) -> bool:
        """
        Runs PRAGMA integrity_check on the backup file to ensure zero page corruption.
        """
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file '{backup_path}' not found.")

        conn = sqlite3.connect(backup_path)
        try:
            cursor = conn.cursor()
            res = cursor.execute("PRAGMA integrity_check;").fetchall()
            if not res or res[0][0] != "ok":
                raise ValueError(f"Backup integrity check failed: {res}")
            return True
        finally:
            conn.close()

    @staticmethod
    def test_restore_to_temp(backup_path: str, temp_restore_path: str) -> Dict[str, Any]:
        """
        Verifies that a backup can be restored into an isolated temporary database
        without touching the live application database.
        Checks record counts to confirm recoverable state.
        """
        BackupService.verify_backup_integrity(backup_path)
        
        if os.path.exists(temp_restore_path):
            os.remove(temp_restore_path)

        # Restore from backup into target
        b_conn = sqlite3.connect(backup_path)
        r_conn = sqlite3.connect(temp_restore_path)
        try:
            with r_conn:
                b_conn.backup(r_conn)
        finally:
            b_conn.close()
            r_conn.close()

        # Query recovered tables
        check_conn = configure_connection(sqlite3.connect(temp_restore_path))
        try:
            patients_count = check_conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
            reports_count = check_conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
            templates_count = check_conn.execute("SELECT COUNT(*) FROM examination_templates").fetchone()[0]
            return {
                "restored_path": temp_restore_path,
                "status": "success",
                "patients_count": patients_count,
                "reports_count": reports_count,
                "templates_count": templates_count
            }
        finally:
            check_conn.close()

    @staticmethod
    def list_backups(backup_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        target_dir = backup_dir or settings.BACKUP_DIR
        if not os.path.exists(target_dir):
            return []

        backups = []
        for f in os.listdir(target_dir):
            if f.endswith(".db"):
                fpath = os.path.join(target_dir, f)
                stat = os.stat(fpath)
                backups.append({
                    "filename": f,
                    "path": fpath,
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
                })
        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return backups
