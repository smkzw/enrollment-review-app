# Codex Execution Plan: phase5-slice61as-ecg-source-closure

Objective: 在不修改真实临床源文件、不发布控制点的前提下，独立核验 D001 II 心电图跨章节来源闭包、重放配置与模型外停止条件，给出是否允许进入一次真实临床语义 Agent 重放的受控结论。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读核对当前 131 包冻结计划中 body.p789/p790/p792/p793/p794、body.t5.r21、body.p331、body.p684 的来源身份、逐字语义、期别和跨章节关系；重点挑战异常+临床意义+研究者不可接受风险的合取逻辑。 | `runs/execution/phase5-slice61as-ecg-source-closure/worker_01.md` |
| `worker_02` | 只读审查 representative_group_ecg_screening.v1.json 与父级盲态清单是否满足现有合同、精确访视、已知目标防重和非项目硬编码边界；运行必要的模型外检查并报告缺口，不调用临床模型。 | `runs/execution/phase5-slice61as-ecg-source-closure/worker_02.md` |
| `worker_03` | 独立检查现有拒绝门和测试覆盖能否在真实 Agent 输出后阻断心电图异常即排除、组合访视、字段遗漏、伪阈值和重复发布；提出最小通用修复或明确无需改共享代码。 | `runs/execution/phase5-slice61as-ecg-source-closure/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
