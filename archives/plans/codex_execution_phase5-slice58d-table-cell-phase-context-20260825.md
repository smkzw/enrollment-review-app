# Codex Execution Plan: phase5-slice58d-table-cell-phase-context-20260825

Objective: 修复方案表格单元格内期别段落继承及数字斜杠误识别，使混合 II/III 内容按真实结构原子化且不误判普通临床数值。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 收紧通用期别词法识别，避免PGA 3/4、访视周数等数字斜杠被误识别为II/III期，同时保留真实2/3期、II/III期写法。 | `runs/execution/phase5-slice58d-table-cell-phase-context-20260825/worker_01.md` |
| `worker_02` | 建立同一表格单元格内明确期别段标题的窄范围上下文切换，后续段落继承最近阶段，普通叙述期别提及不得扩散。 | `runs/execution/phase5-slice58d-table-cell-phase-context-20260825/worker_02.md` |
| `worker_03` | 增加合成反例与真实D001只读重建核对，量化单元、待处置和批次数，检查原批次32及表5并验证源文件未变。 | `runs/execution/phase5-slice58d-table-cell-phase-context-20260825/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
