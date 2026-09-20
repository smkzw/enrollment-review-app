# Codex Execution Plan: phase5-sar31001-facts-profile-20260902

Objective: 在隔离 SAR V2 已发布方案上，仅通过正式 API 完成 31001 资料导入、证据处理、事实规范化与 Patient Profile 临床验收；保持来源不可变、节点隔离、反过拟合和 claims_complete 失败关闭。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读核对隔离运行库、已发布方案、31001 输入清单及正式 HTTP 链路，给出不直接写库的最小受控运行顺序与失败关闭条件。 | `runs/execution/phase5-sar31001-facts-profile-20260902/worker_01.md` |
| `worker_02` | 在隔离 8910 运行时仅通过正式 API 创建 31001 与筛选/基线审核节点资料链，运行证据处理、事实规范化和 Profile 投影，完整记录运行身份、状态、哈希与异常；不得修改原始资料或主服务。 | `runs/execution/phase5-sar31001-facts-profile-20260902/worker_02.md` |
| `worker_03` | 独立逐来源核查 31001 已发布事实、时间轴、用药暴露、异常/临界/冲突、筛选与基线节点边界及原始定位，运行反过拟合和回归检查，不自行宣称 Phase 5 完成。 | `runs/execution/phase5-sar31001-facts-profile-20260902/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
