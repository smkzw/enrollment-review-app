This is a read-only review continuation; per the workflow-state note I'll ask about Trellis: **no Trellis task is warranted for this turn** — it is a bounded adjudication with a fixed read set, no implementation. If you want it tracked as a task/plan afterwards, say so. No plan file/ExitPlanMode applies to an advisory deliverable, so I proceed with the review now.

Starting targeted reads (≤8).

# Adjudication: frozen current-column proof and source/runtime separation

**Decision: the expansion does not overstate `fully_expressed` in a way that adopts a wrong current node; I found no *adoption* hole in it. I found one real, narrower gap in the action-cell proof — an atom can carry extra marker cells — and I state its limit. One wording correction to my prior report. Acceptance of the source-level changes is supported; runtime/clinical checks remain unperformed.**

## Correction of my prior report (as requested)

`check_protocol_control_batch_candidates` is a guard whose **truthy** result makes `_restricted_statement_batch_from_review` return `None` — i.e. it returns `None` when issues exist, and the batch is *not* produced. My earlier sentence ("must fail the batch contract") was backwards and is withdrawn. That path therefore yields no restricted output at all on a candidate-contract issue, which strengthens, not weakens, the "cannot be retagged and adopted" point. I also read that region in the earlier turn; the exact line numbers are no longer current and I did not re-read them this turn, so I cite behavior by function name only.

## 1. Prompt separation (change 1) — verified, no overclaim

`build_source_scope_correction_prompt` (`protocol_control_source_interpretation.py:371-375`, `:392-395`) now emits `runtime_projection.fixed_visit_or_date_unmapped` as a program state and says explicitly it "只表示程序未识别固定访视编号或日期，不能据此说标题文字或动作适用关系不清 … 不在本步骤判断程序能否执行". `build_source_scope_question_prompt` (`:441-472`) repeats the separation and adds "没有共同范围就保留字段为空及原有逐列关系，不因此新增或保留原文疑问". `apply_source_scope_question_recheck` (`:475-490`) is unchanged in its guardrails: the native allowlist is `{unresolved, scope_quote, affected_stage, time_words}` and it re-routes through `apply_source_scope_correction` (which rejects any non-empty `correction.unresolved`). So a cleared source question can still not produce a usable runtime visit; the test at `test_protocol_control_candidate_alignment.py:177-185` asserts exactly that.

## 2. Question history and budget (change 2) — verified

At `protocol_control_deconstructor.py:7201-7229`, a record counts as `seen` only when it was parsed with no error classes, the proposal equals the current statement, and, for table rows, `native_guidance_version == NATIVE_SCOPE_QUESTION_GUIDANCE_VERSION` (`:7219-7227`). Non-table rows keep the old behavior (the `unit.table_context is None` disjunct). Budget: `source_repairs = len(question_history)` (`:7229`) and the check at `:7619` uses `source_repairs >= self._max_schema_repairs`, so old paid records still consume budget and no reset exists. New attempts record `prompt_sha256` and `native_guidance_version` (`:7631-7633`). Verified on source; no runtime confirmation.

## 3. Current-column proof (change 3) — mechanism verified, boundary stated

`native_schedule_visit_scope_is_preserved` (`:2423-2534`) now: requires at least one `at_or_before_baseline` column, no `visit_unresolved` among **current** columns (`:2445`); permits scalar scope/time only in the single-column branch (`:2448-2456`); enforces a bijection between distinct decide nodes and current columns via exact stage/header source-pair matching (`:2479-2504`); and requires atom sources to equal the row's label + current marker sources (`:2506-2533`). The `fully_expressed` bypass remains gated by `native_visit_scope` at `candidate_alignment.py:600-602`, so the expansion inside the gate is *not* a new bypass path.

**On the `after_baseline` counterargument:** the code retains later columns in the frozen row/excerpt and simply does not match them to nodes; the test (`test_later_native_columns_are_retained_but_not_adopted_as_current_visits`, `:252-274`) asserts only that the two current nodes remain and that no atom cites c3/c4 — i.e. it documents retention, not statement construction. The mapping of a non-date event column to "after" is the pre-existing `boundary_side` projection; the patch's claim is limited to current known marked visits, and that claim is enforced by the exact node/header-source bijection. I did not verify that an after-baseline column can never occur before baseline in reality — that remains an owner-declared limit, not established by this proof.

## 4. The gap I can state precisely

`native_schedule_action_cell_is_preserved` (`:2408-2418`) checks only that the **label** source pairs appear in the atom statement and proposition. It does not require the atom's statement/proposition to account for the marker cells. In the single-column case the visit proof's exact set equality (`row_sources == atom pairs`) closes this because the marker cell is one of the required pairs. But in the multi-column case `row_sources` and the atom pairs are the same set — a **superset** is accepted as long as it contains each element once and the count equals `len(label_refs) + len(current_columns)` (`:2522`). Concretely, in `_multi_native_action_material` (`tests/...test_protocol_control_candidate_alignment.py:188-216`), the atom retains `"X"` excerpts for the screening and baseline markers and a statement/proposition "在筛选期和基线期分别完成材料分发及回收"; the label "材料分发及回收" appears in both. A semantic check that never mentions one of the two marker columns would satisfy the same conditions. So: **fully_expressed can be reached with marker-pair presence but no marker-specific commitment in the sentence.** This is a limit on *how much* the claim covers, not evidence that a wrong stage was adopted.

**Minimum stricter constraint (if Codex wants one):** require that each current column's marker cell source pair be "named" in the sentence — the mechanical version is that the atom statement/proposition contain at least one normalized fragment from every cell whose ref is in `current_refs` in addition to the label; or, equivalently, require the atom's marker set to be exactly the current markers and reject any extra marker excerpts beyond labels + current markers. Either preserves single-column behavior and does not add any event/diary dictionary, does not delete columns, and does not need a date map. Mutation coverage currently exercises `missing_marker`, `partial_action`, `extra_content`, `shared_scope`, `wrong_header`, `missing_node`, `duplicate_node`, `unresolved` (`:219-249`) — none of the nine mutations targets a marker that is present but unmentioned in the statement, so adding one would test this boundary.

## 5. Remaining consumer/coverage gate — correctly not "completed"

The source-level route leaves runtime adoption untouched. The faithful non-executable handling in this codebase is the restricted path (`protocol_control_restricted_source.py`), which I inspected earlier this session: it only opens on `publication_invalid` with specific error classes and produces `limitation_kind="consumer_unavailable"` for temporal restrictions, with candidates unable to intersect unproven units. Whether that path still applies to the new token set is a consumer-side question I did not re-verify this turn. So: a clarified source statement does not make an unmapped visit executable, and the restricted route (not a retag) is what would carry a genuine consumer limitation.

## Unperformed checks (explicit)

- No tests, no pipeline/run receipt — I cannot report any pass count; the owner reported 7.27s/0 writes as evidence, which I did not reproduce.
- No independent clinical gold, no header-to-date mapping for any batch, no DB/env/private material, no browsing, no `Bash`/diff.
- No runtime verification of the budget/`seen_questions` behavior under a resumed session; read from source only.
- No re-read of `protocol_control_restricted_source.py` or `protocol_control_execution.py` this turn; their claims are cited by function behavior from my prior reads, not by current line numbers.
- `native_schedule_visit_scope_is_preserved`'s after-baseline positional assumption is flagged as a limit, not independently falsified.

**Recommendation:** accept the three source clarifications plus the coverage-version bump as source-level work; if Codex wants the boundary tightened, apply only the marker-mention constraint in §4. Neither claim constitutes clinical acceptance or evidence that the full batch or workflow is proven.
