我先按指定范围只读门控与测试，核对“豁免状态是否应省略时间窗”这一判断，以及下游是否会把它当成已满足。门控跳过条件已经定位。接下来核对时间窗正则、合取消费，以及已完成结果是否会沿用这次放行。# Conference Output: rv1006-waiver-window-review-20261011 - evidence_single_object

## Output

The v49 skip is right for one same-group, exactly co-sourced validity window. It is not right for an exactly equal excerpt that still contains another action or another window. The highest-impact hole is a shared sentence such as “重新筛选时可豁免12天内的检查，并须在随机前完成妊娠试验。” The gate accepts it, the 12-day validity atom stays fulfilled, and the randomization-timed action is gone.

### Evidence

The frozen diff against `83d8ee59` is only these two files: `app/protocols/protocol_control_gate.py` (+39/−1) and `tests/v2/protocols/test_slice58c_protocol_control_gate.py` (+101). The gate constant changes from `phase5/control-publication-gate/v48` to `v49` at line 65. The behavior change is `_exemption_validity_is_bound_in_group` (lines 2881–2913) and one `continue` in `_check_time_constraints` (lines 3259–3260). Author, schema, compiler, and model files are outside this diff. Tests were not run.

The skip returns true only when the atom is `complete_or_verify`, has no `time_constraint`, is `semantic` / `not_applicable`, has excerpts and spans, and both the joined excerpts and the statement match `_EXEMPTION_MODALITY_RE` or `豁免|免予`. A same-group peer must be `verify_result_validity`, `time_purpose == source_validity`, have some time constraint, the same excerpt tuple, and the same span set. The tested faults then still raise `TIME_ANCHOR_MISSING`: missing validity, missing window, different group, different span, different quote, wrong peer kind, wrong time purpose, and a statement rewritten to “必须在重新筛选前12天内完成检查。” (`tests/v2/protocols/test_slice58c_protocol_control_gate.py` lines 209–289).

`豁免|免予` is local to this helper. The shared regex at lines 472–475 is only `无需|不需要|不要求|可免(除)?|not required|need not`. “可豁免” does not match that regex. “可免予” matches it only because `可免` is a prefix. `_CONDITIONAL_EXEMPTION_SOURCE_RE` (lines 476–481) also requires `若|如|如果|当|符合|满足|可接受`. None of the three synthetic sentences have that cue, so conditional binding (lines 2318–2367) and scope split (lines 2430–2522) do not see this repair.

`_routine_requirement_text` (lines 2400–2407) strips only `_EXEMPTION_MODALITY_RE` clauses. The new skip does not call it. Cue detection uses excerpts when any exist, and ignores the statement (lines 3251–3256). An atom with `time_constraint is None` never reaches the calendar or comparator checks (line 3002).

Two different “N天内” bounds on one excerpt are already fail-closed on the validity atom. `_TIME_BOUND_SUFFIX_RE` treats “12天内” and “7天内” as two upper bounds, and lines 3108–3113 require every expected bound to be structured. One `TimeConstraint` has one upper bound, so “血常规12天内可豁免，尿常规7天内可免予重复。” does not publish. That is rejection, not a stored second window.

A non-bound cue is not covered by that check. For excerpt and statement both equal to “重新筛选时可豁免12天内的检查，并须在随机前完成妊娠试验。”, with validity `upper_bound_days=12`, anchor `event_date`:

- The validity atom’s expected bounds are only the 12-day upper bound. `event_date` does not trip `TIME_ANCHOR_GUESSED_FROM_SCREENING` (lines 3292–3300), which looks only for anchor `screening_date`.
- “随机前” still matches `_TEMPORAL_CUE_RE` (lines 139–145). “须…完成” matches `_ROUTINE_ACTION_RE` (lines 507–512).
- The helper sees `豁免` on both texts and an exactly equal peer, so line 3260 skips `TIME_ANCHOR_MISSING`.
- The same happens for “并必须完成妊娠试验” with no second window. The current `mandatory_action` test never builds this sentence. It only replaces the statement and leaves the exemption excerpt in place, so the statement fails `exemption_text`.

`validate_control_atom_evaluation` (lines 145–150) allows `time_constraint is None` with `time_purpose` `not_applicable`. It checks source containment, not that every cue has an owner. The test atoms use that shape, and the default modality is `mandatory` (`protocol_controls.py` line 947). The skip does not read modality.

`compose_control_layers` ANDs atoms in a group (`control_layer_evaluation.py` lines 51–56 and 175). `ControlObligationGroup` is documented as a conjunction (lines 1139–1146). With waiver injected `TRUE`, group truth equals the validity truth, including `FALSE` and `UNKNOWN`. The test at lines 292–307 stops there. `project_control_review_outcomes` does not read `obligation_group_truth`. Lines 54–59 set each atom’s status from its own truth: waiver `TRUE` and validity `FALSE` yields waiver `fulfilled` and validity `unfulfilled`; validity `UNKNOWN` yields waiver `fulfilled` and validity `unverified`. The projection says it is not an eligibility verdict.

