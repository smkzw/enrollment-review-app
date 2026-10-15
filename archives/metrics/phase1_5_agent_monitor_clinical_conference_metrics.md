# Conference Metrics: phase1_5_agent_monitor_clinical

Date: 2026-08-14

| Role | Actual provider | Actual model | Status | Duration | Recorded tokens | Result |
|---|---|---|---|---:|---:|---|
| `general_pi_qwen38` | `opencode-go` | `deepseek-v4-pro` | completed after declared primary identity mismatch | 4879.913 s | 239909 total | revise |
| `general_grok45` | `grok-build` | `grok-4.6` | cancelled twice | 31.248 s initial; 44.953 s recovery record | 126746 initial | not accepted |
| `general_cursor_grok46_fallback` | `cursor-cli` | `cursor-grok-4.6-high` | completed, browser unavailable | 424.815 s | 178867 input / 21136 output | static challenge only |

## Timeout And Retry Evidence

- Qwen health/catalog probe timed out, then the live attempt returned a runtime identity mismatch. With no usable requested session, the declared DeepSeek V4 Pro fallback established session `019ffb91-a5ee-7000-b138-e71a7201654a`.
- Grok Build session `33c42ddb-60b7-43fc-9eea-cac7de089126` ended cancelled on initial and same-session recovery attempts; no model result was accepted.
- Cursor session `df1e62f8-3aa8-442a-8307-67c0a0654ba9` completed but its browser/terminal tools were denied.

## Quality Decision

Credit real-browser clinical findings only to the actual DeepSeek V4 Pro route. Use Cursor output solely as independent static challenge. Do not count Grok as completed coverage.
