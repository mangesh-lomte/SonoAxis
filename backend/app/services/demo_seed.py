from datetime import datetime, timezone, timedelta
from typing import Optional

from backend.app.db.connection import get_db
from backend.app.db.schema import init_db
from backend.app.services.patient_service import PatientService
from backend.app.services.report_service import ReportService
from backend.app.structuring.engine import structuring_engine


DEMO_PATIENTS = [
    {
        "patient_id": "MRN-2026-1041",
        "full_name": "Aarav Mehta",
        "age_years": 42,
        "gender": "Male",
        "contact_number": "+91 90000 00001",
        "clinical_notes": "[Demo] Routine right upper quadrant abdominal evaluation",
    },
    {
        "patient_id": "MRN-2026-1042",
        "full_name": "Priya Kulkarni",
        "age_years": 34,
        "gender": "Female",
        "contact_number": "+91 90000 00002",
        "clinical_notes": "[Demo] Lower abdominal & pelvic sonography for pelvic pain",
    },
    {
        "patient_id": "MRN-2026-1043",
        "full_name": "Suresh Iyer",
        "age_years": 58,
        "gender": "Male",
        "contact_number": "+91 90000 00003",
        "clinical_notes": "[Demo] Bilateral calf claudication assessment",
    },
    {
        "patient_id": "MRN-2026-1044",
        "full_name": "Meera Krishnan",
        "age_years": 47,
        "gender": "Female",
        "contact_number": "+91 90000 00004",
        "clinical_notes": "[Demo] Left lower limb superficial varicosity & perforator evaluation",
    },
    {
        "patient_id": "MRN-2026-1045",
        "full_name": "Rohan Deshpande",
        "age_years": 63,
        "gender": "Male",
        "contact_number": "+91 90000 00005",
        "clinical_notes": "[Demo] Prostatic evaluation & post-void residual assessment",
    },
    {
        "patient_id": "MRN-2026-1046",
        "full_name": "Ananya Sen",
        "age_years": 29,
        "gender": "Female",
        "contact_number": "+91 90000 00006",
        "clinical_notes": "[Demo] Baseline abdominal and adnexal screening",
    },
]


