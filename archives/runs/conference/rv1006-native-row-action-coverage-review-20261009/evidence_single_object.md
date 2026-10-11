I'll acknowledge the Trellis context and proceed directly with the assigned review. This is a read-only bounded review pass (Delegated mode), so no Trellis task is needed — following the prompt's Hard boundaries only.

This is a critical point — my structural read shows a potential contradiction with the expected positive test. Let me verify the actual patch state and the rest of the helper machinery.

The Bash tool is denied in this environment — I will note that. My structural read of the helper appears to contradict the expected positive test; let me verify the regex and cell machinery precisely.

I have gathered the decisive evidence. This is a read-only delegated review pass — no Trellis task is created for it; I return the complete schema report below.

# Conference Output: rv1006-native-row-action-coverage-review-20261009 - evidence_single_object

## Output

### 1. Verdict (bounded, advisory)

The patch's **separation design is sound** — action-cell text is proved at atom level (`native_schedule_action_cell_is_preserved`, `protocol_control_source_interpretation.py:2379`), markers/visit scope stay gated by `native_schedule_visit_scope_is_preserved` (`:2407`) and the unchanged column gate. I found **no fail-open hole** that would adopt a wrong-row, omitted-action, or OR-for-AND proposition through this helper. However, I found **one must-fix contradiction that makes the helper fail-closed inert on its own documented positive case**, plus one must-verify cache-identity gap and one test-coverage gap.

**Highest-impact defect (must fix before acceptance): `nonempty` comparison rejects the exact frozen problem case.**

Evidence (observed, from the definitions, not the summary):
- `native_schedule_action_cell_is_preserved` (`:2379`) requires `normalize_source_excerpt(statement.quoted_text) == ...(unit.excerpt)` and `set(statement.decision_functions) == {"action"}`.
- `values = schedule_row_values(unit, batch.context_units)` (`:2385`) returns **all** physical cells of the row, including the leftmost label column (`procedure_catalog.py:785-805`; cells built by `_schedule_cells_from_units` `:720-782`, sorted by column).
- The guard is `nonempty = {index for index, text, _refs in values if text.strip() and index != 0}` (`:2388`) and `nonempty != {column.column_index for column in columns}` → `return False` (`:2389`).
- For the frozen row "材料分发及回收 | X": `values = ((0, "材料分发及回收", ...), (2, "X", ...))` → `nonempty = {0, 2}`; `schedule_column_scope` marks only the marker cell `(3,2)` → `{column.column_index} = {2}`. `{0,2} != {2}` → **False**, so the helper never returns True for its target shape.
- The positive test `tests/v2/agents/test_protocol_control_candidate_alignment.py:60-73` (`test_native_action_text_need_not_include_schedule_markers`) sets `atom.statement = "在基线期 V2 D0 完成材料分发及回收"` and expects `validate_candidate_alignment` to pass; tracing `validate_candidate_alignment` (`protocol_control_candidate_alignment.py:591-681`), **every other branch is satisfied only via this helper** (line 600) — I verified the exception/quota/number/direction/time-anchor branches all clear, so the test passes only if the helper returns True. By source tracing it returns False, the fallback `_split_obligations_cover_source` returns False (the atom's `"材料分发及回收 | X"` excerpt matches single fragments, but the atom's statement lacks the separator/X and the remainder is not an AND joiner), and validation must raise `候选义务摘录未按原文保留完整合取内容`.

*Confidence:* source-traced observation, high; I could not execute the test (`Bash` is denied in this session — see §6), so the residual possibility is that a mutation route I did not trace (e.g. mark set membership differing from `schedule_column_scope`) alters one input; but every input set is directly read from the definitions above.

*Minimal recommendation:* change the guard to compare only **non-label** marked-column content — i.e. require the label cell (column 0, already proved by `native_schedule_label_sources`) to be excluded and every other nonempty cell to be a mark: `nonempty | {0}`-style normalization, or `nonempty - {row_values[0][0]} == {column.column_index ...}`. Do not weaken the `marker_footnotes` or `unresolved`/`exception_words`/`decision_functions` gates. If instead the intent is that a valid schedule row must have **no** non-mark content outside marked columns **including the label column**, then the helper can never cover the frozen problem and the patch premise is wrong — this is a decision point for Codex (§5, Q1).

