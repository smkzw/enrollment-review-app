我先读会议上下文，并核对指定 diff，只审这段有界排序改动和它的直接调用方。Diff 已拿到。接下来只看源目标审核、插入组装、检查点序列化和受限消费这几段，核对未决兄弟项会不会被当成已采纳。# Conference Output: rv1006-unresolved-sibling-retention-20261007 - evidence_single_object

## Output

The runner checkpoint can keep a gate-verified insert and still withhold `final_output`. The same shrinkage that makes that checkpoint validate also removes the `additional_requirement` decision that used to stop restricted publication. `restricted_batch_from_review` plus the deep execution return can therefore adopt the insert while an unresolved sibling remains. That is the highest-impact defect. Checkpoint retention and restricted adoption are different outcomes.

### Evidence

Read set, 18 material calls, no writes, no tests, no clinical inputs:

- Context packet.
- `git diff -- app/agents/protocol_control_deconstructor.py tests/v2/protocols/test_slice58c_control_deconstructor.py`.
- `protocol_control_deconstructor.py`: `_require_resolved_source_target_review`; repair-contract hash at `protocol_control_agent_repair_contract_sha256`; runner review/insert/alignment block from the pre-insert `validate_source_target_review` through the unresolved exception return; `recovery_target_review`.
- `protocol_control_source_interpretation.py`: `target_review_indexes`, `validate_source_target_review` scope check, `validated_source_review_seed`.
- `protocol_control_stage_compiler.py`: `assemble_source_requirement_inserts`.
- `protocol_control_restricted_source.py`: `restricted_batch_from_review`, `_coexisting_statement_proofs` header and disjoint-range gate.
- `protocol_control_execution.py`: deep resume load and the `restricted_batch` success return versus `StepFailure`.
- New test `test_unresolved_sibling_keeps_verified_insert_without_accepting_batch` only, via the diff. Fixture body `_stage_bound_example` was located at `tests/v2/protocols/test_slice58c_control_deconstructor.py:10153` and not read.

Observed control flow:

- The full target review is validated before any insert (`validate_source_target_review` on the assembled review). The old immediate `SOURCE_TARGET_REVIEW_UNRESOLVED` raise is gone.
- A successful `assemble_source_requirement_inserts` replaces `target_review`, `latest_source_target_review`, `latest_source_statement_coverage`, and `review_validation_snapshot` with `remaining`, which drops every inserted statement. The assembler itself requires each inserted statement’s coverage status to be `expressed`.
- `target_review_indexes` omits a statement once its status is `expressed` (unless `cited_external_rationale`). The shrunk review therefore satisfies the full-review validator.
- `_require_resolved_source_target_review` runs only after that retention, and only when `pending_additional` is empty. It raises before `final_output` is set. The handler returns `需要核对`, `partial_wire` kept, `final_output` unset, review taken from `recovery_target_review()`.
- `validated_source_review_seed` explicitly allows missing review items. The new test locks the saved review to statement index 1 only, and locks a second candidate draft when selection is valid, for both `same_unit` values.
- `SOURCE_REQUIREMENT_FAILURE_POLICY_VERSION` moved from v3 to v4 and is an input of `protocol_control_agent_repair_contract_sha256` only. It is not an input of `protocol_control_agent_prompt_template_sha256`.
- Restricted eligibility source was not in this diff. Its gate still admits a last attempt whose class is `SOURCE_TARGET_REVIEW_UNRESOLVED`, `TEMPORAL_SCOPE_UNRESOLVED`, or `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED`. A review item whose decision is `additional_requirement` fails that gate unless the index is temporal. A statement with no review item, status `expressed`, and disposition `OTHER_CONTROL_CANDIDATE` is kept. Execution returns that restricted batch as a deep success payload before the unresolved `StepFailure` branch.

The context’s “23 passed / 511 deselected” figure was not re-run.

### Inference

Severity 1 — restricted adoption, not merely a checkpoint. A mixed batch whose bounded insert compiles now stores an `expressed` statement outside the review and an unresolved sibling inside it. That is exactly the shape `restricted_batch_from_review` treats as an adoptable candidate beside a restricted statement. Before this ordering change, the same batch still carried a non-temporal `additional_requirement` item, and the restricted function returned `None` before any proof. The runner test never calls the restricted consumer, so its `final_output is None` assertion does not show that execution will withhold the batch.

Counterexample, cross-unit, valid stage-bound selection, using the new test’s transport shape:

- Statement 0 is `additional_requirement`, compiles, coverage becomes `expressed`, and its review item is removed.
- Statement 1 stays `unresolved` on another unit, with `statement.unresolved` populated.
- Runner result: `需要核对`, `final_output is None`, last class `SOURCE_TARGET_REVIEW_UNRESOLVED`, `partial_wire` has the new draft.
- Restricted consumer: the decision filter no longer sees `additional_requirement`. Statement 0 matches the absent-review + `expressed` + `OTHER_CONTROL_CANDIDATE` branch. Statement 1’s unit can take the single-statement restricted fallback. Candidates that do not cite the unresolved unit survive the unproven-span check.
- Execution then returns `restricted_batch` and does not raise the unresolved failure.

The same hole exists when a temporal sibling raises `SourceTemporalScopeUnresolved` after the insert. That raise sits above the new unresolved check, and `TEMPORAL_SCOPE_UNRESOLVED` is already an eligible restricted class. Temporal `additional_requirement` items are exempt from the decision filter when `_temporal_restriction_indexes` includes them. That helper was not read.

