# Execution Metrics: phase1_5_agent_monitor_remediation

Date: 2026-08-14

| Role | Actual provider | Actual model | Status | Duration | Recorded tokens | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` | `opencode-go` | `deepseek-v4-flash` | completed | 692.082 s | 155240 total | advisory accepted |
| `worker_02` | `opencode-go` | `deepseek-v4-flash` | completed + same-session recovery | 1513.706 s + 333.049 s | 228393 final total | advisory accepted |
| `worker_03` | `opencode-go` | `deepseek-v4-flash` | completed | 1266.926 s | 222249 total | advisory accepted |
| `complex_manager_cursor` | `cursor-cli` | `auto` | completed | 253.124 s | 225515 input / 13146 output | plan consolidated |

The Beijing route policy replaced each declared `cms-smk/deepseek-v4-flash:max` worker with `opencode-go/deepseek-v4-flash:max`; no undeclared fallback occurred. Workers and manager did not own acceptance.
