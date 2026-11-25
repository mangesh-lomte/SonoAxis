import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Union, List

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SONOVOICE_",
        env_file=".env",
        extra="ignore"
    )

    APP_NAME: str = "SonoAxis Clinical Ultrasound Suite"
    VERSION: str = "0.5.0"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = False

    # Base Paths (Configurable, project-relative by default)
    BASE_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    MODELS_DIR: str = os.path.join(BASE_DIR, "models", "whisper")
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    AUDIO_DIR: str = os.path.join(BASE_DIR, "data", "audio")
    DATABASE_PATH: str = os.path.join(BASE_DIR, "data", "sonovoice.db")
    BACKUP_DIR: str = os.path.join(BASE_DIR, "data", "backups")

    # Speech Recognition Settings
    DEFAULT_MODEL: str = "base.en"  # "base.en" or "small.en"
    DEVICE: str = "cpu"             # "cuda" or "cpu"
    COMPUTE_TYPE: str = "int8"      # "int8" for CPU, "float16" for GPU
    CPU_THREADS: int = 4
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = [".wav", ".mp3", ".m4a", ".webm", ".ogg"]
    AUDIO_RETENTION_DAYS: int = 30

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on", "debug")
        return bool(v)

settings = Settings()

# Ensure directories exist
os.makedirs(settings.MODELS_DIR, exist_ok=True)
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.AUDIO_DIR, exist_ok=True)
os.makedirs(settings.BACKUP_DIR, exist_ok=True)
