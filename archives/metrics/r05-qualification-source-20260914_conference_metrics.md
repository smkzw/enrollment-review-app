# Conference Metrics: r05-qualification-source-20260914

Date: 2026-09-14

| Role | Provider | Model | Status | Duration | API calls | Tokens | Result |
|---|---|---|---|---:|---:|---:|---|
| `evidence_single_object` | `grok-build` | `grok-4.6 high` | exit0 | 未单独核实 | 未核实 | 1782367（含缓存） | 修订 |

## Timeout And Retry Evidence

runner timeout7200秒；长等待接收终态，不重派，无fallback。session 7ae39ca4-81f9-4df6-b707-e42c14b87c1f。原回执input126616、cache_read1629440、output26311、reasoning19621（不能再加到output上）；无产品模型调用。

## Quality Decision

首轮源码审阅发现真实缺陷，主线程修订；运行/临床/视觉均未验收。模型级与cursor/default独立性未知，不以角色数替代证据。