### 2. Second finding — proof reuse without current-gate binding (must verify, low-cost fix)

- `NATIVE_ROW_ACTION_COVERAGE_VERSION` (`protocol_control_candidate_alignment.py:22`) is set but **not** included in `_alignment_input_identity` (`:359-388`), which is what `reusable_proven_alignment_items` compares proof hashes against (`:441-444`). A stored `fully_expressed` proof whose helper logic changed between patches would still match if the statement/candidate digests are unchanged.
- Mitigation I inspected: the version **is** in `_deep_component_identity.compiler_versions` (`app/services/protocol_control_execution.py:2073`), and that identity is compared on the saved/resume path (`:2699-2701`, `:3533-3536`) with `_same_deep_components_with_current_gate` allowing only `validator_version` to differ (`:2081-2095`). So a version bump does invalidate saved deep components.
- Residual risk: cache validity depends on a future editor remembering to bump the version literal; the within-session proof-identity check itself is version-blind.
- *Recommendation:* fold `NATIVE_ROW_ACTION_COVERAGE_VERSION` (and `NATIVE_TABLE_ALIGNMENT_CONTEXT_VERSION`) into the digest payload in `_alignment_input_identity`, or at minimum keep the version bump + saved-component check as an explicit invariant in the patch notes.

### 3. Third finding — test gap on the "added text" boundary

- The helper proves label text ∈ {atom statement, atom proposition} (`:2396-2403`), not the reverse. An atom statement such as "在基线期 V2 D0 完成材料分发及回收并记录未回收原因" would still pass the helper's label containment.
- Existing rejection tests (`test_protocol_control_candidate_alignment.py:76-108`) cover `missing_action`, `partial_proposition`, `wrong_row`, `unresolved`, `marker_footnote`, `nonmarker_value`, `exception`, `wrong_scope` — but **not** the "statement/proposition adds unsupported extra content" direction. Rejection there relies on non-helper layers (source-excerpt grounding at `:571-579` and the time/exception/number checks), which reviewers cannot see from the helper's own guard list.
- *Recommendation:* add one negative case where the proposition appends a clause not present in the action cell (e.g. "…并记录未回收原因") while the statement contains the label, asserting the same rejection. This converts an inferred boundary into a tested one.

### 4. Must-fix vs existing limitations (explicit separation)

**Introduced by this patch:**
- The `nonempty`/label-column contradiction (§1) — fail-closed: it rejects instead of adopting. The safety direction is correct, but the intended capability does not materialize and the supplied positive test(s) cannot pass as traced.
- The helper's version literal not being part of the aligned-proof identity (§2).

**Pre-existing limitations (not introduced; must not be silently widened):**
- The `native_visit_scope` alternative at `protocol_control_candidate_alignment.py:600-602` can bypass the full-containment check only when an obligation atom exactly equals the statement text **and** the single-column/stage/row-source gate passed — I found no cross-row or second-column leak: `native_schedule_visit_scope_is_preserved` requires `len(columns) == 1`, `boundary_side == "at_or_before_baseline"`, exact `row_sources == atom span/excerpt pairs` (`:2470-2493`), and re-invokes the new helper only as an atom-identity alternative (`:2488`).
- `_schedule_label_sources` (`:770-797`) prefers per-member span mappings and falls back to a unit-local `::{ref}` suffix span for old frozen units — the returned pairs are still physical refs inside the unit; not a new leak.
- OR-for-AND and partial-action content are rejected because the helper requires **all** label pairs to be present in **both** statement and proposition (`all(...)` at `:2400-2402`) and the fragment-recipe fallback is unchanged.

### 5. What I actually inspected (evidence trail)

