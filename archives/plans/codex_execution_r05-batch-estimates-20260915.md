# Codex Execution Plan: r05-batch-estimates-20260915

Objective: 实现仅从同资料同配置完整批次历史生成的只读耗时参考服务，不伪造费用；所有者负责API/UI整合。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只新增app/services/batch_processing_estimates.py；只读源码，禁止测试、应用、数据库、模型；返回review/OCR批量耗时参考与可比性和不可估算原因。 | `runs/execution/r05-batch-estimates-20260915/worker_01.md` |

## Codex Acceptance

Owner verifies complete source, exact same-source compatibility, event scope/terminal semantics, null-not-zero fees, bounded queries and API/UI integration. Python compile and TypeScript only now; full tests after product construction per user. This finite backend service gives context relief from owner API/UI integration.
