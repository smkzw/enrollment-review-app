我先按指定读集核对补充阶段合同和修复边界，只读源码，不改文件、不跑测试。# Conference Output: rv1006-completion-stage-boundary-20261007 - evidence_single_object

## Output

No clinical, regulatory, or publication acceptance. The two rejections are structural. A short repair JSON would not be success. No code was changed.

### Evidence

Reads this pass, in order:

1. `app/protocols/supplementary_relation_contract.py` (complete)
2. `app/agents/protocol_control_deconstructor.py` repair guidance, including `PROCEDURE_AFFECTED_STAGE_MISMATCH` and `AFFECTED_STAGE_DECISION_MISSING` (about 2480–2679)
3. Same file, `_validate_known_targets` (about 3283–3396) and the tail of excerpt checks just above it
4. Same file, `_merge_candidate_repair_payload` (about 5229–5323)
5. `app/protocols/protocol_control_gate.py` `_check_mixed_decision_stage_control` through part of `_check_time_constraints` (about 2702–2859)
6. Same file, `_check_anchor_decision_alignment` and `_check_post_enrollment_procedure_classification` (about 3470–3649)
7. `app/domain/contracts/protocol_controls.py` obligation kinds, modalities, temporal scope, review-node roles, relation kinds (about 177–296)
8. Same file, `ControlContinuingObligation` and `validate_control_continuing_obligation` (about 881–973)
9. Same file, `ReviewNodeBinding`, `ControlCrossSourceRelation`, `ControlCrossSourceRelationDraft` (about 1632–1829)
10. `app/protocols/protocol_control_gate.py` `_check_supplementary_procedure_stage_alignment` and `_check_temporal_obligation_relation_scope` (about 3906–4094)
11. `tests/v2/protocols/test_slice60zz_cross_stage_supplement_contract.py` (complete; not executed)
12. `app/services/protocol_control_restricted_source.py` temporal and capability admission (about 1–220)
13. `app/domain/contracts/control_evaluation_spec.py` (complete)
14. `app/domain/contracts/control_time_binding.py` `validate_control_time_bindings` (about 1–69)
15. `app/protocols/protocol_control_gate.py` duration and prospective-period checks inside `_check_time_constraints` (about 2860–3184)
16. `app/agents/protocol_control_source_interpretation.py` `SourceStatement` (about 158–183)
17. `app/protocols/protocol_control_gate.py` source-statement independence helpers (about 4912–4933). This 17th read is past the 16-read budget; it only confirmed restricted admission is quote-scoped. No further reads.

Frozen predicate, both consumers:

- `SUBSEQUENT_CONTROL_OBLIGATION_KINDS` is only `verify_result_validity` and `select_baseline_value`.
- `_atom_is_subsequent_control` returns true for every `select_baseline_value`. For validity it also requires `time_constraint.anchor_type` in `FUTURE_ANCHOR_TYPES` (`baseline_date`, `randomization_date`, `first_dose_date`, `study_drug_administration_date`).
- `is_cross_stage_subsequent_control_supplement` then requires affected stage strictly after procedure execution, and not before the first frozen baseline node. It reads no excerpt, no `time_purpose`, and no `SourceStatement.affected_stage`.
- It returns true if any atom in the whole expression qualifies. The check is not per relation.
- `_validate_known_targets` and `_check_supplementary_procedure_stage_alignment` call that helper. If it is false, `execution_id` must equal `affected_workflow_stage_id`, or the code is `PROCEDURE_AFFECTED_STAGE_MISMATCH`. Either way, affected stage must have `decide_at_node`, or the code is `AFFECTED_STAGE_DECISION_MISSING`.
- Equality of execution and affected already forces the helper false, so the helper’s “must be later” branch is unreachable through this helper.

Repair authority already present:

- `_merge_candidate_repair_payload` with `fields == ("cross_source_relations",)` may omit an authorized relation. Identity is only `kind`, `external_target_kind`, `external_target_id`, `candidate_side`.
- `affected_workflow_stage_id` is not part of that identity, so an authorized relation may move its affected stage.
- New target, new kind, or a duplicate identity is rejected. Bindings and evidence are outside a relation-only payload.
- Guidance at the mismatch branch already says not to move the decision earlier, not to drop a real requirement, and not to relabel the obligation when the contract cannot express later verification of a full duration.

Typed time and evaluation do not name a review node:

