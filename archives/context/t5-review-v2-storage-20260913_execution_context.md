# Execution Context: t5-review-v2-storage-20260913

Created: 2026-09-13 22:42:04 CST
Objective: Extend existing formal review storage for explicit legacy/V2 evidence lineage without changing existing clinical data or creating a parallel review chain.
Task type: `E03`
Risk: `medium`
Execution module trigger: Codex assigned 1 bounded work item(s). Each item must identify its inputs, allowed paths, deliverable and acceptance check.
Route schedule: `off_peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> zcode/zcode/glm-5.3-flash:max -> pi/mtplx/mtplx-flash-next-optimized-speed:xhigh -> pi/openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `codebuddy` / `codebuddy-cli` / `deepseek-v4.1-flash`
- Review owner: Codex directly reviews worker outputs and final artifacts.

## Source Of Truth

- TODO: Codex must add authoritative source files, screenshots, datasets, or URLs before dispatch.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. Implement ONLY SQLAlchemy storage models and one additive Alembic migration for formal dual-lineage review. Allowed writes: app/storage/models.py and a single new file under the existing Alembic versions directory (discover path and current head; do not alter older migrations). Do NOT edit domain contracts, repositories, service/API/UI files, tests, docs, personal configuration or any database; do not run migrations, tests, models, services, browser or network. Read current models/migration patterns/database spec, app/domain/contracts/review_evidence_scope.py and review.py, and runs/conference/r07-judgment-publication-boundary-20260913/evidence_v2_storage.md as advisory evidence. Existing ReviewRun/AssessmentCandidate/FinalAssessment/ActionRequest storage must keep legacy evidence_snapshot_id FK but allow NULL only with BOTH evidence_snapshot_v2_id FK and complete_processing_revision_id FK; exactly one lineage via CHECK. AgentCall has legitimate protocol-only calls with no review evidence: preserve that nullable case, do not blindly apply review-only XOR. Preserve old rows/payload/hash, child relations and history. Add real V2 fact and locator associations for formal assessments, candidate/transition references and action trigger where existing consumers need them; use actual existing parent table keys, never generic no-FK IDs, never insert fake legacy evidence. Follow migration runner SQLite parent rebuild conventions and reject downgrade with V2 rows. Preserve ALL existing unrelated dirty changes. Return a precise report with migration assumptions, changed tables, FK/check constraints, limitations and necessary owner integration checks; compile/schema construction inspection permitted, full tests deferred per user. Do not claim migration/clinical acceptance. No recursive delegation.

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
