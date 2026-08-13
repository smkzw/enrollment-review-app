# Enrollment Review App Project Context

## 2026-08-13 Milestone: Phase 1 Frontend Shell Accepted, Phase 1.5 User Gate

Completed:

- Built the no-login React/Vite frontend shell against frozen `fixture/v1` and a typed stub repository, without reading legacy Markdown or old SPA state.
- Implemented nine Chinese-first work surfaces: 今日工作、项目看板、方案工作台、受试者与资料、入排工作台、行动中心、报告、任务与系统、系统帮助。
- Added risk-first Patient Profile, staged rule/evidence/action workbench, parent-child rule rollups, evidence precision, responsibility/action detail, deep links, narrow layout and keyboard paths.
- Independent Kimi K3 visual review first blocked the phase on an `undefined` time-window defect, then accepted the corrected shell in the same session. Codex closed two additional nonblocking findings before archival.

Important root causes retained:

- The time-window defect came from a Wire contract that assumed obsolete fields instead of the frozen fixture's anchor/direction/bounds model. Contract, ViewModel, mapper, UI and regression coverage were corrected together.
- A protocol-diff path bypassed the shared display-code mapper and leaked `REQ-02`; all user-facing required-check codes now display as `必做-xx` while internal IDs remain unchanged.
- Hash navigation plus `networkidle` can measure the prior/loading page and produce false visual-test passes. Route checks now await the new page heading, key content and loading-state exit.
- CSS `body.zoom` does not reproduce browser zoom media-query behavior. The acceptance test now uses the equivalent CSS layout viewport for a 1440 physical display at 150%/200%.

Verification:

- 19 unit/component test files, 137 tests passed.
- Build passed; known fixture-bundle warning remains nonblocking for this read-only phase.
- Playwright: 153 passed, 27 viewport-specific skips, 0 failed across 1280/1440/1920/390, keyboard, evidence paths, accessibility and screenshots.
- 38 screenshots regenerated; Codex visually accepted representative desktop, narrow and 200% equivalent-zoom pages.

Current hold point:

- Phase 1 is complete. The local trial site remains at `http://127.0.0.1:4173/` for Phase 1.5.
- User must compare 今日工作 vs 项目看板 and complete the scripted workflow UAT before Phase 2.
- Do not begin the database, real OCR/LLM, durable Graph workflow or legacy migration until the user explicitly accepts Phase 1.5.

## 2026-08-12 Milestone: Launcher Recovery And V2 Design Approval Checkpoint

User request:

- Restore the desktop launcher, then take over and reassess the complete enrollment-review workflow before another large implementation pass.
- Add a source-traceable Patient Journey covering demographics, disease state/course, medical history, medication/treatment timelines, and eligibility-related risk markers.
- Evaluate the supplied comparator UI and whether Graph engineering/multi-Agent orchestration is appropriate.
- Inventory code, documents, prior sessions, test evidence, runtime artifacts, and previous pitfalls; ask multi-round product questions before finalizing the design and implementation plan.

Launcher repair:

- Root cause: port `8900` was occupied by another local service, while the old launcher treated any HTTP 200 health response as the enrollment-review app.
- The enrollment health endpoint now exposes `service=enrollment-review-app` and `version=2.0.0`.
- Repository and desktop launchers now select/persist a free port in `8901-8910` and validate service identity.
- Live service verified at `http://127.0.0.1:8901`; launcher syntax and identity checks passed.
- Regression test added; full suite passed 131 tests with 1 optional-fixture skip.

Discovery conclusion:

- The current product is a useful file-driven prototype, but not yet a versioned clinical-fact, Patient Journey, durable workflow, or multi-role adjudication platform.
- Repeated clinical errors share structural causes: Markdown rules do not encode AND/OR/NOT, time anchors, exceptions, evidence requirements, or investigator judgment as executable components; model-text corrections have accumulated as post-processing guards.
- The next architecture should preserve upload/OCR adapters, real project samples, error regressions, phase separation, stage anchors, and compatible exports, while replacing file/Markdown business truth, the single top-level verdict, request-bound batch processing, and vague unresolved-action labels.
- Graph engineering is recommended for state, branching, recovery, retries, and human gates. It must not become a free-running Agent swarm or the clinical source of truth.
- Preliminary Agent boundary: Evidence Normalizer, Eligibility Assessor, independent Safety/Provenance Critic, deterministic validators, and structured action routing. The app is AI-led but is not the final enrollment decision authority.

Durable evidence:

- Discovery and first-round questions: `docs/REARCHITECTURE_DISCOVERY_20260812.md`.
- Task contract and loop log: `context/enrollment_review_rearchitecture_20260812_context.md`.
- Current runtime screenshots: `output/product_audit_20260812/`.

Round-one decisions:

- Target is a single-Mac, single-user local application; do not design a multi-user approval system.
- The app should lead the review and state what is not met or unresolved. Every such item must specify which party should provide which exact evidence, description, judgment, or follow-up before the rule can be clarified.
- Same-subject incremental and full upload modes are both required.
- This product's Patient Profile covers all longitudinal events from the earliest evidenced point through prescreen/screening/baseline, with eligibility links and source traceability.
- Protocol/amendment version is authoritative. Only an amendment changes standards; Q&A/letters/email/medical interpretation may clarify ambiguity and must be warned when contradictory.

Current hold point:

- Second-round decisions are complete: delete login/multi-account behavior; support immutable full snapshots and deduplicated incremental uploads; preserve stage history; allow source-preserving single-user OCR/fact correction; use non-final stage judgments; keep full test data but highlight only eligibility-relevant/abnormal/borderline/trending results on the Patient Profile first screen.
- The system must distinguish incomplete medical-record documentation from genuinely absent procedures or source files. It must not convert a history item omitted from the screening note into a definitive absence or a generic request for prior source documents.
- Do not begin the large rearchitecture until the third-round questions in `docs/REARCHITECTURE_DISCOVERY_20260812.md` resolve history-evidence semantics, fixed action owners, dashboard aggregation, action closure, legacy migration, and visual-prototype sequencing.

Third-round decisions:

- Screening-record positive history/long disease duration is usable current evidence but requires an enhanced provenance reminder.
- Remove subject as an action owner; all collection, questioning, documentation, analysis, and closure route through investigator-side, CRC, CRA, or sponsor medical/project roles.
- Dashboard uses primary status plus categorized issue counts.
- The system may auto-close actions after new evidence/recalculation; the user may override, with a complete state-change record.
- Legacy projects are read-only counterexample anchors. The new architecture creates fresh projects from the protocol and reruns the full workflow rather than mutating legacy project state.
- Build and approve an interactive workflow prototype before data-layer and Graph implementation.

Independent conference and final architecture:

- Clinical and architecture participants independently reviewed the confirmed requirements and current source/runtime constraints.
- Shared conclusion: the principal defects are weak clinical representation, non-durable state and missing deterministic gates; adding more free-running Agents would not solve them.
- Selected runtime spine: SQLite/WAL + durable Job/Checkpoint + explicit state machine. Protocol Deconstructor, Evidence Normalizer and Eligibility Assessor are bounded typed semantic calls; Safety/Provenance Critic is conditional, veto/downrank/action-only.
- Evidence conflicts hard-block the contested component and remain side-by-side; V2 removes the old prior-source auto-preference.
- Auto-close is gap-specific and source-linked in a new ReviewRun. Arbitrary uploads never close actions; manual override/reopen remains fully audited.
- Old projects remain read-only counterexample anchors. V2 projects start from the original protocol and rerun the complete workflow.

Final artifacts:

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- `reviews/codex_conference_enrollment_review_design_conference_20260812_review.md`
- `metrics/enrollment_review_design_conference_20260812_conference_metrics.md`

Current hold point:

- Product clarification and independent conference are complete.
- Wait for explicit user approval of the final design and Phase 0-9 plan before starting V2 implementation.
- No V2 business code, old project state or clinical review result has been changed at this checkpoint. The repaired legacy service remains available at `http://127.0.0.1:8901` when running.

## 2026-08-13 Milestone: Phase 1.5 Acceptance Method Changed

User decision:

- The user will not organize or personally perform a human medical-monitor UAT round for the Phase 1 prototype.
- Phase 1.5 final acceptance is instead performed by multiple independent model reviewers role-playing a lazy but expert Chinese senior clinical-trial medical monitor in the real local browser.
- Reviewers must freely explore clinical comprehension, evidence traceability, rule hierarchy, Patient Profile, interaction and visual quality. They must distinguish current synthetic-prototype behavior from Phase 2-8 capabilities that are not implemented yet.
- Exact model names requested by the user are used only when the current global route manifest registers them; actual provider, model, session and fallback evidence must be retained and no route may be impersonated or force-bypassed.

Completed technical preparation:

- Phase 1.5 scripted tasks, reset path, desktop launcher and independent Chinese UAT recorder are implemented and verified.
- The former human-UAT task was closed as technical preparation and archived. Its historical evidence remains immutable; its requirement for at least ten human participants was superseded by the later user decision.

Current hold point:

- Active task: `.trellis/tasks/08-13-phase1-5-agent-monitor-uat`.
- Phase 2 remains blocked until independent visual/interaction and clinical/evidence role reviews complete, current-phase blockers are corrected and retested, and Codex records a final acceptance decision.

## 2026-07-02 Milestone: Hermes Multi-Model UI/Product Audit And Narrow Fix Loop

User request:

- Use the Codex x Hermes cooperation mechanism and the requested model routes `qwen3.7-plus`, `minimax-m3`, and `mimo-v2.5`.
- Run a full-system, full-flow critique of the enrollment-review app for bugs, aesthetics, UI interaction, operational logic, and alignment with the user's original requirements.
- Organize cross-model discussion, form consensus, then tune/debug/retest in a LOOP.

Workflow performed:

- Created Codex/Hermes task packet `enrollment_fullflow_model_audit_20260701`.
- Built bounded review context:
  - `context/enrollment_fullflow_model_audit_20260701_context.md`;
  - Playwright route snapshots under `output/model_audit_20260701/screenshots/`;
  - UI contact sheet `output/model_audit_20260701/screenshots/ui_contact_sheet.png`;
  - UI snapshot summaries under `output/model_audit_20260701/snapshots/`.
- Model outputs:
  - Qwen 3.7 Plus: `runs/hermes_enrollment_audit_qwen37_20260701.md`;
  - MiniMax M3 fallback no-tool audit: `runs/hermes_enrollment_audit_minimaxm3_20260701.md`;
  - MIMO V2.5 fallback no-tool audit: `runs/hermes_enrollment_audit_mimo25_20260701.md`.
- Codex consensus and review artifacts:
  - `runs/hermes_enrollment_model_consensus_20260702.md`;
  - `reviews/codex_enrollment_fullflow_model_audit_20260701_review.md`;
  - `metrics/enrollment_fullflow_model_audit_20260701_metrics.md`.

Important route/pitfall notes:

- Qwen generated a usable visual/text audit but was slow and produced little stdout.
- MiniMax and MIMO long file-read/write prompts timed out; both were rerun as bounded no-tool advisory reviewers.
- MiniMax proposed moving baseline/randomization anchor date to project-level metadata; Codex rejected this because each subject can have a different baseline/randomization date. Keep subject-level phase anchor dates.
- Do not blindly adopt model suggestions. Codex must verify against clinical workflow, source code, and rendered UI.

Accepted and implemented fixes:

- Mobile table usability:
  - Before patch, mobile subject list and report pages clipped table content while page overflow was hidden.
  - `.table-wrap` now uses horizontal scrolling with touch scrolling, and mobile-only hints tell users to swipe horizontally.
  - Desktop width behavior was preserved.
- User-facing terminology cleanup:
  - Replaced visible `LLM` wording with `系统` / `智能审核` / `解析反馈`.
  - Replaced primary `Markdown` labels with `导出报告` / `报告导出` / `个人报告`, while preserving `.md` export files because Markdown report output is still an explicit requirement.
- Phase selector clarity:
  - The subject-list stage dropdown is now labeled `批量操作阶段`.
  - Explanatory copy says it affects only batch review/rerun/export; each row can directly enter its screening or baseline phase.

Validation completed:

- `python3 -m compileall app tests scripts`
  - passed.
- Extracted frontend JS from `static/index.html`, then `node --check /tmp/enrollment_index.js`
  - passed.
- `python3 -m unittest discover -s tests`
  - 130 tests passed, 1 skipped fixture.
- Post-patch Playwright metrics:
  - mobile subject list `.table-wrap`: `clientWidth=362`, `scrollWidth=1741`, `scrollLeft` changed to `1379`, `overflowX=auto`;
  - mobile report `.table-wrap`: `clientWidth=362`, `scrollWidth=904`, `scrollLeft` changed to `542`, `overflowX=auto`;
  - desktop subject list: no body overflow and no horizontal scroll needed;
  - checked visible text had no `LLM` or primary `Markdown` labels.

Residual risks:

- Health check during this audit returned `{"status":"ok","omlx":false,"deepseek":true}`. This patch did not fix launcher/oMLX startup; run a separate launcher test before claiming full offline OCR readiness.
- Mobile is now reachable by horizontal scrolling, but a touch-native card layout remains future product work.
- The large single-file frontend remains a maintainability risk; do not refactor it without a separate scoped plan.

## 2026-06-25 Milestone: MG-K10-SAR III New Project, Center 31 First Batch, Parser QC Fixes

User request:

- Create/test a new MG-K10-SAR project from the uploaded protocol and audit `Ⅲ期` only.
- Use source documents under `/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/13. CFDI核查/自查/入排/各中心原始入排资料`.
- Run `31 河北省中医院` subjects as the first batch.

Implemented run:

- Created project `MG-K10-SAR-III` from `/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx`.
- Project metadata after extraction:
  - project code `MG-K10-SAR-III`;
  - protocol ID `MG-K10-SAR-001`;
  - version/date `V2.1 / 2025-09-19`;
  - fixed stage `Ⅲ期`.
- Center 31 subjects processed:
  - `31001`, `31006`, `31008`, `31010`, `31013`, `31014`, `31015`, `31016`, `31017`, `31018`.
- Each subject was processed through both `screening_run_in` and `baseline_randomization`.
- Final baseline project-list verdicts:
  - `fail`: `31001`, `31010`, `31015`;
  - `investigator`: `31008`, `31014`;
  - `insufficient`: `31006`, `31013`, `31016`, `31017`, `31018`.
- Key run logs:
  - `projects/MG-K10-SAR-III/rerun_logs/mgk10sar_iii_center31_batch_20260625_135429.json`;
  - `projects/MG-K10-SAR-III/rerun_logs/mgk10sar_iii_center31_qc_after_backfill_20260625_144142.json`;
  - `projects/MG-K10-SAR-III/rerun_logs/MG-K10-SAR-III_center31_baseline_markdown_20260625_144817.md`;
  - backfill logs under `projects/MG-K10-SAR-III/rerun_logs/backfill_center31_*_20260625_*.json`.

System issues found and fixed during this batch:

- Protocol schedule-stage inference had treated a shared MG-K10 II/III schedule table as `Ⅱ期` because it inferred phase from generic terms such as treatment/safety follow-up. Fixed stage inference so generic schedule terms do not imply II, and scoped universal phases to the selected project stage.
- LLM deconstruction header could hallucinate protocol IDs such as `MG-K10-SAR-301（假设）`. Added header sanitization from extracted protocol metadata.
- Parser guards were using hard-coded rule IDs such as `EX-15` and `EX-11` from D001 semantics. MG-K10 reuses those IDs for different criteria, so the parser incorrectly downgraded MG-K10 `EX-15` alcohol to investigator judgment. Fixed compound-condition guards to be semantic, not ID-only.
- Parent rows could include cross-rule contamination, for example EX-07 parent mentioning EX-09g. Parent rows are now recomputed only from same-prefix children.
- If a model omits parent rows but outputs child rows, the parser now inserts inferred parent rows and recomputes their verdicts. This restored all MG-K10 reports to the expected 56 rule rows.
- Child rows that explicitly say the current child did not trigger, while redirecting residual concern to another child such as `EX-09g`, now keep the current child local and pass the current child.
- Current-stage evidence gaps, such as missing D1/baseline blood chemistry while screening ALT/AST are below the exclusion threshold, are downgraded from hard fail to `insufficient` with a specific evidence-gap explanation, not a generic researcher-compound warning.
- Syphilis exception logic is now semantic and not limited to D001 `EX-22`; any syphilis-specific antibody-positive row requires both non-specific antibody negativity and explicit cured-prior-infection judgment.
- `review_raw.md` is now preferred for backfill when available, so old normalized reports do not contaminate new parser logic. `review_report.md` remains the fallback if raw output is absent.
- ASCII `-` in the verdict cell is now mapped to `na`.
- Markdown export wording now uses the neutral wording `提醒项`, not `低干预` or `低强度`.

Validation completed:

- `python3 -m unittest tests.test_phase_workflow`
  - 97 tests passed, 1 skipped.
- `python3 -m compileall app tests scripts`
  - passed.
- Local service restarted from the desktop launcher and health returned `{"status":"ok","omlx":true,"deepseek":true}`.
- API verification showed 10 center-31 subjects in `MG-K10-SAR-III`, all `reviewed`, all center code `31`, all ICF date `2025-07-02`.
- File QC confirmed all 20 stage reports have 56 rule rows and no scanned internal phrases such as `疾病存在、异常存在或用药存在本身不等于完整排除触发`, `definitive`, `按要求排除`, `仅III/仅Ⅲ`, or cross-parent `EX-09g` leakage.

Operational notes:

- First-pass OCR is the time bottleneck: about 43-61 pages per subject and roughly 94-143 seconds per first phase. Baseline reruns usually hit cache fully, except subjects with an extra baseline blood routine file, where only the new page was OCRed.
- The center-31 batch was run serially for QC traceability. OCR now reports max 8 VLM calls, and cache reuse worked as expected.
- `31017` included one JPG in prior records; it uploaded and OCRed without pipeline failure. Follow-up QC should still inspect whether its content materially contributes to historical evidence.

## 2026-06-22 Milestone: Historical Diagnosis/Duration Provenance Warning

User correction:

- For protocol criteria requiring historical facts or duration, such as prior allergic rhinitis diagnosis for more than 3 years, earliest symptom onset more than a certain period ago, prior treatment, prior medication exposure, prior testing, or prior surgery, screening/baseline narratives are not enough to prove the historical fact by themselves.
- Prior medical records, diagnosis certificates, discharge summaries, historical test reports, prescriptions, or older progress notes must have higher evidentiary priority for these historical facts.
- If only screening/baseline records contain a transcribed history statement and no older source file is available, the system should warn the reviewer instead of treating the item as a plain pass.

Implemented decision:

