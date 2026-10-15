# Codex Execution Plan: phase4-r3-risk-review-ux

Objective: 修复完整证据版本页序合同漂移，并把不可操作的逐条OCR风险核对收敛为可审计的页级原子核对，同时保持原始风险条目、逐项校对与激活门禁不降级

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 后端新增页级原子风险核对命令与接口，保留逐条不可变记录和幂等/并发合同 | `runs/execution/phase4-r3-risk-review-ux/worker_01.md` |
| `worker_02` | 前端新增对照原件后的本页待核对项一次确认交互，保留逐条展开和校对入口 | `runs/execution/phase4-r3-risk-review-ux/worker_02.md` |
| `worker_03` | 补齐合同、服务、API、前端、真实D001回归及Trellis设计记录 | `runs/execution/phase4-r3-risk-review-ux/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
