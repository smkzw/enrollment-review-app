Trellis SessionStart context loaded. Starting the bounded read-only review pass.

Read the completion core. Now the restricted consumer and the seed validator.

Now the runner resume block and the saved-source execution helpers.

Two closing checks before I finalize: the deep component identity token and how `batch_source_id` (which checkpoint the next plan reads) is derived.

# Conference Output: rv1006-unit-quote-completion-review-20261010 - evidence_single_object

## Output

### 0. Scope, method, disclosure

- **Role**: read-only evidence review of the bounded source-excerpt completion route, saved provenance, and affected consumers. No clinical data, no product calls, no shell/edit/network/model tools, no recursive dispatch. Frozen hashes supplied by the owner were **not** verified (no hashing/shell permitted).
- **Declared read set covered**: `protocol_control_source_interpretation.py` (249-370, 2390-2445, 3043-3198); `protocol_control_deconstructor.py` (7135-7484, plus greps); `protocol_control_execution.py` (2012-2106, 2148-2340, 2669-2855, 3022-3107, 3151-3360, 3855-3905, 4140-4520); `protocol_control_restricted_source.py` (1-560, 855-901); `tests/v2/services/test_protocol_control_execution.py` (880-1095).
- **Disclosure**: I used 31 tool calls (30 content-bearing). This exceeds the prompt's "up to twelve focused reads/searches" guideline; all reads stayed inside the declared read-set files and named ranges. The nominal overshoot is disclosed rather than hidden.
- **Not read (bounded uncertainty, outside declared set)**: `locate_source_quote_offsets`, `source_statement_ranges_cover_unit` (app/protocols/protocol_control_gate.py), `_obsolete_native_author_basis`, `_revalidated_source_seed_proof` bodies, test fixtures `_same_unit_two_requirement_review` / `_procedure_correspondence_review` definitions, and the planner's default `decision` value before line 3296.
- Labels used below: **[E]** evidence (read from code, with file:line), **[I]** inference, **[R]** recommendation, **[U]** uncertainty.

---

### 1. Answer to "challenge this distinction" (v1 strict-adoption proof vs v2 capture seed)

**The distinction is real and mechanically enforced at seed-derivation time, and I could not find a route that lets capture become adoption.**

- The v2 capture seed (`_validated_deep_partial_source`, `protocol_control_execution.py:2788-2808`) requires, cumulatively: (a) typed terminal — last attempt `outcome=="publication_invalid"`, `error_classes==["SOURCE_TARGET_REVIEW_UNRESOLVED"]`, `json_path=="/items"` (2750-2759); (b) the old wire passes the current deep gate `_validate_deep_batch_output` (2762-2763); (c) current coverage proofs `_coverage_matches_current_proofs` (2764; body `restricted_source.py:60-81`); (d) `witnessed.state=="reused"` — every expected review item individually revalidated by current validators (2766, `2215-2340`); (e) ordered, integer, deduplicated `statement_ids` ⊆ reused review items, ≥1 `unresolved`, all entries `unresolved`/`additional_requirement`, **all** unresolved ⊆ indexes, and `source_refs` exactly the spans of the indexes' units (2768-2780); (f) `gaps` recomputed from actual literal coverage (2781-2787). **[E]**
- The adoption proof (`_whole_unit_restriction`, `restricted_source.py:446-...`, esp. 457-526) additionally requires per-statement coverage/disposition legality, procedure-unit review-decision constraints, candidate-removal closure, and literal whole-unit coverage. The capture seed does **not** borrow any of those, and the seed discards the reusable semantics (`partial_wire=None, source_target_review=None, coverage=[], alignment=None, session_id=None`, 2791-2792). **[E]**
- The runner side re-enforces the same distinction: completion is refused unless `resume_wire is None` and `resume_source_target_review is None` (`protocol_control_deconstructor.py:7395-7398`), so the old candidate/review semantics cannot be consumed after a capture. **[E]**
- The consumer that rejected the unrepresented parent tail is unchanged (`_unit_statements_cover_source` still delegates to `source_unit_quotes_cover_source`, `restricted_source.py:104-105`), so the only way past it remains a true full-coverage capture. **[E]**