- Added a distinct internal rule verdict `pass_verify`.
- LLM output should use `✅通过（需验证：病史来源需溯源验证）` when a historical diagnosis/duration item is apparently met but supported only by screening/baseline history narrative.
- `pass_verify` does not downgrade the overall report by itself. If there is no `fail` / `insufficient` / `investigator`, the subject overall verdict remains `pass`.
- Project/center Markdown exports do not include `pass_verify` items in待处理明细; they count them separately as `溯源提醒`. Subject exports continue to show all rule rows.
- Frontend report pages show a separate“溯源提醒” success-style callout, distinct from ordinary“证据不足”.
- The evidence bundle and review system prompt now use contextual evidence hierarchy:
  - current-visit facts such as ICF, current vitals, current lab/exam, and current scores prioritize screening/baseline source documents;
  - historical facts and duration prioritize historical source documents.

Implementation notes:

- `app/pipeline/reviewer.py`
  - added historical fact provenance instructions to the review system prompt and user prompt;
  - parser now recognizes `pass_verify`;
  - parser now checks“不通过/fail” before generic“通过/pass” to avoid false pass mapping.
- DeepSeek V4 Pro prompt decision:
  - local `.env` already uses `REVIEW_MODEL=deepseek-v4-pro` and `REVIEW_BACKEND=deepseek`;
  - DeepSeek official docs say JSON Output requires `response_format`, prompt wording containing json, and a JSON example, but may occasionally return empty content;
  - current review artifacts and parsers are Markdown-table based, so the safer change is tightening the existing Markdown contract rather than switching output protocol midstream;
  - DeepSeek official docs also state thinking mode is enabled by default for `deepseek-v4-pro`; the prompt therefore says not to output chain-of-thought and asks only for final conclusion plus source quotes.
- `app/pipeline/bundler.py`
  - revised the evidence hierarchy notice to separate current facts from historical facts.
- `app/models.py`
  - added markdown rendering for `pass_verify`.
- `app/markdown_export.py`
  - added `pass_verify` labels and `溯源提醒` summary counts, while excluding `pass_verify` from issue sections.
- `static/index.html`
  - added `pass_verify` badges and report callout.
- `tests/test_phase_workflow.py`
  - added regression coverage for `pass_verify`, plain“不通过”, prompt wording, and Markdown issue exclusion.

## 2026-06-22 Milestone: Project Info Management, Global Centers, Shared Read-Only, Markdown Export

User requirements addressed:

- Added a project information management page as a project tab and project-list entry.
  - Project name, project code, protocol ID, protocol version/date, source filename, and fixed study stage can be edited.
  - Only the project creator or `admin` can edit project metadata or rules.
  - Project code changes safely rename the project directory and update subject `project_code` values.
- Changed the permission model after user correction:
  - all logged-in users can read all projects, subject lists, and existing review reports;
  - project mutation remains limited to project creator or `admin`;
  - subject upload, OCR reset, rerun/re-review, and subject deletion are limited to the subject creator/uploader or `admin`;
  - legacy subjects without `owner_username` remain modifiable by the project creator/admin, so old data is not silently taken over by another user.
- Added global center roster support:
  - centers are now stored globally in `projects/_system/centers.json`, not inside one project;
  - all users can select a center created by another user;
  - ordinary users can modify/delete only their own centers; `admin` can modify all;
  - subject creation and subject upload can set `center_code` and `center_name`, and new centers become reusable globally.
- Added center roster management in the project information page:
  - manual add/edit/delete center rows;
  - batch import from Excel/CSV/TXT or pasted text;
  - center deconstruction endpoint first parses structured rows, then asks the deconstruction LLM to refine the draft, falling back to the structured draft if LLM refinement fails.
- Added Markdown export:
  - project-level Markdown report;
  - center-level Markdown report;
  - subject-level Markdown report;
  - project/center reports omit passed rules and focus on not-qualified, evidence-insufficient, investigator-judgment, or missing-report items;
  - subject reports include every rule row.
- Updated help page:
  - global center workflow;
  - shared read-only vs owner-write permissions;
  - subject upload center selection;
  - batch processing limited to owned/modifiable subjects;
  - Markdown export differences by project/center/subject scope.

Files changed:

- `app/authz.py`
  - separated read access from modify access;
  - added subject-level ownership checks.
- `app/models.py`
  - added `owner_username`, `center_code`, and `center_name` to `SubjectInfo`.
- `app/centers.py`
  - new global center roster helpers and Excel/CSV/TXT/text parsing.
- `app/markdown_export.py`
  - new Markdown report generation for project, center, and subject scopes.
- `app/router/projects.py`
  - project metadata PATCH endpoint;
  - global center list/deconstruct/save endpoints;
  - project/center/subject Markdown export endpoint;
  - project mutation endpoints now require project creator/admin.
- `app/router/subjects.py`
  - subject creation/upload stores center and owner;
  - subject mutation endpoints require subject owner/admin.
- `app/router/pipeline.py`
  - OCR/review/process endpoints now require subject owner/admin because they mutate derived outputs.
- `static/index.html`
  - added project info tab, center management, center import, Markdown export tab, upload/add-subject center inputs, read-only button logic, and help updates.
- `tests/test_phase_workflow.py`
  - updated project visibility tests for shared read-only model;
  - added subject ownership and global center tests.

Validation completed:

- `python3 -m compileall app tests scripts`
  - passed.
- Extracted JS from `static/index.html`, then `node --check /tmp/enrollment_index.js`
  - passed.
- `python3 -m unittest discover -s tests`
  - 27 tests passed, 1 skipped because the local MG-K10-SAR/06003 OCR cache fixture is absent.
- Service health:
  - `http://127.0.0.1:8900/api/health` returned `{"status":"ok","omlx":true,"deepseek":true}` during QC.
- Playwright visual/API QC:
  - desktop `1440x980` and mobile `390x844`;
  - routes covered: audit project list, MG-K10-SAR project info/global centers, Markdown export, add-subject modal, upload modal;
  - page-level horizontal overflow was 0 on checked pages;
  - browser console errors: 0;
  - Markdown export API returned a project Markdown report with expected headings.

Screenshot/artifact paths:

- `output/playwright/shared-qc-desktop-audit-list.png`
- `output/playwright/shared-qc-mobile-audit-list.png`
- `output/playwright/shared-qc-desktop-project-info-centers-v2.png`
- `output/playwright/shared-qc-mobile-project-info-centers.png`
- `output/playwright/shared-qc-desktop-markdown-export.png`
- `output/playwright/shared-qc-mobile-markdown-export.png`
- `output/playwright/shared-qc-desktop-add-subject-center-modal.png`
- `output/playwright/shared-qc-upload-center-modal-targeted.png`
- `output/playwright/shared-qc-markdown-project.md`
- `output/playwright/shared-permissions-center-export-qc.json`

Operational notes and pitfalls:

- A first implementation treated centers as project-scoped. The user corrected this: centers are global and reusable across projects/users. The code now stores them under `_system`.
- A first permission pass accidentally put write checks on read-only project endpoints; this was corrected so all logged-in users can read projects/phases/reports.
- The service launcher reported the old service as running while a subsequent curl briefly failed. For QC, the app was run through `scripts/run_enrollment_review_terminal.command`; before final handoff, start the visible service window rather than leaving a Codex tool session as the only service process.
- Existing MG-K10-SAR subjects created before `owner_username` exist as legacy rows; they are treated as project-owner/admin editable.

## 2026-06-22 Milestone: Phase Is Project Identity, Subject List No Stage Picker, Simple ER Icon

User requirements addressed:

- A selected protocol phase is now part of the project identity, not a subject-list audit option.
  - If a protocol contains both `Ⅱ期` and `Ⅲ期`, the user must choose the phase during protocol deconstruction.
  - Newly created/saved multi-phase protocol projects use a phase suffix in the project code, such as `MG-K10-SAR-II` or `MG-K10-SAR-III`.
  - The saved project workflow is scoped to the selected phase, with `study_stages` reduced to one value and `requires_study_stage_selection=false`.
  - Subjects belong to that project only; they are not shared across II/III phase projects.
- The subject list/project page no longer shows a `研究阶段` dropdown.
  - It now only shows the audit timepoint/stage dropdown, such as `筛选/导入期` or `基线/随机前`.
  - The page displays a fixed project-phase note, for example `项目期别：Ⅲ期（解构时已固定，受试者不与其他期别项目共享）`.
  - If an old legacy project still has a mixed-phase workflow and no fixed `study_stage`, the UI blocks temporary subject-page phase selection and tells the user to re-deconstruct/save as a single-phase project.
- The logo was simplified again after visual QC:
  - removed the `入排审核` text;
  - removed the `ELIGIBILITY REVIEW` text;
  - removed the bottom ECG/horizontal line;
  - retained only a compact ER shield/check/search icon.

Files changed:

- `app/router/projects.py`
  - added helpers to treat selected phase as a project-code suffix for multi-phase protocols;
  - fixed the edge case where an already scoped workflow still has `protocol_study_stages`, so saving a draft still produces `-II`/`-III`;
  - persists project workflow after deconstruction as single-phase scoped workflow.
- `app/phases.py`
  - `load_review_workflow()` now reads `config.json`; if `study_stage` is fixed, returned workflow is single-phase and does not ask for phase selection.
- `app/router/pipeline.py`
  - review/process endpoints default to the project config's fixed `study_stage`.
- `static/index.html`
  - removed the subject-list research-stage selector;
  - added fixed project-phase display and legacy mixed-phase warning;
  - updated help text so monitor workflow says phase is selected during deconstruction, not during subject audit.
- `static/header_logo.svg`
  - simplified to icon-only ER logo.
- `tests/test_phase_workflow.py`
  - added coverage for `-II`/`-III` project-code suffixing, including already-scoped workflows;
  - added coverage for workflow scoping from project config;
  - skipped the MG-K10-SAR/06003 evidence bundle cache test when the local OCR cache fixture is absent.

Validation completed:

- `python3 -m unittest discover -s tests`
  - 26 tests passed, 1 skipped because current local MG-K10-SAR/06003 fixture has raw files but no OCR `cache` directory after prior delete/rebuild testing.
- `python3 -m compileall app tests scripts`
  - passed.
- `node --check` on extracted `static/index.html` script
  - passed.
- Source scan confirmed no remaining `studyStageSelect`, old `header_logo.png`, logo text, logo English text, or `erLine` artifacts.
- Service restarted through the desktop-entry fallback path:
  - `http://127.0.0.1:8900/api/health` returned `{"status":"ok","omlx":true,"deepseek":true}`.
- API verification:
  - `/api/projects/MG-K10-SAR/phases` returned `study_stages=["Ⅲ期"]` and `requires_study_stage_selection=false`.
- Playwright visual QC:
  - desktop and mobile project page had no `studyStageSelect`;
  - `reviewPhaseSelect` remained present;
  - fixed project-phase text was visible;
  - page-level horizontal overflow was 0;
  - logo used `/static/header_logo.svg`.

Screenshot artifacts:

- `output/playwright/qc-desktop-header-logo-crop.png`
- `output/playwright/qc-mobile-header-logo-crop.png`
- `output/playwright/qc-desktop-project-fixed-stage-logo.png`
- `output/playwright/qc-mobile-project-fixed-stage-logo.png`

Operational notes and pitfalls:

- Existing legacy project `MG-K10-SAR` is still kept at its original path to avoid breaking current 06002/06003/06004 test data, but its workflow is now treated as fixed `Ⅲ期` because `config.json` has `study_stage="Ⅲ期"`.
- New multi-phase deconstruction/save flows should create phase-specific project codes (`-II`/`-III`), so separately deconstructed phases do not share subject folders.
- The local service usually cannot stay up as a hidden child process from Codex; the reliable path is the existing launcher fallback that opens a visible Terminal service window. Keep that service window open.

## 2026-06-22 Milestone: Standalone Phase Rules, Re-Deconstruction Layout QC, ER Logo SVG

User requirements addressed:

- After the user selects `Ⅱ期` or `Ⅲ期`, protocol deconstruction must treat that selected phase as an independent project ruleset.
  - Do not mix the other phase into formal IN/EX rules.
  - Do not compare against the other phase.
  - Do not output wording such as `仅Ⅲ期`, `适用期别：Ⅲ期`, `按本次所选Ⅲ期编号`, or `与Ⅱ期对应条款一致/差异`.
- MG-K10-SAR saved III期 rules were cleaned to remove the prior `Ⅱ期对应/实质一致` notes while preserving the official III期 parent IN count and EX count.
- The re-deconstruction project selector layout was fixed from the root:
  - project select now uses compact option labels;
  - full long protocol titles wrap inside the project summary card;
  - card/grid/flex containers now use `min-width:0`, wrapping, and bounded widths to prevent page-level horizontal overflow.
- The old PNG logo was removed and replaced with one self-contained SVG asset:
  - `static/header_logo.svg`;
  - the asset is now an icon-only ER mark after later visual QC;
  - the frontend does not assemble the logo from a separate image plus adjacent logo text.

Files changed:

- `app/deconstructor.py`
  - updated the LLM deconstruction prompt to require standalone selected-phase rules;
  - strengthened `sanitize_selected_stage_scope_language()` to remove mixed-stage notes independent of word order.
- `app/router/projects.py`
  - updated re-deconstruction stage instructions sent to the LLM.
- `projects/MG-K10-SAR/criteria_rules.md`
  - removed mixed II/III explanatory notes from the saved III期 rules.
- `static/index.html`
  - replaced logo reference with `/static/header_logo.svg`;
  - fixed project selector, project summary, project header, rule toolbar, workbench grid, card, and mobile wrapping behavior;
  - mapped backend `needs_evidence` verdict to the Chinese `待补证` badge.
- `static/header_logo.svg`
  - new single-file ER logo.
- `tests/test_phase_workflow.py`
  - updated tests for standalone selected-phase rules and SVG logo serving.

Validation completed:

- `python3 -m unittest discover -s tests`
  - 23 tests passed.
- `python3 -m compileall app tests scripts`
  - passed.
- `node --check` on extracted `static/index.html` script
  - passed.
- MG-K10-SAR rules grep check:
  - no `仅III/仅Ⅲ`, `适用期别`, `对应条款`, `对应避孕`, `对应知情`, `实质一致`, `按本次所选`, `另一阶段`, `另一期别`, or `一致/差异` remained in `projects/MG-K10-SAR/criteria_rules.md`.
- Live service restored through the desktop-entry fallback path:
  - `http://127.0.0.1:8900/api/health` returned `{"status":"ok","omlx":true,"deepseek":true}`.
- Browser QA via Playwright:
  - 18 screenshots across desktop `1440x980` and mobile `390x844`;
  - routes covered: login, task home, help, first-deconstruct, re-deconstruct, audit, project subjects, upload modal, project rules, and 06004 screening report;
  - all routes used `/static/header_logo.svg`;
  - browser console had 0 errors;
  - page-level horizontal overflow count was 0.
- MG-K10-SAR long-title re-deconstruction专项视觉检查:
  - desktop and mobile screenshots both had `docScrollWidth == innerWidth`;
  - project select displayed `MG-K10-SAR · MG-K10-SAR-001 · V2.1 · 2025-09-19 · Ⅲ期`;
  - full long project title wrapped inside the summary card rather than stretching the page.

Screenshot artifacts:

- `output/playwright/visual-qc-summary.json`
- `output/playwright/qc-desktop-re-deconstruct-mgk10.png`
- `output/playwright/qc-mobile-re-deconstruct-mgk10.png`

Operational notes:

- The service is currently running on port `8900` from the visible service-window fallback. Keep that Terminal service window open.
- The desktop launcher remains `/Users/smkzw/Desktop/启动入排审核系统.command`.

## 2026-06-21 Milestone: Login, Deconstruction Workspaces, Batch Audit Entry, System Logo

User requirements addressed in this milestone:

- Add a restrained custom system logo to the top-right of every page.
- Prevent generic protocol titles such as `临床研究方案` from being shown or saved as the project name.
- Add a lightweight local login system:
  - first entry requires registration;
  - username is required;
  - password is optional;
  - registration does not auto-login;
  - first registration shows a full-system help page before login.
- Split post-login entry into three explicit routes:
  - `#/first-deconstruct`: new project, first protocol deconstruction, cannot overwrite an existing project;
  - `#/re-deconstruct`: existing project protocol re-deconstruction, with current project info, upload area, LLM feedback, original vs revised rule panes, change summary, save/cancel;
  - `#/audit`: existing project audit list and batch audit guidance.
- Keep MG-K10-SAR phase-aware audit controls visible:
  - stage selector shows `Ⅱ期` and `Ⅲ期`;
  - review phase selector shows screening/run-in and baseline/randomization stages;
  - batch processing requires the phase/stage controls.

Files changed:

- `static/index.html`
  - unified header with `/static/header_logo.svg`;
  - login/register/help views;
  - task home with three work entry cards;
  - first deconstruction workspace;
  - re-deconstruction workspace;
  - audit project list and batch audit guide;
  - project-name display guard for generic protocol titles.
- `static/header_logo.svg`
  - replaced the previous CMS/康哲 asset with a custom ER icon.
- `app/main.py`
  - mounts `/static` with `StaticFiles`.
- `app/router/auth.py`
  - local lightweight auth endpoints.
- `app/router/projects.py`
  - re-deconstruction endpoint and generic-project-name save guard.
- `tests/test_phase_workflow.py`
  - added tests for generic project name guarding, static logo serving, and passwordless local auth.

Validation completed:

- `python3 -m unittest discover -s tests`
  - 14 tests passed.
- `python3 -m compileall app scripts tests`
  - passed.
- `node --check` on extracted `static/index.html` script
  - passed.
- `zsh -n scripts/start_enrollment_review.command`
  - passed.
- `zsh -n /Users/smkzw/Desktop/启动入排审核系统.command`
  - passed.
- Browser QA via Playwright against `http://127.0.0.1:8900`:
  - logo visible on register/login/help/task/first-deconstruct/re-deconstruct/audit/project pages;
  - first registration enters help page and remains logged out;
  - login reaches three-entry task home;
  - first-deconstruct page only offers `保存为新项目`;
  - re-deconstruct page shows original vs revised panes and project selector;
  - audit list shows MG-K10-SAR title as `MG-K10-SAR`, not `临床研究方案`;
  - MG-K10-SAR project page shows `Ⅱ期`/`Ⅲ期` selector and screening/baseline review phases;
  - browser console had 0 errors.
- Screenshot artifact:
  - `output/playwright/audit-list-with-logo.png`.

Operational notes:

- The temporary QA user `qa_codex` was removed after browser testing.
- If the app is already running from an old process, restart it so the new `/static` mount takes effect.
- The desktop launcher remains:
  - `/Users/smkzw/Desktop/启动入排审核系统.command`.

Known continuation items:

