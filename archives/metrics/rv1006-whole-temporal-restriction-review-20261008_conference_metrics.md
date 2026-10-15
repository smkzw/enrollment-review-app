# Conference Metrics: rv1006-whole-temporal-restriction-review-20261008

Date: 2026-10-08

| Role | Provider | Model | Status | Duration | API calls | Tokens | Result |
|---|---|---|---|---:|---:|---:|---|
| initial | codebuddy-cli | deepseek-v4.1-flash/max | exit0, incomplete | 267.503s | unknown | unknown | 16 tool calls; only startup/read narration, owner rejected |
| same-session completion | codebuddy-cli | deepseek-v4.1-flash/max | exit0, report obtained | 33.048s | unknown | unknown | findings delivered without redispatch or fallback |
| same-session recovery review | codebuddy-cli | deepseek-v4.1-flash/max | exit0, report obtained | 169.987s | unknown | unknown | 8 targeted reads, concrete witness/rehydration findings |

## Timeout And Retry Evidence

Approved C03 packet and session 01a118e4-5bb1-7429-afb2-979d2412fe80. All three passes used completion waits bounded at 7200s; owner silent during conference execution, no healthy redispatch, no fallback. Duration comes from runner receipts, not the last shell poll. Raw receipts remain in logs/conference/rv1006-whole-temporal-restriction-review-20261008. The runner emits tool_result_count=0 despite tool-call events; do not infer no file reads or invent token usage.

## Quality Decision

Owner adopted the first report's recovery-causality finding and the second report's typed-witness and private-answer restoration hardening. The second report's crash example omitted a source-unresolved precondition; it is a conditional failure family, not evidence that the natural product response crashed. Both gate/wire validation exceptions are ValueError subclasses; take_call_receipts clears its thread-local list, so this pass's receipts are not historical accumulation. A separate temporal fallback code was not added: a current typed proof already requires a valid rederived restriction, and the existing producer/Runner error identity is retained.

419 connected synthetic tests passed in 95.54s after owner fixes. The reviewer did not run tests, read the final tiny hardening patch, inspect clinical material, establish global definition scope, or approve clinical adoption. Initial output remains incomplete even though its process exited0. Full owner disposition and code hashes are in the task review note.
