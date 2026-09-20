# Codex Execution Plan: phase5-slice61cj-package98-ae-outcome-definition-end-time-boundary

Objective: 依据 Slice 61cj 执行合同，为 D001 II 冻结计划第98包建立最小模型外来源闭包，并由独立攻击审阅验证结果定义、结束时间、退出时间和死亡分支边界。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | Worker 01：只在合同允许范围内创建 Package 98 配置与父级检查清单，逐条核对8个自有来源、4个只读附加来源和第99包排除边界。 | `runs/execution/phase5-slice61cj-package98-ae-outcome-definition-end-time-boundary/worker_01.md` |
| `worker_02` | Worker 02：在 Worker 01 产物完成后创建确定性变异测试并运行模型外 dry-run prepare，覆盖合同中的状态定义、时间对象、OR/AND、死亡因果和零候选边界。 | `runs/execution/phase5-slice61cj-package98-ae-outcome-definition-end-time-boundary/worker_02.md` |
| `worker_03` | Worker 03：在前两项完成后独立只读攻击配置、测试与准备产物，寻找正向字段遮蔽、同义绕过、关系弱化、跨包吸收和越权候选，并输出可复现发现。 | `runs/execution/phase5-slice61cj-package98-ae-outcome-definition-end-time-boundary/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
