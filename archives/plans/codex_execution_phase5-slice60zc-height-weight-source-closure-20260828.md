# Codex Execution Plan: phase5-slice60zc-height-weight-source-closure-20260828

Objective: 基于活动D001Ⅱ期131包冻结计划，以未经用户预处理的原始DOCX结构化来源，独立核对第68包身高/体重测量章节与冻结流程目录的来源闭包，判断测量前准备、测量方法、设备条件、单位及记录精度是否形成独立入排审核控制增量；只读分析，不运行受试者、OCR、浏览器，不作最终临床接受。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 独立核对body.p774-p780身高测量来源，区分流程目录已覆盖的筛选期身高测量与章节新增的准备、体位、设备、呼吸和记录精度要求，给出source_ref级父级验收清单。 | `runs/execution/phase5-slice60zc-height-weight-source-closure-20260828/worker_01.md` |
| `worker_02` | 独立核对body.p781-p783体重测量来源，区分流程目录已覆盖的筛选期体重测量与章节新增的校准设备、排空膀胱、着装、脱鞋、单位及小数精度要求，给出source_ref级父级验收清单。 | `runs/execution/phase5-slice60zc-height-weight-source-closure-20260828/worker_02.md` |
| `worker_03` | 只读审阅当前ProtocolReviewControl、required_procedure、动作覆盖、义务原子和代表组harness，判断是否能通用表达测量方法/准备/记录精度，列出必须用确定性门禁阻断的语义压缩与最小非项目特异修复。 | `runs/execution/phase5-slice60zc-height-weight-source-closure-20260828/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
