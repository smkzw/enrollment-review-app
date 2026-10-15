# Execution Context: phase5-slice61ag-conditional-waiver-scope-20260828

Created: 2026-08-28 20:27:16
Objective: 修复方案控制解构中条件豁免被拆成无条件执行、同源候选乱序修订以及豁免证据过度声明问题，并以项目无关门禁和回归证明，不运行真实模型、不发布控制点。
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

- TODO: Codex must add authoritative source files, screenshots, datasets, or URLs before dispatch.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 独立审查 protocol_control_gate.py 的条件豁免绑定、证据模态和跨候选范围，提出最小通用修复与反例测试，不修改临床来源。
2. 独立审查 protocol_control_deconstructor.py 同源多候选有界修订在乱序、重复、兄弟候选变化时的身份保持，补充或修订最小测试。
3. 独立核对 v6 p804 临床语义与现有测试覆盖，创建不可变重评记录并检查中文错误提示、完整方案层回归入口。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
