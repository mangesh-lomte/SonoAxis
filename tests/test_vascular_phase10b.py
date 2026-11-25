import os
import io
import docx
import pytest
from typing import Dict, Any

from backend.app.structuring.templates import TEMPLATES_CATALOG, get_template_def, STANDARD_ARTERIAL_SEGMENTS
from backend.app.structuring.vascular import (
    parse_incompetent_perforators, parse_arterial_biometry,
    format_arterial_table_text, format_perforators_text
)
from backend.app.structuring.engine import structuring_engine
from backend.app.export.word_service import WordExportService, FORBIDDEN_PLACEHOLDERS
from backend.app.export.preview_service import PreviewService


def test_all_16_templates_registered():
    """Verify that all 16 templates across the 4 examination families are registered."""
    expected_ids = [
        "usg-abdomen-pelvis-male",
        "usg-abdomen-pelvis-female",
        "usg-doppler-venous-left-varicose",
        "usg-doppler-venous-right-varicose",
        "usg-doppler-venous-left-thrombosis",
        "usg-doppler-venous-bilateral-normal",
        "usg-doppler-venous-bilateral-varicose",
        "usg-doppler-venous-bilateral-detailed",
        "usg-doppler-venous-right-dvt",
        "usg-doppler-venous-right-normal",
        "usg-doppler-arterial-right-normal",
        "usg-doppler-arterial-bilateral-normal",
        "usg-doppler-arterial-bilateral-thrombus",
        "usg-doppler-arterial-right-pvd",
        "usg-doppler-av-right",
        "usg-doppler-av-bilateral-thrombosis"
    ]
    assert len(TEMPLATES_CATALOG) == 16
    for t_id in expected_ids:
        assert t_id in TEMPLATES_CATALOG, f"Missing template {t_id}"
        t_def = get_template_def(t_id)
        assert len(t_def["sections"]) > 0
        assert t_def["category"] in ["abdomen_pelvis", "venous_doppler", "arterial_doppler", "arteriovenous_doppler"]


def test_template_files_exist_on_disk():
    """Verify that each registered template resolves to an actual .docx file on disk."""
    for t_id, t_def in TEMPLATES_CATALOG.items():
        resolved_path = WordExportService._resolve_template_path(t_id, "references")
        assert os.path.exists(resolved_path), f"File not found for {t_id}: {resolved_path}"


def test_incompetent_perforators_parsing():
    """Verify repeatable multi-site incompetent perforator parsing."""
    clauses = [
        "Left leg:",
        "3.6 mm sized about 10 cm above ankle on lateral aspect.",
        "3.9 mm sized near ankle on lateral aspect.",
        "2.7 mm sized about 5 cm below knee on lateral aspect.",
        "3.0 mm sized about 5 cm below knee on posterior aspect.",
        "2.7 mm sized about 7 cm above ankle on medial aspect.",
        "Right leg:",
        "3 mm sized about 10 cm below knee on medial aspect."
    ]
    perfs = parse_incompetent_perforators(clauses, default_laterality="bilateral")
    assert len(perfs) == 6

    # Verify first left perforator
    p0 = perfs[0]
    assert p0.laterality == "left"
    assert p0.diameter_mm == 3.6
    assert p0.distance_cm == 10.0
    assert p0.landmark == "above ankle"
    assert p0.aspect == "lateral"

    # Verify right leg perforator
    p_rt = [p for p in perfs if p.laterality == "right"]
    assert len(p_rt) == 1
    assert p_rt[0].diameter_mm == 3.0
    assert p_rt[0].distance_cm == 10.0
    assert p_rt[0].aspect == "medial"

    # Verify formatted text block
    formatted = format_perforators_text(perfs, laterality="bilateral")
    assert "Left Lower Limb:" in formatted
    assert "Right Lower Limb:" in formatted
    assert "3.6 mm about 10 cm above ankle on lateral aspect" in formatted


def test_arterial_biometry_parsing():
    """Verify segment-by-segment and batch arterial waveforms and PSV."""
    clauses = [
        "All bilateral lower limb arteries show normal triphasic flow pattern.",
        "Common femoral artery right 130 triphasic, left 124 triphasic.",
        "Superficial femoral artery right 107 triphasic, left 95.9 triphasic.",
        "Anterior tibial artery right 61.5 triphasic, left 27 monophasic.",
        "Left popliteal artery shows monophasic damped flow with PSV 22 cm per second."
    ]
    biom = parse_arterial_biometry(clauses, laterality="bilateral")
    assert len(biom) == len(STANDARD_ARTERIAL_SEGMENTS)

    biom_dict = {b.segment_key: b for b in biom}

    # CFA
    assert biom_dict["cfa"].psv_right == 130.0
    assert biom_dict["cfa"].psv_left == 124.0
    assert biom_dict["cfa"].flow_pattern_right == "Triphasic"
    assert biom_dict["cfa"].flow_pattern_left == "Triphasic"

    # SFA
    assert biom_dict["sfa"].psv_right == 107.0
    assert biom_dict["sfa"].psv_left == 95.9

    # ATA
    assert biom_dict["ata"].flow_pattern_left == "Monophasic"
    assert biom_dict["ata"].psv_left == 27.0

    # Popliteal
    assert biom_dict["popliteal"].flow_pattern_left == "Monophasic"
    assert biom_dict["popliteal"].psv_left == 22.0

    # Formatted tables
    tbl_5col = format_arterial_table_text(biom, table_type="arterial_5col_table", laterality="bilateral")
    assert "Common femoral artery" in tbl_5col
    assert "130.00" in tbl_5col
    assert "124.00" in tbl_5col

    tbl_3col = format_arterial_table_text(biom, table_type="arterial_3col_table", laterality="right")
    assert "130.00" in tbl_3col


