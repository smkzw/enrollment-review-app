# Codex Execution Plan: phase5-slice61bp-package78-sae-seriousness-boundary

Objective: 为D001 II活动131包计划第78包建立模型外临床语义边界：完整理解SAE定义、任一严重性标准、住院/延长住院的因果限定，以及研究者综合判断可不作为SAE的住院情形；只建立真实来源闭包、通用门禁建议和确定性测试，不修改源方案、不并入正式矩阵、不运行受试者审核或临床语义模型。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读核对body.p995-p1006与第79包body.p1007-p1014、AE/TEAE定义及收集窗口、方案内SAE报告和特殊肝功能SAE章节、现有流程目录和正式矩阵；明确每项定义/严重性标准/住院除外的语义职责、Patient Journey分类影响、与入排标准的边界及后续包所有权，不修改文件。 | `runs/execution/phase5-slice61bp-package78-sae-seriousness-boundary/worker_01.md` |
| `worker_02` | 基于第78包冻结计划创建最小真实来源闭包配置、父级临床核对清单和确定性测试；阻断把SAE定义、严重性标准或住院除外改写为筛选/基线入排门槛，保留任一严重性标准的OR语义、住院由AE导致的因果限定、研究者综合判断及第79包连续列表边界；只编辑本切片新增工件及必要共享测试，不调用模型、不改正式矩阵。 | `runs/execution/phase5-slice61bp-package78-sae-seriousness-boundary/worker_02.md` |
| `worker_03` | 独立审查第78包和现有控制矩阵，寻找SAE定义倒灌入排、死亡结果与死亡原因混淆、危及生命反事实扩大、轻微功能干扰误判严重残疾、任意住院即SAE、研究者综合判断被自动豁免、跨包列表截断和后续ADR/SUSAR提前吞并等反例；给出可执行验收条件，不修改实现。 | `runs/execution/phase5-slice61bp-package78-sae-seriousness-boundary/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

Accepted with parent revision. See `reviews/codex_execution_phase5-slice61bp-package78-sae-seriousness-boundary_review.md`. This acceptance is model-free and package-scoped; it does not publish controls, change the formal D001 matrix, run subject review, or accept packages 79-80.
