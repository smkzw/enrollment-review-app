Round 4: re-reading the current worktree. First the repair-errors module (exclusive-ownership rule), then the tests.

The exclusive-ownership rule is in place in both functions. Now reading the spanning-candidate negative test and the mixed tests.

Mixed tests now pin the cross-unit exclusion. Reading the spanning-candidate negative runner test.

Spanning-candidate test confirmed. Checking whether message preservation of deferred issues is asserted anywhere.

Message preservation is implemented but not assertion-pinned. Re-verifying the authority guard section in the current deconstructor (hash unchanged per Codex — confirming no drift).

All four verification targets confirmed in current code. Returning the round-4 report.

---

# Conference Participant Output: phase5-slice61an-p804-source-closure-final-independent-review-20260828 - general_single_object (Round 4, current-code acceptance)

## Boundary Check

- Read-only: no files modified, no model replay, no control point published. All observations from the current worktree via Read/Grep.
- Bash denied → test counts/hashes are **Codex-reported evidence**, marked as such; code reading is independent.
- Deferred items kept outside this acceptance: replay harness, repair-budget policy, production wiring, a new immutable D001 replay. v8 remains rejected, immutable, unpublished.

## Current-Code Verification

### 1. Spanning-candidate F1 case fails closed before a second model call — YES

**Observed code** (`app/agents/protocol_control_deconstructor.py:2576-2632`): unchanged from round 3 — `closure_candidate_source_union <= source_closure_authority` (`set(error.structure_unit_ids)`) feeds `source_closure_authority_escape` → `repair_scope_unknown` → immediate 需要核对 return (`:2706-2721`), no `continue_session`.

**Observed test** (`test_slice61ab...:767-816`): now constructs a **literal spanning candidate** — `source_structure_unit_ids: ["su-01", "su-02"]`, `source_span_ids: ["span:01", "span:02"]` — while the issue authorizes only `("su-02",)`. Trace: seed key `("su-01","su-02")` → closure union `{su-01, su-02} ⊄ {su-02}` → escape → single attempt, `status == "需要核对"`, "缺少完整的机器可读修订范围" appended. Single-response `_FakeTransport` proves **no continuation call**. The exact F1 shape is now pinned (my round-3 precision gap is closed).

### 2. Mixed issues cannot widen candidate/source-unit/span/disposition authority — YES

**Observed code** (`app/protocols/protocol_control_repair_errors.py`): exclusive-ownership rule at `:56-70` (closure class wins, forces `allow_candidate_repartition=False`; else repartition class; else all issues). The scope loop (`:75-114`) iterates only `repair_scope_issues`, so only the owning class contributes `candidate_ids`/`structure_unit_ids`; spans are structurally zeroed for both structural classes (`:120-124`). `combined_repair_error` applies the same rule (`:152-162`) and now takes ids/units **only from `repair_scope_errors`** (`:166-179`), closing my round-3 residual: an atom issue on another unit can no longer enter `structure_unit_ids` → `mutable_structure_unit_ids` cannot be widened → disposition authority stays within the owning class.

**Observed tests**: `test_scope_split_drops_atom_spans_from_other_publication_issues` (`:453-485`) and `test_combined_source_closure_repair_drops_other_atom_spans` (`:488-509`) now use an unrelated issue on `su-01`/`pcc-other` and assert only `su-02`/closure candidates remain (`candidate_ids`, `structure_unit_ids`, spans `()`).

### 3. Messages preserve all findings; deferred issues reappear next round — IMPLEMENTED, partially tested

**Observed code**: `publication_repair_error` message = all issues (`:74`); `combined_repair_error` message = all active errors (`:165`). Deferred issues are never repaired this round; restore freezes their units to baseline, so the deterministic gate re-raises them on the next validation round (serial-round mechanism).

