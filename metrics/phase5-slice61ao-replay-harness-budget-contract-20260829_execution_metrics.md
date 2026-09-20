# Execution Metrics: phase5-slice61ao-replay-harness-budget-contract-20260829

| Role | Provider | Model | Status | Duration | Tools | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` primary | `codebuddy-cli` | `glm-5.3-flash:max` | terminal 429 text misclassified by runner | 1.902s | 0 | preserved; declared fallback activated manually |
| `worker_01` fallback | `mtplx` | `mtplx-qwen38-27b-optimized-quality:medium` | completed | 3127.067s | 185 | audit accepted |
| `worker_02` fallback | `mtplx` | `mtplx-qwen38-27b-optimized-quality:medium` | completed | 6657.152s | 429 | implementation revised and accepted by Codex |
| `worker_03` fallback | `mtplx` | `mtplx-qwen38-27b-optimized-quality:medium` | completed | 2298.986s | 166 | budget contract accepted |

The primary rate limit applied to the CodeBuddy provider until its stated reset time. AC power, 128 GB physical memory, and more than 50 GB available memory were verified before using the packet-declared local fallback. No undeclared route was used.
