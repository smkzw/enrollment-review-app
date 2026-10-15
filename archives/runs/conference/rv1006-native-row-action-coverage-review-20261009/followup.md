# Continuation Report: rv1006-native-row-action-coverage-review-20261009 - evidence_single_object

## Corrections (retractions first)

**R1 — My blocking finding was wrong. Retracted.**

I misread the set comprehension at `protocol_control_source_interpretation.py:2388`. The condition is `if text.strip() and index != 0`, so the label column (index 0) is excluded as the read now shows directly:

```python
nonempty = {index for index, text, _refs in values if text.strip() and index != 0}
if (not labels or not nonempty or nonempty != {column.column_index for column in columns}
        or any(column.marker_footnotes or column.visit_unresolved for column in columns)):
```

For "材料分发及回收 | X" with the mark at c2: `nonempty = {2}`, `{column.column_index} = {2}` → the guard passes. My earlier claim of `{0,2}` was a reading error on my side, not a code defect. **Withdrawn in full.** The three positive label variants and the helper path are consistent with the owner's test result; no fix is needed and none should be invented. My "must-fix" §1 disappears, and with it the derived claim that the helper was inert.

**R2 — Verifiability note (superseded).** My first-round source-trace conclusion (helper returns False on the positive case) was reached without execution and was wrong; I note this to keep the evidence trail honest.

**R3 — Identity/reuse objection recategorized, not deleted.** Re-reading `_alignment_input_identity` (`candidate_alignment.py:359-388`), the native-row branch does include `NATIVE_TABLE_ALIGNMENT_CONTEXT_VERSION` (`:374`), and `reusable_proven_alignment_items` calls `validate_candidate_alignment(...)` at `:441` **before** comparing `_alignment_input_identity` at `:442` and the response hash at `:445`. So per-item reuse is both gate-current and identity-bound. My §2 conflated two different guarantees; correction below.

**R4 — Scope-recheck reading confirmed (from R4 read).** `can_recheck_source_scope_question` (`:412-429`) admits a readable header as a question only (`:427-429` comment: "enough to ask a question, not to prove its scope"); `apply_source_scope_question_recheck` (`:462-488`) restricts changed fields to `{unresolved, scope_quote, affected_stage, time_words}` (`:473-476`) and, for native rows, routes through `apply_source_scope_correction` (`:479-484`). I did not find a route from a readable-but-unmapped early-exit header to an adopted mapped visit without passing the existing correction gate. Consistent with the owner's statement.

## Verification of the two distinctions

**Current-gate verification vs model input/response identity (as clarified).**
- *Gate-current:* `reusable_proven_alignment_items` re-runs the current `validate_candidate_alignment` on every candidate item before reuse (`:441`). The gate is therefore always current, including the new helper, `visit_unresolved` rejection, and the `native_visit_scope` requirement at the call site.
- *Model identity:* `_alignment_input_identity` (`:368-388`) pins statement, source unit, native context version, context units, stage sources, bound visit sources, and the full candidate digest. Response identity is pinned by `response_sha256` + re-parse (`:445-450`).
- *Consequence I accept:* a gate-only change does not re-read unchanged model observations; the saved response items are revalidated under the new gate. This is a legitimate separation, not a hole. The token sitting under `validator_version` in `_deep_component_identity` (`protocol_control_execution.py:2073`) rather than `compiler_versions` is exactly what makes that separation work as intended.

**Tightened final call site (`candidate_alignment.py:593-610`) — confirmed by direct read.**
- Line 600 now reads `native_visit_scope and native_schedule_action_cell_is_preserved(...)`, so the action-cell proof bypasses literal-conjunction coverage only when the visit-side proof is already true (`:548` computes it; gate requires one `at_or_before_baseline` marked column, exact header source pairs, single bound decide node, exact row-source pairs at `protocol_control_source_interpretation.py:2424-2493`).
- Line 590 (`fully_expressed` with unresolved native table statement rejected) is now **before** the scope-projection branch — I verified the ordering: the unresolved rejection at `:593` runs unconditionally for `fully_expressed`, and the helper additionally rejects `statement.unresolved` plus `column.visit_unresolved` (`:2381-2390`).
- Marked-column requirement is unique and physical: `nonempty` must equal exactly the marked columns; no marker footnote and no `visit_unresolved` column can carry the bypass.

