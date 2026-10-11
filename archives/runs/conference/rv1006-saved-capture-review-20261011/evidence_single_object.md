我先读会议上下文和主会场计划，再只核对当前差异和受影响定义，确认局部补读恢复是否合法。上下文把审查范围收在保存校验和局部补读路径上。我接着核对当前差异和这些函数的完整定义。差异只在保存失败后的局部补读分支，并改了一处身份版本串。我先读完整函数和真实消费方，核对它是否真能只复用来源解释。# Conference Output: rv1006-saved-capture-review-20261011 - evidence_single_object

## Output

The unadopted draft can seed the existing quote-completion path only for one reproduced failure: a parsed save whose current review raises `SOURCE_SEQUENCE_CAPTURE_INCOMPLETE`, with that same unit still uncovered. On that path the old wire, target review, coverage, alignment, and session are removed, and the runner does not replay an old semantic proposal. It does not do this for every restricted-source rejection. A validator-version token also reopens previously stopped quote-completion failures into fresh authorship. This is not final acceptance. Tests were not run, and product source 46 was not opened.

### Evidence

The worktree is `codex/phase5-clinical-facts-profile` at `8c1fee44`. The service diff is uncommitted and limited to `app/services/protocol_control_execution.py`: a new `validator_version` token at line 2158, and a new branch at lines 2979–3016 inside `_validated_deep_partial_source`. The test module is also dirty. I treated it as the draft’s claim, not as a result.

The new branch runs only after an earlier identity, route, batch, repair-contract, and component check. `_same_deep_components_with_current_gate` still ignores `validator_version`. The branch then requires all of the following:

- no changed components, pending source correction, or obsolete author basis
- `repair_contract_sha256` equal to the current repair contract
- step `error_code == "PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID"`
- last attempt `outcome == "parsed"` and a falsy `error_classes`
- `partial_wire` is a mapping

It rebuilds the failed result with `_saved_failed_deep_run_result` and calls the full `_validate_saved_source_review`. Only `SourceInterpretationValidationError` code `SOURCE_SEQUENCE_CAPTURE_INCOMPLETE` can return a seed. Any other code of that type is re-raised. Any other exception leaves the `try` and aborts the caller. If that capture error is raised and the same unit still fails `source_unit_quotes_cover_source`, the branch returns `source_unit_quote_completion_required` with schema `phase5/source-unit-quote-completion-seed-proof/v1`, `adopted: false`, `reused: ["source_interpretation"]`, and `source_repair_limit` taken from the source job’s `deep_max_schema_repairs`. The seed is a shallow copy of the diagnostic with `partial_wire`, `source_target_review`, `source_candidate_alignment`, and `session_id` cleared, and `source_statement_coverage` set to `[]`.

That capture error is raised only at lines 3817–3829, and only for an owned unit that has `eligibility_sequence == "after_eligibility_decision"` and `eligibility_sequence_context is None`, when the quote ranges do not cover the excerpt. A table-reference witness is a different failure: `validate_source_interpretation` maps `validate_table_sequence_context` to `POST_ELIGIBILITY_CONTEXT_INVALID` at lines 3488–3497. `apply_source_unit_quote_completion` rejects any change other than a continuous extension of `quoted_text`.

The service sets `PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID` only when the post-run `try` raises `ValueError` (`protocol_control_execution.py` lines 4834–4906). `_validate_saved_source_review` is called there only when `final_output` is not `None`. `restricted_batch_from_review` returns `None` without raising when the last attempt has empty `error_classes` and there is no capability wire (lines 899–909). The failure checkpoint I read does not store `final_output`.

The reuse plan calls this same function for `failed_final` (`3635–3684`). A non-null seed forces `decision: "resume_partial"`. Because the proof schema is not `phase5/revalidated-source-seed-proof/v3` through `v6`, the plan reason is overwritten to `verified_source_interpretation_repair_material_changed` even though this branch required the repair contract to match. The runner later compares the whole `source_seed_proof`, not that reason string (`4734–4736`).

The runner completion block (`protocol_control_deconstructor.py` lines 7952–8020) refuses the completion when a wire, target review, alignment, or coverage is present. It extends quotes only through `apply_source_unit_quote_completion`. History is rechecked by `_saved_source_scope_question_history` (`4335–4389`) and again at lines 7860–7948. A quote-completion history record is not parsed back into the interpretation. A matching precondition only suppresses another call. A bad or mismatched record raises before a model call, or counts as budget and is not applied. After completion, line 8786 sets `repairs = source_repairs + resume_pending_author_repairs_used`, so later author repairs share that cap. `source_repairs` starts from question-history rows whose `called` is not `False`; a missing `called` counts as used. Ordinary author attempts are not in that history.

The in-job checkpoint resume at lines 4532–4575 does not call the new branch. It uses `_pending_author_resume`, `_resumable_unit_completion_failure`, or `_resumable_saved_source_review`. Cross-job `resume_partial` does call `_validated_deep_partial_source`.

The new token is not read by the new branch. It changes `validator_version`, so every older checkpoint gets `capture_validation_changed=True` at lines 2955–2957. `_resumable_unit_completion_failure` runs first. For `outcome == "schema_invalid"` and `SOURCE_UNIT_QUOTE_COMPLETION_INVALID`, a source that now covers can return `source_capture_revalidated_requires_fresh_author` (`2837–2852`) instead of raising `SOURCE_UNIT_QUOTE_COMPLETION_STOPPED`. That return still requires the saved wire and review fields to be empty, and it clears completion ids. The caller returns the original diagnostic with that proof (`2958–2965`).