- Continue full clinical-flow regression on MG-K10-SAR III期 for 06002/06003/06004 after this UI refactor, especially classified upload, OCR, phased review, and revised protocol deconstruction behavior.
- The current UI still uses the existing subject-level report rendering; deeper reviewer-oriented HTML report redesign should remain source-bound and avoid exposing internal evidence IDs or model/debug terms.

## 2026-06-21 Milestone: Project Ownership, Admin Account, One-Time Help

User requirements addressed:

- Add a super administrator account:
  - username: `admin`
  - password: `20121116`
  - role: `admin`
  - can view, add, edit, audit, and delete all projects.
- Ordinary users can only view and operate projects they created.
- Ordinary users cannot see other users' projects in project lists.
- Ordinary users can delete their own projects only.
- Add a first-login vs repeat-login mechanism:
  - normal user records now include `help_seen`;
  - first login shows the full-system help page if `help_seen=false`;
  - clicking the help completion button marks the user as read;
  - later logins no longer force the first-use help page.

Implementation notes:

- `app/authz.py` is the shared authentication/authorization layer.
- API requests carry:
  - `X-Enrollment-User`
  - `X-Enrollment-Token`
- SSE processing uses query params `user` and `token` because `EventSource` cannot send custom headers.
- `ProjectConfig` now includes `owner_username`.
- Existing legacy projects without `owner_username` are accessible to admin, and to the single registered normal user when there is exactly one normal user. This preserves current MG-K10-SAR access for the existing local `smkzw` account while still hiding projects once explicit owners are assigned.
- Frontend delete buttons are display-only affordances; backend authorization is the source of truth.

Validation completed:

- `python3 -m unittest discover -s tests`
  - 15 tests passed.
- `python3 -m compileall app tests`
  - passed.
- `node --check` on extracted `static/index.html` script
  - passed.
- Live API checks against `http://127.0.0.1:8900`:
  - admin login returned role `admin` and `requires_help=false`;
  - normal `smkzw` login returned role `user`;
  - admin project list included `CMS-D001`, `MG-K10-SAR`, and `test01`;
  - normal `smkzw` still sees current legacy projects under the single-normal-user compatibility rule.
- Browser QA via Playwright:
  - admin login did not route to the help page;
  - header showed `admin（超级管理员）`;
  - audit list showed all projects;
  - each project card showed a `删除项目` button for admin.

Pause note:

- User instructed: pause now and resume only after explicit user instruction.
- Current implemented scope before pause:
  - `admin` / `20121116` super administrator exists as a built-in account.
  - Normal users have token-based sessions, `help_seen` first-login tracking, and role `user`.
  - Project ownership is stored in `owner_username`.
  - Project APIs, subject APIs, pipeline APIs, and report/evidence APIs enforce owner/admin access on the backend.
  - Frontend stores `enrollmentReviewUser`, `enrollmentReviewToken`, and `enrollmentReviewRole`.
  - Frontend shows project delete controls only when backend returns `can_delete=true`.
  - Admin sees all projects and delete controls for all projects.
  - Normal users see only owned projects; legacy projects without owner are visible to the single normal local user for compatibility.
- Current verification before pause:
  - `python3 -m unittest discover -s tests`: 15 tests passed.
  - `python3 -m compileall app tests`: passed.
  - `node --check` on extracted frontend script: passed.
  - live admin API check: admin sees `CMS-D001`, `MG-K10-SAR`, `test01`, all with `can_delete=true`.
  - browser console check: 0 errors.
- Local service state at pause:
  - Desktop launcher was used to restart the service.
  - `http://127.0.0.1:8900/api/health` returned OK before pause.
  - Service may still be running from the desktop launcher; confirm with `lsof -nP -iTCP:8900 -sTCP:LISTEN` when resuming.

## 2026-06-21 Milestone: Stage-Specific Protocol Deconstruction and MG-K10-SAR III期 Regression

New user requirements addressed:

- Protocol deconstruction must keep parent IN/EX counts, order, and numbering exactly aligned with the protocol for the selected study stage.
- If a protocol contains both II/III phases, the system must ask the user to choose II期 or III期 before deconstruction; it must not mix both phases into one ruleset.
- Complex parent criteria may have subcomponents such as `IN-04a`/`IN-04b`, but subcomponents must stay under the official parent ID and must not create new parent IN/EX numbers.
- Baseline-and-earlier required procedures from the schedule table remain in a separate workflow-check appendix and must not change formal IN/EX counts.

Implementation changes:

- `app/deconstructor.py`
  - strengthened the LLM deconstruction prompt with exact parent numbering/count rules;
  - added explicit selected-stage behavior for II/III protocols;
  - fixed DOCX criteria extraction to skip table-of-contents entries and use body headings;
  - supports `extract_docx_criteria(..., study_stage="Ⅲ期")`, which now returns MG-K10-SAR III期 as IN=7 and EX=16.
- `app/router/projects.py`
  - all deconstruction endpoints now accept `study_stage`;
  - multi-stage protocols return HTTP 409 with `study_stage_required` before deconstruction if no stage is selected;
  - new projects save `study_stage` in project config.
- `app/models.py`
  - `ProjectConfig.study_stage` added.
- `static/index.html`
  - first deconstruction, re-deconstruction, new-project modal, and project deconstruction modal now show a deconstruction-stage selector;
  - project cards and re-deconstruction project info display saved `解构期别`;
  - report links keep the selected review phase; report pages default to the first protocol review phase rather than `full`.
- `app/pipeline/reviewer.py`
  - review prompt now says each parent rule ID may appear only once;
  - parser merges duplicate parent rule rows conservatively, e.g. pass + investigator becomes investigator.
- `app/router/reports.py`
  - report/bundle endpoints fall back from `phase=full` to the first configured protocol review phase when no `full` artifact exists.
- `projects/MG-K10-SAR/criteria_rules.md`
  - corrected to the selected III期 parent structure:
    - IN-01 to IN-07 only;
    - IN-05 is baseline EOS `>=300/μL`;
    - EX-01 to EX-16 only;
    - no duplicate IN-02/IN-03 and no EX beyond protocol parent count.
- `projects/MG-K10-SAR/config.json`
  - `study_stage` set to `Ⅲ期`.

Important pitfalls found and fixed:

- Old DOCX extraction started from the table of contents (`5.1 入选标准`, `5.2 排除标准`) and then counted schedule/procedure rows as exclusion criteria, causing bogus counts such as IN=21 and EX=29.
- Clean auto-deconstruction previously produced only EX-01 to EX-08 and even changed identifiers to `MG-K10-SAR-III`; this is now blocked by prompt constraints and selected-stage extraction.
- Existing manual MG-K10-SAR rules had duplicate parent IN-02/IN-03 for II vs III. The III期 ruleset now contains only the III期 parent IDs.
- Report buttons without phase query previously requested `phase=full` and produced 404. Frontend and backend fallback were both fixed.
- LLM review sometimes split one parent rule into multiple rows, e.g. duplicate IN-04. Parser now merges duplicates while keeping the stricter verdict.

MG-K10-SAR III期 regression run:

- Source protocol:
  - `/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx`
- Source raw documents:
  - `/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/13. CFDI核查/自查/入排/各中心原始入排资料`
- Clean rebuild log:
  - `projects/MG-K10-SAR/rerun_logs/mgk10sar_phase3_rerun_20260621_223702.json`
- Previous project backup before clean rebuild:
  - `output/deleted_project_backups/MG-K10-SAR_20260621_223702`
- Inventory observed in clean run:
  - 7 centers;
  - 93 subject folders;
  - 491 supported source files.
- Subjects rerun:
  - `06002`, `06003`, `06004`
- Phases rerun:
  - `screening_run_in`
  - `baseline_randomization`

Review/QC outcomes after corrected rules:

- All six reviewed subject-phase reports parse to exactly 23 parent rows:
  - IN-01 to IN-07;
  - EX-01 to EX-16;
  - no missing parent IDs;
  - no duplicate parent IDs after parser merge.
- All six overall verdicts are `needs_evidence`, not plain pass.
- 06004 EOS behavior is now conservative:
  - screening phase treats screening EOS 250/μL as not final for IN-05;
  - baseline phase remains `needs_evidence` because D1/baseline EOS source is missing, rather than definitively failing solely from the screening EOS.
- 06002 baseline now remains `needs_evidence` because IN-04 baseline rTNSS/iTNSS exact component means are missing despite D1 EOS passing.

Validation completed:

- `python3 -m unittest discover -s tests`
  - 21 tests passed.
- `python3 -m compileall app tests scripts`
  - passed in earlier full check; targeted compiles after later edits passed.
- `node --check` on extracted `static/index.html` script
  - passed.
- Live API checks:
  - MG-K10-SAR protocol draft without `study_stage` returns 409 and asks for II/III selection;
  - `/api/projects/MG-K10-SAR/subjects/06004/report?phase=full` now falls back to `screening_run_in` and returns 23 rule rows.
- Browser QA via Playwright:
  - login page shows custom logo and no CMS logo;
  - help page is detailed and does not expose admin password;
  - task home shows three entry cards;
  - first-deconstruct workspace shows `本次解构期别` selector plus editable rules and feedback panes;
  - audit list shows MG-K10-SAR version/date and `解构期别: Ⅲ期`;
  - project page shows II/III study-stage selector and screening/baseline review-phase selector;
  - 06004 screening report renders with parent rows IN-01..IN-07 and EX-01..EX-16.
- Browser screenshot artifact:
  - `output/playwright/mgk10sar_06004_screening_report_20260621.png`

Remaining risk/next QC targets:

- The LLM summary for 06004 baseline still uses wording like screening EOS 250/μL being below threshold while correctly stating D1 data are missing. Keep monitoring this wording; rule-level verdict is insufficient, not definitive fail.
- Report visible labels still show raw enum text such as `needs_evidence` in the subject list; a later UI polish pass should translate these to Chinese badges consistently.
- Full bulk run beyond 06002/06003/06004 remains pending if the user wants broader center-level validation.

## 2026-06-21 Final Startup Fix and Verification

Additional issue found late in validation:

- The desktop launcher previously said the service had started, but no process was listening on `127.0.0.1:8900` after the launcher exited.
- Existing `~/Library/LaunchAgents/com.smkzw.enrollment-review.plist` repeatedly failed with `last exit code = 78`.
- Direct foreground `python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8900 --loop asyncio` worked.
- LaunchAgent execution from the user domain could not reliably access/run the app path under `Documents/康哲项目资料`; the service wrapper did not write its first diagnostic line when started only through LaunchAgent.

Startup changes:

- Added `scripts/run_enrollment_review_service.sh`
  - sets `HOME`, `PATH`, `PYTHONUNBUFFERED`;
  - writes service-start diagnostics to `output/runtime_logs/enrollment-review-uvicorn.log`;
  - starts uvicorn with `--loop asyncio`.
- Added `scripts/run_enrollment_review_terminal.command`
  - opens a visible service window;
  - tells the user to keep that window open because closing it stops the service.
- Updated both:
  - `scripts/start_enrollment_review.command`;
  - `/Users/smkzw/Desktop/启动入排审核系统.command`.
- Launcher behavior is now:
  - verify/start oMLX;
  - try LaunchAgent first;
  - if `/api/health` is still not ready after timeout, unload the failing LaunchAgent and open the visible Terminal service fallback;
  - open `http://127.0.0.1:8900`;
  - tell the user to keep the service window if one appears.

Final validation after startup fix:

- `zsh -n` passed for:
  - `scripts/run_enrollment_review_service.sh`;
  - `scripts/run_enrollment_review_terminal.command`;
  - `scripts/start_enrollment_review.command`;
  - `/Users/smkzw/Desktop/启动入排审核系统.command`.
- `plutil -lint ~/Library/LaunchAgents/com.smkzw.enrollment-review.plist`: OK.
- Running `/Users/smkzw/Desktop/启动入排审核系统.command` started service via visible service-window fallback.
- `lsof -nP -iTCP:8900 -sTCP:LISTEN` showed Python listening on port 8900.
- `GET http://127.0.0.1:8900/api/health` returned:
  - `status=ok`;
  - `omlx=true`;
  - `deepseek=true`.
- `GET http://127.0.0.1:8000/v1/models` returned content.
- `python3 -m unittest discover -s tests`: 21 tests passed.
- `python3 -m compileall app tests scripts`: passed.
- `node --check` on extracted `static/index.html` script: passed.
- Admin login endpoint works with `admin` / `20121116`.
- Authenticated MG-K10-SAR checks using `X-Enrollment-User` and `X-Enrollment-Token`:
  - `/api/projects/MG-K10-SAR/phases` returns `study_stages=["Ⅱ期","Ⅲ期"]`, `requires_study_stage_selection=true`, and two review phases;
  - `/api/projects/MG-K10-SAR` returns version `V2.1`, protocol date `2025-09-19`, study stage `Ⅲ期`;
  - `/api/projects/MG-K10-SAR/subjects/06004/report?phase=full` falls back to `screening_run_in`, verdict `needs_evidence`, and 23 `rule_results`.
- Workspace is not a Git repository, so `git status` / `git diff` are unavailable here.

Current operational note:

- The service is running from a visible Terminal service window. Do not close that service window during active use. If it is closed, double-click `/Users/smkzw/Desktop/启动入排审核系统.command` again.

## 2026-06-24 D001 Phase II Batch Test and Semantic Verdict Guard

User-confirmed scope:

- Use account `smkzw`.
- Protocol:
  - `/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx`
- Source folder:
  - `/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/全量-入组`
- All subject folders under that source root whose folder name contains `筛败` are D001 Phase II subjects.
- Attachment filenames must not be used to exclude a subject from Phase II. In particular, missing `Ⅱ期` or a stray `Ⅲ期` in an attachment filename is not a subject-level phase signal.
- Photo/image-like files, compressed archives, hidden system files, and exact duplicate files are not review source files.

Batch inclusion root cause and fix:

- The first batch logic inferred study phase from attachment filenames, causing many valid Phase II screen-failure folders to be excluded or left unreviewed.
- A second bug used `\bSA\d{5}\b`, which missed subject IDs followed by Chinese characters because the word boundary did not behave as intended in Chinese filenames.
- Added `app/batch_sources.py`:
  - discovers subject folders from folder name plus `SA\d{5}`;
  - applies a fixed project stage `Ⅱ期`;
  - filters unsupported images/archives/system files and photo-like DOCX names;
  - deduplicates by SHA-256.
- Added regression test:
  - `test_d001_screen_failed_batch_uses_project_stage_not_filename_phase_markers`;
  - confirms 22 subject folders and includes `SA07025` despite attachment phase wording.

Batch run artifacts:

- Script:
  - `scripts/d001_phase2_batch_review.py`
- Run log:
  - `projects/D001-02-II/rerun_logs/d001_phase2_screening_batch_20260624_093440.json`
- Final Markdown report:
  - `projects/D001-02-II/reports/d001_phase2_screening_full_batch_report.md`
- Final HTML report:
  - `projects/D001-02-II/reports/d001_phase2_screening_full_batch_report.html`
- Project Markdown export:
  - `projects/D001-02-II/reports/D001-02-II_screening_run_in_project_report.md`
- Processed subjects:
  - 22 folders, no batch errors.
- Final parsed overall counts after semantic guard and `pass_verify` downgrade:
  - `fail`: 4;
  - `needs_evidence`: 17;
  - `pass`: 1.

Manual IE comparison notes:

- Manual IE sheet had usable manual records for 15/22 subjects.
- Seven subjects had no manual IE record in the workbook extract:
  - `SA01025`, `SA03008`, `SA03009`, `SA03010`, `SA12008`, `SA12010`, `SA14002`.
- Manual `未判断` subjects:
  - `SA20011`, `SA20013`.
- Known mismatch/risk examples still requiring human QC:
  - `SA07020` and `SA07025`: manual EX-30 not system-hit;
  - `SA07030`: manual IN-01 due withdrawal of informed consent, but uploaded source did not contain a clear withdrawal source statement;
  - `SA16002`: manual EX-22 not system-hit.

DeepSeek/LLM semantic conflict found and fixed:

- Failure mode: for complex exclusion rules, especially lab package rule EX-20, model output sometimes wrote table verdict `❌不通过` while the reasoning later said the protocol-defined trigger was not met, such as `未触发排除标准` or `故本条通过`.
- Root cause is semantic, not just formatting:
  - model may confuse local abnormality/reference-range deviation with protocol exclusion trigger;
  - model may write an early mistaken comparison and then self-correct later in the same reasoning sentence;
  - parser previously trusted the verdict cell too strongly.
- Prompt-level fix in `app/pipeline/reviewer.py`:
  - added a判定闭环 rule;
  - every rule must first complete semantic trigger judgment;
  - EX rows can be `❌不通过` only when the reasoning explicitly states `触发判断：已触发` or equivalent trigger facts with subitem/value/unit/threshold;
  - complex lab/package clauses must compare actual value versus protocol threshold, not just abnormal/NCS/CS wording.
- Additional semantic fixes after user QC:
  - lab analytes must match exactly; `GGT` cannot substitute for `ALT` / `AST` / `总胆红素` in EX-20g;
  - evidence topic must match the rule topic; urine glucose or occult blood cannot prove EX-07 active infection / acute disease;
  - protocol AND conditions must remain AND. EX-20h requires other laboratory abnormality + clinical significance + investigator assessment that participation may pose unacceptable risk; missing any component is not a direct exclusion trigger.
- Parser-level guard:
  - detects positive trigger, negative trigger, and investigator semantics;
  - uses the last valid semantic judgment in the reasoning so later `重新确认/故本条通过` can override an earlier mistaken草判;
  - downgrades analyte substitution, topic mismatch, incomplete AND logic, and possibility-only wording to `investigator` instead of hard fail.
- Key D001 checks after fix:
  - `SA16005` EX-20 changed from spurious fail to pass, subject overall `needs_evidence`;
  - `SA18011` EX-20 pass, subject overall `needs_evidence`;
  - `SA07007` EX-20 changed to investigator, but subject remains fail due EX-09;
  - `SA01025` EX-20 changed away from hard fail because `GGT` does not trigger EX-20g; if clinically concerning it belongs under other-lab/investigator assessment;
  - `SA03009` EX-07 and EX-20 changed away from hard fail because urine glucose/occult blood do not prove infection and EX-20h all-of components were incomplete;
  - `SA16002` is overall `pass` with IN-03 retained only as `溯源提醒`.

Pass-verify output wording:

- User clarified that internal prompt-strength wording must not appear in UI or reports.
- The system now writes `溯源提醒`, not the internal strength wording.
- If `pass_verify` is the only non-plain-pass rule result, the overall verdict is `pass`.

HTML report cleanup:

- User rejected log/instructional phrases such as `按要求排除`.
- Final HTML no longer displays:
  - source directory;
  - batch id;
  - upload/exclusion counts;
  - folder inclusion rules;
  - `系统一致性校正` or similar parser-log wording.