def reset_and_seed_clean_demo_db(db_path: Optional[str] = None) -> dict:
    """
    Cleans synthetic test clutter from SQLite and populates six properly registered
    fictional demonstration patients and studies, attributed solely to the fictional
    Radiologist demo account ('Dr. Aarav Sharma', with zero fabricated credentials).
    Preserves all 16 institutional built-in templates intact.
    """
    init_db(db_path)

    with get_db(db_path) as conn:
        conn.execute("DELETE FROM structured_findings")
        conn.execute("DELETE FROM unassigned_findings")
        conn.execute("DELETE FROM report_revisions")
        conn.execute("DELETE FROM audio_recordings")
        conn.execute("DELETE FROM reports")
        conn.execute("DELETE FROM patients")
        # Remove test-generated custom templates (verified carotid-doppler-test duplicates)
        conn.execute("DELETE FROM examination_templates WHERE is_built_in = 0")

    created_patients = {}
    for p_data in DEMO_PATIENTS:
        p = PatientService.create_patient(p_data, db_path=db_path)
        created_patients[p_data["patient_id"]] = p

    today = datetime.now(timezone.utc)
    d0 = today.strftime("%Y-%m-%d")
    d1 = (today - timedelta(days=1)).strftime("%Y-%m-%d")

    sample_studies = [
        {
            "mrn": "MRN-2026-1041",
            "template_id": "usg-abdomen-pelvis-male",
            "report_date": d1,
            "referral_doctor": "Dr. Rajeshwari Nair (Demo Referral)",
            "transcript": (
                "Liver is normal in size measuring 14.1 cm with homogeneous echotexture and no focal lesion. "
                "Gall bladder is well distended with normal wall thickness measuring 2.0 mm, no calculi seen. "
                "Common bile duct measures 4.0 mm. Pancreas appears normal. Spleen measures 10.8 cm. "
                "Right kidney measures 10.6 by 4.4 cm and left kidney measures 9.9 by 4.2 cm with preserved corticomedullary differentiation. "
                "Urinary bladder is well distended with normal wall thickness. Prostate measures 3.8 by 3.0 by 3.2 cm. "
                "Impression: Normal abdominal and pelvic ultrasound study."
            ),
            "review_by": "Dr. Aarav Sharma",
        },
        {
            "mrn": "MRN-2026-1042",
            "template_id": "usg-abdomen-pelvis-female",
            "report_date": d1,
            "referral_doctor": "Dr. Vikram Deshmukh (Demo Referral)",
            "transcript": (
                "Liver measures 13.8 cm and is normal in echogenicity. Gall bladder is normal without calculi. "
                "Right kidney measures 10.4 by 4.3 cm. Left kidney measures 9.7 by 4.1 cm. "
                "Uterus is anteverted measuring 6.8 by 3.5 by 4.6 cm with normal myometrial echotexture. "
                "Endometrial thickness measures 6.2 mm. Both ovaries appear normal with physiological follicles. "
                "Impression: Unremarkable female pelvic and abdominal sonography."
            ),
            "review_by": "Dr. Aarav Sharma",
        },
        {
            "mrn": "MRN-2026-1043",
            "template_id": "usg-doppler-arterial-bilateral-normal",
            "report_date": d0,
            "referral_doctor": "Dr. Anand Rao (Demo Referral)",
            "transcript": (
                "Bilateral common femoral, superficial femoral, popliteal, anterior tibial, posterior tibial, and dorsalis pedis arteries "
                "are patent with normal color flow and triphasic spectral waveforms. No hemodynamically significant stenosis."
            ),
            "review_by": "Dr. Aarav Sharma",
        },
        {
            "mrn": "MRN-2026-1044",
            "template_id": "usg-doppler-venous-left-varicose",
            "report_date": d0,
            "referral_doctor": "Dr. Kavita Joshi (Demo Referral)",
            "transcript": (
                "Left common femoral, superficial femoral, popliteal, and calf deep veins show normal luminal compressibility "
                "and spontaneous phasic flow. Saphenofemoral junction is competent with no deep venous thrombosis."
            ),
            "review_by": None,
        },
        {
            "mrn": "MRN-2026-1045",
            "template_id": "usg-abdomen-pelvis-male",
            "report_date": d0,
            "referral_doctor": "Dr. Sanjay Gupta (Demo Referral)",
            "transcript": (
                "Liver measures 14.4 cm. Gall bladder shows normal wall thickness. Common bile duct measures 4.2 mm. "
                "Right kidney measures 10.9 by 4.6 cm and left kidney measures 10.0 by 4.3 cm. "
                "Prostate measures 4.2 by 3.3 by 3.6 cm. Post void residual urine measures 24 ml."
            ),
            "review_by": None,
        },
        {
            "mrn": "MRN-2026-1046",
            "template_id": "usg-abdomen-pelvis-female",
            "report_date": d0,
            "referral_doctor": "Dr. Sunita Menon (Demo Referral)",
            "transcript": (
                "Liver measures 13.5 cm with normal echogenicity. Gall bladder and CBD appear normal. "
                "Both kidneys are normal in size and cortical echogenicity. Uterus is normal measuring 6.4 by 3.2 by 4.4 cm."
            ),
            "review_by": None,
        },
    ]

    created_reports = []
    for st in sample_studies:
        pat = created_patients[st["mrn"]]
        rep = ReportService.create_report(
            {
                "template_id": st["template_id"],
                "patient_id": pat["id"],
                "report_date": st["report_date"],
                "referral_doctor": st["referral_doctor"],
            },
            db_path=db_path,
        )
        structured = structuring_engine.structure_transcript(
            transcript=st["transcript"],
            template_id=st["template_id"],
            transcript_source="typed_transcript",
        )
        rep_updated = ReportService.update_report(
            rep["id"],
            {
                "original_transcript": st["transcript"],
                "edited_transcript": st["transcript"],
                "structured_findings": structured.model_dump(),
                "impression": structured.impression,
            },
            change_type="INITIAL_CLINICAL_SEED",
            changed_by=st["review_by"] or "Dr. Aarav Sharma",
            db_path=db_path,
        )
        if st["review_by"]:
            rep_updated = ReportService.mark_reviewed(
                report_id=rep["id"],
                reviewed_by=st["review_by"],
                acknowledge_unresolved=True,
                db_path=db_path,
            )
        created_reports.append(rep_updated["id"])

    return {
        "patients_count": len(created_patients),
        "reports_count": len(created_reports),
    }
