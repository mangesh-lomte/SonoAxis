import io
import time
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.main import app
from backend.app.structuring.calculations import calculate_ankle_brachial_index
from backend.app.ocr.preprocessing import validate_image_file, preprocess_ultrasound_image
from backend.app.ocr.engine import ocr_engine
from backend.app.export.word_service import WordExportService
from backend.app.export.pdf_service import PDFExportService

FIXTURES_DIR = Path("D:/sovoice/tests/fixtures/ocr")

def test_01_valid_image_upload_and_preprocessing(client):
    """
    Verifies valid image validation, local storage, and preprocessing (grayscale, contrast, Otsu).
    """
    fixture_path = FIXTURES_DIR / "test_a_abdomen.png"
    assert fixture_path.exists(), f"Missing fixture: {fixture_path}"

    with open(fixture_path, "rb") as f:
        file_bytes = f.read()

    # Create temporary report
    rep_res = client.post("/api/reports", json={
        "template_id": "usg-abdomen-pelvis-male"
    })
    assert rep_res.status_code in [200, 201]
    report_id = rep_res.json()["id"]

    # Upload
    files = {"file": ("test_a_abdomen.png", file_bytes, "image/png")}
    data = {"rotate": 0}
    up_res = client.post(f"/api/reports/{report_id}/ocr/upload", files=files, data=data)
    assert up_res.status_code == 200, up_res.text
    payload = up_res.json()

    assert payload["source_document_id"].startswith("doc-ocr-")
    assert "grayscale" in payload["preprocessing_applied"]
    assert any("otsu_threshold" in s for s in payload["preprocessing_applied"])
    assert payload["execution_time_ms"] > 0
    assert len(payload["candidates"]) == 4

def test_02_invalid_and_oversized_image_rejection(client):
    """
    Verifies security boundary: rejects corrupted files, non-images, and payloads > 15MB.
    """
    rep_res = client.post("/api/reports", json={
        "template_id": "usg-abdomen-pelvis-male"
    })
    report_id = rep_res.json()["id"]

    # Corrupted / text file disguised as PNG
    fake_png = b"NOT_A_REAL_PNG_HEADER_DATA_1234567890"
    files = {"file": ("malicious.png", fake_png, "image/png")}
    res_bad = client.post(f"/api/reports/{report_id}/ocr/upload", files=files)
    assert res_bad.status_code == 400
    assert "invalid image" in res_bad.json()["detail"].lower()

    # Oversized payload (> 15 MB)
    oversized_bytes = b"0" * (15 * 1024 * 1024 + 1024)
    files_over = {"file": ("huge.png", oversized_bytes, "image/png")}
    res_over = client.post(f"/api/reports/{report_id}/ocr/upload", files=files_over)
    assert res_over.status_code == 400
    assert "exceeds maximum permitted size" in res_over.json()["detail"].lower()

