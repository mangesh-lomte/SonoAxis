import os
import io
import glob
import hashlib
import logging
from typing import Dict, Any, Optional, List
import docx
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from backend.app.structuring.templates import TEMPLATES_CATALOG, get_template_def, STANDARD_ARTERIAL_SEGMENTS

logger = logging.getLogger("sonovoice.export.word")

# Baseline hashes for template integrity verification
BASELINE_HASHES = {
    "references/male-abdomen-pelvis.docx": "D9E61DEB759F4F21A8445A29332ACE7A2ED02E692335B5DB109328110133FCF1",
    "references/female-abdomen-pelvis.docx": "F308D3016FFD46FCC0A95CFE0845AD756BCD347F2F1053034A34103620DF0D9F"
}

# Forbidden placeholder tokens that must NEVER appear in clinical exports
FORBIDDEN_PLACEHOLDERS = [
    "[PSV]",
    "[INCOMPETENT PERFORATOR]",
    "[BLANK - CLINICAL IMPRESSION TO BE DICTATED]",
    "[CLINICAL PROFILE / INDICATION]",
    "[PATIENT NAME]",
    "[PATIENT ID]",
    "[REPORT DATE]",
    "[AGE]",
    "[GENDER]",
    "[REFERRAL DOCTOR]"
]

