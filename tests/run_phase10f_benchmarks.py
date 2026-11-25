import os
import sys
sys.path.insert(0, os.path.abspath("."))
import time
import json
import ctypes
import io
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.schema import init_db
from backend.app.services.speech_service import SpeechRecognitionService
from backend.app.structuring.engine import structuring_engine
from backend.app.ocr.engine import UltrasoundOCREngine
from backend.app.services.template_service import TemplateService
from backend.app.export.word_service import WordExportService
from backend.app.export.pdf_service import PDFExportService
from backend.app.services.report_service import ReportService
from backend.app.services.patient_service import PatientService

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]

def get_avail_ram_mb():
    try:
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return round(stat.ullAvailPhys / (1024 * 1024), 2)
    except Exception:
        return 0.0

def run_all_benchmarks():
    client = TestClient(app)
    results = {}
    init_ram = get_avail_ram_mb()
    results["initial_available_ram_mb"] = init_ram

    # 1. Database & App Startup Time
    t0 = time.time()
    init_db()
    results["db_init_latency_ms"] = round((time.time() - t0) * 1000, 2)

    # 2. Page Loading Performance (SPA & API)
    t0 = time.time()
    r = client.get("/")
    assert r.status_code == 200
    results["page_load_spa_ms"] = round((time.time() - t0) * 1000, 2)

    t0 = time.time()
    r = client.get("/api/health")
    assert r.status_code == 200
    results["api_health_latency_ms"] = round((time.time() - t0) * 1000, 2)

    # 3. Report Structuring Latency
    struct_transcripts = {
        "male_abdomen": "Liver is normal in size and echotexture measuring 14.2 cm. Spleen is normal. Right kidney measures 10.8 by 4.5 cm. Left kidney measures 9.8 by 4.2 cm. Prostate measures 4.0 by 3.0 by 3.4 cm. IMPRESSION: Normal study.",
        "female_pelvis": "Uterus is anteverted measuring 7.5 by 4.2 by 3.8 cm. Endometrium double layer thickness is 7.2 mm. Right ovary measures 3.2 by 2.1 by 1.8 cm. Left ovary measures 2.8 by 1.9 by 1.5 cm. No free fluid. IMPRESSION: Normal pelvic ultrasound.",
        "arterial_doppler": "Right CFA PSV is 85 cm per second with triphasic flow. Right SFA PSV is 78 cm per second. Left CFA PSV is 82 cm per second. Left SFA PSV is 75 cm per second. Brachial pressure is 120 mmHg. Right DP pressure is 115 mmHg. Left DP pressure is 114 mmHg.",
        "venous_doppler": "Great saphenous vein shows incompetent saphenofemoral junction. Mid-calf incompetent perforator noted measuring 3.8 mm, 12 cm above medial malleolus. Deep veins compressible."
    }

    results["structuring_latency_ms"] = {}
    for k, text in struct_transcripts.items():
        t0 = time.time()
        struct_res = structuring_engine.structure_transcript(text, template_id="usg-abdomen-pelvis-male" if "male" in k else "usg-abdomen-pelvis-female" if "female" in k else "usg-doppler-arterial-bilateral" if "arterial" in k else "usg-doppler-venous-left-varicose")
        results["structuring_latency_ms"][k] = round((time.time() - t0) * 1000, 2)

    # 4. OCR Extraction Latency
    ocr_fixtures = [
        ("test_a_abdomen", "tests/fixtures/ocr/test_a_abdomen.png"),
        ("test_b_female_pelvis", "tests/fixtures/ocr/test_b_female_pelvis.png"),
        ("test_c_bilateral_arterial", "tests/fixtures/ocr/test_c_bilateral_arterial.png"),
        ("test_d_venous_perforators", "tests/fixtures/ocr/test_d_venous_perforators.png")
    ]
    ocr_engine = UltrasoundOCREngine()
    results["ocr_extraction_latency_ms"] = {}
    for name, path in ocr_fixtures:
        if os.path.exists(path):
            with open(path, "rb") as f:
                img_bytes = f.read()
            t0 = time.time()
            ocr_res = ocr_engine.process_and_extract("perf_report_id", os.path.basename(path), img_bytes)
            results["ocr_extraction_latency_ms"][name] = round((time.time() - t0) * 1000, 2)

    # 5. Template Import Latency
    sample_template_path = "references/sanitized_templates/abd male-new.docx"
    if os.path.exists(sample_template_path):
        with open(sample_template_path, "rb") as f:
            docx_bytes = f.read()
        t0 = time.time()
        structure = TemplateService.extract_docx_structure(docx_bytes, "abd male-new.docx")
        results["template_import_latency_ms"] = round((time.time() - t0) * 1000, 2)

    # 6. Patient & Report Creation for Export Benchmarks
    patient = PatientService.create_patient({
        "patient_id": f"PT-PERF-{int(time.time())}",
        "full_name": "Performance Test",
        "gender": "Male",
        "age_years": 45
    })
    report = ReportService.create_report({
        "template_id": "usg-abdomen-pelvis-male",
        "patient_id": patient["id"],
        "referral_doctor": "Dr. Benchmark"
    })
    # Update with findings
    ReportService.update_report(report["id"], {
        "structured_findings": {
            "sections": [
                {"order": 1, "key": "liver", "label": "Liver", "heading": "Liver: ", "text": "Liver is normal in size and echotexture measuring 14.2 cm.", "is_present": True},
                {"order": 7, "key": "right_kidney", "label": "Right Kidney", "heading": "Right Kidney: ", "text": "Right kidney measures 10.8 x 4.5 cm.", "is_present": True},
                {"order": 8, "key": "left_kidney", "label": "Left Kidney", "heading": "Left Kidney: ", "text": "Left kidney measures 9.8 x 4.2 cm.", "is_present": True},
                {"order": 11, "key": "prostate", "label": "Prostate", "heading": "Prostate: ", "text": "Prostate measures 4.0 x 3.0 x 3.4 cm.", "is_present": True}
            ],
            "impression": "Normal study."
        },
        "impression": "Normal study."
    })
    full_report = ReportService.get_report(report["id"])

    # 7. Word Export Latency
    t0 = time.time()
    docx_bytes = WordExportService.generate_docx(full_report)
    results["word_export_latency_ms"] = round((time.time() - t0) * 1000, 2)
    results["word_export_size_bytes"] = len(docx_bytes)

    # 8. PDF Export Latency
    t0 = time.time()
    pdf_bytes = PDFExportService.generate_pdf(full_report)
    results["pdf_export_latency_ms"] = round((time.time() - t0) * 1000, 2)
    results["pdf_export_size_bytes"] = len(pdf_bytes)

    # 9. RAM Memory Delta
    post_ram = get_avail_ram_mb()
    results["final_available_ram_mb"] = post_ram
    results["net_ram_delta_mb"] = round(init_ram - post_ram, 2)

    print(json.dumps(results, indent=2))
    return results

if __name__ == "__main__":
    run_all_benchmarks()
