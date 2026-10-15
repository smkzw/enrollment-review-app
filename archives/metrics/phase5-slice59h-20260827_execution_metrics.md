# Execution Metrics: phase5-slice59h-20260827

| Role | Provider | Model | Status | Duration | Tools | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` | `cursor-cli` + product MTPLX | `auto` + `mtplx-qwen38-27b-optimized-quality` | completed | ~536s | endpoint, shell, files | 旧包39门禁绿但临床拒绝；暴露期别作用域缺陷 |
| `worker_02` | `cursor-cli` + product MTPLX | `auto` + `mtplx-qwen38-27b-optimized-quality` | completed | ~214s | endpoint, shell, files | 旧包69仅保留诊断证据；新包63须重跑 |
| `worker_03` | `cursor-cli` + product MTPLX | `auto` + `mtplx-qwen38-27b-optimized-quality` | completed | ~170s | endpoint, shell, files | 旧包70仅保留诊断证据；新包64/65须重跑 |

本表中的 Cursor 为执行者外层路线，MTPLX 为系统内置语义 Agent 的真实调用；两者不是同一层级。`claims_complete=false`。
