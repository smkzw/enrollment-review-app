# Codex Execution Plan: phase5-slice61br-package80-adr-susar-ae-collection-boundary

Objective: 为D001 II活动131包计划第80包建立模型外临床语义边界：逐项区分ADR因果关系、SUSAR严重性/可疑因果性/非预期性组合、非预期性权威参照、首次服药前病史与给药后AE收集记录职责；只建立真实来源闭包、通用门禁和确定性测试，不改原方案、不改正式矩阵、不运行受试者或临床语义模型。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读核对body.p1015-p1026与第79包SAE尾段、第81-84包AE记录规则、第85-86包肝损伤、第90包因果关系、第92-99包报告流程的真实来源、列表层级、语义职责和所有权；明确最小闭包与不得提前吞并的边界，不修改文件。 | `runs/execution/phase5-slice61br-package80-adr-susar-ae-collection-boundary/worker_01.md` |
| `worker_02` | 基于活动冻结计划创建第80包最小模型外来源闭包配置、父级临床核对清单和确定性测试；锁定ADR至少合理可能性、SUSAR三维组合、IB等预期性参照、ICF后首次服药前病史/伴随疾病、给药后AE收集期、末次安全随访与末次访视差异、单一事件术语记录，不调用模型、不改正式矩阵。 | `runs/execution/phase5-slice61br-package80-adr-susar-ae-collection-boundary/worker_02.md` |
| `worker_03` | 独立寻找因果性与严重性混同、SUSAR把三维AND弱化为任一维度、非预期性无权威参照、给药前病史被记为AE、首次服药后AE漏记、末次安全随访与末次访视窗口混同、单一事件拆并错误、后续肝损伤/因果共同判断/24小时报告被提前吞并等反例；提出可执行验收条件，不修改实现。 | `runs/execution/phase5-slice61br-package80-adr-susar-ae-collection-boundary/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
