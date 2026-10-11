我先按指定源码核对两处冻结失败：前件/动作切分是否保住全部语义，以及条件改写被拒的最小修复路径。# Conference Output: rv1006-sequence-and-condition-review-20261011 - evidence_single_object

## Output

The partition repair keeps a uniquely located antecedent string and the action’s registered marks on the clean fixture. It does not prohibit an omitted independent action, and a validator-only replay will not re-apply the correction guards. The paraphrase candidate must stay not `fully_expressed`. Current repeat consumers do not verify that “时” preserves “因检测结果符合某标准的情况”.

### Evidence

**Family 1 — what the clean split actually checks**

`_preceding_sequence_boundary` (`protocol_control_source_interpretation.py` 1002–1011) returns offsets only when `eligibility_sequence == "after_eligibility_decision"`, `eligibility_sequence_context is None`, and both the antecedent quote and the action quote locate uniquely with the antecedent ending at or before the action. `locate_source_quote_offsets` (`protocol_control_gate.py` 5087–5104) returns `None` when the compact quote is missing or occurs twice.

`apply_source_quote_correction` (1014–1087) treats that as a retained antecedent only when the old quote is exactly `[antecedent start, new action end]` and the gap is only whitespace or `，,。；;：:` (1033–1037). On that path, marker, digit, and Chinese-quantity comparison uses the action span, not the antecedent (1038–1072). A `time_words` item may leave the action quote only if it is inside the retained antecedent (1053–1058). `exception_words` may not leave the old quote unless it remains in the new quote (1060–1062); the antecedent is not an exemption. The only field written is `quoted_text` (1077). The following isolated `validate_source_interpretation` drops every other statement, including same-unit siblings (1078–1086).

`validate_source_interpretation` allows a time word that sits only in the antecedent when the boundary still locates (3457–3466). The sequence check itself uses `str.find` on the normalized excerpt (3476–3489), so a repeated antecedent or action is not rejected there. `source_unit_quotes_cover_source` (308–360, especially 329–343) does count a unique antecedent as coverage for that statement and fails on overlap, ambiguity, or leftover words. Neither `apply_source_quote_correction` nor the deconstructor’s post-correction break (`protocol_control_deconstructor.py` 8245–8272) calls it. Completed-result replay calls `validate_source_interpretation` (`protocol_control_execution.py` 3772) and does not call coverage. `_source_interpretation_requires_refresh` (3661–3693) does not inspect partition gaps.

`_same_deep_components_with_current_gate` (2164–2177) treats a validator-only difference as still the same material. `compiler_versions` are compared. Prompt mismatch is a separate `prompt_material_changed` (3527–3528). Replay of `apply_source_quote_correction` from raw attempts happens in `_revalidated_source_seed_proof` (2622–2624), which the failure path enters when components differ (3057–3071), not when only `validator_version` differs. `CONTROL_PUBLICATION_GATE_VERSION` is `phase5/control-publication-gate/v49` (`protocol_control_gate.py` 65). `SOURCE_INTERPRETATION_VERSION` is `phase5/control-source-interpretation/v11`. This pass did not diff `c0deee28`.

The new tests are software fixtures only. `test_quote_partition_preserves_antecedent_without_deleting_action_dimensions` (2656–2698) accepts one clean split and rejects the named faults by any `ValueError`. The clean boundary is `若资格核对符合后`, which itself contains the marker `若`. `extra_action` inserts `必须记录签名`, which contains `必须`. `test_source_inventory_corrects_embedded_eligibility_basis_locally` (2612–2651) keeps `time_words` that include the antecedent. Marker-loss cases are at 2802–2830. Sibling field preservation at 2733–2787 is a spelling repair, not a same-unit partition. The assigned owner window of 67 passes was not re-run here.

Cross-context does not use the exemption: a non-`None` `eligibility_sequence_context` makes `_preceding_sequence_boundary` return `None`. `validate_table_sequence_context` (`control_scope_sources.py` 131–163) rechecks the context witness, table reference, and column objects. It does not prove the boundary contains no second action. `_has_external_attribution_before_action` (169–184) still sees attribution in the same clause after the action quote is shortened, because the clause window is cut on `。！？；;`, not on `，`.

**Family 2 — why this candidate fails, and what the repeat objects actually prove**

`validate_candidate_alignment` builds `rendered` only from selected atoms’ `statement` and `evaluation.proposition` (1024–1029). At 1051–1052, `fully_expressed` fails when normalized `exception_words` is absent from that string. For `因检测结果符合某标准的情况` versus `…符合某标准时…`, that substring check fails. The check runs before repeat-count preservation (1086–1090).

`_statement_grounded_atoms` (421–436) selects atoms from applicability, trigger, obligation, and exception only. A literal source excerpt inside the unit can select an atom whose statement is paraphrased. `repeat_trigger_conditions` are not in that scan, so a side condition cannot satisfy `candidate_atom_quotes` or `rendered`.

`_source_repeat_count_is_preserved` (515–549) can succeed when one current scheme has `maximum_repeats == 2`, spans inside the unit, and a `source_excerpt` equal to the whole source sentence (543–547). `permission == "optional"` is allowed for `force == "descriptive"` (537–539). It does not read `exception_words`, `trigger_excerpt`, or the referenced condition’s proposition.

`RepeatScheme` requires `trigger == "source_condition"` to have a non-empty `trigger_condition_id` and a `trigger_excerpt` contained in `source_excerpts` (`repeat_scheme.py` 171–191). `validate_control_repeat_conditions` (`protocol_controls.py` 1355–1386) and `validate_repeat_trigger_conditions` (`rules.py` 605–620) require the condition id to exist and the condition’s source clauses to be literal substrings of the scheme excerpts. The repeat calculators (`repeat_trigger_calculation.py` 74–104, `control_repeat_trigger_calculation.py` 80–106) evaluate that condition expression and record whether the id is the trigger or the permission reference. They do not compare the expression with `exception_words`.

