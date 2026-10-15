# Codex Execution Plan: phase5-cross-protocol-glm-acceptance-20260901

Objective: 基于两份不可变方案快照，以纯结构指标选择异构父规则，使用产品内置 GLM-5.3-Flash high 生成一个完整候选，并由当前生产门禁确定性验收；严禁恢复 D001 第20包、修改旧快照或写入项目特异规则。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 审计两份冻结快照的哈希、结构指标选样算法及 D001 暂停边界，输出只读审计结论。 | `runs/execution/phase5-cross-protocol-glm-acceptance-20260901/worker_01.md` |
| `worker_02` | 复用现有生产 ProtocolDeconstructorRunner 与 zhipu-coding-plan GLM-5.3-Flash high，完成选中父规则的一次隔离整候选运行并保留原始响应、模型身份、时延和前后哈希。 | `runs/execution/phase5-cross-protocol-glm-acceptance-20260901/worker_02.md` |
| `worker_03` | 独立重放当前完整门禁，核对候选可发布性、跨项目硬编码风险、来源闭包和证据完整性，不把模型自报当作验收。 | `runs/execution/phase5-cross-protocol-glm-acceptance-20260901/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
