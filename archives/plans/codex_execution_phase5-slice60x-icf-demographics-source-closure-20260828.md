# Codex Execution Plan: phase5-slice60x-icf-demographics-source-closure-20260828

Objective: 基于当前D001 II期131包冻结计划，为知情同意和人口学第103/104包建立稳定source_ref来源闭包、既有流程目录核对与独立父级临床验收清单；仅在通用合同确有缺口时提出最小实现，不运行受试者/OCR/浏览器，不把金标准注入Agent。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 独立核对body.p767/p768知情同意原文、流程表body.t5.r5、脚注body.p315和IN-01/IN-02之间的权威边界，输出是否已有流程目录完整覆盖及必须保留的时序/证据语义。 | `runs/execution/phase5-slice60x-icf-demographics-source-closure-20260828/worker_01.md` |
| `worker_02` | 独立核对body.p769/p770人口学原文、流程表body.t5.r6、脚注body.p317及IN-02年龄/性别规则，区分资料采集流程与入选判定，输出重复/补充关系和父级检查点。 | `runs/execution/phase5-slice60x-icf-demographics-source-closure-20260828/worker_02.md` |
| `worker_03` | 以共享架构审阅者身份检查当前代表组harness、required_procedure处置、精确访视和资料家族合同是否足以表达知情同意/人口学；只报告通用缺口、所需确定性门禁和最小回归，不写项目特异规则。 | `runs/execution/phase5-slice60x-icf-demographics-source-closure-20260828/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
