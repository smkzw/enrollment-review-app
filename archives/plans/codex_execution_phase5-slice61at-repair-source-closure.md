# Codex Execution Plan: phase5-slice61at-repair-source-closure

Objective: 修复其他方案控制 Agent 同会话定向修复缺少权威原文闭包导致逐字引文反复失败的问题；保持严格逐字校验与动作增量门控，不写入任何项目特异临床规则，并以通用回归和 D001 心电图受控重放验证。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 实现最小共享修复：定向修复提示仅附带授权结构单元的冻结原文及来源定位，并为 FABRICATED_EXCERPT 提供逐字复制指引；不得放松连续原文校验或自动篡改模型引文。 | `runs/execution/phase5-slice61at-repair-source-closure/worker_01.md` |
| `worker_02` | 补充通用回归：覆盖弯引号、全角标点等必须逐字保真的原文，验证修复提示包含且仅包含授权原文闭包，同时未授权单元不泄露且严格校验仍拒绝改写引文。 | `runs/execution/phase5-slice61at-repair-source-closure/worker_02.md` |
| `worker_03` | 独立审查动作差集与修复收敛边界：确认 PROCEDURE_ACTION_UNCOVERED 仍阻断把已执行/已记录扩张为覆盖准备与计算动作，并运行相关协议控制测试，报告任何跨层回归。 | `runs/execution/phase5-slice61at-repair-source-closure/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
