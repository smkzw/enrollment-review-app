# Execution Context: phase5-sar31001-closeout-r3-20260902

Created: 2026-09-02 20:49:18 CST
Objective: 按 R3 设计和暂停检查点收口 Phase 5：恢复服务契约，查清 MTPLX 502 与基线处理失败根因，合法重建 31001 事实、事件、暴露和 Patient Profile，并完成原始证据临床核验；不得提前实施 Phase 5.5。
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `off_peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `zcode/glm-5.3-flash:max -> openai-codex/gpt-5.6-luna:max -> codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor` -> `zcode` / `zcode` / `GLM-5.3-Flash`
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

1. 只读审计 8001/8002/8900、MTPLX 实际模型与响应格式、三次 502 日志、OCR 8 路准入，以及 cancel_requested 规范化作业租约终态；给出最小根因证据和安全恢复建议，不修改共享服务。
2. 在显式 env 契约和专用 8910 边界内诊断基线期 EXECUTOR_ERROR 与 SNAPSHOT_STATE_INVALID 的共同根因，做最小代码修复及聚焦测试；禁止激活失败快照或复用取消作业。
3. 从合法新作业入口运行 31001 事实规范化与 Profile 投影，逐事件对照当前活动原始证据和来源定位，核对事实、事件、用药暴露、日期、极性、冲突、资料覆盖，并记录 claims_complete 判定证据。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
