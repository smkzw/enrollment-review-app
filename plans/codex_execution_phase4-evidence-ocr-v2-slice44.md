# Codex Execution Plan: phase4-evidence-ocr-v2-slice44

Objective: 按已冻结的 Slice 4.4 契约串行实现证据定位、OCR 风险核对、校对覆盖层、完整处理修订与权威活动指针；先完成并验收 WP-44A 领域合同、0010 无损迁移和追加仓储

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | WP-44A：收敛唯一 ReviewEpisode 运行时合同，新增成对活动指针、base/complete 修订辨别与处理候选合同 | `runs/execution/phase4-evidence-ocr-v2-slice44/worker_01.md` |
| `worker_02` | WP-44B：实现 occurrence-aware 定位、OCR 风险旁路核对、校对投影、完整修订和原子激活/回滚 | `runs/execution/phase4-evidence-ocr-v2-slice44/worker_02.md` |
| `worker_03` | WP-44C：实现页、校对、完整修订、激活、引用资料等后端接口与 current 指针投影 | `runs/execution/phase4-evidence-ocr-v2-slice44/worker_03.md` |
| `worker_04` | WP-44D：实现中文原生 OCR 核对闭环前端并完成宽屏交互验证 | `runs/execution/phase4-evidence-ocr-v2-slice44/worker_04.md` |

## Release Order

The table is an ownership map, not a parallel schedule. Dispatch only `worker_01` first. Codex must inspect the actual diff, run independent checks, and record acceptance before dispatching `worker_02`; repeat for `worker_03` and `worker_04`. Shared contracts and repositories must never receive concurrent writes.

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

Verify each package against the frozen Slice 4.4 contract, then verify migration integrity, focused and full regressions, source-preserving OCR/correction behavior, current-version pointer authority, Chinese user-facing projections, and wide-screen rendered behavior within the declared Slice 4.4 boundary. Do not claim the Slice 4.5 continuous source viewer or verified red-box experience here.
