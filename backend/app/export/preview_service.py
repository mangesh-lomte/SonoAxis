import html
from typing import Dict, Any, Optional
from backend.app.structuring.templates import get_template_def

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

class PreviewService:
    @staticmethod
    def _format_date(date_str: Optional[str]) -> str:
        if not date_str:
            return ""
        parts = date_str.strip().split("-")
        if len(parts) == 3 and len(parts[0]) == 4:
            return f"{parts[2]}.{parts[1]}.{parts[0]}"
        return date_str

    @classmethod
    def render_html(cls, report_data: Dict[str, Any]) -> str:
        """
        Renders an exact HTML representation of the clinical report,
        matching Letter page geometry, margins, typography, tables, and signature block.
        Supports Abdominal and Multi-Protocol Vascular examinations.
        Serves both live web preview and headless Edge PDF rendering.
        """
        template_id = report_data.get("template_id") or "usg-abdomen-pelvis-male"
        template_def = get_template_def(template_id)
        is_female = "female" in template_id.lower()
        category = template_def.get("category", "abdomen_pelvis")
        laterality = template_def.get("laterality", "not_applicable")

        patient_snap = report_data.get("patient_snapshot") or {}
        patient_name = patient_snap.get("full_name") or report_data.get("patient_name") or "—"
        age_years = patient_snap.get("age_years")
        if age_years is None:
            age_years = report_data.get("age_years")
        age_display = f"{age_years} years" if age_years is not None else "Not specified"
        gender = patient_snap.get("gender") or report_data.get("gender") or ("Female" if is_female else "Male")
        gender_cap = gender.capitalize()
        age_gender_str = f"{age_display} | Sex: {gender_cap}"

        patient_id = (
            patient_snap.get("patient_id")
            or report_data.get("patient_identifier")
            or report_data.get("patient_id")
            or report_data.get("report_number")
            or ""
        )
        report_date_str = cls._format_date(report_data.get("report_date"))
        referral_doc = report_data.get("referral_doctor") or patient_snap.get("referral_doctor") or ""

        status = (report_data.get("status") or "DRAFT").upper()
        is_draft = status == "DRAFT"

        # Determine clinical examination title
        if category == "abdomen_pelvis":
            report_title = "ULTRASOUND ABDOMEN AND PELVIS"
        elif category == "venous_doppler":
            lat_str = laterality.upper() if laterality in ["right", "left", "bilateral"] else ""
            report_title = f"{lat_str} LOWER LIMB VENOUS DOPPLER STUDY".strip()
        elif category == "arterial_doppler":
            lat_str = laterality.upper() if laterality in ["right", "left", "bilateral"] else ""
            report_title = f"{lat_str} LOWER LIMB ARTERIAL DOPPLER STUDY".strip()
        elif category == "arteriovenous_doppler":
            lat_str = laterality.upper() if laterality in ["right", "left", "bilateral"] else ""
            report_title = f"{lat_str} LOWER LIMB ARTERIO VENOUS DOPPLER STUDY".strip()
        else:
            report_title = template_def.get("name", "ULTRASOUND EXAMINATION").upper()

        # Structured findings
        structured_findings = report_data.get("structured_findings") or {}
        sections = structured_findings.get("sections", [])
        sections_map = {s.get("key"): s for s in sections}
        canonical_sections = template_def.get("sections", [])

        sections_html_parts = []
        for sec_def in canonical_sections:
            sec_key = sec_def.get("key")
            if sec_key == "impression":
                continue

            sec_data = sections_map.get(sec_key)
            if not sec_data:
                continue

            is_present = sec_data.get("is_present", False)
            raw_text = (sec_data.get("text") or "").strip()

            if is_present and raw_text:
                heading = sec_def.get("heading")
                if heading is None:
                    heading = f"{sec_def.get('label', '')}: "

                cleaned_text = raw_text
                if heading:
                    if cleaned_text.lower().startswith(heading.strip().lower()):
                        cleaned_text = cleaned_text[len(heading.strip()):].lstrip(" :")
                elif sec_def.get("label") and sec_def.get("label").lower() not in cleaned_text.lower():
                    heading = f"{sec_def.get('label')}: "

                # Clean any forbidden placeholder tokens
                for ph in FORBIDDEN_PLACEHOLDERS:
                    cleaned_text = cleaned_text.replace(ph, "")

                escaped_text = html.escape(cleaned_text)

                if "\n" in cleaned_text or "\t" in cleaned_text or sec_key in ["measurement_table", "arterial_table", "perforators"]:
                    heading_html = f"<div class='section-heading-block'>{html.escape(heading.strip())}</div>" if heading else ""
                    sections_html_parts.append(
                        f"<div class='tabular-block'>{heading_html}<pre class='tab-stop-pre'>{escaped_text}</pre></div>"
                    )
                else:
                    heading_html = f"<span class='organ-label'>{html.escape(heading.strip())} </span>" if heading else ""
                    sections_html_parts.append(
                        f"<div class='section-p'>{heading_html}{escaped_text}</div>"
                    )

        sections_html = "\n".join(sections_html_parts)

        # Impression (Always show heading; blank content if undictated)
        impression_text = (
            structured_findings.get("impression")
            or report_data.get("impression")
            or ""
        ).strip()
        for ph in FORBIDDEN_PLACEHOLDERS:
            impression_text = impression_text.replace(ph, "")

        if impression_text:
            impression_html = f"""
            <div class='impression-block'>
                <span class='impression-label'>IMPRESSION: </span>
                <span class='impression-text'>{html.escape(impression_text)}</span>
            </div>
            """
        else:
            impression_html = """
            <div class='impression-block'>
                <span class='impression-label'>IMPRESSION: </span>
                <span class='impression-text'></span>
            </div>
            """

        # Recommendations (ADV:)
        rec_text = (
            structured_findings.get("recommendations")
            or report_data.get("recommendations")
            or ""
        ).strip()
        for ph in FORBIDDEN_PLACEHOLDERS:
            rec_text = rec_text.replace(ph, "")

        rec_html = ""
        if rec_text:
            rec_html = f"""
            <div class='adv-block'>
                <span class='adv-label'>ADV: </span>
                <span class='adv-text'>{html.escape(rec_text)}</span>
            </div>
            """

        # Status banners & metadata
        top_draft_banner = ""
        bottom_status_block = ""

        if is_draft:
            top_draft_banner = "<div class='draft-banner-top'>*** DRAFT — REQUIRES RADIOLOGIST REVIEW ***</div>"
            bottom_status_block = "<div class='draft-banner-bottom'>*** DRAFT — REQUIRES RADIOLOGIST REVIEW — NOT FOR CLINICAL USE ***</div>"
        else:
            reviewed_by = report_data.get("reviewed_by") or "Radiologist"
            reviewed_at = report_data.get("reviewed_at") or ""
            bottom_status_block = f"<div class='reviewed-metadata'>Reviewed and clinically verified by: {html.escape(reviewed_by)} on {html.escape(str(reviewed_at))}</div>"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Ultrasound Report - {html.escape(str(report_data.get('report_number', 'Draft')))}</title>
