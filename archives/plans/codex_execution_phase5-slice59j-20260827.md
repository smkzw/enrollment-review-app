# Codex Execution Plan: phase5-slice59j-20260827

Objective: 在修复后的D001 II 131包冻结新基线上，以系统内置MTPLX语义Agent仅运行第63、64、65包，验证合并用药总则与表5全部禁用治疗/洗脱时间窗的期别适用性、来源闭包和关键逻辑表达；不扩大到其他包。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 仅运行并审查新计划第63包：合并用药记录、允许用药、基线前禁用总则和表5父子交接。 | `runs/execution/phase5-slice59j-20260827/worker_01.md` |
| `worker_02` | 仅运行并审查新计划第64包：表5表头至r11，逐行核对固定窗口、较长者为准、清除剂缩短洗脱和嵌套例外。 | `runs/execution/phase5-slice59j-20260827/worker_02.md` |
| `worker_03` | 仅运行并审查新计划第65包：表5最后r12的首次给药前7天限制，并联合核对63至65包是否闭合整张表但不宣称全方案完成。 | `runs/execution/phase5-slice59j-20260827/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

Codex will verify exact model identity, package provenance, source-span closure, all 24 owned source rows across packages 63-65, and the logic of fixed windows, longer-of alternatives, washout-shortening exceptions, nested exceptions, and the final seven-day restriction. No worker may close the task or expand beyond these packages.
