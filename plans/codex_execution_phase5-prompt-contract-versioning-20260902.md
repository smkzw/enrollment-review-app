# Codex Execution Plan: phase5-prompt-contract-versioning-20260902

Objective: 在不改写 D001 v1/v2 历史检查点、不改变临床规则内容的前提下，将当前方案控制提示词显式版本化，建立当前可重建的新重放检查点，并恢复完整协议回归。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读分析现有提示词版本、重放配置与 v1/v2 检查点，给出最小兼容边界和不得修改项。 | `runs/execution/phase5-prompt-contract-versioning-20260902/worker_01.md` |
| `worker_02` | 实现当前提示词版本声明、重放包版本记录和新的只读检查点；禁止写入项目特异生产逻辑。 | `runs/execution/phase5-prompt-contract-versioning-20260902/worker_02.md` |
| `worker_03` | 独立审查旧历史不可变性、当前重建确定性及聚焦/完整协议测试，记录剩余风险。 | `runs/execution/phase5-prompt-contract-versioning-20260902/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