- These operational details remain in run JSON/Markdown/context, not in the clinical-facing HTML.
- Mobile visual QC found the summary table was too cramped; tables now render inside `.table-wrap` scroll containers on narrow screens.

Validation completed:

- `python3 -m py_compile app/pipeline/reviewer.py scripts/d001_phase2_batch_review.py app/batch_sources.py`
  - passed.
- `python3 -m unittest discover -s tests`
  - 44 tests passed, 1 skipped.
- HTML forbidden-term scan for:
  - `按要求`, `按用户`, `排除上传`, `剔除`, `源目录`, `批次`, `上传N`, `日志`, `log`, `用户确认`, `纳入规则已`, `未上传审核`, `文件夹名包含`, `系统一致性校正`
  - returned no matches in final HTML.
- Browser QC via Playwright:
  - mobile 390px: `scrollWidth=390`, `.table-wrap` count 23;
  - desktop 1440px: `scrollWidth=1440`, `.table-wrap` count 23.
- Screenshot artifacts:
  - `output/playwright/d001_phase2_report_mobile_clean_html_v2.png`
  - `output/playwright/d001_phase2_report_desktop_clean_html_v2.png`

Follow-up UI/verdict validation after user QC:

- User clarified:
  - `通过（需验证）` should be treated as `pass` when it is the only non-plain-pass rule result;
  - user-facing text should say `溯源提醒`;
  - maximized windows should use the available page width rather than leaving a large blank right area.
- Implemented:
  - `static/index.html` removes the global `1680px` page cap for `#app` and `.header-inner`;
  - D001 batch HTML report removes the `1440px` main cap;
  - `app/pipeline/reviewer.py`, `app/markdown_export.py`, `app/models.py`, and `static/index.html` align `pass_verify` wording and final verdict behavior;
  - D001 generated reports and subject `info.json` were refreshed from existing raw review outputs, without rerunning OCR/LLM.
- API validation after restart:
  - `/api/health` returned `{"status":"ok","omlx":true,"deepseek":true}`;
  - D001 subject list returned 22 subjects: `4 fail`, `17 needs_evidence`, `1 pass`;
  - `SA16002` report returned overall `pass`, with only `IN-03 pass_verify`.
- Browser visual QC at 2048px width:
  - project page `#app` width `2048`, right gap `0`, subject table width `1984`;
  - SA16002 page `#app` width `2048`, right gap `0`, verdict card shows `可入组`, callout title `溯源提醒`;
  - generated D001 HTML report `main` width `2048`, right gap `0`.
- New screenshot artifacts:
  - `output/playwright/d001-project-wide-2048-fullwidth-v4.png`
  - `output/playwright/sa16002-report-pass-traceability-v4.png`
  - `output/playwright/d001-batch-html-wide-2048-fullwidth-v4.png`
- Final verification:
  - `python3 -m unittest discover -s tests` passed: 54 tests, 1 skipped;
  - `python3 -m compileall app scripts tests` passed;
  - `node --check /tmp/static_index_inline_final.js` passed.

OCR concurrency note:

- User later requested OCR concurrency be adjusted to at most 8.
- Implemented default `OCR_MAX_CONCURRENT=8` in `app/config.py` and explicit `OCR_MAX_CONCURRENT=8` in project `.env`.
- `app/router/pipeline.py` now calls `ocr_documents_parallel()` for the OCR stage instead of processing files one by one.
- `app/pipeline/ocr.py` now uses one shared VLM semaphore across concurrent files so the cap means at most 8 VLM OCR calls total, not 8 per file.
- Added regression coverage showing 9 one-page image files reach exactly 8 concurrent patched VLM calls under the default OCR path.
- Caveat: an already-running uvicorn process keeps its imported config/code. The active D001 batch that started before this change still uses the old service process until the service is restarted.

2026-06-24 continuation - D001 remaining-subject batch gate:

- User clarified that after system fixes, every remaining subject folder under `/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/全量-入组` should be audited; the statement that remaining subjects were manually judged eligible is comparison-only and must not be included in DeepSeek prompts.
- Root cause of missed subjects:
  - `scripts/d001_phase2_batch_review.py` hard-coded discovery to folder names containing `筛败`, so only the 22 already reviewed screen-failed subjects entered the batch.
  - The source tree contains 143 unique `SAxxxxx` subject IDs; 22 already existed in `projects/D001-02-II/subjects`, leaving 121 remaining IDs for this continuation run.
  - A naive all-folder `rglob` sees 187 candidate directories because nested photo folders and duplicate transfer folders repeat the same SA ID.
- System-level fix implemented:
  - `app/batch_sources.discover_subject_folders(..., folder_keyword=None)` now supports all-folder discovery.
  - Subject discovery skips photo-like candidate directories, collapses nested directories under the same subject root, and keeps multiple non-nested roots for one subject as `BatchSubjectFolder.folders`.
  - `collect_review_files_from_folders()` merges those roots into one upload package and deduplicates by SHA-256 while still skipping photos/images, archives, hidden/system files, unsupported files, and duplicates.
  - D001 batch script gained `--all-folders`, `--only-new`, and `--limit`; run logs explicitly state `manual_ie_usage = 人工IE仅用于审核后对照，不进入DeepSeek提示词。`
  - Batch report parsing now prefers corrected `review_report.md` over raw LLM output, matching the API report endpoint.
  - Manual IE comparison now treats `IE=是` as an explicit pass baseline: if the system still reports fail/needs-evidence/investigator items, the report says `存在差异：人工通过但系统仍有关注条目` instead of `人工未填具体条目`.
- Verification so far:
  - Added and passed target tests in `tests/test_phase_workflow.py` for all-folder subject discovery/merge and D001 batch report parsing/manual-pass comparison.
  - Real source discovery check: `discovered 143`, `existing 22`, `new 121`, `multi_roots 4`.
  - `python3 -m compileall app/batch_sources.py scripts/d001_phase2_batch_review.py app/markdown_export.py tests/test_phase_workflow.py` passed.
  - `python3 -m unittest tests.test_phase_workflow.SubjectUploadTests` passed.

2026-06-24 D001 remaining-subject pilot QC:

- Ran a 3-subject pilot with `python3 scripts/d001_phase2_batch_review.py --all-folders --only-new --limit 3 --username smkzw --password ''`.
- Pilot subjects: `SA01001`, `SA01002`, `SA01003`; all completed without batch errors.
- Run log: `projects/D001-02-II/rerun_logs/d001_phase2_screening_batch_20260624_122506.json`.
- Pilot observations:
  - The revised all-folder discovery/upload path worked end to end.
  - HTML report forbidden-term scan found none of `按要求`, `排除上传`, `文件夹名包含`, `系统一致性`, `低强度`, `log`, `日志`, `用户确认`, `人工判定满足`.
  - Manual IE comparison correctly reports `存在差异：人工通过但系统仍有关注条目` for manually eligible pilot subjects with system investigator items.
  - EX-20h pilot reasoning preserved all-of logic: urine/protein/lipid abnormalities were not direct exclusions unless laboratory abnormality + clinical significance + investigator unacceptable-risk assessment were all supported.
- New system-level issue found and fixed:
  - EX-11 reasoning could borrow EX-20h/EX-21 language and say `不可接受风险` instead of the EX-11-specific second component `研究者明确判断不具备临床研究条件`.
  - Added parser tests:
    - `test_review_parser_uses_ex11_specific_researcher_component_not_generic_risk`;
    - `test_review_parser_downgrades_ex11_fail_when_only_generic_unacceptable_risk_is_stated`.
  - `app/pipeline/reviewer.py` now has EX-11-specific component detection and wording normalization; generic `不可接受风险` no longer counts as EX-11 definitive fail.
  - Existing SA01003 EX-11 report now reparses as: `研究者尚未明确评估这些情况是否导致受试者不具备临床研究条件...当前依据未完整证明该研究者判断。`
- Verification after EX-11 fix:
  - `python3 -m unittest discover -s tests` passed: 70 tests, 1 skipped.
  - `python3 -m compileall app scripts tests` passed.
- User added a post-batch experiment requirement:
  - After the 121 remaining-subject batch finishes, select several successful/pass subjects and several screen-failed/fail subjects.
  - Run a separate JSON schema output experiment using the same evidence packages, compare against the current Markdown-table-plus-parser route.
  - Compare practical advantages: parsing stability, missing-rule rate, all-of/compound-condition consistency, report readability/generation cost, speed, and failure modes.
  - Do not switch the main route during the active batch; only adopt JSON schema output if the controlled experiment shows clear advantage.
- User clarified another reminder-class requirement during the batch:
  - `基线期评估待后续阶段复核` and similar future baseline/D1/randomization gaps should be a reminder at the same strength as traceability reminders, but must not be mixed with `溯源提醒`.
  - Implemented as the same internal `pass_verify` verdict for compatibility, with reasoning-based labels:
    - `通过（溯源提醒）` for historical/provenance gaps;
    - `通过（后续阶段复核）` for baseline/D1/randomization components not yet reached in screening review.
  - API report rows now include `verification_type` (`source_traceability`, `future_phase`, `other`).
  - Frontend individual reports render separate callouts: `溯源提醒` and `后续阶段复核提醒`.
  - Project/center Markdown summary counts these two reminder types separately; subject-level rule tables use separate labels.
  - D001 batch report now has a separate `提醒条目` column and subject-level reminder table, distinct from `系统关注条目`.
  - Added tests:
    - `test_review_parser_separates_future_phase_verify_from_traceability_verify`;
    - updated `test_screening_phase_adjustment_does_not_downgrade_future_baseline_gap`;
    - `test_markdown_export_treats_pass_verify_as_traceability_note`.
  - Targeted reminder tests passed.

2026-06-24 continuation - subject-list filters and split pending verdicts:

- User requested the old overall `待补证` bucket be split:
  - `insufficient`: evidence/source material is missing and extra documents are needed (`证据不足`);
  - `investigator`: available data exist but need investigator or medical-monitor judgment (`需研究者判定`);
  - legacy `needs_evidence` is retained only for old persisted reports and shown as `需处理`, not as the new canonical label.
- Backend verdict changes:
  - `app/pipeline/reviewer.py` system prompt now asks DeepSeek for `pass / fail / insufficient / investigator`.
  - Overall priority is `fail > insufficient > investigator > pass`.
  - `pass_verify` does not downgrade the overall verdict.
  - Legacy raw outputs containing `needs_evidence` or Chinese `待补证` are reparsed into `insufficient` or `investigator` when rule-level semantics make that clear.
  - Legacy summaries saying `补充资料或研究者判断` are rebuilt so missing-source cases and investigator-judgment cases are not mixed.
- Export/UI changes:
  - `app/models.py` and `app/markdown_export.py` now expose separate labels/counts for `证据不足` and `需研究者判定`.
  - `static/index.html` renders separate badges and separate report callouts for missing evidence vs investigator judgment.
  - Existing old report data still appears as `⚠️ 需处理` until the running batch finishes and the backend is restarted/backfilled.
- Subject table UX changes:
  - Removed standalone `按中心筛选`.
  - Added per-column filters and sortable headers for: subject ID, center, uploader/creator, ICF date, status, and review conclusion.
  - Center is compacted as code on the first line and hospital name as smaller grey text.
  - File count column remains removed.
  - Checkbox handlers no longer re-render the whole project page, fixing the bug where clicking a subject checkbox jumped back to the top.
  - Clear filter / clear selection update the visible DOM state without replacing the whole page.
- Visual/manual browser QC:
  - In Edge at `127.0.0.1:8900/#/project/D001-02-II`, per-column filter inputs and sort buttons are visible.
  - Filtering `筛ID = SA01009` reduced the table to exactly one visible subject and showed `当前显示 1 名`.
  - Clearing filters restored `当前显示 53 名`.
  - Sorting `受试者ID` changed the header icon to `▲` and then `▼`; descending order moved `SA20013` to the first row.
  - Clicking a subject checkbox and clearing filters did not jump to the top; viewport stayed on the subject-table area.
  - The table fits the current maximized window width without requiring horizontal scrolling to see the operation column.
- Automated verification:
  - `python3 -m unittest tests.test_phase_workflow` passed: 75 tests, 1 skipped.
  - `python3 -m compileall app tests scripts` passed.
  - Extracted inline JS from `static/index.html` and ran `node --check /tmp/enrollment_index_check.js`; passed.
- Backfill preparation:
  - Added `app/report_backfill.py` and `scripts/backfill_review_reports.py`.
  - Purpose: after the active batch finishes, reparse persisted `review_report.md`/`review_raw.md`, rewrite normalized `review_report.md`, and update each subject `info.json` `overall_verdict` so the subject list no longer shows legacy `needs_evidence`/`需处理`.
  - Added regression test `test_backfill_reports_rewrites_legacy_needs_evidence_to_specific_verdict`; it first failed on missing module, then passed after implementation.
  - `python3 scripts/backfill_review_reports.py --project D001-02-II --phase screening_run_in --dry-run --output /tmp/d001_backfill_dry_run.json` succeeded without writing project files.
  - After adding the backfill utility, `python3 -m unittest tests.test_phase_workflow` passed: 76 tests, 1 skipped; `python3 -m compileall app tests scripts` passed.
- Active batch caveat:
  - D001 remaining-subject batch is still running in exec session `21757`.
  - Do not restart the service while that batch runs; backend verdict splitting will apply to new requests after restart.
  - After the batch completes, restart the enrollment-review service and run a legacy-report backfill/reparse so old `needs_evidence` reports are split into `insufficient` or `investigator` where possible.

2026-06-24 continuation - OCR concurrency raised to 8 and D001 resume handling:

- User asked to raise OCR concurrency from the observed two-way behavior to at most eight-way.
- Root cause:
  - `app/config.py` defaulted `OCR_MAX_CONCURRENT` to `2`.
  - `/api/.../process` and `/run-ocr` were still iterating documents sequentially.
  - `ocr_documents_parallel()` had a per-document semaphore model that did not provide one shared global cap across files.
- Implemented:
  - `OCR_MAX_CONCURRENT` default changed to `8`; `.env` also explicitly sets `OCR_MAX_CONCURRENT=8`.
  - `app/pipeline/ocr.py` now accepts a shared VLM semaphore and `ocr_documents_parallel()` uses one shared `asyncio.Semaphore(OCR_MAX_CONCURRENT)` across all files/pages, so total VLM OCR calls are capped at eight.
  - `app/router/pipeline.py` now uses `ocr_documents_parallel()` for both direct OCR and SSE process OCR, and emits `OCR并发处理中: ...最多8路VLM调用...`.
  - Added regression test `test_default_parallel_ocr_allows_up_to_eight_concurrent_vlm_calls`; full `tests.test_phase_workflow` passed after change.
- Running-batch correction:
  - Existing D001 batch session `21757` was using old imported code. It was stopped at SA07009 after confirming a safe resume path was needed.
  - Added `--only-unreviewed` to `scripts/d001_phase2_batch_review.py`; it skips only subjects with `status=reviewed`, non-empty `overall_verdict`, and an existing phase/legacy `review_report.md`. Subjects left as `processing`, `pending`, or missing report remain eligible and are recreated by default.
  - `--only-new` was not enough because it only checks whether a subject directory exists and would skip interrupted half-products such as SA07009.
- Service-start pitfall:
  - LaunchAgent restart failed with `EX_CONFIG` and detached/nohup/disown processes were cleaned up by the execution environment after health checks.
  - Stable workaround for this run: keep uvicorn in an explicit long-running exec session (`18548`, server PID `50936`) while D001 batch continues in session `19959`.
  - Failed LaunchAgent was booted out to stop spawn interference; durable desktop-start cleanup remains a later maintenance item.
- Runtime verification:
  - New D001 resumed run log: `projects/D001-02-II/rerun_logs/d001_phase2_screening_batch_20260624_144818.json`.
  - SA07009 event log confirms: `OCR并发处理中: 7个文件，最多8路VLM调用...`.
  - SA07009 completed under new service with `overall_verdict=investigator`, confirming the split pending-verdict path is active.
  - Resume command: `python3 scripts/d001_phase2_batch_review.py --all-folders --only-unreviewed`.

2026-06-24 continuation - overlapping OCR and LLM across subjects:

- User correctly pointed out that batch mode was still `A受试者 OCR -> A受试者 LLM -> B受试者 OCR`, leaving OCR idle while DeepSeek reviewed A.
- System-level fix:
  - `app/pipeline/ocr.py` now has `global_vlm_semaphore()` with one event-loop-local shared semaphore for all OCR VLM calls in the server process.
  - This prevents subject-level concurrency from multiplying the OCR cap. Without this, two simultaneous subject requests could each create an 8-way semaphore and effectively hit oMLX with up to 16 VLM OCR calls.
  - `ocr_document()`, `ocr_documents_parallel()`, and `ocr_pages_batch()` all use the global semaphore unless an explicit test semaphore is injected.
- Batch-script fix:
  - `scripts/d001_phase2_batch_review.py` now supports `--subject-workers N`.
  - Default remains `1` for conservative behavior.
  - For D001 continuation we switched to `--subject-workers 2`, so one subject can be in DeepSeek review while the next subject is already uploading/OCRing/bundling.
  - Each worker uses its own authenticated HTTP session; progress is written to the run log after each completed subject.
- Verification:
  - Added `test_parallel_ocr_uses_one_global_limit_across_batches`, covering two concurrent OCR batches and asserting total concurrent VLM calls still peak at `8`, not `16`.
  - `python3 -m unittest tests.test_phase_workflow` passed: 78 tests, 1 skipped.
  - `python3 -m compileall app tests scripts` passed.
  - Current concurrent D001 run log: `projects/D001-02-II/rerun_logs/d001_phase2_screening_batch_20260624_153846.json`.
  - It records `subject_workers=2`; SA10002 has `OCR并发处理中: 8个文件，最多8路VLM调用...`.
- Operational decision:
  - Do not jump directly to 4+ subject workers until observed stable over multiple centers, because DeepSeek review, oMLX OCR, upload, and evidence-bundle generation can all compete for local CPU/memory and remote API rate limits.
  - Current recommendation: use `--subject-workers 2` for large batches; consider `3` only after confirming no oMLX timeouts, DeepSeek rate limits, or memory growth.

2026-06-24 checkpoint - D001 batch intentionally stopped before full completion:

- User asked to checkpoint and not finish the entire remaining batch.
- Actions taken:
  - Let the active in-hand subjects complete where practical:
    - `SA10003` completed with `investigator`;
    - `SA10005` completed with `investigator`;
    - `SA11003` completed with `investigator` while the thread pool was being stopped;
    - `SA11004` had generated a report but was interrupted before `info.json` final save, so it was manually reconciled to `status=reviewed`, `overall_verdict=pass`;
    - `SA11005` had no report and was reset to `status=pending`, empty `overall_verdict`.
  - Stopped the concurrent batch process `scripts/d001_phase2_batch_review.py --all-folders --only-unreviewed --subject-workers 2`.
  - Left no `processing` subjects in `projects/D001-02-II/subjects`.
