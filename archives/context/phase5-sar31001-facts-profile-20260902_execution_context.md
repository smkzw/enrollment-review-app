# Execution Context: phase5-sar31001-facts-profile-20260902

Created: 2026-09-02 14:00:40 CST
Objective: 在隔离 SAR V2 已发布方案上，仅通过正式 API 完成 31001 资料导入、证据处理、事实规范化与 Patient Profile 临床验收；保持来源不可变、节点隔离、反过拟合和 claims_complete 失败关闭。
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
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

1. 只读核对隔离运行库、已发布方案、31001 输入清单及正式 HTTP 链路，给出不直接写库的最小受控运行顺序与失败关闭条件。
2. 在隔离 8910 运行时仅通过正式 API 创建 31001 与筛选/基线审核节点资料链，运行证据处理、事实规范化和 Profile 投影，完整记录运行身份、状态、哈希与异常；不得修改原始资料或主服务。
3. 独立逐来源核查 31001 已发布事实、时间轴、用药暴露、异常/临界/冲突、筛选与基线节点边界及原始定位，运行反过拟合和回归检查，不自行宣称 Phase 5 完成。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
