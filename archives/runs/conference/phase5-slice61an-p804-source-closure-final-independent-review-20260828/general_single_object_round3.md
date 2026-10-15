Round 3: re-reading the current worktree (post-remediation) rather than trusting prior line numbers. Starting with the runner's authority check.

The authority check is in place. Now reading the three named tests to verify Q2/Q3 behavior.

The negative runner test is exactly the F1 spanning case — verifying the helpers actually construct a spanning candidate.

The negative test's seed candidate appears to be su-01-only. Verifying `_wire()` — whether it rewrites candidate source units to span both.

`_wire()` doesn't touch candidate source units — the negative test's seed candidate is su-01-only (disjoint-mismatch shape), while the authority check itself is a general set-inclusion test covering the spanning shape. Now re-verifying the restore/conservation code is unchanged.

The restore branch is byte-identical in behavior to round 1. Reading the tail of the scope assignment to complete Q4.

All verification complete. I have the full current-code picture. Returning the round-3 report.

---

# Conference Participant Output: phase5-slice61an-p804-source-closure-final-independent-review-20260828 - general_single_object (Round 3, current-code acceptance)

## Boundary Check

- Role: `general_single_object` (codebuddy-cli / deepseek-v4-flash / max). Read-only: no files modified, no model replay, no control point published. All observations from the current worktree via Read/Grep.
- Bash remains denied → I could not re-run suites or recompute hashes. Test counts and SHA-256 values below are **Codex-reported evidence**, marked as such; my code reading is independent.
- Scope of this acceptance: the bounded source-closure contract only. Deferred production wiring, committed replay harness, repair-budget policy, and a new immutable D001 replay are **explicitly outside** this acceptance and remain future prerequisites. Engineering acceptance here does **not** mean v8 p804 clinically passed; v8 stays immutable, rejected, unpublished.

## Current-Code Verification

### Q1. Does the authority check close F1 (including a spanning candidate)?

**Observed code** (`app/agents/protocol_control_deconstructor.py:2576-2632`): the transitive candidate-key closure is still computed over all baseline candidates, but now `closure_candidate_source_union` is compared against `source_closure_authority = set(error.structure_unit_ids)`:

```python
source_closure_authority_escape = (
    error.allow_source_closure_rewrite
    and (
        not source_closure_authority
        or not closure_candidate_source_union
        or not closure_candidate_source_union <= source_closure_authority
    )
)
```

`source_closure_authority_escape` feeds `repair_scope_unknown`, which returns 需要核对 immediately (`:2706-2721`) without a repair prompt.

**Answer: YES, F1 is closed.** The guard is a general set-inclusion test, so both F1 shapes fail closed: (a) disjoint mismatch (seed unit ≠ authorized unit) and (b) **spanning candidate** — a candidate key `{p804, p805}` produces union `{p804, p805} ⊄ {p804}` → escape. Authority is bounded by the gate issue's `structure_unit_ids`; the seed candidate's own frozen units do **not** widen it (repair_errors only adds seed units when the issue carries none — `protocol_control_repair_errors.py:75`), so no silent unfreeze of a must-freeze unit is possible.

**Test-precision caveat (not a blocker):** the named negative test `test_scope_split_runner_rejects_source_closure_beyond_issue_authority` constructs the **disjoint-mismatch** shape, not the literal spanning shape — its seed candidate has `source_structure_unit_ids=["su-01"]` (inherited from `_deconstructor_candidate()`; `_wire()` does not modify source units), authority `("su-02",)`. The spanning shape hits the identical code path, but is not pinned. Recommendation: add a variant with a candidate key `{su-01, su-02}` and authority `("su-02",)` to pin the exact F1 scenario Codex described.

### Q2. Positive merge test and negative no-second-call test

**Observed tests** (`test_slice61ab_candidate_repartition_contract.py`):

- `test_scope_split_runner_uses_source_closure_not_atom_repair` (`:631`): batch restricted to `su-02`; two same-unit candidates; validator raises closure issue (`structure_unit_ids=("su-02",)`) **plus** an atom issue (`RECORD_PRECISION_COMPRESSED`, spans dropped by mutual exclusion); `_FakeTransport` carries exactly two responses (baseline wire, then merged wire); asserts `status == "已解析"`, `len(final_output.candidates) == 1`, `validator_calls == 2`. This proves: legal same-unit merge through the **real runner loop** (parse → restore → hydrate → validate → one repair `continue_session` → re-validate), and that the mixed report took the closure path, not the atom path.
- `test_scope_split_runner_rejects_source_closure_beyond_issue_authority` (`:763`): transport carries **one** response; asserts `status == "需要核对"`, `len(result.attempts) == 1`, outcome `publication_invalid`, and the "缺少完整的机器可读修订范围" issue. A single attempt with a single-response transport proves **no second model call** on authority escape.

**Answer: YES on both counts.** The assertion set pins the exact behaviors (merge outcome, mixed-report routing, repair-round count, no-call-on-escape).

### Q3. Does the control-scope test close C3?

