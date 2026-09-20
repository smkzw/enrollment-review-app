Delegated mode. Continue the SAME worker_02 execution session for a fourth bounded remediation pass. Keep all original hard boundaries, authorized files, model `gpt-5.6-luna` effort `max`, and report schema. Do not run final real-project acceptance.

Fresh D001-II rerun 2 produced decisive evidence:

- Job attempt 1: both oMLX calls ended `finish_reason=length` at 8,192 tokens (526.9s and 519.6s). No JSON was accepted.
- Job attempt 2: first call completed normally at 2,972 tokens, but hydration rejected `predicate node 结构无效：n1-icf-voluntary`; its bounded structural repair returned 2,632 tokens but remained invalid.
- This reveals that the shared `nodes[]` item schema still conflates two tagged variants. Because it avoids `oneOf`, the schema permits predicate nodes to also carry logical `operator` and logical nodes to carry predicate/time fields. The parser rejects these combinations, but the provider grammar cannot prevent them. Ignoring semantically populated conflicting fields would weaken the contract.

Redesign the wire expression graph so structural typing is unambiguous without recursive unions or `oneOf`/`anyOf`:

1. Replace the mixed `nodes` array in the provider wire schema with two explicit arrays in each component, e.g. `predicate_nodes` and `logical_nodes` (names may differ if clearer).
   - Predicate node schema contains only `node_id`, a non-null predicate object, and optional/null time constraint. It must not expose logical operator/children.
   - Logical node schema contains only `node_id`, non-null operator, and child IDs. It must not expose predicate/time fields.
   - Require both arrays if that helps strict schema; allow an empty logical array for a single atomic predicate. At least one predicate node is required.
   - `root_node_id` and optional `exception_root_node_id` continue to reference the combined unique ID namespace.

2. Hydration must combine both arrays into one lookup, retain duplicate/cycle/orphan/shared-child checks, and reconstruct the exact existing recursive domain model. Reject duplicate IDs across the two arrays. Do not silently ignore contradictory fields from the old mixed representation.

3. The wire serializer used by tests must emit the new split form. Backward compatibility for persisted/domain contracts is mandatory; compatibility for the unpublished failed wire shape is unnecessary unless keeping a strict parser fallback is trivial and cannot reintroduce ambiguity.

4. Remove any obsolete mixed-node schema/prompt language and update prompt/retry text to name the split representation. Keep candidate/repair schemas below the prior ~5.8K size if feasible.

5. Set oMLX compact-generation temperature to deterministic `0.0` while keeping DeepSeek behavior unchanged. This real run showed the same prompt alternated between pathological 8,192-token repetition and a 2,972-token complete result; strict structured extraction should not add sampling variance.

6. Add targeted regressions:
   - schema has separate predicate/logical arrays and no mixed node object;
   - predicate node cannot carry operator/children by schema;
   - logical node cannot carry predicate/time fields;
   - duplicate IDs across arrays, cycles, orphans, shared children rejected;
   - representative ALL/ANY/NOT + exception + time constraint exact round trip;
   - oMLX temperature 0.0 and DeepSeek request options unchanged.

Run focused protocol tests, full protocol tests if feasible, schema validation, compile, and diff checks. Return the complete report to the runner-managed round-four path. Do not weaken domain validation, source closure, official numbering, phase identity, or deterministic gates.
