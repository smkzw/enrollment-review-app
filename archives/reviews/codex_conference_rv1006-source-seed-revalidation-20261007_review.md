# Source-only replay review disposition

Baseline c55a528e plus four named source/test patches. C03 actual Grok Build/grok-4.7/high, same session2db23ea8-9d1c-4b83-b90f-c6d082b24fea, two end_turn/exit0 passes, no fallback. Initial preflight exit0. Parent quiet120min completion waits. Read-only engineering advice, no clinical originals, credentials, databases, model calls or tests execution assigned. Tool count unknown, not0.

## Findings and Owner Decisions

- Obsolete wire semantic gate ran before source-only replay. Adopted: structurally invalid wire hard-fails, obsolete semantic author output is discarded without being reused. Current source replay remains tied to frozen material and actual raw hash.
- Missing second correction trigger. Adopted: producer saves code/index/refs on every correction, replay validates each trigger and integer sequence. Legacy first correction can use initial failure detail; second missing witness does not reuse. Do not fabricate historical provenance.
- Validator-only failed partial changes previously retained author material. Adopted: full component comparison for failed partial source-only route. Completed-source current full-gate revalidation unchanged.
- In-place retry remains identity-frozen by owner decision. Engine changes require versioned new Job with preflight; not expanded to mutate old terminal runs.
- Final adviser identified an assertion copied into a single-correction test. Owner corrected it and added actual producer→SQLite checkpoint→new Job preflight→source-only Runner recovery. Missing target review remains a precise failed_final state, not success.

## Evidence and Limits

Five connected original modules1125passed/135.97s/exit0/5third-partySWIGwarnings. Early targeted failures are owner synthetic-fixture errors (mocked fingerprint lookup, missing direct time/function, missing review service), not clinical defects or dismissed old fixtures. Wrong module path exit4 and private audit missing PYTHONPATH exit1 retained as owner execution mistakes. Overlapping windows not additive.

Actual32ec checkpoint readonly:17 source points, SHA6cb48727e131c9ee3f4d2512e64c088c188113a8626ad60fbe77c5adf4e5bc73, second correction historical trigger absent, source replay not proved. No new model call, no clinical DB write, old DB hash/state unchanged. Local private audit referenced in current review_index is not externally readable.

This closes software replay correctness within tested boundaries, NOT current clinical recovery, complete source adoption, rule publication or a new case report. Shared regimen/execution relationship and duration/definition consumers remain unresolved and are not adviser-approved.
