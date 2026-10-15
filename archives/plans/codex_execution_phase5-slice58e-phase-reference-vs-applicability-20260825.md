# Codex Execution Plan: phase5-slice58e-phase-reference-vs-applicability-20260825

Objective: 修复方案期别结构识别把段落中引用的对侧期别误当作实际适用期别的系统缺陷，使明确期别章节上下文支配普通叙述，而真正期别标题和明确两期共用声明仍可切换范围。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审计正文与表格期别上下文传播，基于D001 p9、p20、p24、p28、p33及合成反例定义“期别引用”与“期别适用性”边界。 | `runs/execution/phase5-slice58e-phase-reference-vs-applicability-20260825/worker_01.md` |
| `worker_02` | 在app/protocols/phase_detection.py实现通用上下文优先规则：明确章节标题可切换，明确共同适用可覆盖，普通叙述中的对侧期别引用不改变当前适用范围；不得写项目特异规则。 | `runs/execution/phase5-slice58e-phase-reference-vs-applicability-20260825/worker_02.md` |
| `worker_03` | 更新合成回归并只读重建D001，确认p9属于Ⅱ期、p20/p24/p28/p33属于Ⅲ期，重新量化结构图、全文单元、待处置单元和批次并核对MG-K10回归。 | `runs/execution/phase5-slice58e-phase-reference-vs-applicability-20260825/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
