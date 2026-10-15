# Codex Execution Plan: phase5-ex07-issue-refinement-20260902

Objective: 修复局部方案语义修订把同一来源的覆盖缺失精化为未解析时间锚点时误判为无关新问题的通用边界；不得削弱发布门禁、不得写入 SAR/D001 特异逻辑。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 在 app/agents/protocol_deconstructor.py 设计并实现最小问题精化比较，仅允许由同一父规则和同一来源定位证明的 PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING 到 TIME_ANCHOR_UNRESOLVED 精化；保留其余新指纹拒绝。 | `runs/execution/phase5-ex07-issue-refinement-20260902/worker_01.md` |
| `worker_02` | 在 tests/v2/protocols 增加服务级和比较器级反例，证明合法精化可保存但仍不可发布，外来来源、不同规则、不同未解析问题和普通新问题继续被拒绝。 | `runs/execution/phase5-ex07-issue-refinement-20260902/worker_02.md` |
| `worker_03` | 只读核查 app/protocols/deconstruction_gate.py 与现有跨项目测试，提出是否需要给 TIME_ANCHOR_UNRESOLVED 增加稳定来源定位；扫描新增实现不得包含项目、疾病、药物、评分或具体时间点硬编码。 | `runs/execution/phase5-ex07-issue-refinement-20260902/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
