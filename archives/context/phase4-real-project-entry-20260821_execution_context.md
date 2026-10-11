# Execution Context: phase4-real-project-entry-20260821

Created: 2026-08-21 22:36:34
Objective: 补齐V2真实项目从方案发布到受试者资料工作台的用户入口，并保持Phase 4临床边界
Task type: `finite_code_task`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor_cms` -> `pi` / `cms-smk` / `deepseek-v4-flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- Product and phase authority: `AGENTS.md`, `.trellis/tasks/08-19-phase4-evidence-ocr-v2/{prd.md,design.md,implement.md}`, `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`, and `docs/PROJECT_CONTEXT.md`.
- Current implementation surfaces: `app/api/v2/subjects.py`, `app/services/evidence_api_{read,command}_service.py`, `app/storage/{models,repositories}.py`, `frontend/src/api/catalog/`, `frontend/src/pages/SubjectsCatalogPage.tsx`, related tests, and shared desktop styles used by that page.
- Real clinical source files remain read-only and are not needed for this bounded code task. Workers must not open the MG-K10 protocol or subject folders.
- Existing project and user changes must be preserved. Do not add production paths.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.
- Phase 4 may add only the minimum subject-management UI/API needed to reach the evidence workspace. Do not implement clinical fact extraction, Patient Profile, eligibility judgment, action closure, reporting, or Phase 5/6 behavior.
- The write-capable worker may modify only the V2 subject route/service/repository contracts, the catalog API/page/styles, and their directly related tests. No source protocol, raw evidence, legacy project, report, fixture contract, or unrelated refactor may be modified.
- User-facing text must be native Chinese clinical-trial language. No account ownership, login, administrator, model name, backend state, field name, log label, or programmer vocabulary may be added.

## Work Items

1. 审计V2新增/删除受试者与审核节点创建合同，定位缺失闭环
2. 实现中文原生的受试者新增与删除入口、确认和错误恢复
3. 补充API/前端/真实浏览器回归并核对1080P至4K布局

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