<style>
  @page {{
    size: letter portrait;
    margin: 1.0in 1.125in 0.5in 1.25in;
  }}
  @media print {{
    body {{
      margin: 0;
      padding: 0;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }}
    .no-print {{ display: none; }}
  }}
  body {{
    font-family: Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.35;
    color: #000;
    margin: 0;
    padding: 24px;
    background: #fff;
    max-width: 8.5in;
    margin-left: auto;
    margin-right: auto;
  }}
  .draft-banner-top {{
    color: #dc2626;
    font-weight: bold;
    font-size: 11pt;
    text-align: center;
    border: 1.5px dashed #dc2626;
    padding: 6px 10px;
    margin-bottom: 14px;
    border-radius: 4px;
    background-color: #fef2f2;
  }}
  .draft-banner-bottom {{
    color: #dc2626;
    font-weight: bold;
    font-size: 10pt;
    text-align: center;
    border: 1px dashed #dc2626;
    padding: 5px;
    margin-top: 24px;
    margin-bottom: 14px;
    background-color: #fef2f2;
  }}
  .reviewed-metadata {{
    color: #1e293b;
    font-weight: bold;
    font-style: italic;
    font-size: 10pt;
    margin-top: 20px;
    margin-bottom: 12px;
  }}
  table.patient-info {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 16px;
    font-weight: bold;
    font-size: 11pt;
  }}
  table.patient-info td {{
    padding: 3px 0;
    vertical-align: top;
    width: 50%;
  }}
  .report-title {{
    font-family: Calibri, sans-serif;
    font-size: 13pt;
    font-weight: bold;
    text-align: center;
    margin-top: 14px;
    margin-bottom: 16px;
    text-transform: uppercase;
  }}
  .section-p {{
    text-align: justify;
    margin: 6px 0;
  }}
  .section-heading-block {{
    font-weight: bold;
    margin-top: 10px;
    margin-bottom: 4px;
  }}
  .organ-label {{
    font-weight: bold;
  }}
  .tabular-block {{
    margin: 8px 0;
  }}
  .tab-stop-pre {{
    font-family: "Courier New", Courier, monospace;
    font-size: 9.5pt;
    line-height: 1.3;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    padding: 8px 12px;
    border-radius: 4px;
    overflow-x: auto;
    white-space: pre-wrap;
  }}
  .impression-block {{
    margin-top: 14px;
    margin-bottom: 12px;
    text-align: justify;
  }}
  .impression-label {{
    font-weight: bold;
    font-size: 11pt;
  }}
  .impression-text {{
    font-weight: bold;
    font-style: italic;
  }}
  .adv-block {{
    margin-top: 10px;
    margin-bottom: 12px;
    text-align: justify;
  }}
  .adv-label {{
    font-weight: bold;
    font-size: 11pt;
  }}
  .adv-text {{
    font-weight: normal;
  }}
  .sig-block {{
    margin-top: 36px;
    display: flex;
    justify-content: space-between;
    font-size: 9pt;
    page-break-inside: avoid;
    border-top: 1px solid #e2e8f0;
    padding-top: 12px;
  }}
  .sig-col {{
    width: 24%;
    line-height: 1.25;
  }}
  .sig-name {{
    font-weight: bold;
    font-size: 10pt;
    margin-bottom: 2px;
  }}
  .sig-sub {{
    font-size: 8pt;
    color: #334155;
  }}
</style>
</head>
<body>
{top_draft_banner}

<table class="patient-info">
  <tr>
    <td>Patient Name: {html.escape(patient_name)}</td>
    <td>Age: {html.escape(age_gender_str)}</td>
  </tr>
  <tr>
    <td>Patient ID: {html.escape(patient_id)}</td>
    <td>Date: {html.escape(report_date_str)}</td>
  </tr>
  <tr>
    <td colspan="2">Referral Dr.: {html.escape(referral_doc)}</td>
  </tr>
</table>

<div class="report-title">{html.escape(report_title)}</div>

<div class="report-body">
{sections_html}
</div>

{impression_html}
{rec_html}

{"" if is_draft else f"<div class='sig-block'><div class='sig-col'><div class='sig-name'>{html.escape(report_data.get('reviewed_by') or 'Signing Radiologist')}</div><div class='sig-sub'>Electronically Verified Clinical Sign-Off</div></div></div>"}

{bottom_status_block}
</body>
</html>
"""
