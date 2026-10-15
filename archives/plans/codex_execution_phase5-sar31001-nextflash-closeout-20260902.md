# Codex Execution Plan: phase5-sar31001-nextflash-closeout-20260902

Objective: 按R3和用户最新裁决将现行MTPLX路线统一切换为Qwen3.8-Next-Flash，解决Phase5 OCR缓存归属与内容复用冲突，并从合法新入口完成SAR 31001事实/Profile收口；历史证据不可改写，claims_complete仅在原始证据临床QC后变更。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审查现行设计、配置、测试与运行时真实模型标识，核对Qwen3.8-Next-Flash切换是否完整、是否误改历史证据，并提出最小修正；不得写文件。 | `runs/execution/phase5-sar31001-nextflash-closeout-20260902/worker_01.md` |
| `worker_02` | 审查并最小实现OCR缓存的内容级推理复用与当前page_artifact归属并存，保持不可变证据门禁和设计书内容哈希缓存契约；补根因回归测试。 | `runs/execution/phase5-sar31001-nextflash-closeout-20260902/worker_02.md` |
| `worker_03` | 在专用8910与显式env契约下审计已取消作业和新基线证据链，从合法新幂等入口运行SAR 31001事实规范化、事件/用药/Profile投影并完成逐源临床QC；不得复用取消作业或把未QC结果标完成。 | `runs/execution/phase5-sar31001-nextflash-closeout-20260902/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
