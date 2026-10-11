# Codex Execution Plan: phase5-protocol-control-recovery-20260831

Objective: 从现有 Phase 5.8d 检查点恢复 D001 只读方案控制点回放，不重复已完成批次；补齐最小既有任务恢复入口与确定性回归，保持协议通用、项目中立，并由独立执行审查确认恢复和反过拟合边界。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 检查现有 JobStore、JobRunner 与方案控制点回放脚本的恢复语义，提出并实现复用既有 SQLite 任务和检查点的最小恢复入口。 | `runs/execution/phase5-protocol-control-recovery-20260831/worker_01.md` |
| `worker_02` | 新增确定性测试，证明中断动态步骤按租约恢复、已完成发现批次不重复执行、来源文件不被重新解析。 | `runs/execution/phase5-protocol-control-recovery-20260831/worker_02.md` |
| `worker_03` | 独立审查恢复实现与提示/合同边界，确认没有 D001、疾病、药物、评分或时间点特异硬编码，并核对未完成结果不会被误报为正式目录或临床验收。 | `runs/execution/phase5-protocol-control-recovery-20260831/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
