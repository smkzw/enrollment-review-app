# Codex Execution Plan: phase5-slice61ab-candidate-repartition-contract-20260828

Objective: 修复跨阶段混合控制要求拆分候选时，受限修复编排器静默丢弃新增候选仍判为通过的系统级合同冲突，并以保存的真实病毒学输出与通用回归证明修复。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 独立追踪 MIXED_DECISION_STAGE_CONTROL 从发布门禁、错误机器范围、修复提示到 bounded restore 的完整链路，确认最小通用根因和相邻风险。 | `runs/execution/phase5-slice61ab-candidate-repartition-contract-20260828/worker_01.md` |
| `worker_02` | 在共享门禁错误中提供精确候选重分区授权，保证按决定阶段拆分后的全部候选进入水合与发布复核，不硬编码病毒学或项目词。 | `runs/execution/phase5-slice61ab-candidate-repartition-contract-20260828/worker_02.md` |
| `worker_03` | 新增合成 runner 回归和保存真实输出重放，证明旧路径会静默丢候选、新路径保留两个候选且不能越界修改范围外内容。 | `runs/execution/phase5-slice61ab-candidate-repartition-contract-20260828/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
