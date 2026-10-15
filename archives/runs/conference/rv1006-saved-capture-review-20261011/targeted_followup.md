源 46 已由负责人定为捕获不完整。我只核对当前分支和真实消费方，看上一轮的采纳、身份和预算问题是否还在。# Conference Output: rv1006-saved-capture-review-20261011 - evidence_single_object

## Output

The current revision closes the material adoption, identity, and budget issues in this branch. A clean parsed `SOURCE_SEQUENCE_CAPTURE_INCOMPLETE` failure is seeded as source interpretation only. The old wire and the other listed semantic fields are not passed to the runner, and this diff does not reopen a stopped quote failure. No remaining adoption, identity, or budget defect showed up in this branch or its direct consumers.

### Evidence

The service diff is still the two uncommitted hunks in `app/services/protocol_control_execution.py` (54 lines) at `8c1fee44`. `saved-sequence-capture-local-recovery/v1` occurs once in application code, as `recovery_version` on the new proof at line 3016. It is not part of `validator_version`. `_resumable_unit_completion_failure` still runs first, at lines 2954–2964, and its `capture_validation_changed` flag is still the existing validator-version comparison. This diff does not change that comparison.

The branch at lines 2978–3028 admits only a current repair contract, step error `PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID`, every attempt `parsed` with no error classes, `pending_author_repairs_used` of integer 0, and no pending-author, capability, or front-flow wire. It calls `validate_source_interpretation`, then collects every context-free `after_eligibility_decision` unit that fails `source_unit_quotes_cover_source`. It does not call the full semantic validator and does not stop at the first exception. The seed clears `partial_wire`, target review, coverage, alignment, session, front review, capability wire, source-review reuse, pending author, and pending definition consumers. It keeps `source_interpretation`, `attempts`, and any question-history field. `adopted` is false. `source_repair_limit` is the source job cap.

Preflight lines 3687–3699 label this schema `source_unit_quote_completion_required`. `preserve_unresolved` still requires a null proof. The execution consumer compares the whole proof, passes completion ids, and passes pending-author state only for a different reason. With `partial_wire` cleared, `resume_wire` stays null. The existing runner block at `protocol_control_deconstructor.py` lines 7952–7962 rejects a wire, review, alignment, or coverage on that path. Quote history is not parsed back onto the interpretation. After completion, a null session starts a new author call. The runner counts question-history rows whose `called` is not false against that same cap.

The owner test diff adds `parsed_capture`, `parsed_two_units`, `parsed_foreign_quote`, `parsed_wrong_failure`, `parsed_prior_failure`, and `parsed_author_used` to `test_saved_source_gap_preflight_preserves_source_but_discards_semantic_draft`. Those assertions match this branch: two-unit ids, a raised foreign quote, and a null proof for the wrong failure, a prior failed attempt, and a non-zero pending-author count. I did not run them.

The owner’s revalidation that source 46 raised `SOURCE_SEQUENCE_CAPTURE_INCOMPLETE` matches the predicate this branch now computes. I did not reopen the product payload.

### Inference

The prior token defect is gone, so old stopped quote failures are not newly reopened. The context-invalid uncertainty is closed by the owner’s exception code: this branch validates the source and then applies the same sequence-cover condition the saving consumer uses for that code. All uncovered units of that kind are listed, so a second gap is not left for a later semantic resume.

A prior failed attempt or a non-zero pending-author count does not enter the branch and does not receive a new cap here. On the path that does enter, the old semantic fields are absent from the runner arguments, and the completion consumer refuses them if they were present. The bad proposal in an old attempt or history row is not applied. Fresh author and the existing saving gate remain after the quote extension.

Identity used by the resume decision is unchanged: repair contract must match, component identity is not edited, and route and batch checks above the branch are unchanged. `recovery_version` travels only inside this proof. Plan build and execution both compute it, so it does not create a second identity.

Budget on this path is the source-job cap minus the preserved question-history calls. The branch does not reduce a positive `pending_author_repairs_used`; it refuses the seed. It also does not treat a failed non-history attempt as reusable budget, because that attempt cannot enter.

### Recommendation

No further change is required in this branch for adoption, identity, or budget. The `discarded` list still omits four cleared receipt fields (`pending_author_wire_sha256`, `pending_author_source_sha256`, `pending_author_repairs_used`, and `pending_source_definition_consumer_attempts`). Those fields are cleared on the seed and are not loaded by the runner. That is a receipt omission, not an adoption path.

### Uncertainty

I did not execute the owner tests or the runner. The owner tests inspect `_validated_deep_partial_source` only. The runner refusal and the history budget count come from reading the existing consumers, not from a run. No clinical acceptance is claimed.
