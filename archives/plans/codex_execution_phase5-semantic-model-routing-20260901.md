# Codex Execution Plan: phase5-semantic-model-routing-20260901

Objective: 为Phase 5方案语义解构实现通用任务分级模型路由：复杂方案语义主用GLM-5.3-Flash，失败后依次MTPLX、DeepSeek V4 Flash high；短提示小任务优先MTPLX，并保证回退显式、作业隔离、可审计且不含项目特异硬编码。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 审阅现有方案语义传输、配置、执行器和缓存合同，形成最小兼容的任务分级与显式回退设计，指出不得混合不同模型批次的边界。 | `runs/execution/phase5-semantic-model-routing-20260901/worker_01.md` |
| `worker_02` | 在当前工作树实现通用模型配置、GLM OpenAI兼容传输接入、复杂任务与短任务路由选择、显式全尝试回退和审计记录；保留旧导入兼容且不修改原始临床资料。 | `runs/execution/phase5-semantic-model-routing-20260901/worker_02.md` |
| `worker_03` | 新增独立确定性测试，覆盖默认路由、短任务分流、回退触发、提供方切换后的候选隔离、缓存不跨模型复用、中文诊断和无项目特异硬编码。 | `runs/execution/phase5-semantic-model-routing-20260901/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
