# Execution Context: phase5-slice52-deterministic-gates

Created: 2026-08-23 00:23:56
Objective: Implement only Phase 5 Slice 5.2 deterministic candidate gates on structured fixtures. Validate page coverage, authenticated locator and text hash closure, polarity/assertion, value-unit/date/source semantics, scoped OCR risks, exact deduplication and unresolved conflicts. Persist per-candidate accepted/rejected outcomes and affected scope. Do not call a model, publish facts/Profile, add API/UI, create eligibility conclusions, or add project-specific logic.
Task type: `finite_code_task`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- Declared first-line executor: `finite_code_executor_cms` -> `pi` / `cms-smk` / `deepseek-v4-flash`
- Effective Beijing-night route: `pi` / `opencode-go` / `muse-spark-1.2-contributor` (`xhigh`), restored from the live role manifest; no fallback occurred.
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `.trellis/tasks/08-22-phase5-clinical-facts-profile/prd.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/design.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/implement.md`
- `app/domain/contracts/facts.py`、`app/storage/fact_authority.py` 与 Phase 4 当前完整处理修订/定位合同
- `tests/v2/domain/test_phase5_fact_contracts.py`、`tests/v2/storage/test_fact_repositories.py`、`tests/v2/storage/test_migration_0013.py`
- 不读取或修改生产临床资料；本切片只使用结构化测试夹具。

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. Implement gate-domain contracts and pure deterministic validators for polarity/assertion, value/unit, partial date bounds, record time, source derivation inputs, and candidate-reference closure; add focused tests. Limit edits to new Phase 5 gate modules/contracts/tests and coordinate with existing facts contracts.
2. Implement Phase 4 evidence closure adapter for run/call page coverage, authenticated current-revision locator verification, effective-text/hash matching, and candidate-scoped blocking OCR risk checks; add focused repository-backed tests. Do not edit fact publication repositories.
3. Implement deterministic batch gate orchestration for stable exact-duplicate grouping, semantic conflict detection without winner selection, per-candidate outcomes/affected scope, and failure behavior for empty output or incomplete page coverage; add property/counterexample tests. Do not publish facts or create Profile revisions.

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