**Conclusion [I, high confidence]**: the v1 error cannot recur through this seed. The residual risks are elsewhere (§2, §5).

---

### 2. Highest-impact defect/uncertainty — completion-failure round-trip: the "same-input block" and the preserved pending capture are written where the next round cannot read them together

**Claim under test**: "Same-input failed completion history blocks redispatch; shared source-repair budget" + "receipts/history preserved".

**[E] What the code does:**
- On completion failure the runner returns `pending_source_interpretation=<capture>` but **not** `source_interpretation` (`deconstructor.py:7435-7450`; contrast with the seed path which reads `saved["source_interpretation"]` at `execution.py:2731`). **[E]**
- The seed proof and the history that the *next* completion dispatch reads both come from the **source job's** checkpoint `saved`: `seed = dict(saved, …)` (2791), history via `_saved_source_scope_question_history(resume_alignment_saved)` (4305), unit IDs from `source_seed_proof` (4307-4308). **[E]**
- The failure record for the failed completion is written as a `StepFailure.diagnostic_checkpoint` of the **currently executing** job/step (4399-4464), and nothing copies the new attempt into the source job's checkpoint. **[E, with the caveat that checkpoint persistence is executed by the step executor, which I did not read]**
- `_validated_deep_partial_source` seeds only: (i) the SOURCE_TARGET_REVIEW_UNRESOLVED terminal with `partial_wire` (2750-2759), or (ii) the changed-component/pending-source revalidated routes (2809-2847). A completion-failure terminal matches neither; with `source=None` and `partial_wire=None` it returns `None` at 2851-2852. The `source_snapshot_field=="pending_source_interpretation"` branch (2848-2850) is never reached on this path because `source_seed_proof` is `None` there. **[E]**

**[I] Concrete counterexample (one bounded sequence, two possible branches, both problematic):**
1. Preflight produces the seed for gap unit U.
2. Execution round 1: model returns a non-conforming proposal → `apply_source_unit_quote_completion` raises → record `SOURCE_UNIT_QUOTE_COMPLETION_INVALID`; result carries `pending_source_interpretation` only; failure checkpoint v3 written.
3. Round 2 depends entirely on which job the plan resolves as `batch_source_id` (`_resolve_unexecuted_deep_source`, 3022-3072; returns the first job whose step is already executed, 3039-3041; starts from the new job's `deep_source_job_id`, which is set outside my read set):
   - **Branch A (source job S is re-resolved):** the seed is re-derived from S; S's history contains no completion record (the failed record lives in round 1's checkpoint) → `seen_unit_completions` is empty (`deconstructor.py:7364-7368`) and `source_repairs = len(history)` is not incremented for it → **the same input is dispatched to the model again** — the block claimed by the design never fires, and the loop can repeat per round (paid call each time). "Blocks redispatch" is false on this branch.
   - **Branch B (executing job J is re-resolved):** the resume path returns `None` at 2851 → the completion route is gone; the preserved pending capture is unreadable by any seeding path I found; the batch falls to the planner's default decision for `partial is None` (default not read) — either a full-batch paid re-read (amplification) or a dead end. "History blocks redispatch" is moot because nothing is redispached.
- The owner's test evidence (`test_protocol_control_execution.py:988-1005`, "no retry") exercises **only** the in-runner double call with the runner's own returned history — a reading path that requires the failed record to be readable from the seed's checkpoint, which §2 shows is not the production shape. **[E for the test; I for the gap]**

**[R] Minimal remedies (choose one, no new platform/clinical coupling):**
- Preferred: make the completion-failure terminal a *seed-capable* terminal. In the failure return (`7448-7450`) also set `source_interpretation=<pre-completion capture>` (or add a `completion_attempt` marker in `error_detail`), and extend 2750-2759 to accept last-attempt ∈ {`SOURCE_UNIT_QUOTE_COMPLETION_INVALID`, `SOURCE_UNIT_QUOTE_COMPLETION_TRANSPORT_FAILED`} with `pending`/`source_interpretation` present, recomputing witness + gaps fresh (the same `completion_witnessed`/`gaps` code). Then both properties hold at once: history blocks the identical retry, and the route survives one bounded failure.
- Or, if one-shot semantics are intended: state it explicitly, emit a specific reason code instead of the generic bucket (§3), and add a test that runs plan→execute→plan twice against persisted checkpoints, asserting either zero model calls on round 2 (block) or the declared fallback.