- `ControlTimePurpose` is `not_applicable`, `event_membership`, `interval_condition`, `source_validity`, `unresolved`.
- `validate_control_atom_evaluation` rejects `observation_policy.mode == "action_completion"` when a `time_constraint` is present. That mode is only a point `complete_or_verify`.
- Semantic `complete_or_verify` plus `time_purpose == "interval_condition"` only changes duration-versus-window checks in `_check_time_constraints`. It does not authorize a later affected stage.
- `validate_control_time_bindings` checks that a bound atom repeats the control-level constraint and has a time purpose. It does not select a workflow stage.
- `continuing_obligation` is valid only on prohibit kinds. The slice60zz test already asserts a future prohibit continuation does not authorize a cross-stage supplement.
- `SourceStatement.affected_stage` is an optional string. `decision_functions` has no completion-at-later-node value. Restricted admission (`_restricted_capability_batch`, `_temporal_restriction_indexes`) accepts only proved `TIME_PRECISION_UNSUPPORTED` or `TEMPORAL_SCOPE_UNRESOLVED`. `PROCEDURE_AFFECTED_STAGE_MISMATCH` is not an admission code.

Existing negatives already encoded:

- Slice60zz `test_syn_reject_02`: same-stage `complete_or_verify` with baseline affected raises `PROCEDURE_AFFECTED_STAGE_MISMATCH`.
- `test_syn_reject_03`: validity supplement whose affected stage is screening, while `decide_at_node` stays at baseline, raises `AFFECTED_STAGE_DECISION_MISSING`.
- `_check_anchor_decision_alignment` rejects a future-anchor `decide_at_node` before the first baseline node (`EARLY_DECISION_FOR_FUTURE_ANCHOR`).
- `_check_post_enrollment_procedure_classification` rejects `complete_or_verify` in `treatment_period`, or a future anchor with direction `after` and a positive bound.
- `_check_mixed_decision_stage_control` rejects an unanchored routine action mixed with a future-anchor atom.

Uncovered consumers, not read: `protocol_control_execution.py`, `eligibility_review_projection.py`, `qualified_binding_selection.py`, `protocol_control_stage_compiler.requires_temporal_resolution`, the repair dispatcher near deconstructor line 9785, and the two gate call sites that pass arguments into `_check_supplementary_procedure_stage_alignment`. Hydration was seen only through the slice60zz test, which keeps `affected_workflow_stage_id` on a validity supplement.

### Inference

The first causal layer is `is_cross_stage_subsequent_control_supplement` / `_atom_is_subsequent_control`, not the merger and not the two error codes.

Those codes do what the helper says. For this shape the helper is false because the kind is `complete_or_verify`. Affected baseline versus run-in execution therefore mismatches. A relation-only repair can move affected back to run-in, and then the same function demands `decide_at_node` on run-in while the binding stays at baseline. That is `AFFECTED_STAGE_DECISION_MISSING`. Deleting one authorized relation leaves every sibling relation under the same predicate, so the same mismatch moves to the sibling. No batch acceptance follows.

`interval_condition`, a baseline `decide_at_node`, `early_attention`, or a `baseline_date` anchor does not prove that the source named that node as the completion check. Anchor alignment and duration checks answer a different question. Using them as the cross-stage proof would treat an invented final node as sourced.

The owned source’s verbatim text was not in the read set. “Represented as baseline binding” is the candidate shape, not proof the excerpt says “在基线核实完成”. If that excerpt is only start plus duration, it is case (d), and this same helper is the correct rejection.

### Recommendation

Preferred bounded path: one source-qualified branch inside the existing helper, still consumed only by `_validate_known_targets` and `_check_supplementary_procedure_stage_alignment`. Keep `SUPPLEMENTARY_REQUIREMENT`. Do not add a relation kind, an obligation kind, a disease or day prompt, or a restricted-admission code. Do not change the procedure’s `review_stage` or `visit_instance`.

Allow affected stage later than execution only when all of the following hold for that relation:

- The qualifying atom is `complete_or_verify`, determination `semantic`, `time_purpose == "interval_condition"`, with its own `time_constraint`.
- `observation_policy.mode` is not `action_completion`. The atom is not a prohibit continuation.
- That atom’s own excerpts, not another atom in the expression, contain a completion or verification cue and a stage mention that resolves to exactly one frozen workflow target, and that target is `affected_workflow_stage_id`.
- That affected stage is strictly after `procedure_execution_workflow_stage_id`. A start-stage mention such as “筛选开始” does not satisfy the affected stage.
- Existing checks stay: `decide_at_node` and same-stage minimum evidence on the affected node; earlier node may be `early_attention` only.
- Do not exempt this branch from `EARLY_DECISION_FOR_FUTURE_ANCHOR`, `POST_ENROLLMENT_PROCEDURE_MISCLASSIFIED`, `MIXED_DECISION_STAGE_CONTROL`, or the current “not before first baseline” floor.