def test_vascular_structuring_workflow():
    """Verify end-to-end vascular transcript structuring."""
    transcript = (
        "Clinical profile: Bilateral lower limb swelling. "
        "The bilateral common femoral, superficial femoral and popliteal veins show normal wall, lumen and flow pattern. "
        "No segment of venous thrombosis noted. "
        "Saphenofemoral junction appears competent. "
        "Great saphenous vein measures 8 mm in thigh. "
        "Incompetent perforators noted: 6 mm about 5 cm below knee, and 5.2 mm in mid leg. "
        "Impression: Hemodynamically normal deep venous system. Dilated GSV with incompetent perforators. "
        "ADV: Clinical correlation suggested."
    )
    report = structuring_engine.structure_transcript(
        transcript,
        template_id="usg-doppler-venous-bilateral-detailed"
    )

    assert report.template_id == "usg-doppler-venous-bilateral-detailed"
    assert report.category == "venous_doppler"
    assert report.impression == "Hemodynamically normal deep venous system. Dilated GSV with incompetent perforators."
    assert "Bilateral lower limb swelling" in report.clinical_profile
    assert "Clinical correlation suggested" in report.recommendations

    # Perforators captured in vascular biometry
    assert report.vascular_biometry is not None
    assert len(report.vascular_biometry.incompetent_perforators) >= 2


def test_incompatible_anatomy_flagging_in_vascular():
    """Verify that abdominal organs dictated in a vascular study flag as incompatible."""
    transcript = (
        "Liver is 14 cm normal. "
        "Common femoral vein is normal."
    )
    report = structuring_engine.structure_transcript(
        transcript,
        template_id="usg-doppler-venous-bilateral-normal"
    )
    # Liver should be in unassigned findings as incompatible anatomy
    unassigned_reasons = [u.reason for u in report.unassigned_findings]
    assert any("incompatible_anatomy" in r for r in unassigned_reasons)
    assert report.has_flags is True


def test_word_export_all_16_templates():
    """Verify that Word export succeeds across all 16 templates and strips all placeholders."""
    dummy_report = {
        "template_id": "usg-doppler-arterial-bilateral-normal",
        "report_number": "REP-2026-TEST",
        "report_date": "2026-11-24",
        "status": "DRAFT",
        "patient_snapshot": {
            "patient_id": "PAT-9999",
            "full_name": "Test Patient",
            "age_years": 52,
            "gender": "Male",
            "referral_doctor": "Dr. Referral Surgeon"
        },
        "structured_findings": {
            "sections": [
                {
                    "key": "arterial_findings",
                    "label": "Arterial Findings",
                    "heading": "Arterial Flow & Waveforms: ",
                    "is_present": True,
                    "text": "Bilateral lower limb arteries show triphasic flow pattern."
                }
            ],
            "impression": "Normal bilateral arterial Doppler study.",
            "recommendations": "No further vascular intervention required.",
            "vascular_biometry": {
                "arterial_table": [
                    {
                        "segment_key": "cfa",
                        "segment_name": "Common femoral artery",
                        "psv_right": 58.74,
                        "psv_left": 60.43,
                        "flow_pattern_right": "Triphasic",
                        "flow_pattern_left": "Triphasic"
                    }
                ]
            }
        }
    }

    # Test export for all 16 template IDs
    for t_id in TEMPLATES_CATALOG:
        dummy_report["template_id"] = t_id
        docx_bytes = WordExportService.generate_docx(dummy_report, references_dir="references")
        assert len(docx_bytes) > 1000, f"Export too small for {t_id}"

        # Verify output docx contains NO forbidden placeholders
        doc = docx.Document(io.BytesIO(docx_bytes))
        full_text = " ".join(p.text for p in doc.paragraphs)
        for t in doc.tables:
            for r in t.rows:
                full_text += " " + " ".join(c.text for c in r.cells)

        for ph in FORBIDDEN_PLACEHOLDERS:
            assert ph not in full_text, f"Forbidden placeholder '{ph}' leaked in {t_id} export!"


def test_preview_html_all_16_templates():
    """Verify that HTML preview renders without placeholder leakage for all 16 templates."""
    dummy_report = {
        "template_id": "usg-doppler-venous-bilateral-varicose",
        "report_number": "REP-2026-HTML",
        "report_date": "2026-11-24",
        "status": "DRAFT",
        "patient_name": "Preview Patient",
        "structured_findings": {
            "sections": [
                {
                    "key": "gsv",
                    "label": "Great Saphenous Vein",
                    "heading": "Great Saphenous Vein (GSV): ",
                    "is_present": True,
                    "text": "Bilateral GSV dilated."
                }
            ],
            "impression": "Bilateral varicose veins.",
            "recommendations": "Surgical evaluation."
        }
    }

    for t_id in TEMPLATES_CATALOG:
        dummy_report["template_id"] = t_id
        html_out = PreviewService.render_html(dummy_report)
        assert len(html_out) > 500
        assert "DRAFT" in html_out.upper()
        assert "Chief Radiologist" not in html_out
        for ph in FORBIDDEN_PLACEHOLDERS:
            assert ph not in html_out, f"Placeholder {ph} leaked in HTML preview for {t_id}"

    # Reviewed state renders signing radiologist name without real doctor leakage
    reviewed_dummy = dict(dummy_report, status="REVIEWED", is_reviewed=True, reviewed_by="Dr. Pytest Radiologist", reviewed_at="2026-11-24")
    reviewed_html = PreviewService.render_html(reviewed_dummy)
    assert "Dr. Pytest Radiologist" in reviewed_html
