from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x: int = Field(..., description="Top-left X coordinate in pixels")
    y: int = Field(..., description="Top-left Y coordinate in pixels")
    width: int = Field(..., description="Width in pixels")
    height: int = Field(..., description="Height in pixels")


class OCRRegionBox(BaseModel):
    x1: int = Field(..., description="Top-left X pixel coordinate")
    y1: int = Field(..., description="Top-left Y pixel coordinate")
    x2: int = Field(..., description="Bottom-right X pixel coordinate")
    y2: int = Field(..., description="Bottom-right Y pixel coordinate")
    confidence: float = Field(1.0, description="Detection confidence")
    detection_method: str = Field("auto_table_grid", description="auto_table_grid or manual_selection")


class OCRAssignableField(BaseModel):
    field_key: str
    section_key: str
    label: str
    laterality: Optional[str] = None
    default_unit: str = "cm"


class OCRCandidateMeasurement(BaseModel):
    measurement_id: str = Field(..., description="Unique candidate ID")
    source_document_id: str = Field(..., description="ID of the uploaded printout")
    raw_text: str = Field(..., description="Original printed text line extracted by OCR")
    anatomical_label: str = Field(..., description="Identified anatomical structure or specific dimension")
    specificity: Optional[str] = Field(None, description="wall_thickness, length, ap_dimension, diameter, volume, post_void_residual, etc.")
    value: Union[float, List[float]] = Field(..., description="Parsed numeric value (single float or list for multi-D)")
    dimension: int = Field(1, description="1D, 2D, or 3D measurement")
    original_unit: str = Field(..., description="Unit printed on the machine image")
    normalized_unit: str = Field(..., description="Standardized clinical unit")
    laterality: Optional[str] = Field(None, description="right, left, bilateral, or None")
    proposed_destination_field: str = Field(..., description="Target clinical section or field key")
    bounding_box: Optional[BoundingBox] = Field(None, description="Pixel coordinates on the source image")
    ocr_confidence: Optional[float] = Field(None, description="OCR character recognition confidence (0.0 - 1.0)")
    mapping_confidence: float = Field(1.0, description="Confidence in anatomical label mapping (0.0 - 1.0)")
    is_uncertain: bool = Field(False, description="True if low OCR confidence, ambiguous label, or decimal uncertainty")
    uncertainty_reason: Optional[str] = Field(None, description="Explanation if uncertain")
    existing_value: Optional[Any] = Field(None, description="Existing value in report section if present")
    has_conflict: bool = Field(False, description="True if existing dictated or manual value differs from extracted value")
    waveform: Optional[str] = Field(None, description="For arterial Doppler: triphasic, biphasic, monophasic")
    location: Optional[str] = Field(None, description="For venous perforators: anatomical location")
    source_zone: str = Field("worksheet_table", description="worksheet_table, ultrasound_annotation, or full_image")
    is_duplicate_annotation: bool = Field(False, description="True if matching caliper annotation outside table")
    verification_status: str = Field("pending", description="pending, approved, rejected, modified")


class OCRUploadResponse(BaseModel):
    source_document_id: str
    filename: str
    image_url: str
    image_width: int
    image_height: int
    candidates: List[OCRCandidateMeasurement]
    preprocessing_applied: List[str]
    execution_time_ms: float
    raw_ocr_text: str = ""
    ocr_mode_used: str = Field("auto_table_region", description="auto_table_region, manual_region, or full_image")
    detected_region: Optional[OCRRegionBox] = None
    filtered_duplicate_count: int = 0
    available_target_fields: List[OCRAssignableField] = Field(default_factory=list)


class OCRConfirmationItem(BaseModel):
    measurement_id: str
    destination_field: str
    anatomical_label: str
    value: Union[float, List[float]]
    unit: str
    dimension: int = 1
    laterality: Optional[str] = None
    waveform: Optional[str] = None
    location: Optional[str] = None
    conflict_resolution: Optional[str] = Field("use_extracted", description="use_extracted, keep_existing, edit_manually, leave_unresolved")
    manual_edit_note: Optional[str] = None
    status: str = Field("approved", description="approved, rejected, pending")


class OCRConfirmRequest(BaseModel):
    source_document_id: str
    items: List[OCRConfirmationItem]
