Acknowledging my earlier report's error up front, then completing the assigned reads (4 of 6 used this turn).

# Findings: R1 implementation boundary for unresolved required-procedure correspondence

**Correction first.** My previous conference line asserted through a delegated test-audit that `_restricted_statement_batch_from_review` did not exist and there was no symbol-level confirmation. That assertion was wrong: `protocol_control_restricted_source.py:504` is `_restricted_statement_batch_from_review`, and `720` is `restricted_batch_from_review`. What went wrong: I treated the delegated Test-Audit agent's phrase "no such symbol in the test file" as a statement about the module, and I did not spend one of my remaining reads to verify it directly. The test file indeed never calls the private function directly; that is a statement about the tests, not about the module. I am correcting the record and replacing the inventory with the actual implementation reads below.

**Evidence basis for this report.** Direct reads of `app/services/protocol_control_restricted_source.py` lines 319-378, 379-478, 504-574, 576-650, 651-717; `app/services/protocol_control_execution.py` lines 4145-4219; `app/agents/protocol_control_source_interpretation.py` lines 1749-1808. `restricted_batch_from_review` lines 720-758 and `_whole_unit_restriction`'s post-lock steps were read at the start of the previous turn and are consistent with the above; the source-target-review time/frequency guards at 1995-2030 are *not* independently verified by me this session.

## 1. Why the two-statement unit cannot use R1 today (verified)

The whole-unit path is reachable for exactly your error class — `set(result.attempts[-1].error_classes) not in ({"SOURCE_TARGET_REVIEW_UNRESOLVED"}, {"TEMPORAL_SCOPE_UNRESOLVED"})` → `return None` (lines 333-336), so a pure `SOURCE_TARGET_REVIEW_UNRESOLVED` attempt enters. Then it locks on three requirements:

| Step | Line | What it requires |
|---|---|---|
| Entry | 330 | `result.partial_wire is not None` (your wire exists — ok) |
| Multi-statement | 363-364 | `if not any(len(by_unit[unit_id]) > 1 for unit_id in restricted_units): return None` |
| Uncertainty | 353-355 | every `unresolved` review item must carry `unresolved_aspects` |
| Disposition | 369 | `dispositions[unit_id].disposition != OTHER_CONTROL_CANDIDATE → return None` ← **the block for the owner's case** |
| Decomposition | 371-398 | quotes locate, are pairwise non-overlapping, and `source_statement_ranges_cover_unit(..., allow_joining_punctuation=True)` |

Your two-statement unit satisfies the meta-shape (multi-statement, full verbatim coverage) but its disposition is `REQUIRED_PROCEDURE`, so line 369 refuses. Note the restricted-statement construction (445-460) keeps `source_quote`, full `source_span_ids`, `scope_quote`, `time_words`, `exception_words`, `affected_stage`, `decision_functions`, `source_force`, and `limitation_kind = interpretation_unresolved` — exactly the "non-executable, no coverage claim" shape you want.

The statement-level path also cannot serve it: its per-unit fallback (599-607) requires, for a single-statement unit, either `interpretation.statements[index].unresolved` or temporal membership; your source has no `unresolved`. And its independent-index branch (631-636) requires a present `target_id` inside the linked ids whenever the disposition is `REQUIRED_PROCEDURE` — so an unresolved mapping with no target cannot pass there either.

## 2. The single-statement recommended unit (verified: no faithful route exists)

Two independent locks:

- Whole-unit: line 363 rejects because the unit has only one statement (regardless of disposition).
- Statement-level: lines 600-605 reject because `statement.unresolved` is false **and** the quote that does not cover the excerpt is accepted only by the temporal branch, which additionally demands `quoted_text == units[unit_id].excerpt`.

There is a further structural point: the restricted-statement constructor (666-686) always records `source_span_ids = sorted(unit.source_span_ids)` — the full unit spans — while `source_quote` may be a proper sub-range. The containment between quote and spans is **not** enforced at construction. For the two-statement case the quote coverage is proven by the 394-398 range union, so full spans are honest. For your single-statement case they would not be: restricted spans would assert the statement covers the whole unit while its verbatim quote covers only part. That is exactly the "dropping full-source range checks" move you ruled out, and it would also put the unit's leftover source text outside every restricted statement. The example makes the failure concrete: a recommended action ("take at approximately the same time") whose quote does not cover its unit cannot claim full-unit coverage, and `recommended` force is additionally excluded from `native_schedule_visit_scope_is_preserved` (force whitelist `required`/`descriptive`), so the native executable route is closed for it too.

