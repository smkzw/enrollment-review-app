# Codex Execution Plan: phase5-package101-analysis-set-boundary-20260830

Objective: 对D001 II期冻结候选第101包进行模型外临床语义闭合，确认样本量、分析集、盲态审核及一般统计方法是否形成预筛/筛选/基线控制点，并建立可复核的零候选契约。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读核验body.p1179及p1180-p1185上下文，区分II/III期样本量设计与个例入排控制，指出任何不应归零的语义。 | `runs/execution/phase5-package101-analysis-set-boundary-20260830/worker_01.md` |
| `worker_02` | 只读核验body.p1186-p1196的分析集、盲态审核、统计软件和编码方法，攻击随机后定义被误转为筛选或基线义务的风险。 | `runs/execution/phase5-package101-analysis-set-boundary-20260830/worker_02.md` |
| `worker_03` | 只读核验Package100/101/102所有权与上下文边界，特别检查p1197-p1205不得被Package101吸收。 | `runs/execution/phase5-package101-analysis-set-boundary-20260830/worker_03.md` |
| `worker_04` | 审阅拟定确定性契约与最小测试覆盖，列出必须锁定的不变量和反例；不得修改冻结基线或临床源文件。 | `runs/execution/phase5-package101-analysis-set-boundary-20260830/worker_04.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
