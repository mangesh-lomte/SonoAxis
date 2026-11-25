import os
import io
import re
import json
import uuid
import logging
import zipfile
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
import docx

from backend.app.core.config import settings
from backend.app.db.connection import get_db
from backend.app.structuring.templates import TEMPLATES_CATALOG
from backend.app.schemas.template import (
    TemplateResponse, TemplateConfigUpdate, DocStructureResponse
)

logger = logging.getLogger("sonovoice.templates.service")

PLACEHOLDER_REGEX = re.compile(r"\[([A-Z0-9\s/_-]+)\]")
HEADING_REGEX = re.compile(r"^([A-Z\s/&-]+)\s*:\s*")


class TemplateService:
    TEMPLATES_UPLOAD_DIR = os.path.join("uploads", "templates")

    @classmethod
    def _ensure_upload_dir(cls):
        os.makedirs(cls.TEMPLATES_UPLOAD_DIR, exist_ok=True)

    @classmethod
    def extract_docx_structure(cls, docx_bytes: bytes, file_name: str) -> DocStructureResponse:
        """
        Extracts paragraphs, headings, placeholders, and table layouts from a DOCX file.
        Provides intelligent suggested clinical sections and table mapping for configuration.
        Enforces strict DOCX security validation (file size, zip integrity, macro inspection).
        """
        if len(docx_bytes) > 20 * 1024 * 1024:
            raise ValueError("File size exceeds 20MB limit.")

        if not file_name.lower().endswith(".docx"):
            raise ValueError("Security violation: Only valid .docx files are permitted. Macros (.docm) and other formats are prohibited.")

        # Security check: ensure valid zip and verify absence of macros or malicious payloads
        try:
            with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
                namelist = z.namelist()
                if any(n.startswith("word/vba") or (n.endswith(".bin") and "vba" in n.lower()) for n in namelist):
                    raise ValueError("Security violation: Template contains executable macros (VBA). Only macro-free .docx templates are permitted.")
                
                # Check for floating text boxes / drawing shapes
                has_floating_boxes = False
                warnings: List[str] = []
                if "word/document.xml" in namelist:
                    doc_xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
                    if "<w:txbx" in doc_xml or ("<w:drawing" in doc_xml and "<w:txbxContent" in doc_xml):
                        has_floating_boxes = True
                        warnings.append("Floating text box detected. Note that text inside floating shapes may not flow sequentially.")
        except zipfile.BadZipFile:
            raise ValueError("Invalid or corrupt DOCX archive.")

        doc = docx.Document(io.BytesIO(docx_bytes))
        detected_headings: List[str] = []
        detected_placeholders: List[str] = []
        tables_summary: List[Dict[str, Any]] = []
        suggested_sections: List[Dict[str, Any]] = []

        full_text_lower = ""
        placeholder_set = set()

        # 1. Paragraph Analysis
        order = 1
        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue
            full_text_lower += " " + text.lower()

            # Placeholders
            for m in PLACEHOLDER_REGEX.finditer(text):
                placeholder_set.add(f"[{m.group(1)}]")

            # Heading Detection
            match_head = HEADING_REGEX.match(text)
            if match_head and len(match_head.group(1).strip()) < 40:
                h_name = match_head.group(1).strip()
                if h_name not in detected_headings:
                    detected_headings.append(h_name)
                    key = re.sub(r"[^a-z0-9]+", "_", h_name.lower()).strip("_")
                    suggested_sections.append({
                        "order": order,
                        "key": key,
                        "label": h_name.title(),
                        "heading": f"{h_name}: "
                    })
                    order += 1
            elif any(kw in text.upper() for kw in ["IMPRESSION", "CONCLUSION", "ADV:", "RECOMMENDATIONS"]):
                for kw in ["IMPRESSION", "CONCLUSION", "ADV", "RECOMMENDATIONS"]:
                    if kw in text.upper() and kw not in detected_headings:
                        detected_headings.append(kw)
                        suggested_sections.append({
                            "order": order,
                            "key": kw.lower(),
                            "label": kw.title(),
                            "heading": f"{kw}: "
                        })
                        order += 1

        # 2. Table Analysis
        for idx, t in enumerate(doc.tables):
            num_rows = len(t.rows)
            num_cols = len(t.columns) if num_rows > 0 else 0
            headers = []
            if num_rows > 0:
                headers = [c.text.strip().replace("\n", " ") for c in t.rows[0].cells[:num_cols]]

            row_samples = []
            for r in t.rows[1:min(num_rows, 4)]:
                row_samples.append([c.text.strip().replace("\n", " ") for c in r.cells[:num_cols]])

            for r in t.rows:
                for c in r.cells:
                    c_text = c.text.strip()
                    for m in PLACEHOLDER_REGEX.finditer(c_text):
                        placeholder_set.add(f"[{m.group(1)}]")

            tables_summary.append({
                "table_index": idx,
                "rows": num_rows,
                "columns": num_cols,
                "header_sample": headers,
                "row_samples": row_samples
            })

        detected_placeholders = sorted(list(placeholder_set))

        # 3. Categorization Heuristics
        suggested_category = "custom"
        suggested_laterality = "not_applicable"

        if "venous" in full_text_lower and "arterial" in full_text_lower:
            suggested_category = "arteriovenous_doppler"
        elif "venous" in full_text_lower:
            suggested_category = "venous_doppler"
        elif "arterial" in full_text_lower:
            suggested_category = "arterial_doppler"
        elif "abdomen" in full_text_lower or "liver" in full_text_lower:
            suggested_category = "abdomen_pelvis"

        if "bilateral" in full_text_lower:
            suggested_laterality = "bilateral"
        elif "left" in full_text_lower and "right" not in full_text_lower:
            suggested_laterality = "left"
        elif "right" in full_text_lower and "left" not in full_text_lower:
            suggested_laterality = "right"

        return DocStructureResponse(
            file_name=file_name,
            paragraphs_count=len(doc.paragraphs),
            tables_count=len(doc.tables),
            detected_headings=detected_headings,
            detected_placeholders=detected_placeholders,
            tables_summary=tables_summary,
            suggested_sections=suggested_sections,
            suggested_category=suggested_category,
            suggested_laterality=suggested_laterality,
            warnings=warnings,
            has_floating_boxes=has_floating_boxes
        )

    @classmethod
    def import_template(
        cls,
        file_bytes: bytes,
        filename: str,
        custom_name: Optional[str] = None,
        category: Optional[str] = None,
        created_by_user_id: Optional[str] = None,
        created_by_name: Optional[str] = None,
        is_shared: bool = False,
        db_path: Optional[str] = None
    ) -> TemplateResponse:
        """
        Imports a new DOCX template.
        Stores the document on disk, extracts its structure, and registers it as DRAFT_CONFIG (unapproved).
        """
        cls._ensure_upload_dir()

        # 1. Validate structure and security BEFORE persisting to disk
        structure = cls.extract_docx_structure(file_bytes, filename)

        t_id = f"tpl-{uuid.uuid4().hex[:10]}"
        safe_filename = f"{t_id}_{re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)}"
        file_path = os.path.join(cls.TEMPLATES_UPLOAD_DIR, safe_filename)

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        final_category = category or structure.suggested_category
        display_name = custom_name or filename.replace(".docx", "").replace("_", " ").title()

        now = datetime.now(timezone.utc).isoformat()
        sections_json = json.dumps(structure.suggested_sections)
        doc_struct_json = json.dumps(structure.model_dump())

        # Determine default table type
        table_type = "none"
        if structure.tables_count > 0:
            cols = structure.tables_summary[0]["columns"] if structure.tables_summary else 0
            if cols == 5:
                table_type = "arterial_5col_table"
            elif cols == 3:
                table_type = "arterial_3col_table"
            else:
                table_type = "custom_table"

        with get_db(db_path) as conn:
            conn.execute(
                """
                INSERT INTO examination_templates (
                    id, name, gender, examination_type, canonical_sections, version,
                    created_at, updated_at, category, laterality, file_name, file_path, status,
                    table_type, is_built_in, is_shared, created_by_user_id, created_by_name, doc_structure_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    t_id,
                    display_name,
                    "Any",
                    final_category,
                    sections_json,
                    1,
                    now,
                    now,
                    final_category,
                    structure.suggested_laterality,
                    filename,
                    file_path,
                    "DRAFT_CONFIG",
                    table_type,
                    0,
                    1 if is_shared else 0,
                    created_by_user_id,
                    created_by_name,
                    doc_struct_json
                )
            )

        return cls.get_template(t_id, db_path=db_path)

    @classmethod
    def bulk_import_templates(
        cls,
        files: List[Tuple[str, bytes]],
        created_by_user_id: Optional[str] = None,
        created_by_name: Optional[str] = None,
        is_shared: bool = False,
        db_path: Optional[str] = None
    ) -> List[TemplateResponse]:
        """
        Imports multiple DOCX files concurrently in bulk.
        """
        results = []
        for filename, b_content in files:
            tpl = cls.import_template(
                b_content,
                filename,
                created_by_user_id=created_by_user_id,
                created_by_name=created_by_name,
                is_shared=is_shared,
                db_path=db_path,
            )
            results.append(tpl)
        return results

    @staticmethod
    def _row_to_response(r) -> TemplateResponse:
        keys = set(r.keys())
        sections = json.loads(r["canonical_sections"]) if r["canonical_sections"] else []
        table_config = json.loads(r["table_config_json"]) if r["table_config_json"] else None
        repeatable_config = json.loads(r["repeatable_config_json"]) if r["repeatable_config_json"] else None
        return TemplateResponse(
            id=r["id"],
            name=r["name"],
            gender=r["gender"],
            category=r["category"] or "abdomen_pelvis",
            laterality=r["laterality"] or "not_applicable",
            file_name=r["file_name"],
            file_path=r["file_path"],
            version=r["version"] or 1,
            status=r["status"] or "APPROVED",
            table_type=r["table_type"] or "none",
            sections=sections,
            table_config=table_config,
            repeatable_config=repeatable_config,
            created_at=r["created_at"],
            updated_at=r["updated_at"] if "updated_at" in keys else None,
            approved_by=r["approved_by"],
            approved_at=r["approved_at"],
            is_built_in=bool(r["is_built_in"]),
            is_shared=bool(r["is_shared"]) if "is_shared" in keys and r["is_shared"] is not None else bool(r["is_built_in"]),
            created_by_user_id=r["created_by_user_id"] if "created_by_user_id" in keys else None,
            created_by_name=r["created_by_name"] if "created_by_name" in keys else None,
            section_count=len(sections),
        )

    @classmethod
    def list_templates(
        cls,
        category: Optional[str] = None,
        laterality: Optional[str] = None,
        status: Optional[str] = None,
        query: Optional[str] = None,
        only_approved: bool = False,
        viewer_user_id: Optional[str] = None,
        viewer_role: Optional[str] = None,
        db_path: Optional[str] = None
    ) -> List[TemplateResponse]:
        """
        Returns template library entries scoped to shared/institutional templates plus caller's own custom templates.
        """
        with get_db(db_path) as conn:
            clauses = ["1=1"]
            params: List[Any] = []

            if viewer_role != "Administrator" and viewer_user_id:
                clauses.append("(is_built_in = 1 OR is_shared = 1 OR created_by_user_id = ?)")
                params.append(viewer_user_id)

            if only_approved:
                clauses.append("status = 'APPROVED'")
            elif status:
                clauses.append("status = ?")
                params.append(status.upper())

            if category and category.lower() != "all":
                if category.lower() == "custom":
                    clauses.append("(category = 'custom' OR is_built_in = 0)")
                else:
                    clauses.append("category = ?")
                    params.append(category)

            if laterality and laterality.lower() != "all":
                clauses.append("laterality = ?")
                params.append(laterality)

            if query:
                clauses.append("(name LIKE ? OR id LIKE ? OR file_name LIKE ?)")
                p_like = f"%{query}%"
                params.extend([p_like, p_like, p_like])

            sql = f"""
                SELECT * FROM examination_templates
                WHERE {' AND '.join(clauses)}
                ORDER BY is_built_in DESC, created_at DESC
            """
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [cls._row_to_response(r) for r in rows]

    @classmethod
    def get_template(cls, template_id: str, db_path: Optional[str] = None) -> Optional[TemplateResponse]:
        with get_db(db_path) as conn:
            r = conn.execute("SELECT * FROM examination_templates WHERE id = ?", (template_id,)).fetchone()
            if not r:
                return None
            return cls._row_to_response(r)

    @classmethod
    def configure_template(
        cls,
        template_id: str,
        update_data: TemplateConfigUpdate,
        db_path: Optional[str] = None
    ) -> TemplateResponse:
        """
        Updates clinical section definitions, measurement table mappings, and metadata.
        """
        tpl = cls.get_template(template_id, db_path=db_path)
        if not tpl:
            raise ValueError(f"Template '{template_id}' not found.")

        updates = []
        params = []

        if update_data.name is not None:
            updates.append("name = ?")
            params.append(update_data.name)
        if update_data.gender is not None:
            updates.append("gender = ?")
            params.append(update_data.gender)
        if update_data.category is not None:
            updates.append("category = ?")
            params.append(update_data.category)
        if update_data.laterality is not None:
            updates.append("laterality = ?")
            params.append(update_data.laterality)
        if update_data.table_type is not None:
            updates.append("table_type = ?")
            params.append(update_data.table_type)
        if update_data.sections is not None:
            updates.append("canonical_sections = ?")
            params.append(json.dumps(update_data.sections))
        if update_data.table_config is not None:
            updates.append("table_config_json = ?")
            params.append(json.dumps(update_data.table_config))
        if update_data.repeatable_config is not None:
            updates.append("repeatable_config_json = ?")
            params.append(json.dumps(update_data.repeatable_config))

        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now(timezone.utc).isoformat())
            with get_db(db_path) as conn:
                params.append(template_id)
                conn.execute(
                    f"UPDATE examination_templates SET {', '.join(updates)} WHERE id = ?",
                    tuple(params)
                )

        return cls.get_template(template_id, db_path=db_path)

    @classmethod
    def approve_template(
        cls,
        template_id: str,
        approved_by: str = "Clinical Director",
        mark_shared: Optional[bool] = None,
        db_path: Optional[str] = None
    ) -> TemplateResponse:
        """
        Approves or activates an imported template after configuration verification.
        Makes it selectable for clinical report creation.
        """
        tpl = cls.get_template(template_id, db_path=db_path)
        if not tpl:
            raise ValueError(f"Template '{template_id}' not found.")
        if not tpl.sections:
            raise ValueError(f"Cannot approve template '{template_id}': Must configure at least one clinical section.")

        now = datetime.now(timezone.utc).isoformat()
        with get_db(db_path) as conn:
            if mark_shared is not None:
                conn.execute(
                    """
                    UPDATE examination_templates
                    SET status = 'APPROVED', approved_by = ?, approved_at = ?, updated_at = ?, is_shared = ?
                    WHERE id = ?
                    """,
                    (approved_by, now, now, 1 if mark_shared else 0, template_id)
                )
            else:
                conn.execute(
                    """
                    UPDATE examination_templates
                    SET status = 'APPROVED', approved_by = ?, approved_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (approved_by, now, now, template_id)
                )

        return cls.get_template(template_id, db_path=db_path)

    @classmethod
    def archive_template(cls, template_id: str, db_path: Optional[str] = None) -> TemplateResponse:
        """
        Archives a template so it is hidden from New Report creation without breaking historic reports.
        """
        tpl = cls.get_template(template_id, db_path=db_path)
        if not tpl:
            raise ValueError(f"Template '{template_id}' not found.")

        now = datetime.now(timezone.utc).isoformat()
        with get_db(db_path) as conn:
            conn.execute(
                "UPDATE examination_templates SET status = 'ARCHIVED', updated_at = ? WHERE id = ?",
                (now, template_id)
            )

        return cls.get_template(template_id, db_path=db_path)

    @classmethod
    def version_template(cls, template_id: str, db_path: Optional[str] = None) -> TemplateResponse:
        """
        Increments the revision version of a template when modifying configurations.
        """
        tpl = cls.get_template(template_id, db_path=db_path)
        if not tpl:
            raise ValueError(f"Template '{template_id}' not found.")

        new_version = tpl.version + 1
        now = datetime.now(timezone.utc).isoformat()
        with get_db(db_path) as conn:
            conn.execute(
                "UPDATE examination_templates SET version = ?, status = 'DRAFT_CONFIG', updated_at = ? WHERE id = ?",
                (new_version, now, template_id)
            )

        return cls.get_template(template_id, db_path=db_path)

    @classmethod
    def render_template_preview_html(cls, template_id: str, db_path: Optional[str] = None) -> str:
        """Builds an HTML structure preview showing layout sections, placeholders, and extracted tables."""
        import html as _html

        tpl = cls.get_template(template_id, db_path=db_path)
        doc_struct: Dict[str, Any] = {}
        if tpl:
            with get_db(db_path) as conn:
                row = conn.execute(
                    "SELECT doc_structure_json FROM examination_templates WHERE id = ?", (template_id,)
                ).fetchone()
                if row and row["doc_structure_json"]:
                    doc_struct = json.loads(row["doc_structure_json"])
        else:
            from backend.app.structuring.templates import get_template_def
            t_def = get_template_def(template_id)
            if not t_def:
                raise ValueError(f"Template '{template_id}' not found.")
            tpl = TemplateResponse(
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
                section_count=len(t_def.get("sections", [])),
            )

        esc = _html.escape
        scope_label = (
            "Shared Institutional Template"
            if tpl.is_built_in or tpl.is_shared
            else f"Personal Custom Template ({esc(tpl.created_by_name or 'Radiologist')})"
        )
        rows_html = "".join(
            f"<tr><td style='padding:6px 10px;border:1px solid #e2e8f0;font-family:monospace;'>{idx+1}</td>"
            f"<td style='padding:6px 10px;border:1px solid #e2e8f0;font-weight:600;'>{esc(str(s.get('label','')))}</td>"
            f"<td style='padding:6px 10px;border:1px solid #e2e8f0;font-family:monospace;color:#475569;'>{esc(str(s.get('key','')))}</td>"
            f"<td style='padding:6px 10px;border:1px solid #e2e8f0;color:#334155;'>{esc(str(s.get('heading','')))}</td></tr>"
            for idx, s in enumerate(tpl.sections)
        )
        placeholders = doc_struct.get("detected_placeholders") or []
        ph_html = (
            "".join(
                f"<span style='display:inline-block;margin:2px 4px 2px 0;padding:2px 7px;border-radius:4px;background:#f0fdfa;border:1px solid #99f6e4;font-family:monospace;font-size:11px;color:#0f766e;'>{esc(str(p))}</span>"
                for p in placeholders
            )
            if placeholders
            else "<span style='color:#94a3b8;font-size:12px;'>No bracketed placeholders detected</span>"
        )
        return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Template Preview - {esc(tpl.name)}</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;background:#f8fafc;color:#0f172a;margin:0;padding:24px;">
  <div style="max-width:860px;margin:0 auto;background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:24px;">
    <div style="border-bottom:2px solid #0d9488;padding-bottom:12px;margin-bottom:16px;">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#0d9488;">{scope_label}</div>
      <h1 style="margin:4px 0 6px;font-size:20px;">{esc(tpl.name)}</h1>
      <div style="font-size:12px;color:#475569;">
        Status: <strong>{esc(tpl.status)}</strong> &middot;
        Version: <strong>v{tpl.version}</strong> &middot;
        Category: <strong>{esc(tpl.category)}</strong> &middot;
        Laterality: <strong>{esc(tpl.laterality)}</strong> &middot;
        Table Type: <strong>{esc(tpl.table_type)}</strong>
      </div>
    </div>
    <h3 style="font-size:13px;text-transform:uppercase;color:#334155;margin:16px 0 8px;">Clinical Sections ({len(tpl.sections)})</h3>
    <table style="width:100%;border-collapse:collapse;font-size:12px;">
      <thead>
        <tr style="background:#f1f5f9;text-align:left;">
          <th style="padding:6px 10px;border:1px solid #e2e8f0;">#</th>
          <th style="padding:6px 10px;border:1px solid #e2e8f0;">Section Label</th>
          <th style="padding:6px 10px;border:1px solid #e2e8f0;">Anatomical Key</th>
          <th style="padding:6px 10px;border:1px solid #e2e8f0;">Document Heading</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    <h3 style="font-size:13px;text-transform:uppercase;color:#334155;margin:18px 0 8px;">Detected Placeholders</h3>
    <div>{ph_html}</div>
  </div>
</body>
</html>"""
