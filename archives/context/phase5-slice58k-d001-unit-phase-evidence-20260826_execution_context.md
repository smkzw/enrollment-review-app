# Execution Context: phase5-slice58k-d001-unit-phase-evidence-20260826

Created: 2026-08-26 05:36:41
Objective: 为D001 II当前闭包矩阵建立可回源、确定性的单位级期别证据视图，收紧共同章节共享证据边界，并用真实冻结工件独立验证；保持claims_complete=false，不运行全部137个语义包。
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `codex-subagent` / `codex` / `gpt-5.6-luna`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- Project instructions: `AGENTS.md`, `.trellis/tasks/08-22-phase5-clinical-facts-profile/{prd.md,design.md,implement.md,CHECKPOINT_20260826_D001_PHASE_EVIDENCE_DESIGN_ACCEPTED.md}`, `.trellis/spec/backend/{index.md,quality-guidelines.md,directory-structure.md,error-handling.md}`.
- Frozen D001 research inputs: `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/{coverage_manifest.json,frozen_phase_plan.json,freeze_metadata.json,d001-ii-control-matrix-closed.json,d001-ii-control-matrix-closure-report.json,slice58i-v2-plan/summary.json}`.
- Existing source-closure implementation and tests: `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/{map_matrix_source_closure.py,test_matrix_source_closure.py}`.
- Phase applicability implementation and tests: `app/agents/phase_applicability.py`, `app/protocols/phase_applicability_planning.py`, `app/services/phase_applicability_execution.py`, `tests/v2/protocols/test_slice58c2_phase_applicability_agent.py`, and directly related protocol tests discovered by references from these files.
- The original D001 protocol named by `freeze_metadata.json` is read-only and may be hashed for verification only. Do not modify, copy over, or normalize it.

## Authorized Writes

- Worker 01 may add or modify only the D001 research generator/test/output files under `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/` needed for the unit-level phase evidence view.
- Worker 02 may modify only `app/agents/phase_applicability.py` and directly corresponding tests under `tests/v2/protocols/` for the shared-evidence obligation-family boundary.
- Worker 03 is verification-only: it may run commands and report evidence but must not modify application, tests, frozen inputs, source protocols, or generated research outputs.
- No worker may change the closed matrix, coverage manifest, frozen plan, original protocol, project context, Trellis specifications, user interface, database, legacy project, or report/metrics files owned by the runner.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.
- Matrix `phase_disposition` is a hypothesis. Unknown, mixed, opposite-phase, partial-anchor, or obligation-family-incompatible evidence must remain blocking.
- Keep `claims_complete=false`; do not execute all 137 semantic packages and do not create subject-review conclusions.
- Shared applicability requires positive evidence for the same obligation family and must not be inferred from generic wording, chapter proximity, official numbering, predose timing, or absence of an explicit phase label.

## Work Items

1. 实现最小单位级期别证据视图生成器与聚焦回归，绑定当前清单、矩阵、方案和计划身份，区分结构阻断与语义未决。
2. 检查并收紧期别语义提示及门禁中共同章节正向证据的义务家族边界，增加全局广播和部分闭合反例。
3. 在真实D001 II冻结工件上独立复算152单元、行级阻断与异质代表包，并执行聚焦测试、源文件哈希和差异检查。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
