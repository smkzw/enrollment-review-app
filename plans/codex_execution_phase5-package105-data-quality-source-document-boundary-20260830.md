# Codex Execution Plan: phase5-package105-data-quality-source-document-boundary-20260830

Objective: 在不调用临床语义模型、不发布控制点、不进入受试者、OCR、Patient Profile或浏览器流程的前提下，核对并建立D001 II冻结计划第105包数据质量、eCRF和源数据/源文件章节的最小模型外来源闭包与确定性回归；区分研究执行和数据治理义务与入排审核证据接受边界，并严格保持第104/106包及无所有权上下文边界。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 独立核对冻结计划第105包的准确来源、原始DOCX结构、期别范围、所有权、相邻包边界和只读上下文，报告任何预期外来源缺口或所有权漂移。 | `runs/execution/phase5-package105-data-quality-source-document-boundary-20260830/worker_01.md` |
| `worker_02` | 在父级授权的最小文件范围内实现Package105模型外配置、父级清单、确定性回归和dry-run；不得预设零候选，必须先根据源文判断数据治理条款是否属于入排控制候选。 | `runs/execution/phase5-package105-data-quality-source-document-boundary-20260830/worker_02.md` |
| `worker_03` | 从临床医学监查和证据治理视角攻击审阅数据质量、eCRF、源数据定义、核证副本、稽查跟踪和源文件访问语义，重点查找把研究执行义务误升格为单例入排条件或把证据可接受性要求错误忽略的两类风险。 | `runs/execution/phase5-package105-data-quality-source-document-boundary-20260830/worker_03.md` |
| `worker_04` | 待父级实现和纠错后，独立只读复核准确来源、提示最小性、候选/流程/规则/动作/程序输出、证据接受边界及相邻包隔离，并运行声明的确定性测试和dry-run。 | `runs/execution/phase5-package105-data-quality-source-document-boundary-20260830/worker_04.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
