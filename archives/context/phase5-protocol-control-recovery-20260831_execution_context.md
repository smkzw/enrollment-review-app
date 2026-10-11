# Execution Context: phase5-protocol-control-recovery-20260831

Created: 2026-08-31 08:13:55 CST
Objective: 从现有 Phase 5.8d 检查点恢复 D001 只读方案控制点回放，不重复已完成批次；补齐最小既有任务恢复入口与确定性回归，保持协议通用、项目中立，并由独立执行审查确认恢复和反过拟合边界。
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `unscheduled`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `openai-codex/gpt-5.6-luna:max -> codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor` -> `pi` / `openai-codex` / `gpt-5.6-luna`
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

1. 检查现有 JobStore、JobRunner 与方案控制点回放脚本的恢复语义，提出并实现复用既有 SQLite 任务和检查点的最小恢复入口。
2. 新增确定性测试，证明中断动态步骤按租约恢复、已完成发现批次不重复执行、来源文件不被重新解析。
3. 独立审查恢复实现与提示/合同边界，确认没有 D001、疾病、药物、评分或时间点特异硬编码，并核对未完成结果不会被误报为正式目录或临床验收。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