**Conclusion:** expanding the disposition enum is indeed insufficient, and the single-statement case must stay unretained until Codex decides a capability that can honestly carry a partially quoted unit. Retaining it by manufacturing `source.unresolved` would write a medical ambiguity into the source record, which the contract forbids.

## 3. Minimum necessary action (bounded, no guard weakened)

One change, inside `_whole_unit_restriction` only, and only for units whose every review decision is an unproved-mapping item:

- Replace the blanket `!= OTHER_CONTROL_CANDIDATE → return None` (line 369) with: accept `OTHER_CONTROL_CANDIDATE` **or** `REQUIRED_PROCEDURE` **only when** (a) every review item for the unit is `unresolved` (or in the already-whitelisted non-closure decisions at 417-421), (b) no review item for the unit names a `target_id` covered by the disposition's linked ids, and (c) the linked procedure targets' frozen excerpts remain untouched. Everything else — offsets, disjointness, range-cover, candidate removal discipline (422-431), `unresolved_aspects` requirement (353-355), and the final `check_protocol_control_batch_candidates` refusal (473-475) — runs unchanged.
- Result: the unit becomes `RESTRICTED_SOURCE` with `limited` statements and no `independent_scope_proof`; the linked procedure is *not* claimed as covering. No coverage, frequency, or visit guard is touched, and the frequency-only / shared-visit guards in `validate_source_target_review` (1995-2030) are out of scope of this change.

## 4. Decisive positive / negative / consumer checks

**Positive (must produce restricted output):** the owner's two-statement unit — full-coverage verbatim quotes, disjoint ranges, `unresolved` review items with `unresolved_aspects`, wire disposition `REQUIRED_PROCEDURE` with linked target ids, attempt error class exactly `SOURCE_TARGET_REVIEW_UNRESOLVED` → `restricted_batch_from_review` returns an output whose unit is `RESTRICTED_SOURCE`, `candidates` emptied for it, `independent_scope_proof is None`, and `limitation_kind == "interpretation_unresolved"`.

**Negatives (must still return None / fail):** a review item that actually names the linked `target_id` (that is a coverage claim → keep the 631-636 refusal); `unresolved_aspects` empty; any `covered_by_*` decision; quote ranges that overlap or leave a gap (`source_statement_ranges_cover_unit` false); a candidate retained for the restricted unit or intersecting its spans (422-431); error classes other than the two accepted sets (333-336); schema/transport damage (`publication_invalid` precondition at 521-529 plus `validate_source_interpretation`/`validate_source_target_review` at 530-539). The single-statement partial-coverage unit must remain `None` in this change.

**Consumer checks required before landing:** `protocol_control_execution.py` gates on the restricted result at 4162-4169; if it returns `None`, the run fails closed with `PROTOCOL_CONTROL_<code>` and `retryable=False` for the source-review codes (4178-4219, `SOURCE_TARGET_REVIEW_UNRESOLVED` at 4194). Saved-batch revalidation must also agree: `restricted_batch_from_review` is re-called on checkpoint rehydrate, `_preserved_unresolved_review_proof`, deep-source rebuild, and definition-registration tail, and any drift raises the corresponding `..._INVALID` step failure. So the positive case must round-trip byte-identically through those consumers, and the new branch must not change output for any existing passing test.

## 5. Limitations / unperformed checks

- I did not independently verify `_temporal_restriction_indexes` beyond its call sites, the frequency-only and `TARGET_VISIT_SCOPE_UNPROVEN` guard bodies this session, `check_protocol_control_batch_candidates`, or `hydrate_protocol_control_agent_output`.
- No tests, product runs, or clinical data; the owner's failing-batch shape (two-statement full-coverage unit + one single-statement partial-coverage recommended unit) is treated as the frozen observation, not gold.
- I did not decide whether the single-statement recommended unit should eventually be retained; that needs an explicit Codex capability decision and an honest way to represent a partially quoted unit.
- Per your statement, no new Trellis task was created for this existing advisory packet, and this review makes no claim of clinical or production acceptance.