Completed deep results ignore a validator-version-only change (`_same_deep_components_with_current_gate`, lines 2164–2178) and then call `_validate_deep_batch_output` (lines 1962–1968), which calls `check_protocol_control_batch_candidates` and therefore this gate. Acceptance becomes `same_material_and_current_gate` (lines 3584–3592). Rejection becomes `current_gate_requires_refresh`. The stage-`gate` checkpoint still requires an exact `gate_version` (lines 1354–1358). A v49 false accept can therefore reuse a completed deep result without a new model call.

### Inference

Omitting the duplicate window is correct only for the narrow case the three sentences actually are: one exemption clause, one structured “N天内” bound, same conjunction group, exact excerpt tuple and span set, validity kind and `source_validity`, and a semantic `not_applicable` waiver. Missing peer, missing window, or a changed source still fails closed.

It is not correct once the same excerpt contains another action. The skip forgives the whole atom, not the one window. A mandatory pregnancy test, with or without “随机前”, stays inside the windowless mandatory waiver. Conjunction cannot recover an action that was never its own atom. Numeric pairs such as 12 days and 7 days do not silently pass. They die on the validity comparator. The known limitation still holds for any second cue that is not a second prefix or suffix bound.

The private `豁免|免予` lexicon means the older shared-source guards are not a backstop for the synthetic wording. v49 is the only control on those sentences.

Injected false or unknown validity does not make the group truth `TRUE`. That does not mean the review row stays unfulfilled. The waiver atom can still be projected `fulfilled`. The consumer test does not call the projection. Nothing in the checked path computes a 13-day-old result. The test supplies truths. `observation_policy.mode` is `unresolved` on both specs. The calculator was not read.

### Recommendation

Do not treat v49 as sufficient. Keep the single-window skip. At the existing `continue` (line 3259), fall through to `TIME_ANCHOR_MISSING` when either of these is true:

- After splitting on `，,。；;`, any clause contains a temporal cue or `_ROUTINE_ACTION_RE` and is not an exemption clause under the helper’s own lexicon, including `豁免|免予`.
- More than one of those clauses contains a temporal cue.

No new error code, modality, or clinical window type. The three current sentences still skip: “重新筛选时” has no cue, and the only cued clause is the exemption. “并须在随机前完成妊娠试验” and “并必须完成妊娠试验” do not skip. Two cued exemption clauses, “12天内…可豁免，7天内…可免予”, do not skip either. Leave `_EXEMPTION_MODALITY_RE` unchanged so binding and scope-split do not move with this repair.

Add those two sentences to the fault test. Also add a statement that keeps the 12-day excerpt but appends “，并须在随机前完成妊娠试验。” Today that statement still skips, because cue detection never reads it, while the helper does read it for `豁免`.

Do not change `compose_control_layers` or the projection. Group truth already preserves false and unknown. Atom-level `fulfilled` on the waiver is the projection’s existing per-atom rule. A test that calls the projection should record that boundary, not collapse the group into one verdict.

### Uncertainty

Same-clause coordination is still open: “可豁免12天内的检查或随机前的心电图” is one punctuation clause, so the veto above still skips, and the 12-day peer still passes. Splitting on `或` would also hit legitimate “较长者” wording. That case is not covered by the current tests.

Two upper bounds on one exactly equal excerpt remain unrepresentable. The comparator rejects them. The gate does not create a second constraint. Splitting the excerpt so the tuples are no longer equal is the representation that keeps both windows.

Checked consumers: `validate_control_atom_evaluation`, `compose_control_layers`, `project_control_review_outcomes`, and the completed-result path through `_same_deep_components_with_current_gate` and `_validate_deep_batch_output`. Unread: the date calculator, UI readers of `status`, author, schema, compiler, and exception-layer modeling beyond the early `activates_obligation_group_ids` continue at line 3249. No clinical, execution, adoption, or publication authority is claimed.

### Objections, decision, question

The main objection is that exact source equality is being used as proof that the excerpt contains one action. The tests lock the happy path and the unrelated-window faults, and they miss the multi-action excerpt this review was asked to challenge. A green suite would not show the dropped “随机前” action. Because deep reuse revalidates with the current gate, that false accept becomes a reusable completed result.

The proposed fix is the residual-clause veto at the existing skip, reusing `TIME_ANCHOR_MISSING`.

Decision for Codex: the comma-clause veto is required before this repair is coherent. Same-clause `或` coordination can stay a named hole in this patch. It should not be closed by widening the shared exemption regex or by adding a clinical anchor table.

Question: should a later edit treat same-clause “或/并” coordination as in scope, or is excerpt splitting the required authoring rule for that shape? The safe provisional path is to reject only residual and multi-cue punctuation clauses, and not to publish the “随机前” counterexample under v49.
