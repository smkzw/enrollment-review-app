# Codex Execution Plan: phase5-slice54-fact-publication

Objective: 实现 Phase 5 Slice 5.4：把已通过确定性门禁的候选事务发布为不可变临床事实、事件、用药暴露和冲突组，并构建精确规则索引与五类资料覆盖投影。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 事务发布服务：从运行级门禁结果构造并原子写入事实、事件、用药暴露、冲突组及 Phase 4 定位链接，复核活动权威指针并保证幂等。 | `runs/execution/phase5-slice54-fact-publication/worker_01.md` |
| `worker_02` | 规则索引：建立仅基于已发布事实类型、RuleComponent 和 EvidenceRequirement 明确身份的双向可重建 FactRuleLink，不使用自由文本模糊匹配。 | `runs/execution/phase5-slice54-fact-publication/worker_02.md` |
| `worker_03` | 资料覆盖投影：从当前审核节点模板生成五类 EvidenceExpectation，细分缺口原因，并正确表达较弱转述事实加溯源提醒而不重复报无证据。 | `runs/execution/phase5-slice54-fact-publication/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

1. Review each owned implementation against the existing 0013 schema and immutable authority validator.
2. Integrate only the smallest shared changes needed; do not add a migration without a reproduced schema gap.
3. Add cross-work-item transaction/idempotency/rebuild/coverage-matrix regressions.
4. Run focused Slice 5.4 tests, adjacent Phase 5 tests, migration tests, then full `tests/v2`.
5. Run compileall, `git diff --check`, Trellis validation, independent check, and update durable records.
