# Security, Privacy & Clinical Safety Architecture

## 1. Local Execution & Data Sovereignty Boundary

- **Network Binding:** Production server (`start_sonoaxis.bat` / Uvicorn command) binds strictly to `127.0.0.1:8000` (localhost loopback).
- **CORS Restrictions:** `backend/app/main.py` restricts `allow_origins` to `http://127.0.0.1:8000`, `http://localhost:8000`, and `http://127.0.0.1:5173`.
- **Zero External Telemetry:** No outbound patient health information (PHI), audio, or image calls are made by the backend engines (`Faster-Whisper`, deterministic structuring, `Tesseract OCR`, `python-docx`, `msedge --headless`).

---

## 2. Authentication, Session Management & CSRF Protection

Implemented in `backend/app/services/auth_service.py` and `backend/app/api/endpoints.py`:

| Control | Implementation Details |
| :--- | :--- |
| **Password Hashing** | **Argon2id** via `argon2-cffi` (`time_cost=3`, `memory_cost=65536` KiB, `parallelism=2`, `hash_len=32`, `salt_len=16`). Legacy/non-Argon2id hashes are rejected. |
| **Session Signing** | Cryptographically random 36-byte token hashed with **HMAC-SHA256** (`_token_digest`) using a locally generated secret (`auth_secret.key`). Raw session tokens are never stored in SQLite (`user_sessions.token_hash`). |
| **Browser Cookies** | `sonoaxis_session` set as `HttpOnly`, `SameSite=Lax`, `max_age=28800` (8 hours). |
| **CSRF Defense** | Cookie-authenticated `POST`, `PUT`, `PATCH`, and `DELETE` requests strictly require a matching `X-CSRF-Token` request header validated in constant time (`hmac.compare_digest`) against the session's `csrf_token`. Failures return `HTTP 403`. |
| **Brute-Force Lockout** | In-memory sliding window (`LOGIN_RATE_LIMIT_WINDOW_SECONDS = 300`, `LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 5`) keyed by `<client_ip>:<username>`. Exceeding threshold returns `HTTP 429` (`Retry-After: 300`). |
| **Session Revocation** | Logging out (`POST /api/auth/logout`), password rotation (`POST /api/auth/change-password`), or CLI `reset-password` marks active sessions `revoked = 1`. |
| **CLI Account Setup** | `backend/app/cli_accounts.py` uses `getpass` or non-committed environment variables (`SONOAXIS_*`) with minimum 8-character enforcement. No plaintext defaults exist in source files. |

---

## 3. Route Authorization Matrix

Every route on `router` (`APIRouter(prefix="/api", dependencies=[Depends(require_authenticated_session)])`) requires valid authentication and returns **`HTTP 401`** otherwise:

- **Public Routes (`public_router` only):** `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/health` (returns `{status, app_name, version}` only — no clinical records or user data).
- **Radiologist-Exclusive Actions (`require_radiologist_user`, `HTTP 403` otherwise):** `POST /api/reports/{id}/review`, `POST /api/reports/{id}/revert-draft`.
- **Administrator-Exclusive Actions (`require_admin_user`, `HTTP 403` otherwise):** `/api/auth/users` (`GET`/`POST`/`PATCH`), `POST /api/templates/{id}/approve`, `PUT /api/settings`, `POST /api/backups`, `GET /api/backups`, `POST /api/backups/test-restore`.
- **Custom Template Ownership (`_authorize_template_view` / `_authorize_template_mutation`):**
  - Built-in templates (`is_built_in = 1`) cannot be updated, archived, or deleted by any role (`HTTP 403`).
  - Draft/private custom templates created by one Radiologist are isolated from edits/previews/versions by another Radiologist (`HTTP 403`).

---

## 4. Input & File Upload Security Controls

- **DOCX Template Validation (`TemplateService.extract_docx_structure`):**
  - Max file size: **20 MB**.
  - Extension allowlist: strictly `.docx` (`.docm` rejected).
  - Zip structural verification (`zipfile.BadZipFile` handled safely) and explicit scanning against `word/vba*` or `*vba*.bin` embedded macros.
- **OCR Image Validation (`validate_image_file`):**
  - Max payload size: **15 MB**.
  - Decompression bomb cap: `Image.MAX_IMAGE_PIXELS = 25_000_000` (25 megapixels).
  - Strict image format allowlist (`JPEG`, `JPG`, `PNG`, `WEBP`, `BMP`, `TIFF`) plus `img.verify()` structural check.
- **Static & Local File Retrieval:**
  - `GET /api/reports/{id}/ocr/images/{filename}` verifies authentication, report existence, and path traversal containment (`os.path.basename` + realpath under `OCR_STORAGE_DIR`).

---

## 5. Honest Security Disclosures & Deployment Requirements

1. **No Database-Layer Encryption at Rest:** SQLite (`sonovoice.db`), stored audio files (`data/audio/`), OCR uploads (`data/ocr_uploads/`), and backups are stored in standard unencrypted files. Production workstations **must** enable OS full-disk encryption (Windows BitLocker), locked OS login accounts, and physical workstation access control.
2. **Cookie `Secure` Flag:** Over local HTTP (`http://127.0.0.1:8000`), session cookies operate without TLS/HTTPS (`Secure` flag not set for local loopback HTTP). Do not expose SonoAxis over untrusted LANs or public networks without placing it behind a properly configured TLS reverse proxy.
3. **Clinical Safety & Hallucination Boundary:** Automated transcription, NLP structuring, OCR parsing, and calculated volumes (`Prostate`, `Uterus`, `ABI`, `Carotid Ratio`) are strictly clinical aids. Final medical responsibility rests solely with the reviewing clinician signing off (`REVIEWED`).
4. **Compliance Scope:** SonoAxis has not undergone external HIPAA, GDPR, CE, or FDA medical-device certification.
