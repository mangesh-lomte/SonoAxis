# SonoAxis Clinician & Administrator User Guide

## 1. Roles & Permissions Overview

| Capability | Radiologist | Administrator |
| :--- | :---: | :---: |
| Patient creation & editing | Yes | Yes |
| Audio dictation / transcript editing | Yes | Yes |
| Worksheet OCR upload & verification | Yes | Yes |
| Draft report editing & saving | Yes | Yes |
| Finalize review (`DRAFT` -> `REVIEWED`) & revert to `DRAFT` | **Yes** | No |
| Export Word (`.docx`) & PDF | Yes | Yes |
| Import custom `.docx` templates (single/bulk) & edit own drafts | **Yes** | Yes |
| Approve / manage shared templates & archive any custom template | No | **Yes** |
| Modify/delete the 16 built-in institutional templates | Forbidden | Forbidden |
| User management (`/auth/users`) & system backups/restore test | No | **Yes** |

---

## 2. Standard Clinical Reporting Workflow

### Step 1: Sign In
Navigate to `http://127.0.0.1:8000/` and sign in on `/login` with your workstation credentials. Sessions expire after **8 hours** (`28800` seconds) and invalidate upon sign-out or password change.

### Step 2: Select Patient & Examination Protocol
1. Open **New Report** or **Patients** to select or register a patient record (`patient_id`/MRN, full name, age, gender, clinical notes).
2. Select an ultrasound protocol from the 4 examination families:
   - **Abdomen & Pelvis** (`Male`, `Female`)
   - **Venous Doppler** (Unilateral & Bilateral normal, varicosities, DVT)
   - **Arterial Doppler** (Unilateral & Bilateral normal, PVD, thrombus with 3-col / 5-col hemodynamic tables)
   - **Combined Arteriovenous Doppler**
   - Or choose any **Custom / Imported** template.

### Step 3: Dictate, Upload Audio, or Edit Transcript
Inside **Local AI Dictation**:
- **Record Audio:** Capture microphone audio directly in the browser, stop recording, and transcribe locally via `Faster-Whisper`.
- **Upload Audio:** Upload `.wav` or supported audio recordings for local transcription. Incremental recording takes append rather than wiping prior structured sections.
- **Edit Transcript:** Refine the text directly in the **Dictation Transcript** field (original raw transcript remains preserved in the database).
- Click **Process with AI (Generate Draft)** to invoke the deterministic clinical structuring engine.

### Step 4: Verify Anatomical Guidance, Presets & Unassigned Findings
- **Anatomical Dictation Guidance:** Collapsible checklist showing which sections are `Dictated`, `OCR`, `Preset`, or still `Pending`. Undictated sections stay strictly blank (`Draft`).
- **Normal Presets:** Use **Preset** on individual section cards to insert vetted normal text cleanly marked with a `Preset` attribution badge.
- **Explicit Verbal Corrections:** Phrases such as *"correction..."* or *"make that..."* automatically update the active section and log the superseded text in the **Explicit Correction Audit Trail**.
- **Unassigned Clinical Findings:** Any statement without an unambiguous organ target appears in the yellow unresolved box. Select the target organ section from the dropdown to append it cleanly (or exclude it when irrelevant). Assigning appends text rather than overwriting existing findings or measurements, prevents duplicate insertion, and keeps unresolved state if assignment fails.

### Step 5: Worksheet OCR (`Scan Measurements`)
1. Click **Scan** / **Scan OCR** inside a report workspace and upload a `.jpg`, `.png`, `.webp`, `.bmp`, or `.tiff` ultrasound worksheet image (<= `15 MB`, <= `25 MP`).
2. Choose **Auto Region** (detects bright/bordered worksheet parameters), **Select Region** (draw a manual rectangle over the parameter table), or **Full Image**.
3. Review every extracted candidate side by side against the highlighted image bounding box:
   - Edit numeric values, anatomical field mappings, or units inline if needed.
   - Click **Approve** or **Reject** individually (or **Approve All Valid Mapped** when confident). Pending items are never inserted automatically.
4. Click **Confirm & Insert** to commit approved measurements with `OCR Verified` / `OCR Edited` provenance and trigger deterministic biometry recalculations (e.g., prostate/uterine volume).

### Step 6: Radiologist Review & Document Export
1. Click **Preview** to inspect the institutional HTML rendering and confirm any remaining unresolved findings.
2. While in `DRAFT`, all HTML/DOCX/PDF previews carry clear **DRAFT — Pending Radiologist Sign-Off** notices.
3. Radiologist accounts click **Mark Reviewed** to sign off (`REVIEWED`), timestamp the revision, and record clinician attribution.
4. Download **Word (`.docx`)** or **PDF** for institutional distribution.
5. Inspect full change history at any time via **Audit**.

---

## 3. Custom Template Workflow (Radiologists & Administrators)

- In **Templates**, click **Import Template** (or **Import Your First Template** under **Custom / Imported**) to upload single or multiple macro-free `.docx` templates (<= `20 MB`).
- SonoAxis automatically parses headings, `[PLACEHOLDER]` tags, and tables while rejecting `.docm` files or `.docx` archives containing VBA macros (`vbaProject.bin`).
- Radiologists can edit, preview, version (`Draft Config` -> new revision), and archive their own custom templates; Administrators approve templates for shared institutional availability.
- The **16 built-in institutional protocols** are protected on both UI and backend (`HTTP 403`) against alteration or deletion.

---

## 4. Database Backups & Administration (Administrator Role)

Under **Settings**:
- Inspect active Whisper model (`small.en` / `base.en`), CPU INT8 / CUDA compute status, and Word/PDF export engine availability.
- Manage clinician accounts (create users, change roles, activate/deactivate accounts). Note: the system blocks demoting or deactivating the last remaining active Administrator.
- Create verified SQLite online backups (`POST /api/backups`) and run non-destructive integrity & temporary restore verification (`POST /api/backups/test-restore`).
