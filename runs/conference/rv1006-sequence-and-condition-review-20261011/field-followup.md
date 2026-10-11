我按当前代码复核两处改动：同单元覆盖是否只证明摘录捕获，以及命题修补是否会绕过例外门、证明失效和兄弟冻结。The second pass stays read-only. I will re-read the current bind, proof, transport, and splice paths before judging whether a changed proposition can be accepted by an old proof or a statement-only check.The exception gate is unchanged and still rejects the paraphrase. A changed proposition is not accepted by an old proof. A statement-only citation can still leave extra words in that proposition unexamined, and a legacy sequence gap now fails closed with a wider blast radius than the existing refresh path.

# Conference Output: rv1006-sequence-and-condition-review-20261011 - evidence_single_object

## Output

Read-only review of the current worktree. No implementation, test run, or clinical acceptance. The three new tests are synthetic software evidence only.

### Findings

1. A repaired proposition can pass while the fresh review still cites only the frozen statement. This is the acceptance gap.

`validate_candidate_alignment` still builds `rendered` from each selected atom’s `statement` and `evaluation.proposition`, and a missing literal `exception_words` still raises `CandidatePropositionAlignmentError` with reason `source_condition_unrepresented`. That class does not approve anything. `app/agents/protocol_control_candidate_alignment.py` lines 38–52 and 1041–1071.

The conjunction loop above it can skip on a statement or source excerpt alone. If a frozen `source_excerpt` contains the whole source sentence, the loop `continue`s at lines 1017–1020 and never reads the proposition. The synthetic material does this: the excerpt is `出现异常的情况，记录结果` while the statement and proposition are `出现异常时记录结果`. The exception gate still fails. Citations and counts remain insufficient.

After `proposition_only` splice, those frozen fields stay put. The fresh prompt’s `allowed_candidate_atom_quotes` is built only from `atom.statement` (lines 605–608). The alignment item may keep citing the paraphrase. Selection still matches because the quote occurs in the statement (lines 988–994). The gate then passes as soon as the new proposition contains the condition phrase. Nothing requires the rest of the proposition to be the old proposition or a span of the frozen excerpt. The prompt at `protocol_control_deconstructor.py` lines 7233–7236 says not to add facts; the host does not enforce that sentence.

An old proof cannot paper over this. `_alignment_input_identity` hashes the full candidate dump, including `evaluation.proposition` (`candidate_alignment.py` lines 671–721). `reusable_proven_alignment_items` (lines 811–852) also reruns `validate_candidate_alignment`. A changed proposition misses the old `candidate_sha256`. An unchanged paraphrase still fails the current gate, so its old `fully_expressed` proof is dropped too. A passing fresh item gets a new hash. The hash change proves identity changed. It does not prove the new proposition has no added claim.

2. The condition repair is one existing atom call, and the failure paths stay on the pre-splice draft.

`bind_partial_candidate_alignment` writes `statement_ids: [item.statement_index]` and then spreads `error_detail`, which does not contain `statement_ids` (`candidate_alignment.py` lines 780–790). Dispatch therefore sees one statement. `proposition_only` is true only when that single failure’s reason is `source_condition_unrepresented` and `atom_paths` has length 1 (`deconstructor.py` lines 10510–10521). The outer guard also requires that statement to be in `cited_unexpressed`, a live `continue_atom`, and repair budget remaining (lines 10526–10530). `patch_reader` is `None`, so the provider schema stays `protocol_control_atom_repair_v1`, the full atom object (`deconstructor.py` lines 1789–1815; `continue_atom` at `protocol_control_agent_transport.py` lines 1697–1752). A session change raises before merge (line 10550).

`_merge_obligation_atom_repair(..., proposition_only=True)` replaces one atom on a deepcopy. It rejects changes to kind, statement, modality, temporal scope, both source fields, professional-judgment, prospective period, continuing obligation, `time_constraint`, and every evaluation field except `proposition` (lines 7165–7200). Sibling atoms and other candidates are untouched. The other merge and prompt call sites, lines 8786 and 11969, do not pass `proposition_only`. They are the older structural atom repair, not this branch.

The path is added to `reviewed_atom_repairs` before the call (lines 10533–10534). A later failure of the same path does not call the model again. Two condition failures, two atom paths, or a mix with `repeat_scheme_missing` / `numeric_predicate_missing` leave `len(numeric_failures) != 1`, force `semantic_repair` to `None` while alignment failures exist (lines 10596–10600), and stop at `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED`.

On a clean merge the runner stores the pre-splice wire, coverage, alignment, and target review, then continues the main loop (lines 10576–10583). Publication still depends on the full gate and a new alignment read. If `final_output` stays `None`, `build_result` puts that baseline back (lines 7712–7716). Invalid and escape replies raise `ATOM_REPAIR_INVALID` inside the merge `try`, before the baseline is stored, and return the pre-splice wire (lines 10556–10569). The ledger detail keeps `automatic_adoption: false` and the original `source_condition_unrepresented` reason. A `parsed` repair receipt is not an acceptance record.

“Exactly one obligation path” is implemented as one selected atom path. An independent group that this alignment item does not select does not increment `atom_paths` (`_independent_source_obligation_groups`, lines 457–517). The synthetic fixture has one group, so the test does not exercise that shape.

3. Full same-unit capture is now on the partition success path and on saved review. It proves located, non-overlapping coverage, not that the antecedent is only an antecedent.

