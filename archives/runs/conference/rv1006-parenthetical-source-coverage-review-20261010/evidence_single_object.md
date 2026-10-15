Trellis SessionStart context loaded. Executing the bounded read-only review under the stated limits — reads only, no delegation, max 8 read/search calls, report returned as text.

Locations identified. Now executing the remaining four reads (budget: 8 total, 4 used).

Review complete. 8/8 read/search calls used, all within the permitted set. Report below.

---

# Bounded independent engineering review — parenthetical prohibition presence branch (v48)

Artifact reviewed: working-tree code (uncommitted patch on ea69c598) as directed. No tests executed, no diff read (outside permitted set), no clinical/semantic evaluation performed. This is engineering advice, not medical approval.

## Findings

### F1 — BLOCKING (protection not established): the changed layer admits a parenthetical-only prohibition atom without any check for the sentence's governing condition

- `app/protocols/protocol_control_gate.py:226-253` `_parenthetical_prohibitions_are_quoted`; consumed at `protocol_control_gate.py:4929-4932` inside `_uncovered_enrollment_prohibitions` (`4861-4982`). Returning `True` executes `continue` (4932), suppressing `ENROLLMENT_PROHIBITION_UNCOVERED` for the entire clause.
- The predicate directly enforces only: well-formed literal paren pairs (231-233), no prohibition keyword remaining outside parens (235), and every prohibition-keyword parenthetical exactly atomized — statement == fragment and excerpt == fragment (normalized), on nonempty span sets that are subsets of the unit's spans (242-252).
- It enforces nothing about the non-parenthetical remainder. The governing conditional and permission text are simply no longer required to be quoted at this layer.
- **Dangerous counterexample** (using the patch's own fixture, `tests/v2/protocols/test_slice58c_protocol_control_gate.py:439`): sentence `筛选期发现检查异常时，允许复核（复核前不得改变原有治疗方案），结果正常后进入后续流程。` with candidate carrying only atom `{statement: 复核前不得改变原有治疗方案, excerpts: [同上], spans: ["span"]}`. The branch returns `True`; the outer condition `筛选期发现检查异常时` and permission `允许复核` are unrequired. If the candidate has no trigger/condition atom quoting the outer conditional, **nothing I inspected at the coverage layer rejects it**.
- The decisive conditional-integrity check, if any, is candidate-level: `_check_conditional_branch_mapping` (invoked at `gate.py:4312`, receives source `units` + trigger + obligation) and `_check_branch_scope_and_paired_consequences` (`gate.py:4467`). These run on the same path (`_validate_candidate` → `check_protocol_control_batch_candidates:5346-5360`; re-run at publication `5513`), so the branch does not remove them — but **their bodies were outside my permitted/budgeted read, so decisive rejection is assumed, not proven.**
- Exact missing evidence to resolve: the body of `_check_conditional_branch_mapping` and the test at `test_slice58c_protocol_control_gate.py:1837` (`test_single_condition_action_pair_requires_an_explicit_trigger`). Question to answer: does a unit of the fixture's shape force an explicit trigger atom and fail without it? If yes, F1 downgrades to a documented delegation. If no, F1 is a confirmed blocking defect and the minimal fix below is required. Per the stated rule, this cannot be cleared as protective from what was inspected; do not freeze v48 as protection-complete until this one read is done.

### F2 — Positive counterexample (intended behavior works)
Same fixture; branch returns `True` → 0 coverage issues for both fullwidth and ASCII paren forms (authored expectations `slice58c:429` rows `fullwidth`, `ascii` = 0). Scope is literal presence only; `slice58c:479-480` states this explicitly. Code-read inference + authored test source, not executed.

### F3 — Nested / mismatched / outside / punctuation / wrong source: all conservative (fail toward strict)
- Outside prohibition keyword anywhere in remainder → `False` (235) → strict whole-sentence demand (row `outside_prohibition` = 1).
- Nested: `[^（）()]+` cannot cross a paren, and residual paren chars after substitution (233) force `False` → strict (row `nested` = 1).
- Mismatched pair: no fragment matches / residual chars → `False` → strict (row `mismatched` = 1). A fullwidth-open/ASCII-close mix is likewise never a recognized pair — conservative, though that exact combination is untested.
- Wrong source: nonempty span set ⊆ `unit.source_span_ids` required (244-246) (row `wrong_source` = 1).
- Changed action or dropped qualifier inside the parenthetical → exact normalized equality fails (247-249) (rows `changed_action`, `missing_qualifier` = 1).
- Consequence: the branch can only relax when *every* lexically detected prohibition in the clause is exactly atomized inside well-formed parens; any doubt falls back to the strict path. No partial acceptance.

### F4 — Multiple parentheticals and preservation of independent findings
- `for fragment in prohibitions` (242-252) requires an exact atom per prohibitive fragment; one atom cannot cover a second parenthetical (row `second_missing` = 1). Confirmed by code.
- Collector preserves independent findings: `check_protocol_control_batch_candidates:5346-5362` appends every candidate's error and returns all issues (batch identity/scope mismatch and `_check_conditional_exemption_scope_split` remain first-error-only, by design per docstring `5315-5318`). Service wrapper `app/services/protocol_control_execution.py:1943-1975` converts **all** errors and now passes `source_excerpt_sha256` through (`execution.py:1968`) — the copy side of the hash fix is directly present. Whether `ProtocolControlGateError` populates the hash for the `ENROLLMENT_PROHIBITION_UNCOVERED` construction path is unverified: `gate.py:4969-4979` passes no hash argument and the model/constructor was not read.
- `break` at `gate.py:4981` reports only the first uncovered clause per unit per pass — pre-existing, not introduced by this patch; do not attribute it to v48.
- `tests/v2/services/test_protocol_control_execution.py:2848` was not read (budget); independent-candidates-together behavior is supported by the service code path but not independently confirmed by that test.

### F5 — Time errors
The branch contains no time logic. `_check_time_constraints` (`gate.py:4474-4488`) still runs per candidate on the same path. Nothing here waives or borrows time; the separate missing-time error on another atom is untouched by this change.

## Proof vs assumption

- **Proven by direct read**: conservative fallbacks (nested/mismatched/outside/wrong-source/text-change); per-fragment exact-atom requirement; branch cannot fire with any prohibition keyword outside parens; suppression is limited to one diagnostic code; candidate and publication validation paths remain invoked unchanged; service conversion keeps all errors and copies the error hash.
- **Assumed, not proven**: that `_validate_candidate` (or later source/semantic review) decisively rejects a parenthetical-only prohibition atom that drops a governing conditional from the same sentence. The synthetic presence test (`slice58c:428-480`) proves presence only, never trigger/exception equivalence — it is not clinical acceptance and is not presented as one.

## Minimal source-preserving change (only if the F1 confirmation read fails)

In `_parenthetical_prohibitions_are_quoted` (`gate.py:226-253`), add a governing-context condition per prohibitive fragment: pass only if either (a) the clause text preceding the fragment contains no condition/exception cue, or (b) some atom of the same linked candidates (same exact-quote and span rules) additionally quotes the governing conditional text verbatim, else return `False` (strict fallback). The existing cues (`_CONDITIONAL_SUBJECT_RE` 370, `_EXCEPTION_CUE_RE` 388) do not match the fixture's `…异常时` form, so the cue set needs the temporal-conditional extension, e.g. text preceding the parenthetical matching `[^，。；]{1,48}(?:时|后|前)[，,；;]`. Deterministic, source-bound, no model/threshold/budget change, no new prompts. Alternative equivalent placement: enforce the same requirement inside `_check_conditional_branch_mapping` for parenthetical-prohibition obligations, if that check is the intended home.

## Evidence limitations

- 8/8 calls used; not read: `_check_conditional_branch_mapping`, `_check_branch_scope_and_paired_consequences`, `_check_dnf`, `_check_exception_layer`, `_PROHIBITION_WORD_RE`, `_normalize_prohibition_quote`, `_fail` tail, `ProtocolControlGateError` hash population, slice58c tests 218-385, and the service test at line 2848. The exact missing evidence for the blocking decision is named in F1.
- No diff vs ea69c598 was inspected; "changed" attribution follows the prompt, not a diff review. No tests, browser, network, clinical documents, databases, logs, env, or other tasks were accessed. No model-identity, clinical-review, or acceptance claims are made.
