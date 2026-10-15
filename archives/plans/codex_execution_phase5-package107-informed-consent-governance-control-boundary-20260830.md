# Codex Execution Plan: phase5-package107-informed-consent-governance-control-boundary-20260830

Objective: 在D001 II期不可变候选计划中完成第107包body.p1251-p1259的伦理与知情同意语义闭环：逐项区分研究级伦理治理、ICF文件治理、知情过程、签署与重新同意控制；对照第67包已接受的筛选前解释和自愿签署控制避免重复，保留第108包边界；产出最小配置、父级清单、确定性回归、独立验收和可恢复记录，不进入临床模型发布、受试者、OCR、Patient Profile、浏览器或视觉阶段。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读核对冻结计划第107包身份、p1251-p1259逐字原文、41项语境、第106/108包边界，并对照第67包p767-p770及已接受ICF动作闭包判断哪些是研究治理、哪些是前置知情同意控制、哪些已被现有来源权威覆盖；输出来源闭包和重复/遗漏风险，不修改文件。 | `runs/execution/phase5-package107-informed-consent-governance-control-boundary-20260830/worker_01.md` |
| `worker_02` | 在父级授权的精确路径内创建Package107配置、父级临床清单和专项确定性回归，并运行模型外dry-run；保持官方来源所有权与第67包控制去重，严禁把ICF模板内容、伦理报批或持续告知全部误成单例资格，也不得把真正参与研究前的签署/日期/充分理解控制丢失。共享代码仅在可复现系统根因且先向父级报告后修改。 | `runs/execution/phase5-package107-informed-consent-governance-control-boundary-20260830/worker_02.md` |
| `worker_03` | 独立攻击审阅Package107临床语义与产品边界：重点检查研究开始前伦理批准、口头和书面告知、无阅读能力时公正见证人、可理解解释、充分时间、参与者或监护人与执行知情同意研究者分别签名日期、非本人签署关系、双方留存、重要新资料后的伦理批准和再次同意，以及与第67包筛选前解释/自愿签署控制的来源权威去重。只读输出。 | `runs/execution/phase5-package107-informed-consent-governance-control-boundary-20260830/worker_03.md` |
| `worker_04` | 待父级合并修正后独立验收实际文件：复跑专项、相邻包及ICF既有回归和dry-run，核对Package107所有权、41项语境隔离、第108包未吸收、控制不重复不漏项、claims_complete=false、中文临床语义和无跨包污染；只读输出。 | `runs/execution/phase5-package107-informed-consent-governance-control-boundary-20260830/worker_04.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

ACCEPTED after parent revision. Worker02's zero-candidate disposition was rejected. Package107 now separates research/ICF governance from pre-participation consent process controls, links only incremental actions to the existing ICF procedure, preserves Package67 and Package108 ownership, and passes 144 adjacent/action regressions plus same-session independent verification. No rendered surface belongs to this model-free source-semantic slice; `claims_complete=false`.
