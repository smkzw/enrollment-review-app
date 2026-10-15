# Codex Execution Plan: phase5-slice61ck-package99-pregnancy-reporting-followup-boundary

Objective: 依据 Slice 61ck 执行合同，为 D001 II 当前131包冻结计划第99包建立最小模型外来源闭包，并由独立攻击审阅验证妊娠报告、角色差异、AE/SAE分流、随访终点及跨包所有权边界。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | Worker 01：只在合同允许范围内创建 Package 99 配置与父级检查清单，逐条核对10个自有来源、2个只读定义来源和第98/100包排除边界。 | `runs/execution/phase5-slice61ck-package99-pregnancy-reporting-followup-boundary/worker_01.md` |
| `worker_02` | Worker 02：在 Worker 01 产物完成后创建确定性变异测试并运行模型外 dry-run prepare，覆盖对象、时间窗、24小时报告、停药角色差异、AE/SAE分流、随访较晚者终点、条件与例外以及零候选边界。 | `runs/execution/phase5-slice61ck-package99-pregnancy-reporting-followup-boundary/worker_02.md` |
| `worker_03` | Worker 03：在前两项完成后独立只读攻击配置、测试与准备产物，寻找正向字段遮蔽、对象合并、时间漂移、AE/SAE过度扩张、条件例外丢失、跨包吸收和越权候选，并输出可复现发现。 | `runs/execution/phase5-slice61ck-package99-pregnancy-reporting-followup-boundary/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
