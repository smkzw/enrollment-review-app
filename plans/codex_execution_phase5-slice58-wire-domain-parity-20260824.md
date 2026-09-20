# Codex Execution Plan: phase5-slice58-wire-domain-parity-20260824

Objective: 修复 oMLX 方案解构 wire 严格结构与领域合同不等价：原子定位字段互斥，NOT 与 ALL/ANY 逻辑元数精确，并以捕获的真实 D001 首批反例和通用回归证明。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 在共享 compact wire Schema 中表达 source_clause/source_clauses 互斥且至少一种定位存在，不使用项目特异逻辑，并保持 provider 兼容。 | `runs/execution/phase5-slice58-wire-domain-parity-20260824/worker_01.md` |
| `worker_02` | 将逻辑节点按 NOT 与 ALL/ANY 的不同元数约束拆分或等价表达，保持统一图身份、循环/孤儿/共享子节点校验与无损水合。 | `runs/execution/phase5-slice58-wire-domain-parity-20260824/worker_02.md` |
| `worker_03` | 增加独立 Schema 与水合回归覆盖真实反例、合法单段/多段定位、NOT=1、ALL/ANY不少于2，并运行聚焦及协议测试。 | `runs/execution/phase5-slice58-wire-domain-parity-20260824/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
