# Execution Metrics: phase1_5_uat_recorder

| Role | Provider | Model | Status | Duration | Tools | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` | `opencode-go` | `deepseek-v4-pro` | completed, corrected by Codex | 2061s | enabled | core delivered; five semantic defects corrected before UI integration |
| `worker_02` | `opencode-go` | `deepseek-v4-pro` | completed | 2689s | enabled | static recorder UI and launcher extension delivered |
| `worker_03` | `opencode-go` | `deepseek-v4-pro` | completed after same-session recovery | 2 recovery rounds, 983s | enabled | first response was empty delivery; recovery produced E2E, screenshots and guides |
| `visual_manager_cursor` | `cursor-cli` | `auto` | accepted | 102s | enabled | isolated disk and test review; no worker rerun required |

Declared Alibaba routes were replaced by the daytime Beijing route policy before dispatch; no fallback occurred. Durations are runner-recorded wall times and are not model latency benchmarks.