**Observed test** `test_control_scope_gate_issue_seeds_originating_candidate_closure` (`:532`): runs `_check_conditional_exemption_scope_split(controls, candidate_scope=False)` on two controls (`control-screening`/`control-validity`, each with `originating_candidate_id`); asserts the gate issue shape (`code`, `entity_id == "control-screening"`, `candidate_ids == ()`); feeds that issue through `publication_repair_error` with `control_to_candidate` built from `originating_candidate_id`; asserts `allow_source_closure_rewrite is True`, `candidate_ids == ("pcc-screening",)`, `structure_unit_ids == ("su-02",)`.

**Answer: YES, C3 is closed** from gate issue shape → originating-candidate mapping → repair seed. The runner's downstream consumption is issue-shape-agnostic and already covered by the candidate-scope runner tests. Optional (non-blocking): a runner-level control-scope integration test would be belt-and-braces only.

### Q4. Did the repair weaken repartition or conservation?

**Observed:** `protocol_control_repair_errors.py` hash is unchanged from 61am (`c5453a8d…` — Codex-reported), so mutual exclusion and seed logic are untouched. I re-read `_restore_bounded_wire_repair` closure branch (`:2121-2162`): union conservation (`current_union != mutable_candidate_source_union` → escape), crossing-candidate rejection, out-of-closure freeze — all intact. The runner's authority escape is gated strictly on `error.allow_source_closure_rewrite`, so **ordinary candidate repartition remains transitive and unbounded**, exactly as before; `mutable_candidate_source_keys = closure_candidate_source_keys` and `mutable_structure_unit_ids.update(union)` behave identically for repartition.

**Answer: NO weakening.** Atom-span coverage, source-union conservation, and repartition semantics are unchanged; the only change is the runner's scope determination.

### Q5. Remaining correctness blockers in the bounded contract

**None found.** Residual observations (all non-blocking or pre-existing):

1. Duplicate dead condition `or not closure_candidate_source_union` (`:2614-2615`) — harmless; cleanup only.
2. Negative test pins the disjoint-mismatch shape, not the spanning shape (Q1 caveat) — add a spanning variant.
3. Control-scope originating candidate spanning units beyond the gate issue's unit(s) → `closure union ⊄ authority` → fail-closed manual review. This is intended conservative behavior; document it.
4. Pre-existing (not introduced here): a mixed report whose atom issue sits on a **different unit** than the closure issue puts both units into `mutable_structure_unit_ids`, so dispositions on the non-closure unit are not frozen by restore (the gate still bounds disposition kinds). Residual, gate-bounded, unchanged from round 1.

## Evidence And Assumptions

| Item | Evidence | Status |
|---|---|---|
| Authority check semantics | deconstructor `:2576-2632` (set-inclusion guard into `repair_scope_unknown`) | OBSERVED |
| Fail-closed, no second call | `:2706-2721` + negative test single-response transport | OBSERVED |
| Positive runner merge | test `:631-760` (1 candidate final, validator_calls==2, 2 responses) | OBSERVED |
| Negative runner escape | test `:763-804` (1 attempt, 需要核对, scope message) | OBSERVED |
| Control-scope C3 chain | test `:532-592` (gate shape → originating map → seed) | OBSERVED |
| Conservation/repartition unchanged | restore `:2121-2162` re-read; escape gated on closure flag only | OBSERVED |
| Negative test shape | `_mixed_decision_initial_wire`/`_deconstructor_candidate` source units = `["su-01"]`; `_wire()` no source rewrite | OBSERVED (spanning shape not pinned) |
| repair_errors hash unchanged | `c5453a8d…` (Codex-reported, matches 61am) | CODE-REPORTED, consistent |
| 47 focused / 1007 full / compileall / diff-check | Codex-reported | CODE-REPORTED, **not re-run by me** |
| Deconstructor hash `55735333…`, tests `2c13721a…` | Codex-reported | CODE-REPORTED, **not re-hashed by me** |

Inference: the runner-only delta between the 61am hash (`3f5e6d00…`) and the current deconstructor hash is consistent with the ~40-line scope-determination change I read. Assumption: the worktree I read is the same state Codex tested.

## Remaining Blockers

- **None within the bounded source-closure contract.**
- Deferred (explicitly outside this acceptance; not completed work): committed replay harness; repair-budget policy (default `max_schema_repairs=2` is still below the 5 attempts v8 consumed); production wiring of `ProtocolControlAgentRunner`/`replay_validation_error`; one new immutable D001 model replay under Codex's decision. v8 p804 remains clinically rejected, immutable, unpublished — unchanged.

## Recommended Disposition

**Accept the remediation.** F1 is closed by the authority check (general set-inclusion, covering both disjoint-mismatch and spanning-candidate shapes), C3 is closed by the control-scope gate→seed test, the positive/negative runner tests prove legal merge and no-second-call-on-escape respectively, and no weakening of repartition or source/atom conservation was found. This is **engineering acceptance only** — it does not make v8 p804 clinically acceptable, does not publish any control point, and does not by itself authorize a replay.

Non-blocking follow-ups for the next slice: (1) add the spanning-candidate variant of the negative runner test; (2) delete the duplicated condition; (3) document the fail-closed control-scope multi-unit behavior; (4) before any replay decision, commit the harness with an explicit repair budget ≥ 5 and re-run the suites/hashes.

Codex's go/no-go on a new immutable D001 replay may now proceed on the basis of this acceptance plus the deferred prerequisites; the conference does not itself authorize the replay.
