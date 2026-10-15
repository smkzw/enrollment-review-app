# Codex Execution Plan: phase5-slice61au-typographic-source-restoration

Objective: 在不增加全局修订预算、不放松逐字来源门禁的前提下，仅对模型引文与唯一授权冻结原文之间可证明为引号字形差异的情况进行确定性原文还原，并保留原始输出和还原记录；重新验证 D001 心电图真实重放。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 实现最小的引号字形等价映射与唯一连续来源匹配；仅在 runner 解析后、严格水合前还原 source_excerpts，禁止词字、数字、单位、比较符、一般标点或空白变化通过。 | `runs/execution/phase5-slice61au-typographic-source-restoration/worker_01.md` |
| `worker_02` | 补充通用回归，覆盖弯/直单双引号唯一匹配可还原，多重匹配、非引号差异、数字单位比较符和跨来源差异仍失败；验证原始模型文本哈希与审计提示保留。 | `runs/execution/phase5-slice61au-typographic-source-restoration/worker_02.md` |
| `worker_03` | 独立审查全局两轮修订预算、来源闭包、候选动作差集和发布门禁未被绕过，并运行聚焦及协议全量回归；若实现不满足边界则明确拒绝。 | `runs/execution/phase5-slice61au-typographic-source-restoration/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
