# Codex Execution Plan: phase5-slice58-reference-free-wire-design-20260824

Objective: 基于连续真实 oMLX 失败证据，选择一个不依赖跨数组节点引用、能无损表达临床入排布尔逻辑、且可由 provider 严格 Schema 最大程度约束的 compact wire 结构，并形成可实施与可验收的迁移设计。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 独立评估 ANY-of-ALL 无引用布尔组加原子否定的表达完备性、临床可解释性、重复项风险及从 wire 到正式领域树的确定性水合方案。 | `runs/execution/phase5-slice58-reference-free-wire-design-20260824/worker_01.md` |
| `worker_02` | 独立比较固定深度树、布尔 DSL、位置引用、DNF/CNF 布尔组等候选结构在 oMLX provider Schema 支持、模型稳定性、领域等价性和失败可诊断性上的权衡。 | `runs/execution/phase5-slice58-reference-free-wire-design-20260824/worker_02.md` |
| `worker_03` | 基于 v6-v9 真实失败回包制定迁移边界、稳定身份生成、Schema/水合/提示词测试矩阵和 D001/MG-K10-SAR 真实验收门槛，并给出明确推荐。 | `runs/execution/phase5-slice58-reference-free-wire-design-20260824/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
