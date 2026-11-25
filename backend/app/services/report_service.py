import copy
import os
import re
import uuid
from typing import Optional, List, Dict, Any
from backend.app.db.connection import get_db
from backend.app.db.repositories.report_repo import ReportRepository
from backend.app.db.repositories.audio_repo import AudioRepository
from backend.app.structuring.engine import structuring_engine


def _norm_clause(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _append_sentence(existing: Optional[str], addition: str) -> str:
    clean_add = addition.strip().rstrip(".")
    if not clean_add:
        return (existing or "").strip()
    base = (existing or "").strip()
    if not base:
        return f"{clean_add}."
    if _norm_clause(clean_add) in _norm_clause(base):
        return base if base.endswith((".", "!", "?")) else f"{base}."
    if not base.endswith((".", "!", "?")):
        base += "."
    return f"{base} {clean_add}."

class ReportService:
    @staticmethod
    def create_report(data: Dict[str, Any], db_path: Optional[str] = None) -> Dict[str, Any]:
        with get_db(db_path) as conn:
            return ReportRepository.create(conn, data)

    @staticmethod
    def get_report(report_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with get_db(db_path) as conn:
            return ReportRepository.get_by_id(conn, report_id)

    @staticmethod
    def list_reports(
        status: Optional[str] = None,
        template_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        db_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        with get_db(db_path) as conn:
            return ReportRepository.list_reports(conn, status, template_id, patient_id, query, limit, offset)

    @staticmethod
    def update_report(
        report_id: str,
        data: Dict[str, Any],
        change_type: str = "MANUAL_EDIT",
        expected_revision_number: Optional[int] = None,
        db_path: Optional[str] = None,
        changed_by: str = "clinician"
    ) -> Dict[str, Any]:
        with get_db(db_path) as conn:
            if expected_revision_number is not None and "expected_revision_number" not in data:
                data["expected_revision_number"] = expected_revision_number
            return ReportRepository.update(conn, report_id, data, change_type, changed_by=changed_by)

    @staticmethod
    def structure_and_save_report(
        report_id: str,
        transcript_text: str,
        audio_segments: Optional[List[Dict[str, Any]]] = None,
        force_regenerate: bool = False,
        db_path: Optional[str] = None,
        transcript_source: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Runs the deterministic structuring engine on transcript_text and persists
        the canonical structured findings into the report with revision tracking.
        """
        with get_db(db_path) as conn:
            existing = ReportRepository.get_by_id(conn, report_id)
            if not existing:
                raise ValueError(f"Report '{report_id}' not found.")

            # Determine accurate source attribution
            resolved_source = transcript_source
            if not resolved_source:
                recs = existing.get("recordings") or []
                if not recs:
                    resolved_source = "typed_transcript"
                else:
                    last_rec = recs[-1]
                    fname = (last_rec.get("filename") or "").lower()
                    if "dictation" in fname or "recording" in fname:
                        resolved_source = "recorded_voice"
                    else:
                        resolved_source = "uploaded_audio"

            # Check if existing report has manual edits
            has_manual_edits = existing.get("edited_transcript") or (
                existing.get("structured_findings") and any(
                    s.get("is_present") for s in existing["structured_findings"].get("sections", [])
                )
            )
            if has_manual_edits and not force_regenerate:
                # Warning flag: Caller should explicitly confirm regeneration
                pass

            # Structure transcript deterministically
            template_id = existing["template_id"]
            structured = structuring_engine.structure_transcript(
                transcript=transcript_text,
                template_id=template_id,
                audio_segments=audio_segments,
                transcript_source=resolved_source
            )

            update_data = {
                "original_transcript": transcript_text if not existing.get("original_transcript") else existing["original_transcript"],
                "edited_transcript": transcript_text,
                "structured_findings": structured.model_dump(),
                "impression": structured.impression
            }

            change_type = "REGENERATE" if force_regenerate else "STRUCTURING"
            return ReportRepository.update(conn, report_id, update_data, change_type=change_type)

    @staticmethod
    def mark_reviewed(
        report_id: str,
        reviewed_by: str,
        acknowledge_unresolved: bool = False,
        db_path: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_db(db_path) as conn:
            return ReportRepository.mark_reviewed(conn, report_id, reviewed_by, acknowledge_unresolved)

    @staticmethod
    def revert_to_draft(report_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
        with get_db(db_path) as conn:
            return ReportRepository.revert_to_draft(conn, report_id)

    @staticmethod
    def delete_report(report_id: str, db_path: Optional[str] = None) -> bool:
        with get_db(db_path) as conn:
            # Also clean up associated audio recordings on disk
            audio_records = AudioRepository.get_by_report_id(conn, report_id)
            for a in audio_records:
                if a.get("file_path") and os.path.exists(a["file_path"]):
                    try:
                        os.remove(a["file_path"])
                    except Exception:
                        pass
            return ReportRepository.delete(conn, report_id)

    @staticmethod
    def get_revisions(report_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_db(db_path) as conn:
            return ReportRepository.get_revisions(conn, report_id)

    @staticmethod
    def apply_unassigned_assignment(
        structured_dict: Dict[str, Any],
        unassigned_id: str,
        target_organ_key: str,
        custom_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        sf = copy.deepcopy(structured_dict or {})
        unassigned_list = sf.get("unassigned_findings") or []
        unassigned = next((u for u in unassigned_list if u.get("id") == unassigned_id), None)
        if not unassigned:
            raise KeyError("Unassigned finding not found.")
        if unassigned.get("is_resolved"):
            raise ValueError("This clinical finding has already been resolved.")

        sections = sf.get("sections") or []
        text_to_assign = (custom_text or unassigned.get("raw_text") or "").strip()
        if not text_to_assign:
            raise ValueError("Cannot assign empty finding text.")

        if target_organ_key == "impression":
            sf["impression"] = _append_sentence(sf.get("impression"), text_to_assign)
        else:
            target_sec = next((s for s in sections if s.get("key") == target_organ_key), None)
            if not target_sec:
                raise ValueError(f"Target section '{target_organ_key}' is invalid for this template.")

            existing_text = (target_sec.get("text") or "").strip() if target_sec.get("is_present") else ""
            norm_add = _norm_clause(text_to_assign)
            is_dup_text = bool(existing_text and norm_add and norm_add in _norm_clause(existing_text))

            target_sec["text"] = _append_sentence(existing_text, text_to_assign)
            target_sec["is_present"] = True
            if not target_sec.get("source_type"):
                target_sec["source_type"] = "manual"

            # Merge measurements while preserving existing entries and avoiding duplicates
            existing_meas = list(target_sec.get("measurements") or [])
            seen_meas = {
                (m.get("raw_str"), str(m.get("value")), m.get("unit"))
                for m in existing_meas if isinstance(m, dict)
            }
            for m in (unassigned.get("measurements") or []):
                sig = (m.get("raw_str"), str(m.get("value")), m.get("unit"))
                if not is_dup_text and sig not in seen_meas:
                    existing_meas.append(m)
                    seen_meas.add(sig)
            target_sec["measurements"] = existing_meas

            if not is_dup_text:
                findings = list(target_sec.get("findings") or [])
                findings.append({
                    "id": str(uuid.uuid4()),
                    "organ_key": target_organ_key,
                    "source_text": text_to_assign,
                    "current_text": text_to_assign,
                    "measurements": list(unassigned.get("measurements") or []),
                    "laterality": None,
                    "is_negation": False,
                    "is_uncertain": False,
                    "assignment_status": "confidently_assigned",
                    "review_flags": [],
                    "source_type": "manual",
                })
                target_sec["findings"] = findings

        unassigned["is_resolved"] = True
        unassigned["resolved_organ_key"] = target_organ_key
        unassigned["is_excluded"] = False
        unassigned["exclusion_reason"] = None
        sf["has_flags"] = any(not u.get("is_resolved") for u in unassigned_list) or len(sf.get("all_flags") or []) > 0
        return sf

    @staticmethod
    def apply_unassigned_exclusion(
        structured_dict: Dict[str, Any],
        unassigned_id: str,
        exclusion_reason: str,
    ) -> Dict[str, Any]:
        reason = (exclusion_reason or "").strip()
        if len(reason) < 3:
            raise ValueError("Please provide a documented clinical exclusion reason (at least 3 characters).")
        sf = copy.deepcopy(structured_dict or {})
        unassigned_list = sf.get("unassigned_findings") or []
        unassigned = next((u for u in unassigned_list if u.get("id") == unassigned_id), None)
        if not unassigned:
            raise KeyError("Unassigned finding not found.")
        unassigned["is_resolved"] = True
        unassigned["resolved_organ_key"] = None
        unassigned["is_excluded"] = True
        unassigned["exclusion_reason"] = reason
        sf["has_flags"] = any(not u.get("is_resolved") for u in unassigned_list) or len(sf.get("all_flags") or []) > 0
        return sf

    @staticmethod
    def assign_unassigned_finding(
        report_id: str,
        unassigned_id: str,
        target_organ_key: str,
        custom_text: Optional[str] = None,
        changed_by: str = "clinician",
        db_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        with get_db(db_path) as conn:
            existing = ReportRepository.get_by_id(conn, report_id)
            if not existing:
                raise KeyError(f"Report '{report_id}' not found.")
            updated_sf = ReportService.apply_unassigned_assignment(
                existing.get("structured_findings") or {},
                unassigned_id=unassigned_id,
                target_organ_key=target_organ_key,
                custom_text=custom_text,
            )
            update_payload: Dict[str, Any] = {"structured_findings": updated_sf}
            if target_organ_key == "impression" and updated_sf.get("impression") is not None:
                update_payload["impression"] = updated_sf["impression"]
            return ReportRepository.update(
                conn, report_id, update_payload, change_type="ASSIGN_UNASSIGNED", changed_by=changed_by
            )

    @staticmethod
    def exclude_unassigned_finding(
        report_id: str,
        unassigned_id: str,
        exclusion_reason: str,
        changed_by: str = "clinician",
        db_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        with get_db(db_path) as conn:
            existing = ReportRepository.get_by_id(conn, report_id)
            if not existing:
                raise KeyError(f"Report '{report_id}' not found.")
            updated_sf = ReportService.apply_unassigned_exclusion(
                existing.get("structured_findings") or {},
                unassigned_id=unassigned_id,
                exclusion_reason=exclusion_reason,
            )
            return ReportRepository.update(
                conn, report_id, {"structured_findings": updated_sf}, change_type="EXCLUDE_UNASSIGNED", changed_by=changed_by
            )
