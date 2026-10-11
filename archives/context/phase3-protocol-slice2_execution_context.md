# Execution Context: phase3-protocol-slice2

Created: 2026-08-14 14:41:14
Objective: 实现Phase 3切片2：可追溯方案元信息候选、研究期别适用图与解释材料权威约束，并用MG-K10-SAR和D001只读回归验证
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `pi` / `opencode-go` / `deepseek-v4-flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- `.trellis/tasks/08-14-phase3-protocol-deconstruction/{prd,design,implement,research}.md`
- `app/protocols/docx_structure.py` 与切片 1 冻结的不可变方案/来源合同
- MG-K10-SAR V2.1 和 D001 V1.0 真实 DOCX，仅读回归
- 不写回源方案、legacy 项目、旧审核结果或人工资料。

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 元信息候选、字段类别、优先级、冲突与用户确认合同及持久化
2. II/III/共享/真正无缝候选的细粒度适用图、单一期别投影与反例
3. 解释材料、权威冲突和不得改写方案的确定性约束及持久化

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
