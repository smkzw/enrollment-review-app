# Codex Execution Plan: phase5-slice60zw-candidate-action-semantic-coverage-20260828

Objective: 建立项目无关的候选义务动作覆盖证明合同：冻结来源动作若未被流程目录覆盖，只有在其他控制候选的义务陈述逐项保留该动作且来源闭包正确时才可通过；先用保存响应和合成反例离线验证，不调用产品模型、不发布控制点。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审查现有动作冻结、流程目录动作覆盖和候选水合结构，提出最小通用门控位置、错误范围与误报边界；不得修改文件。 | `runs/execution/phase5-slice60zw-candidate-action-semantic-coverage-20260828/worker_01.md` |
| `worker_02` | 实现候选义务动作覆盖证明及聚焦回归，复用共享动作语义检测，不写 D001 专属词句或项目编号，不调用模型，不发布。 | `runs/execution/phase5-slice60zw-candidate-action-semantic-coverage-20260828/worker_02.md` |
| `worker_03` | 独立对保存的 60zv 响应和合成候选进行对抗核验，验证仅改 disposition 不能绕过、逐项动作都必须进入义务陈述、来源摘录不能冒充义务表达；不得修改实现文件。 | `runs/execution/phase5-slice60zw-candidate-action-semantic-coverage-20260828/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
