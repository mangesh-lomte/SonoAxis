# Testing & Quality Assurance Guide

## 1. Running the Automated Test Suite

From the repository root with the project virtual environment active:

```powershell
.\.venv\Scripts\pytest.exe tests
```

Pytest configuration (`pytest.ini`):
- `pythonpath = .`
- `norecursedirs = backups .git .venv node_modules frontend references`
- `testpaths = tests`

---

## 2. Frontend Type Check, Lint & Build

```powershell
cd frontend
npm run lint
npm run build
```

`npm run build` runs `tsc -b && vite build` to validate TypeScript types and emit the production bundle into `frontend/dist/`.

---

## 3. Automated Test Suite Inventory (`tests/`)

The regression suite contains **193 tests** across **14 test modules**:

| Test File | Scope Covered |
| :--- | :--- |
| `tests/test_structuring.py` | Clinical NLP segmentation, organ routing, negation preservation, correction precedence, blank section preservation |
| `tests/test_vascular_phase10b.py` | Arterial 3-column/5-column measurement tables, bilateral vs. unilateral isolation, perforator card parsing, ABI validation |
| `tests/test_voice_to_report.py` | End-to-end audio-to-report structuring cases across male/female abdomen, pelvic eponyms, and ambiguous phrases |
| `tests/test_speech_recognition.py` | Faster-Whisper local engine initialization, model discovery, and deterministic audio fixture transcription |
| `tests/test_microphone_verification.py` | Acoustic capture payload handling and audio validation |
| `tests/test_persistence.py` | SQLite CRUD, foreign key integrity, revisions, audio recording attachment, unassigned assignment/exclusion |
| `tests/test_phase10c_all_16_templates.py` | Parameterized verification across all 16 institutional examination templates |
| `tests/test_phase10c_stress_and_security.py` | Concurrency/stress paths, file size bounds, and path traversal resistance |
| `tests/test_phase10d_advanced_workflows.py` | Multi-recording append workflows, presets add/remove, checklist synchronization, biometry recalculation |
| `tests/test_phase10e_ocr_workflows.py` | Image bomb/format validation, Otsu preprocessing, region-based Tesseract OCR extraction, spatial pairing, confirmation gating |
| `tests/test_template_management_phase10b1.py` | Single/bulk `.docx` import, XML structure parsing, macro/`.docm` rejection, approval, versioning, archiving |
| `tests/test_export.py` | Institutional HTML preview, `python-docx` export structure & Draft watermark rules, Microsoft Edge PDF output |
| `tests/test_phase10h_auth_and_cleanup.py` | Argon2id password verification, `401` enforcement across protected APIs, CSRF checks, RBAC (`Radiologist` vs `Administrator`), rate limiting, custom template isolation, unassigned-finding append fix |
| `tests/test_e2e_full_workflow.py` | Complete clinical reporting lifecycle from patient creation through dictation/structuring, review sign-off, and export |

---

## 4. Test Isolation Notes

- Authentication tests create isolated temporary SQLite databases and accounts without altering the workstation's live `data/sonovoice.db` or clinician passwords.
- Several integration and export tests (`test_export.py`, `test_phase10e_ocr_workflows.py`, `test_speech_recognition.py`) require locally provisioned assets (Tesseract OCR, Whisper models, Microsoft Edge, and local `.docx` references when running full export checks).