## New unsafe-hole search (deterministic layer)

I probed the helper and the tightened call site for a runnable synthetic input that would newly achieve `fully_expressed` unsoundly. I found **none** in the deterministic layer:

- **Extra unmarked nonempty cell** (e.g. "完成后3天" at an unmarked column): `nonempty` gains that index → `nonempty != marked columns` → False. Covered by the `nonmarker_value` case.
- **Marker footnote / unresolved header**: rejected in the same guard via `marker_footnotes or visit_unresolved`. Covered.
- **Wrong row without `native_visit_scope`**: the visit proof's exact `stage_sources == header_sources` and `row_sources == atom span/excerpt pairs` (`:2470-2493`) fail; the helper alone no longer admits the bypass.
- **OR-for-AND / partial action**: helper requires `all` label pairs in both atom statement and proposition; set-equality of `nonempty` with marked columns; no OR relaxation.
- **Second marked column**: `len(columns) != 1` rejects in the visit proof.

The one boundary that remains in the helper is **non-containment of added prose**: the helper proves every source label pair is present in the atom statement/proposition, not the inverse. A runnable synthetic input to document the boundary (not a defect claim):

```python
# statement/proposition = "在基线期 V2 D0 完成材料分发及回收并同步记录未回收原因"
# source pair "材料分发及回收" is present -> helper True; the visit-side proof still holds.
# "并同步记录未回收原因" has no corresponding physical source pair and no source excerpt.
```

A probe like this should be **rejected** by the independent semantic alignment (`fully_expressed` requires the candidate to jointly and only jointly express the sentence), not by the containment helper. I therefore classify it as a **limit**, not an unsafe hole.

## Remaining limits (no acceptance implied)

1. **Semantic completeness is model-adjudicated, as designed.** The helper proves physical action-cell text and source pairs; it does not prove arbitrary added prose equivalent. The mandatory `SourceCandidateAlignment` decision, bound to the full candidate and source, remains the semantic gate. I do not claim the helper proves clinical meaning, and I expressly do not treat the passing test count as clinical evidence.
2. **Statement/proposition over-addition** is the residual boundary of the helper and is safeguarded by (a) mandatory semantic alignment and (b) exact source-pair set identity in the visit-side proof. If the owner wants deterministic insurance beyond that, the natural candidate is a bounded check that the atom statement/proposition introduces no clause with a source-pair set beyond the physical row pairs — but this is optional hardening, not a demonstrated live hole, and I did not verify feasibility within the current atom schema.
3. **Aligned-proof identity does not hash the action-coverage version literal.** Reuse is still gate-current (`:441`) and the deep-component identity carries the token under `validator_version` (`:2073`), so no unchecked reuse path exists that I could trace. Low-severity note only: a future helper change must bump `NATIVE_ROW_ACTION_COVERAGE_VERSION` to force model re-reading, consistent with the intentional distinction in this review.
4. **Early-exit header question** remains a bounded read: readable headers admit a question (`:427-429`) and the correction gate keeps unresolved non-empty; adoption of an unmapped header as a visit is still blocked by `visit_unresolved` in the helper and the visit-side gate.

## Tools/evidence, and this review's scope

- Read set used in this continuation: 4 focused reads (two each from the two current source files) covering `native_schedule_action_cell_is_preserved` + the tightened `validate_candidate_alignment` call site, `_alignment_input_identity` + `reusable_proven_alignment_items`, and `can_recheck_source_scope_question` + `apply_source_scope_question_recheck`. No tests run, no edits, `Bash` still unavailable in this session; my first-round execution check remains unperformed and is now moot for R1.
- Acknowledged: my first round exceeded the ten-read packet budget; I stayed within four this turn.
- I close this engineering review as **no newly introduced unsafe hole found in the deterministic action-cell/marker separation**, with the limits above. This is not clinical acceptance, not a rule activation, and not Codex final authority — those remain with Codex.
