# Codex Execution Plan: phase5-slice58h-cross-heading-packing-20260826

Objective: 在不改变临床期别判断、来源闭包和每批最多12个目标的前提下，将相邻小章节的期别适用性批次安全合并，减少真实D001 II调用次数，并保持计划身份、恢复和发布门禁可审计。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 审查现有期别适用性规划器、计划身份与执行恢复合同，提出最小且可泛化的跨标题批次合并边界。 | `runs/execution/phase5-slice58h-cross-heading-packing-20260826/worker_01.md` |
| `worker_02` | 实现相邻批次合并及必要合同更新，保持目标顺序、来源闭包、批次上限和稳定身份，不写项目特异规则。 | `runs/execution/phase5-slice58h-cross-heading-packing-20260826/worker_02.md` |
| `worker_03` | 补充正反例与真实D001 II规模回归，验证批次数下降且上下文、提示规模、源文件和发布完整性不回退。 | `runs/execution/phase5-slice58h-cross-heading-packing-20260826/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
