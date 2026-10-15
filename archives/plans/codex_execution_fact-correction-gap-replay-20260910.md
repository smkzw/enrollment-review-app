# Codex Execution Plan: fact-correction-gap-replay-20260910

Objective: 合成测试复现事实修订后资料缺口丢失，不改产品实现，查清最小同源修复入口

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 仅新建tests/v2/services/test_fact_correction_gap_reprojection.py，复现非默认风险丢失导致升级和无覆盖无信号导致回滚两种情况；阅读既有修订测试和仓储，报告源运行关联及最小修复建议，不修改产品、不读真实数据 | `runs/execution/fact-correction-gap-replay-20260910/worker_01.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
