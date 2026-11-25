from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from backend.app.schemas.report import ReportListItem

class DashboardStatsResponse(BaseModel):
    today_reports: int
    total_reports: int
    draft_reports: int
    reviewed_reports: int
    total_patients: int = 0
    recent_reports: List[ReportListItem]
    recent_patients: List[Dict[str, Any]]
    template_distribution: Dict[str, int]
