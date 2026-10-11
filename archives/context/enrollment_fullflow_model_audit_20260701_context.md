# Task Context: enrollment_fullflow_model_audit_20260701

Created: 2026-07-01 23:31:14
Updated: 2026-07-02 00:18 local

Objective: use bounded Hermes model routes `qwen3.7-plus`, `minimax-m3`, and `mimo-v2.5` to independently audit the enrollment-review app workflow, UI, and operational logic; synthesize consensus; then Codex verifies and implements only validated fixes.

Risk: high. The app supports clinical-trial eligibility review and stores derived subject review artifacts. Hermes must not edit source files or raw clinical files.

## Source Of Truth

- Workspace: `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app`
- App under review:
  - frontend: `static/index.html`
  - backend: `app/router/*.py`, `app/pipeline/*.py`
  - task record: `docs/PROJECT_CONTEXT.md`
  - prior external review: `SYSTEM_REVIEW_REPORT.md`
- Current UI snapshot artifacts:
  - contact sheet image for visual review: `output/model_audit_20260701/screenshots/ui_contact_sheet.png`
  - raw Playwright snapshot JSON: `output/model_audit_20260701/snapshots/ui_snapshot.json`
  - compact Playwright summary: `output/model_audit_20260701/snapshots/ui_snapshot_summary.json`
- Current SAR test project:
  - project code: `MG-K10-SAR-III`
  - protocol ID: `MG-K10-SAR-001`
  - version/date: `V2.1 / 2025-09-19`
  - fixed study stage: `Ⅲ期`
  - center 31 subjects: `31001`, `31006`, `31008`, `31010`, `31013`, `31014`, `31015`, `31016`, `31017`, `31018`
  - review phases: `screening_run_in` and `baseline_randomization`
  - latest QC report: `output/sar31_flash_max_rerun_20260625/qc_summary_final.md`

## User Requirements To Reconcile Against

- The system is for senior medical monitors who may not understand AI or computer workflows.
- Login is required. First registration/login should show detailed help once; repeated logins should not force the help page.
- Admin account: username `admin`, password `20121116`; admin can do all operations. Ordinary users can modify only their own created/uploaded content. Other users' projects/subjects/results should be readable but not editable.
- Homepage should split three workflows:
  - new project, first protocol deconstruction;
  - existing project, protocol re-deconstruction/revision;
  - existing project, start eligibility review.
- Protocol metadata should be extracted from the protocol, especially version/date from header/footer or page 1. Users should not be asked to manually type many protocol fields.
- If one protocol includes both phase II and phase III, deconstruction must ask the user to choose one. After choice, phase II and III become separate project identities; subjects are not shared.
- Eligibility rules must preserve official IN/EX numbering. Child rules such as `IN-04a` are allowed only when the parent criterion is compound and logic is explicit.
- Eligibility review is phase/timepoint based. Screening and baseline/randomization can be audited separately. Subject list should make phase-specific entry points visible.
- Baseline/randomization time-window checks need a user-entered anchor date. Without the date, date-dependent rules should become evidence-insufficient or a reminder, not silently use screening date as baseline.
- `pass_verify`/source traceability reminder is a pass-level reminder, not a hard block. It should be displayed as `溯源提醒`, not as a low-strength internal label.
- Evidence-insufficient and investigator-judgment states must be separated:
  - missing source data -> `证据不足`;
  - existing data needs clinical/investigator judgment -> `需研究者判定`.
- OCR precision is more important than speed. OCR concurrency is currently intended to allow up to 8 VLM calls.
- Batch processing should avoid unnecessary serial OCR->LLM->OCR->LLM blocking if safe, but correctness and inspectability are more important.
- Reports and UI must not show internal/log-like language such as `按要求排除`, parser guard phrases, or prompt-only instructions.
- The UI should use page width well on desktop and remain usable on smaller windows without incoherent wrapping or hidden information.
- All pages should use the simplified ER logo, no old CMS logo, no extra text line around logo.

## Current Live State Captured By Codex

Health check on 2026-07-02 local:

```json
{"status":"ok","omlx":false,"deepseek":true}
```

This means the app API is up, DeepSeek config is available, but oMLX was not ready at capture time. Earlier user requirements said the desktop launcher should start both the app and oMLX, so this belongs in reliability review.

Playwright routes captured without console errors or failed requests at desktop width:

- task dashboard
- audit project list
- first protocol deconstruction
- existing project re-deconstruction
- SAR subject list
- SAR rules tab
- SAR project info tab
- SAR subject 31001 screening report
- SAR subject 31001 baseline report
- help page

Compact UI metrics:

```text
- task_dashboard 1440x980: overflow=0, scrollOverflow=0
- audit_projects 1440x980: overflow=0, scrollOverflow=0
- first_deconstruct 1440x980: overflow=0, scrollOverflow=0
- re_deconstruct 1440x980: overflow=0, scrollOverflow=0
- sar_subjects 1440x980: overflow=0, scrollOverflow=0
- sar_rules 1440x980: overflow=0, scrollOverflow=0
- sar_project_info 1440x980: overflow=0, scrollOverflow=0
- sar_subject_31001_screening 1440x980: overflow=0, scrollOverflow=0
- sar_subject_31001_baseline 1440x980: overflow=0, scrollOverflow=0
- help 1440x980: overflow=0, scrollOverflow=0
- task_dashboard 390x844: overflow=0, scrollOverflow=0
- sar_subjects 390x844: overflow=30, scrollOverflow=0
- sar_subject_31001_screening 390x844: overflow=30, scrollOverflow=0
- help 390x844: overflow=0, scrollOverflow=0
```

