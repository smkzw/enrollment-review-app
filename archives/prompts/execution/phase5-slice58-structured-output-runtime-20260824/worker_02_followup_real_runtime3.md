Delegated mode. Continue the SAME worker_02 execution session for a fifth bounded remediation pass. Keep the original hard boundaries, authorized files, model `gpt-5.6-luna` effort `max`, and report schema. Do not run final real-project acceptance.

Fresh split-node D001-II full rerun still failed at batch 1/12. Both job attempts produced the same domain errors after one structural repair:

`exists 比较器不接受 value` on multiple predicates in IN-01 and IN-03.

The split predicate/logical node contract solved mixed node fields and eliminated the previous orphan/type failure after bounded repair, but the predicate object still conflates three incompatible comparator shapes. The provider grammar permits `comparator="exists"` and a non-null `value`; prompt repair repeats it because the schema still declares that shape legal.

Extend the same structural-typing principle inside predicate nodes. Do not weaken the authoritative domain validator and do not silently discard a contradictory value:

1. Use explicit comparator-shape arrays in each component, all sharing the same node ID namespace with logical nodes. Recommended wire shapes:
   - `existence_predicate_nodes`: comparator is structurally `exists` (or omitted and hydrated as `exists`); no `value` field is present.
   - `scalar_predicate_nodes`: comparator only `eq/ne/gt/gte/lt/lte`; exactly one scalar value, never an array.
   - `set_predicate_nodes`: comparator only `in/not_in`; a non-empty scalar-values array.
   - `logical_nodes`: unchanged.
   Names may vary if clearer, but the provider schema must make invalid comparator/value combinations impossible without `oneOf`/`anyOf`/`allOf`.

2. Factor shared predicate metadata into code helpers only; do not reintroduce a union in JSON schema. Keep source term/clause(s), applicable population, professional judgment, occurrence/prospective semantics, and time constraint lossless.

3. Hydration merges all four arrays into one graph namespace and preserves duplicate ID, cycle, orphan, shared-child, root, exception and exact round-trip checks. Reject duplicate IDs across any arrays.

4. Keep persisted/domain contracts unchanged. Update the test serializer and prompt/retry wording. Remove obsolete `predicate_nodes` mixed-comparator wording and fields.

5. Add regression coverage:
   - existence node schema has no value/value-list field;
   - scalar node cannot carry list and set node cannot carry scalar;
   - comparator enums are disjoint and hydrate to exact domain comparators;
   - duplicate IDs across all arrays rejected;
   - ALL/ANY/NOT, exception, time constraint, scalar numeric/unit, categorical scalar, and set membership exact round trips;
   - old mixed comparator wire shape rejected, not silently coerced.

6. Keep oMLX temperature 0.0, 8192 cap, bounded retries, batch/source/provenance closure and DeepSeek compatibility. Run focused and full protocol tests, schema validation, compile and diff checks.

Return the complete report to the runner-managed round-five path. Do not introduce D001-specific rules or clinical shortcuts.
