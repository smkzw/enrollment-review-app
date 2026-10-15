# Conference Metrics: rv1006-source-purpose-route-20261006

Date: 2026-10-06. Durations below are runner receipt durations, not parent wait times.

| Role | Provider | Model | Status | Duration | API calls | Tokens | Result |
|---|---|---|---|---:|---:|---:|---|
| `evidence_single_object` / first round | `codebuddy-cli` | `deepseek-v4.1-flash:max` | terminal exit0 | 279.14s | unknown internal API count | unknown billable tokens | source defects identified |
| same session / final boundary | `codebuddy-cli` | `deepseek-v4.1-flash:max` | terminal exit0 | 54.397s | unknown internal API count | unknown billable tokens | c067 frozen diff reviewed; heading gap found |

## Timeout And Retry Evidence

120-minute completion waits, no timeout/fallback/redispatch. Session 01a112c5-47cc-7bba-a894-cebf043f6b35 continued, not an independent second model opinion. First preflight failed due to malformed read-set declarations but launch proceeded erroneously; final preflight passed. Raw receipts retained locally, not committed. Huge source/test files expanded first-round context; final round used a frozen narrow diff rather than rereading the whole file. Aggregate CLI usage must not be reported as product API cost.

## Quality Decision

Owner accepted F1/F2; did not accept F3 single-guard widening as a complete mixed-batch consumer. Final heading-only fix and 1103 connected tests are owner evidence after the review. Product diagnostic was separate: two calls/17.6214s/zero DB writes, not clinical acceptance.