**Test gap (non-blocking)**: no assertion pins that `str(error)` contains the deferred issue text, and no runner test exercises a deferred atom issue actually re-firing in round 2 and driving a second repair round. Recommendation: add `assert "RECORD_PRECISION_COMPRESSED" in str(error)` to the mixed tests, and optionally a two-round runner test.

### 4. Repartition remains transitive; source/atom conservation unchanged — YES

**Observed**: deconstructor hash identical to round 3 (`55735333…`, Codex-reported) and I re-read the authority guard byte-for-byte — unchanged, including transitive closure for both classes (`:2584-2603`) and the escape gated strictly on `allow_source_closure_rewrite`. Restore/validate conservation (union equality, crossing rejection, out-of-closure freeze, atom coverage) untouched. The repair_errors change only restricts *which issues* contribute to a round, not repartition semantics: a repartition issue in a report with atom issues still gets its own full transitive scope; atom issues serialize into a later round. Clinical repair (`:130-137`) likewise now defers after a structural class in `combined_repair_error` — consistent with exclusive ownership and safe (restore freezes).

### 5. Remaining correctness blockers — NONE

Non-blocking residuals: (a) duplicated dead condition `or not closure_candidate_source_union` (`deconstructor.py:2614-2615`); (b) message-preservation/round-2-reappearance test gap (item 3); (c) control-scope originating candidate spanning units beyond the gate issue → fail-closed manual review (intended, documented); (d) serial rounds consume `max_schema_repairs` — budget policy explicitly deferred.

## Evidence And Assumptions

| Item | Evidence | Status |
|---|---|---|
| Authority guard unchanged | deconstructor `:2576-2645` re-read; hash `55735333…` identical to round 3 | OBSERVED + CODE-REPORTED |
| Spanning negative test | test `:767-816` literal `["su-01","su-02"]` candidate, authority `("su-02",)`, 1 attempt | OBSERVED |
| Exclusive ownership | repair_errors `:56-70`, `:152-162`; ids/units from owning class only `:166-179` | OBSERVED |
| Cross-unit exclusion tests | `:453-485`, `:488-509` (su-01/pcc-other excluded) | OBSERVED |
| Message preservation | repair_errors `:74`, `:165` (all findings) | OBSERVED; not assertion-pinned |
| Repartition/conservation | deconstructor unchanged; restore `:2121-2162` (round-3 re-read) | OBSERVED + CODE-REPORTED |
| 47 focused / 1007 full / compileall / diff-check; hashes `69f0d6c2…`, `f36817fd…` | Codex-reported | CODE-REPORTED, **not re-run by me** |

Inference: the delta between rounds 3 and 4 (repair_errors `c5453a8d…` → `69f0d6c2…`, tests `2c13721a…` → `f36817fd…`, deconstructor unchanged) matches exactly the two repairs Codex described. Assumption: the worktree I read is the state Codex tested.

## Remaining Blockers

- **None within the bounded contract.**
- Deferred (not completed): committed replay harness; repair-budget policy (serial rounds now make multi-class reports budget-sensitive; default `max_schema_repairs=2`); production wiring of the runner/repair pipeline; one new immutable D001 replay under Codex's decision. v8 p804 remains clinically rejected, immutable, unpublished.

## Recommended Disposition

**Accept.** The spanning-candidate F1 case now fails closed before any second model call and is pinned by a literal-spanning test; mixed issues cannot widen candidate, source-unit, span, or disposition authority (both at publication and combined level); all findings remain in the error message with deferred issues structurally reappearing on the next round; ordinary candidate repartition stays transitive within its own class and source/atom conservation is untouched. This is **engineering acceptance only** — no clinical acceptance of v8 p804, no control point published, no replay authorized.

Non-blocking follow-ups for the next slice: (1) pin message preservation (`assert deferred code in str(error)`) and add a two-round runner test where the deferred atom issue re-fires; (2) delete the duplicated condition; (3) finalize the repair-budget policy given serial rounds; (4) commit the replay harness before any replay go/no-go.
