export type Gender = 'Male' | 'Female' | 'Other' | 'MALE' | 'FEMALE';
export type ReportStatus = 'DRAFT' | 'REVIEWED';

export interface Patient {
  id: string;
  patient_id: string;
  full_name: string;
  gender: string;
  age_years?: number | null;
  referral_doctor?: string | null;
  notes?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface PatientCreate {
  patient_id: string;
  full_name: string;
  gender: string;
  age_years?: number | null;
  referral_doctor?: string | null;
  notes?: string | null;
}

export interface MeasurementItem {
  raw_str: string;
  val_primary?: number | null;
  val_secondary?: number | null;
  val_tertiary?: number | null;
  value?: any;
  unit: string;
  dimension?: number;
  dimension_count: number;
  is_volume: boolean;
  computed_volume_cc?: number | null;
  flag_missing_unit?: boolean;
  audio_id?: string | null;
  audio_timestamp_start?: number | null;
  audio_timestamp_end?: number | null;
  source_type?: 'voice' | 'manual' | 'calculation' | 'preset' | string | null;
  calculation_formula?: string | null;
  preset_name?: string | null;
}

export interface SectionFinding {
  id?: string;
  organ_key?: string;
  raw_text?: string;
  source_text?: string;
  current_text?: string;
  is_normal?: boolean;
  is_negation?: boolean;
  audio_id?: string | null;
  audio_timestamp_start?: number | null;
  audio_timestamp_end?: number | null;
  source_type?: 'voice' | 'manual' | 'calculation' | 'preset' | string | null;
  preset_name?: string | null;
  measurements?: MeasurementItem[];
}

export interface ReportSection {
  key: string;
  label: string;
  is_present: boolean;
  text: string | null;
  measurements: MeasurementItem[];
  findings: SectionFinding[];
  calculated_biometry?: any | null;
  source_type?: 'voice' | 'manual' | 'calculation' | 'preset' | string | null;
  preset_name?: string | null;
}

export interface UnassignedFinding {
  id: string;
  raw_text: string;
  reason: string;
  measurements: MeasurementItem[];
  is_resolved: boolean;
  resolved_organ_key?: string | null;
  is_excluded?: boolean;
  exclusion_reason?: string | null;
}

export interface SupersededMeasurement {
  organ_key: string;
  measurement_type?: string | null;
  superseded_text: string;
  superseded_measurements?: MeasurementItem[];
  superseded_value?: number | null;
  active_value?: number | null;
  active_text?: string | null;
  active_measurements?: MeasurementItem[];
  correction_trigger?: string;
  reason?: string;
}

export interface IncompetentPerforatorItem {
  id?: string;
  laterality?: string | null;
  diameter_mm?: number | null;
  unit?: string;
  aspect?: string | null;
  landmark?: string | null;
  distance_cm?: number | string | null;
  raw_str?: string;
  raw_text?: string;
}

export interface ArterialSegmentBiometry {
  segment_key: string;
  segment_name: string;
  psv_right?: number | null;
  psv_left?: number | null;
  flow_pattern_right?: string | null;
  flow_pattern_left?: string | null;
}

export interface VascularBiometry {
  arterial_table?: ArterialSegmentBiometry[];
  incompetent_perforators?: IncompetentPerforatorItem[];
  clinical_profile?: string | null;
  recommendations?: string | null;
}

export interface StructuredFindings {
  sections: ReportSection[];
  impression: string | null;
  clinical_profile?: string | null;
  recommendations?: string | null;
  vascular_biometry?: VascularBiometry | null;
  category?: string;
  laterality?: string;
  unassigned_findings: UnassignedFinding[];
  superseded_history: SupersededMeasurement[];
  recordings?: any[];
  has_flags?: boolean;
  all_flags?: string[];
  processing_time_ms?: number;
}

export interface Report {
  id: string;
  patient_id: string | null;
  template_id: string;
  report_number: string;
  report_date: string;
  referral_doctor?: string | null;
  status: ReportStatus;
  category?: string;
  laterality?: string;
  patient_snapshot?: Patient | null;
  patient_name?: string | null;
  original_transcript?: string | null;
  edited_transcript?: string | null;
  structured_findings?: StructuredFindings | null;
  impression?: string | null;
  clinical_profile?: string | null;
  recommendations?: string | null;
  vascular_biometry?: VascularBiometry | null;
  recordings?: any[];
  revision_number: number;
  is_reviewed: boolean;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  created_at: string;
  updated_at: string;
  template_name?: string;
}

export interface PresetItem {
  id: string;
  section_key: string;
  name: string;
  category: string;
  text: string;
  clinical_rationale: string;
}

export interface AnatomicalChecklistItem {
  key: string;
  label: string;
  description: string;
  status: 'not_documented' | 'dictated' | 'typed_transcript' | 'uploaded_audio' | 'manually_entered' | 'preset_applied' | 'ocr_verified' | 'requires_review';
  is_present: boolean;
  source_type?: string | null;
  summary_text?: string | null;
}

export interface ReportListItem {
  id: string;
  report_number: string;
  patient_id: string | null;
  patient_name?: string | null;
  template_id: string;
  template_name?: string;
  status: ReportStatus;
  report_date: string;
  revision_number: number;
  is_reviewed: boolean;
  updated_at: string;
}

export interface Revision {
  id: string;
  report_id: string;
  revision_number: number;
  change_type: string;
  snapshot: any;
  changed_by: string;
  is_reviewed: boolean;
  created_at: string;
}

export interface TemplateDef {
  id: string;
  name: string;
  gender: string;
  category?: string;
  laterality?: string;
  file_name?: string | null;
  version?: number;
  status?: string; // "APPROVED", "DRAFT_CONFIG", "ARCHIVED"
  table_type?: string;
  sections: { order: number; key: string; label: string; heading: string }[];
  incompatible_organs?: string[];
  is_built_in?: boolean;
  is_shared?: boolean;
  created_by_user_id?: string | null;
  created_by_name?: string | null;
  section_count?: number;
  approved_by?: string | null;
  approved_at?: string | null;
  created_at?: string;
}

export interface DocStructureResponse {
  file_name: string;
  paragraphs_count: number;
  tables_count: number;
  detected_headings: string[];
  detected_placeholders: string[];
  tables_summary: any[];
  suggested_sections: { order: number; key: string; label: string; heading: string }[];
  suggested_category: string;
  suggested_laterality: string;
}

export interface EngineStatus {
  engine: string;
  active_model?: string | null;
  device: string;
  compute_type: string;
  available_models: { name: string; size: string; status: string; path: string }[];
}

export type DoctorRole = 'Radiologist' | 'Administrator';

export interface DoctorUser {
  id: string;
  username: string;
  full_name: string;
  display_name: string;
  credentials?: string | null;
  designation?: string | null;
  role: DoctorRole;
  department?: string | null;
  email?: string | null;
  is_active: boolean;
  is_demo?: boolean;
  created_at: string;
  last_login_at?: string | null;
}

export interface LoginResponse {
  access_token: string;
  csrf_token?: string;
  token_type: string;
  user: DoctorUser;
}

export interface DashboardStats {
  today_reports: number;
  total_reports: number;
  draft_reports: number;
  reviewed_reports: number;
  total_patients: number;
  recent_reports: ReportListItem[];
  recent_patients: Patient[];
}

export interface ExportStatus {
  docx_export: boolean;
  pdf_export: boolean;
  pdf_engine: string;
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface OCRRegionBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  confidence: number;
  detection_method: string;
}

export interface OCRAssignableField {
  field_key: string;
  section_key: string;
  label: string;
  laterality?: string | null;
  default_unit: string;
}

export interface OCRCandidateMeasurement {
  measurement_id: string;
  source_document_id: string;
  raw_text: string;
  anatomical_label: string;
  specificity?: string | null;
  value: number | number[];
  dimension: number;
  original_unit: string;
  normalized_unit: string;
  laterality?: string | null;
  proposed_destination_field: string;
  bounding_box?: BoundingBox | null;
  ocr_confidence?: number | null;
  mapping_confidence: number;
  is_uncertain: boolean;
  uncertainty_reason?: string | null;
  existing_value?: any;
  has_conflict: boolean;
  waveform?: string | null;
  location?: string | null;
  source_zone?: string;
  is_duplicate_annotation?: boolean;
  verification_status: 'pending' | 'approved' | 'rejected' | string;
}

export interface OCRUploadResponse {
  source_document_id: string;
  filename: string;
  image_url: string;
  image_width: number;
  image_height: number;
  candidates: OCRCandidateMeasurement[];
  preprocessing_applied: string[];
  execution_time_ms: number;
  raw_ocr_text?: string;
  ocr_mode_used?: string;
  detected_region?: OCRRegionBox | null;
  filtered_duplicate_count?: number;
  available_target_fields?: OCRAssignableField[];
}

export interface OCRConfirmationItem {
  measurement_id: string;
  destination_field: string;
  anatomical_label: string;
  value: number | number[];
  unit: string;
  dimension: number;
  laterality?: string | null;
  waveform?: string | null;
  location?: string | null;
  conflict_resolution?: 'use_extracted' | 'keep_existing' | 'edit_manually' | 'leave_unresolved';
  manual_edit_note?: string | null;
  status: 'approved' | 'rejected' | 'pending';
}

export interface OCRConfirmRequest {
  source_document_id: string;
  items: OCRConfirmationItem[];
}