- Current D001 source/project counts:
  - Source-discovered II期 subjects: `143`.
  - Completed reviewed subjects by `completed_project_subject_ids()`: `96`.
  - Remaining unreviewed subjects: `47`.
  - Remaining starts with: `SA11005`, `SA12001`, `SA12002`, `SA12003`, `SA12007`, `SA12009`, `SA13002`, `SA13003`, `SA14001`, `SA14003`, `SA16001`, `SA16004`, `SA17001`, ...
- Current run logs:
  - Serial resumed run: `projects/D001-02-II/rerun_logs/d001_phase2_screening_batch_20260624_144818.json`, logged 25, errors 0.
  - 2-worker overlap run: `projects/D001-02-II/rerun_logs/d001_phase2_screening_batch_20260624_153846.json`, logged 4, errors 0.
- Important caveat:
  - The project still contains older pre-split `needs_evidence` reports from the earlier batch. Before final reporting/QC, run the backfill/reparse utility to split legacy `needs_evidence` into `insufficient`/`investigator` where the saved report supports it.
  - Suggested later resume command if needed: `python3 scripts/d001_phase2_batch_review.py --all-folders --only-unreviewed --subject-workers 2`.

2026-06-24 checkpoint next step - JSON schema route experiment:

- User previously asked to test a JSON schema output route on a few successful and screen-failed subjects, and only adopt it if it clearly improves the current technical route.
- Implemented a non-production experiment script:
  - `scripts/experiment_json_schema_review.py`
  - It does not modify project reports or the production review flow.
  - It reads existing D001 criteria and evidence bundles, asks DeepSeek for strict JSON, writes raw and parsed JSON under the project reports folder, and compares against current Markdown reports.
- Representative samples:
  - `SA11004`: current `pass`.
  - `SA09002`: current `fail`.
  - `SA07009`: current `investigator`.
  - `SA10002`: current `insufficient`.
- Output folder:
  - `projects/D001-02-II/reports/json_schema_experiment_20260624_155126/`
  - Key files: `summary.md`, `summary.json`, `assessment.md`, plus per-subject raw/parsed JSON.
- Surface metrics looked good:
  - All 4 JSON responses parsed successfully.
  - Each covered 36/36 expected rules.
  - No missing rule IDs or invalid verdict enums.
  - Overall verdict matched the existing route for all 4 samples.
- Critical item-level finding:
  - Overall agreement hid safety downgrades.
  - `assessment.md` found item-level differences:
    - `SA07009`: 6 rule differences, 6 potential downgrades. JSON kept overall `investigator` only because EX-20 remained investigator, while EX-11/EX-21/EX-30 were downgraded to pass.
    - `SA09002`: 9 rule differences, 6 potential downgrades, including missing/weakening several safety-relevant interpretations.
    - `SA10002`: 1 minor difference.
    - `SA11004`: 0 differences.
- Decision:
  - Do not replace the production Markdown-table route with prompt-only JSON schema output yet.
  - JSON is promising as a structured sidecar/validator because parsing and rule coverage are strong.
  - Before adopting it, add item-level downgrade detection and missing-reminder detection; otherwise it can make the same overall decision while silently weakening specific clinical review points.

2026-06-24 startup issue - desktop launcher appeared stuck at "入排审核服务未运行，正在启动...":

- User observed `/Users/smkzw/Desktop/启动入排审核系统.command` hanging after `oMLX 已就绪。入排审核服务未运行，正在启动...`.
- Root-cause evidence:
  - `http://127.0.0.1:8900/api/health` returned `{"status":"ok","omlx":true,"deepseek":true}` during investigation, so oMLX and the FastAPI app were not fundamentally broken.
  - `lsof -nP -iTCP:8900 -sTCP:LISTEN` showed Python/uvicorn listening on `127.0.0.1:8900`.
  - `launchctl print gui/$(id -u)/com.smkzw.enrollment-review` returned "Could not find service", so the LaunchAgent was not registered even though the plist existed.
  - This matches the earlier LaunchAgent pitfall where restart failed with `EX_CONFIG`; the visible Terminal service fallback can run the app while the original launcher window still looks uninformative.
- System-level fixes:
  - Updated `scripts/start_enrollment_review.command` and recopied it to `/Users/smkzw/Desktop/启动入排审核系统.command`.
  - Added bounded `curl` health checks (`--connect-timeout 2 --max-time 4`) so a half-responsive endpoint cannot freeze the launcher.
  - Added `output/runtime_logs/enrollment-review-launch.log` for LaunchAgent bootstrap/kickstart diagnostics instead of suppressing every `launchctl` error.
  - Made the LaunchAgent plist mode conventional (`chmod 644`) after writing.
  - Changed startup flow so the visible service window is the primary cold-start path. The unreliable LaunchAgent path is no longer the first user-facing startup route; it remains only as a fallback diagnostic route if the service window cannot respond.
  - Added progress dots during waits so the terminal does not appear dead.
  - Changed `scripts/run_enrollment_review_service.sh` log heading from `LaunchAgent service start` to `enrollment review service start` because the service may now be started from a visible Terminal window.
- Verification:
  - `zsh -n scripts/start_enrollment_review.command` passed.
  - Desktop launcher and repository launcher are byte-identical after sync (`cmp` exit `0`).
  - `curl -fsS --connect-timeout 2 --max-time 4 http://127.0.0.1:8900/api/health` returned healthy.
  - Running `/bin/zsh /Users/smkzw/Desktop/启动入排审核系统.command` completed with:
    - `oMLX 已就绪。`
    - When already running: `入排审核服务已运行。`
    - After cold stop: `入排审核服务未运行，正在打开服务窗口...` then `入排审核服务已在服务窗口中启动。请保留该窗口。`
    - `正在打开浏览器...`
    - `完成。若出现单独的服务窗口，请保留该窗口以维持服务运行。`
  - Cold-start health after final change: Python/uvicorn listening on `127.0.0.1:8900`, and `/api/health` returned `{"status":"ok","omlx":true,"deepseek":true}`.

2026-06-25 third-party system review response:

- Source reviewed:
  - `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/SYSTEM_REVIEW_REPORT.md` was read in full and treated as a review report, not as binding instructions.
- Findings accepted as real and fixed systemically:
  - Path traversal risk in project/subject identifiers and upload filenames.
    - Added centralized storage ID validation in `app/shared.py`.
    - Applied validation in project/subject paths, subject creation, protocol upload, and subject material upload.
    - Rejected path separators, `..`, empty names, unsupported subject-upload extensions, and unsupported protocol-upload extensions.
  - OCR hallucination/repetition risk entering evidence bundles.
    - Added OCR quality detection in `app/pipeline/ocr.py` for dominant repeated lines, repeated segments, and very long page outputs.
    - New OCR cache pages now carry explicit OCR quality warnings and deduplicated/truncated content before entering review evidence.
    - Old OCR cache artifacts are not silently rewritten; affected subjects need OCR reset/rerun or a separate cache-cleaning pass.
  - ICF date extraction selected non-source discussion material and another subject's date.
    - Made `app/subject_dates.py` category-aware.
    - Prefer `screening_record`; exclude communication/discussion/enrollment-eligibility files from date extraction.
    - Reject candidate dates if nearby text references a different subject number.
  - Evidence bundle source filenames always showing `.pdf`.
    - `app/pipeline/bundler.py` now preserves the real extension from `file_categories.json`.
  - Subject/file mismatch not surfaced.
    - Evidence bundles now warn when OCR text contains a different `SAxxxxx` than the subject folder.
  - Concurrent duplicate processing for the same subject.
    - Added `app/processing_locks.py`.
    - OCR/review/process endpoints now reject duplicate in-process subject workflows with HTTP 409 and reset cleanly on errors.
  - Admin token/password weakness.
    - Admin password can now be overridden by environment variable while preserving the required fallback `20121116`.
    - Admin session token is now random, in-memory, TTL-bound, and different on each login.
    - New normal-user passwords are stored with PBKDF2-SHA256; legacy hashes still verify for compatibility.
  - Missing audit trail.
    - Added `app/audit.py`.
    - Project, subject, upload, reset, OCR, review, and process operations now write audit events.
    - Audit events are written both to the project ledger and to a system ledger at `projects/_system/audit_ledger.jsonl`, so delete events remain after project deletion.
  - Project statistics were too coarse.
    - Project list stats now separate `pass`, `pass_verify`, `fail`, `insufficient`, `investigator`, `pending`, `error`, and `pending_total`.
  - Frontend route race risk.
    - `static/index.html` route rendering is serialized so rapid hash changes do not interleave async renders.
  - Draft protocol workflow loss.
    - Saving a protocol draft now attempts workflow extraction from uploaded DOC/DOCX when workflow JSON is otherwise empty.
  - `.txt` ownership/upload regression surfaced during tests.
    - Subject uploads now allow `.txt`, and OCR pipeline supports text-file extraction into cache.
- Findings judged valid but not fully adopted in this pass:
  - Large `reviewer.py` decomposition is real architecture debt, but immediate broad splitting is higher risk than value while D001 semantic guards are still being tuned. Keep as a future phased refactor with tests around parser/prompt/rule guards.
  - Swagger docs hiding was not changed. This app remains a local clinical-review tool where API docs help debugging; add an environment-gated production mode before any network deployment.
  - `.env` encryption/keychain storage was not implemented. `.env` remains local and gitignored; keychain or encrypted settings should be a separate credential-hardening task.
  - Full cancellation of in-flight OCR/VLM calls was not completed. Review streaming now detects client disconnect and cancels the review task, but individual OCR page calls are still best-effort once submitted.
- Extra cleanup/verification:
  - Checked for the reported path-traversal artifact `etc/passwd`; no such repo path exists after the fix.
  - Restarted the running service through the visible service-window path after discovering `nohup` startup from the Codex shell could exit immediately. Keep the service Terminal window open.
- Regression tests added:
  - Storage ID path traversal rejection.
  - Upload filename traversal/extension rejection.
  - ICF extraction ignoring discussion files and other-subject IDs.
  - OCR hallucination deduplication.
  - Evidence-bundle real source extension and subject-mismatch warning.
  - Duplicate subject workflow lock.
  - Project stats split for `insufficient`/`investigator`.
  - System audit survives project deletion.
- Verification passed:
  - `python3 -m unittest tests.test_phase_workflow` -> 86 tests OK, 1 skipped.
  - `python3 -m compileall app tests scripts` -> OK.
  - Extracted scripts from `static/index.html` and ran `node --check` -> OK.
  - Restarted service and verified `/api/health` -> `{"status":"ok","omlx":true,"deepseek":true}`.
  - API smoke:
    - Admin login works and consecutive admin tokens differ.
    - Creating subject `../../../etc/passwd` returns HTTP 400.
    - `/api/projects` returns split stats including `insufficient`, `investigator`, and `pending_total`.
- Remaining limitation:
  - Browser visual screenshot QC was attempted earlier but the automated screenshot captured the macOS lock screen rather than the page. Do not treat visual QC as passed for this report-response turn; only API, parser, unit, compile, and JS syntax checks passed.

2026-06-25 login button no-response fix:

- User-facing symptom:
  - On the login card, clicking `登录` appeared to do nothing.
  - Live Edge state showed `127.0.0.1:8900/#/task`, header already displayed an authenticated user, but the main content was still the login form.
- Root cause:
  - Backend auth was healthy; `/api/auth/login` returned a valid token for `smkzw`.
  - `submitLogin()` persisted auth and called `navigate('#/task')`.
  - When the browser was already on `#/task`, assigning the same hash did not fire `hashchange`, so `route()` never rerendered the main content.
  - This created a split state: header read the new localStorage auth session, while the body stayed on the old login DOM.
- Fix:
  - In `static/index.html`, after successful login and no first-help redirect, force `await route()` when the current hash is already `#/task`; otherwise keep normal `navigate('#/task')`.
  - Scope intentionally kept narrow; backend auth and route serialization were left unchanged.
- Verification:
  - Reproduced before the fix with Python Playwright: after clicking login, `localStorage.enrollmentReviewUser = smkzw`, `location.hash = #/task`, but task home text was absent and login card remained.
  - `node --check` on the extracted frontend script passed.
  - `/api/health` returned `{"status":"ok","omlx":true,"deepseek":true}` and direct `/api/auth/login` returned a valid `smkzw` token.
  - Re-ran the same Playwright path after the fix: task home text appeared, login card disappeared, hash remained `#/task`, and user was `smkzw`.
  - Refreshed the real Edge tab, clicked login, and confirmed the visible UI entered the task home as `smkzw`.

2026-06-25 staged review anchors, phase-level subject list, OCR polarity review, and conmed-denial guard:

- User-facing triggers:
  - MG-K10 SAR subject list only showed one final conclusion; screening and baseline/randomization review results required using the top phase dropdown and then entering the subject report, which was not intuitive.
  - Parent and child rules such as `EX-06` / `EX-06f` had the same visual hierarchy in the report table.
  - SAR time-window rules such as `EX-06f` and `EX-12` depend on "随机前/基线前" anchors; without a baseline/randomization date, the model could over-infer from screening dates or report dates.
  - OCR polarity error risk was observed in source text like "否认3个月内有大量饮酒" being read as "确认3个月内有大量饮酒".
  - Missing standalone concomitant-medication records were being over-treated as evidence insufficiency even when the medical record explicitly denied relevant prohibited medication/treatment categories in the required protocol time windows.
- Root causes:
  - `SubjectInfo` only stored one `overall_verdict`; phase reports existed under `llm/<phase_id>/review_report.md`, but `list_subjects` did not expose phase-level summaries.
  - Review anchoring only included screening/ICF/first-dose/birth dates. There was no phase-specific baseline/randomization anchor, and reviewer/bundler prompts still used legacy wording that encouraged the LLM to "identify key dates" broadly.
  - Native PDF text extraction skipped VLM when enough text existed, so high-risk polarity pages had no image cross-check.
  - Parser guards covered several AND/OR and lab-substitution failure modes, but did not yet handle the specific "missing conmed table + explicit source denial" false-insufficient pattern.
- System-level fixes:
  - Added `SubjectInfo.phase_anchor_dates` and PATCH support for `phase_anchor_dates`.
  - `subject_anchor_dates(subject_path, review_phase)` now exposes `review_phase_anchor_date` for the selected phase.
  - OCR/review/process endpoints pass the selected phase into anchor-date construction and evidence bundling.
  - Subject list API now returns `phase_reviews` for each configured non-full review phase, parsed from corrected `review_report.md` before raw LLM output.
  - Report API now returns rule hierarchy metadata: `parent_rule_id`, `is_child_rule`, `is_parent_rule`, and `hierarchy_level`.
  - Reviewer prompt now states:
    - baseline/randomization anchors must be explicit;
    - if no baseline/randomization anchor is provided or found, random-before/baseline-before/first-dose-before time-window components should become evidence-insufficient or investigator-judgment items rather than inferred passes;
    - explicit source-record denial of relevant prohibited medications/treatments and time windows is valid negative evidence; missing a separate conmed log alone should not create evidence insufficiency, though it can remain a `溯源提醒`.
  - Evidence bundle anchor table no longer says "待LLM从证据识别"; it now says missing structured values may only be verified from explicit source text and must not be substituted with report/print/upload dates.
  - OCR now flags high-risk native text pages for VLM polarity review when they contain combinations such as `否认/确认/有/无/阴性/阳性/未使用/已使用` plus clinical trigger terms or protocol time windows.
  - OCR cache for such pages stores both native text and image-OCR review text with an explicit quality warning.
  - Parser now downgrades the specific false-insufficient pattern to `pass_verify` when a missing conmed log is the only gap and the reasoning itself contains explicit time-window denials for relevant prohibited medication/treatment categories.
  - Frontend subject list now renders one column per review phase with direct report/review buttons; baseline/randomization-like phases show an inline date input for the anchor date.
  - Row operation buttons no longer duplicate generic "execute/review report" actions that ignore phase context.
  - Report table visually distinguishes parent rows and child rows; child rows are indented with a connector marker.
  - Subject-list phase/filter columns were made responsive; checkbox clicks stop propagation and no longer jump the page to the top.
- Verification:
  - Focused tests added and passed for:
    - saving phase anchor dates and using them in `subject_anchor_dates`;
    - subject-list phase review summaries;
    - report API parent/child hierarchy metadata;
    - high-risk OCR polarity text detection;
    - baseline prompt behavior with and without a phase anchor;
    - conmed-denial false-insufficient parser guard.
  - `python3 -m unittest tests.test_phase_workflow` -> 103 tests OK, 1 skipped.
  - `python3 -m compileall app tests scripts` -> OK.
  - Extracted frontend script from `static/index.html` and ran `node --check` -> OK.
  - Temporary uvicorn service on `127.0.0.1:8900` returned `/api/health` healthy.
  - Playwright visual/QC:
    - `#/project/D001-02-II` at 1920 px showed direct screening and baseline/randomization phase columns.
    - `document.documentElement.scrollWidth` and `window.innerWidth` were both `1920`; table right edge stayed inside the viewport.
    - Baseline/randomization phase date inputs were present.
    - Checkbox click test kept `window.scrollY` at `650` before and after click.
    - Temporary hierarchy report rendered one `rule-parent-row` and one `rule-child-row`, with child row shown as `↳EX-06f`.
- Pitfalls:
  - Starting uvicorn via background `nohup` from the Codex shell can pass a health check and then be cleaned up by the command environment. For persistent user-facing startup, keep using the desktop/Terminal launcher service window; for validation, use a foreground controlled session and stop it explicitly.
  - Native HTML `input type=date` cannot preselect only year/month without a day. Empty inputs still open the platform date picker around the current date/month, which satisfies the practical "no default day selected" constraint without inventing a custom date widget.
  - OCR polarity review improves risk detection but does not guarantee truth when native text and image OCR disagree. Reports must preserve the warning so clinical reviewers can open the source page for final adjudication.

2026-06-25 OCR model options research:

- User asked for an independent sub-agent style assessment of PaddleOCR-VL 1.6, UnlimitedOCR, and PP-OCRv6 for enrollment-review source materials.
- Conclusion:
  - Keep PaddleOCR-VL 1.6 as the main OCR/VLM path for now.
  - Consider PP-OCRv6 plus PP-StructureV3 later as a targeted secondary verifier for pure printed Chinese text, lab-report numbers, and tables.
  - Do not move UnlimitedOCR into the production path now; it is interesting for long-document research but mismatched with page-level clinical evidence traceability.
