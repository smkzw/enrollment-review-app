# Conference Metrics: enrollment-rv1001-target-scope-cause-20261006

Date: 2026-10-06

| Role | Provider | Model | Status | Duration | API calls | Tokens | Result |
|---|---|---|---|---:|---:|---:|---|
| `evidence_single_object` | `codebuddy-cli` | `deepseek-v4.1-flash` / max | terminal success, no fallback | 631.697 s | runner invocation 1; underlying API calls unknown | unknown | diagnostic advice, not clinical adoption |

## Timeout And Retry Evidence

Native CLI session 01a111b7-e359-7e14-8dea-84f0a80805ac; runner exit 0, no timeout. One 7200-second completion wait, owner silent while running. Six tool starts, zero parsed tool-result events and 24 events in the runner receipt; missing parsed results are not evidence of zero tool work. No unchanged retry or additional round dispatched.

## Quality Decision

Owner accepts the day-time/visit-scope distinction and conditional false-positive diagnosis, not the unsupported inference that absent scope means all applicable visits. Four frozen packet files bounded context; regex constants and full downstream coverage contract were not part of this review. Relative speed and token savings were not measured against a same-route comparator.
