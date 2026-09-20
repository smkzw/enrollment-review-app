# Execution Metrics: phase5-package110-data-publication-commercial-secret-governance-boundary-20260830

| Role | Provider | Model | Status | Duration | Tools | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` | `cursor` | `default` | completed | 134.462s | 31 | 冻结来源、语境分区及逐项零候选核对通过 |
| `worker_02` | `cursor` | `default` | completed | 555.646s | 125 | 三项正式工件、模型外准备及专项34项通过 |
| `worker_03` | `cursor` | `default` | completed | 213.991s | 83 | 来源级独立攻击清单完成，无文件写入 |
| `worker_04` | `cursor` | `default` | completed | 247.417s | 181 | 实际工件、相邻包、共享门禁和dry-run独立验收通过 |

四路return code均为0，`fallback=null`；父级合并回归为`239 passed, 5 warnings`。