- Rationale:
  - Enrollment review is most sensitive to polarity and exact facts: `否认/确认`, `有/无`, `阴性/阳性`, dates, time windows, lab value/unit/reference-range triples, and investigator judgment wording.
  - PaddleOCR-VL 1.6's public positioning covers document parsing, tables/layout, reading order, Chinese text, stamps, scanned/tilted/photo-like documents, and complex document elements, which better matches mixed clinical source packets than character-only OCR.
  - Current app already defaults to `models--PaddlePaddle--PaddleOCR-VL-1.6` through oMLX, so short-term engineering risk is lower than replacing the OCR stack.
  - Important limitation: the app currently calls the VLM via an OpenAI-compatible visual prompt route, not the full official PaddleOCR-VL document parser pipeline. Treat current output as page-image Markdown extraction, not a guaranteed reproduction of official full-pipeline benchmarks.
  - PP-OCRv6 alone is stronger as a fast OCR engine but not enough for complex layout/table reconstruction; PP-StructureV3 would be needed for table/layout use cases.
  - UnlimitedOCR's long-document one-pass strategy conflicts with this app's need for page-level source references, retryability, and exact evidence localization.
- Evidence sources named in the research branch:
  - PaddleOCR-VL 1.6 official algorithm page: `https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/algorithm/PaddleOCR-VL/PaddleOCR-VL-1.6.html`
  - PaddleOCR-VL pipeline usage: `https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html`
  - PaddleOCR-VL Apple Silicon usage: `https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/pipeline_usage/PaddleOCR-VL-Apple-Silicon.html`
  - PP-OCRv6 technical report: `https://arxiv.org/html/2606.13108v1`
  - PP-OCRv6 model collection: `https://huggingface.co/collections/PaddlePaddle/pp-ocrv6`
  - PP-StructureV3 usage: `https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/pipeline_usage/PP-StructureV3.html`
  - UnlimitedOCR GitHub: `https://github.com/baidu/Unlimited-OCR`
  - UnlimitedOCR arXiv: `https://arxiv.org/html/2606.23050v1`
- Proposed empirical benchmark before any OCR replacement:
  - Build an 80-120 page local gold set covering Chinese research records, scanned PDFs, phone photos, lab reports, eligibility discussion tables, stamps, low-resolution/tilted/shadowed pages, signatures, historical records, and screening/baseline records.
  - Force inclusion of high-risk pages containing negation/polarity, date windows, SA IDs, lab values/units/reference ranges, and investigator judgment text.
  - Measure full-text CER/WER, key-field exact match, polarity recall, date/window accuracy, lab triple accuracy, table-cell F1/TEDS, reading-order error rate, stamp/signature detection, hallucination/repetition rate, page/source traceability, p95 latency, memory use, 8-concurrency stability, and downstream eligibility-verdict difference rate.
  - Replacement threshold: do not change the primary OCR unless key-field accuracy improves or stays at least equal, hallucination is lower, source traceability is preserved, and throughput remains clinically usable.

2026-06-25 DeepSeek V4 Flash/Pro review-parameter audit and prompt hardening:

- User asked to deeply judge DeepSeek capability and optimize prompts around DeepSeek behavior, then specifically challenged whether V4 Flash should be considered because default Flash is much faster and cheaper than Pro.
- Current production `.env` before this pass used:
  - `REVIEW_BACKEND=deepseek`;
  - `REVIEW_MODEL=deepseek-v4-pro`;
  - no explicit review reasoning effort.
- Official DeepSeek docs checked:
  - thinking-mode docs describe `deepseek-v4-pro` thinking mode and `reasoning_effort` values such as `high` / `max`;
  - pricing/model page lists `deepseek-v4-flash` and `deepseek-v4-pro` as separate models and indicates Flash has lower per-token pricing and higher concurrency limits than Pro.
- Experiment design:
  - Used 6 known historical semantic-error cases from D001 and MG-K10-SAR:
    - D001 `SA01025` `EX-20g`: GGT must not substitute ALT/AST/TBil.
    - D001 `SA03009` `EX-07`/`EX-20h`: urine glucose/occult blood must not imply infection; EX-20h is AND.
    - D001 `SA16002` `EX-22`: TPPA positive + TRUST negative still needs explicit cured-prior-infection judgment.
    - SAR `31001` `EX-09e/g`: threshold child vs other-abnormal researcher component.
    - SAR `31010` `IN-05`: unreadable/missing current-stage baseline evidence is insufficient, not fail.
    - SAR `31015` `EX-09e/g`: ALT/AST not above exclusion threshold; CS abnormality must route to researcher component.
  - First run compared `V4 Flash max`, `V4 Pro high`, `V4 Pro max` in `output/deepseek_reasoning_mode_comparison_20260625/`.
  - User then requested Flash default; added and ran `V4 Flash default` in `output/deepseek_flash_default_20260625/`.
  - Old timing method started before acquiring the concurrency semaphore, so queue wait contaminated elapsed time. This made old Flash max latency numbers invalid, although request parameters and semantic outputs were still valid.
  - Rechecked Flash default vs Flash max after fixing API timing and strengthening the focused experiment prompt in `output/deepseek_flash_default_vs_max_recheck_20260625/`.
- Corrected comparison after timing fix:
  - `V4 Flash default`: average score `93.3`, `5/6` perfect, average true API time `19.7s`, average total tokens `6038`, average reasoning tokens `1441.5`.
  - `V4 Flash max`: average score `100.0`, `6/6` perfect, average true API time `40.8s`, average total tokens `7812.8`, average reasoning tokens `3110.5`.
  - Earlier `V4 Pro high`: average score `93.3`, `5/6` perfect, average elapsed in the old queue-contaminated run `203.3s`, average total tokens `5943.3`.
  - Earlier `V4 Pro max`: average score `81.7`, `4/6` perfect, and incorrectly hard-failed the syphilis exception case.
- Capability judgment:
  - DeepSeek V4 is capable on these eligibility semantics when prompted with explicit fail gates and AND/OR decomposition.
  - V4 Flash default is strong enough for routine batch review and much faster in true API time, but it can still use global IE wording (`初步符合入排/不符合排除/发放导入期药物`) as a substitute for rule-specific researcher judgment.
  - V4 Flash max fixes the SAR-31015 style ambiguity in this small set, but costs about 2x true API time and substantially more reasoning tokens than default Flash.
  - V4 Pro max is not automatically safer; it can over-reason and hard-fail missing exception components.
- Production decision:
  - Changed actual `.env` review path to `REVIEW_MODEL=deepseek-v4-flash` and `REVIEW_REASONING_EFFORT=default`.
  - `REVIEW_REASONING_EFFORT=default` means the client does not send provider-specific `reasoning_effort`; this preserves Flash's default speed/cost profile.
  - `.env.example` now documents `default | high | max`; `high`/`max` should be used for targeted difficult-case reruns, not routine bulk review.
- System prompt hardening:
  - Added a `DeepSeek输出前自检` block to the formal review system prompt:
    - every official parent rule ID must be output;
    - fail requires a positive trigger and cannot coexist with missing/needs-confirmation wording;
    - aggregate IE/global eligibility wording cannot replace rule-specific researcher judgment;
    - threshold child criteria and other-abnormal researcher criteria must be separated;
    - incomplete exceptions must not be forced into pass or definitive fail.
  - Added the same self-check reminder to the user prompt tail so long prompts keep the constraint near the output instruction.
- Parser/postprocess hardening:
  - Syphilis exception guard now handles both directions:
    - pass/na/pass_verify is downgraded if TPPA/TP-Ab positive lacks the complete exception;
    - fail is also downgraded to investigator when the only missing element is the cured-prior-infection judgment and the case cannot be passed by exception yet.
  - Fixed negation-scope detection so `未见研究者明确判断既往感染已治愈` and `表明未判断为不适合入组` are not misread as positive judgments.
  - Added a generic guard for global IE substitution: a pass that relies on `初步符合入排标准/不符合排除标准/可入组/发放导入期药物` while abnormal/CS evidence exists and the rule requires a rule-specific researcher component is downgraded to `investigator`.
- Verification:
  - `python3 -m unittest tests.test_phase_workflow` -> 117 tests OK, 1 skipped.
  - `python3 -m compileall app tests scripts` -> OK.
  - Focused DeepSeek experiment artifacts:
    - `output/deepseek_flash_default_20260625/comparison.md`;
    - `output/deepseek_flash_default_vs_max_recheck_20260625/comparison.md`;
    - `output/deepseek_reasoning_mode_comparison_20260625/combined_flash_default_summary.md`.

2026-06-25 MG-K10-SAR III期 31中心 Flash max 全流程重跑与QC闭环：

- User decision and active runtime:
  - After the corrected timing comparison showed `V4 Flash max` averaged about `40.8s` true API time with better semantic accuracy than Flash default on the focused difficult-case set, the user chose quality over default-speed mode.
  - Current `.env` is intentionally set to:
    - `REVIEW_BACKEND=deepseek`
    - `REVIEW_MODEL=deepseek-v4-flash`
    - `REVIEW_REASONING_EFFORT=max`
    - `OCR_MAX_CONCURRENT=8`
  - This supersedes the earlier default-Flash production note above for current SAR rerun work. Flash default remains a possible routine-batch option, but SAR III center-31 rerun used Flash max.
- Scope:
  - Project recreated as phase-scoped `MG-K10-SAR-III`, study stage `Ⅲ期`.
  - Protocol source: `/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx`.
  - Raw subject source root: `/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/13. CFDI核查/自查/入排/各中心原始入排资料`.
  - First batch center: `31｜河北省中医院`.
  - Subjects processed: `31001`, `31006`, `31008`, `31010`, `31013`, `31014`, `31015`, `31016`, `31017`, `31018`.
  - Review phases processed for every subject:
    - `screening_run_in`（筛选/导入期）
    - `baseline_randomization`（基线/随机期）
- Main run artifacts:
  - Full rerun log: `projects/MG-K10-SAR-III/rerun_logs/mgk10sar_phase3_rerun_20260625_212425.json`.
  - Workflow snapshot: `projects/MG-K10-SAR-III/rerun_logs/protocol_workflow_snapshot_20260625_212425.json`.
  - Project config: `projects/MG-K10-SAR-III/config.json`.
  - Review reports: `projects/MG-K10-SAR-III/subjects/<SUBJECT>/llm/<PHASE>/review_report.md`.
  - Raw LLM retry capture exists for model omission cases:
    - `projects/MG-K10-SAR-III/subjects/31001/llm/screening_run_in/review_attempt_1_raw.md`
    - `projects/MG-K10-SAR-III/subjects/31001/llm/screening_run_in/review_attempt_2_raw.md`
    - `projects/MG-K10-SAR-III/subjects/31010/llm/screening_run_in/review_attempt_1_raw.md`
    - `projects/MG-K10-SAR-III/subjects/31010/llm/screening_run_in/review_attempt_2_raw.md`
- System-level fixes discovered during this rerun:
  - Baseline/current-stage required evidence must not be substituted by screening-only evidence. This was enforced for baseline/D1/randomization-current requirements.
  - Source labels such as `筛选-基线病历` are not proof that a baseline-specific procedure was completed; guards must inspect the actual phase requirement and source content rather than the label string.
  - Screening-phase future baseline/randomization/D1 components should be `pass_verify` follow-up reminders, not ordinary pass/NA.
  - If DeepSeek omits official rule IDs, `run_review` now retries once with explicit missing IDs; if still missing, placeholders are inserted as evidence-insufficient.
  - EX-08 FEV1 pass requires numeric or interpretable FEV1 percent-predicted support. Header-only or OCR-muddled lung-function text is insufficient.
  - Positive biologic/monoclonal exposure with uncertain washout must not be neutralized by broad concomitant-medication denial wording.
  - Historical diagnosis/duration rules such as SAR IN-02 require source traceability. If the duration is supported only by screening/baseline medical-record narrative, keep the rule as `pass_verify` / `溯源提醒`; only prior medical records, diagnosis certificates, prior prescriptions, discharge summaries, or similar traceable prior records support ordinary pass.
  - A final missed expression was found in 31001 baseline IN-02: `病史自2000年起≥2年`. The generic historical-duration regex now covers this pattern and a regression test locks it.
- Backfill/QC:
  - After parser-guard changes, reports were backfilled for both phases:
    - `output/sar31_flash_max_rerun_20260625/backfill_after_parser_guards.json`
    - `output/sar31_flash_max_rerun_20260625/backfill_after_history_regex_fix.json`
  - Final QC outputs:
    - `output/sar31_flash_max_rerun_20260625/qc_summary_final.md`
    - `output/sar31_flash_max_rerun_20260625/qc_summary_final.json`
    - `output/sar31_flash_max_rerun_20260625/qc_flags_final.json`
  - Final QC result: 10 subjects x 2 phases all had 23 rules; preset QC flags were `0`.
  - QC scanned rule count, duplicates, missed reports, IN-02 history traceability, EX-08 numeric FEV1 support, EX-06/EX-12 washout uncertainty marked as pass, EX-09 threshold/non-trigger fail conflicts, and fail/reasoning polarity contradictions.
  - One temporary QC false positive on 31001 baseline IN-05 was due to the QC regex treating ordinary `不符合/不通过` wording as contradiction. The QC regex was tightened; the clinical report was correct.
- Exported reports:
  - Screening Markdown: `output/sar31_flash_max_rerun_20260625/MG-K10-SAR-III_31中心_screening_run_in_Markdown报告.md`.
  - Baseline/randomization Markdown: `output/sar31_flash_max_rerun_20260625/MG-K10-SAR-III_31中心_baseline_randomization_Markdown报告.md`.
  - Combined HTML: `output/sar31_flash_max_rerun_20260625/MG-K10-SAR-III_31中心_FlashMax_双阶段入排审核报告.html`.
  - HTML body leakage check found no `模型`, `RAW-`, `EDC-`, `按要求排除`, `review_raw`, `review_attempt`, `backfill`, `DeepSeek`, or debug wording in visible body text.
  - Browser rendering QC used local Microsoft Edge via Playwright package with explicit executable path; screenshots saved:
    - `output/sar31_flash_max_rerun_20260625/html_qc_1440.png`
    - `output/sar31_flash_max_rerun_20260625/html_qc_1920.png`
    - `output/sar31_flash_max_rerun_20260625/html_qc_390.png`
    - metrics: `output/sar31_flash_max_rerun_20260625/html_visual_qc.json`
  - Visual/browser QC: 1440, 1920, and 390 px viewports had no horizontal overflow; page contained 10 subject sections and final QC-zero text.
- Test and service verification:
  - Targeted historical-duration tests passed.
  - `python3 -m unittest tests.test_phase_workflow` -> 130 tests OK, 1 skipped.
  - `python3 -m compileall app tests scripts` -> OK.
  - `git diff --check` was attempted but this workspace is not a git repository, so it is not applicable here.
  - Service was restarted after backend parser changes using the project Terminal service script. New process served `/api/health` as `{"status":"ok","omlx":true,"deepseek":true}`.
- Pitfalls to remember:
  - Do not trust a healthy API alone after parser changes; restart the uvicorn service or the browser/API will keep using old imported code.
  - Do not reuse a QC regex that flags any co-occurrence of `不符合` and `不通过`; those words can be a correct reason for an inclusion fail.
  - Keep report exports separate from operational/raw retry files. Raw retry files are useful audit artifacts but should not leak into clinical-facing HTML.
  - For SAR 31 center, many baseline/randomization results remain `证据不足` because required D1/baseline raw records or anchor dates are not present, not because the system should infer from screening records.

2026-08-12 expanded V2 architecture conference (Kimi K3 + CodeBuddy GLM-5.2):

- User requested a second complete conference emphasizing independent Agent implementation, testing LOOP, frontend/interaction, provenance and user-oriented workflow.
- Active independent routes were fixed to:
  - `pi/kimi-code/k3-256k:max`, session `019ff580-3595-7000-bc4c-2ab69f8ee01c`, one complete pass, no fallback;
  - `codebuddy/codebuddy-cli/glm-5.2:max`, session `6bce0b95-89e9-49e3-85e9-6f08f18b1e7c`, one complete pass, no fallback.
- Qwen 3.8 was never dispatched. The user first replaced it with GLM-5.2 and then explicitly requested that no Qwen 3.8 conference be run later.
- Codex independently confirmed the live legacy problems cited by the panel:
  - reviewer prompt still auto-prefers prior source on conflict;
  - OCR cache uses mtime;
  - SSE request/disconnect owns and can cancel model review;
  - SubjectInfo still has one `overall_verdict`;
  - OCR adapter returns plain text and strips LOC tokens, so exact bbox provenance is not currently guaranteed.
- Accepted architecture changes:
  - new Phase 0.5 freezes fixture/API, RuleExpression, Agent I/O, rollup and UAT contracts;
  - Phase 1 is the real React shell over a stub API, followed by Phase 1.5 measured user acceptance before backend work;
  - EvidenceRequirement/EvidenceExpectation make absent expected records/procedures first-class;
  - EvidenceSpan has a visible precision ladder `bbox > text_range > page_excerpt > page_only` and a Phase 4 capability spike;
  - Assessor emits semantic candidates; deterministic Evaluator/Gates own final component state, rollup and Action transitions;
  - AgentCall/PromptVersion, optimistic revision, stale scope, per-item Job UX and ReviewRun diff are required;
  - testing expands to contract, deterministic/property/mutation, Agent/OCR eval, clinical regression, failure injection, E2E/visual/accessibility/performance and UAT.
- Rejected/deferred:
  - no day-one LangGraph, free-running swarm, always-on Critic or extra Profile/Report Agent;
  - no split Safety/Provenance Critic until evaluation proves value;
  - no database/backend implementation before Phase 1.5 approval;
  - no fake bbox, silent conflict source preference or legacy verdict migration.
- Conference evidence:
  - `runs/conference/enrollment_review_expanded_design_conference_20260812/`;
  - `reviews/codex_conference_enrollment_review_expanded_design_conference_20260812_review.md`;
  - `metrics/enrollment_review_expanded_design_conference_20260812_conference_metrics.md`.
- Updated baselines:
  - `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`;
  - `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`.
- Hold point remains active: no V2 business implementation, legacy project write, deletion or clinical rerun until the user approves the revised design. After approval, only Phase 0/0.5/1 starts; Phase 1.5 is the next mandatory user gate.

2026-08-12 V2 Phase 0 与 Phase 0.5 合同候选进度：

