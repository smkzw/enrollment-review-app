# Codex Execution Plan: phase5-slice61al-p804-source-closure-repair-20260828

Objective: 在不写入 D001 项目特异规则的前提下，为 CONDITIONAL_EXEMPTION_SCOPE_SPLIT 建立同一来源闭包内候选合并或重写的有界修订合同；冻结不同来源候选，先完成确定性测试和父级可复核证据，不运行语义模型、不发布控制点。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审查真实 v8 第4到第5次响应、离线恢复工件和当前门禁/修订路径，给出最小通用不变量、失败模式及测试矩阵；不得修改文件。 | `runs/execution/phase5-slice61al-p804-source-closure-repair-20260828/worker_01.md` |
| `worker_02` | 实现最小的同源候选闭包修订合同：允许获授权来源键内候选合并或重写，要求来源全集守恒，并恢复所有不同来源候选；只改共享代码和聚焦测试，不触碰临床工件。 | `runs/execution/phase5-slice61al-p804-source-closure-repair-20260828/worker_02.md` |
| `worker_03` | 以对抗视角补充或运行确定性回归，覆盖同源合并、同源拆分、跨来源吸收、来源丢失、不同来源多候选冻结和候选乱序；核对中文提示不泄露父级金标准，不运行模型。 | `runs/execution/phase5-slice61al-p804-source-closure-repair-20260828/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
