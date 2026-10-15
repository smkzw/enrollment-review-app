# Codex Conference Review: phase5-slice61an-p804-source-closure-final-independent-review-20260828

Date: 2026-08-28

## Verdict

Pass for the bounded engineering contract. This is not clinical acceptance of D001 p804 and does not authorize publication or replay.

## Boundary Compliance

- The independent reviewer remained read-only and used the same resumable session for all four rounds.
- No model replay, clinical artifact mutation, or control-point publication occurred.
- No fallback route or replacement session was used.
- v8 remains an immutable rejected and unpublished run.

## Participant Outputs Reviewed

- Round 1 identified that source-closure repair authority was inferred from the candidate closure instead of being bounded by the deterministic issue scope.
- Round 2 identified that a control-level finding could lose the candidate seed needed to recover the intended closure.
- Round 3 accepted those repairs but found that mixed source-closure and atom/clinical issues could widen mutable structure-unit and disposition scope.
- Round 4 re-read the final code and accepted the exact spanning-candidate guard and exclusive repair-class ownership. It found no remaining blocker within this bounded contract.

## Conference Panel Review

The review correctly separated repair authority from the model's proposed candidate graph. A source-closure rewrite now requires the full transitive candidate-source union to be contained within the deterministic issue's authorized structure units. Mixed findings no longer combine repair scopes: source closure, ordinary repartition, and atom/clinical repair are serialized, while every finding remains visible in the error message and is re-evaluated in a later round.

## Main-Venue Codex Review

Codex accepted both root-cause findings and implemented them in shared code rather than adding D001-specific rules. The final contract preserves ordinary transitive candidate repartition, source and atom conservation, out-of-scope freezing, and fail-closed behavior before another model call when authority is incomplete.

## Codex Independent Verification

- Focused contract suite: `47 passed in 0.09s`.
- Full product-code suite after the final product change: `1007 passed, 58 warnings in 131.53s`.
- After the final test-only message assertions: focused suite again `47 passed in 0.09s`.
- Python compilation and `git diff --check` passed.
- Hermes conference validation passed for the generated packet and same-session continuation records.
- SHA-256:
  - `app/agents/protocol_control_deconstructor.py`: `55735333bbce470c38068c18b7dab213a9bd4d9988d4b429c21543a15e0b78ff`
  - `app/protocols/protocol_control_repair_errors.py`: `69f0d6c2dddb156681d21119820d075518a61c6dfd3ee0ffd84831bc3cfcbb47`
  - `tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py`: `c113547fca9db2325d41df6f6e41e74a0e1002ea8b1560ed66ecf89bec8d398e`
- This backend-only slice did not require browser or visual acceptance.

## Final Decision

Accept the p804 source-closure repair-authority contract as an engineering prerequisite. Keep `claims_complete=false`; keep v8 rejected and unpublished. Before any new immutable p803-p805 replay, commit a reproducible replay harness, decide the repair-budget policy for serialized repair classes, and make a separate replay go/no-go decision.
