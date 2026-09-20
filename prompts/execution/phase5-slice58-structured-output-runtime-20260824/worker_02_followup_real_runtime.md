Delegated mode. Continue the SAME worker_02 execution session for a third bounded remediation pass. Keep the original hard boundaries, authorized files, model `gpt-5.6-luna` effort `max`, and report schema. Do not run final real-project acceptance.

Codex ran a fresh isolated real D001-II browser flow against the round-two implementation. It failed after 31 minutes in `generate_draft`, first batch 1/12. This is new decisive runtime evidence:

- oMLX request 1: prompt 2,822 tokens, generated exactly 16,000 tokens in 1,038 seconds, `finish_reason=length`, JSON validation failed.
- bounded retry returned 1,795 tokens in 118 seconds.
- semantic hydration rejected repeated fields such as `predicate.unit_match_policy=null` and `time_constraint.direction=null`; the domain requires `unit_match_policy="exact_canonical_label"`, and any actual `TimeConstraint` requires non-null anchor/direction.
- the structural repair response still repeated these invalid nullable placeholders; the job-level retry repeated the same class and ended `SEMANTIC_DRAFT_MISSING`.
- The wire schema is ~7,018 JSON chars and the batch prompt is already compact. The root defect is the wire contract's nullable-placeholder design plus unbounded generation behavior, not the frozen source size.

Repair the root contract without weakening authoritative domain validation:

1. Nullable object means object-or-absent semantic, not an object full of null placeholders.
   - For `_wire_time_constraint_schema`, when the value is an object, `anchor_type` and `direction` must be non-null valid enum values; `allow_partial_date` must be a boolean. Bounds may remain nullable.
   - For `_wire_time_quantity_schema`, when object, `value` must be a positive integer and `unit` a non-null valid enum.
   - Apply the same principle to occurrence/prospective windows and prospective periods: if the outer object exists, its semantically required members must be non-null.
   - Predicate objects used by predicate nodes must have non-null `predicate_id`, `subject`, `attribute`, and comparator. Logical nodes may still carry `predicate=null`.

2. Do not ask the model to emit domain constants/default-only fields.
   - Remove `unit_match_policy` from the wire predicate schema and hydrate it deterministically as `exact_canonical_label`.
   - For default-only booleans, either require real booleans in the wire or deterministically hydrate omitted/nullable placeholders only where omission has no semantic ambiguity. Never coerce a genuinely partial time window into a valid window.

3. Defensive hydration.
   - An all-null optional nested object from a legacy/fake response may normalize to `None` only if it carries zero semantic content.
   - A partially populated object missing a required semantic field must remain rejected with a precise error.
   - Add tests for all-null normalization, partial-object rejection, and exact domain round trip.

4. Prevent pathological first-batch output from consuming 16K tokens.
   - Reduce the default oMLX per-batch output ceiling to the smallest evidence-supported value that safely accommodates 1-3 clinical parent rules; use 8,192 unless focused fixtures prove it too small. Keep DeepSeek unchanged.
   - Strengthen the compact prompt and the `finish_reason=length` retry instruction to forbid duplicate nodes/components/source excerpts and demand the smallest complete graph for exactly the requested parent rules.
   - Do not reintroduce an arbitrary wire-only 128-node semantic limit. If you use any operational collection cap, it must fail explicitly as an operational limit and be tested, not silently truncate a valid domain rule.

5. Tests and evidence.
   - Add regression tests reproducing the exact nullable-placeholder failures reported above.
   - Prove compact schema objects have non-null required inner semantics and no `unit_match_policy` field.
   - Prove default oMLX max tokens is now bounded at the selected value while DeepSeek behavior remains unchanged.
   - Run focused protocol tests, complete non-rendering protocol regressions if feasible, compile, and diff checks.

Read the current runtime evidence in the job database only if needed; do not touch or reuse clinical source files. Return the full execution report to the round-three report path managed by the runner.