def test_03_test_a_abdominal_measurements_extraction(client):
    """
    Mandatory Test A: Abdominal measurements
    - Liver: 14.2 cm
    - Right kidney: 10.8 x 4.5 cm
    - Left kidney: 9.8 x 4.2 cm
    - Prostate: 4.0 x 3.0 x 3.4 cm
    """
    fixture_path = FIXTURES_DIR / "test_a_abdomen.png"
    with open(fixture_path, "rb") as f:
        file_bytes = f.read()

    rep_res = client.post("/api/reports", json={
        "template_id": "usg-abdomen-pelvis-male"
    })
    report_id = rep_res.json()["id"]

    files = {"file": ("test_a_abdomen.png", file_bytes, "image/png")}
    res = client.post(f"/api/reports/{report_id}/ocr/upload", files=files)
    assert res.status_code == 200
    cands = res.json()["candidates"]

    by_label = {c["anatomical_label"]: c for c in cands}
    assert "Liver" in by_label
    assert by_label["Liver"]["value"] == 14.2
    assert by_label["Liver"]["dimension"] == 1
    assert by_label["Liver"]["normalized_unit"] == "cm"
    assert by_label["Liver"]["proposed_destination_field"] == "liver"

    assert "Right Kidney" in by_label
    assert by_label["Right Kidney"]["value"] == [10.8, 4.5]
    assert by_label["Right Kidney"]["dimension"] == 2
    assert by_label["Right Kidney"]["laterality"] == "right"
    assert by_label["Right Kidney"]["proposed_destination_field"] == "right_kidney"

    assert "Left Kidney" in by_label
    assert by_label["Left Kidney"]["value"] == [9.8, 4.2]
    assert by_label["Left Kidney"]["dimension"] == 2
    assert by_label["Left Kidney"]["laterality"] == "left"
    assert by_label["Left Kidney"]["proposed_destination_field"] == "left_kidney"

    assert "Prostate" in by_label
    assert by_label["Prostate"]["value"] == [4.0, 3.0, 3.4]
    assert by_label["Prostate"]["dimension"] == 3
    assert by_label["Prostate"]["proposed_destination_field"] == "prostate"

def test_04_test_b_female_pelvic_measurements_extraction(client):
    """
    Mandatory Test B: Female pelvic measurements
    - Uterus: 6.5 x 3.3 x 4.7 cm
    - Endometrial thickness: 5 mm
    - Right ovary: 3.2 x 2.4 cm
    """
    fixture_path = FIXTURES_DIR / "test_b_female_pelvis.png"
    with open(fixture_path, "rb") as f:
        file_bytes = f.read()

    rep_res = client.post("/api/reports", json={
        "template_id": "usg-abdomen-pelvis-female"
    })
    report_id = rep_res.json()["id"]

    files = {"file": ("test_b_female_pelvis.png", file_bytes, "image/png")}
    res = client.post(f"/api/reports/{report_id}/ocr/upload", files=files)
    assert res.status_code == 200
    cands = res.json()["candidates"]

    by_label = {c["anatomical_label"]: c for c in cands}
    assert "Uterus" in by_label
    assert by_label["Uterus"]["value"] == [6.5, 3.3, 4.7]
    assert by_label["Uterus"]["dimension"] == 3

    assert "Endometrial Thickness" in by_label
    assert by_label["Endometrial Thickness"]["value"] == 5.0
    assert by_label["Endometrial Thickness"]["normalized_unit"] == "mm"

    assert "Right Ovary" in by_label
    assert by_label["Right Ovary"]["value"] == [3.2, 2.4]
    assert by_label["Right Ovary"]["laterality"] == "right"

def test_05_test_c_bilateral_arterial_measurements_extraction(client):
    """
    Mandatory Test C: Bilateral arterial measurements
    - Right CFA PSV: 98.4 cm/s (triphasic)
    - Left CFA PSV: 87.6 cm/s (triphasic)
    - Right popliteal PSV: 72.5 cm/s (biphasic)
    - Left popliteal PSV: 42.3 cm/s (biphasic)
    """
    fixture_path = FIXTURES_DIR / "test_c_bilateral_arterial.png"
    with open(fixture_path, "rb") as f:
        file_bytes = f.read()

    rep_res = client.post("/api/reports", json={
        "template_id": "usg-doppler-arterial-bilateral-normal"
    })
    report_id = rep_res.json()["id"]

    files = {"file": ("test_c_bilateral_arterial.png", file_bytes, "image/png")}
    res = client.post(f"/api/reports/{report_id}/ocr/upload", files=files)
    assert res.status_code == 200
    cands = res.json()["candidates"]

    # Verify right CFA
    rcfa = next(c for c in cands if c["laterality"] == "right" and "cfa" in c["proposed_destination_field"])
    assert rcfa["value"] == 98.4
    assert rcfa["waveform"] == "triphasic"
    assert rcfa["normalized_unit"] == "cm/s"

    # Verify left CFA
    lcfa = next(c for c in cands if c["laterality"] == "left" and "cfa" in c["proposed_destination_field"])
    assert lcfa["value"] == 87.6
    assert lcfa["waveform"] == "triphasic"

    # Verify right popliteal
    rpop = next(c for c in cands if c["laterality"] == "right" and "popliteal" in c["proposed_destination_field"])
    assert rpop["value"] == 72.5
    assert rpop["waveform"] == "biphasic"

    # Verify left popliteal
    lpop = next(c for c in cands if c["laterality"] == "left" and "popliteal" in c["proposed_destination_field"])
    assert lpop["value"] == 42.3
    assert lpop["waveform"] == "biphasic"

