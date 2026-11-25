import os
import uuid
import hmac
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Query, Depends, Request, Response as FastAPIResponse
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.services.auth_service import (
    AuthService,
    SESSION_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    SESSION_TTL_SECONDS,
    RateLimitError,
)
from backend.app.schemas.auth import (
    LoginRequest, LoginResponse, UserProfileResponse,
    UserCreateRequest, UserUpdateRequest, ProfileUpdateRequest, ChangePasswordRequest
)
from backend.app.services.speech_service import SpeechRecognitionService
from backend.app.services.patient_service import PatientService
from backend.app.services.report_service import ReportService
from backend.app.services.audio_storage import AudioStorageService
from backend.app.services.backup_service import BackupService
from backend.app.export.word_service import WordExportService
from backend.app.export.pdf_service import PDFExportService
from backend.app.export.preview_service import PreviewService
from backend.app.db.connection import get_db
from backend.app.db.repositories.dashboard_repo import DashboardRepository
from backend.app.db.repositories.settings_repo import SettingsRepository

from backend.app.schemas.patient import PatientCreate, PatientUpdate, PatientResponse
from backend.app.schemas.report import (
    ReportCreate, ReportUpdate, ReportResponse, ReportListItem, ReportReviewRequest
)
from datetime import datetime, timezone
from backend.app.schemas.revision import RevisionResponse
from backend.app.schemas.ocr import OCRUploadResponse, OCRConfirmRequest
from backend.app.ocr.engine import ocr_engine
from backend.app.schemas.dashboard import DashboardStatsResponse
from backend.app.schemas.audio import AudioRecordResponse
from backend.app.schemas.settings import AppSettingsResponse, AppSettingsUpdateRequest
from backend.app.schemas.structuring import (
    StructuringRequest, StructuredReport, ManualAssignmentRequest,
    ExcludeUnassignedRequest, ValidationRequest
)
from backend.app.structuring.templates import TEMPLATES_CATALOG, get_template_def
from backend.app.structuring.engine import structuring_engine
from backend.app.structuring.calculations import recalculate_report_calculations
from backend.app.structuring.checklist import generate_anatomical_checklist
from backend.app.structuring.presets import NORMAL_PRESETS_CATALOG, get_presets_for_category, get_preset_for_section
from backend.app.db.repositories.audio_repo import AudioRepository

logger = logging.getLogger("sonovoice.api")
public_router = APIRouter(prefix="/api")

speech_service = SpeechRecognitionService.get_instance()


def _extract_auth_credentials(request: Request) -> tuple[Optional[str], bool]:
    """Returns (token, used_cookie_auth)."""
    auth_header = request.headers.get("Authorization") or ""
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip(), False
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_token:
        return cookie_token.strip(), True
    return None, False


def require_authenticated_session(request: Request) -> Dict[str, Any]:
    token, used_cookie = _extract_auth_credentials(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in with your doctor credentials.",
        )

    session_info = AuthService.get_session_and_user_by_token(token)
    if not session_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please sign in again.",
        )

    user, expected_csrf = session_info

    # Enforce CSRF validation on cookie-authenticated state-changing requests
    if used_cookie and request.method in ("POST", "PUT", "PATCH", "DELETE"):
        header_csrf = request.headers.get("X-CSRF-Token") or ""
        if not expected_csrf or not hmac.compare_digest(header_csrf, expected_csrf):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF verification failed.",
            )

    return user


# Backwards-compatible alias names for explicit route dependencies
require_current_user = require_authenticated_session


def require_admin_user(current_user: Dict[str, Any] = Depends(require_authenticated_session)) -> Dict[str, Any]:
    if current_user.get("role") != "Administrator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required for this action.",
        )
    return current_user


def require_radiologist_user(current_user: Dict[str, Any] = Depends(require_authenticated_session)) -> Dict[str, Any]:
    if current_user.get("role") != "Radiologist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authorized Radiologist accounts may finalize or revert clinical report reviews.",
        )
    return current_user


# Protected API router: EVERY clinical and administrative route requires authentication
router = APIRouter(prefix="/api", dependencies=[Depends(require_authenticated_session)])


# ================= PUBLIC ENDPOINTS (LOGIN / LOGOUT / NON-SENSITIVE HEALTH) =================

@public_router.post("/auth/login", response_model=LoginResponse)
def login_doctor(req: LoginRequest, request: Request, response: FastAPIResponse):
    client_ip = request.client.host if request.client else "local"
    try:
        token, csrf_token, user = AuthService.authenticate_and_create_session(
            req.username,
            req.password,
            client_ip=client_ip,
        )
    except RateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers={"Retry-After": "300"},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=SESSION_TTL_SECONDS,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        samesite="lax",
        path="/",
        max_age=SESSION_TTL_SECONDS,
    )
    return LoginResponse(access_token=token, csrf_token=csrf_token, user=UserProfileResponse(**user))


@public_router.post("/auth/logout")
def logout_doctor(request: Request, response: FastAPIResponse):
    token, _ = _extract_auth_credentials(request)
    AuthService.revoke_session(token)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/")
    return {"logged_out": True}


@router.get("/auth/me", response_model=UserProfileResponse)
def get_authenticated_profile(current_user: Dict[str, Any] = Depends(require_authenticated_session)):
    return UserProfileResponse(**current_user)