Read in full or targeted, from the live uncommitted worktree files:
- `app/agents/protocol_control_candidate_alignment.py`: complete file (validator `validate_candidate_alignment` :511-681, `bind_candidate_alignment` :391-408, `reusable_proven_alignment_items` :418-456, identity :359-388, version constants :19-22).
- `app/agents/protocol_control_source_interpretation.py`: `can_recheck_source_scope_question` :412-429, `build_source_scope_question_prompt` :432-459, `apply_source_scope_question_recheck` :462-488, `apply_source_scope_correction` :502-558, `_schedule_label_sources` :770-797, `native_schedule_label_sources` :809-822, `shared_prohibition_preserves_source` :2345-2376, `native_schedule_action_cell_is_preserved` :2379-2404, `native_schedule_visit_scope_is_preserved` :2407-2495.
- `app/protocols/procedure_catalog.py`: `_Cell`/`_VisitColumn`/`ScheduleColumnScope` :185-230, `_is_mark`/`_non_mark_text` :326-334, `_header_projection` :617-690, `_enrollment_boundary` :693-717, `_schedule_cells_from_units` :720-782, `schedule_row_values` :785-805, `schedule_column_scope` :808-862, regexes :61-131.
- `app/services/protocol_control_execution.py`: `_validate_saved_source_review` :3320-3404 (read), `_deep_component_identity` :1995-2078 (read, including `NATIVE_ROW_ACTION_COVERAGE_VERSION` at :2073), `_same_deep_components_with_current_gate` :2081-2095, use sites :2699-2701, :3121, :3533-3536, and the executor call `apply_source_scope_question_recheck` at :2536-2539 (grep-verified).
- `tests/v2/agents/test_protocol_control_candidate_alignment.py`: lines 1-180 (new synthetic cases :41-147; `_native_visit_candidate_material` fixture :6789-6826 in the slice58c file).
- `tests/v2/protocols/test_slice58c_control_deconstructor.py`: `_native_time_recheck_batch` :6752-6786, `_native_visit_candidate_material` :6789-6826, `test_native_visit_components_require_complete_physical_correspondence` :6829-6902.

Not inspected (out of the declared read set): `apply_source_scope_correction` callers beyond the executor line, `_source_inventory` internals, `validate_source_interpretation` body, `ControlObligationKind` enum body, and the rest of both test files.

### 6. Tool/evidence failures

- `Bash` (git status/diff to confirm the uncommitted patch boundary and to run the two new tests) was **denied** in this non-interactive session. Therefore: (a) I could not independently confirm the patch boundary against HEAD `9abf0e32`, and (b) the §1 counterexample is derived by exhaustive source tracing, not by test execution. This is the one material piece of missing evidence.

### 7. Objections / decision points / bounded questions for Codex

1. **Q1 (blocking):** Does the positive test `test_native_action_text_need_not_include_schedule_markers` actually pass in your run? If yes, please paste the passing assertion context — my source trace says the `nonempty != {marked columns}` guard at :2389 must reject, which would mean my reading misses an input mutation; if no, the minimal fix in §1 applies. Either way I recommend the `nonempty` guard be changed to compare **non-label** cells only.
2. **Q2:** Is "marker-only non-label cells" in the objective intended to *exclude* the leftmost label cell from the `nonempty` set (my proposed fix), or does it mean the row truly must contain no other nonempty cells at all (in which case the frozen problem row itself violates the guard and the patch needs a different anchor)? This changes the fix.
3. **Q3:** Will you add `NATIVE_ROW_ACTION_COVERAGE_VERSION` to the aligned-proof digest (`_alignment_input_identity`), or is the saved-component-identity check at `:2073` considered sufficient? I recommend the former as cheap defense.
4. **Q4:** The `can_recheck_source_scope_question` readable-header widening (`:425-429`) routes any accepted scope change through `apply_source_scope_correction` and full `validate_source_interpretation` (`:477-488`); I did not find a path that adopts an unmapped header into a known visit without that gate, and `native_schedule_visit_scope_is_preserved` still rejects `visit_unresolved`/non-`at_or_before_baseline` columns (`:2429-2431`). Confirm the early-exit fixture is exercised only for the bounded question and never for adoption.
5. **Q5:** Per the objective, this is not clinical approval and I claim no Codex authority. The §1 defect is a rejection-side (fail-closed) defect, so no wrong adoption occurs today — but the patch's stated capability and its tests are inconsistent until fixed. Safe provisional path: keep the current helper in place (fail-closed), do not widen `nonempty` without re-running the negative matrix, and verify §1 before any acceptance claim. Resume point if you want same-session continuation: re-run just `tests/v2/agents/test_protocol_control_candidate_alignment.py::test_native_action_text_need_not_include_schedule_markers` plus the eight `test_native_action_text_does_not_prove_unknown_or_changed_content` mutations and report the first failing assertion.