Legal saved recovery for a true (a) is relation-only and already legal: put `affected_workflow_stage_id` back on the source-named later node and leave the baseline decision in place. The failing move, affected back to run-in while decision stays at baseline, must still raise `AFFECTED_STAGE_DECISION_MISSING`.

Update only the two guidance returns for those error codes so the retry stops moving the decision earlier. State the source proof. Do not add training, drug, or day text.

Alternatives:

- Independent candidate with the procedure link removed is the right recovery when the link is false, and guidance already says that. It is not sufficient for (a). After the link is gone, `_check_temporal_obligation_relation_scope` does not require a procedure target for `complete_or_verify`. A one-time screening action can then keep a baseline decision unless some other gate happens to fire. Case (b) would not be reliably rejected. Sibling deletion also matches the diagnostic: one deletion did not clear the batch.
- Typed non-executable restricted record is the wrong sink for (a) and for the whole mismatch class. Current admission will not fire. Extending it to every `PROCEDURE_AFFECTED_STAGE_MISMATCH` would hide false links and real later completions together. Case (c) already has prospective period, post-treatment disposition, and prohibit-only continuation. It should stay there.

Checks the patch has to satisfy, still without implementing them:

- Positive (a), “筛选开始训练，连续完成若干日后，在基线核实完成情况”: same procedure execution stage, affected and `decide_at_node` at the frozen baseline node, screening `early_attention`, semantic interval `complete_or_verify`. Helper true. Both current consumers accept. Validity and baseline-value siblings unchanged.
- Negative (b), “筛选完成一次检查” linked to baseline: point action, no later completion cue. Helper false. Mismatch remains. Deleting the link must not by itself make baseline the decision node.
- Negative (c), “筛选完成操作，研究期继续维持” with no later eligibility sentence: no cross-stage supplement. Prospective period or post-treatment path only.
- Negative (d), start plus duration and no named final node: helper false. Do not invent baseline from `interval_condition` or from an existing baseline binding.
- Replay of the diagnostic repair, affected moved to execution while decision stays later, still `AFFECTED_STAGE_DECISION_MISSING`.
- Existing slice60zz accepts and rejects for validity, early future-anchor decision, mixed execution plus validity, and prohibit continuation stay as they are.

### Uncertainty

The owned excerpt was not read. If it does not itself name the later verification node, do not apply this branch to that candidate. Keep the mismatch. Do not write a restricted or accepted record.

Execution and projection were not read. It is unproved that a published later `decide_at_node` is the stage those consumers score. A helper-only change could publish a shape the reviewer still scores on the procedure visit.

The stage-cue match is the brittle part. A bare “基线” in the wrong clause can false-pass. The proof has to tie the verification cue to that stage token, and fail closed when two later stages are named.

The helper’s current `any subsequent atom` rule can already let one validity atom authorize every procedure relation on the candidate. The new branch must not copy that. Qualification has to be on the atom that supports the relation being checked.

The pre-baseline floor is unchanged. A completion node that is after run-in but before the first baseline node stays illegal. Case (a) uses baseline, so this pass does not loosen that floor.

### Objections, decision, and questions for Codex

Highest-impact objection: widening every `complete_or_verify`, or treating `interval_condition` plus baseline binding as proof, would accept (b) and (d). The current any-atom helper is already too coarse to extend as-is.

Competing explanation: the contract is right, and the candidate should drop the procedure link and stand as its own control. That is the correct recovery only for a false link. It does not reject (b) after deletion, and it drops the audit link the diagnostic says exists. I do not prefer it for (a).

Decision point: widen nothing until the owned excerpt is classed as (a) rather than (d). Safe provisional path is to keep both current rejections and leave the helper allowlist unchanged for any source that does not verbatim name one later frozen node as the completion check.

Bounded question: does the owned excerpt contain an explicit later-node completion clause, as in (a), or only a start and a duration, as in (d)? This chooses whether the helper branch is applicable to that candidate or whether continued mismatch is the correct structural result.
