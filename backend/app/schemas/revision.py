from pydantic import BaseModel
from typing import Optional, Dict, Any

class RevisionResponse(BaseModel):
    id: str
    report_id: str
    revision_number: int
    change_type: str
    changed_by: str
    is_reviewed: bool
    created_at: str
    report_snapshot: Dict[str, Any]