### Inference

The clean fixture preserves the antecedent as `eligibility_sequence_quote`, keeps antecedent time words, and refuses to drop an exception, digit, Chinese quantity, or protected marker that belongs to the action span. Sibling statement objects are not rewritten. That is source-field preservation for one shaped input. It is not a general prohibition on omitted actions.

An interstitial action with no protected mark, no registered time word, and no exception is outside the gap-strip and outside the marker equality, because the exemption does not apply and the full old quote is compared only for marks that exist. If similarity stays at least 0.75, `apply_source_quote_correction` returns the shortened quote. `validate_source_interpretation` still passes. Coverage would reject the leftover words, but the accept path never calls it. The `extra_action` test rejects `必须` and `若`, so it does not show that a marker-free action is prohibited.

A second action packed inside `eligibility_sequence_quote` is counted as this statement’s antecedent (coverage comment at 338–339) and is not opened as its own statement. The split has no check that the boundary is only a sequence witness.

A repeated antecedent fails the unique locate, so the exemption stays off. The validator’s `find` check can still pass. Time words that live only in the action do not need the unique boundary. A marker-free duplicate can therefore survive validation. Completed-result replay will not reconstruct the correction delta after a validator-only bump. The new time rule is more permissive than a validator that rejected antecedent-only time words. Old acceptance is not re-proved by the correction guards.

For family 2, optional permission, `maximum_repeats == 2`, unchanged source and scope, `trigger_excerpt`, and a live condition id can all be true while the executable obligation sentence says `时`. Citation membership and `fully_expressed` do not identify those strings. Clinical sameness of `情况` and `时` is not established by this excerpt.

### Recommendation

Do not add a recovery route, a synonym table, or another author pass.

1. In `apply_source_quote_correction`, after the quote update, call `source_unit_quotes_cover_source` for every statement of that unit on the full interpretation. Reject the correction when it returns false. Call the same predicate from `_validate_saved_source_review` and set the completed batch to `current_source_review_requires_refresh` on failure. That uses the existing coverage rule against interstitial omissions, sibling overlap, and ambiguous repeats.
2. Keep the boundary exemption only when every protected marker inside the antecedent is in the sequence-connective subset already listed (`若|如果|只有|仅当`). Any other protected marker inside `eligibility_sequence_quote` rejects the split. The clean fixture’s `若` still passes. `必须` or `不得` inside the boundary does not. Do not invent a semantic classifier.
3. Exit evidence is a unit test whose gap is a marker-free independent clause, a test whose extra action sits inside the boundary quote, a duplicate-antecedent test with no protected mark, and a replay fixture whose stored interpretation fails coverage while `validate_source_interpretation` passes. The current fault list does not cover those.

For the paraphrase candidate, keep the alignment rejected. Precise software reason: `exception_words` is not in the rendered obligation `statement` or `proposition`, and the referenced trigger condition’s own `statement` or `proposition` was not shown to contain that literal phrase. `trigger_excerpt` and source excerpts must not satisfy the check.

The later, smaller change is a field check, not an acceptance of this candidate. Resolve `trigger_condition_id` inside this candidate’s `repeat_trigger_conditions`. Require normalized `exception_words` to occur in that condition atom’s `statement` or `evaluation.proposition`. Require `trigger_excerpt` to be that same literal phrase. Only then may the obligation sentence use a different connective. If the condition atom does not literally contain `因检测结果符合某标准的情况`, leave the decision not `fully_expressed`. Do not regenerate the author to invent a wording match.

### Uncertainty

This pass did not execute the owner window, did not diff `c0deee28`, and did not replay a saved gate job. Whether the referenced condition atom already contains the literal exception phrase is not in the assigned materials. `情况` versus `时` remains clinically unjudged. No adoption, clinical, or regulatory acceptance is claimed.

### Objections, decision points, and one question

The highest-impact defect is that omitted independent text survives the correction and the current validator, while coverage already knows how to reject it and is not on the accept or validator-only replay path. The passing window does not close that hole: its extra-action fixture is rejected by `若` and `必须`, not by an uncovered-action rule. A validator bump that leaves compiler and prompt versions unchanged revalidates the stored snapshot with a more permissive time rule. It does not replay the correction guards.

The second defect is treating the repeat scheme as proof of the condition. Count preservation and condition-id resolution are real software capabilities. They prove a count and a linked expression. They do not prove the paraphrase.

Decision for Codex: authorize the coverage call plus the existing-marker boundary limit, and keep this candidate not `fully_expressed` until the condition atom’s own statement or proposition contains the literal exception phrase. Do not authorize acceptance from `trigger_excerpt`, citations, or `fully_expressed`.

Bounded question: what are the exact `statement` and `evaluation.proposition` on the `repeat_trigger_conditions` item whose `condition_id` equals this scheme’s `trigger_condition_id`? If they contain `因检测结果符合某标准的情况`, the field check above is sufficient and the obligation’s `时` can stay. If they contain `时` or only a citation, the candidate stays not `fully_expressed` with no author regeneration. Provisional path either way: do not mark this pair `fully_expressed` in the current code.

### Read limits

Read in full for the affected definitions: the quote-correction and validator sections, coverage, alignment through the numeric continuation, `RepeatScheme`, and the named tests. Additional direct consumers read for this decision: deconstructor quote-correction loop, execution replay and component identity, `validate_control_repeat_conditions`, `validate_repeat_trigger_conditions`, both repeat-trigger calculators, and `validate_table_sequence_context`. No clinical files, database, model calls, web, tests, or writes. Conference reports were not used as evidence.
