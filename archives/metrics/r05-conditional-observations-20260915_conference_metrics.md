# Conference Metrics: r05-conditional-observations-20260915

Date: 2026-09-15

| Role | Provider | Model | Status | Duration | API calls | Tokens | Result |
|---|---|---|---|---:|---:|---:|---|
| `evidence_single_object` | `zcode` | `GLM-5.3 max` | exit 0 | 613.095 s | unknown | unknown | source findings; revised |
| same-session followup | `zcode` | `GLM-5.3 max` | exit 0 | 514.203 s | unknown | unknown | corrected design; partly adopted |
| same-session period integration | `zcode` | `GLM-5.3 max` | exit 0 | 586.200 s | unknown | unknown | D1-D3 corrected by owner |

## Timeout And Retry Evidence

Runner timeout 7200 seconds each; completion observed through bounded long waits. No redispatch of active session, no fallback; same session retained for directed revision. Health probe 0.455 s is not included as clinical/model inference time. Tokens and API costs not estimated from wall time.

## Quality Decision

Source review only. Narrow current control-period implementation and official guard passed static compilation, not runtime/clinical acceptance. Larger retest/occurrence/official prospective paths remain open. No product-model calls were made; conference timings do not measure product harness performance.
