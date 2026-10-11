# Codex Execution Plan: phase5-slice58-reference-free-wire-implementation-20260824

Objective: 将连续真实失败的 oMLX 引用图紧凑输出替换为 versioned dnf-v1 无引用结构，在不改变正式领域表达式和三值评估器的前提下，实现严格 Schema、确定性水合、系统所有身份、显式复杂度和旧合同拒绝，并通过真实项目之前的全面自动回归。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 实现 dnf-v1 provider 严格 Schema 与中文原生提示合同，候选和修订输出统一迁移，删除模型侧节点引用与正式 predicate 身份。 | `runs/execution/phase5-slice58-reference-free-wire-implementation-20260824/worker_01.md` |
| `worker_02` | 实现 dnf-v1 确定性解析和水合，包括原子否定、来源/单位/时间保真、系统生成稳定身份、重复/空组/复杂度/旧图字段显式拒绝。 | `runs/execution/phase5-slice58-reference-free-wire-implementation-20260824/worker_02.md` |
| `worker_03` | 迁移并补充 Schema、解析、水合、三值等价、候选与修订、v6-v9 反例和旧合同拒绝测试，运行聚焦及完整协议回归。 | `runs/execution/phase5-slice58-reference-free-wire-implementation-20260824/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
