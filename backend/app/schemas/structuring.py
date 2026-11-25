from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union

class MeasurementItem(BaseModel):
    value: Union[float, List[float]]
    unit: Optional[str] = None
    dimension: int = 1  # 1D, 2D, or 3D
    raw_str: str
    is_calculated: bool = False
    flag_missing_unit: bool = False
    flag_unusual_value: bool = False
    audio_id: Optional[str] = None
    audio_timestamp_start: Optional[float] = None
    audio_timestamp_end: Optional[float] = None
    source_type: str = "voice"  # "voice", "manual", "calculation", "preset"
    calculation_formula: Optional[str] = None

class FindingItem(BaseModel):
    id: str
    organ_key: str
    source_text: str
    current_text: str
    measurements: List[MeasurementItem] = Field(default_factory=list)
    laterality: Optional[str] = None  # "right", "left", "bilateral", "midline", None
    is_negation: bool = False
    is_uncertain: bool = False
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    audio_id: Optional[str] = None
    audio_timestamp_start: Optional[float] = None
    audio_timestamp_end: Optional[float] = None
    assignment_status: str = "confidently_assigned"  # "confidently_assigned", "requires_review"
    review_flags: List[str] = Field(default_factory=list)
    source_type: str = "voice"  # "voice", "manual", "calculation", "preset", "template"
    preset_name: Optional[str] = None
    calculation_formula: Optional[str] = None

class SupersededFinding(BaseModel):
    organ_key: str
    superseded_text: str
    superseded_measurements: List[MeasurementItem] = Field(default_factory=list)
    active_text: Optional[str] = None
    active_measurements: List[MeasurementItem] = Field(default_factory=list)
    correction_trigger: str
    reason: str

class UnassignedFinding(BaseModel):
    id: str
    raw_text: str
    reason: str  # e.g., "no_organ_identified", "incompatible_anatomy", "ambiguous_target"
    suggested_organs: List[str] = Field(default_factory=list)
    measurements: List[MeasurementItem] = Field(default_factory=list)
    is_resolved: bool = False
    resolved_organ_key: Optional[str] = None
    is_excluded: bool = False
    exclusion_reason: Optional[str] = None

class SectionOutput(BaseModel):
    order: int
    key: str
    label: str
    heading: str
    is_present: bool = False
    text: Optional[str] = None
    measurements: List[MeasurementItem] = Field(default_factory=list)
    calculated_biometry: Optional[Dict[str, Any]] = None
    findings: List[FindingItem] = Field(default_factory=list)
    source_type: Optional[str] = None
    preset_name: Optional[str] = None

class IncompetentPerforatorItem(BaseModel):
    id: str
    laterality: Optional[str] = None  # "right", "left", "bilateral"
    diameter_mm: float
    aspect: Optional[str] = None      # "medial", "lateral", "posterior", "anteromedial"
    landmark: Optional[str] = None    # "below knee", "above ankle", "mid-calf", "at ankle"
    distance_cm: Optional[float] = None
    raw_str: str

class ArterialSegmentBiometry(BaseModel):
    segment_key: str                  # "cfa", "sfa", "dfa", "popliteal", "ata", "pta", "dpa"
    segment_name: str                 # "Common femoral artery", etc.
    psv_right: Optional[float] = None
    psv_left: Optional[float] = None
    flow_pattern_right: Optional[str] = "Triphasic"
    flow_pattern_left: Optional[str] = "Triphasic"

class VascularBiometryOutput(BaseModel):
    arterial_table: List[ArterialSegmentBiometry] = Field(default_factory=list)
    incompetent_perforators: List[IncompetentPerforatorItem] = Field(default_factory=list)
    clinical_profile: Optional[str] = None
    recommendations: Optional[str] = None

class StructuredReport(BaseModel):
    template_id: str
    template_name: str = ""
    gender: str = "Any"
    category: str = "abdomen_pelvis"   # "abdomen_pelvis", "venous_doppler", "arterial_doppler", "arteriovenous_doppler"
    laterality: Optional[str] = None   # "right", "left", "bilateral", "not_applicable"
    raw_transcript: str = ""
    sections: List[SectionOutput]
    impression: Optional[str] = None
    clinical_profile: Optional[str] = None
    recommendations: Optional[str] = None
    vascular_biometry: Optional[VascularBiometryOutput] = None
    unassigned_findings: List[UnassignedFinding] = Field(default_factory=list)
    superseded_history: List[SupersededFinding] = Field(default_factory=list)
    processing_time_ms: float = 0.0
    has_flags: bool = False
    all_flags: List[str] = Field(default_factory=list)
    recordings: List[Dict[str, Any]] = Field(default_factory=list)

class StructuringRequest(BaseModel):
    transcript: str
    template_id: str = "usg-abdomen-pelvis-male"
    audio_segments: Optional[List[Dict[str, Any]]] = None
    audio_id: Optional[str] = None

class ManualAssignmentRequest(BaseModel):
    unassigned_id: str
    target_organ_key: str
    custom_text: Optional[str] = None

class ExcludeUnassignedRequest(BaseModel):
    unassigned_id: str
    exclusion_reason: str = Field(..., min_length=3, description="Documented clinical reason for excluding finding")

class ValidationRequest(BaseModel):
    report: StructuredReport
