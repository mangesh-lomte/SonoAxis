from pydantic import BaseModel
from typing import Optional, Dict, Any

class AudioRecordResponse(BaseModel):
    id: str
    report_id: Optional[str] = None
    filename: str
    file_size: Optional[int] = None
    duration_seconds: Optional[float] = None
    recorded_at: str
    transcription_model: Optional[str] = None
    transcription_status: str
