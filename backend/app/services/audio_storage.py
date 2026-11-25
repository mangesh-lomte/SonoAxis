import os
import time
import uuid
import logging
from typing import Optional, List, Dict, Any
from backend.app.core.config import settings
from backend.app.db.connection import get_db
from backend.app.db.repositories.audio_repo import AudioRepository

logger = logging.getLogger("sonovoice.audio")

class AudioStorageService:
    @staticmethod
    def save_audio_file(
        report_id: Optional[str],
        file_bytes: bytes,
        original_filename: str,
        duration_seconds: Optional[float] = None,
        transcription_model: Optional[str] = None,
        db_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Saves audio file with safe, generated UUID filename in settings.AUDIO_DIR.
        Validates size, extension, and prevents path traversal.
        """
        ext = os.path.splitext(original_filename)[1].lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported audio extension '{ext}'. Allowed: {settings.ALLOWED_EXTENSIONS}")

        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise ValueError(f"Audio file exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB")

        safe_filename = f"{uuid.uuid4().hex}{ext}"
        saved_path = os.path.join(settings.AUDIO_DIR, safe_filename)

        with open(saved_path, "wb") as f:
            f.write(file_bytes)

        record_data = {
            "report_id": report_id,
            "file_path": saved_path,
            "filename": safe_filename,
            "mime_type": f"audio/{ext.lstrip('.')}",
            "file_size": len(file_bytes),
            "duration_seconds": duration_seconds,
            "transcription_model": transcription_model or settings.DEFAULT_MODEL,
            "transcription_status": "completed",
            "retention_policy": "retain"
        }

        with get_db(db_path) as conn:
            return AudioRepository.create(conn, record_data)

    @staticmethod
    def get_audio_file_path(audio_id: str, db_path: Optional[str] = None) -> Optional[str]:
        with get_db(db_path) as conn:
            rec = AudioRepository.get_by_id(conn, audio_id)
            if not rec:
                return None
            path = rec["file_path"]
            # Path traversal safety check
            real_path = os.path.abspath(path)
            real_audio_dir = os.path.abspath(settings.AUDIO_DIR)
            if not real_path.startswith(real_audio_dir):
                raise PermissionError("Access denied: File outside designated audio directory.")
            return real_path if os.path.exists(real_path) else None

    @staticmethod
    def cleanup_old_audio(retention_days: int = 30, db_path: Optional[str] = None) -> int:
        """
        Removes audio files older than retention_days.
        """
        now = time.time()
        cutoff = now - (retention_days * 86400)
        cleaned = 0

        if not os.path.exists(settings.AUDIO_DIR):
            return 0

        for f in os.listdir(settings.AUDIO_DIR):
            fpath = os.path.join(settings.AUDIO_DIR, f)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                if stat.st_mtime < cutoff:
                    try:
                        os.remove(fpath)
                        cleaned += 1
                    except Exception as e:
                        logger.warning(f"Could not remove old audio {fpath}: {e}")
        return cleaned