- Phase 0 已经独立 checker 验收并归档：候选 `97dbadd` 首轮因默认 pytest 覆盖不足、写边界假阳性、依赖/镜像记录不足和文档漂移被拒绝；经 `6fa901d`、`8036d6a` 修复后由同一 checker 接受，验收提交 `2fbe25c`，归档提交 `56bf2f5`。
- Phase 0.5 Trellis 任务为 `.trellis/tasks/08-12-phase0-5-contracts`，当前仍是候选，尚未归档。
- 新合同实现包含 `app/domain/contracts/`、`app/domain/gates/`、`app/domain/expression.py`、`app/domain/rollup.py`、`contracts/v1/`、`scripts/generate_v2_contracts.py` 和 `tests/v2/`。
- 根因防线：Agent 只能写 draft/candidate/CriticRun；FinalAssessment、Action 阻断和 EpisodeRollup 由确定性 Gate/Projection 产生；`ALL/ANY/NOT` 有独立真值语义测试，防止“和”被弱化为“或”。
- 证据状态、判断状态和待办阻断等级分离；溯源待办非阻断、后续节点为关注、当前缺口/专业判断/冲突为阻断。
- Agent/交互/UAT 合同由独立 Luna worker 在限定写域完成，主线程核对后将概念字段统一为 `RuleSet.revision`、`EpisodeRollup`、`AgentCall.model_config_id`。
- 三个合成 Fixture 覆盖明确障碍、未发现明确障碍、缺口/冲突及四级 EvidenceSpan；Schema/OpenAPI/Fixture 连续生成 SHA-256 一致。
- 首轮 Phase 0.5 候选 `43896d1` 被独立 checker 拒绝，finding 包括：表达式只有逻辑结构而无比较器/单位/时间求值、Agent/Gate Schema 与文档漂移、OpenAPI 不可直接消费、3 个单节点 Fixture 不足以执行 UAT、rollup 对弱证据/溯源误判、缺少 ProtocolIntegrity/StageIsolation Gate，以及 FinalAssessment/Action/EpisodeRollup 可直接绕过 Gate 构造。
- 现已按根因修复形成待复核工作树：三值 Evaluator 计算比较器/单位/显式锚点和时间窗，trigger 与 exception 独立；Assessment Gate 从规则类型与求值结果推导状态并拒绝不一致候选；最终 DTO 在模型边界自校验；共享 gap 阻断策略驱动 rollup；新增机器可读 Agent I/O Schema、可消费 OpenAPI、ProtocolIntegrity/StageIsolation 闭包 Gate，以及 6 名受试者 x 2 Episode 的 UAT 工作区。
- 修复后候选测试：合同专项 `82 passed`；V2 默认全套 `218 passed, 1 skipped`；legacy Python 3.9 `130 passed, 1 skipped`。8 个生成 Schema/OpenAPI/Fixture 连续生成 SHA-256 一致；唯一跳过仍是 MG-K10-SAR/06003 OCR 缓存 Fixture 不存在。
- 复核前最后一次测试收集发现 `AgentContractsV1.model_config` 与 Pydantic v2 保留配置名冲突；复合合同字段改为 `model_configuration`，底层审计引用仍为 `AgentCall.model_config_id`，并通过生成器、Schema 和全套回归重新验证。
- 本阶段没有调用真实 LLM/OCR、没有临床重审、没有修改 legacy 项目数据；用户明确要求不再找 Qwen 3.8 会商，后续执行与 checker 路由均排除 Qwen 3.8。
- 下一硬门槛：新上下文独立 checker 无阻断 finding，Codex 接受后才归档 Phase 0.5；Phase 1 只构建真实 React 产品壳和 stub API，Phase 1.5 仍需用户批准后才进入后端业务层。

2026-08-12 Phase 0.5 同一 Luna checker 二次复核：

- 修复提交 `9a47bbc` 仍被拒绝；OpenAPI 可消费性已确认关闭，其余边界只有部分关闭。
- 新的根因级 finding：数值谓词单位可省略且 Evaluator 没有事实 scope；事实极性仍允许空值 fail-open；AssessmentCandidate 可用 gap 改写 UNKNOWN；`historical_source_unavailable` 被错误降级；角色 I/O 与 GateResult runtime 仍未完全兑现；UAT 只有筛选/基线且复制了错误的 baseline `not_due`；ProtocolIntegrity 依赖调用方给出编号答案；Final/Action/Rollup 可用内部一致但未经 accepted Gate 的对象绕过。
- 决定按四组处理：事实/求值范围、Gate 发布链、权威方案与阶段闭包、真实 UAT 前置条件。Phase 1 继续冻结，Qwen 3.8 继续禁用。

2026-08-12 Phase 0.5 二次拒绝后的根因修复（进行中）：

- 用户再次明确“不用再找 Qwen 3.8 会商”；本轮未调用 Qwen，后续仅复用已存在的同一 Luna checker 会话。
- ClinicalFact 已强制 Project/Subject/Episode/Snapshot 范围和 typed polarity；数值事实/谓词必须有显式单位，无量纲使用 `unitless`。Evaluator 只能读取 Gate 接受且与当前范围一致的事实。
- Assessment Gate 现在独立从 EvidenceRequirement/EvidenceExpectation、阶段、冲突和三值求值重建 gap 和 decision；Agent 候选不能用 gap 改写 UNKNOWN。得到确定 TRUE/FALSE 的逻辑树不会继承不影响结果的兄弟分支不确定原因。
- 纯未到期组件在当前阶段直接发布 `not_due + future_stage_not_due`，不被当前证据冲突提前升级为阻断；到期后必须重新投影为当前证据状态。
- FinalAssessment、ActionRequest 和 EpisodeRollup 均由发布函数生成指纹及 accepted GateResult；Fixture 完整性校验会拒绝被拒 Gate、输出哈希不符或跨范围引用。
- ProtocolIntegrity 不再接受调用方填写的官方编号清单；改为对比绑定正式方案哈希的 ProtocolIntegrityManifest，逐项校验完整 Rule 树、逻辑、单位、时间窗、例外、EvidenceRequirement 和 WorkflowStage。
- 合成规则已实际包含嵌套 `ALL/ANY/NOT`、研究者专业判断和随机日期时间窗，不再只是 Schema 理论能表达。
- UAT 生成器不再把筛选 Fixture 换 ID 后复制成基线；每个 Episode 都按当前阶段重新计算 Expectation、Candidate、FinalAssessment、Action 和 Rollup。当前 UAT 是 6 名主要受试者 x 筛选/基线 12 Episode，加预筛和导入/洗脱期 2 个模板，共 14 Episode。
- ProtocolDiffExample 现携带当前和拟议两套真实 RuleSet，新增、删除和逻辑/时间窗变化编号由代码从实际结构差异验证，调用方无法自行“宣布”差异。
- 当前合同专项验证为 `91 passed`，默认全套为 `227 passed, 1 skipped, 18 subtests`，legacy 只读回归为 `130 passed, 1 skipped`；编译、diff 检查和 8 个生成制品的两次哈希重现均通过。尚未完成同一 Luna checker 三次复核，因此 Phase 0.5 仍不可归档。

2026-08-12 Phase 0.5 同一 Luna checker 第三次复核后的修复（进行中）：

- 复核提交 `3eb994f` 仍被拒绝。真实问题不是文案矛盾，而是发布权边界仍有旁路：Assessment Gate 接受 caller-supplied evaluation；UNKNOWN 事实可夹带 typed value；`on` 时间方向忽略区间/半衰期；候选可伪造观察值、单位和 Span；Agent 输出 scope 不完整；方案 Manifest 仍可由调用方自证；Action/Rollup 未强制验证完整上游 publication。
- Assessment Gate 已改为在 Gate 内从 accepted Evidence Gate、规则组件、事实、Span 和锚点独立重建 Evaluation；候选观察逐项对比 Evaluator 推导值、单位、fact/span 和 reason code。UNKNOWN 事实禁止携带 value/unit，`on` 禁止携带上下界或半衰期参数。
- 新增 Evidence Acceptance Gate；AssessmentCandidate、FinalAssessment、ActionRequest、EpisodeRollup 形成逐层 accepted GateResult 闭包。Action 必须引用产生其 gap 的 AssessmentPublication，Rollup 必须验证同一 Episode 内 Assessment/Action publication，不能只凭自洽指纹进入汇总。
- 新增 `ProtocolAuthorityRecord` 与独立 Authority Gate：记录正式方案哈希、期别、完整规则/流程、逐规则来源锚点及人工核对元数据；Manifest 只能从 accepted Authority Record 构建，Protocol Integrity Gate 再对 ProtocolVersion/RuleSet/Workflow/Manifest 闭包重算。
- AgentCall 的 `gate_result_ids` 强制非空；受试者 Agent 及 Eligibility/Evidence/Critic 输出完整绑定 Project、RuleSet revision、Subject、Episode、Run、Snapshot、Source 和创建调用，跨 scope/call 候选被拒绝。
- UAT 模型现强制实际覆盖 `ALL / ANY / NOT`、可执行时间窗、明确障碍/当前缺口/未见明确障碍、四类阶段及基线增量重算；新增语义退化测试，不能靠 14 个结构化 Fixture 的数量通过验收。
- Evidence Gate 进一步封闭为 Normalizer AgentCall -> EvidenceNormalizationCandidate -> Fact/Span -> accepted GateResult；Fixture 保存候选并可重算闭包，Assessment 不能在 Gate 外替换另一组事实。FinalAssessment 与 ActionRequest 也补齐 RuleSet revision，Action 额外绑定 Snapshot。
- AgentCall 进一步补入 `protocol_version_id`，并要求 Candidate Gate 依赖已接受的 Agent 输出 Schema Gate；FinalAssessment、ActionRequest 和相应 Agent 输出也完整携带 ProtocolVersion/RuleSet revision 作用域。
- 新增回归后 V2 合同专项为 `106 passed, 2 subtests passed`；默认全套 `236 passed, 1 skipped, 18 subtests`；legacy Python 3.9 `130 passed, 1 skipped`。生成物双跑哈希一致，同一 Luna checker 四次复核尚未完成，Phase 0.5 继续冻结。
- 用户已明确“不用再找 Qwen 3.8 会商”；Qwen 3.8 保持禁用，本轮仅复用原 Luna checker 会话。
- 本轮本地全量验证的唯一跳过仍为既有 MG-K10-SAR/06003 OCR 缓存 Fixture 不存在。`compileall`、`git diff --check` 通过，4 个 Schema/OpenAPI 与 4 个 Fixture 连续两次生成 SHA-256 一致。

2026-08-13 Phase 0.5 同一 Luna checker 第四次复核后的根因修复（待第五次复核）：

- 第四次复核拒绝 `e2cfd9c`，提出 7 个 P1、2 个 P2：下游只核局部 Gate；AgentCall 未绑定实际 typed Candidate；Assessment 可替换组件；Fixture 保存未水合 Candidate；AgentCall 未核 Protocol/RuleSet scope；方案权威缺服务侧确认事件；Pydantic 条件未进入 Schema；UAT 可在保持计数时改变语义且无真实 `historical_source_unavailable`；错误码仍是自由字符串。
- AssessmentPublication 现保存 RuleSet、AssessmentCandidate、Evidence Candidate、两个 AgentCall、各层 Gate、锚点、Expectation 和 Conflict，并在验证时从完整闭包重算。ActionPublication 内嵌 AssessmentPublication 并重算；EpisodeRollup 对每条 Assessment/Action 完整闭包重放，不接受另一份调用方上游对象。
- Fixture 重放不再按“第一个相同 Candidate”取 Gate，而从 FinalAssessment Gate 的输入引用反向锁定唯一 Candidate Gate 和 Evidence Gate。修复过程中还发现 AgentCall Gate 校验块误缩进在异常分支后、正常路径未执行，已纠正为每个调用核对 ProtocolVersion、RuleSet/revision 及唯一 accepted Schema Gate。
- AgentCall 用 `typed_output_hashes` 逐实体绑定实际 Candidate；Fixture 持久化水合后的 AssessmentCandidate。`AgentCall.error_codes` 和 `GateResult.error_codes` 改为封闭 `RuntimeErrorCode` 枚举。
- 新增由服务记录的 `ProtocolAuthorityConfirmation`，精确绑定方案 SHA、AuthorityRecord SHA/ID、确认命令、确认人和时间；Authority Gate、Manifest、ProtocolVersion 和 Integrity Gate 均纳入该事件。逐规则来源锚点必须以当前 `protocol_version_id` 为前缀。
- UNKNOWN ClinicalFact 禁止 value/unit、`direction=on` 禁止时间窗/半衰期的约束已进入 JSON Schema/OpenAPI 条件语句，并由生成 Schema 的反例测试验证。
- UAT 除统计运算符外，逐 Episode 校验关键复合排除规则为固定 `ALL(研究者判断, ANY(阈值, 随机前28天用药), NOT(测量无效))` 语义；新增保持 ALL/ANY 数量但互换位置及 28->29 天的变异测试，并由第 4 名合成受试者筛选 Episode 实际产生 `observed_weak + historical_source_unavailable`。
- 当前验证：V2 `111 passed, 2 subtests`；默认全套 `241 passed, 1 skipped, 18 subtests`；legacy Python 3.9 `130 passed, 1 skipped`；唯一跳过仍为 06003 OCR 缓存缺失。生成器双跑 8 个制品 SHA-256 完全一致，`compileall` 与 `git diff --check` 通过。
- 用户明确不再找 Qwen 3.8 会商；本轮未调用 Qwen，后续仅复用现有 Luna checker `019ff5fa-ccc9-7cc0-8f38-2cc489783423`。在该 checker 无阻断接受前，Phase 0.5 保持 `in_progress`，Phase 1 继续冻结。

2026-08-13 Phase 0.5 同一 Luna checker 第五次复核：

- 候选 `39fd4de` 被拒绝，Phase 0.5 继续 `in_progress`，不得进入 Phase 1。已关闭：Fixture 水合 Candidate、Agent Protocol/RuleSet scope、Schema/OpenAPI 条件、UAT 语义/历史来源场景、封闭错误码。
- 仍开放的根因不是字段缺失，而是“调用方提供一整套可同步重算的自洽对象”仍可冒充服务端已接受状态：ReviewEpisode/锚点/Expectation/Conflict/半衰期、Agent Schema Gate、RuleSet/Integrity Gate、ProtocolAuthorityConfirmation 和来源清单均缺少只读服务注册表反查。
- 具体 P1：Assessment 可接受伪阶段/锚点/Expectation；伪 Agent Schema Gate 可同步重算；最终 Assessment 未再次验证 typed Candidate；同 ID/revision RuleSet payload 可替换；Fixture 顶层 Fact/Span 只比 ID 不比 payload；Confirmation 与 Manifest source_refs 可自造。P2：Evidence 路径误用 `gate_result_ids[0]`；文档过早宣称闭环。
- 下一修复不再继续堆哈希字段：建立服务端只读发布注册表和版本化 ReviewContext publication；所有发布路径按 ID 解析唯一上游。方案确认改为注册的命令事件，方案来源改为注册的来源目录；Fixture 对 Fact/Span 逐 payload 比较，并补“同步重算全部 Gate 仍拒绝”的对抗测试。
- 用户要求继续严格按设计书/分阶段计划/Trellis 实施；最新全局与项目 `AGENTS.md` 已重读。所有用户文字保持中文临床语境，清除程序员/日志式界面术语；不扩展安全性测试，聚焦产品功能、临床逻辑、证据与真实可用性。测试与复核采用长等待，不因延迟随意 fallback；Qwen 3.8 继续禁用。

2026-08-13 Phase 0.5 第五次拒绝后的根因修复（待第六次复核）：

- 新增只读 `TrustedPublicationRegistry` 与版本化 `ReviewContextSnapshot`。Assessment 不再接受调用方重复提交阶段、日期锚点、Expectation、Conflict 或半衰期；这些输入只从已登记上下文派生。Action/Rollup 必须携带同一注册表重放完整发布链。
- Agent Schema Gate 必须同时被 AgentCall 的 `gate_result_ids` 声明；Assessment 发布再次核对 typed Candidate 哈希并精确重算 Candidate Gate。同 ID/revision 的 RuleSet 仍按完整 payload 哈希核对，并绑定已登记的 Protocol Integrity Gate。
- 方案权威确认改由已登记的服务操作事件派生确认人和时间；Manifest 的来源字符串改为可解析的登记来源记录。Fixture 额外持久化命令事件和来源记录，但验证时必须使用验证前已存在的注册表，禁止从待验证 Fixture 自建信任。
- Fixture 顶层 Fact/Span 与 accepted Evidence Candidate 逐完整 payload 比对；Agent/Evidence Gate 不再依赖 `gate_result_ids[0]`，按门类型、调用声明和唯一性解析。
- 新增同步重算对抗测试，覆盖伪 Evidence Candidate+AgentCall+Gate、伪 Assessment Candidate+AgentCall+Gate、同 ID/revision 替换 RuleSet、重算服务确认事件、重算方案来源记录。局部对象全部自洽仍不能替代服务端登记状态。
- 当前验证：V2 `115 passed, 2 subtests`；默认全套 `245 passed, 1 skipped, 18 subtests`；legacy Python 3.9 `130 passed, 1 skipped`；唯一跳过仍为 06003 OCR 缓存缺失。8 个生成制品双跑哈希一致，`compileall` 与 `git diff --check` 通过。
- Phase 0.5 仍为 `in_progress`，必须由同一 Luna checker 第六次无阻断接受后才可归档并创建 Phase 1 Trellis 子任务。Qwen 3.8 保持禁用。

2026-08-13 Phase 0.5 同一 Luna checker 第六次复核：

- 候选 `9becd6b` 被拒绝，任务继续 `in_progress`。第五轮的审核上下文、typed Candidate、同 ID/revision RuleSet、Fixture Fact/Span 和 Gate 顺序问题已关闭；服务事件/来源与既存注册表只部分关闭。
- 真实 P1：Candidate/Evidence Gate 自身仍未反查注册表；Authority Gate 可只改时间戳后由调用方重算；EpisodeRollup 接受空 Assessment/Expectation/Action 并发布“未发现明确障碍”；Action 的责任方、动作、可接受证据、到期阶段和重算范围仍由调用方任意填写；临床 SourceDocumentVersion、PromptVersion、ModelConfig、Subject、Snapshot、Run 未进入注册表完整 payload 闭包。
- P2：Fixture 可附加未登记但自洽的额外 AgentCall/Schema Gate；证据文档对 Action/Rollup 闭包表述过早。
- 根因统一为：仍有发布函数只验证调用方传入对象的内部一致性，或只验证“被选中路径”，没有证明全集来自验证前既存服务状态。下一轮必须让 Candidate/Evidence/Authority/Action/Rollup 全部消费注册表解析出的唯一实体和完整期望集合。
- 第六轮独立复核自行确认 V2 `115 passed + 2 subtests`、8 个生成物逐字节一致、`compileall`/`git diff --check`/`uv lock --check` 通过；测试绿灯不构成验收。Phase 1 继续冻结，Qwen 3.8 继续禁用。

