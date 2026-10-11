# Codex Execution Plan: phase5-slice58-deconstruct-model-drift-20260824

Objective: 修复 Phase 5.8 真实隔离验收暴露的方案解构模型配置漂移，使新数据库使用当前可用的专属方案解构模型并以聚焦回归和真实运行证明。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 审计方案解构配置来源、注册路径和 oMLX 当前模型目录，界定共享 REVIEW_MODEL 继承导致的系统性漂移。 | `runs/execution/phase5-slice58-deconstruct-model-drift-20260824/worker_01.md` |
| `worker_02` | 以最小共享层修改将方案解构默认模型与旧审核模型解耦，保持环境变量显式覆盖和现有临床逻辑不变。 | `runs/execution/phase5-slice58-deconstruct-model-drift-20260824/worker_02.md` |
| `worker_03` | 补充配置合同和方案解构传输路径回归，执行聚焦测试并给出真实隔离重跑前的风险清单。 | `runs/execution/phase5-slice58-deconstruct-model-drift-20260824/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