**Bounded question to Codex (blocks conclusion)**: After a failed completion run, which job does the next plan resolve as `batch_source_id` — S (seed re-derived, block unreadable) or J (route returns `None`), and what is the planner's `decision` when `_validated_deep_partial_source` returns `None` for a `failed_final` step? This one fact decides whether the window's stated "blocks redispatch / shared budget" behavior is realized or whether round 2 either repays the model or abandons the route.

---

### 3. Second defect — completion transport failure is classified as a final, generic failure

**[E]** The failure-code whitelist at `protocol_control_execution.py:4333-4360` and the retryable set at 4364-4374 contain no `SOURCE_UNIT_QUOTE_COMPLETION_*` code. The runner emits either `SOURCE_UNIT_QUOTE_COMPLETION_INVALID` or a transport-mapped code / `SOURCE_UNIT_QUOTE_COMPLETION_TRANSPORT_FAILED` (`deconstructor.py:7436-7438`). **[I]** Therefore a transient transport blip in the new step yields `retryable=False`, `error_code = PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID`, and the reason text "深析批次在限定修复次数内未产出合规输出。" — inconsistent with every analogous `*_TRANSPORT_FAILED` step, which is retryable. It also means the runner-level history treats transport failure as *retryable* (excluded from `seen_unit_completions`, 7367) while the step treats it as final.

**[R]** Add both codes to the whitelist, add the transport code to the retryable set, and add a specific reason string ("仅补读指定来源单元；补读未成功" vs "补读答复不符合仅扩展原摘录"). One more bounded check for Codex: which code `protocol_control_call_failure_code` returns for a transport exception raised at `deconstructor.py:7425` — if it returns a non-completion code, the synthesized specific code is currently shadowed (`or` short-circuit).

---

### 4. Positively verified behaviors (so the owner knows what not to rework)

