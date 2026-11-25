from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from backend.app.schemas.structuring import StructuredReport

class ReportCreate(BaseModel):
    template_id: str = Field(..., description="'usg-abdomen-pelvis-male' or 'usg-abdomen-pelvis-female'")
    patient_id: Optional[str] = None
    report_date: Optional[str] = None
    referral_doctor: Optional[str] = None

class ReportUpdate(BaseModel):
    report_date: Optional[str] = None
    referral_doctor: Optional[str] = None
    patient_id: Optional[str] = None
    original_transcript: Optional[str] = None
    edited_transcript: Optional[str] = None
    structured_findings: Optional[Dict[str, Any]] = None
    impression: Optional[str] = None
    recordings: Optional[List[Dict[str, Any]]] = None
    expected_revision_number: Optional[int] = Field(None, description="Current revision number for optimistic concurrency lock")

class ReportListItem(BaseModel):
    id: str
    report_number: Optional[str] = None
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    patient_identifier: Optional[str] = None
    template_id: str
    template_name: str
    report_date: str
    status: str
    is_reviewed: bool
    revision_number: int
    created_at: str
    updated_at: str

class ReportResponse(BaseModel):
    id: str
    patient_id: Optional[str] = None
    template_id: str
    template_name: str
    report_number: Optional[str] = None
    report_date: str
    referral_doctor: Optional[str] = None
    status: str  # "DRAFT" or "REVIEWED"
    patient_snapshot: Optional[Dict[str, Any]] = None
    original_transcript: Optional[str] = None
    edited_transcript: Optional[str] = None
    structured_findings: Optional[Dict[str, Any]] = None
    impression: Optional[str] = None
    recordings: List[Dict[str, Any]] = Field(default_factory=list)
    revision_number: int
    is_reviewed: bool
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    created_at: str
    updated_at: str

class ReportReviewRequest(BaseModel):
    reviewed_by: str = Field(..., min_length=1, description="Clinician / Radiologist name performing review")
    acknowledge_unresolved: bool = Field(False, description="Explicit confirmation if unresolved unassigned findings remain")
