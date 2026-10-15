上一轮已定位补丁和回滚入口。我补齐错误码落盘、独立续读资格，以及损坏负例能否清掉回滚这几处证据。The late negative path can authorize a unit rewrite from a failed re-read, and the sibling-retention check does not guard that raise. This is a read-only advisory pass, not acceptance.

# Conference Output: rv1006-late-policy-recovery-review-20261011 - evidence_single_object

## Output

HEAD is `5bb2d4e6`. The declared diff is `app/agents/protocol_control_deconstructor.py` (+41) and `tests/v2/protocols/test_slice58c_control_deconstructor.py` (+92). No source edit, test run, browser, or clinical read was done. The “15 passed / 1088 deselected” result is the assignment’s report, not an observation from this pass.

### Evidence

The new handler is inside `build_result` at `protocol_control_deconstructor.py:7692-7758`. After `require_evidence_policy_alignment` throws, it reloads receipts with `reusable_proven_alignment_items(..., require_positive=False)`, keeps `decision == "incomplete"` pairs, and enters recovery when that list is non-empty and the exception is not `EvidencePolicyCheckError`. It may clear `pending_alignment_atom_baseline`, always assigns `partial_wire` and the two `latest_*` bindings, then calls `_reviewed_semantic_closure_repair`. A unique unit, an unused ledger entry, a live `continue_scoped_unit_repair`, and remaining budget cause `raise semantic_repair`. That exception is a `ProtocolControlAgentWireValidationError` with `allow_source_closure_rewrite=True` (`5188-5195`). The success `return build_result(...)` at `10905-10924` and `10436-10454` sits in the `try` whose `except` starts at `10925`, so the typed error does reach the existing scope calculation at `11249-11310` and the existing splice at `11948-12148`. `nonlocal` names are real outer locals (`7599`, `7613`, `8751-8752`). The late path assigns them; it does not read them before assignment. Early `build_result` returns before line 8751 do not pass `final_output`, so they do not enter this block.

`reusable_proven_alignment_items` (`811-852`) drops a bad version, a duplicate pair, a missing or extra proof, a hash mismatch, a response-body mismatch, and any `validate_candidate_alignment` failure. `_validate_evidence_policy_checks` (`882-920`) raises `EvidencePolicyCheckError` for a duplicate, out-of-scope, or source-mismatched check. Value mismatch and missing dimensions are enforced only when `decision == "fully_expressed"`. An `incomplete` item may therefore bind with `evidence_policy_checks=[]`, with `boolean_value=None`, or with a boolean equal to the draft. `EvidencePolicyCheck.boolean_value` is `StrictBool | None` (`316-344`). `require_evidence_policy_alignment` (`125-131`) only checks that every policy pair is positively proven. Its failure is `SourceCandidateAlignmentValidationError`, not `EvidencePolicyCheckError`.

The retention predicate (`7703-7716`) clears the atom baseline only when candidate cardinality and dispositions match, every changed candidate index appears in some `fully_expressed` receipt, no changed index is also negative, and every policy pair on a changed candidate is positive. `partial_wire = saved_wire` and the `raise` sit outside that predicate. On a raise, lines `7759-7763` never run, so a failed predicate does not roll the sibling back. On a non-raise, those lines still restore the baseline.

`_reviewed_semantic_closure_repair` (`5157-5195`) returns nothing unless the negative statements share one unit, no statement in that unit is unresolved, and every candidate touching the unit has that unit as its entire source set. It does not inspect the retained candidate’s other statements or dependencies.