def test_06_test_d_venous_measurements_and_perforators(client):
    """
    Mandatory Test D: Venous measurements
    - Right GSV: 8.2 mm
    - Left GSV: 6.4 mm
    - Right perforator: 3.2 mm
    - Second right perforator: 4.1 mm
    Verifies repeated findings remain separate!
    """
    fixture_path = FIXTURES_DIR / "test_d_venous_perforators.png"
    with open(fixture_path, "rb") as f:
        file_bytes = f.read()

    rep_res = client.post("/api/reports", json={
        "template_id": "usg-doppler-venous-bilateral-normal"
    })
    report_id = rep_res.json()["id"]

    files = {"file": ("test_d_venous_perforators.png", file_bytes, "image/png")}
    res = client.post(f"/api/reports/{report_id}/ocr/upload", files=files)
    assert res.status_code == 200
    cands = res.json()["candidates"]

    # Verify GSV separation
    rgsv = next(c for c in cands if c["laterality"] == "right" and "gsv" in c["proposed_destination_field"])
    assert rgsv["value"] == 8.2
    assert rgsv["normalized_unit"] == "mm"

    lgsv = next(c for c in cands if c["laterality"] == "left" and "gsv" in c["proposed_destination_field"])
    assert lgsv["value"] == 6.4
    assert lgsv["normalized_unit"] == "mm"

    # Verify repeated perforators remain separate
    perforators = [c for c in cands if "perforator" in c["proposed_destination_field"]]
    assert len(perforators) == 2
    p_values = sorted([p["value"] for p in perforators])
    assert p_values == [3.2, 4.1]
    assert perforators[0]["proposed_destination_field"] != perforators[1]["proposed_destination_field"]

def test_07_test_e_difficult_and_uncertain_extractions(client):
    """
    Mandatory Test E: Difficult extractions
    - Ambiguous label: Kidney 10.2 cm -> requires manual verification
    - Missing unit: Liver: 14.5 -> requires manual verification
    - Unknown anatomical label: Unknown Structure: 3.4 mm -> mapped to unassigned
    """
    fixture_path = FIXTURES_DIR / "test_e_ambiguous_labels.png"
    with open(fixture_path, "rb") as f:
        file_bytes = f.read()

    rep_res = client.post("/api/reports", json={
        "template_id": "usg-abdomen-pelvis-male"
    })
    report_id = rep_res.json()["id"]

    files = {"file": ("test_e_ambiguous_labels.png", file_bytes, "image/png")}
    res = client.post(f"/api/reports/{report_id}/ocr/upload", files=files)
    assert res.status_code == 200
    cands = res.json()["candidates"]

    # Kidney without laterality
    ambig_k = next(c for c in cands if "kidney" in c["anatomical_label"].lower())
    assert ambig_k["is_uncertain"] is True
    assert "laterality" in ambig_k["uncertainty_reason"].lower()

    # Missing unit
    missing_u = next(c for c in cands if "liver" in c["anatomical_label"].lower())
    assert missing_u["is_uncertain"] is True
    assert "unit" in missing_u["uncertainty_reason"].lower()

    # Unknown label
    unkn = next(c for c in cands if c["proposed_destination_field"] == "unassigned")
    assert unkn["is_uncertain"] is True
    assert "unknown" in unkn["uncertainty_reason"].lower()

