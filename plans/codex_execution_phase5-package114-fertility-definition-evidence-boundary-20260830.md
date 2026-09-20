# Codex Execution Plan: phase5-package114-fertility-definition-evidence-boundary-20260830

Objective: 在D001 II期当前不可变131包计划中，完成Package114 body.p1310-p1321的附录结构、有生育能力女性定义、非生育能力条件与核查动作的模型外语义闭环；保留父子OR逻辑与Package115绝经/避孕后续条款边界，不回吸Package113题录，产出最小配置、父级临床清单、确定性回归、独立攻击验收和可恢复记录，不进入临床语义模型发布、受试者、OCR、Patient Profile、浏览器或视觉阶段。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | worker_01：只读核对Package114冻结身份、body.p1310-p1321原文、38项语境及Package113/115边界；重建生育能力定义的父子逻辑，判断哪些是定义、支持性事实或参与研究前核查动作。 | `runs/execution/phase5-package114-fertility-definition-evidence-boundary-20260830/worker_01.md` |
| `worker_02` | worker_02：在父级补齐Source of Truth与授权路径后，仅在Package114授权路径内创建最小配置、父级临床清单和专项回归，运行模型外dry-run；不得将并列OR条件压平为AND，不得吸收Package115未完整的绝经及避孕条款。 | `runs/execution/phase5-package114-fertility-definition-evidence-boundary-20260830/worker_02.md` |
| `worker_03` | worker_03：只读独立攻击Package114方案，重点查月经初潮/绝经定义倒置、手术史OR变AND、双侧条件丢失、p1320核查方式丢失、p1321与Package115 p1322裂断、相邻包吸收、context升格及冻结身份漂移。 | `runs/execution/phase5-package114-fertility-definition-evidence-boundary-20260830/worker_03.md` |
| `worker_04` | worker_04：待父级复核后只读验收真实工件；复跑专项、相邻包和共享语义回归及dry-run，核对所有权、父子OR逻辑、核查动作、Package113/115隔离、claims_complete=false及无跨包污染。 | `runs/execution/phase5-package114-fertility-definition-evidence-boundary-20260830/worker_04.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Execution Order And Parent Baseline

1. `worker_01` 与 `worker_03` 先独立只读审查冻结原文和边界。
2. `worker_02` 只能在execution context明确授权的四个Package114路径内生成最小工件和dry-run。
3. Codex将对照原文复核工件，必要时在授权路径内做最小修正。
4. `worker_04` 仅在父级复核后启动，对真实工件做只读验收。

父级语义基线：p1310-p1312为附录/定义结构；p1313定义有生育能力时间范围；p1314下为“不视为有生育能力”的并列OR逻辑，p1317-p1319是p1316下的手术史OR分支，p1320为并列确认方式。p1321的“绝经后女性”需结合Package115所有的p1322才完整，但p1322只能只读附加，不得在Package114内改写或发布。最终候选数必须由逐项原文处置决定，不预设。

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
