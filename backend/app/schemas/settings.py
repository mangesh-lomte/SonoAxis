from pydantic import BaseModel
from typing import Optional, Dict, Any

class AppSettingsResponse(BaseModel):
    settings: Dict[str, Any]

class AppSettingsUpdateRequest(BaseModel):
    settings: Dict[str, Any]
