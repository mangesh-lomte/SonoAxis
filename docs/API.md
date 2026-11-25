# SonoAxis REST API Reference

Base URL: `http://127.0.0.1:8000/api`  
Interactive Swagger/OpenAPI schema when running locally: `http://127.0.0.1:8000/docs`

---

## 1. Authentication & CSRF Model

- **Public Endpoints:** `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/health`
- **All Other Endpoints (`/api/*`):** Require either:
  - Browser cookies `sonoaxis_session` (`HttpOnly`) **and** header `X-CSRF-Token: <csrf_token>` on `POST`, `PUT`, `PATCH`, `DELETE` requests, OR
  - Header `Authorization: Bearer <access_token>` (for scripted/API test clients).
- Unauthenticated calls return `401 Unauthorized`. Missing/invalid CSRF on cookie mutations or insufficient RBAC privileges returns `403 Forbidden`.

---

## 2. Authentication & User Governance

| Method | Endpoint | Access | Purpose |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/login` | Public | Verify credentials (`username`, `password`), return tokens & set cookies; `429` after 5 failed attempts / 300s |
| `POST` | `/auth/logout` | Public | Revoke current session and clear cookies |
| `GET` | `/auth/me` | Authenticated | Return current clinician profile |
| `PUT` | `/auth/profile` | Authenticated | Update own profile metadata |
| `POST` | `/auth/change-password` | Authenticated | Verify current password, update Argon2id hash, revoke sessions |
| `GET` | `/auth/users` | Admin | List all workstation clinician/admin accounts |
| `POST` | `/auth/users` | Admin | Create new clinician or admin account (`201 Created`) |
| `PATCH` | `/auth/users/{user_id}` | Admin | Update user role, profile, activation status, or reset password |

---

## 3. Health & Engine Telemetry

| Method | Endpoint | Access | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Public | Non-sensitive health probe (`status`, `app_name`, `version`) |
| `GET` | `/engine/status` | Authenticated | Loaded Whisper model, compute device (`cpu`/`cuda`), quantization (`int8`) |
| `GET` | `/engine/models` | Authenticated | Inventory of offline models detected under `models/whisper/` |
| `GET` | `/dashboard/stats` | Authenticated | Study counts (`Today`, `Draft`, `Reviewed`) and patient totals |

---

## 4. Patients & Clinical Reports

| Method | Endpoint | Access | Purpose |
| :--- | :--- | :--- | :--- |
| `POST` | `/patients` | Authenticated | Register patient (`201 Created`) |
| `GET` | `/patients` | Authenticated | List / search patient registry |
| `GET` | `/patients/{patient_id}` | Authenticated | Fetch patient profile |
| `PUT` | `/patients/{patient_id}` | Authenticated | Update patient demographics / clinical notes |
| `DELETE` | `/patients/{patient_id}` | Authenticated | Remove patient record (`patient_id` on reports set null) |
| `GET` | `/patients/{patient_id}/reports` | Authenticated | List studies linked to a patient |
| `POST` | `/reports` | Authenticated | Create new `DRAFT` ultrasound report (`201 Created`) |
| `GET` | `/reports` | Authenticated | Filterable list of reports |
| `GET` | `/reports/{report_id}` | Authenticated | Fetch full report state, sections, unassigned items, metadata |
| `PUT` | `/reports/{report_id}` | Authenticated | Save edited transcript/findings/impression; records revision snapshot |
| `DELETE` | `/reports/{report_id}` | Authenticated | Delete report record |
| `GET` | `/reports/{report_id}/revisions` | Authenticated | Immutable revision audit history |
| `POST` | `/reports/{report_id}/review` | **Radiologist** | Transition `DRAFT` -> `REVIEWED` (`403` if Administrator) |
| `POST` | `/reports/{report_id}/revert-draft` | **Radiologist** | Revert `REVIEWED` -> `DRAFT` for revision |

---

## 5. Dictation, Audio, Structuring & Clinical Checklists

| Method | Endpoint | Access | Purpose |
| :--- | :--- | :--- | :--- |
| `POST` | `/audio/transcribe` | Authenticated | Direct local Whisper transcription of uploaded audio file |
| `POST` | `/reports/{report_id}/audio` | Authenticated | Upload audio recording and populate initial report structuring |
| `POST` | `/reports/{report_id}/recordings` | Authenticated | Append incremental recording take without clearing prior findings |
| `GET` | `/reports/{report_id}/recordings` | Authenticated | List recordings attached to a report |
| `GET` | `/audio/{audio_id}` | Authenticated | Stream/download stored recording for synced playback |
| `POST` | `/reports/{report_id}/structure` | Authenticated | Re-run deterministic structuring on edited transcript text |
| `POST` | `/reports/{report_id}/assign-unassigned` | Authenticated | Assign unresolved statement to an anatomical section (appends cleanly, deduplicates) |
| `POST` | `/reports/{report_id}/exclude-unassigned` | Authenticated | Exclude non-clinical/irrelevant unassigned item |
| `GET` | `/structuring/presets` | Authenticated | Fetch institutional normal preset snippets |
| `POST` | `/reports/{report_id}/apply-preset` | Authenticated | Insert normal preset text with `Preset` attribution |
| `POST` | `/reports/{report_id}/remove-preset` | Authenticated | Remove previously inserted preset |
| `GET` | `/structuring/checklist/{report_id}` | Authenticated | Retrieve anatomical guidance state (`Dictated`, `OCR`, `Preset`, `Pending`) |
| `POST` | `/reports/{report_id}/recalculate` | Authenticated | Recompute prostate/uterine volumes and biometry checks |
| `GET` | `/structuring/templates` | Authenticated | Structuring template summary list |
| `GET` | `/structuring/templates/{template_id}` | Authenticated | Structuring metadata for specific template |
| `POST` | `/structuring/process` | Authenticated | Stateless structuring preview endpoint |
| `POST` | `/structuring/assign-unassigned` | Authenticated | Stateless unassigned statement helper |
| `POST` | `/structuring/validate` | Authenticated | Validate template compatibility / clinical checks |

---

## 6. Worksheet OCR (`Scan Measurements`)

| Method | Endpoint | Access | Purpose |
| :--- | :--- | :--- | :--- |
| `POST` | `/reports/{report_id}/ocr/upload` | Authenticated | Validate image, run auto/manual region detection & Tesseract OCR, return candidates |
| `GET` | `/reports/{report_id}/ocr/images/{filename}` | Authenticated | Retrieve safely scoped OCR source image for review canvas |
| `POST` | `/reports/{report_id}/ocr/confirm` | Authenticated | Commit clinician-approved OCR candidates into report sections & recalculate biometry |

---

## 7. Institutional & Custom Templates

| Method | Endpoint | Access | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/templates` | Authenticated | List templates filtered by category, laterality, status, visibility |
| `GET` | `/templates/{template_id}` | Authenticated | View template metadata & section definitions (`403` for private templates of other users) |
| `GET` | `/templates/{template_id}/preview` | Authenticated | Preview extracted structure/sections (`403` if private to another user) |
| `POST` | `/templates/import` | Authenticated | Upload single `.docx` template with VBA macro check (`201 Created`) |
| `POST` | `/templates/bulk-import` | Authenticated | Upload multiple `.docx` templates in batch (`201 Created`) |
| `POST` | `/templates/extract-structure` | Authenticated | Inspect headings, `[PLACEHOLDERS]`, and tables without saving |
| `PUT` | `/templates/{template_id}` | Owner / Admin | Update custom template configuration (`403` on built-in templates) |
| `POST` | `/templates/{template_id}/approve` | **Admin** | Approve custom template for shared institutional visibility |
| `POST` | `/templates/{template_id}/archive` | Owner / Admin | Archive custom template (`403` on built-in) |
| `POST` | `/templates/{template_id}/version` | Owner / Admin | Create new version increment of custom template (`403` on built-in) |

---

## 8. Previews, Exports, Settings & Backups

| Method | Endpoint | Access | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/exports/status` | Authenticated | Report availability of OpenXML Word & Edge Headless PDF engines |
| `GET` | `/reports/{report_id}/preview` | Authenticated | Canonical institutional HTML preview (with Draft banner if unreviewed) |
| `GET` | `/reports/{report_id}/export/docx` | Authenticated | Generate & download `.docx` report |
| `GET` | `/reports/{report_id}/export/pdf` | Authenticated | Generate & download US-Letter `.pdf` report via Edge Headless |
| `GET` | `/settings` | Authenticated | Read workstation settings |
| `PUT` | `/settings` | **Admin** | Modify persisted settings |
| `POST` | `/backups` | **Admin** | Execute native online SQLite backup & `PRAGMA integrity_check` |
| `GET` | `/backups` | **Admin** | List verified backup files |
| `POST` | `/backups/test-restore` | **Admin** | Restore latest backup into an isolated temp DB to verify recoverability |
