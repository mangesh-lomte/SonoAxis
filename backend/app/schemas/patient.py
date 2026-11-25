from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class PatientBase(BaseModel):
    patient_id: str = Field(..., description="Unique medical record number or hospital ID", min_length=1, max_length=64)
    full_name: str = Field(..., description="Patient's full name", min_length=1, max_length=128)
    age_years: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[str] = Field(None, description="'Male' or 'Female'")
    contact_number: Optional[str] = None
    clinical_notes: Optional[str] = None

class PatientCreate(PatientBase):
    pass

class PatientUpdate(BaseModel):
    patient_id: Optional[str] = Field(None, min_length=1, max_length=64)
    full_name: Optional[str] = Field(None, min_length=1, max_length=128)
    age_years: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[str] = None
    contact_number: Optional[str] = None
    clinical_notes: Optional[str] = None

class PatientResponse(PatientBase):
    id: str
    created_at: str
    updated_at: str
    report_count: int = 0
