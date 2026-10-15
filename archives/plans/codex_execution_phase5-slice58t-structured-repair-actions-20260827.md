# Codex Execution Plan: phase5-slice58t-structured-repair-actions-20260827

Objective: 将真实D001第36、60、78包暴露的结构化期别问题转为通用修复动作，不降低来源和期别门禁，并为失败包重跑建立可验收合同

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 仅修改期别语义修复提示：针对成对规则来源被忽略、目标相关支持缺失、证据摘录非逐字三类结构化问题生成通用定向修复要求，不加入D001特异规则 | `runs/execution/phase5-slice58t-structured-repair-actions-20260827/worker_01.md` |
| `worker_02` | 仅增加独立回归：验证三类问题的修复提示要求完整批次回显、成对来源比较、目标自身/同义务来源绑定和逐字摘录，不改生产代码 | `runs/execution/phase5-slice58t-structured-repair-actions-20260827/worker_02.md` |
| `worker_03` | 只读复核slice58s第36、60、78、121包的原文、门禁问题和临床边界，提出父级重跑验收要点，不修改应用代码或临床源文件 | `runs/execution/phase5-slice58t-structured-repair-actions-20260827/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
