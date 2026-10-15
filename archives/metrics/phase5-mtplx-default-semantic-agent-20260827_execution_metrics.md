# Execution Metrics: phase5-mtplx-default-semantic-agent-20260827

| Role | Provider | Model | Status | Duration | Tools | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` | `codex` | `gpt-5.6-luna:max` | completed | 17m49s | not separately metered | semantic routing; parent revised strict local contract |
| `worker_02` | `codex` | `gpt-5.6-luna:max` | completed | 16m15s | not separately metered | dual-service launcher |
| `worker_03` | `codex` | `gpt-5.6-luna:max` | completed | 24m24s | not separately metered | route tests and fail-closed probe |

Parent host verification: exact MTPLX model load and strict-schema probe passed after installing the declared `llguidance 1.8.0` dependency. Focused regression: `71 passed, 5 warnings`.
