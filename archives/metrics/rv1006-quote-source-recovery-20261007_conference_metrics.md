# Conference Metrics: rv1006-quote-source-recovery-20261007

Date: 2026-10-07

| Role | Provider | Model | Status | Duration | API calls | Tokens | Result |
|---|---|---|---|---:|---:|---:|---|
| `evidence_single_object` | `codebuddy-cli` | `deepseek-v4.1-flash/max` | completed / exit0 | 200.521s | unknown | unknown | 14 read/search calls; source-only review |

## Timeout And Retry Evidence

Health probe exit0/5.959s; no fallback, no redispatch. Session 01a1160f-39c6-7882-bd4c-2cf8f5f2ec45. Parent used a 120-minute completion wait and remained quiet until completion. Runner reports 14 tool-call starts and 0 parsed tool-result events; the report quotes actual source definitions, not independently executed tests. Character-derived token estimates are not actual usage. Raw stdout contains private reasoning and is not included in the source delivery.

## Quality Decision

Confirmed missing quote-correction trigger receipts and the scope-only replay gap. Rejected identity-only recovery. Owner used the actual SourceQuoteCorrection contract (corrected_quote/structure_unit_id), added producer receipts and bounded replay, and retained refusal of historical missing triggers. Same-component semantic-wire failure may discard downstream output only after the same actual-response proof passes; damaged structural wire still fails before that branch. Review was against 9d4f94c4 before the patch; final integration and regression are the owner's responsibility. Fresh context is procedural independence, not an independent clinical model gold standard.
