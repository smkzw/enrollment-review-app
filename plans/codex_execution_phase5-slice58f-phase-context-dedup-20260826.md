# Codex Execution Plan: phase5-slice58f-phase-context-dedup-20260826

Objective: 消除期别语义Agent提示中上下文单元的重复正文注入，在保留完整来源闭包、索引可追溯性和中文临床语义合同的前提下显著缩短真实D001批次输入，并验证技术与临床语义不回退。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审计当前context_units与context_packets重复渲染的合同边界，提出不丢来源、不改变身份与水合逻辑的最小压缩方案。 | `runs/execution/phase5-slice58f-phase-context-dedup-20260826/worker_01.md` |
| `worker_02` | 实现上下文正文单次呈现、上下文包只保留类型与索引的通用提示压缩，并更新相关合同说明，不加入项目特异规则。 | `runs/execution/phase5-slice58f-phase-context-dedup-20260826/worker_02.md` |
| `worker_03` | 更新合成回归，重建真实D001 package 32并量化提示长度、索引闭包与模型前置条件，核对MG-K10相关回归和源文件只读性。 | `runs/execution/phase5-slice58f-phase-context-dedup-20260826/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