def test_08_conflict_resolution_and_audit_history(client):
    """
    Mandatory Conflict Resolution:
    Existing dictated Right Kidney length: 10.8 cm
    Extracted machine printout value: 10.6 cm
    User chooses 'use_extracted' -> replaces value and records 10.8 cm in correction_history.
    """
    rep_res = client.post("/api/reports", json={
        "template_id": "usg-abdomen-pelvis-male"
    })
    report_id = rep_res.json()["id"]

    # Initial dictation
    struct_res = client.post("/api/structuring/process", json={
        "template_id": "usg-abdomen-pelvis-male",
        "transcript": "Right kidney measures 10.2 by 4.5 cm."
    })
    assert struct_res.status_code == 200
    client.put(f"/api/reports/{report_id}", json={
        "structured_findings": struct_res.json()
    })

    # Upload printout with conflicting value (10.8 x 4.5 cm vs 10.2 x 4.5 cm)
    fixture_path = FIXTURES_DIR / "test_a_abdomen.png"
    with open(fixture_path, "rb") as f:
        file_bytes = f.read()

    files = {"file": ("test_a_abdomen.png", file_bytes, "image/png")}
    up_res = client.post(f"/api/reports/{report_id}/ocr/upload", files=files)
    assert up_res.status_code == 200
    cands = up_res.json()["candidates"]

    rk_cand = next(c for c in cands if c["proposed_destination_field"] == "right_kidney")
    assert rk_cand["has_conflict"] is True
    assert rk_cand["existing_value"] is not None

    # Confirm with use_extracted
    confirm_payload = {
        "source_document_id": up_res.json()["source_document_id"],
        "items": [
            {
                "measurement_id": rk_cand["measurement_id"],
                "destination_field": "right_kidney",
                "anatomical_label": "Right Kidney",
                "value": [10.8, 4.5],
                "unit": "cm",
                "dimension": 2,
                "conflict_resolution": "use_extracted",
                "status": "approved"
            }
        ]
    }
    conf_res = client.post(f"/api/reports/{report_id}/ocr/confirm", json=confirm_payload)
    assert conf_res.status_code == 200
    updated_rep = conf_res.json()

    sec_map = {s["key"]: s for s in updated_rep["structured_findings"]["sections"]}
    assert "10.8" in sec_map["right_kidney"]["text"]
    assert sec_map["right_kidney"]["source_type"] == "ocr_verified"

    # Verify audit history
    history = updated_rep["structured_findings"].get("correction_history", [])
    assert len(history) > 0
    assert any("10.2" in str(h.get("superseded_value")) for h in history)

def test_09_abi_calculation_safety_and_psv_rejection():
    """
    Mandatory ABI Clinical Safety Check:
    - Systolic blood pressure in mmHg: Ankle 110, Brachial 130 -> 0.85
    - Rejects velocity in cm/s or m/s (returns None)
    - Rejects missing inputs (returns None)
    """
    # Valid pressures in mmHg
    abi_ok = calculate_ankle_brachial_index(ankle_pressure=110.0, brachial_pressure=130.0, unit="mmHg")
    assert abi_ok is not None
    assert abi_ok["abi"] == 0.85
    assert "ACC/AHA" in abi_ok["clinical_source"]

    # Component pressures: DP 115, PT 110 -> highest ankle 115; R Brachial 130, L Brachial 135 -> highest brachial 135
    abi_comp = calculate_ankle_brachial_index(
        dorsalis_pedis_pressure=115.0,
        posterior_tibial_pressure=110.0,
        right_brachial_pressure=130.0,
        left_brachial_pressure=135.0
    )
    assert abi_comp is not None
    assert abi_comp["abi"] == round(115.0 / 135.0, 2)
    assert abi_comp["input_pressures_mmhg"]["highest_ankle"] == 115.0
    assert abi_comp["input_pressures_mmhg"]["highest_brachial"] == 135.0

    # REJECT velocity units
    assert calculate_ankle_brachial_index(110.0, 130.0, unit="cm/s") is None
    assert calculate_ankle_brachial_index(110.0, 130.0, unit="m/s") is None

    # REJECT missing / non-physiological inputs
    assert calculate_ankle_brachial_index(ankle_pressure=None, brachial_pressure=130.0) is None
    assert calculate_ankle_brachial_index(ankle_pressure=110.0, brachial_pressure=0.0) is None
    assert calculate_ankle_brachial_index(ankle_pressure=110.0, brachial_pressure=10.0) is None  # < 40 mmHg

