# Execution Metrics: phase5-slice59l-20260827

| Role | Provider | Model | Status | Duration | Tools | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` | `cursor-cli` | `auto` | accepted | 203.887s | recorded in runner log | shared longer-of contract |
| `worker_02` | `cursor-cli` | `auto` | accepted after same-session repair | 515.578s | recorded in runner log | condition-to-alternative-obligation binding |
| `worker_03` | `cursor-cli` | `auto` | rejected for completion claim | 557.699s | recorded in runner log | deterministic gate replay only; no product MTPLX Agent call |

Declared worker route was `pi/mtplx/mtplx-qwen38-27b-optimized-quality`;
the runner's resource gate selected `cursor/cursor-cli/auto`. This route fact
does not change the product-level requirement to call the built-in MTPLX Agent.