If the new `try` does not return, execution continues through the older reuse paths. Those paths can restore `partial_wire`. `preserve_unresolved` is used only when `source_seed_proof is None` (`3656–3662`).

### Inference

For a context-free post-eligibility unit whose excerpt tail is still outside the saved quotes, the draft does the requested thing. It keeps the source interpretation, drops the listed semantic proofs, reuses the existing completion consumer, and relies on a later full `_validate_saved_source_review` before a `final_output` can be kept. A second uncovered sequence unit is not listed, but that later gate rejects it, so one resume fixes one unit and does not adopt the rest.

The branch does not mean “the saving consumer rejected this capture.” It means “revalidation happened to raise this one code.” A tail stored as `eligibility_sequence_context.table_reference` fails earlier as `POST_ELIGIBILITY_CONTEXT_INVALID` and is re-raised. Quote completion cannot legally repair that field. A restricted failure that passes the sequence check and then raises a plain `ValueError` inside the full review now aborts plan construction; before this diff, that same parsed diagnostic could fall through to an unpublished-draft or source-only resume.

The false plan reason does not select a full reread. The execution consumer will still demand an equal proof. The label is still a bad receipt: repair material was not required to change.

The version token is the adoption-adjacent defect. It does not copy a rejected completion into the interpretation. It does change a hard stop into fresh authorship for every old invalid completion whose current quotes already cover. Fresh author and review gates can then adopt a new result that this code previously refused to start. That is wider than “incomplete capture seeds local completion.”

Mismatched completion history is not accepted as a new interpretation. It is either rejected or retained only as spent budget. The cap itself is the source job’s configured cap, not the repairs already spent on non-history author attempts. Those attempts remain on the seed’s `attempts` list, but the runner does not receive them and the next diagnostic is built from the new run.

`pending_author_wire`, `capability_wire`, `source_front_target_review`, and `source_review_reuse` stay on the seed. This reason does not pass them into the runner. They are not in `discarded`.

### Recommendation

Keep the source-only seed, but make the predicate the capture check itself. Do not use a full `_validate_saved_source_review` whose non-capture `ValueError` aborts the plan. If the code is not `SOURCE_SEQUENCE_CAPTURE_INCOMPLETE`, leave the new branch and keep the older per-batch behavior. Seed every currently uncovered context-free sequence unit, matching the older collector at lines 3051–3057, not only the first exception unit.

Do not treat `saved-sequence-capture-local-recovery/v1` as proof that capture checking changed. Either drop it from the global `capture_validation_changed` switch, or compare a capture-specific version before reopening `source_capture_revalidated_requires_fresh_author`.

When the proof schema is `phase5/source-unit-quote-completion-seed-proof/v1`, set the plan reason to `source_unit_quote_completion_required` and do not overwrite it with `verified_source_interpretation_repair_material_changed`.

Clear the leftover semantic fields on the seed. Pass only question history plus the original cap if that is the intended cumulative budget; if author repairs share that cap, subtract their already recorded use before the next completion call.

Leave same-job checkpoint resume unchanged unless Codex decides that retrying the failed job, rather than a cross-job `resume_partial`, must perform this recovery.

### Uncertainty

I did not run tests, call a model, or inspect product `244296b31b9e4c459e0f162d64e7e427`, its database, logs, environment, or source text. The context says source 46 missed a tail table reference and the saving validator rejects it. The code I read can reproduce that only as `SOURCE_SEQUENCE_CAPTURE_INCOMPLETE`. I cannot tell whether source 46 actually raised that code.

### Objections

The highest-impact defect is the validator token at line 2158. The new branch never reads it, but it makes every older checkpoint look like capture validation changed. A stopped `SOURCE_UNIT_QUOTE_COMPLETION_INVALID` whose quotes now cover becomes fresh authorship. That can turn a previously blocked semantic cycle into a new adoptable author result after the normal gates. The rejected completion text itself is not copied.

The second defect is the branch predicate. It claims to recover a saving-consumer capture rejection, but it recovers only one exception, and other exceptions from the same full validator now fail the whole reuse plan. A table-reference context mismatch is not a legal quote-completion input.

The plan reason falsely says repair material changed. The runner does not act on that sentence, so this is a receipt defect, not a reread by itself.

### Decision points

1. Is the authorized recovery only cross-job `resume_partial`, or must a same-job retry of the failed diagnostic use the same seed?
2. Should `capture_validation_changed` remain a whole-`validator_version` comparison after this token is added?
3. Is the cumulative budget the source-job cap minus question-history calls, or must prior author schema repairs be deducted as well?

### Bounded question

Which exception did the saving consumer raise for source 46: `SOURCE_SEQUENCE_CAPTURE_INCOMPLETE`, or `POST_ELIGIBILITY_CONTEXT_INVALID` or another `ValueError`? The safe provisional path is to seed quote completion only when the current sequence-cover check reproduces `SOURCE_SEQUENCE_CAPTURE_INCOMPLETE`, and to leave every other restricted-source failure on its existing path without adopting the saved wire.