`apply_source_quote_correction` grants the boundary exemption only when the old span is exactly the antecedent start through the new action end and the gap is punctuation (`source_interpretation.py` lines 1033–1037). A retained antecedent may contain only `若`, `如果`, `只有`, and `仅当` among protected marks (lines 1048–1050). Any other span change on `after_eligibility_decision` raises `先决与动作分区未完整保留中间来源` (lines 1051–1055), including cross-context statements, because those statements do not receive a boundary. When a boundary is retained, `source_unit_quotes_cover_source` must cover every statement in the unit (lines 1086–1089). The coverage helper says the antecedent count does not assign that text to another statement (lines 338–339).

`_validate_saved_source_review` applies the same full-unit check to every unit that has a context-free `after_eligibility_decision` statement (execution.py lines 3775–3783). Cross-context statements are outside that set. `_revalidated_source_seed_proof` replays `apply_source_quote_correction` (lines 2622–2624), so the new guards run on that replay. `_source_interpretation_requires_refresh` (lines 3661–3693) still does not look for a partition gap. The saved-review call is what closes a completed non-restricted result.

The marker-free interstitial fixture `记录签名` is rejected. `action_in_boundary` is rejected because that fixture contains `必须`, which the mark list catches. A marker-free action written inside `eligibility_sequence_quote` is still only a capture check. Unanchored `不`, `未`, `无`, `应`, and `须` can reject an ordinary antecedent that merely contains those characters. A same-length spelling repair can still pass. A length-changing repair on any `after_eligibility_decision` statement now fails even when it does not drop text between antecedent and action.

4. Two resume consumers do not treat the new capture failure as the refresh they already use for typed review errors.

The new message is a bare `ValueError`. `_preflight_deep_source` catches only `SourceInterpretationValidationError`, `SourceTargetReviewValidationError`, and `SourceCandidateAlignmentValidationError` (execution.py lines 3578–3582). The same trio is caught at lines 4006–4010, where a typed failure returns no checkpoint. A sequence gap therefore leaves the planner instead of setting `refresh_required`, and the lookup’s outer handler turns it into `PROTOCOL_CONTROL_DEEP_SOURCE_INVALID`. The gap is not reused. Sibling batches in that preflight share the abort.

Restricted checkpoints never call `_validate_saved_source_review` (lines 1288–1293, 3557–3574, 3993–4001, and 5411–5427). `_same_deep_components_with_current_gate` treats a validator-only difference as the same identity (lines 2164–2177). A restricted result can stay reusable across this validator change without the new capture check. This review did not re-open `restricted_batch_from_review`, so it does not claim the restricted object itself stores the antecedent quote.

The proposition fixture has no `after_eligibility_decision` statement. `test_source_condition_repair_uses_existing_atom_path_and_fresh_saved_review` does call `_validate_saved_source_review`, and that call does not enter the new sequence branch.

### Statement-only check and unchanged replies

A statement-only check does not validate the unrepaired paraphrase. The excerpt can contain the full sentence, and the cited quote can be the statement, while lines 1068–1071 still reject the missing condition.

That same statement-only path can leave a changed proposition unexamined beyond the substring. The statement, excerpts, and citable quotes stay frozen. The atom stays selected. The gate passes when the new proposition contains the condition, including when it also contains other claims. The fresh call is real, and the old hash does not match. The structured review item does not have to name the new proposition because the allow-list is statement-only.

Unchanged replies stay bounded. An equal proposition merges, the fresh gate fails again, and the path cannot be repaired twice. `build_result` restores the pre-splice draft when nothing is published. A reply that changes any other frozen field, or adds a sibling key, fails in the merge and never continues. The synthetic test records one `continue_atom`, no `continue_session`, no `start_source_insert`, and `final_output is None` with `partial_wire == wire` for `unchanged` and `escape`. That bounds this control flow. It is not a clinical bound.

### Objections

The implementation matches the owner’s narrower claim: capture is checked, the substring gate was not relaxed, and the splice can change only `evaluation.proposition` on one atom path. It does not make the fresh review a review of the proposition text, and it does not make a legacy sequence gap follow the existing per-batch refresh.

### Smallest correction

Keep this repair family. In the existing `proposition_only` branch, reject a changed proposition unless its normalized text occurs inside one source excerpt already frozen on that same atom. The valid synthetic reply is exactly that excerpt, so it still passes. Added words fail before the second alignment. Unchanged replies can keep today’s fail-and-restore path.

Separately, raise the existing capture failure as `SourceInterpretationValidationError`. The preflight and checkpoint lookup already catch that type and refresh. Adoption and checkpoint validation already catch `ValueError`, so they stay fail-closed. No new recovery method, schema, provider, or clinical rule.

### Decision points

Adopt the excerpt-containment predicate if a proposition that merely contains the condition must not add words. Leave it to the fresh model call only if the chair accepts that the structured citation will still be the old statement.

Adopt the typed capture error if one legacy gap should refresh that batch. Leave the bare `ValueError` if an abort of the whole preflight is the intended fail-closed result.

### Bounded question

Should a restricted-batch checkpoint be required to pass `_validate_saved_source_review` on the same source interpretation, or is its hydrated-batch equality enough across a validator-only change?

### Limitations

No tests were executed. Line references are from this read. The extra-claim path is a control-flow reading of the current gate, not a run. Whether any saved restricted checkpoint actually contains a split antecedent was not established from `restricted_batch_from_review`. Test counts and a `fully_expressed` stub are not medical approval.