class WordExportService:
    @staticmethod
    def _verify_template_hash(template_path: str):
        norm_path = template_path.replace("\\", "/")
        for ref_key, expected_hash in BASELINE_HASHES.items():
            if norm_path.endswith(ref_key) or ref_key.endswith(norm_path):
                if os.path.exists(template_path):
                    with open(template_path, "rb") as f:
                        current_hash = hashlib.sha256(f.read()).hexdigest().upper()
                    if current_hash != expected_hash:
                        raise ValueError(f"CRITICAL: Template integrity violation! {template_path} hash changed.")
                break

    @staticmethod
    def _format_date(date_str: Optional[str]) -> str:
        if not date_str:
            return ""
        parts = date_str.strip().split("-")
        if len(parts) == 3 and len(parts[0]) == 4:
            return f"{parts[2]}.{parts[1]}.{parts[0]}"
        return date_str

    @classmethod
    def _resolve_template_path(cls, template_id: str, references_dir: str) -> str:
        template_def = get_template_def(template_id)
        file_path = template_def.get("file_path")
        file_name = template_def.get("file_name")
        legacy_file = template_def.get("legacy_file_name")

        candidates = []
        if file_path:
            candidates.append(file_path)
        if legacy_file:
            candidates.append(os.path.join(references_dir, legacy_file))
        if file_name:
            candidates.append(os.path.join(references_dir, "sanitized_templates", file_name))
            candidates.append(os.path.join(references_dir, "original_templates", file_name))
            candidates.append(os.path.join(references_dir, file_name))
            candidates.append(os.path.join("uploads", "templates", file_name))

        for c in candidates:
            if os.path.exists(c):
                return c

        if file_name and file_name.lower().endswith(".docx"):
            stem = os.path.splitext(file_name)[0]
            for pattern in (
                os.path.join(references_dir, "**", f"{stem}*.docx"),
                os.path.join(references_dir, f"{stem}*.docx"),
            ):
                matches = sorted(glob.glob(pattern, recursive=True))
                if matches:
                    return matches[0]

        # Check existing abdomen fallbacks
        is_female = "female" in template_id.lower()
        fallback = os.path.join(references_dir, "female-abdomen-pelvis.docx" if is_female else "male-abdomen-pelvis.docx")
        if os.path.exists(fallback):
            return fallback

        raise FileNotFoundError(f"Reference template for '{template_id}' not found in candidates: {candidates}")

    @classmethod
    def generate_docx(cls, report_data: Dict[str, Any], references_dir: str = "references") -> bytes:
        """
        Generates a pristine Microsoft Word .docx report adhering strictly to the
        configured institutional or custom DOCX template while replacing sample findings
        with actual dictated data. Supports Abdominal and Multi-Protocol Vascular examinations.
        NEVER modifies reference files on disk.
        """
        template_id = report_data.get("template_id") or "usg-abdomen-pelvis-male"
        template_def = get_template_def(template_id)
        is_female = "female" in template_id.lower()

        template_path = cls._resolve_template_path(template_id, references_dir)

        # 1. Verify template integrity baseline before loading
        cls._verify_template_hash(template_path)

        # 2. Read into memory buffer (strictly read-only from disk)
        with open(template_path, "rb") as f:
            template_bytes = f.read()

        doc_stream = io.BytesIO(template_bytes)
        doc = docx.Document(doc_stream)

        # 3. Extract patient snapshot and report metadata
        patient_snap = report_data.get("patient_snapshot") or {}
        patient_name = patient_snap.get("full_name") or report_data.get("patient_name") or "—"
        age_years = patient_snap.get("age_years")
        if age_years is None:
            age_years = report_data.get("age_years")
        age_display = f"{age_years} years" if age_years is not None else "Not specified"
        gender = patient_snap.get("gender") or report_data.get("gender") or ("Female" if is_female else "Male")
        gender_cap = gender.capitalize()
        age_gender_str = f"{age_display}   Sex: {gender_cap}"

        patient_id = (
            patient_snap.get("patient_id")
            or report_data.get("patient_identifier")
            or report_data.get("patient_id")
            or report_data.get("report_number")
            or ""
        )
        report_date_raw = report_data.get("report_date") or ""
        report_date_str = cls._format_date(report_date_raw)
        referral_doc = report_data.get("referral_doctor") or patient_snap.get("referral_doctor") or ""

        status = (report_data.get("status") or "DRAFT").upper()
        is_draft = status == "DRAFT"

        # 4. Populate Demographics Block
        # Check if Table 0 is a 3x2 demographic table (abdomen templates)
        has_demographic_table = False
        if doc.tables and len(doc.tables[0].columns) == 2 and len(doc.tables[0].rows) >= 2:
            t0 = doc.tables[0]
            if "Patient Name" in t0.rows[0].cells[0].text or "PATIENT" in t0.rows[0].cells[0].text.upper():
                has_demographic_table = True

                def _populate_cell(cell, label_text: str, val_text: str):
                    p = cell.paragraphs[0]
                    p.text = ""
                    r1 = p.add_run(label_text)
                    r1.bold = True
                    r1.font.name = "Arial"
                    r1.font.size = Pt(11)
                    r2 = p.add_run(val_text)
                    r2.bold = True
                    r2.font.name = "Arial"
                    r2.font.size = Pt(11)

                if len(t0.rows) > 0 and len(t0.rows[0].cells) > 1:
                    _populate_cell(t0.rows[0].cells[0], "Patient Name: ", patient_name)
                    _populate_cell(t0.rows[0].cells[1], "Age: ", age_gender_str)

                if len(t0.rows) > 1 and len(t0.rows[1].cells) > 1:
                    _populate_cell(t0.rows[1].cells[0], "Patient ID: ", patient_id)
                    _populate_cell(t0.rows[1].cells[1], "Date: ", report_date_str)

                if len(t0.rows) > 2:
                    for c in t0.rows[2].cells:
                        _populate_cell(c, "Referral Dr.: ", referral_doc)

        # In Doppler templates without a demographic table, demographics are in top paragraphs
        if not has_demographic_table:
            for p in doc.paragraphs[:8]:
                p_text = p.text
                if "Patient Name:" in p_text or "[PATIENT NAME]" in p_text:
                    p.text = ""
                    r1 = p.add_run(f"  Patient Name: {patient_name}\tAge: {age_gender_str}")
                    r1.bold = True
                    r1.font.name = "Arial"
                    r1.font.size = Pt(11)
                elif "Patient ID:" in p_text or "[PATIENT ID]" in p_text:
                    p.text = ""
                    r2 = p.add_run(f"  Patient ID: {patient_id}\t Date: {report_date_str}")
                    r2.bold = True
                    r2.font.name = "Arial"
                    r2.font.size = Pt(11)
                elif "Referral Dr.:" in p_text or "[REFERRAL DOCTOR]" in p_text:
                    p.text = ""
                    r3 = p.add_run(f"  Referral Dr.: {referral_doc}")
                    r3.bold = True
                    r3.font.name = "Arial"
                    r3.font.size = Pt(11)

        # 5. Locate Title and Signature Block Paragraphs
        title_p = None
        sig_p = None
        body_to_remove = []
        found_title = False

        title_keywords = [
            "ULTRASOUND ABDOMEN AND PELVIS",
            "LOWER LIMB VENOUS DOPPLER STUDY",
            "LOWER LIMB ARTERIAL DOPPLER STUDY",
            "LOWER LIMB ARTERIO VENOUS DOPPLER STUDY",
            "LOWER LIMB ARTERIO DOPPLER STUDY",
            "LOWER LIMB ARTERIALPERIPHERAL VASCULAR DISEASE",
            "VENOUS DOPPLER STUDY",
            "ARTERIAL DOPPLER STUDY"
        ]

        paragraphs = list(doc.paragraphs)
        role_keywords = ["Chief Radiologist", "MD, DNB.", "Consultant Radiologist", "Attending Radiologist"]
        sig_idx = None
        for idx, p in enumerate(paragraphs):
            p_upper = p.text.strip().upper()
            if any(kw in p_upper for kw in title_keywords):
                title_p = p
                found_title = True
                continue
            if found_title:
                if any(kw in p.text for kw in role_keywords):
                    sig_idx = idx
                    break
                body_to_remove.append(p)

        if sig_idx is None:
            for idx, p in enumerate(paragraphs):
                if any(kw in p.text for kw in role_keywords):
                    sig_idx = idx
                    break

        if sig_idx is not None:
            if sig_idx > 0 and "Dr." in paragraphs[sig_idx - 1].text:
                sig_p = paragraphs[sig_idx - 1]
                body_to_remove = [p for p in body_to_remove if p._element is not sig_p._element]
            else:
                sig_p = paragraphs[sig_idx]
        else:
            raise ValueError("Template structure error: Signature block anchor not found.")

        # 6. Remove all hardcoded sample body paragraphs
        for p in body_to_remove:
            p._element.getparent().remove(p._element)

        # 7. Draft Banner at Top (if DRAFT)
        if is_draft and title_p:
            draft_top = title_p.insert_paragraph_before()
            draft_top.alignment = WD_ALIGN_PARAGRAPH.CENTER
            draft_top.paragraph_format.space_before = Pt(0)
            draft_top.paragraph_format.space_after = Pt(8)
            r_dt = draft_top.add_run("*** DRAFT — REQUIRES RADIOLOGIST REVIEW ***")
            r_dt.bold = True
            r_dt.font.name = "Arial"
            r_dt.font.size = Pt(11)
            r_dt.font.color.rgb = RGBColor(220, 38, 38)

        # 8. Check and Populate Native Word Arterial Measurement Table (if present)
        # Some templates have a 9-row arterial table (e.g. BILATERAL LOWER LIMB ARTERIO DOPPLER STUDY)
        has_native_arterial_table = False
        arterial_table = None
        for t in doc.tables:
            if len(t.rows) >= 7 and len(t.columns) in [3, 5]:
                # Check if cell(0,0) is ARTERY
                if "ARTERY" in t.rows[0].cells[0].text.upper():
                    has_native_arterial_table = True
                    arterial_table = t
                    break

        structured_findings = report_data.get("structured_findings") or {}
        vascular_biometry = report_data.get("vascular_biometry") or structured_findings.get("vascular_biometry") or {}
        arterial_rows = vascular_biometry.get("arterial_table") or []
        arterial_map = {item.get("segment_key"): item for item in arterial_rows if isinstance(item, dict)}

        if has_native_arterial_table and arterial_table:
            # Populate cells in table rows (Row 2 onwards are anatomical segments)
            start_row = 2 if len(arterial_table.rows) >= 9 else 1
            for r_idx in range(start_row, len(arterial_table.rows)):
                row = arterial_table.rows[r_idx]
                seg_idx = r_idx - start_row
                if seg_idx < len(STANDARD_ARTERIAL_SEGMENTS):
                    seg_def = STANDARD_ARTERIAL_SEGMENTS[seg_idx]
                    seg_key = seg_def["key"]
                    biom = arterial_map.get(seg_key, {})

                    # Artery label
                    row.cells[0].text = seg_def["name"]
                    p0 = row.cells[0].paragraphs[0]
                    p0.runs[0].font.name = "Arial"
                    p0.runs[0].font.size = Pt(10)
                    p0.runs[0].bold = True

                    if len(row.cells) == 5:
                        # 5-column: Col 1=PSV Right, Col 2=PSV Left, Col 3=Flow Right, Col 4=Flow Left
                        psv_r = biom.get("psv_right")
                        psv_l = biom.get("psv_left")
                        flow_r = biom.get("flow_pattern_right") or "Triphasic"
                        flow_l = biom.get("flow_pattern_left") or "Triphasic"

                        row.cells[1].text = f"{psv_r:.2f}" if psv_r is not None else "-"
                        row.cells[2].text = f"{psv_l:.2f}" if psv_l is not None else "-"
                        row.cells[3].text = flow_r
                        row.cells[4].text = flow_l
                    elif len(row.cells) == 3:
                        # 3-column unilateral: Col 1=PSV, Col 2=Flow Pattern
                        psv_val = biom.get("psv_left") if template_def.get("laterality") == "left" else biom.get("psv_right")
                        flow_val = biom.get("flow_pattern_left") if template_def.get("laterality") == "left" else biom.get("flow_pattern_right")
                        row.cells[1].text = f"{psv_val:.2f}" if psv_val is not None else "-"
                        row.cells[2].text = flow_val or "Triphasic"

                    # Format cell fonts
                    for cell in row.cells[1:]:
                        if cell.paragraphs and cell.paragraphs[0].runs:
                            cell.paragraphs[0].runs[0].font.name = "Arial"
                            cell.paragraphs[0].runs[0].font.size = Pt(10)

        # 9. Insert Canonical Structured Findings
        sections = structured_findings.get("sections", [])
        sections_map = {s.get("key"): s for s in sections}
        canonical_sections = template_def.get("sections", [])

        for sec_def in canonical_sections:
            sec_key = sec_def.get("key")
            if sec_key == "impression":
                continue

            # If template already has a native Word arterial table, skip duplicate text table
            if sec_key in ["measurement_table", "arterial_table"] and has_native_arterial_table:
                continue

            sec_data = sections_map.get(sec_key)
            if not sec_data:
                continue

            is_present = sec_data.get("is_present", False)
            raw_text = (sec_data.get("text") or "").strip()

            if is_present and raw_text:
                new_p = sig_p.insert_paragraph_before()
                new_p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                new_p.paragraph_format.space_before = Pt(0)
                new_p.paragraph_format.space_after = Pt(4)
                new_p.paragraph_format.line_spacing = 1.15

                heading = sec_def.get("heading")
                if heading is None:
                    heading = f"{sec_def.get('label', '')}: "

                cleaned_text = raw_text
                if heading:
                    if cleaned_text.lower().startswith(heading.strip().lower()):
                        cleaned_text = cleaned_text[len(heading.strip()):].lstrip(" :")
                elif sec_def.get("label") and sec_def.get("label").lower() not in cleaned_text.lower():
                    heading = f"{sec_def.get('label')}: "

                # Check if this is a tab-stop table or perforators block (keep newlines)
                if "\n" in cleaned_text or "\t" in cleaned_text:
                    if heading:
                        r_head = new_p.add_run(heading.strip() + "\n")
                        r_head.bold = True
                        r_head.font.name = "Arial"
                        r_head.font.size = Pt(11)
                    r_body = new_p.add_run(cleaned_text)
                    r_body.bold = False
                    r_body.font.name = "Arial"
                    r_body.font.size = Pt(10)
                else:
                    if heading:
                        r_head = new_p.add_run(heading.strip() + " ")
                        r_head.bold = True
                        r_head.font.name = "Arial"
                        r_head.font.size = Pt(11)
                    r_body = new_p.add_run(cleaned_text)
                    r_body.bold = False
                    r_body.font.name = "Arial"
                    r_body.font.size = Pt(11)

        # 10. Insert Impression (Heading is preserved; content remains blank if undictated)
        impression_text = (
            structured_findings.get("impression")
            or report_data.get("impression")
            or ""
        ).strip()

        imp_p = sig_p.insert_paragraph_before()
        imp_p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        imp_p.paragraph_format.space_before = Pt(8)
        imp_p.paragraph_format.space_after = Pt(4)

        if impression_text:
            r_imp_lbl = imp_p.add_run("IMPRESSION: ")
            r_imp_lbl.bold = True
            r_imp_lbl.font.name = "Arial"
            r_imp_lbl.font.size = Pt(11)
            r_imp_val = imp_p.add_run(impression_text)
            r_imp_val.bold = True
            r_imp_val.font.name = "Arial"
            r_imp_val.font.size = Pt(11)
        else:
            r_imp_lbl = imp_p.add_run("IMPRESSION: ")
            r_imp_lbl.bold = True
            r_imp_lbl.font.name = "Arial"
            r_imp_lbl.font.size = Pt(11)

        # 11. Recommendations (ADV:) if dictated
        rec_text = (
            structured_findings.get("recommendations")
            or report_data.get("recommendations")
            or ""
        ).strip()

        if rec_text:
            rec_p = sig_p.insert_paragraph_before()
            rec_p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            rec_p.paragraph_format.space_before = Pt(4)
            rec_p.paragraph_format.space_after = Pt(8)
            r_rec_lbl = rec_p.add_run("ADV: ")
            r_rec_lbl.bold = True
            r_rec_lbl.font.name = "Arial"
            r_rec_lbl.font.size = Pt(11)
            r_rec_val = rec_p.add_run(rec_text)
            r_rec_val.bold = False
            r_rec_val.font.name = "Arial"
            r_rec_val.font.size = Pt(11)

        # 12. Bottom status banner or reviewer attestation
        if is_draft:
            draft_bottom = doc.add_paragraph()
            draft_bottom.alignment = WD_ALIGN_PARAGRAPH.CENTER
            draft_bottom.paragraph_format.space_before = Pt(12)
            draft_bottom.paragraph_format.space_after = Pt(6)
            r_db = draft_bottom.add_run("*** DRAFT — REQUIRES RADIOLOGIST REVIEW — NOT FOR CLINICAL USE ***")
            r_db.bold = True
            r_db.font.name = "Arial"
            r_db.font.size = Pt(10)
            r_db.font.color.rgb = RGBColor(220, 38, 38)
        else:
            reviewed_by = report_data.get("reviewed_by") or "Radiologist"
            reviewed_at = report_data.get("reviewed_at")
            rev_p = doc.add_paragraph()
            rev_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            rev_p.paragraph_format.space_before = Pt(12)
            rev_p.paragraph_format.space_after = Pt(6)
            rev_msg = f"Reviewed and clinically verified by: {reviewed_by}"
            if reviewed_at:
                rev_msg += f" on {reviewed_at}"
            r_rev = rev_p.add_run(rev_msg)
            r_rev.bold = True
            r_rev.font.name = "Arial"
            r_rev.font.size = Pt(10)
            r_rev.italic = True

        # 13. Global Placeholder Sanitization Check
        # Guarantees tokens like [PSV], [INCOMPETENT PERFORATOR], etc. NEVER appear in output
        for p in doc.paragraphs:
            for ph in FORBIDDEN_PLACEHOLDERS:
                if ph in p.text:
                    p.text = p.text.replace(ph, "")
        for t in doc.tables:
            for r in t.rows:
                for c in r.cells:
                    for ph in FORBIDDEN_PLACEHOLDERS:
                        if ph in c.text:
                            c.text = c.text.replace(ph, "-" if ph == "[PSV]" else "")

        # 14. Save to output buffer
        output_stream = io.BytesIO()
        doc.save(output_stream)
        output_stream.seek(0)
        return output_stream.getvalue()
