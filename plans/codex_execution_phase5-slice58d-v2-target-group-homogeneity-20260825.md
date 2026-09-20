# Codex Execution Plan: phase5-slice58d-v2-target-group-homogeneity-20260825

Objective: 修复期别适用性紧凑v2输出合同允许异质目标共享一套证据理由的系统缺陷，以确定性目标等价边界防止不同段落被同组掩盖，并用真实D001批次32验证临床语义。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审计v2分组输入、输出、扩展、门禁与提示词，提出最小且通用的确定性目标同组等价条件，明确对现有v1兼容和输出预算的影响。 | `runs/execution/phase5-slice58d-v2-target-group-homogeneity-20260825/worker_01.md` |
| `worker_02` | 在app/agents/phase_applicability.py内实现异质目标同组失败关闭及中文原生定向修复提示；不得写D001特异词句，不得改变v1历史读取。 | `runs/execution/phase5-slice58d-v2-target-group-homogeneity-20260825/worker_02.md` |
| `worker_03` | 补充合成回归覆盖不同摘录/标题/表格上下文/期别范围不得同组和真正等价目标可同组，并只读重跑D001当前批次32进行临床语义核对。 | `runs/execution/phase5-slice58d-v2-target-group-homogeneity-20260825/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