2026-08-13 Phase 0.5 第六次拒绝后的根因修复（待第七次复核）：

- `TrustedPublicationRegistry` 已扩展到 Candidate、Evidence、Assessment、Action、RuleSet、ReviewContext、Project、Subject、Episode、Snapshot、Run、SourceDocumentVersion、Expectation、Prompt、ModelConfig 及方案权威/来源/完整性审计实体；所有读取均返回深拷贝，只能由应用服务签发。
- Candidate Gate、Evidence Gate 和 Authority/Integrity Gate 均反查验证前已登记的完整 payload。Evidence Gate 的闭包包含完整来源文件版本；Integrity Gate 的闭包含完整 Authority Gate，而非仅绑定 ID。
- Action 发布接口只接受最终判断、缺口类型与服务生成 ID；责任方、补充内容、可接受证据、到期节点、触发证据和重算范围由规则组件、证据要求、当前节点和已发布判断确定性派生。旧生成器中已失效的人工文案参数与映射已清理。
- EpisodeRollup 必须一一覆盖 RuleSet 全部组件和全部 EvidenceRequirement，并为每个最终判断缺口包含唯一 Action；空集合、不完整、重复、跨节点或与注册表全集不一致均拒绝。
- Fixture 完整性校验要求其全部 AgentCall、Gate、Candidate、Assessment、Action、临床来源与审计对象已预先登记；夹带内部自洽的额外记录不能成为信任来源。
- 修复过程发现 UAT 基线新增的后续节点事实只进入 Evidence Candidate、未回写 Fixture 顶层事实，导致完整 payload 集合不一致；已从生成源修复并补回归测试，而非放宽校验。
- 新增 13 项对抗场景；当前 V2 `128 passed + 2 subtests`，默认全套 `258 passed, 1 skipped + 18 subtests`，legacy Python 3.9 `130 passed, 1 skipped`。8 个 Schema/OpenAPI/Fixture 连续两次生成的 SHA-256 完全一致，`compileall`、`uv lock --check`、`git diff --check` 通过。
- Phase 0.5 仍为 `in_progress`，不得创建 Phase 1；下一动作是提交本候选并复用同一 Luna checker `019ff5fa-ccc9-7cc0-8f38-2cc489783423` 进行第七次验收。Qwen 3.8 保持禁用。

2026-08-13 Phase 0.5 同一 Luna checker 第七次复核：

- 候选 `ac0e982` 被拒绝，Phase 0.5 继续 `in_progress`，不得进入 Phase 1。已确认关闭：EpisodeRollup 的完整 Assessment/Expectation/Action 集合；Action 责任方、动作、证据形式、到期节点、触发定位和重算范围的确定性派生。
- P1 根因仍是完整作用域图未成为同一个注册表不变量：Candidate、Evidence、AgentCall 可以同步改成未登记的 `protocol_version_id`，同时保留原 Episode/Run/Project/RuleSet，局部对象仍会被接受。Registry 尚未独立登记 `ProtocolDocumentVersion`。
- 另一个 P1：Protocol Integrity 虽已绑定完整 Authority Gate，但仍未对调用方传入的 ProtocolVersion 与 ProtocolIntegrityManifest 执行完整 payload 反查，可替换版本号或新建自洽 Manifest。
- P2：PromptVersion 只按 ID 存在性查找，尚未强制节点与 AgentCall 一致；Fixture 对完全相同 ID 的 Fact、Span、Call、SourceDocument、Prompt、Model 等重复记录会先经 set/dict 折叠；实施证据文档把“本地已修”写成“已关闭”过早。
- 下一轮统一改造：新增独立 ProtocolVersion 注册实体和共享审核作用域解析器；Evidence、Candidate、Assessment 统一核对 Project/ProtocolVersion/RuleSet/Episode/Run/Snapshot/Prompt；Integrity 先反查 ProtocolVersion 与 Manifest；Fixture 所有顶层实体先做 ID 一对一基数检查。
- 同一 checker 实测 V2 `128 passed + 2 subtests`、8 个生成物一致、`uv lock --check`/`git diff --check` 通过；这些绿灯没有覆盖上述绕过。第八次仍复用同一 checker，不调用 Qwen 3.8，不 fallback。

2026-08-13 Phase 0.5 第七次拒绝后的本地根因修复（待第八次复核）：

- 新增 `app/domain/gates/scope.py`，把 Project、独立 ProtocolDocumentVersion、RuleSet、Subject、ReviewEpisode、ReviewRun、EvidenceSnapshot、SourceDocumentVersion、PromptVersion 和 ModelConfig 解析为一个不可混搭的已登记审核作用域。Evidence、AssessmentCandidate 和最终 Assessment 均复用同一校验，不再各自维护局部 ID 比较。
- Registry 新增独立 `protocol_document_version` 类型。Project 内嵌方案版本必须与该登记 payload 完全一致；Episode、Run、RuleSet、Snapshot 与 AgentCall 的 protocol/project/revision/source 集合必须构成同一图。
- Protocol Integrity 在重算前精确反查 ProtocolVersion 与 ProtocolIntegrityManifest；调用方替换版本名、重算自洽 Manifest 或更换 Manifest ID 均不能成为新信任根。
- PromptVersion 必须满足 `prompt.node == agent_call.node` 且 Schema 合同版本与候选一致；ModelConfig 仍由已登记 ID 唯一解析。
- Fixture 对 19 类顶层/嵌套实体列表在任何 set/dict 折叠前执行 ID 唯一性检查，覆盖 checker 复现的相同 Fact、Span、Call、Document、Prompt、Model 重复以及相邻实体。
- 新增跨未登记 protocol、Prompt 节点漂移、ProtocolVersion/Manifest 替换和 11 类完全重复记录反向测试。本地 V2 `132 passed + 2 subtests`，默认 `262 passed, 1 skipped + 18 subtests`，legacy `130 passed, 1 skipped`；8 个制品双跑 SHA-256 一致，`compileall`、`uv lock --check`、`git diff --check` 通过。
- 本节只记录本地候选，不宣称独立关闭；Phase 0.5 保持 `in_progress`，第八次只复用同一 Luna checker。

2026-08-13 Phase 0.5 同一 Luna checker 第八次复核：

- 候选 `6bfba2c` 被拒绝；第七次五类 finding 已全部确认关闭：未登记方案版本无法发布 Candidate/Evidence/Assessment；ProtocolVersion/Manifest 替换被拒绝；Prompt node 错配被拒绝；19 类 Fixture 实体重复 ID 被拒绝；文档正确区分本地候选与独立验收。
- 新 P1：共享 scope 解析了 SourceDocumentVersion 但只比较 ID 集合，未比较 `source.review_stage <= episode.stage`，导致筛选 Episode 的直接 Candidate/Evidence/Assessment 发布可消费已登记的基线来源。
- 新 P2：Snapshot 的 `source_document_version_ids` 可重复同一 ID；AgentCall 的 `gate_result_ids` 可重复同一 Schema Gate。set 比较和局部 Gate 检查会掩盖重复引用。
- 下一修复在共享 scope 统一加入阶段排序、Snapshot/Agent 引用唯一性和唯一 Schema Gate 检查，并补三层直接发布负例。Phase 1 继续冻结，第九次仍只复用同一 checker，不调用 Qwen 3.8。

2026-08-13 Phase 0.5 第八次拒绝后的本地根因修复（待第九次复核）：

- 共享审核作用域新增来源阶段排序，当前 Episode 不能读取更晚节点的 SourceDocumentVersion；该检查位于直接发布共用路径，不再仅依赖 Fixture 完整性校验。
- EvidenceSnapshot 的来源 ID、AgentCall 的来源 ID 和 Gate ID 均必须唯一；每个 AgentCall 必须且只能绑定一个结构化输出 Gate。Fixture 在进入 set/dict 处理前也显式检查相同引用基数。
- 新增 Evidence 与 Candidate 直接发布未来来源负例、FinalAssessment 重放未来来源负例、重复 Snapshot 来源和重复 Gate 引用的直接发布及 Fixture 负例。
- 本地验证为 V2 `135 passed + 2 subtests`、默认全套 `265 passed, 1 skipped + 18 subtests`、legacy `130 passed, 1 skipped`；8 个生成制品双跑 SHA-256 一致，`compileall`、`uv lock --check`、`git diff --check` 通过。
- 本节仍只描述本地候选，Phase 0.5 保持 `in_progress`；第九次继续复用同一 Luna checker。

2026-08-13 Phase 0.5 同一 Luna checker 第九次复核：

- 候选 `e12b88e` 被拒绝；第八次所有 finding 已确认关闭，包括 Candidate/Evidence/FinalAssessment 的未来节点来源、Snapshot/Gate/Source 重复引用、零个或多个 Schema Gate 及三组相邻阶段边界。
- 唯一 P2：共享 scope 只保证恰好一个 Schema Gate，未验证 AgentCall.gate_result_ids 中额外声明的 Gate。直接发布可夹带一个 rejected 或 scope/hash 错配的额外 Gate，Fixture 路径则会拒绝。
- 下一修复统一直接发布与 Fixture 合同：共享 scope 对每个声明 Gate 逐一检查 accepted、AgentCall 引用、input scope、revision map 和 output hash。Phase 1 继续冻结，第十次仍复用同一 checker。

2026-08-13 Phase 0.5 第九次拒绝后的本地修复（待第十次复核）：

- 共享 scope 现在逐一读取 AgentCall.gate_result_ids 的所有已登记 Gate，不再只挑选唯一 Schema Gate；每项必须 accepted，input/accepted refs 必须包含当前调用，input_scope_hash、input_revision_map 和 output_hash 必须与 AgentCall 完全一致。
- 新增 Evidence 直接发布夹带 rejected Gate、夹带 scope 错配但 accepted 的 Gate，以及 FinalAssessment 夹带 rejected Gate 的反向测试；Fixture 与直接发布合同现使用同一严格度。
- 本地验证为 V2 `137 passed + 2 subtests`、默认 `267 passed, 1 skipped + 18 subtests`、legacy `130 passed, 1 skipped`；8 个生成制品双跑一致，`compileall`、`uv lock --check`、`git diff --check` 通过。
- Phase 0.5 仍为 `in_progress`；第十次继续复用同一 Luna checker，不调用 Qwen 3.8。

2026-08-13 Phase 0.5 同一 Luna checker 第十次复核：

- 候选 `a249d9a` 被拒绝；第九次直接发布 finding 已确认关闭。Evidence、Candidate、FinalAssessment 均拒绝 rejected Gate 和五类错配 accepted Gate，并允许一个 Schema Gate 加多个完整接受的非 Schema Gate。
- 唯一 P2：Fixture 的 AgentCall 循环仍有一份较弱手写 Gate 检查。追加一个未参与下游发布的 AgentCall 时，可夹带 input_scope_hash/input_revision_map 错配的 accepted 非 Schema Gate。
- 根因是直接发布和 Fixture 重复实现同一闭包。下一修复让 Fixture 每个 AgentCall 无条件复用 `require_registered_review_scope`，不再依赖是否被 Evidence/Assessment 使用。Phase 1 继续冻结，第十一次仍复用同一 checker。

2026-08-13 Phase 0.5 第十次拒绝后的本地修复（待第十一次复核）：

- `validate_fixture_scope` 的每个 AgentCall 现在无条件调用 `require_registered_review_scope`，因此所有声明 Gate 都执行与直接发布完全相同的 accepted、调用引用、scope、revision 和 output 闭包检查。
- 新增未参与任何 Evidence/Assessment 发布的额外 AgentCall 场景：即使 Schema Gate 合法，只要附加 accepted Gate 的 input_scope_hash 或 input_revision_map 错配，Fixture 也会拒绝。
- 本地验证为 V2 `138 passed + 2 subtests`、默认 `268 passed, 1 skipped + 18 subtests`、legacy `130 passed, 1 skipped`；8 个生成制品双跑一致，`compileall`、`uv lock --check`、`git diff --check` 通过。
- Phase 0.5 继续 `in_progress`；第十一次仍只复用同一 Luna checker。

2026-08-13 Phase 0.5 同一 Luna checker 第十一次复核：

- 候选 `1535304` 被拒绝；未参与 Evidence/Assessment 发布的 AgentCall 现已确认执行全部 Gate 闭包检查。
- 唯一 P2：可向 Fixture 和预先 registry 同时追加一个完全不被 AgentCall、Protocol、Assessment、Action、Rollup 引用的 GateResult，当前只检查其已登记，未检查它属于当前发布图。
- 下一修复按 Protocol Authority/Integrity、AgentCall 声明 Gate、Assessment 发布链、Action 和 EpisodeRollup 建立显式 Gate 归属集合，拒绝任何无业务归属 Gate 或孤立 Gate 子图；自由 input 引用不能产生归属。Phase 1 继续冻结，第十二次仍复用同一 checker。

2026-08-13 Phase 0.5 第十一次拒绝后的本地修复（待第十二次复核）：

- Fixture 的 GateResult 集合现在必须与当前发布对象显式拥有的 Gate 集合完全相等；历史/审计对象若未来需要保留，应进入独立集合，不能夹带在当前发布 Fixture。
- 新增单个孤立 Gate、互相引用的孤立 Gate 子图、以及向合法 Schema Gate 注入孤立 Gate ID 的反向测试，三者均在发布前拒绝。
- 本地验证为 V2 `139 passed + 2 subtests`、默认 `269 passed, 1 skipped + 18 subtests`、legacy `130 passed, 1 skipped`；8 个生成制品双跑一致，`compileall`、`uv lock --check`、`git diff --check` 通过。
- Phase 0.5 保持 `in_progress`，第十二次继续复用同一 Luna checker，不调用 Qwen 3.8。

2026-08-13 Phase 0.5 同一 Luna checker 第十二次复核：

- 候选 `c22b4bb` 被拒绝；第十一次的孤立 Gate、孤立子图和自由引用绕过均确认关闭。
- 唯一 P2：可向 Fixture 与既存 registry 同时追加一个 scope 合法的 AssessmentCandidate，而不提供 Candidate Gate、不绑定 AgentCall typed output、也不进入 FinalAssessment，当前仍会接受。
- 下一修复从每个已验证 FinalAssessment 发布链反向取得 Candidate 与 Candidate Gate，要求 Fixture 候选集合精确等于已发布候选集合，且每个候选只进入一个最终发布链。Phase 1 继续冻结，第十三次仍复用同一 checker。

2026-08-13 Phase 0.5 第十二次拒绝后的本地修复（待第十三次复核）：

- Fixture 先为每个 FinalAssessment 构造完整 AssessmentPublication，再反向汇总已发布 AssessmentCandidate；候选 ID 不得重复进入多个发布链，且集合必须与 Fixture 的候选集合完全相等。
- 新增“registry 中已登记、scope 合法，但无 Candidate Gate、无 AgentCall typed output、无 FinalAssessment”的候选负例。
- EvidenceNormalizationCandidate 已由 Evidence Gate 与 Fact/Span 全集相等约束覆盖，不存在同构的空候选夹带路径。
- 本地验证为 V2 `140 passed + 2 subtests`、默认 `270 passed, 1 skipped + 18 subtests`、legacy `130 passed, 1 skipped`；8 个生成制品双跑一致，`compileall`、`uv lock --check`、`git diff --check` 通过。
- Phase 0.5 保持 `in_progress`，第十三次继续复用同一 Luna checker，不调用 Qwen 3.8。

2026-08-13 Phase 0.5 同一 Luna checker 第十三次复核：

- 候选 `efbebe6` 获得 `ACCEPT`，无 P1/P2/P3 阻断 finding；第十二次的 AssessmentCandidate 发布全集问题及前十二轮回归面均确认关闭。
- 独立复现覆盖已登记未发布候选、Candidate Gate 无 FinalAssessment、候选重复发布、同步替换、额外 AgentCall 与 EvidenceNormalizationCandidate；独立测试为 V2 `140 passed + 2 subtests`、默认 `270 passed, 1 skipped + 18 subtests`、legacy `130 passed, 1 skipped`、定向 `21 passed`，8 个制品逐字节一致。
- Phase 0.5 已满足退出门槛，按 Trellis 归档；Phase 1 不混入本阶段提交。

2026-08-14 Phase 1.5 多模型医学监查员角色验收：

- Phase 1 合成交互原型经 Kimi K3-256K 真实浏览器视觉/交互审评、独立临床逻辑审评、Codex 根因修订和新鲜 Kimi 会话复测。Grok Build 会话两次被运行时取消，不计端到端覆盖；Cursor/Grok 后备因浏览器权限受限，只计静态审查。
- 已从共享层关闭看板关注类别计数、冲突来源并列、父子/例外语义、无效导航回落、空 Profile 主题误判、溯源分类、证据快照/应备要求、合成时序与阻断不变量、布局跳动等问题。
- 复测发现并关闭 Patient Profile 事件借用同节点其他证据的问题：事件证据关系分为原始依据、判断依据、关联规则资料和无独立定位；可点击事件的规则组件必须与 EvidenceSpan 实际属主一致。
- 最终确定性证据：前端 205 项测试、后端 281 项测试、Playwright 283 项、桌面启动器 14 项全部通过；1 项历史 OCR 固定样本因文件不存在按条件跳过。真实 Chrome 100%/150%/200% 和 1280/1440/1920/390 视口无关键溢出、裁切或重叠。
- Phase 1.5 裁决为可进入 Phase 2。该裁决只接受信息架构、中文交互、证据诚实性和合成数据工作流，不代表真实方案解析、OCR、事实抽取、模型审核、持久化或真实报告已实现。
- Phase 2 必须承接：SQLite 领域层与持久任务；冲突同页来源的可区分摘录；Patient Journey 真实事件时间/精度；390px 长规则名称的渐进展示。V2 继续与 legacy 写路径物理隔离。

## 2026-08-14 Phase 2 规划冻结点

- 当前子任务：`.trellis/tasks/08-14-phase2-sqlite-domain-jobs`，状态 `planning`。
- 已完成：需求、技术设计、实施顺序、验收标准和执行/检查上下文清单；Trellis 校验及 `git diff --check` 通过。
- 已确定：V2 写入独立 `data_v2/`；使用同步 SQLAlchemy 2、SQLite WAL 和 Alembic；迁移前使用 SQLite backup API 生成并校验一致备份；领域历史记录追加写；任务、步骤、检查点和事件持久化；支持租约恢复、幂等、乐观并发及精确过期范围。
- 未开始：任何 Phase 2 产品代码、数据库迁移、接口、后台任务或前端订阅改造。
- 边界：本阶段不接入真实方案解析、上传/OCR、临床事实抽取、Patient Journey 或模型审核，不迁移或写回 legacy 项目。
- 下一安全动作：等待用户在最终规划摘要之后明确批准；获批后执行 `task.py start`，再按 `implement.md` 六个批次实施和独立验证。