@router.put("/auth/profile", response_model=UserProfileResponse)
def update_own_profile(
    req: ProfileUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_authenticated_session),
):
    updated = AuthService.update_user(current_user["id"], req.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="User account not found.")
    return UserProfileResponse(**updated)


@router.post("/auth/change-password")
def change_own_password(
    req: ChangePasswordRequest,
    response: FastAPIResponse,
    current_user: Dict[str, Any] = Depends(require_authenticated_session),
):
    try:
        AuthService.change_password(current_user["id"], req.current_password, req.new_password)
        response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
        response.delete_cookie(key=CSRF_COOKIE_NAME, path="/")
        return {"changed": True}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/auth/users", response_model=List[UserProfileResponse])
def list_doctor_accounts(_: Dict[str, Any] = Depends(require_admin_user)):
    return [UserProfileResponse(**u) for u in AuthService.list_users()]


@router.post("/auth/users", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
def create_doctor_account(
    req: UserCreateRequest,
    _: Dict[str, Any] = Depends(require_admin_user),
):
    try:
        user = AuthService.create_user(req.model_dump())
        return UserProfileResponse(**user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/auth/users/{user_id}", response_model=UserProfileResponse)
def update_doctor_account(
    user_id: str,
    req: UserUpdateRequest,
    _: Dict[str, Any] = Depends(require_admin_user),
):
    try:
        updated = AuthService.update_user(user_id, req.model_dump(exclude_unset=True))
        if not updated:
            raise HTTPException(status_code=404, detail="Doctor account not found.")
        return UserProfileResponse(**updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ================= HEALTH & ENGINE STATUS =================

class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str

class EngineStatusResponse(BaseModel):
    engine: str
    active_model: Optional[str]
    device: str
    compute_type: str
    available_models: List[Dict[str, Any]]

@public_router.get("/health", response_model=HealthResponse)
def get_health():
    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        version=settings.VERSION,
    )

@router.get("/engine/status", response_model=EngineStatusResponse)
def get_engine_status():
    models = speech_service.get_available_models()
    return EngineStatusResponse(
        engine="Faster-Whisper (CTranslate2)",
        active_model=speech_service._loaded_model_name,
        device=speech_service._active_device,
        compute_type=speech_service._active_compute_type,
        available_models=models
    )

@router.get("/engine/models")
def list_models():
    return {"models": speech_service.get_available_models()}

# ================= AUDIO TRANSCRIPTION =================

@router.post("/audio/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    model_name: Optional[str] = Form(None),
    word_timestamps: bool = Form(True)
):
    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Allowed: {settings.ALLOWED_EXTENSIONS}"
        )

    safe_filename = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(settings.AUDIO_DIR, safe_filename)

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    total_bytes = 0
    try:
        with open(saved_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    buffer.close()
                    if os.path.exists(saved_path):
                        os.remove(saved_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Audio file exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB"
                    )
                buffer.write(chunk)
    except Exception as e:
        if os.path.exists(saved_path):
            os.remove(saved_path)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to save audio file: {e}")

    try:
        result = speech_service.transcribe(
            audio_path=saved_path,
            model_name=model_name,
            word_timestamps=word_timestamps
        )
        result["file_id"] = safe_filename
        return result
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

# ================= PATIENT MANAGEMENT =================

@router.post("/patients", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def create_patient(req: PatientCreate):
    try:
        return PatientService.create_patient(req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating patient: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create patient: {e}")

@router.get("/patients", response_model=List[PatientResponse])
def search_patients(
    query: Optional[str] = Query(None, description="Search by name or patient ID"),
    limit: int = Query(50, ge=1, le=200)
):
    return PatientService.search_patients(query, limit)

@router.get("/patients/{patient_id}", response_model=PatientResponse)
def get_patient(patient_id: str):
    p = PatientService.get_patient(patient_id)
    if not p:
        p = PatientService.get_patient_by_identifier(patient_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found.")
    return p

@router.put("/patients/{patient_id}", response_model=PatientResponse)
def update_patient(patient_id: str, req: PatientUpdate):
    try:
        updated = PatientService.update_patient(patient_id, req.model_dump(exclude_unset=True))
        if not updated:
            raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found.")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/patients/{patient_id}")
def delete_patient(patient_id: str, force: bool = Query(False, description="Force delete even if reports exist")):
    try:
        deleted = PatientService.delete_patient(patient_id, force)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found.")
        return {"deleted": True, "patient_id": patient_id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

@router.get("/patients/{patient_id}/reports", response_model=List[ReportListItem])
def list_patient_reports(patient_id: str):
    p = PatientService.get_patient(patient_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found.")
    return ReportService.list_reports(patient_id=p["id"])

# ================= REPORT MANAGEMENT =================

@router.post("/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    req: ReportCreate,
    current_user: Dict[str, Any] = Depends(require_authenticated_session),
):
    tpl = TemplateService.get_template(req.template_id)
    if tpl:
        _authorize_template_access(tpl, current_user)
    try:
        return ReportService.create_report(req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/reports", response_model=List[ReportListItem])
def list_reports(
    status: Optional[str] = Query(None, description="Filter by 'DRAFT' or 'REVIEWED'"),
    template_id: Optional[str] = Query(None, description="Filter by template ID"),
    patient_id: Optional[str] = Query(None),
    query: Optional[str] = Query(None, description="Search by report number or patient name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    return ReportService.list_reports(status, template_id, patient_id, query, limit, offset)

@router.get("/reports/{report_id}", response_model=ReportResponse)
def get_report(report_id: str):
    r = ReportService.get_report(report_id)
    if not r:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
    return r

@router.put("/reports/{report_id}", response_model=ReportResponse)
def update_report(report_id: str, req: ReportUpdate, current_user: Dict[str, Any] = Depends(require_authenticated_session)):
    try:
        changed_by = current_user["display_name"]
        return ReportService.update_report(report_id, req.model_dump(exclude_unset=True), changed_by=changed_by)
    except ValueError as e:
        if "Concurrency conflict" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/reports/{report_id}")
def delete_report(report_id: str):
    deleted = ReportService.delete_report(report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
    return {"deleted": True, "report_id": report_id}

@router.get("/reports/{report_id}/revisions", response_model=List[RevisionResponse])
def get_report_revisions(report_id: str):
    return ReportService.get_revisions(report_id)

@router.post("/reports/{report_id}/review", response_model=ReportResponse)
def review_report(
    report_id: str,
    req: ReportReviewRequest,
    current_user: Dict[str, Any] = Depends(require_radiologist_user),
):
    try:
        # Enforce authenticated Radiologist attribution cleanly
        return ReportService.mark_reviewed(
            report_id=report_id,
            reviewed_by=current_user["display_name"],
            acknowledge_unresolved=req.acknowledge_unresolved
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/reports/{report_id}/revert-draft", response_model=ReportResponse)
def revert_report_to_draft(
    report_id: str,
    _: Dict[str, Any] = Depends(require_radiologist_user),
):
    try:
        return ReportService.revert_to_draft(report_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/reports/{report_id}/assign-unassigned", response_model=ReportResponse)
def assign_report_unassigned_finding(
    report_id: str,
    req: ManualAssignmentRequest,
    current_user: Dict[str, Any] = Depends(require_authenticated_session),
):
    try:
        return ReportService.assign_unassigned_finding(
            report_id=report_id,
            unassigned_id=req.unassigned_id,
            target_organ_key=req.target_organ_key,
            custom_text=req.custom_text,
            changed_by=current_user["display_name"],
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e).strip("'\""))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/reports/{report_id}/exclude-unassigned", response_model=ReportResponse)
def exclude_report_unassigned_finding(
    report_id: str,
    req: ExcludeUnassignedRequest,
    current_user: Dict[str, Any] = Depends(require_authenticated_session),
):
    try:
        return ReportService.exclude_unassigned_finding(
            report_id=report_id,
            unassigned_id=req.unassigned_id,
            exclusion_reason=req.exclusion_reason,
            changed_by=current_user["display_name"],
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e).strip("'\""))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# ================= REPORT AUDIO & STRUCTURING WORKFLOW =================

@router.post("/reports/{report_id}/audio", response_model=ReportResponse)
async def attach_and_transcribe_audio(
    report_id: str,
    file: UploadFile = File(...),
    model_name: Optional[str] = Form(None)
):
    # 1. Verify report exists
    rep = ReportService.get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")

    # 2. Read bytes
    content = await file.read()
    filename = file.filename or "audio.wav"

    # 3. Save audio file locally
    try:
        audio_rec = AudioStorageService.save_audio_file(
            report_id=report_id,
            file_bytes=content,
            original_filename=filename,
            transcription_model=model_name or settings.DEFAULT_MODEL
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 4. Transcribe using Faster-Whisper
    transcription = speech_service.transcribe(
        audio_path=audio_rec["file_path"],
        model_name=model_name,
        word_timestamps=True
    )
    transcript_text = transcription["transcript"]

    # 5. Update transcripts without modifying structured findings (Decoupled clinical workflow: Audio -> Transcript -> Manual review -> Explicit Structuring)
    update_data = {
        "original_transcript": transcript_text if not rep.get("original_transcript") else rep["original_transcript"],
        "edited_transcript": transcript_text
    }
    updated_rep = ReportService.update_report(
        report_id=report_id,
        data=update_data,
        change_type="AUDIO_DICTATION"
    )
    return updated_rep

class StructureReportRequest(BaseModel):
    transcript_text: str
    force_regenerate: bool = False
    transcript_source: Optional[str] = None

@router.post("/reports/{report_id}/structure", response_model=ReportResponse)
def structure_report_transcript(report_id: str, req: StructureReportRequest):
    try:
        return ReportService.structure_and_save_report(
            report_id=report_id,
            transcript_text=req.transcript_text,
            force_regenerate=req.force_regenerate,
            transcript_source=req.transcript_source
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/audio/{audio_id}")
def stream_audio_file(audio_id: str):
    try:
        path = AudioStorageService.get_audio_file_path(audio_id)
        if not path:
            raise HTTPException(status_code=404, detail="Audio file not found.")
        return FileResponse(path, media_type="audio/wav")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

# ================= MULTI-RECORDING & ADVANCED STRUCTURING =================

class ApplyPresetRequest(BaseModel):
    section_key: str
    preset_name: Optional[str] = None

class RemovePresetRequest(BaseModel):
    section_key: str

@router.post("/reports/{report_id}/recordings", response_model=ReportResponse)
async def add_additional_recording(
    report_id: str,
    file: UploadFile = File(...),
    model_name: Optional[str] = Form(None)
):
    rep = ReportService.get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
    if rep.get("is_reviewed"):
        raise HTTPException(status_code=400, detail="Cannot attach recording to a finalized/reviewed report.")

    content = await file.read()
    filename = file.filename or "recording.wav"

    try:
        audio_rec = AudioStorageService.save_audio_file(
            report_id=report_id,
            file_bytes=content,
            original_filename=filename,
            transcription_model=model_name or settings.DEFAULT_MODEL
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    transcription = speech_service.transcribe(
        audio_path=audio_rec["file_path"],
        model_name=model_name,
        word_timestamps=True
    )
    new_transcript = transcription.get("transcript", "")
    segments = transcription.get("segments", [])
    duration = transcription.get("duration", 0.0)

    # Update audio record duration if available
    with get_db() as conn:
        conn.execute("UPDATE audio_recordings SET duration_seconds = ? WHERE id = ?", (duration, audio_rec["id"]))

    # Merge into structured findings
    existing_structured = rep.get("structured_findings")
    template_id = rep["template_id"]
    rec_source = "recorded_voice" if ("dictation" in filename.lower() or "additional_recording" in filename.lower()) else "uploaded_audio"
    merged_structured = structuring_engine.structure_transcript(
        transcript=new_transcript,
        template_id=template_id,
        audio_segments=segments,
        audio_id=audio_rec["id"],
        prior_report=existing_structured,
        transcript_source=rec_source
    )

    prev_transcript = rep.get("edited_transcript") or rep.get("original_transcript") or ""
    rec_count = len(merged_structured.recordings) if merged_structured.recordings else 1
    updated_transcript = f"{prev_transcript}\n\n[Recording {rec_count}]: {new_transcript}".strip() if prev_transcript else new_transcript

    update_data = {
        "edited_transcript": updated_transcript,
        "structured_findings": merged_structured.model_dump(),
        "impression": merged_structured.impression or rep.get("impression")
    }

    updated_rep = ReportService.update_report(
        report_id=report_id,
        data=update_data,
        change_type="ADD_RECORDING"
    )
    return updated_rep

@router.get("/reports/{report_id}/recordings")
def list_report_recordings(report_id: str):
    with get_db() as conn:
        recs = AudioRepository.get_by_report_id(conn, report_id)
        return recs

@router.get("/structuring/presets")
def get_presets(category: Optional[str] = Query(None)):
    if category:
        return get_presets_for_category(category)
    return NORMAL_PRESETS_CATALOG

@router.post("/reports/{report_id}/apply-preset", response_model=ReportResponse)
def apply_section_preset(report_id: str, req: ApplyPresetRequest):
    rep = ReportService.get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
    if rep.get("is_reviewed"):
        raise HTTPException(status_code=400, detail="Cannot modify reviewed report.")

    preset = get_preset_for_section(req.section_key)
    if not preset:
        raise HTTPException(status_code=404, detail=f"No preset found for section '{req.section_key}'.")

    structured = rep.get("structured_findings") or {}
    sections = structured.get("sections") or []

    found = False
    for sec in sections:
        if sec.get("key") == req.section_key:
            sec["is_present"] = True
            sec["text"] = preset["text"]
            sec["preset_name"] = preset["name"]
            sec["source_type"] = "preset"
            sec["findings"] = [{
                "id": str(uuid.uuid4()),
                "organ_key": req.section_key,
                "source_text": preset["text"],
                "current_text": preset["text"],
                "measurements": [],
                "assignment_status": "confidently_assigned",
                "source_type": "preset",
                "preset_name": preset["name"]
            }]
            found = True
            break

    if not found:
        raise HTTPException(status_code=400, detail=f"Section '{req.section_key}' does not exist in report template.")

    update_data = {
        "structured_findings": structured
    }
    return ReportService.update_report(report_id, update_data, change_type="APPLY_PRESET")

@router.post("/reports/{report_id}/remove-preset", response_model=ReportResponse)
def remove_section_preset(report_id: str, req: RemovePresetRequest):
    rep = ReportService.get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
    if rep.get("is_reviewed"):
        raise HTTPException(status_code=400, detail="Cannot modify reviewed report.")

    structured = rep.get("structured_findings") or {}
    sections = structured.get("sections") or []

    for sec in sections:
        if sec.get("key") == req.section_key:
            non_preset_findings = [f for f in sec.get("findings", []) if f.get("source_type") != "preset"]
            if non_preset_findings:
                sec["findings"] = non_preset_findings
                sec["text"] = ". ".join(f.get("current_text", "") for f in non_preset_findings)
                sec["source_type"] = non_preset_findings[0].get("source_type", "voice")
                sec["preset_name"] = None
            else:
                sec["findings"] = []
                sec["text"] = None
                sec["is_present"] = False
                sec["preset_name"] = None
                sec["source_type"] = None
            break

    update_data = {
        "structured_findings": structured
    }
    return ReportService.update_report(report_id, update_data, change_type="REMOVE_PRESET")

@router.get("/structuring/checklist/{report_id}")
def get_report_checklist(report_id: str):
    rep = ReportService.get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")

    structured = rep.get("structured_findings") or {}
    sections = structured.get("sections") or []
    t_def = get_template_def(rep["template_id"])
    category = t_def.get("category", "abdomen_pelvis")
    template_gender = t_def.get("gender", "Any")

    checklist = generate_anatomical_checklist(category, sections, template_gender=template_gender)
    return {
        "report_id": report_id,
        "category": category,
        "items": checklist
    }

@router.post("/reports/{report_id}/recalculate", response_model=ReportResponse)
def recalculate_report(report_id: str):
    rep = ReportService.get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
    if rep.get("is_reviewed"):
        raise HTTPException(status_code=400, detail="Cannot modify reviewed report.")

    structured = rep.get("structured_findings") or {}
    recalc_data = recalculate_report_calculations(structured)

    update_data = {
        "structured_findings": recalc_data
    }
    return ReportService.update_report(report_id, update_data, change_type="RECALCULATE")

# ================= OCR & MACHINE PRINTOUT MEASUREMENT EXTRACTION =================

@router.post("/reports/{report_id}/ocr/upload", response_model=OCRUploadResponse)
async def upload_machine_printout(
    report_id: str,
    file: UploadFile = File(...),
    rotate: int = Form(0),
    mode: str = Form("auto"),
    crop_x1: Optional[int] = Form(None),
    crop_y1: Optional[int] = Form(None),
    crop_x2: Optional[int] = Form(None),
    crop_y2: Optional[int] = Form(None)
):
    rep = ReportService.get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
    if rep.get("is_reviewed"):
        raise HTTPException(status_code=400, detail="Cannot upload measurements for a reviewed report.")

    crop_box = None
    if all(v is not None for v in [crop_x1, crop_y1, crop_x2, crop_y2]):
        crop_box = (crop_x1, crop_y1, crop_x2, crop_y2)

    ocr_mode = mode if mode in ("auto", "region", "full") else "auto"

    content = await file.read()
    try:
        structured = rep.get("structured_findings") or {}
        existing_sections = structured.get("sections")
        response = ocr_engine.process_and_extract(
            report_id=report_id,
            filename=file.filename or "printout.png",
            file_bytes=content,
            rotate_degrees=rotate,
            crop_box=crop_box,
            existing_sections=existing_sections,
            ocr_mode=ocr_mode
        )
        return response
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"OCR processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"OCR extraction failed: {str(e)}")

@router.get("/reports/{report_id}/ocr/images/{filename}")
def get_ocr_image(report_id: str, filename: str):
    clean_report_id = os.path.basename(report_id)
    clean_filename = os.path.basename(filename)
    base_dir = os.path.abspath("D:/sovoice/data/ocr_uploads")
    file_path = os.path.abspath(os.path.join(base_dir, clean_report_id, clean_filename))
    if not file_path.startswith(base_dir) or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="OCR image not found.")
    return FileResponse(file_path)

@router.post("/reports/{report_id}/ocr/confirm", response_model=ReportResponse)
def confirm_ocr_measurements(report_id: str, req: OCRConfirmRequest):
    rep = ReportService.get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
    if rep.get("is_reviewed"):
        raise HTTPException(status_code=400, detail="Cannot modify reviewed report.")

    structured = rep.get("structured_findings") or {}
    sections = structured.get("sections") or []

    # Map of destination field or key to section
    sec_by_key = {s.get("key"): s for s in sections}

    # Track changes for audit history
    correction_history = structured.get("correction_history") or []
    updated_sections_in_batch: set[str] = set()

    # Sub-dimension / alias destination key resolution -> canonical template section key
    field_to_section = {
        "gb_wall": "gall_bladder",
        "rk_length": "right_kidney",
        "rk_ap": "right_kidney",
        "lk_length": "left_kidney",
        "lk_ap": "left_kidney",
        "prostate_volume": "prostate",
        "pvr": "urinary_bladder",
    }

    for item in req.items:
        # Strict clinical verification guard: never insert pending or rejected items
        if item.status != "approved":
            continue

        target_field = (item.destination_field or "").strip()
        if not target_field or target_field in ("unassigned", "kidneys_ambiguous") or item.conflict_resolution == "leave_unresolved":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot insert unresolved or unassigned measurement '{item.anatomical_label}'. Assign an explicit anatomical field or reject it before confirmation."
            )

        resolved_field = field_to_section.get(target_field, target_field)

        # Find matching section
        target_sec = None
        for k, s in sec_by_key.items():
            if k == resolved_field or resolved_field.startswith(f"{k}_") or resolved_field in k:
                target_sec = s
                break

        # Fallback: match by anatomical label against section label/key
        if not target_sec:
            for k, s in sec_by_key.items():
                if item.anatomical_label.lower() in k.lower() or k.lower() in item.anatomical_label.lower():
                    target_sec = s
                    break

        if not target_sec:
            raise HTTPException(
                status_code=400,
                detail=f"Target clinical section for '{item.anatomical_label}' ({target_field}) was not found in this report template."
            )

        # Value string format
        if isinstance(item.value, list):
            val_str = " x ".join(str(v) for v in item.value) + f" {item.unit}"
        else:
            val_str = f"{item.value} {item.unit}"

        # Conflict resolution check
        source_type = "ocr_manually_corrected" if item.conflict_resolution == "edit_manually" else "ocr_verified"

        if target_sec:
            sec_key = target_sec.get("key")
            old_text = target_sec.get("text")

            # Add structured measurement
            meas_item = {
                "value": item.value,
                "unit": item.unit,
                "dimension": item.dimension,
                "raw_str": val_str,
                "source_type": source_type,
                "source_document_id": req.source_document_id
            }

            if sec_key in updated_sections_in_batch:
                # Merge secondary measurement (e.g. RK AP + RK Length, or Prostate Vol) without overwriting the first
                existing_meas = target_sec.get("measurements") or []
                existing_meas.append(meas_item)
                target_sec["measurements"] = existing_meas
                extra_txt = f"{item.anatomical_label} measures {val_str}."
                target_sec["text"] = f"{old_text} {extra_txt}".strip() if old_text else extra_txt
                existing_findings = target_sec.get("findings") or []
                existing_findings.append({
                    "current_text": extra_txt,
                    "source_type": source_type,
                    "measurements": [meas_item]
                })
                target_sec["findings"] = existing_findings
                continue

            # Log in correction history if overwriting pre-existing value
            if old_text and item.conflict_resolution == "use_extracted":
                correction_history.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "ocr_import",
                    "section_key": sec_key,
                    "superseded_value": old_text,
                    "new_value": f"{item.anatomical_label} measures {val_str}.",
                    "source_document_id": req.source_document_id
                })

            new_finding_text = f"{item.anatomical_label} measures {val_str}."
            if item.waveform:
                new_finding_text += f" Waveform shows {item.waveform} flow."

            target_sec["text"] = new_finding_text
            target_sec["is_present"] = True
            target_sec["source_type"] = source_type
            target_sec["measurements"] = [meas_item]
            target_sec["findings"] = [{
                "current_text": new_finding_text,
                "source_type": source_type,
                "measurements": [meas_item]
            }]
            updated_sections_in_batch.add(sec_key)

    structured["correction_history"] = correction_history

    # Recalculate calculations (prostate volume, uterine volume, carotid ratio, ABI)
    recalculated = recalculate_report_calculations(structured)

    update_data = {
        "structured_findings": recalculated
    }
    return ReportService.update_report(report_id, update_data, change_type="OCR_MEASUREMENT_CONFIRMATION")


# ================= EXPORT & PREVIEW =================

@router.get("/exports/status")
def get_export_status():
    pdf_ready = PDFExportService.is_available()
    return {
        "docx_export": True,
        "pdf_export": pdf_ready,
        "pdf_engine": "Microsoft Edge Headless" if pdf_ready else "Unavailable"
    }

@router.get("/reports/{report_id}/preview")
def preview_report(report_id: str, format: str = Query("html", description="'html' or 'json'")):
    rep = ReportService.get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
    
    html_content = PreviewService.render_html(rep)
    if format == "json":
        return {"report_id": report_id, "html": html_content}
    return HTMLResponse(content=html_content, status_code=200)

@router.get("/reports/{report_id}/export/docx")
def export_report_docx(report_id: str):
    rep = ReportService.get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
    
    try:
        docx_bytes = WordExportService.generate_docx(rep)
        rep_num = rep.get("report_number") or f"report-{report_id[:8]}"
        filename = f"{rep_num}.docx"
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"DOCX export error for report {report_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate Word document: {str(e)}")

@router.get("/reports/{report_id}/export/pdf")
def export_report_pdf(report_id: str):
    rep = ReportService.get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
    
    try:
        pdf_bytes = PDFExportService.generate_pdf(rep)
        rep_num = rep.get("report_number") or f"report-{report_id[:8]}"
        filename = f"{rep_num}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"PDF export error for report {report_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF document: {str(e)}")

# ================= TEMPLATES MANAGEMENT =================

from backend.app.services.template_service import TemplateService
from backend.app.schemas.template import (
    TemplateResponse, TemplateConfigUpdate, TemplateApproveRequest, DocStructureResponse
)

def _authorize_template_access(tpl: TemplateResponse, current_user: Dict[str, Any]) -> None:
    if tpl.is_built_in or tpl.is_shared or current_user.get("role") == "Administrator":
        return
    if tpl.created_by_user_id != current_user.get("id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: this custom template belongs to another clinician.",
        )


def _authorize_template_mutation(
    tpl: TemplateResponse,
    current_user: Dict[str, Any],
    action: str = "modify",
) -> None:
    if tpl.is_built_in:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Original institutional templates are protected and cannot be modified, archived, or deleted.",
        )
    if current_user.get("role") == "Administrator":
        return
    if tpl.is_shared or tpl.created_by_user_id != current_user.get("id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Permission denied: only an Administrator can {action} shared templates "
                "or templates created by another clinician."
            ),
        )


@router.get("/templates", response_model=List[TemplateResponse])
def list_templates(
    category: Optional[str] = Query(None, description="Category filter"),
    laterality: Optional[str] = Query(None, description="Laterality filter"),
    status: Optional[str] = Query(None, description="Status filter: APPROVED, DRAFT_CONFIG, ARCHIVED"),
    query: Optional[str] = Query(None, description="Search term"),
    only_approved: bool = Query(False, description="Filter only approved templates"),
    current_user: Dict[str, Any] = Depends(require_authenticated_session),
):
    return TemplateService.list_templates(
        category=category,
        laterality=laterality,
        status=status,
        query=query,
        only_approved=only_approved,
        viewer_user_id=current_user["id"],
        viewer_role=current_user["role"],
    )

@router.get("/templates/{template_id}", response_model=TemplateResponse)
def get_template(
    template_id: str,
    current_user: Dict[str, Any] = Depends(require_authenticated_session),
):
    tpl = TemplateService.get_template(template_id)
    if not tpl:
        # Fallback to get_template_def
        t_def = get_template_def(template_id)
        if t_def and t_def.get("id") == template_id:
            return TemplateResponse(
                id=t_def["id"],
                name=t_def["name"],
                gender=t_def.get("gender", "Any"),
                category=t_def.get("category", "abdomen_pelvis"),
                laterality=t_def.get("laterality", "not_applicable"),
                file_name=t_def.get("file_name"),
                status="APPROVED",
                table_type=t_def.get("table_type", "none"),
                sections=t_def.get("sections", []),
                created_at="2026-11-24T00:00:00Z",
                is_built_in=True,
                is_shared=True,
                section_count=len(t_def.get("sections", []))
            )
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    _authorize_template_access(tpl, current_user)
    return tpl

@router.get("/templates/{template_id}/preview")
def preview_template(
    template_id: str,
    current_user: Dict[str, Any] = Depends(require_authenticated_session),
):
    tpl = TemplateService.get_template(template_id)
    if tpl:
        _authorize_template_access(tpl, current_user)
    try:
        html_out = TemplateService.render_template_preview_html(template_id)
        return HTMLResponse(content=html_out, status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/templates/import", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def import_single_template(
    file: UploadFile = File(...),
    custom_name: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    current_user: Dict[str, Any] = Depends(require_authenticated_session),
):
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only Microsoft Word (.docx) files are supported.")
    try:
        content = await file.read()
        tpl = TemplateService.import_template(
            file_bytes=content,
            filename=file.filename,
            custom_name=custom_name,
            category=category,
            created_by_user_id=current_user["id"],
            created_by_name=current_user["display_name"],
            is_shared=(current_user.get("role") == "Administrator"),
        )
        return tpl
    except ValueError as e:
        logger.warning(f"Template import rejected: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Template import error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to import template: {str(e)}")

@router.post("/templates/bulk-import", response_model=List[TemplateResponse], status_code=status.HTTP_201_CREATED)
async def import_bulk_templates(
    files: List[UploadFile] = File(...),
    current_user: Dict[str, Any] = Depends(require_authenticated_session),
):
    imported = []
    errors = []
    for f in files:
        if not f.filename.lower().endswith(".docx"):
            errors.append(f"{f.filename}: not a .docx file")
            continue
        try:
            content = await f.read()
            tpl = TemplateService.import_template(
                file_bytes=content,
                filename=f.filename,
                created_by_user_id=current_user["id"],
                created_by_name=current_user["display_name"],
                is_shared=(current_user.get("role") == "Administrator"),
            )
            imported.append(tpl)
        except Exception as e:
            errors.append(f"{f.filename}: {str(e)}")
    if not imported and errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    return imported

@router.post("/templates/extract-structure", response_model=DocStructureResponse)
async def extract_template_structure(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only Microsoft Word (.docx) files are supported.")
    try:
        content = await file.read()
        return TemplateService.extract_docx_structure(content, file.filename)
    except ValueError as e:
        logger.warning(f"Structure extraction rejected: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Structure extraction error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to extract structure: {str(e)}")

@router.put("/templates/{template_id}", response_model=TemplateResponse)
def update_template_configuration(
    template_id: str,
    req: TemplateConfigUpdate,
    current_user: Dict[str, Any] = Depends(require_authenticated_session),
):
    tpl = TemplateService.get_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found.")
    _authorize_template_mutation(tpl, current_user, action="configure")
    try:
        return TemplateService.configure_template(template_id, req)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Configure error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to configure template: {str(e)}")

@router.post("/templates/{template_id}/approve", response_model=TemplateResponse)
def approve_template(
    template_id: str,
    req: TemplateApproveRequest,
    current_user: Dict[str, Any] = Depends(require_authenticated_session),
):
    tpl = TemplateService.get_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found.")
    _authorize_template_mutation(tpl, current_user, action="approve")
    try:
        is_admin = current_user.get("role") == "Administrator"
        return TemplateService.approve_template(
            template_id,
            approved_by=current_user["display_name"] or req.approved_by,
            mark_shared=True if is_admin else False,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Approval error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to approve template: {str(e)}")

@router.post("/templates/{template_id}/archive", response_model=TemplateResponse)
def archive_template(
    template_id: str,
    current_user: Dict[str, Any] = Depends(require_authenticated_session),
):
    tpl = TemplateService.get_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found.")
    _authorize_template_mutation(tpl, current_user, action="archive")
    try:
        return TemplateService.archive_template(template_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Archive error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to archive template: {str(e)}")

@router.post("/templates/{template_id}/version", response_model=TemplateResponse)
def increment_template_version(
    template_id: str,
    current_user: Dict[str, Any] = Depends(require_authenticated_session),
):
    tpl = TemplateService.get_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found.")
    _authorize_template_mutation(tpl, current_user, action="version")
    try:
        return TemplateService.version_template(template_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Versioning error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to version template: {str(e)}")

# ================= TEMPLATES =================

@router.get("/structuring/templates")
def list_structuring_templates(category: Optional[str] = None, all: bool = Query(False, description="Include all multi-protocol templates")):
    if all or category:
        templates = [
            {"id": k, "name": v["name"], "gender": v.get("gender", "Any"), "category": v.get("category", "abdomen_pelvis"), "section_count": len(v["sections"])}
            for k, v in TEMPLATES_CATALOG.items()
            if not category or v.get("category") == category
        ]
    else:
        # Default backward-compatible view: Abdomen & Pelvis templates (Male & Female)
        templates = [
            {"id": k, "name": v["name"], "gender": v.get("gender", "Any"), "category": v.get("category", "abdomen_pelvis"), "section_count": len(v["sections"])}
            for k, v in TEMPLATES_CATALOG.items()
            if v.get("category", "abdomen_pelvis") == "abdomen_pelvis"
        ]
    return {"templates": templates}

@router.get("/structuring/templates/{template_id}")
def get_template_definition(template_id: str):
    t_def = get_template_def(template_id)
    if not t_def:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return t_def

@router.post("/structuring/process", response_model=StructuredReport)
def process_structuring(req: StructuringRequest):
    try:
        report = structuring_engine.structure_transcript(
            transcript=req.transcript,
            template_id=req.template_id,
            audio_segments=req.audio_segments
        )
        return report
    except Exception as e:
        logger.error(f"Structuring error: {e}")
        raise HTTPException(status_code=500, detail=f"Structuring failed: {str(e)}")

@router.post("/structuring/assign-unassigned")
def assign_unassigned_finding(req: ManualAssignmentRequest, report: StructuredReport):
    try:
        return ReportService.apply_unassigned_assignment(
            report.model_dump(),
            unassigned_id=req.unassigned_id,
            target_organ_key=req.target_organ_key,
            custom_text=req.custom_text,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).strip("'\""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/structuring/validate")
def validate_report(req: ValidationRequest):
    r = req.report
    warnings = []
    
    active_count = sum(1 for s in r.sections if s.is_present)
    if active_count == 0 and not r.impression:
        warnings.append("Report is completely blank. No anatomical findings or impression.")

    unresolved_count = sum(1 for u in r.unassigned_findings if not u.is_resolved)
    if unresolved_count > 0:
        warnings.append(f"{unresolved_count} unassigned finding(s) require review or manual assignment.")

    missing_units = []
    for s in r.sections:
        for m in s.measurements:
            if m.flag_missing_unit:
                missing_units.append(f"{s.label}: '{m.raw_str}' is missing measurement unit.")
    warnings.extend(missing_units)

    return {
        "is_valid": len(warnings) == 0,
        "active_section_count": active_count,
        "warnings": warnings
    }

# ================= DASHBOARD & STATISTICS =================

@router.get("/dashboard/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats():
    with get_db() as conn:
        return DashboardRepository.get_stats(conn)

# ================= APP SETTINGS =================

@router.get("/settings", response_model=AppSettingsResponse)
def get_settings():
    with get_db() as conn:
        all_s = SettingsRepository.get_all(conn)
        return AppSettingsResponse(settings=all_s)

@router.put("/settings", response_model=AppSettingsResponse)
def update_settings(req: AppSettingsUpdateRequest, _: Dict[str, Any] = Depends(require_admin_user)):
    with get_db() as conn:
        for k, v in req.settings.items():
            SettingsRepository.set(conn, k, v)
        all_s = SettingsRepository.get_all(conn)
        return AppSettingsResponse(settings=all_s)

# ================= BACKUP & RECOVERY =================

@router.post("/backups")
def create_backup(_: Dict[str, Any] = Depends(require_admin_user)):
    try:
        res = BackupService.create_backup()
        return res
    except Exception as e:
        logger.error(f"Backup creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Backup creation failed: {e}")

@router.get("/backups")
def list_backups(_: Dict[str, Any] = Depends(require_admin_user)):
    return {"backups": BackupService.list_backups()}

@router.post("/backups/test-restore")
def test_restore_backup(
    filename: str = Query(..., description="Backup filename to test restore"),
    _: Dict[str, Any] = Depends(require_admin_user),
):
    target_path = os.path.join(settings.BACKUP_DIR, filename)
    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="Backup file not found.")

    temp_db_path = os.path.join(settings.BACKUP_DIR, f"temp_restore_{uuid.uuid4().hex[:8]}.db")
    try:
        res = BackupService.test_restore_to_temp(target_path, temp_db_path)
        return res
    except Exception as e:
        logger.error(f"Test restore failed: {e}")
        raise HTTPException(status_code=500, detail=f"Restore verification failed: {e}")
    finally:
        if os.path.exists(temp_db_path):
            try:
                os.remove(temp_db_path)
            except Exception:
                pass