Codex visual observation from the screenshots:

- Desktop subject list is dense but readable and shows both phase-specific review cells.
- Mobile subject list is not truly usable: the table content extends beyond viewport but the page hides horizontal overflow, so the right side is clipped rather than scrollable or reflowed.
- Mobile report page has similar clipping risk for the rule table.
- Subject list currently still has a separate global `审核阶段` select above the table while also showing per-phase cells in the table. This may be conceptually redundant now that phase-specific entry points are visible.
- Baseline anchor date input is visible inside each baseline phase cell, but its placeholder is `yyyy/mm/日`, not ideal Chinese date affordance; empty anchor fields are repeated per row and can dominate the column.
- Buttons inside each row are many but legible at desktop; on mobile they contribute to clipping.
- Help page is detailed and scrollable; it did not overflow in the captured widths.

## Previously Found And Mostly Fixed System Risks

The task record says the following have already been fixed and should not be rediscovered as open defects unless current evidence shows regression:

- Path traversal via project/subject IDs is now mitigated by `validate_storage_id()` in `app/shared.py`.
- Subject upload filenames are validated by `_safe_upload_filename()`.
- OCR hallucination/repetition detection exists in `app/pipeline/ocr.py::detect_ocr_hallucination()`.
- Semantic parser guards were added for:
  - GGT not substituting ALT/AST/TBil;
  - urine glucose/occult blood not substituting infection evidence;
  - EX-20h all-of logic requiring abnormality + clinical significance + unacceptable risk judgment;
  - syphilis exception needing non-specific antibody negativity and cured-prior-infection judgment;
  - systemic disease/other disease rules needing unfavorable researcher judgment when required by the protocol;
  - missing/randomization anchor date adjustments.
- `pass_verify` is separated from hard evidence insufficiency and should not downgrade a subject by itself.
- Phase II/III selection should be fixed at project identity, not subject-level stage selection.

## Current Known Technical Surfaces For Review

- The app is not a git repository in this folder, so use file-level review rather than git diff.
- Main frontend is a single large `static/index.html`; this increases regression risk because UI, routing, state, and rendering are coupled.
- Important functions in `static/index.html` include:
  - auth and first-help: `renderAuth`, `doLogin`, `renderHelpPage`;
  - project routing: `renderTaskDashboard`, `renderAuditProjectList`, `renderProject`;
  - subject table: `applySubjectTableState`, `subjectFilterKeys`, `phaseReviewCellHtml`;
  - report page: `renderReport`;
  - batch actions: `batchProcess`, `bulkRerunSelected`, `bulkResetCacheSelected`, `bulkDownloadSelectedMd`.
- Important backend areas:
  - auth/permissions: `app/authz.py`, `app/router/auth.py`;
  - project/protocol deconstruction: `app/router/projects.py`, `app/pipeline/deconstructor.py`;
  - subjects/uploads/metadata: `app/router/subjects.py`;
  - OCR: `app/pipeline/ocr.py`;
  - bundling and evidence hierarchy: `app/pipeline/bundler.py`;
  - review prompt and parser semantics: `app/pipeline/reviewer.py`;
  - markdown/report exports: `app/markdown_export.py`, `app/router/reports.py`.

## What Each Hermes Model Should Produce

For every finding:

- severity: `P0`, `P1`, `P2`, or `P3`;
- evidence: screenshot/snapshot/source excerpt path or observed workflow;
- root cause hypothesis;
- why it matters to a medical monitor;
- recommended fix or verification;
- whether this is a confirmed issue or a question requiring Codex verification.

Do not make source edits. Write only the requested audit output file.

## Success Criteria For The Whole Task

- Three model outputs exist under `runs/`.
- Codex reviews them critically and creates a consensus list.
- Only validated issues are implemented.
- The system is retested by browser/API/tests after changes.
- `docs/PROJECT_CONTEXT.md` is updated with what was done, decisions, pitfalls, and remaining risk.

## Risk Boundaries

- Hermes is advisory only. Codex owns source verification, browser visual acceptance, and final code changes.
- Do not read raw clinical source folders outside this workspace.
- Do not delete or overwrite project data during this audit.
- Do not run costly OCR/LLM full reprocessing unless Codex explicitly decides it is needed.
- Do not expose API keys, `.env` content, patient-identifying raw source documents, or raw verbose model logs in user-facing outputs.

## Loop Log

- 2026-07-01 23:31:14: Task initialized by `hermes_workflow_guard.py init-task`.
- 2026-07-02 00:05: Codex confirmed app health is `ok`, `deepseek=true`, `omlx=false`.
- 2026-07-02 00:10: Codex captured Playwright screenshots and route metrics for desktop and mobile routes.
- 2026-07-02 00:16: Codex built `ui_contact_sheet.png` for model visual review.
