# Codex Execution Plan: r05-batch-ocr-20260915

Objective: 实现批量原件重新识别后台，复用现有任务恢复，不改原结果、不自动启用

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 批量OCR后台服务及读取投影，所有者负责API与前端集成，禁止运行测试、模型和数据库 | `runs/execution/r05-batch-ocr-20260915/worker_01.md` |

## Codex Acceptance

Owner reads the complete changed definitions and adjacent callers; verify source identity, no original mutation, parent/child ownership, cancellation/retry/deferred lifecycle. Only source/compilation checks now; full runtime/browser/clinical tests are deferred by user. API, frontend and maintenance registration remain owner's integration responsibility. Worker completion is not product acceptance.
