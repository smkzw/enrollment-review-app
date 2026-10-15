# Execution Context: phase5-slice58h-cross-heading-packing-20260826

Created: 2026-08-26 01:59:57
Objective: 在不改变临床期别判断、来源闭包和每批最多12个目标的前提下，将相邻小章节的期别适用性批次安全合并，减少真实D001 II调用次数，并保持计划身份、恢复和发布门禁可审计。
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

- TODO: Codex must add authoritative source files, screenshots, datasets, or URLs before dispatch.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 审查现有期别适用性规划器、计划身份与执行恢复合同，提出最小且可泛化的跨标题批次合并边界。
2. 实现相邻批次合并及必要合同更新，保持目标顺序、来源闭包、批次上限和稳定身份，不写项目特异规则。
3. 补充正反例与真实D001 II规模回归，验证批次数下降且上下文、提示规模、源文件和发布完整性不回退。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
