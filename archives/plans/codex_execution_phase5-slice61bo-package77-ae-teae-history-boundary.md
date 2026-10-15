# Codex Execution Plan: phase5-slice61bo-package77-ae-teae-history-boundary

Objective: 为D001 II活动131包计划第77包建立模型外临床语义边界：完整理解AE定义、五类不作为AE记录的除外情形、TEAE定义及其与知情同意前既往病史、首次给药前病史记录、给药后AE收集窗口的关系；只建立真实来源闭包、通用门禁建议和确定性测试，不修改源方案、不并入正式矩阵、不运行受试者审核。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读核对body.p985-p994与body.p1022-p1024、Ⅱ期流程表不良事件起始时点、body.p835/p885及现有流程目录和官方入排矩阵，明确每项定义/除外情形的语义职责、Patient Journey资料分类影响和后续包所有权；不得修改文件。 | `runs/execution/phase5-slice61bo-package77-ae-teae-history-boundary/worker_01.md` |
| `worker_02` | 基于第77包冻结计划创建最小真实来源闭包配置、父级临床核对清单和确定性测试，阻断把AE定义、AE记录除外情形或TEAE定义改写为新的筛选/基线入排门槛，同时保留计划住院、侵入检查、疾病预期进展、既存病史及恶化例外的合取/例外语义；只编辑本切片新增工件及必要共享测试，不调用模型、不改正式矩阵。 | `runs/execution/phase5-slice61bo-package77-ae-teae-history-boundary/worker_02.md` |
| `worker_03` | 独立审查第77包和现有控制矩阵，寻找AE定义倒灌筛选期、既存异常错误当AE、计划住院或侵入检查的例外条件丢失、疾病预期进展与异常恶化混淆、TEAE给药前后锚点弱化、后续SAE/ADR/SUSAR包提前吞并等反例；给出可执行验收条件，不修改实现。 | `runs/execution/phase5-slice61bo-package77-ae-teae-history-boundary/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

Accepted with parent revisions. See reviews/codex_execution_phase5-slice61bo-package77-ae-teae-history-boundary_review.md. This acceptance is model-free and package-scoped; it does not change the formal D001 matrix, run subject review, or accept packages 78-80.
