# Task Context: enrollment_review_rearchitecture_20260812

Created: 2026-08-12 16:11:47
Objective: 全量盘点并重构设计临床试验入排审核多Agent工作平台，先修复桌面启动入口，形成可追溯的现状审计、需求澄清和阶段实施计划
Task type: `long_horizon_code`
Risk: `high`
Selected agent route: `cms-smk` / `deepseek-v4-flash` / `max`

## Trigger Reason

This task was initialized through the Codex x Hermes complex-task entrypoint because it is expected to involve more than three execution steps, research/writing/report/code/report-visual work, or source-grounded verification.

## Source Of Truth

- Current workspace: `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app`.
- Current implementation: `app/`, `static/index.html`, `scripts/`, `tests/test_phase_workflow.py`.
- Durable project history and reviews: `docs/PROJECT_CONTEXT.md`, `SYSTEM_REVIEW_REPORT.md`, `context/`, `runs/`, `reviews/`, `metrics/`, and project-level `rerun_logs`/audit ledgers.
- Prior conversation exports explicitly authorized by the user: `/Users/smkzw/Downloads/session-20260606.json` and `/Users/smkzw/Downloads/session-20260620.json`.
- Current clinical test projects and derived artifacts: `projects/D001-02-II`, `projects/MG-K10-SAR-III`, and their reports/QC records. Source protocol and subject raw files are read-only evidence.
- User-provided comparator screenshots:
  - `/var/folders/yb/31r9763x6_54mdxswxk36c4w0000gn/T/codex-clipboard-5c1619f9-5d27-4b50-85b8-76109092d27e.png`
  - `/var/folders/yb/31r9763x6_54mdxswxk36c4w0000gn/T/codex-clipboard-b94c619d-02d8-457f-a2b5-64519b5c1658.png`
- Live runtime acceptance target: the local app launched from `/Users/smkzw/Desktop/启动入排审核系统.command` and opened in a real browser.

## Scope

- In scope: diagnose and repair the desktop launcher; inventory all implementation, root documents, historical records, tests, project artifacts, and current runtime behavior; assess Patient Journey and source-linked evidence requirements; assess Graph engineering/multi-Agent suitability; produce an AI-native target design, staged plan, and acceptance criteria after multi-round user clarification.
- Out of scope for the discovery round: destructive cleanup, modification of source protocols/raw subject files/manual IE trackers, bulk clinical reruns, production migration, or a large implementation rewrite before the user confirms the design.

## Success Criteria

- Desktop launcher opens the actual enrollment-review app even when port 8900 is occupied by another local service; service identity and health are verified.
- Current state is supported by a file/record manifest, code and test map, project-artifact inventory, and real browser screenshots.
- The review identifies clinical-rule, evidence, temporal, provenance, workflow, authorization, UI, accessibility, auditability, and operational gaps without confusing prior generated artifacts with current truth.
- Patient Journey design covers demographics, disease state/course, disease-event history, medical-history timeline, medication/treatment timeline, eligibility risk linkage, and exact original-file/page/excerpt traceability.
- Multi-Agent recommendation has explicit node responsibilities, inputs/outputs, deterministic gates, action-routing points, retry/escalation policy, and reasons for or against Graph engineering.
- User-facing implementation plan is only finalized after the necessary multi-round product decisions are answered.

## Risk Boundaries

- Do not modify or move source protocols, EDC exports, raw subject documents, manual trackers, or validated historical reports.
- Derived audit/design artifacts may be written only inside this workspace; the explicitly authorized desktop launcher may be repaired in place.
- Do not expose model names, debug logs, internal evidence IDs, credentials, or raw audit events in reviewer-facing clinical output.
- The system is not the final eligibility decision authority. It is AI-led and must produce concrete, source-linked next actions for every unresolved, ambiguous, or insufficient rule component; no multi-user approval chain is required.
- Do not begin the large rearchitecture until the design questions and acceptance boundary are confirmed with the user.
- The delegated agent is not final authority; Codex owns verification and acceptance.

## Timeout Policy

- Do not mark the delegated agent failed for slow response alone.
- For complex or artifact-heavy work, wait and poll generously; use conference mode when multiple independent model perspectives are needed.
- Failure requires terminal error, provider exhaustion/rate limit after controlled retry, empty/truncated retry output, or no progress after hard wait plus one retry.
- A provider catalog/auth/transport preflight is diagnostic, not a live capability verdict: timeout, auth refresh failure, or malformed probe output must be recorded and followed by one real route attempt. Only a missing executable or explicit invalid/retired/unlisted model may stop before that attempt.

## Loop Log

