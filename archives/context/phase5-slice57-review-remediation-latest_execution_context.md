# Execution Context: phase5-slice57-review-remediation-latest

Created: 2026-08-23 21:04:03
Objective: 闭环 Phase 5.7 独立审查发现的历史版本绑定、修订任务幂等与严格请求结构问题，并补齐可复现测试
Task type: `finite_code_task`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor_cms` -> `cursor` / `cursor-cli` / `auto`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `.trellis/tasks/08-22-phase5-clinical-facts-profile/{prd.md,design.md,implement.md}`
- `docs/PROJECT_CONTEXT.md`
- `context/phase5-slice57-recompute-ui-latest-route_execution_context.md`
- Phase 5.7 current source and tests under `app/**`, `frontend/src/**`, `frontend/e2e/**`, and `tests/v2/**`
- Independent review findings frozen by Codex: history must survive later episode revisions; history UI must use the exact Profile revision; a completed identical correction request must reuse the existing Job; nested date-range request fields must be strict.
- Do not add production paths without explicit Codex authorization.

## Current State And Non-Negotiable Semantics

- The branch is intentionally dirty with accepted Phase 5 work and unrelated project configuration edits. Never revert or reformat unrelated changes.
- Backend history repository/service and strict nested date DTO have partial fixes already present. Review and complete them instead of restarting the implementation.
- A correction request identity is based on the frozen authority plus normalized user request, not the current mutability of the target after the first correction completes.
- Historical correction display must resolve its title, locator excerpt, page, and evidence action from `profile_revision_id` recorded by that correction. The latest Profile is not a valid fallback.
- Workers do not update Trellis task status, project context, execution plans/reports, screenshots, or generated route artifacts.

## Authorized Write Sets

- `worker_01`: `app/storage/fact_correction_repository.py`, `app/storage/fact_correction_commit_repository.py`, `app/services/fact_correction_service.py`, `app/services/fact_correction_job_service.py`, `app/api/v2/fact_corrections.py`, `app/api/v2/fact_correction_schemas.py`, and directly corresponding files under `tests/v2/{api,services,storage}/` only.
- `worker_02`: `frontend/src/pages/SubjectsPage.tsx`, `frontend/src/components/profile/ProfileCorrectionHistory.tsx`, their directly corresponding `*.test.tsx` files, and `frontend/e2e/profile-correction.spec.ts` only.
- `worker_03`: read-only review and test execution. No source, test, task, context, screenshot, plan, prompt, report, or configuration writes.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 核查并修复后端修订历史跨审核节点修订号持久可见及完成任务重复提交幂等
2. 核查并修复前端修订历史严格绑定形成该记录时的 Patient Profile 版本和原始证据定位
3. 补充后端与前端聚焦回归，执行差异审查并提交紧凑实施交接

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