The runner allowlist is only `PROTOCOL_CONTROL_SOURCE_TARGET_REVIEW_UNRESOLVED` and `PROTOCOL_CONTROL_SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED` (`protocol_control_execution.py:262-268`, `runner.py:244-275`). The deep failure mapper (`4834-4853`) turns the last attempt class into `PROTOCOL_CONTROL_<class>` when that class is in its table. `EVIDENCE_POLICY_UNJUSTIFIED`, `EVIDENCE_POLICY_REVIEW_UNAVAILABLE`, and `SOURCE_CANDIDATE_ALIGNMENT_TRANSPORT_FAILED` are in that table but not in the allowlist. `WIRE_SCHEMA_INVALID`, `INVALID_JSON`, and `REPAIR_SCOPE_ESCAPE` are not in the table, so they persist as `PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID`. `_preserved_negative_alignment_proof` (`3251-3304`) accepts only a last attempt whose class and detail code are exactly the semantic code, whose statement ids equal the current incomplete receipts, and whose units are already in `reviewed_semantic_repair_unit_ids`. Resume reloads that ledger from the diagnostic (`4769-4770`). `_resumable_saved_candidate_alignment` (`2214-2259`) reloads positive receipts only.

The new test’s `reply` axis changes `continue_scoped_unit_repair`, not the policy response. The policy response is always one bound incomplete item with `boolean_value=None`. Candidate 0’s fixture policy is all null / `not_specified`, so `has_explicit_evidence_policy` is false for it; its positive receipt is a semantic alignment, not a policy pair. Candidate 1 sets `requires_contemporaneous_objective_source=True`, so only candidate 1 is a policy pair. The test therefore does not exercise a damaged, duplicate, stale, or field-invalid negative.

### Inference

Damaged, duplicate, and hash-stale receipts do not themselves clear rollback. `reusable_proven_alignment_items` excludes them. A fresh `EvidencePolicyCheckError` also stays outside the new block, so duplicate dimensions and source mismatches keep the generic `EVIDENCE_POLICY_UNJUSTIFIED` code and the baseline. A `decision == "uncertain"` item is not treated as negative.

The hole is a failed fresh read combined with an older incomplete receipt still on `alignment`. `alignment` is reassigned only after `bind_candidate_alignment` succeeds (`7673-7681`). A transport exception, `ValidationError` from bad JSON, or `ValueError` from a duplicate or a pair mismatch leaves the previous alignment in place. If that previous alignment still has a hash-valid `incomplete` item, `negative` is non-empty and the exception is not `EvidencePolicyCheckError`. Recovery then runs. The fresh failure never reaches the transport / schema arm at `7730-7736`. The same fallback can clear the sibling baseline, authorize one source-unit rewrite, and, when no repair is raised, persist `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED`. That persisted code is independent-read eligible. A provenance fault can therefore enter the allowlist. This does not happen on the new test, because candidate 1 has no older incomplete receipt. It does happen if the main-loop alignment at `10219-10252` already stored an incomplete item for a policy pair, including one with no policy checks, and the late re-read then fails. Resume filtering does not close this in-process hole: the filter runs on the next job, not inside this `build_result` call.

A successful incomplete bind has the same authorization power without a policy disagreement. Missing dimensions and a boolean equal to the draft are legal for `incomplete`. The test’s `boolean_value=None` is a disagreement, but the code never requires one.

Positive binding is not whole-candidate. One `fully_expressed` receipt for the changed index is enough when that candidate has no policy pair, which is exactly candidate 0 in the new fixture. A second policy pair that is not positive correctly blocks the predicate. An unresolved statement or definition dependency that is not itself a policy pair is not consulted. The negative unit’s unresolved statements block repair only. Whether a non-policy unresolved statement on candidate 0 can still reach `final_output` was not exhaustively traced.

The typed raise does join the old repair loop without resetting the repair counter first. The handler increments `repairs` once (`11806`). The pre-check uses the existing budget. Scope is replaced from the raised unit, and closure escape at `11210-11217` rejects a union outside that unit. Nonlocals are bound. No new repair channel is added.

The retention predicate is dead on the raise path. Any repairable negative keeps the current wire, including a sibling edit the predicate rejected. The predicate matters only when the function returns: unavailable channel, ledger hit, budget exhausted, or non-unique closure. The test’s unavailable case still keeps candidate 0 because its predicate happens to pass, not because both paths share one guard.

Unavailable, bad JSON, escape, and a second negative behave differently:

- Unavailable channel: no raise, ledger unchanged, sibling kept when the predicate passes, last class `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED`. Other units may continue. Preserved-proof restart fails because the unit was never written to the ledger. A later diagnostic resume can still attempt the one repair.
- Bad JSON and scope escape: the raise writes the ledger first, then the existing splice fails. The last class is the schema or `REPAIR_SCOPE_ESCAPE` class, persisted as `PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID`, which is not allowlisted. The diagnostic carries the ledger and the partial wire, so resume can continue without a second scoped repair. They are not preserved-negative restarts.
- Second negative in the same run: the ledger blocks the raise. There is no second call. The baseline clear still happens before that check.

No `adopted=True` was added. A successful splice still hydrates and passes the output validator. Gate, proof, and independent-read stop lists were not edited.

### Recommendation

Do not rerun for acceptance until the recovery entry is tied to the fresh response.

1. Enter the block only after this attempt’s `bind_candidate_alignment` has replaced `alignment`, and only when the exception is the missing-positive failure from `require_evidence_policy_alignment`. A transport error, `ValidationError`, duplicate `ValueError`, or `EvidencePolicyCheckError` must keep today’s non-semantic code and must not clear the baseline.
2. Put `partial_wire` assignment, `latest_*` assignment, and the raise inside the retention predicate. If the predicate fails, leave the baseline in place and do not raise.
3. Require the bound incomplete checks to cover `_evidence_policy_dimensions` and to disagree with the draft, or explicitly accept `decision == "incomplete"` with empty checks as the contract. The current test does not decide that.
4. Add four focused cases before a real rerun: fresh bad JSON, transport failure, and duplicate item, each with and without an older incomplete receipt; `EvidencePolicyCheckError` must not retain candidate 0; a ledger that already contains `su-02` must not call `continue_scoped_unit_repair`; an incomplete item with empty checks or a boolean equal to the draft must follow the chosen contract. Assert the last attempt class, not only the surviving proposition.
5. Do not add a framework, a second full-wire read, or an allowlist change. The existing splice is the right repair once the entry condition is true.

### Uncertainty

- Reachability of a non-policy unresolved statement on the retained candidate all the way to `final_output` was not closed. The predicate gap is visible; a concrete publication path was not.
- The writer that chooses `preserve_unresolved` versus `resume_partial` was not read. Eligibility above is the runner allowlist plus the preserved-proof predicate.
- `app/services/protocol_control_restricted_source.py` names the same semantic code. It was not part of the declared consumer set and was not read.
- The assignment’s 15-pass window was not reproduced here.

### Objections, decision points, and questions

The highest-impact objection: “valid bound negative” is implemented as “any still-hashing incomplete item currently sitting on `alignment`.” A failed re-read satisfies that. The sibling-retention comment describes a guard that the raise does not use.

Proposed remedy is the three-line tightening above, not a new recovery stack.

Decision points for Codex:

- Is an older incomplete receipt allowed to authorize recovery when the fresh policy call fails? Provisional safe path: no.
- Must a negative policy receipt disagree on every declared dimension? Provisional safe path: yes, before the first real rerun.
- If the retention predicate fails, may the raise still keep the sibling edit? Provisional safe path: no.

Bounded question: for a main-loop incomplete item with no `evidence_policy_checks`, followed by a late policy response of `{`, should candidate 0 roll back and the last class stay non-semantic? This pass recommends yes. The safe provisional patch is to ignore `alignment` unless this attempt bound it.

### Inspected and not inspected

Inspected: the two-file diff; `build_result` policy block; both semantic-repair raises; closure repair; scoped merge entry; bounded-restore call and closure flag; repair `except` through scoped dispatch; alignment bind, reuse, and policy checks; `has_explicit_evidence_policy`; execution failure mapping, preserved-negative proof, and resume ledger; runner allowlist; the new test, its fixture, and `_synthetic_policy_checks_from_prompt`.

Not inspected: test execution, clinical originals, databases, endpoints, credentials, the reuse-plan writer, `protocol_control_restricted_source.py`, the remainder of `_restore_bounded_wire_repair`, and the unrelated dirty Trellis files in the worktree.
