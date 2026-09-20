# Codex Execution Plan: phase5-package111-protocol-amendment-authority-version-table-boundary-20260830

Objective: 在D001 II期当前不可变131包计划中，完成Package111 body.p1291、body.p1292和body.t15.r0-r1的方案修订授权与版本表语义闭环；保留方案/现行修订案的权威变更机制，区分V1.0初始版本记录与实际修订，不把申办者、主要研究者及伦理委员会的治理义务误成受试者级入排条件，保持Package110/112边界，产出最小配置、父级临床清单、确定性回归、独立攻击验收和可恢复记录，不进入临床语义模型发布、受试者、OCR、Patient Profile、浏览器或视觉阶段。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读核对当前重基线冻结计划Package111身份、四项拥有来源的完整原文、37项只读语境及Package110/112边界；逐项判断修订签署/伦理审批治理、版本表头与V1.0初始记录是否形成任何参加研究前动作，不修改文件。 | `runs/execution/phase5-package111-protocol-amendment-authority-version-table-boundary-20260830/worker_01.md` |
| `worker_02` | 在父级精确授权路径内创建Package111配置、父级临床清单、专项确定性回归并运行模型外dry-run；必须保留方案修订作为唯一授权标准变更形式，不得把V1.0/NA臆造为既往修订，也不得把申办者、主要研究者、伦理委员会义务候选化为受试者资格。 | `runs/execution/phase5-package111-protocol-amendment-authority-version-table-boundary-20260830/worker_02.md` |
| `worker_03` | 独立攻击审阅Package111来源闭包、方案修订权威、版本表头/数据行原子化和相邻包边界；只读输出，重点寻找修订权威丢失、V1.0误读为修订、治理义务候选化、表头数据混淆、Package110/112跨包吸收等漏洞。 | `runs/execution/phase5-package111-protocol-amendment-authority-version-table-boundary-20260830/worker_03.md` |
| `worker_04` | 待父级完成来源与临床语义复核后，独立验收实际文件：复跑专项、相邻包和共享语义回归及dry-run，核对所有权、37项语境隔离、Package110/112未吸收、方案修订权威与V1.0初始版本区分、每个零候选或候选处置均有逐项原文依据、claims_complete=false、中文临床语义和无跨包污染；只读输出。 | `runs/execution/phase5-package111-protocol-amendment-authority-version-table-boundary-20260830/worker_04.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

ACCEPTED：冻结包仅拥有 `body.p1291`、`body.p1292`、`body.t15.r0`、`body.t15.r1`；37项语境保持只读，第110/112包未跨包吸收。方案变更必须采用方案修订、经申办者和主要研究者签字并提交伦理委员会审批或备案，此权威机制保留为项目级治理，不生成单例受试者入排条件。版本表只证明 V1.0 初始版本及 2025年12月10日日期，`NA/NA` 与空白预留行均不被外推为既往修订、变更内容或理由。模型外准备为 `4/0/4`，专项 `29 passed`，Package103-111及共享语义 `268 passed`；未调用临床语义模型或下游流程，`claims_complete=false`。
