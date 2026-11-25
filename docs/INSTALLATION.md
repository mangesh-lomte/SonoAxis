# Installation & Local Provisioning Guide

## 1. Prerequisites

| Component | Requirement | Notes |
| :--- | :--- | :--- |
| **Operating System** | Windows 10 / 11 (64-bit) | Production launcher (`start_sonoaxis.bat`) and PDF headless path target Windows |
| **Python** | Python 3.12+ | Create isolated virtual environment (`.venv`) |
| **Node.js & npm** | Node.js 20 LTS+ / npm 10+ | Required to build `frontend/dist/` |
| **Tesseract OCR** | Tesseract 5.x binary | Required for `Scan Measurements` worksheet OCR |
| **Microsoft Edge** | Pre-installed Windows Edge | Required by `PDFExportService` (`msedge.exe --headless --print-to-pdf`) |
| **Microphone Hardware** | Standard USB/integrated audio input | Optional if uploading `.wav`/audio recordings or pasting transcripts |

---

## 2. Setup Steps (Windows PowerShell)

```powershell
# Clone the repository and enter the project directory
git clone https://github.com/mangesh-lomte/SonoAxis.git
cd SonoAxis

# 1. Python environment setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

# 2. Frontend production bundle
cd frontend
npm install
npm run build
cd ..

# 3. Optional environment configuration
Copy-Item .env.example .env
```

---

## 3. External Local Assets Provisioning

### A. Tesseract OCR Binary
`backend/app/ocr/engine.py` checks `tesseract` on `PATH` and then looks in standard Windows locations:
- `C:\Program Files\Tesseract-OCR\tesseract.exe`
- `C:\Program Files (x86)\Tesseract-OCR\tesseract.exe`
- `D:\tools\tesseract\tesseract.exe`
- `D:\Tesseract-OCR\tesseract.exe`

Install Tesseract OCR on Windows and verify:
```powershell
tesseract --version
```

### B. Faster-Whisper Offline Models
Local transcription models are excluded from Git (`models/` in `.gitignore`) because weight binaries exceed hundreds of megabytes. Place CTranslate2 Whisper models (`base.en`, `small.en`) into `models\whisper\<model_name>\` containing `model.bin` and `config.json` (plus vocabulary/tokenizer files from standard `Systran/faster-whisper-*` releases).

Verify the directory layout:
```text
models/
└── whisper/
    ├── base.en/
    │   ├── config.json
    │   ├── model.bin
    │   └── tokenizer.json
    └── small.en/
        ├── config.json
        ├── model.bin
        └── tokenizer.json
```

### C. Institutional DOCX Reference Templates (`references/`)
Original clinical letterhead `.docx` files are excluded from Git for confidentiality (`references/*.docx` in `.gitignore`).
For full institutional stationery DOCX generation against the 16 built-in profiles (`backend/app/structuring/templates.py`), provision the matching hospital `.docx` files under `references\` (matching filenames in `TEMPLATES_CATALOG`, such as `male-abdomen-pelvis.docx` / `abd male-new.docx` and `female-abdomen-pelvis.docx` / `abdo female1-new.docx`).

---

## 4. Clinician Account Initialization

SonoAxis never creates default plaintext passwords in source code. Initialize workstation accounts locally using the CLI tool (`backend/app/cli_accounts.py`):

```powershell
# Initialize demonstration Radiologist (asharma) and Administrator (sysadmin) accounts with interactive password prompts:
python -m backend.app.cli_accounts init-demo

# Or register a clinical user directly:
python -m backend.app.cli_accounts create-user --username doctor1 --full-name "Dr. Jane Smith" --role Radiologist

# List active/inactive workstation accounts:
python -m backend.app.cli_accounts list-users

# Rotate password and revoke existing sessions for an account:
python -m backend.app.cli_accounts reset-password --username doctor1
```

Passwords must be at least 8 characters.

---

## 5. Running the Application

### Option 1: Direct Uvicorn Launch
```powershell
.\.venv\Scripts\uvicorn.exe backend.app.main:app --host 127.0.0.1 --port 8000
```
Open `http://127.0.0.1:8000/`.

### Option 2: Windows Launcher (`start_sonoaxis.bat`)
Double-click `start_sonoaxis.bat` (or execute it in PowerShell). It checks `.venv\Scripts\uvicorn.exe`, prevents duplicate listeners on port `8000`, launches Uvicorn minimized, and opens `http://127.0.0.1:8000/`.

---

## 6. Known Portability Considerations

Before deploying this codebase outside `D:\sovoice`, note the following hardcoded path defaults currently present in source and test files (preserved untouched for release baseline stability):

- `backend/app/api/endpoints.py:825` (`os.path.abspath("D:/sovoice/data/ocr_uploads")`)
- `backend/app/ocr/engine.py:24` (`Path("D:/sovoice/data/ocr_uploads")`) and Tesseract fallback paths (`D:\tools\tesseract\tesseract.exe`, `D:\Tesseract-OCR\tesseract.exe`)
- `backend/app/ocr/extractor.py:9,284` (`Path("D:/sovoice/data/config/ocr_aliases.json")`)
- `backend/app/ocr/synthetic_fixtures.py:5` (`Path("D:/sovoice/tests/fixtures/ocr")`)
- `backend/app/services/auth_service.py:15` (`Path("D:/sovoice/data/config/auth_secret.key")`)
- Multiple automated test scripts in `tests/` reference `D:/sovoice/...` paths directly.

On machines where SonoAxis is cloned to a non-`D:\sovoice` directory, running OCR uploads, custom OCR aliases, session key storage, or full test runs requires either resolving those path constants to `settings.BASE_DIR` / `settings.DATA_DIR` or creating the corresponding paths.