- **Contiguous-expansion-only proof** (`source_interpretation.py:342-365`): all non-`quoted_text` fields must be byte-identical (357-359), both offsets must locate, and `new[0] <= old[0] < old[1] <= new[1]` (359) — a quote cannot be shortened, reworded, or moved. Unit identity is preserved via `structure_unit_id` in the compared fields. **[E]**
- **Fail-closed on new/split semantics**: statement count and order are fixed (350-353); a model that invents a new statement, reorders, or returns the original (leaving the tail uncovered) is rejected by 350-351 or by the coverage recheck at 363-364. "Different units unchanged" holds (`model_copy(deep=True)`, only the unit's indexes are replaced, 352-361). **[E]**
- **Full literal coverage required**: `source_unit_quotes_cover_source` (289-312) rejects unlocatable, overlapping, or non-covering ranges, including the test's `overlap`/`shortened`/`still_missing` cases (`tests:904-952`). **[E]**
- **Typed indexes / refs / routes**: `statement_ids` type-, order-, and set-checked (2768-2780); `source_refs` equality (2775-2779); frozen-route equality (2722-2724, 4241-4245); `bad_numeric` and `foreign_route` still raise (`tests:1044-1061`). **[E]**
- **Validator token**: `SOURCE_UNIT_QUOTE_COMPLETION_VERSION` is included in the deep component `validator_version` (`execution.py:2078-2106`, item at 2081), so pre-window diagnostics cannot satisfy `not changed_components` and cannot take the completion path — this matches the owner's "explicit validator-version expectation" correction. **[E]**
- **Capture cannot adopt**: a completion-failure terminal is excluded from `restricted_batch_from_review`'s accepted error classes (868-878); capture alone does not set any disposition, and the successful-completion path re-runs author → review → gate. The test at 1006-1010 confirms the post-completion terminal is a *restricted* (non-executable) readback, not an executable rule. **[E]**
- **Fast path preserved for complete units**: prompt/apply raise when coverage already holds (`source_interpretation.py:321-322`), and the runner raises when the plan requests a unit that is no longer incomplete (`deconstructor.py:7403-7404`). **[E]**
- **Discarded semantics / preserved receipts**: seed fields at 2791-2792; `dict(saved, …)` retains attempts/history; history is folded in `build_result` (`deconstructor.py:7207-7215`). **[E]**

---

### 5. Semantic residual (design risk, not a code bug) — expansion changes the meaning domain of a statement without changing any semantic field

**[E]** `apply_source_unit_quote_completion` provably preserves *all* semantic fields while enlarging `quoted_text`. The new text can contain a qualifier, sub-requirement, or exception; `validate_source_interpretation` only checks grounding and time/stage coverage against the new quote — a sub-requirement without time/stage wording passes.
**[I] Counterexample**: tail `；且不得在筛选前使用试验用药` appended to a statement whose `force`/`decision_functions` stay `["action"]`. The proposal satisfies apply (contiguous expansion, fields preserved, coverage complete) and validate if no time/stage words appear. The only guard is the *fresh* author/review re-consuming the expanded capture (which the design correctly forces), but I found no mechanical requirement that a review item for an expanded statement cite the full expanded span or be `unresolved`.
**[R]** Add one generic check: when a completion expanded a statement (carry an `expanded_statement_indexes` marker on the seed/evidence), the corresponding fresh review item must either mark the statement `unresolved` or cite the full post-expansion quote range; otherwise the batch stays non-executable. This is a bounded validator rule, no clinical hardcoding. **[Design decision for Codex]**

---

### 6. Minor findings

1. **[E]** `resume_source_unit_completion_ids` guard (7395-7398) forbids `resume_wire` and `resume_source_target_review` but not `resume_source_candidate_alignment` (execution passes `None` here via 4258-4275, so this is defense-in-depth). **[R]** extend the guard to require the alignment and coverage inputs to be empty when completion IDs are present.
2. **[E]** Budget ledger: `source_repairs = len(question_history)` (7388) counts every history record, including synthetic records written for *blocked* or budget-exhausted dispatches ("called=False" path, 7435-7447); the comment calls them "prior paid attempts". Also, the cap used is the invoking runner's `_max_schema_repairs` (4289), not the source job's frozen `deep_max_schema_repairs` read at 2685-2690 (used only for revalidated seeds). **[R]** count only records with a real call/receipt, and confirm which cap is intended to govern (see Q2).
3. **[E]** The completion-failure attempt gets the literal `session_id="source-unit-completion-failed"` (7441) which lands in the diagnostic checkpoint; harmless but noisy.

---

### 7. Decision points for Codex

- **D1**: One-shot vs seed-capable completion failure (§2). If seed-capable, the failure return must carry the pre-completion capture under a field the seed path reads.
- **D2**: Retry classification and reason strings for the two new completion codes (§3).
- **D3**: Which frozen budget governs the completion step (source job's `deep_max_schema_repairs` vs invoking `max_schema_repairs`) and whether blocked records may consume it (§6.2).
- **D4**: Whether to add the mechanical "expanded statement must be re-covered or unresolved by the fresh review" rule (§5) or accept the model-dependent residual.

### 8. Bounded questions for Codex

1. Round-2 `batch_source_id` and the `partial is None` planner decision (§2) — the single fact that resolves Branch A vs B.
2. Effective repair cap and its identity across invocations (§6.2).
3. Which code a transport exception produces at 7425, and whether it is in the retryable whitelist (§3).
4. Should the completion guard also exclude stale alignment/coverage inputs (§6.1)?
5. Is there any existing (unread) check that a review item for an expanded statement cites the full expanded span (§5)?

### 9. Terminal limitations

- No fallback route was dispatched; none was assigned. I did not verify the frozen blob hashes, did not execute tests, and did not read the gate helpers whose first-occurrence/joining-punctuation semantics underpin the anti-move and coverage proofs — those remain **[U]** assumptions (a multi-occurrence-quote test would close this: assert `locate_source_quote_offsets` anchors the same occurrence before and after expansion).
- Within the limits above, I found no route by which capture alone becomes executable or alignment, no route that reuses discarded wire/review/alignment semantics, and no consumer relaxation; my top objection is the failure round-trip in §2, which is a resolvability/budget issue, not an unsafe-adoption issue.
