# Codex Execution Plan: phase5-protocol-control-concurrency-20260831

Objective: 为方案控制发现链实现最小、可恢复、可审计的持久任务内受控并行执行；并行只适用于相互独立的发现批次，必须保持租约、幂等、部分成功、失败、取消和恢复语义，不恢复或修改暂停中的D001任务，不写入项目特异规则。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审查JobRunner、JobStore、方案控制executor和transport生命周期，提出最小并行边界，明确部分成功/失败、取消、租约丢失和线程安全风险；不得修改代码。 | `runs/execution/phase5-protocol-control-concurrency-20260831/worker_01.md` |
| `worker_02` | 在授权工作树内实现最小租约安全并行执行与配置冻结，仅作用于明确声明可并行的独立发现步骤；补齐必要单元测试，不改临床判定或旧D001数据。 | `runs/execution/phase5-protocol-control-concurrency-20260831/worker_02.md` |
| `worker_03` | 独立设计并执行并发验收测试，覆盖并行峰值、结果顺序、部分成功、可重试/致命失败、取消、租约丢失、恢复和串行兼容；审计是否存在假并发或项目过拟合。 | `runs/execution/phase5-protocol-control-concurrency-20260831/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
