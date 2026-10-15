# Execution Context: phase5-slice58r3-phase-semantic-contract-repair-20260827

Created: 2026-08-27 02:11:56
Objective: 修复D001五包真实语义试跑暴露的候选期别输出合同、完整批次修复回显和规则标题族过宽传播问题，并以通用回归证明不把全局章节或仅提及标题的段落广播到具体控制点。
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

1. 审阅并最小修订 phase applicability 基础提示与修复提示，明确输入 UNKNOWN/MIXED 不是输出候选，并要求修复轮逐项回显完整冻结目标清单。
2. 审阅并收紧确定性规则标题族关联，区分目标相关证据与可传播期别范围证据，禁止共同上层标题或普通提及造成跨规则广播。
3. 补充针对上述根因和相邻路径的回归测试，运行真实运行时聚焦测试并独立核对旧五包中被错误接受的证据链。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