- 2026-08-12 16:11:47: Task initialized by `tools/hermes_workflow_guard.py init-task`.
- 2026-08-12: Desktop-launch failure reproduced. Port 8900 was occupied by `/Users/smkzw/Vibe-Research/backend`, while the launcher accepted any HTTP 200 response as the enrollment app.
- 2026-08-12: Launcher repaired to select a dedicated free port in 8901-8910, persist the selected port, and require `service=enrollment-review-app` in `/api/health`. Repository launcher scripts and the desktop entry were synchronized.
- 2026-08-12: Verified live service at `http://127.0.0.1:8901` with response `service=enrollment-review-app`, version `2.0.0`, oMLX available, DeepSeek available; login and current home screen opened in a real browser.
- 2026-08-12: Full discovery pass completed across implementation, root documentation, project history, authorized prior-session exports, representative project artifacts, tests, and live browser views. Raw clinical source files were inventoried and sampled but were not modified or indiscriminately reprocessed during the design stage.
- 2026-08-12: Current architecture classified as a file-driven working prototype. Root causes include absence of a versioned clinical-fact/provenance layer, Markdown rules without executable logical components, stage labels without durable review episodes, request-bound batch execution, and missing first-class human dispositions.
- 2026-08-12: Independent read-only review completed with a fresh-context Luna subagent. It agreed that Graph engineering is appropriate for orchestration and human-in-the-loop state, but clinical truth must remain in structured versioned domain records; recommended the minimal split of Evidence Normalizer, Eligibility Assessor, independent Safety/Provenance Critic, deterministic gates, and human disposition.
- 2026-08-12: Bounded external scan compared LangGraph OSS, Temporal Python SDK, Prefect, and Pydantic AI, and checked FHIR Provenance/MedicationStatement/Observation plus CDISC SDTMIG concepts. After deployment confirmation, the leading direction is explicit domain models plus SQLite/WAL, a local durable task runner, and a state graph; LangGraph OSS versus a smaller explicit state machine remains an implementation-spike decision.
- 2026-08-12: Durable discovery artifact written to `docs/REARCHITECTURE_DISCOVERY_20260812.md`. Large rearchitecture remains intentionally blocked pending multi-round user confirmation.
- 2026-08-12: User confirmed round-one product boundaries: local single-Mac/single-user; AI lead rather than an in-system final decision/approval workflow; both incremental and full subject uploads; Patient Profile limited to longitudinal events through prescreen/screening/baseline; protocol version is authoritative and amendments alone can change standards; Q&A/letters/email/medical interpretation may clarify ambiguity but must be warned when conflicting with the protocol/current amendment.
- 2026-08-12: Patient Profile model expanded into research milestones, demographics, index-disease course, symptoms/findings, MH, medication exposure, non-drug treatment/procedures, tests/scores, allergy/infection/immunization, reproductive, social exposure, and evidence/conflict lanes. Every unresolved rule component now targets an ActionRequest with responsible party, requested evidence/action, due stage, blocking level, source, and rule locator.
- 2026-08-12: Second-round decisions opened for seamless II/III project boundaries, full-upload snapshot semantics, stage history, evidence precedence, single-user OCR/fact correction, local login, non-final verdict wording, action-party taxonomy, and lab/display density.
- 2026-08-12: User confirmed all second-round decisions: seamless II/III is the sole combined-project exception; incremental upload merges/deduplicates and selectively reruns, full upload creates a new complete evidence snapshot without deleting history; later-stage evidence cannot silently rewrite earlier-stage reports; original contemporaneous records outrank later narrative summaries; single-user OCR/fact correction is required; login and all multi-account ownership logic should be removed; stage-support wording replaces final enrollment wording; Patient Profile first screen highlights only eligibility-related, abnormal, borderline, and trending test results.
- 2026-08-12: User further required semantic separation between inadequate clinical documentation and genuinely missing procedures/files. A screening-history criterion that is not mentioned is primarily a medical-record completeness gap unless prior source materials establish it; it must not be treated as a definitive event, definitive absence, or generic missing-file request.
- 2026-08-12: Gap taxonomy and action routing expanded in `docs/REARCHITECTURE_DISCOVERY_20260812.md`: record incompleteness, insufficient description, unavailable historical source, known file not uploaded, required procedure not completed, incomplete result, missing date/anchor, professional judgment, conflict, OCR risk, interpretation conflict, and not-yet-due stage requirement.
- 2026-08-12: User confirmed the third-round boundary: screening-record positive history/long disease duration is usable current evidence with an enhanced provenance reminder; subject is never an independent action owner; dashboard uses primary status plus issue counts; actions may auto-close with recorded manual override; legacy projects remain read-only counterexample anchors while the new model creates fresh projects from scratch; interactive visual prototype precedes backend/Graph implementation.
- 2026-08-12: Independent conference completed. Both participants converged that the root problem is clinical representation, durable state and deterministic gates rather than Agent count. Codex selected SQLite/WAL + durable Job/Checkpoint + explicit state machine, bounded Protocol Deconstructor/Evidence Normalizer/Eligibility Assessor calls, and a conditionally triggered veto-only Safety/Provenance Critic. Conflicts hard-block the contested component and are never auto-resolved by source precedence.
- 2026-08-12: Final design baseline saved to `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`; Phase 0-9 plan saved to `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`. No V2 implementation or clinical rerun starts before user approval.
- 2026-08-12: Discovery questions are complete. Final architecture and phased implementation plan now enter independent conference review before design freeze; no large implementation starts until that review is consolidated and presented.
