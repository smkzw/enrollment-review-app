# Codex Execution Plan: phase5-sar31001-closeout-r3-20260902

Objective: 按 R3 设计和暂停检查点收口 Phase 5：恢复服务契约，查清 MTPLX 502 与基线处理失败根因，合法重建 31001 事实、事件、暴露和 Patient Profile，并完成原始证据临床核验；不得提前实施 Phase 5.5。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审计 8001/8002/8900、MTPLX 实际模型与响应格式、三次 502 日志、OCR 8 路准入，以及 cancel_requested 规范化作业租约终态；给出最小根因证据和安全恢复建议，不修改共享服务。 | `runs/execution/phase5-sar31001-closeout-r3-20260902/worker_01.md` |
| `worker_02` | 在显式 env 契约和专用 8910 边界内诊断基线期 EXECUTOR_ERROR 与 SNAPSHOT_STATE_INVALID 的共同根因，做最小代码修复及聚焦测试；禁止激活失败快照或复用取消作业。 | `runs/execution/phase5-sar31001-closeout-r3-20260902/worker_02.md` |
| `worker_03` | 从合法新作业入口运行 31001 事实规范化与 Profile 投影，逐事件对照当前活动原始证据和来源定位，核对事实、事件、用药暴露、日期、极性、冲突、资料覆盖，并记录 claims_complete 判定证据。 | `runs/execution/phase5-sar31001-closeout-r3-20260902/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