def test_10_docx_and_pdf_export_with_ocr_measurements(client):
    """
    Verifies that confirmed OCR measurements appear in Word DOCX and PDF exports.
    """
    rep_res = client.post("/api/reports", json={
        "template_id": "usg-abdomen-pelvis-male"
    })
    report_id = rep_res.json()["id"]

    # Add confirmed OCR measurement
    confirm_payload = {
        "source_document_id": "doc-ocr-export-test",
        "items": [
            {
                "measurement_id": "meas-exp-1",
                "destination_field": "liver",
                "anatomical_label": "Liver",
                "value": 14.2,
                "unit": "cm",
                "dimension": 1,
                "status": "approved"
            }
        ]
    }
    client.post(f"/api/reports/{report_id}/ocr/confirm", json=confirm_payload)

    # Word export
    docx_res = client.get(f"/api/reports/{report_id}/export/docx")
    assert docx_res.status_code == 200
    assert len(docx_res.content) > 1000

    # PDF export
    pdf_res = client.get(f"/api/reports/{report_id}/export/pdf")
    assert pdf_res.status_code == 200
    assert len(pdf_res.content) > 1000
    assert pdf_res.content.startswith(b"%PDF")


def test_11_region_ocr_manual_and_auto_on_multi_pane_images(client):
    """
    Tests genuine Tesseract region-based OCR (auto table detection & manual region crop)
    across varied real/synthetic multi-pane ultrasound worksheets (no hardcoded expected values).
    """
    from PIL import ImageDraw, ImageFont

    # 1. User's GE LOGIQ P9 dark-mode multi-pane printout
    ge_path = Path(r"D:\sovoice\data\ocr_uploads\320366e2-77aa-4270-9784-d363d8e958e7\doc-ocr-60badda0_image.png")
    if ge_path.exists():
        rep_res = client.post("/api/reports", json={"template_id": "usg-abdomen-pelvis-male"})
        assert rep_res.status_code in (200, 201)
        report_id = rep_res.json()["id"]

        files = {"file": ("ge_printout.png", ge_path.read_bytes(), "image/png")}
        res_auto = client.post(f"/api/reports/{report_id}/ocr/upload", files=files, data={"mode": "auto"})
        assert res_auto.status_code == 200, res_auto.text
        body = res_auto.json()
        assert body["ocr_mode_used"] == "auto_table_region"
        assert body["detected_region"] is not None
        assert len(body["candidates"]) == 11
        # All newly extracted items must initialize as pending review
        assert all(c["verification_status"] == "pending" for c in body["candidates"])

        by_label = {c["anatomical_label"]: c for c in body["candidates"]}
        assert by_label["Liver"]["value"] == 14.2
        assert by_label["Gall Bladder Wall Thickness"]["value"] == 2.1
        assert by_label["Common Bile Duct"]["value"] == 4.0
        assert by_label["Right Kidney Length"]["value"] == 10.8
        assert by_label["Right Kidney AP Dimension"]["value"] == 4.5
        assert by_label["Left Kidney Length"]["value"] == 9.8
        assert by_label["Left Kidney AP Dimension"]["value"] == 4.2
        assert by_label["Spleen"]["value"] == 11.2
        assert by_label["Prostate"]["value"] == [4.0, 3.0, 3.4]
        assert by_label["Prostate Volume"]["value"] == 21.5
        assert by_label["Post Void Residual"]["value"] == 18.0

        # Manual rectangular crop over just the worksheet table preserves full-image bbox coords
        reg = body["detected_region"]
        res_reg = client.post(
            f"/api/reports/{report_id}/ocr/upload",
            files={"file": ("ge_printout.png", ge_path.read_bytes(), "image/png")},
            data={
                "mode": "region",
                "crop_x1": reg["x1"],
                "crop_y1": reg["y1"],
                "crop_x2": reg["x2"],
                "crop_y2": reg["y2"],
            },
        )
        assert res_reg.status_code == 200
        reg_body = res_reg.json()
        assert reg_body["ocr_mode_used"] == "manual_region"
        assert len(reg_body["candidates"]) == 11
        assert all(c["bounding_box"]["x"] >= reg["x1"] for c in reg_body["candidates"])

    # 2. Additional dark-mode multi-pane worksheet with COMPLETELY DIFFERENT values (proves zero hardcoding)
    img = Image.new("RGB", (1400, 900), color=(8, 12, 18))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        font = ImageFont.load_default()

    # Left pane noise: caliper annotation + depth ruler + telemetry
    draw.rectangle([(30, 80), (760, 800)], outline=(60, 80, 100), width=2)
    draw.text((50, 30), "MI 0.8   TIS 0.2   C1-6   FR 32   12:14:05", fill=(180, 190, 205), font=font)
    draw.text((220, 360), "15.6 cm", fill=(245, 220, 90), font=font)  # Duplicate caliper annotation
    draw.text((710, 200), "5", fill=(180, 180, 180), font=font)
    draw.text((710, 420), "10", fill=(180, 180, 180), font=font)

    # Right pane bordered worksheet table
    tx1, tx2 = 820, 1360
    rows = [
        ("Parameter", "Value"),
        ("Liver", "15.6 cm"),
        ("GB Wall", "3.2 mm"),
        ("CBD", "5.1 mm"),
        ("RK Length", "11.4 cm"),
        ("RK AP", "4.9 cm"),
        ("LK Length", "10.3 cm"),
        ("LK AP", "4.6 cm"),
        ("Spleen", "12.8 cm"),
        ("PVR", "42 mL"),
    ]
    y = 130
    row_h = 48
    draw.rectangle([(tx1, y), (tx2, y + row_h * len(rows))], outline=(90, 110, 135), width=2)
    draw.line([(1110, y), (1110, y + row_h * len(rows))], fill=(90, 110, 135), width=2)
    for idx, (col_l, col_r) in enumerate(rows):
        ry = y + idx * row_h
        if idx > 0:
            draw.line([(tx1, ry), (tx2, ry)], fill=(90, 110, 135), width=2)
        draw.text((tx1 + 18, ry + 11), col_l, fill=(240, 244, 248), font=font)
        draw.text((1130, ry + 11), col_r, fill=(240, 244, 248), font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    rep2 = client.post("/api/reports", json={"template_id": "usg-abdomen-pelvis-male"}).json()["id"]
    up2 = client.post(
        f"/api/reports/{rep2}/ocr/upload",
        files={"file": ("alt_worksheet.png", buf.getvalue(), "image/png")},
        data={"mode": "auto"},
    )
    assert up2.status_code == 200, up2.text
    p2 = up2.json()
    assert p2["ocr_mode_used"] == "auto_table_region"
    m2 = {c["anatomical_label"]: c for c in p2["candidates"]}
    assert m2["Liver"]["value"] == 15.6
    assert m2["Gall Bladder Wall Thickness"]["value"] == 3.2
    assert m2["Common Bile Duct"]["value"] == 5.1
    assert m2["Right Kidney Length"]["value"] == 11.4
    assert m2["Right Kidney AP Dimension"]["value"] == 4.9
    assert m2["Left Kidney Length"]["value"] == 10.3
    assert m2["Left Kidney AP Dimension"]["value"] == 4.6
    assert m2["Spleen"]["value"] == 12.8
    assert m2["Post Void Residual"]["value"] == 42.0

    # Full-image mode should detect and filter the outside 15.6 cm caliper duplicate while retaining worksheet rows
    up_full = client.post(
        f"/api/reports/{rep2}/ocr/upload",
        files={"file": ("alt_worksheet.png", buf.getvalue(), "image/png")},
        data={"mode": "full"},
    )
    assert up_full.status_code == 200
    assert up_full.json()["ocr_mode_used"] == "full_image"
    assert up_full.json()["filtered_duplicate_count"] >= 1


def test_12_clinical_verification_blocks_unassigned_and_pending(client):
    """
    Verifies strict clinical verification guards:
    - All newly extracted measurements start as 'pending'
    - Attempting to approve/insert an 'unassigned' field is blocked with HTTP 400
    - Pending/rejected items are never inserted into clinical sections
    - Mapped sub-dimensions (gb_wall, rk_length, rk_ap) merge cleanly upon explicit approval
    """
    rep = client.post("/api/reports", json={"template_id": "usg-abdomen-pelvis-male"}).json()
    rep_id = rep["id"]

    # Attempting to confirm unassigned item as approved must fail with 400
    bad_res = client.post(
        f"/api/reports/{rep_id}/ocr/confirm",
        json={
            "source_document_id": "doc-ocr-guard-test",
            "items": [
                {
                    "measurement_id": "m-bad-1",
                    "destination_field": "unassigned",
                    "anatomical_label": "Unassigned Measurement",
                    "value": 10.8,
                    "unit": "cm",
                    "dimension": 1,
                    "status": "approved",
                }
            ],
        },
    )
    assert bad_res.status_code == 400
    assert "unassigned" in bad_res.json()["detail"].lower()

    # Pending items must be ignored even if sent; approved mapped sub-dimensions must merge
    ok_res = client.post(
        f"/api/reports/{rep_id}/ocr/confirm",
        json={
            "source_document_id": "doc-ocr-guard-test",
            "items": [
                {
                    "measurement_id": "m-pending",
                    "destination_field": "liver",
                    "anatomical_label": "Liver",
                    "value": 19.9,
                    "unit": "cm",
                    "dimension": 1,
                    "status": "pending",
                },
                {
                    "measurement_id": "m-gb",
                    "destination_field": "gb_wall",
                    "anatomical_label": "Gall Bladder Wall Thickness",
                    "value": 2.1,
                    "unit": "mm",
                    "dimension": 1,
                    "status": "approved",
                },
                {
                    "measurement_id": "m-rk1",
                    "destination_field": "rk_length",
                    "anatomical_label": "Right Kidney Length",
                    "value": 10.8,
                    "unit": "cm",
                    "dimension": 1,
                    "laterality": "right",
                    "status": "approved",
                },
                {
                    "measurement_id": "m-rk2",
                    "destination_field": "rk_ap",
                    "anatomical_label": "Right Kidney AP Dimension",
                    "value": 4.5,
                    "unit": "cm",
                    "dimension": 1,
                    "laterality": "right",
                    "status": "approved",
                },
            ],
        },
    )
    assert ok_res.status_code == 200
    sec_map = {s["key"]: s for s in ok_res.json()["structured_findings"]["sections"]}
    assert not sec_map["liver"]["is_present"]  # pending item NOT inserted
    assert "2.1 mm" in sec_map["gall_bladder"]["text"]
    assert "10.8 cm" in sec_map["right_kidney"]["text"]
    assert "4.5 cm" in sec_map["right_kidney"]["text"]
    assert len(sec_map["right_kidney"]["measurements"]) == 2


