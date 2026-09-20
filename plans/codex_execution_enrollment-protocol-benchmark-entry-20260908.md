# Codex Execution Plan: enrollment-protocol-benchmark-entry-20260908

Objective: 实现原始DOCX经现有产品服务的隔离方案解构横评入口，不改产品提示或生产代码；原生传输可替换配置且保留真实请求回执，无模型调用的测试验证。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 仅scripts/run_frozen_protocol_comparison.py和tests/test_frozen_protocol_comparison.py：复用ProtocolWorkbenchService、create_protocol_deconstruction_executor、JobRunner建立隔离来源与真实解构，准备和执行分开，强制至少65536；禁止模型调用、个人harness、修改app或原件。 | `runs/execution/enrollment-protocol-benchmark-entry-20260908/worker_01.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