Same-unit syntactic separation is not a semantic-independence proof. `_coexisting_statement_proofs` says literal disjoint ranges are necessary and are not semantic equivalence. The runner never calls that proof before writing `partial_wire`. The new test expects two drafts when `same_unit` is true and selection is valid. A same-unit pair that later satisfies the literal proof can now reach publication; previously the `additional_requirement` item stopped the restricted function first. A same-unit pair that fails the proof still returns `None` from the restricted function because the unit has more than one statement. That failure keeps a diagnostic checkpoint only. It does not stop the draft from sitting in `partial_wire`.

Severity 2 — rejected bounded insert skips the unresolved stop and opens unit-scoped repair. If assembly throws, those reviews go back to `pending_additional`, so the new check at the empty-pending branch does not run. The code then raises `ProtocolControlAgentWireValidationError` with `allow_source_insert=True` for the additional items’ units. The wire-validation handler re-raises it. For `same_unit=True`, the unresolved sibling’s unit is inside that authorized unit set. The new test’s `start_source_insert` always throws, and the invalid-selection assertions only require one draft and some unresolved item. They do not require that whole-batch insert was not called. The repair-loop body from about line 9200 was not read, so a successful repair that quotes the sibling and turns it `expressed` is an open path, not a demonstrated publish.

Severity 3 — recovery of a retained insert does not re-review it. `target_review_indexes` skips `expressed` statements. Resume reuse only keeps covered, background, definition, or resumed non-unresolved decisions. After this checkpoint, a later resolution of the sibling can finish the batch with the inserted candidate still outside review scope. v4 changes the repair-contract hash, which separates v3 from v4 for any caller that compares that hash. The resume block that was read checks source-seed proof, transport identity, and component identity. It does not show a repair-hash comparison. A v4 checkpoint of this new shape remains resumable.

Unresolved-only batches still hit `_require_resolved_source_target_review` after the empty `additional` block. No insert runs, and the review is not shrunk. That path is intact in the source. This diff adds no unresolved-only test.

Transport failure after a successful sibling read returns `需要核对` with the updated wire and no `final_output`. The last outcome is `transport_failed`, which the restricted gate does not admit. Execution classifies `SOURCE_REQUIREMENT_TRANSPORT_FAILED` as retryable. That is checkpoint retention with a retry, not adoption. The return uses `target_review` directly, so a failure after assembly persists the shrunk review.

A coverage list that fails `validate_source_target_review`, or an insert whose status is not `expressed`, is caught as `STAGE_BOUND_INSERT_INVALID` and is not assigned to `partial_wire`. Missing coverage on the success path fails closed inside the assembler. The new test does not assert statement 1’s coverage entry.

### Recommendation

Keep the post-insert checkpoint. Stop it from qualifying as restricted publication.

- Record a distinct terminal class, or an explicit retention marker, when a gate-verified insert is kept and any sibling is still unresolved or temporal. Do not add that class to the restricted eligible set `{SOURCE_TARGET_REVIEW_UNRESOLVED, TEMPORAL_SCOPE_UNRESOLVED, SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED}`. Leave pure unresolved-only results on the existing class so their current restricted behavior stays put.
- On a rejected bounded insert, stop at the unresolved sibling before `allow_source_insert=True`. Do not authorize the sibling’s unit for whole-batch repair.
- Extend the synthetic test so `restricted_batch_from_review` is `None` for both `same_unit` values, the execution wrapper does not return `restricted_batch`, invalid selection does not call `start_source_insert`, and a mid-batch transport failure stays non-adopting. Add an unresolved-only control and a v3-versus-v4 repair-hash resume check.
- Do not treat the current test’s review shape `[1]` as evidence that publication was withheld.

### Uncertainty

These were not read, because the 18-call cap was reached:

- `_stage_bound_example` at test line 10153, so this pass did not observe that fixture’s disposition enum. The adoption branch is `OTHER_CONTROL_CANDIDATE`; if this fixture uses another disposition, this fixture may fail closed while any batch that does use `OTHER_CONTROL_CANDIDATE` still adopts.
- `check_protocol_control_batch_candidates` on the rewritten restricted output. The insert already passed the runner’s output validator. This last predicate can still reject the restricted object.
- `_temporal_restriction_indexes`.
- The source-insert repair loop around lines 9200–9810 and `_merge_source_candidate_insert`.
- Every `repair_contract_sha256` comparison on resume.
- `source_statement_ranges_cover_unit` and `source_statement_context_is_self_contained`.

No clinical, regulatory, visual, or current-web acceptance is claimed. Owner owns integration and tests.

### Objections, decision points, and questions for Codex

The plausible reading of this patch is “move the unresolved stop until after a verified insert, and keep the batch unpublished.” The runner honors that for `final_output`. The direct execution consumer does not. Shrinking the review is what lets the full validator accept the checkpoint, and it is also what deletes the decision that blocked restricted adoption. The new test freezes that shrunk review and never calls the consumer.

Proposed resolution: a retained insert beside an unresolved or temporal sibling stays in the diagnostic checkpoint under a class the restricted gate does not admit. Rejected inserts do not enter unit-scoped source repair while an unresolved sibling remains.

Decision needed from Codex: should any cross-unit, gate-verified insert beside a restricted unresolved sibling be returned as `restricted_batch` in this change? The packet text says the result remains an unaccepted checkpoint and restricted eligibility is unchanged. The execution path contradicts that sentence. If Codex wants that adoption, the packet text and the test both need to say so, and same-unit cases need a semantic proof stronger than disjoint quotes.

Bounded question: where resume compares `repair_contract_sha256`, does a v3 partial fail closed before `ProtocolControlAgentRunner.run`, or can it resume under v4? This matters because v4 as currently written changes repair identity without marking “insert retained beside unresolved sibling” as a non-resumable seed. Safe provisional path: treat every v3 partial as non-resumable, and do not resume a v4 checkpoint whose review is missing an `expressed` statement that was inserted in the same run as an unresolved sibling, until the adoption gate above is explicit.
