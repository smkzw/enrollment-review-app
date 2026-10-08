Three anchor greps in parallel (reads 1–3 of 8), then targeted body reads.

Reads 4–6: the two new helpers, the updated whole-unit path, and the execution source-seed branch.

Reads 7–8: the actual caller of `_whole_unit_restriction`, and the component-identity function.

8/8 direct reads used (3 anchor greps + 5 targeted reads). Report follows; unverified items are marked.

## Verdict

The delta does what it claims, within the limits below: a clear-source procedure unit whose saved `unresolved` item is **explicitly typed** `target_correspondence` can become wholly non-executable with `consumer_unavailable`; anything untyped or source-flagged stays `interpretation_unresolved`; the mixed-sibling message defect I reported is fixed; and every path I read strips or refuses executable material.

## Typed-cause contract (source_interpretation.py, verified)

- `SourceTargetReviewItem.unresolved_cause: Literal["source_ambiguity","target_correspondence"] | None` with `exclude_if=lambda value: value is None` (863-865) — null/legacy serialization omits it.
- Gate in `validate_source_target_review` (1739-1743): non-`unresolved` decisions carrying a cause → `UNRESOLVED_CAUSE_INVALID`; `target_correspondence` while `statement.unresolved` is truthy → `UNRESOLVED_CAUSE_INVALID` ("来源仍有疑问，不能仅归因于系统对应关系"). Net: a *set* source question cannot be relabeled as a software mapping gap, and the gate is one-directional (`source_ambiguity` is not rejected when the flag is empty — conservative, harmless).
- Prompt contract (1593-1596, JSON template 1626): fill the cause only for `decision=unresolved`; `target_correspondence` only when source meaning is clear with no remaining source question; **"两者不能区分或兼有时填 null，不因早先 unresolved 为空就默认没有新来源疑问"** — this is the owner's stated refusal to treat an empty earlier source question as proof, and the null default routes to `interpretation_unresolved`.

## Restricted path and caller (restricted_source.py, verified)

- `_unit_statements_cover_source` (52-74): one literal-range proof — quotes locate, sorted ranges non-overlap, scope ranges accounted for, `source_statement_ranges_cover_unit(..., allow_joining_punctuation=True)`.
- `procedure_correspondence_source_gaps` (77-94): units whose review has an `unresolved` item, whose disposition is `REQUIRED_PROCEDURE`, and whose statements do **not** cover the unit excerpt. Docstring: that failed mapping "cannot reuse an incomplete source seed … needs a new, bounded source read".
- `_whole_unit_restriction` (365-523): procedure units admitted (410-422); review-decision whitelist for procedure units (426-432); coverage now delegates to the shared proof (434) — same criterion as the preflight, so source-prefix omission refuses here too. `correspondence_only` (472-477) requires for **every** statement in the unit `not statement.unresolved` **and** (review decision != unresolved **or** cause == `target_correspondence`). Message triage (494-501) now distinguishes: temporal; own-unresolved correspondence ("系统尚未证明本条与具体操作或访视的对应关系"); covered sibling ("本条对应关系已有核对，但尚未证明它与同单元未决要求独立") — my mixed-sibling counterexample is addressed; untagged/ambiguous → the old interpretation message. The unit's disposition becomes `RESTRICTED_SOURCE`, candidates for the unit are dropped, and the final `check_protocol_control_batch_candidates` gate remains (521-522).
- Caller `restricted_batch_from_review` (768-806): statement-level path first with definition registration (785-788), then status/outcome/interpretation/review validation (789-802), then `_whole_unit_restriction` (803) with the same registration check (804-805). The whole-unit path is genuinely reachable for the failing shape.

## Execution source-seed branch and component identity (execution.py, verified)

- `_validated_deep_partial_source` (2638-2810): receipt validation precedes anything else — payload hash (2649), route identity (2688-2693), component identity (2694-2695, 2706-2708), prompt hash (2696-2697); the comment at 2719-2721 records that a changed compiler cannot justify reusing executable semantics and may only rederive a wholly non-executable disposition under the current validators. The gap gate (2767-2781) fires only when the saved record has `partial_wire` + `source_target_review` + attempts, last error classes exactly `{"SOURCE_TARGET_REVIEW_UNRESOLVED"}`, `_validate_deep_batch_output(hydrate(...))` passes, and `_resumable_saved_source_review(...).state == "reused"`; if gaps exist → `return None` (this batch gets a fresh read). The seed otherwise strips executable material: `partial_wire=None`, `source_target_review=None`, `source_statement_coverage=[]`, `source_candidate_alignment=None`, `session_id=None` (2782-2788).
- `_deep_component_identity` (1999-2081 read; the `validator_version` join continues past my read): the new tokens are recorded in the **current** identity — `SOURCE_TARGET_REVIEW_GAP_VERSION` and `PROCEDURE_SOURCE_CONTEXT_VERSION` in `validator_version` (2069-2070). No saved hash is rewritten; comparison happens against the current identity, and `obsolete_basis` is computed only when saved vs current `validator_version` differ (2716-2718).

## Challenge answers

1. **Hide damaged receipts as a miss — no path found.** Gap detection runs strictly after hash/route/component/wire/output/review-reuse verification, and a non-empty gap list returns `None` (fresh read), never a silent pass. Damaged receipts fail earlier (raise/state not `reused`), so the gap function is not consulted on them.
2. **Invalidate unaffected successes — scoped, with one unread link.** The gate is bound to this batch (`old_batch` matched by `batch_number` + `_same_deep_batch_material`, 2671-2675) and to the exact failure class; it returns `None` for this batch only, and the comment (2778-2780) states completed siblings revalidate normally. I did **not** read the loop that calls this per batch, so the sibling-scoping is supported by the function's own state, not by reading the caller.
3. **Label a real source uncertainty as software — one-directional gate, documented residual.** Hard-blocked when `statement.unresolved` is set (1741-1743). Residual counterexample: interpretation flag empty, review aspect actually describes a source question, reviewer nevertheless writes `target_correspondence` → gate passes (nothing parses the free-text aspect), the unit becomes `consumer_unavailable`, and research staff are not asked. The prompt (1596) forbids inferring "no ambiguity" from the empty flag and defaults to null, but that is model behavior, not a machine check; the code cannot contradict a confidently wrong cause. No code-level counterexample beyond "the reviewer mislabels"; no free-text classifier proposed.
4. **Release an executable target accidentally — no path found.** The gap branch either refuses (`None`) or returns a seed with wire/review/coverage/alignment stripped (2782-2788); the restricted path drops the unit's links and candidates. Neither route carries an executable claim.

## Unverified / limits

- New procedure-correspondence/source-context **tests were not read** this turn — I spent the last two reads on the `_whole_unit_restriction` caller and `_deep_component_identity` as listed; test pass/fail is not claimed (owner reports tests running separately).
- `_deep_component_identity` read stopped at line 2081; the `validator_version` join tail, `_resumable_saved_source_review`, `_validate_deep_batch_output`, `_same_deep_components_with_current_gate` (prior-session knowledge only), `validate_restricted_definition_consumers`, `source_statement_ranges_cover_unit` internals, and the per-batch caller loop were not read this turn.
- `build_source_target_review_prompt` was seen only for the typed-cause guidance lines (1593-1596, 1626) via context, not in full.
- The private clinical failure is not claimed solved: a refreshed read must still pass the current source, review, and consumer gates; no dates are invented and no approval is copied. This is engineering evidence only, not clinical acceptance.
