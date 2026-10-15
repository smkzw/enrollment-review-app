This is a bounded read-only review, not an implementation — before creating any Trellis task I ask: **should this turn open a Trellis task?** My recommendation is **no** (review-only, fixed read set, deliverable is a findings report). If you agree, say so and I'll continue; if you want it tracked, I'll create it first.

Meanwhile I proceed with the read-only exploration the prompt assigns (Explore agents, parallel).

I'll start by exploring the codebase to find the relevant test files.

Let me read the test file directly.

Let me read additional sections, especially around lines 800-1200 to understand the same-unit tests and the fixture helpers.

Let me check the tests/v2/protocols/ and tests/v2/agents/ directories for frequency guard tests, and look at additional test details.

# Restricted Source Recovery Test AuditFile audited: `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/tests/v2/services/test_protocol_control_execution.py` (plus one cross-suite file).

Implementation under test: `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/app/services/protocol_control_restricted_source.py`.

There is no symbol named `_restricted_statement_batch_from_review` in this test file (nor in the module under test — the public entry point is `restricted_batch_from_review`). All test references below call `restricted_batch_from_review` directly.

---

## 1. Mixed procedure + restricted source scenarios (positive cases)

### `test_whole_mixed_unit_retains_all_points_without_fake_independence` — lines 349-370
- Parametrized over `swap` ∈ {False, True} (line 349).
- Fixture: `_same_unit_two_requirement_review(swap=swap)` (line 351). Same frozen unit, two requirements: `"年龄至少18岁"` (independent) and `"给药前90分钟内完成首次给药"` (restricted).
- Setup (lines 352-355): clears `statements[1].unresolved`, recomputes `source_statement_coverage`.
- Decisive assertions (lines 357-370):
  - `output = restricted_batch_from_review(batch, result)` → not `None`
  - `assert output.candidates == []`
  - `assert len(output.restricted_statements) == 2`
  - `assert {item.source_quote for item in output.restricted_statements} == {_SAME_UNIT_INDEPENDENT, _SAME_UNIT_RESTRICTED}`
  - `assert all(item.independent_scope_proof is None for item in output.restricted_statements)` ← the required-procedure correspondence is **deliberately not promoted to executable**
  - `assert output.dispositions[0].disposition == StructureUnitDispositionKind.RESTRICTED_SOURCE`
  - `frozen == result` (no silent mutation) and reloaded run produces identical output (lines 366-370).
  - `module._validate_deep_batch_output(batch, output)` does not raise.

### `test_whole_unit_coverage_keeps_joiners_without_proving_independence` — lines 391-412
- Parametrized over separator ∈ {`"；\n"`, `"；"`, `"，"`} (line 391). The required-procedure correspondence is **not retained as executable** for any separator — all branches keep both points restricted.
- Setup (lines 395-400): uses `_same_unit_two_requirement_review()` then rebuilds excerpt from `separator.join([_SAME_UNIT_INDEPENDENT, _SAME_UNIT_RESTRICTED])` and recomputes coverage.
- Decisive assertions:
  - `output = restricted_batch_from_review(batch, result)` → not `None`; `not output.candidates`; `len(output.restricted_statements) == 2` (lines 401-403)
  - Range-coverage proof: `source_statement_ranges_cover_unit(excerpt, ranges, allow_joining_punctuation=True)` is `True` (line 406); strict form only matches when separator is `；\n` (line 409); adding `例外情况` makes coverage fail (lines 410-412).

### `test_whole_temporal_unit_preserves_time_and_scope_without_executable_siblings` — lines 429-479
- Parametrized over `with_scope` × `sibling_unresolved` (2×2) (lines 429-430).
- Fixture: `_independent_candidate_and_temporal_gap(same_unit=True)` (line 437) — same unit with `独立年龄` + `持续7天` (the second is unexecuting temporal).
- Decisive assertions (lines 459-479):
  - `output = restricted_batch_from_review(batch, result)` → not `None`, `not output.candidates`
  - `len(output.restricted_statements) == 2`
  - `all(item.independent_scope_proof is None for item in output.restricted_statements)` ← required-procedure correspondence is **not promoted to executable**; both points stay restricted.
  - `all(item.limitation_kind == ("interpretation_unresolved" if sibling_unresolved else "consumer_unavailable") for item in output.restricted_statements)`
  - `output.restricted_statements[1].time_words == ["7天"]`
  - `output.restricted_statements[1].decision_functions == ["action", "time_validity"]`
  - `scope_quote` is `"筛选期："` when `with_scope`, else `None`.
  - `_restricted_control_projections` → `len(projections) == 2`, all `obligations[0].status == "restricted"` with empty `fact_refs` (lines 477-479).

### `test_same_unit_independent_requirement_keeps_source_proven_candidate` — lines 857-888
- Fixture: `_same_unit_two_requirement_review()`.
- This is the **only** test asserting that a required-procedure correspondence **can be retained as a non-restricted candidate alongside a sibling restricted statement** (i.e. R1 may promote the source-proven half, but only when the proof is local and disjoint).
- Decisive assertions:
  - `output.candidates` length 1; `output.dispositions == [OTHER_CONTROL_CANDIDATE, SUPPORTING_OR_SUPPLEMENT]` (lines 862-866).
  - The restricted list contains only `su-01` (line 867) with `source_quote == _SAME_UNIT_RESTRICTED`, `time_words == ["90分钟"]` (lines 868-870).
  - `statement.independent_scope_proof is not None` with excerpt-anchored `restricted_source_start/end` and one `independent_excerpts` entry with `candidate_control_ids == [output.candidates[0].control_candidate_id]` (lines 871-882).

### `test_mixed_source_review_keeps_covered_procedure_and_restricts_only_gap` — lines 1752-1803
- This is the **direct required-procedure + restricted-source positive case** the question asks about.
- Fixture: `_unresolved_batch_review()` mutated so statement 1 becomes `linked_only` with `disposition = "required_procedure"` and `linked_procedure_target_ids = [target.catalog_item_id]` (lines 1760-1762); review item 1 set to `covered_by_procedure` (lines 1763-1769); `wire.dispositions[1].disposition = REQUIRED_PROCEDURE` (lines 1771-1772).
- Decisive assertions:
  - When `unresolved = ["适用对象未核清"]` is restored (lines 1778-1784): `pytest.raises(ValueError, match="来源陈述仍有未核清内容")`.
  - When clean: `mixed = restricted_batch_from_review(batch, result)` → not `None`; `dispositions == [RESTRICTED_SOURCE, REQUIRED_PROCEDURE]`; `restricted_statements` covers only `["su-01"]` (lines 1786-1792).
  - When `linked_procedure_target_ids = []`: `pytest.raises(ValueError, match="覆盖目标与草稿链接不一致")` (lines 1795-1797).
  - When `result.partial_wire = None`: `restricted_batch_from_review(...) is None` (lines 1802-1803).

### `test_unresolved_review_keeps_non_enrollment_execution_from_verified_wire` — lines 1806-1827
- Related: an author-wire disposition of `POST_TREATMENT_EXECUTION` (no candidate drafts) on the unrelated unit lets the restricted sibling stand. Counterexample when `coverage[1].disposition == "required_procedure"`: `pytest.raises(ValueError, match="逐项来源核对必须且只能覆盖")` (lines 1825-1827) — i.e. the wire-only/no-candidate-draft case with `required_procedure` is refused.

---

## 2. Whole-unit source coverage / whole-unit restriction behavior (positive)

### `test_whole_unit_restriction_reads_back_without_projection_fields` — lines 918-928
- Fixture: `_unresolved_batch_review()` (line 919).
- Assertion: `output = restricted_batch_from_review(batch, result)` → not `None`; **no** `independent_scope_proof` field in the dumped output (lines 921-926); model round-trips identical to itself (line 927); `_validate_deep_batch_output` accepts.

### `test_same_unit_proof_holds_for_a_semantics_preserving_arrangement` — lines 891-902
- Parametrized indirectly via `swap=True`.
- Decisive assertions: `output.restricted_statements[0].independent_scope_proof is not None` (line 895); excerpt-anchored offsets confirm positions and `source_start > restricted_source_start` (lines 898-901).

### `test_same_unit_shared_scope_cannot_be_proved_by_disjoint_actions` — lines 931-940
- Adds a `"符合下述条件者："` prefix shared between the two statements.
- Decisive assertions: `output is not None and output.candidates == []`; `len(output.restricted_statements) == 2`; `all(item.independent_scope_proof is None for item in output.restricted_statements)` (lines 935-938). **Whole-unit restriction is preserved** when the scope cannot be split.

### `test_same_unit_source_function_cannot_be_promoted_by_literal_separation` — lines 958-967
- Parametrized over `function` ∈ {`"definition"`, `"threshold"`, `"calculation_input"`, `"unclassified"`}.
- Decisive assertion: `output.candidates == []`; `len(output.restricted_statements) == 2`; `all(item.independent_scope_proof is None for item in output.restricted_statements)` (lines 964-966) — comment: "R1 permits a whole-unit non-executable record, not a promoted sibling" (line 963).

### `test_restricted_source_keeps_its_context_without_guessing_independence` — lines 970-980
- `source.scope_quote = source.quoted_text`, `source.exception_words = source.quoted_text` (lines 973-974). Output is `not None` and the same values round-trip through the model.

### `test_same_unit_restriction_survives_real_checkpoint_and_rebuild` — lines 1073-1118
- Parametrized over `kind ∈ {"interpretation", "temporal"}`. End-to-end via `JobStore`. Decisive: `rebuilt[batch.batch_id] == output` (line 1111), `projected.obligations[0].status == "restricted"` and `fact_refs == ()` (lines 1115-1116).

---

## 3. Invalid-result counterexamples (output must be refused = `None` or raise)

### `test_whole_mixed_unit_does_not_disguise_invalid_source_or_author` — lines 373-388
- Parametrized over `failure ∈ {"bad_value", "extra_error", "transport", "unread_prefix"}` (line 373).
- Fixture: `_same_unit_two_requirement_review()` (line 375); `statements[1].unresolved = []` (line 376).
- Defect variants (lines 377-384): wrong predicate value, extra error class, transport failure, unread source prefix.
- Decisive: `assert restricted_batch_from_review(batch, result) is None` (line 388).

### `test_invalid_partial_review_cannot_be_reclassified_as_faithful_restriction` — lines 415-426
- Parametrized over `errors` ∈ three lists (line 415-419):
  - `["SOURCE_TARGET_REVIEW_INVALID"]`
  - `["SOURCE_TARGET_REVIEW_INVALID", "SOURCE_TARGET_REVIEW_UNRESOLVED"]`
  - `["SOURCE_TARGET_REVIEW_TRANSPORT_FAILED"]`
- Setup: `result.source_target_review.items = []`, then set `attempts[-1].error_classes = errors`.
- Decisive: `assert restricted_batch_from_review(batch, result) is None` (line 425); `result` frozen state unchanged (line 426).

### `test_whole_temporal_unit_rejects_damaged_witness_or_unread_source` — lines 482-503
- Parametrized over `defect ∈ {"wrong_ids", "bool_ids", "wrong_refs", "missing_detail", "missing_scope", "unread_exception", "wrong_value", "extra_error"}` (lines 482-483).
- Decisive: `assert restricted_batch_from_review(batch, result) is None` (line 503).

### `test_temporal_restriction_does_not_approve_unproven_error_ranges` — lines 788-854
- Parametrized over 17 `failure` values (lines 788-793): `missing_detail`, `wrong_code`, `wrong_scope`, `wrong_source`, `wrong_dependents`, `bool_index`, `extra_index`, `extra_error`, `transport`, `non_temporal`, `unresolved_semantics`, `definition`, `recommended`, `shared_scope`, `overlap`, `unreported_prefix`, `candidate_cites_restriction`, `changed_sibling_value`.
- Fixture: `_independent_candidate_and_temporal_gap(same_unit=True)` (line 795).
- Decisive: `output is None` for every failure except `shared_scope`, which keeps both restricted and `independent_scope_proof is None` (lines 846-854) — comment at lines 847-849: "Shared meaning cannot keep an executable sibling. Complete frozen source may instead remain wholly non-executable, not be discarded."

### `test_same_unit_restriction_stays_whole_without_an_independent_proof` — lines 905-915
- Forces the restricted quote and the independent excerpt to be identical (`unit.excerpt`).
- Decisive: `result.source_statement_coverage[1].status != "expressed"` and `restricted_batch_from_review(batch, result) is None` (lines 914-915).

### `test_same_unit_independence_cannot_omit_source_words` — lines 943-955
- Parametrized over `position ∈ {"before", "between", "after"}`. Decisive: `assert restricted_batch_from_review(batch, result) is None` (line 955) for all three positions.

### `test_changed_compiler_revalidates_only_wholly_nonexecuting_temporal_source` — lines 506-566
- Parametrized over 10 `change` values (lines 506-507): `None`, `"source"`, `"prompt"`, `"schema"`, `"repair"`, `"missing_wire"`, `"bad_wire"`, `"boolean_ids"`, `"coverage"`, `"unread_source"`, `"executable_sibling"`.
- This is the **compiler-material revalidation** gate, not directly restricted_batch_from_review; decisive lines: `assert (partial is not None) == (change is None)` (line 560); `bad_wire` raises `ValueError` (line 556); `proof["adopted"] is False` (line 564).

### `test_restricted_review_does_not_approve_dependent_or_invalid_candidate` — lines 1680-1697
- Parametrized over `failure ∈ {"shared_source", "invalid_evaluation", "wrong_comparator", "wrong_unit", "unresolved"}` (the `else` branch sets `unresolved=["适用对象仍待核清"]`, line 1696).
- Decisive: `assert restricted_batch_from_review(batch, result) is None` (line 1697).

---

## 4. SOURCE_TARGET_REVIEW_UNRESOLVED stop conditions & author-wire-only cases with `required_procedure`

### `test_deep_failure_keeps_reason_and_partial_source_without_false_adoption` — lines 184-237
- Parametrized over 4 codes × messages (lines 184-189):
  - `SOURCE_TARGET_REVIEW_UNRESOLVED` ↔ `"对应关系仍需核清"`
  - `SOURCE_REQUIREMENT_CONSUMER_UNAVAILABLE` ↔ `"尚缺可靠的装配核验能力"`
  - `SOURCE_REQUIREMENT_INSERTION_LIMIT_REACHED` ↔ `"本次限定修订次数内"`
  - `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED` ↔ `"忠实表达了原文含义"`
- Fixture: `_independent_candidate_and_unresolved_review()` (line 192). Comment at line 193: "Target matching uncertainty is not evidence that the source is ambiguous."
- Setup (lines 194-198): clears `statements[1].unresolved`; sets `attempts[-1].error_classes = [code]` and matching `error_detail`.
- Decisive assertions:
  - **`assert module.restricted_batch_from_review(batch, result) is None`** (line 199) — refuses all four codes up-front.
  - `_execute_deep(...)` raises `StepFailure` with `error_code == "PROTOCOL_CONTROL_" + code` and `retryable is False`; `message in failure.detail` (lines 219-224).
  - Diagnostic checkpoint preserves `partial_wire`, `source_target_review`, `source_interpretation`, `source_statement_coverage`, and `attempts` verbatim (lines 225-235).
  - After re-loading the failure checkpoint: `module.restricted_batch_from_review(batch, restored) is None` (line 237) — re-application also refuses.

### Author-wire-only with `required_procedure` disposition

`test_unresolved_review_keeps_non_enrollment_execution_from_verified_wire` (lines 1806-1827) is the **closest author-wire-only (no candidate drafts) test that interacts with a `required_procedure` coverage row**. It asserts that `POST_TREATMENT_EXECUTION` (an author-wire disposition without candidate drafts) co-exists with a restricted sibling (lines 1816-1822), but mutating `coverage[1].disposition` to `"required_procedure"` makes the call raise:
```python
with pytest.raises(ValueError, match="逐项来源核对必须且只能覆盖"):
    protocol_control_execution_module.restricted_batch_from_review(batch, result)
```
(lines 1825-1827)

There is **no other test in the file** that combines `required_procedure` disposition with a fully empty/author-wire-only candidate wire to confirm R1 retention; the closest analog is `test_mixed_source_review_keeps_covered_procedure_and_restricts_only_gap` (lines 1752-1803), which uses a real procedure target and a `covered_by_procedure` review decision — that case **is retained** (line 1786), but it is not author-wire-only.

---

## 5. Required-procedure correspondence: retained / refused — direct summary

- **Retained (non-executable, restricted)** — required-procedure correspondence is NOT promoted:
  - `test_whole_mixed_unit_retains_all_points_without_fake_independence` (line 357 onward)
  - `test_whole_unit_coverage_keeps_joiners_without_proving_independence` (line 401)
  - `test_whole_temporal_unit_preserves_time_and_scope_without_executable_siblings` (line 459; `limitation_kind ∈ {interpretation_unresolved, consumer_unavailable}`)
  - `test_same_unit_shared_scope_cannot_be_proved_by_disjoint_actions` (line 935)
  - `test_same_unit_source_function_cannot_be_promoted_by_literal_separation` (line 962)
  - `test_temporal_restriction_does_not_approve_unproven_error_ranges` — `shared_scope` branch (line 850)
- **Retained (executable alongside restricted)** — correspondence is shown to be independent with disjoint, source-anchored offsets:
  - `test_same_unit_independent_requirement_keeps_source_proven_candidate` (line 860)
  - `test_same_unit_proof_holds_for_a_semantics_preserving_arrangement` (line 893)
- **Refused (`None` or `ValueError`)**:
  - All defect variants in `test_whole_mixed_unit_does_not_disguise_invalid_source_or_author` (line 388)
  - All three error-class variants in `test_invalid_partial_review_cannot_be_reclassified_as_faithful_restriction` (line 425)
  - All eight defect variants in `test_whole_temporal_unit_rejects_damaged_witness_or_unread_source` (line 503)
  - 16 of 17 failure variants in `test_temporal_restriction_does_not_approve_unproven_error_ranges` (lines 853-854)
  - 3 of 3 word-position variants in `test_same_unit_independence_cannot_omit_source_words` (line 955)
  - 5 variants in `test_restricted_review_does_not_approve_dependent_or_invalid_candidate` (line 1697)
  - Overlap case in `test_same_unit_restriction_stays_whole_without_an_independent_proof` (line 915)
  - All four SOURCE_REQUIREMENT/SOURCE_TARGET codes in `test_deep_failure_keeps_reason_and_partial_source_without_false_adoption` (lines 199, 237)
  - Required-procedure mismatches in `test_mixed_source_review_keeps_covered_procedure_and_restricts_only_gap` (lines 1783, 1796) and `test_unresolved_review_keeps_non_enrollment_execution_from_verified_wire` (line 1826)

The decisive R1 invariant the suite enforces: **when correspondence cannot be proven with disjoint source-anchored ranges, restricted output is the only acceptable form** — `independent_scope_proof is None` is the mark of an unpromotable sibling. A wire-only/empty-candidate state is only valid for `POST_TREATMENT_EXECUTION` / `SUPPORTING_OR_SUPPLEMENT`; attempting the same with `required_procedure` raises.

---

## 6. Frequency guard / shared-visit & shared-excerpt guard

File searched: `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/tests/v2/agents/test_protocol_control_candidate_alignment.py`. (No other `tests/v2/agents/` or `tests/v2/protocols/` test contains explicit `frequency` / `shared_visit` / `shared_excerpt` / `visit_frequency` symbols.)

### `test_literal_frequency_is_not_proof_of_an_executable_time_policy` — lines 425-442
- Build: `_material()` (line 426) returns `(batch, interpretation, output, coverage, _)`; mutates to source `"每3周接受一次治疗，共12周"` (line 427); `decision_functions = ["action", "time_validity"]`; `time_words = ["每3周", "12周"]` (lines 430-431); `atom.evaluation = atom.evaluation.model_copy(update={"determination_mode": "semantic", "proposition": source, "operation": None, "predicate": None})` (lines 435-438).
- Alignment: `quote=source`, items[0].source_excerpt=source (lines 439-440).
- Decisive assertion (lines 441-442):
  ```python
  with pytest.raises(ValueError, match="时间锚点或方向"):
      validate_candidate_alignment(batch, interpretation, coverage, output, alignment)
  ```
  i.e. literal frequency strings are rejected as proof of an executable time policy.

### `test_all_current_native_marks_need_their_own_sourced_visit` — lines 221-249
- Build: `_multi_native_action_material()` (line 222); candidate/statement/unit from the wire.
- Parametrized over mutations: `None`, `missing_node`, `duplicate_node`, `wrong_header`, `missing_marker`, `partial_action`, `unresolved`, `shared_scope`, `extra_content` (lines 225-244). The `shared_scope` mutation sets `statement.scope_quote = "基线期 / V2 / D0"` (line 239); `extra_content` extends `unit.member_texts` with `"完成后3天"` (line 241).
- Decisive assertions:
  - `None` mutation: `validate_candidate_alignment(...)` does not raise (line 246).
  - All other mutations: `with pytest.raises(ValueError): validate_candidate_alignment(...)` (lines 248-249). This is the **shared-excerpt/scope guard**: a single shared scope cannot anchor multiple native marks to a single visit binding.

---

## Areas I did NOT inspect

- The full body of `protocol_control_restricted_source.py` beyond the first 200 lines (the `_restricted_statement_batch_from_review` body and `restricted_batch_from_review` top-level dispatch were not read).
- Tests in `tests/v2/services/test_protocol_control_execution.py` at and after line 1194's `_restriction_case` helper end (lines ~1230-1842) were not fully read; in particular I did not audit `test_unresolved_source_survives_deep_checkpoint_and_rejects_changed_quote` body in full, nor `test_completed_restricted_source_reuse_rechecks_saved_review`, nor the job/checkpoint tests at lines 2138-6426 (these do not directly probe R1 retention and were outside the question's scope).
- `tests/v2/protocols/test_definition_scope_check.py`, `test_publication_service.py`, `test_deepseek_protocol_transport_slice3.py`, `test_slice58c_control_deconstructor.py`, `test_deconstruction_gate_slice3.py`, `test_redeconstruction_backend.py`, and the other `tests/v2/agents/test_*` files returned by the frequency/shared-scope grep — only `test_protocol_control_candidate_alignment.py` was inspected in detail; I confirmed no other file contains `frequency`/`shared_visit`/`shared_excerpt` symbols.
- `tests/v2/domain/test_control_catalog_restricted_contract.py` was referenced via its helper imports but not opened.
- `_unresolved_batch_review` (imported on line 55) was not inspected directly; its behavior was inferred from its consumers.

I have enough information from the targeted reads. Here is the read-only audit report. I did not edit any files, I only used Read/Grep, and I only inspected the two files explicitly listed in the task.

---

## File under audit (absolute path)

`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/app/services/protocol_control_restricted_source.py`

Companion file inspected (callers):
`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/app/services/protocol_control_execution.py`

---

## 1. `restricted_batch_from_review` (lines 720–758)

**Entry guards (return None)**
- L724–725: `if not result.attempts: return None`
- L726–736: capability absent and `error_classes` not a subset of `{SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED, SOURCE_TARGET_REVIEW_UNRESOLVED, TEMPORAL_SCOPE_UNRESOLVED}` → "An invalid/partial review is a recovery diagnostic, not a faithful non-executable requirement. Do not validate it as an adopted review." → return None.

**Route selection**
- L737: try `_restricted_statement_batch_from_review(batch, result)`. If it returns a value, call `_validate_restricted_definition_registration(...)` (L739) and return that output.
- Otherwise L741–758: another guard, then `_whole_unit_restriction(batch, result)`. On success, also runs `_validate_restricted_definition_registration`.

**Comment note**: the function never attempts a path where there IS an author wire with dispositions linking to required_procedure targets but NO candidate drafts. There is no such branch.

---

## 2. `_restricted_statement_batch_from_review` (lines 504–717)

**Top dispatch (L515–516)**: `if result.capability_wire is not None: return _restricted_capability_batch(batch, result)`. So this path only runs when there is no capability wire, i.e. normal/author-wire path.

**Header guard (L521–529)** — return None unless:
- `status == "需要核对"`, `final_output is None`,
- `source_interpretation is not None`, `source_target_review is not None`,
- last attempt `outcome == "publication_invalid"`,
- error_class intersects `{SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED, SOURCE_TARGET_REVIEW_UNRESOLVED, TEMPORAL_SCOPE_UNRESOLVED}` (set intersection, not equality).

**Sanity guard (L531–536)**: empty statements → None. Coverage indices must equal `range(len(statements))` → else None.

**Wire/no-wire branch (L542–566)** — this is the key part for your question:

```python
has_wire = result.partial_wire is not None
if has_wire:
    if ((result.source_definition_consumers is not None
         and not result.restricted_source_definition_consumer_attempts)
            or any("calculation_input" in item.decision_functions
                   for item in interpretation.statements)
            or any(item.decision not in covered | {"unresolved"}
                   and not (item.decision == "additional_requirement"
                            and item.statement_index in temporal_indexes)
                   for item in review.items)):
        return None
    original = hydrate_protocol_control_agent_output(result.partial_wire, batch)
    if (result.source_statement_coverage
            != source_statement_coverage(batch, interpretation, result.partial_wire)):
        return None
else:
    if (interpretation.units_without_statement
            or any(not item.unresolved for item in interpretation.statements)
            or {item.statement_index for item in review.items}
            != set(range(len(interpretation.statements)))
            or any(item.decision in covered for item in review.items)
            or any(item.decision not in {"unresolved", "additional_requirement"}
                   for item in review.items)):
        return None
    original = None
```

- `covered = {"covered_by_official", "covered_by_procedure"}` (L540). Already-covered decisions explicitly disqualify this path when there IS a wire — they can be kept/restricted only via the proven path; the code prohibits a covered statement going through `_restricted_statement_batch_from_review` when there is a wire.
- `additional_requirement` is allowed only when its index is also a temporal index (other risk classes like `potential_same_requirement`, `definition_dependency`, `cited_external_rationale`, `background_context` → all cause `return None` on the wire path).
- When there is NO wire (L557–566): `units_without_statement` must be empty; every statement must be `unresolved`; review must contain every statement index; no decision may be in `covered`; every decision must be in `{unresolved, additional_requirement}`.

**Per-unit proven/whole-unit dance (L586–643)**: for each unit with restricted indexes, it tries `_coexisting_statement_proofs` (see §5). If proofs come back None, **L600–606**:
```python
if (len(indexes) != 1 or indexes[0] not in unresolved_indexes
        or (not interpretation.statements[indexes[0]].unresolved
            and indexes[0] not in temporal_indexes)
        or (indexes[0] in temporal_indexes
            and interpretation.statements[indexes[0]].quoted_text
            != units[unit_id].excerpt)):
    return None
continue
```
That means: when the proof fails for a single-statement unit, the function lets the whole unit become restricted only if (a) that one statement is unresolved, or (b) it is a temporal-only statement whose quoted text equals the unit excerpt. **Anything else (e.g. additional_requirement without temporal) → return None**.

**Independent-index requirement (L610–612)**: any unresolved source statement among independent (non-restricted) indexes → return None.

**Per-index decision disposition branch (L616–636)**:
- `decision is None` AND disposition is `OTHER_CONTROL_CANDIDATE` → coverage must be `expressed` AND `statement.unresolved` must be False (else return None).
- `decision is None` AND disposition not in `{POST_TREATMENT_EXECUTION, NON_ENROLLMENT_EXECUTION, PHASE_EXCLUDED}` → return None.
- `decision == "covered_by_official"` → disposition must be `OFFICIAL_ELIGIBILITY` and `linked_official_code == decision.target_id`, else None.
- All other decisions → disposition must be `REQUIRED_PROCEDURE` AND `target_id` must be in `disposition.linked_procedure_catalog_item_ids` (or `linked_procedure_catalog_item_id`). Else None.

**Important for your question — there is NO branch that retains a candidate targeting a `REQUIRED_PROCEDURE` unit when the review item is "unresolved"** (correspondence still open). An unresolved review item cannot map a target to REQUIRED_PROCEDURE; the per-index check requires the disposition to be OTHER_CONTROL_CANDIDATE for unresolved cases. Required-procedure linkage is gated exclusively on decision∈covered/other-non-unresolved.

**Tail guard (L637–652)**: dispositions for `units_without_statement` must be in the support/excluded/post-treatment/non-enrollment set, else None. Then any candidate overlapping unproven units/unproven spans → None.

**Final rejection (L715–717)**: `if check_protocol_control_batch_candidates(batch, output): return None`.

---

## 3. `_restricted_capability_batch` — wire-vs-unwire selection (lines 100–212)

This is reached only when `result.capability_wire is not None`. Top guard (L113–120):
```python
if (wire is None or interpretation is None or result.final_output is not None
        or result.status != "需要核对" or attempt.outcome != "publication_invalid"
        or "TIME_PRECISION_UNSUPPORTED" not in attempt.error_classes
        or set(attempt.error_classes) - {"TIME_PRECISION_UNSUPPORTED", "PUBLICATION_GATE_REJECTED"}
        or result.source_definition_consumers is not None
        or any(item.unresolved or "calculation_input" in item.decision_functions
               for item in interpretation.statements)):
    return None
```
Any source `unresolved` statement disqualifies this path. There is no author-wire/candidate-route branching inside this function beyond the discipline "capability_wire required".

---

## 4. `_temporal_restriction_indexes` (lines 51–97)

Header hard identity check (L63–68):
- `error_classes == {"TEMPORAL_SCOPE_UNRESOLVED"}` (exact equality, not subset).
- `detail.code == "TEMPORAL_SCOPE_UNRESOLVED"`, `detail.json_path == "/items"`, `detail.retry_class == "temporal_scope_review"`.

Index sanity (L70–75): `ids` is a sorted set of ints in range; `affected_dependents == ids`.

Unit-spans/review-match (L77–85): `additional_requirement` review items must equal the indices (and other non-`{covered_by_official, covered_by_procedure, additional_requirement}` review items are forbidden when not whole_unit). When `whole_unit=False`, every other decision outside `{covered_by_official, covered_by_procedure, additional_requirement}` → None.

Per-statement gate (L87–96):
- `statement.unresolved` → None.
- whole_unit vs not: requires `source_statement_is_standalone_action(statement)` (not whole_unit) vs a relaxed action/decision check (whole_unit).
- Not whole_unit requires `source_statement_context_is_self_contained`.
- `requires_temporal_resolution(interpretation, index)` must be True.

Critical takeaway: when the failure is `SOURCE_TARGET_REVIEW_UNRESOLVED` (not temporal), `_temporal_restriction_indexes` returns None. The temporal path bypasses `covered_by_official/covered_by_procedure`.

---

## 5. `_coexisting_statement_proofs` (lines 215–316) — conditions to prove a unit

Headers (L240–242): disposition MUST be `OTHER_CONTROL_CANDIDATE` AND `candidates` non-empty. Else None.

Restrict-set vs independent-set (L243–245): `independent_indexes = [index for index in indexes if index not in restricted_indexes]`; must be non-empty, else None.

Range-covering (L246–251): every statement's quoted text must locate in `unit.excerpt` (else None) and `source_statement_ranges_cover_unit` must pass.

Per-independent-statement checks (L253–268):
- `statement.unresolved` → None.
- `coverage[index].status != "expressed"` → None.
- not `source_statement_context_is_self_contained` → None.
- not `source_statement_is_standalone_action` → None.
- `offsets` missing → None.
- No candidate cites that exact unit quote → None.

No-candidate-may-cite-restricted (L270–277): if any retained candidate cites a restricted statement's quote → None.

Per-restricted-statement preparation (L280–288):
- Must satisfy `not statement.unresolved and index not in temporal_indexes` XOR `statement.unresolved` is OK if temporal — i.e. a non-unresolved statement that is NOT temporal → None.
- self-contained/standalone action checks.
- offsets in unit excerpt.

Borrowed-label and overlap checks (L290–296):
- ANY independent statement with `scope_context_unit_id is not None` → None ("Existing same-unit independence proofs do not prove borrowed label dependencies; retain the whole unit until they do").
- Overlapping offsets between restricted and independent ranges → None.

It can therefore prove a unit ONLY when:
- disposition is `OTHER_CONTROL_CANDIDATE`,
- restricted statements are temporally restricted or truly unresolved,
- restricted and independent ranges are disjoint,
- no independent statement uses borrowed scope labels,
- at least one candidate per independent statement literally cites the unit quote.

---

## 6. `_whole_unit_restriction` (lines 319–475)

Header guard (L330–336):
```python
if (result.partial_wire is None
        or (result.source_definition_consumers is not None
            and not result.restricted_source_definition_consumer_attempts)
        or set(result.attempts[-1].error_classes) not in (
            {"SOURCE_TARGET_REVIEW_UNRESOLVED"}, {"TEMPORAL_SCOPE_UNRESOLVED"},
        )):
    return None
```
**Already a major signal**: this path requires `result.partial_wire is not None` — it is unreachable when there is NO author wire. Combined with `_restricted_statement_batch_from_review`'s `has_wire` guard, an author wire and partial candidates are mandatory inputs to retain anything via this restricted-source path. When there is no wire at all (`partial_wire is None`), the restricted source recovery cannot produce anything.

Hydration & coverage parity (L339–343): hydrates wire; if `check_protocol_control_batch_candidates` flags anything OR coverage parity drifts → None.

Temporal proof (L348–352): when the error class is temporal, `_temporal_restriction_indexes(..., whole_unit=True)` must succeed; else None.

Uncertain + temporal composition (L353–355): `(not uncertain and not temporal_indexes)` → None; any uncertain item without `unresolved_aspects` → None.

**Multi-statement requirement (L363–364)**: `if not any(len(by_unit[unit_id]) > 1 for unit_id in restricted_units): return None`. The restricted set must contain at least one multi-statement unit — single-statement units fall through to `_restricted_statement_batch_from_review`, not this whole-unit path.

Per-unit check (L367–399):
- For restricted units: disposition MUST equal `OTHER_CONTROL_CANDIDATE` (L369), else None.
- All statement offsets must locate in the unit excerpt and must not overlap (L371–377): "if any(left[1] > right[0] for left, right in zip(ordered, ordered[1:])): return None".
- scope_quote range handling with strict subset/overlap rules (L380–398).

Per non-restricted index (L400–421):
- `statement.unresolved` → None (a remaining unresolved in a non-restricted unit is fatal).
- `item is None` AND coverage not `expressed/semantically_aligned` AND disposition not in `{POST_TREATMENT_EXECUTION, NON_ENROLLMENT_EXECUTION, PHASE_EXCLUDED, ADMINISTRATIVE_STATISTICAL_BACKGROUND}` → None.
- `item.decision == "additional_requirement"` → coverage must be `expressed/semantically_aligned`.
- Otherwise decision must be in `{covered_by_official, covered_by_procedure, definition_dependency, potential_same_requirement, background_context, cited_external_rationale}` — **"unresolved" is NOT in that whitelist**, so an unresolved review item on a non-restricted unit will return None.

**Candidate-removal discipline (L422–431)**: a removed candidate whose `frozen_structure_unit_ids` is not a subset of `restricted_units` → None ("A shared candidate cannot be removed without limiting its other source units as well. No guessed dependency expansion is performed here."). Any retained candidate sharing `source_span_ids` with restricted spans → None.

`limitation_kind` (L449): `"consumer_unavailable"` when `temporal_only` (i.e. no uncertain), else `"interpretation_unresolved"`. So a whole-unit cap with no temporal trigger gets `"interpretation_unresolved"`.

Final gate (L473–475): `check_protocol_control_batch_candidates` must pass.

**Disposition requirement**: `OTHER_CONTROL_CANDIDATE` is required on the wire for every restricted unit (L369), and the unprocessed disposition whitelist explicitly excludes `OFFICIAL_ELIGIBILITY` and `REQUIRED_PROCEDURE` — meaning a unit classified as REQUIRED_PROCEDURE on the wire cannot be wholly restricted through this path either.

---

## 7. RestrictedProtocolControlStatement construction sites

There are three construction points, all producing the same field shape:

**(a) Capability path `_restricted_capability_batch` (L179–190)**:
```python
RestrictedProtocolControlStatement(
    restricted_statement_id=f"restricted:{digest}",
    source_structure_unit_id=unit_id, source_statement_index=index,
    source_quote=unit.excerpt, source_span_ids=sorted(unit.source_span_ids),
    limitation_kind="consumer_unavailable",
    unresolved_dimensions=["当前系统尚不支持原文所需的小时或分钟精度计算"],
    time_words=list(statement.time_words),
    exception_words=statement.exception_words,
    affected_stage=statement.affected_stage,
    decision_functions=list(statement.decision_functions),
    source_force=statement.force,
)
```

**(b) Whole-unit path `_whole_unit_restriction` (L445–460)**:
```python
RestrictedProtocolControlStatement(
    restricted_statement_id=f"restricted:{digest}",
    source_structure_unit_id=unit_id, source_statement_index=index,
    source_quote=source.quoted_text, source_span_ids=sorted(units[unit_id].source_span_ids),
    limitation_kind="consumer_unavailable" if temporal_only else "interpretation_unresolved",
    unresolved_dimensions=[
        ("同一原文单元的持续期或跨节点要求尚未完成核对，未证明各要求可独立采用；本单元整体保留待核"
         if temporal_only else
         "同一原文单元的对应关系尚未核清，未证明各要求可独立采用；本单元整体保留待核"),
        *aspects,
    ],
    scope_quote=source.scope_quote, scope_context_unit_id=source.scope_context_unit_id,
    time_words=list(source.time_words), exception_words=source.exception_words,
    affected_stage=source.affected_stage, decision_functions=list(source.decision_functions),
    source_force=source.force,
)
```

**(c) Statement-level path `_restricted_statement_batch_from_review` (L666–686)**:
```python
RestrictedProtocolControlStatement(
    restricted_statement_id=f"restricted:{digest}",
    source_structure_unit_id=source.structure_unit_id,
    source_statement_index=index,
    source_quote=source.quoted_text,
    source_span_ids=sorted(unit.source_span_ids),
    limitation_kind=("consumer_unavailable" if index in temporal_indexes
                     else "interpretation_unresolved"),
    unresolved_dimensions=(
        ["当前系统尚未完成本条持续期或跨节点时间要求的核对，不能用于判定", *aspects]
        if index in temporal_indexes else aspects
    ),
    independent_scope_proof=proofs.get(index),
    scope_quote=source.scope_quote,
    scope_context_unit_id=source.scope_context_unit_id,
    time_words=list(source.time_words),
    exception_words=source.exception_words,
    affected_stage=source.affected_stage,
    decision_functions=list(source.decision_functions),
    source_force=source.force,
)
```

`limitation_kind` is always one of the two literals: `"consumer_unavailable"` or `"interpretation_unresolved"`. There is no `"correspondence_unresolved"` or similar.

---

## 8. `_validate_restricted_definition_registration` (lines 478–501)

Trigger condition (L484): only runs when `result.source_definition_consumers is not None`. Otherwise no-op.

If consumers exist:
- L486–487: `len(attempts) != 1` → `raise ValueError("受限定义登记缺少唯一实际回答")`.
- L490–493: `attempt.outcome != "parsed"` OR raw text length/hash mismatch → `raise ValueError("受限定义登记原答与实际回执不一致")`.
- L495–497: `declaration.version != SOURCE_DEFINITION_CONSUMER_VERSION` OR `declaration != result.source_definition_consumers` → `raise ValueError("受限定义登记字段与实际原答不一致")`.
- L498: `validate_source_definition_consumers(batch, result.source_interpretation, declaration)`.
- L499–501: `validate_restricted_definition_consumers(batch, result.source_interpretation, declaration, output.restricted_statements)` (not inspected here; only called).

This function can raise ValueError; the two callers above (`restricted_batch_from_review` L739, L757) DO NOT catch it — so a registration mismatch aborts the function and propagates upward.

---

## Caller chain in `protocol_control_execution.py`

Line numbers and the exact error/stop conditions around each call:

- **L124**: `from app.services.protocol_control_restricted_source import restricted_batch_from_review` (import at L124).
- **L233**: `_INDEPENDENT_DEEP_READ_POLICY = {... "error_codes": ["PROTOCOL_CONTROL_SOURCE_TARGET_REVIEW_UNRESOLVED"], "max_failed_steps": 2 ...}` — the independent-deep-read budget is keyed on `SOURCE_TARGET_REVIEW_UNRESOLVED`.
- **L1252–1266**: inside checkpoint re-hydrate; if `checkpoint.get("restricted_batch") is not None`, calls `expected = restricted_batch_from_review(batch, run_result)` and asserts `expected is None or saved != expected` → raises `PROTOCOL_CONTROL_CHECKPOINT_INVALID`. Otherwise extracts `restricted_indexes = {item.source_statement_index for item in saved.restricted_statements}` (L1265) used downstream for `potential_same_requirement` exemption. Failure mode: revalidation drift aborts with "受限来源与逐项核对不一致" (L1256).
- **L2809–2883**: `_preserved_unresolved_review_proof` — requires last attempt `outcome == "publication_invalid"` and `error_classes == ["SOURCE_TARGET_REVIEW_UNRESOLVED"]` (exact list equality, L2809). Then `restricted = restricted_batch_from_review(batch, result)` (L2864). If restricted is None, has candidates, has no restricted_statements, or any restricted_statement has `independent_scope_proof` → return None (L2865–2869). This is the dedicated SOURCE_TARGET_REVIEW_UNRESOLVED proof gate.
- **L3145**: revalidation path on `restricted_batch` saved slot. Wraps the call in a `try/except SourceTargetReviewValidationError as exc:` branch (L3146). Special-cases `exc.code == "SOURCE_UNRESOLVED_STILL_EXCLUDED"` with a validator_version check (L3147–3149). Any other ValueError or mismatch → "已保存的受限来源与当前逐项核对不一致" (L3155).
- **L3547**: another rehydration context (`_validated_deep_source`). On `expected is None or expected != saved["restricted_batch"]` → `raise ValueError("已保存的受限来源与当前逐项核对不一致")` → wraps into `PROTOCOL_CONTROL_DEEP_SOURCE_INVALID` (L3568–3571).
- **L3796**: definition registration tail revalidation. `revalidated = restricted_batch_from_review(batch, result)`; any ValueError → `PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_INVALID` ("定义登记未通过原答与来源核验，原文和失败记录保留"); drift `revalidated != restricted_batch` → same StepFailure (L3807–3816). Note: this revalidation is intentionally present — saved checkpoints can be invalidated by registration drift.
- **L4016**: in revalidate-prior branch; `restricted = restricted_batch_from_review(batch, prior_result)`. Any ValueError → `PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID` ("已保存的未决来源未通过当前逐项重核，原记录保持", L4018). If returns None → fall to `proof["error_code"]` (`PROTOCOL_CONTROL_DEEP_SOURCE_INVALID` etc., L4038–4044).
- **L4166**: live restricted-batch creation. Wraps the call in `try/except ValueError as exc` (L4167). On ValueError, `restricted_error = exc` is non-None; on the `restricted_batch is None` branch (L4176+), a giant `source_review_failure_codes` set (L4178–4204) — which explicitly contains `SOURCE_TARGET_REVIEW_UNRESOLVED` (L4194) and `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED` (L4199) — drives the StepFailure. The error-code → human-readable mapping has: `"SOURCE_TARGET_REVIEW_UNRESOLVED": "原文已保存，但它与审核要求的对应关系仍需核清；尚不能作为完整采用依据。"` (L4234–4235). The error class determines whether the StepFailure is `retryable=True` (only transport codes — L4210–4219).
- **L4741**: assignment loop in stage assembler; if `expected is None or restricted != expected` → `raise ValueError("受限来源与已保存的原文核对不一致")` → `PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID` ("受限来源陈述未通过逐条原文重核", L4747–4752).

---

## Direct answers to the audit questions

**Disposition kinds required**:
- Coexisting statement proof: `OTHER_CONTROL_CANDIDATE` only (L240).
- Whole-unit restriction: every restricted unit must be `OTHER_CONTROL_CANDIDATE` (L369); non-restricted units fall back to `OFFICIAL_ELIGIBILITY`, `REQUIRED_PROCEDURE`, or `POST_TREATMENT_EXECUTION`/`NON_ENROLLMENT_EXECUTION`/`PHASE_EXCLUDED`/`ADMINISTRATIVE_STATISTICAL_BACKGROUND` per whitelist at L406–421.
- Capability path: non-restricted units must keep `OTHER_CONTROL_CANDIDATE` (L164); units_without_statement must use the support/excluded/post-treatment/non-enrollment set (L193–199).

**Are candidate drafts (wire) required?** Yes — both whole-unit path (`result.partial_wire is None` ⇒ None, L330) and statement-level path with `has_wire=False` use a heavily-disciplined fallback (every statement unresolved, no covered decisions, all in `{unresolved, additional_requirement}`, no `units_without_statement`; else None, L557–566). With a wire, candidate `source_span_ids` must not intersect restricted spans (L430, L649–651).

**No candidates but wire with dispositions linking to required_procedure targets**? This is not a recognized branch. The wire path requires the review decisions to fit within `covered ∪ {unresolved} ∪ {additional_requirement ∩ temporal_indexes}` (L548–551). A wire with no candidates would fail the hard "candidate must cite unit quote" requirement inside `_coexisting_statement_proofs` (L267) and the strict per-unit disposition requirements at L616–636. It returns None.

**Statement-level vs whole-unit restriction**: statement-level retains candidate only with `OTHER_CONTROL_CANDIDATE` + disjoint literal ranges (L596, L599 succeeds) + non-overlapping timing; whole-unit kicks in when `_coexisting_statement_proofs` fails AND the unit has multiple statements (forced by L363) OR the single-statement case fails the additional `unresolved or temporal_only` test (L600–606). Statement-level uses `independent_scope_proof`; whole-unit does not.

**`source.unresolved` required, or `review.unresolved` ok?** Both can qualify. The temporal path explicitly allows non-unresolved statements (L92, "statement.unresolved" returns None). The whole-unit path accepts `uncertain = [item for item in review.items if item.decision == "unresolved"]` (L346) so review-level unresolved carries it. Statement-level path requires `source.unresolved` OR membership in `temporal_indexes` (L601–605). The coexisting path also accepts temporal indexes for non-unresolved statements (L282).

**Unresolved correspondence vs covered_by_procedure**: `covered_by_procedure` (and `covered_by_official`) is hard-disallowed on the no-wire branch (L562) and is allowed-but-not-stricter on the wire branch (L548). On the wire path, "covered" decisions DO NOT enter `unresolved_indexes` (L572–573: `if item.decision in {"unresolved", "additional_requirement"}`). The per-non-restricted-index check forces `REQUIRED_PROCEDURE` units with `covered_by_procedure` to keep `target_id ∈ linked_procedure_catalog_item_ids` (L631–636); if target can't be named, it returns None. So when required_procedure correspondence is unresolved, the candidate cannot be retained through the restricted-source pipeline.

---

## Parts I did NOT inspect

- `app.agents.protocol_control_source_interpretation.validate_source_target_review`, `validate_source_interpretation`, `validate_restricted_definition_consumers`, `validate_source_definition_consumers` — only called; semantics/inner conditions not re-traced.
- `ProtocolControlAgentRunResult`, `ProtocolControlBatchDispositionHydrated`, `RestrictedProtocolControlStatement` model validators — only field usage inspected; Pydantic-side rules not re-traced.
- `app.protocols.protocol_control_gate.check_protocol_control_batch_candidates`, `locate_source_quote_offsets`, `source_statement_context_is_self_contained`, `source_statement_is_standalone_action`, `source_statement_ranges_cover_unit`, `candidate_cites_unit_quote` — only called.
- `app.agents.protocol_control_stage_compiler.requires_temporal_resolution` — only called.
- `app.protocols.source_time_fragments.intraday_time_fragments` — only called.
- The full `protocol_control_execution.py` file beyond the lines I read for caller context (~L120–480, L1218–1290, L2800–2895, L3530–3820, L3995–4070, L4150–4260, L4725–4795). Other call sites of `restricted_batch_from_review` (e.g. L4586 mentioned by grep but not read in depth) were not deeply inspected.
- Anything outside the two listed files (including other services, repositories, and the discovery-step path).

# Read-Only Report: `app/agents/protocol_control_source_interpretation.py`

Scope of inspection: lines 1–1640 and 1701–2060 of the file at the absolute path above. Helper functions outside this file (`_visit_scope_keys` imported from `app.protocols.protocol_control_gate`) were NOT inspected.

---

## 1. Models: `SourceTargetReviewItem` and `SourceTargetReview` (lines 846–868)

```python
846→class SourceTargetReviewItem(ContractModel):
847→    statement_index: int = Field(ge=0)
848→    decision: Literal[
849→        "covered_by_official", "covered_by_procedure", "additional_requirement",
850→        "not_current_control", "unresolved", "potential_same_requirement",
851→        "cited_external_rationale", "background_context", "definition_dependency",
852→    ]
853→    target_id: str | None = None
854→    source_action_excerpt: str = Field(min_length=1)
855→    target_action_excerpt: str | None = None
856→    source_time_excerpt: str | None = None
857→    target_time_excerpt: str | None = None
858→    target_scope_excerpt: str | None = None
859→    source_object_excerpt: str | None = None
860→    target_object_excerpt: str | None = None
861→    unresolved_aspects: list[str] = Field(default_factory=list)
862→    non_control_basis_excerpt: str | None = None
863→    attribution_excerpt: str | None = None
864→
865→
866→class SourceTargetReview(ContractModel):
867→    version: Literal[SOURCE_TARGET_REVIEW_VERSION]
868→    items: list[SourceTargetReviewItem]
```

The decision literal set (lines 848–852) contains nine values. `target_id` is the only target-anchor field and is nullable. Fields available for recording "the limitation" rather than proving a target: `unresolved_aspects` (line 861), `non_control_basis_excerpt` (line 862), `attribution_excerpt` (line 863).

---

## 2. `build_source_target_review_prompt` (lines 1432–1640) — guard/contract language

Selected verbatim lines:

- **1543–1548 (separation between source ambiguity and missing target support):**
  > "unresolved 是当前冻结来源解释尚未核清的具体维度，不是受试者缺件。此字段非空时，不得选择 covered_by_official 或 covered_by_procedure；目标文字相同也不能消除已保存的来源疑问。"
  > "未核清的原文也不得作为 not_current_control、potential_same_requirement 或 cited_external_rationale 关闭；只能在现有未完整覆盖路径中保留具体 unresolved_aspects，不将原文疑问改写成受试者缺件。"

- **1564 (shared-visit positions, not a proof):**
  > "shared_visit_source_positions 只表示多访视共用位置，不是时间已对应的证明。"

- **1577 (frequency-only is not period/duration proof):**
  > "仅有每日或每周给药次数相同，不证明审核时期或持续期相同；须保留时间范围待核。"

- **1583–1585 (shared paragraph across visits is not visit-specific proof):**
  > "若多个访视目录项共用同一段说明，不能仅因该段包含本条时期就说所选访视已覆盖；还须核对该目录项独有的访视名称或独有来源。"

- **1597–1608 (potential_same_requirement is registered, not closed; only this decision may carry object/scope excerpts):**
  > "potential_same_requirement 只可引用给出的另一只读原文单元 … 此判断仅登记待核关系，不等于已有控制覆盖。"
  > "source_object_excerpt、target_object_excerpt、target_scope_excerpt 仅限 potential_same_requirement；其他所有 decision 的这三个字段必须填 null …"

- **1613–1617 (JSON contract):**
  > `"decision":"covered_by_official|covered_by_procedure|additional_requirement|not_current_control|unresolved|potential_same_requirement|cited_external_rationale|background_context|definition_dependency"`
  > `"unresolved_aspects":[],"non_control_basis_excerpt":null,"attribution_excerpt":null` … "枚举值只选一个，未知目标填 null；非跨章节关系的对象与另一来源时期字段一律填 null。"

---

## 3. `validate_source_target_review` (lines 1701–2060)

The function loops over `review.items` and uses a `reject(item, code, field, message)` helper (lines 1719–1726) that raises `SourceTargetReviewValidationError` with a per-item `json_path` and the statement's `source_refs`. Every `reject` call below is a hard failure (the review cannot pass).

### 3.1 Scope, action-excerpt, and source-function guards (lines 1728–1748)

- **1708–1712 — `REVIEW_SCOPE_INVALID`** (rejects): review items' `statement_index` set must equal `target_review_indexes(...)` exactly.
- **1744–1745 — `SOURCE_ACTION_MISMATCH`** (rejects): `source_action_excerpt` normalized must appear in `quoted_text` (or in a bounded same-sentence subject extension).
- **1746–1748 — `SOURCE_FUNCTION_UNRESOLVED`** (rejects):
  > "原文对本节点审核的用途仍未核清，不能仅凭文字对应宣称已覆盖或无需审核"
  Fires when `statement.decision_functions == ["unclassified"]` AND `item.decision != "unresolved"`.

### 3.2 Source-ambiguity vs. closure-of-doubt guards (lines 1749–1761)

- **1749–1752 — `SOURCE_UNRESOLVED_STILL_COVERED`** (rejects): decision is one of `covered_by_*` AND `statement.unresolved` is true.
- **1753–1757 — `SOURCE_UNRESOLVED_STILL_EXCLUDED`** (rejects): `statement.unresolved` is true AND decision ∈ {`not_current_control`, `potential_same_requirement`, `cited_external_rationale`}. So `unresolved`-flagged statements must NOT be closed out by exclusion decisions.
- **1758–1761 — `UNRESOLVED_ASPECTS_MISSING`** (rejects): when the decision is NOT covered AND NOT in the open-ended set {`not_current_control`, `potential_same_requirement`, `cited_external_rationale`, `background_context`, `definition_dependency`} AND `unresolved_aspects` is empty.
  > "未完整覆盖的陈述必须说明待核实之处"
  In other words, an `additional_requirement` decision without `unresolved_aspects` is rejected; only the listed open decisions are allowed to leave the list empty.

### 3.3 Per-decision validators (lines 1762–1866)

These blocks enforce the prompt's per-decision contracts; each `reject` keeps the source interpretation intact while refusing the chosen label:

- **`cited_external_rationale` (1762–1782):**
  - `SOURCE_ATTRIBUTION_UNCONFIRMED` (1764–1772): requires `statement.control_authority == "cited_external_rationale"` AND `attribution_excerpt` matches `statement.attribution_quote` AND appears in the same sentence as `quoted_text` per `_attribution_in_same_sentence` (line 82).
  - `EXTERNAL_RATIONALE_STILL_CONTROL` (1773–1775): rejects if the statement is still an action candidate (`coverage_by_index[…].action_candidate_indexes` non-empty).
  - `SOURCE_ATTRIBUTION_SCOPE_INVALID` (1776–1781): rejects if any of `target_id, target_action_excerpt, source_time_excerpt, target_time_excerpt, target_scope_excerpt, source_object_excerpt, target_object_excerpt, non_control_basis_excerpt` is non-empty OR `unresolved_aspects` non-empty.
  - Then `continue` (line 1782) — bypasses all subsequent per-item checks for this decision.

- **`background_context` (1783–1801):**
  - `BACKGROUND_CONTEXT_UNPROVEN` (1799–1800): rejects unless `decision_functions == ["background"]`, `force ∈ {"descriptive","unclear"}`, `statement.unresolved` is False, `non_control_basis_excerpt` appears in `quoted_text`, and all target/excerpt/object/time/scope/attribution/aspects fields are null.
  - `continue` at line 1801.

- **`definition_dependency` (1802–1813):**
  - `DEFINITION_DEPENDENCY_UNPROVEN` (1811–1812): rejects unless `is_non_action_definition(statement)` (line 1012) AND no candidate indexes AND all target/excerpt/object/time/scope/basis/attribution fields null AND `unresolved_aspects` empty.
  - `continue` at line 1813.

- **Cross-decision guards between 1814 and 1820:**
  - `SOURCE_ATTRIBUTION_UNEXPECTED` (1814–1816): rejects `attribution_excerpt` for any non-`cited_external_rationale` decision.
  - `SOURCE_ATTRIBUTION_DECISION_INVALID` (1817–1820): rejects if `statement.control_authority == "cited_external_rationale"` AND decision != `"unresolved"`.

- **`potential_same_requirement` (1821–1866):**
  - `CONTEXT_TARGET_ID_INVALID` (1824–1828): rejects if `target_id` matches a `source_ref` rather than a `structure_unit_id`.
  - `CONTEXT_RELATION_UNGROUNDED` (1843–1854): rejects unless both unit excerpts contain the action verbatim, both contain the same object (≥ 3 chars), object is in same clause as action on both sides, scope precedes action, and no clause boundary between scope and action.
  - `CONTEXT_RELATION_UNRESOLVED` (1855–1859): rejects if `unresolved_aspects` is non-empty OR `non_control_basis_excerpt`, `source_time_excerpt`, or `target_time_excerpt` is non-null.
  - `CONTEXT_RELATION_DIMENSION_MISSING` (1860–1865): rejects if `statement.time_words` (or `exception_words`) are not present in the other unit's excerpt.
  - `continue` at line 1866.

### 3.4 Target binding, time equivalence, and the two visit-scope guards (lines 1867–2060)

- **1867–1870 — `CONTEXT_SCOPE_UNEXPECTED`** (rejects): `target_scope_excerpt`, `source_object_excerpt`, or `target_object_excerpt` set for any decision that isn't `potential_same_requirement`.
- **1871–1872 — `TARGET_ACTION_INCOMPLETE`** (rejects): `bool(target_id) != bool(target_action_excerpt)`.
- **1873–1875 — `FROZEN_TARGET_MISSING`** (rejects): when `target_id` is empty AND (`covered` is True OR `target_time_excerpt` is set).
  > "目标时间或完整覆盖必须有冻结目标"
  CRITICAL for (b): this is the only place where "no target_id" is rejected, and only when the decision claims coverage or anchors a target time. `unresolved`, `additional_requirement`, `not_current_control`, `potential_same_requirement`, `cited_external_rationale`, `background_context`, and `definition_dependency` are all permitted with `target_id = None`.
- **1877–1883:** if `target_id` is set, `target` is looked up in `official` (for `covered_by_official`), `procedures` (for `covered_by_procedure`), or either (for other decisions; must resolve uniquely).
- **1884–1885 — `FROZEN_TARGET_INVALID`** (rejects): `target_id` set but `target` not resolvable.
- **1887–1905 — `not_current_control` block:**
  - `POST_ELIGIBILITY_BASIS_INVALID` (1892–1895): rejects unless `non_control_basis_excerpt` is a contiguous slice of the same unit's `excerpt` that precedes the action.
  - `POST_ELIGIBILITY_SEQUENCE_UNCONFIRMED` (1896–1899): rejects unless `statement.eligibility_sequence == "after_eligibility_decision"` and basis equals `statement.eligibility_sequence_quote`.
  - `POST_ELIGIBILITY_ACTION_STILL_CONTROL` (1900–1902): rejects if the statement is still an action candidate.
  - `POST_ELIGIBILITY_SCOPE_UNRESOLVED` (1903–1905): rejects if `unresolved_aspects` is non-empty.
- **1906–1908 — `POST_ELIGIBILITY_BASIS_UNEXPECTED`:** `non_control_basis_excerpt` set for any decision that isn't `not_current_control`.
- **1909–1915 — `TARGET_LINK_MISMATCH`:** when `covered` and `entry.status == "linked_only"`, the chosen `target_id` must be in the draft's linked set.
- **1916–1920 — `TARGET_PROCEDURE_ROW_UNPROVEN`:** when `covered_by_procedure`, schedule row labels from the source must appear in the target.
- **1921–1936:** general target-excerpt grounding; `TARGET_ACTION_UNGROUNDED` and `TARGET_ACTION_LABEL_ONLY_UNPROVEN` reject when the target's `label` alone is cited without action-text verification (line 1933–1936).
- **1937–1976:** source-time grounding helpers (`inherited_leading_time`, `source_time_is_composite`, `source_time_in_scope`); `SOURCE_TIME_INCOMPLETE` (1962–1968) and `SOURCE_TIME_UNGROUNDED` (1973–1976) reject time excerpts not anchored in `quoted_text`, `scope_quote`, heading path, or `time_words`.
- **1977–1982 — `TARGET_TIME_UNGROUNDED`:** rejects if `target_time_excerpt` isn't found in any of `target_excerpts` (or `procedures[id].visit_instance`).

### 3.5 The frequency-only guard (lines 1983–1992)

```python
1983→        if covered and statement.time_words and all(
1984→            re.fullmatch(r"每(?:日|天|周|月)(?:\d+|[一二三四五六七八九十]+)次", normalize_source_excerpt(word))
1985→            for word in statement.time_words
1986→        ):
1987→            scope = normalize_source_excerpt(statement.scope_quote or "")
1988→            target_scopes = [*target_excerpts]
1989→            if item.target_id in procedures:
1990→                target_scopes.append(procedures[item.target_id].visit_instance)
1991→            if not scope or not any(scope in normalize_source_excerpt(value) for value in target_scopes):
1992→                reject(item, "FREQUENCY_ONLY_COVERAGE", "target_time_excerpt", "给药频次相同仍须证明来源与目标属于同一访视范围")
```

Conditions to fire: `covered` is True AND every `time_words` entry matches the regex for frequency-only phrases (`每日N次 / 每天N次 / 每周N次 / 每月N次` with N a digit or Chinese numeral). Then the validator requires `statement.scope_quote` to appear in one of the target's `source_excerpts` or its `visit_instance`. The error code is `FREQUENCY_ONLY_COVERAGE` and the message reads "Even with identical dosing frequency, source and target must still be shown to share the same visit scope."

Note the boundary: this only triggers when `covered` is True. A review that admits it cannot prove coverage (e.g. `additional_requirement` or `unresolved`) does not hit this guard.

### 3.6 The shared-time / shared-visit guard (lines 1995–2030)

```python
1995→        if item.decision == "covered_by_procedure" and source_time and target is not None:
1996→            shared_time_spans = {
1997→                span_id
1998→                for span_id, excerpt in zip(target.source_span_ids, target.source_excerpts)
1999→                if excerpt and target_time in normalize_source_excerpt(excerpt)
2000→                and any(
2001→                    other.catalog_item_id != target.catalog_item_id
2002→                    and other.visit_instance != target.visit_instance
2003→                    and any(
2004→                        other_span == span_id and other_excerpt
2005→                        and target_time in normalize_source_excerpt(other_excerpt)
2006→                        for other_span, other_excerpt in zip(
2007→                            other.source_span_ids, other.source_excerpts
2008→                        )
2009→                    )
2010→                    for other in procedures.values()
2011→                )
2012→            }
2013→            if shared_time_spans:
2014→                visit = normalize_source_excerpt(target.visit_instance)
2015→                specific_quote = any(
2016→                    excerpt and target_time in normalize_source_excerpt(excerpt)
2017→                    and span_id not in shared_time_spans
2018→                    for span_id, excerpt in zip(target.source_span_ids, target.source_excerpts)
2019→                )
2020→                source_visits = _visit_scope_keys(source_time)
2021→                target_visits = _visit_scope_keys(visit)
2022→                relative_or_excluded = bool(re.search(
2023→                    r"(?:其余|其他|剩余|后续)(?:的)?访视|除[^。；;]{0,30}外",
2024→                    source_time,
2025→                ))
2026→                if not specific_quote and (
2027→                    relative_or_excluded or not source_visits or not source_visits <= target_visits
2028→                ):
2029→                    reject(item, "TARGET_VISIT_SCOPE_UNPROVEN", "target_id",
2030→                           "多个访视共用原文，所选流程目标缺少本条时期的独立访视依据")
```

What `shared_time_spans` collects: the span IDs where (a) the chosen target's own excerpt contains `target_time` AND (b) some other procedure with a different `visit_instance` references the same `span_id` AND also contains `target_time`. If that set is non-empty:

- A `specific_quote` is computed as a target excerpt that contains `target_time` from a span NOT in `shared_time_spans`.
- `_visit_scope_keys` is applied to both `source_time` and `target.visit_instance` (helper imported from `app.protocols.protocol_control_gate`).
- A relative/excluded regex fires on `source_time` for phrases like "其余/其他/剩余/后续 访视" or "除…外".
- If there is no `specific_quote` AND (relative_or_excluded OR `source_visits` empty OR `source_visits` not a subset of `target_visits`), reject with `TARGET_VISIT_SCOPE_UNPROVEN`: "Multiple visits share the original text; the chosen procedure target lacks an independent visit basis for this statement's period."

Boundary: this guard fires only for `covered_by_procedure` with a non-null `target` and a non-empty `source_time`. Other decisions (including `additional_requirement`, `unresolved`, `not_current_control`, `cited_external_rationale`, etc.) are not touched here, and the `relative_or_excluded` clause explicitly tolerates cases where the source names the visit directly or where `source_visits <= target_visits` even with a shared excerpt.

### 3.7 Final per-coverage checks (lines 2031–2060)

- **2031–2032 — `COVERED_WITH_GAPS`** (rejects): `covered` AND `unresolved_aspects` non-empty.
- **2033–2037 — `TARGET_EXCEPTION_UNGROUNDED`:** exception words not found in target excerpts.
- **2038–2057 — `TIME_SCOPE_MISMATCH` and `TARGET_TIME_INCOMPLETE`:** uses `_same_explicit_day_week_window` (line 47) for exact relative day/week window equivalence; otherwise requires every `time_words` token to appear in target's `source_excerpts` or `visit_instance`.
- **2058–2060 — `TIME_INVENTED`:** rejects time excerpts on statements that have no time words.

---

## 4. Direct answers to the three questions

### (a) Is there an existing review decision that can record "the target mapping is genuinely unproved" while keeping the original requirement intact and non-executable, with no `source.unresolved`?

Yes — multiple.

- **`decision == "additional_requirement"`** is exactly the label the prompt at line 1580–1582 prescribes for "the source has its action/object/relative-time clearly anchored, but the existing target is missing the time point":
  > "若本条来源的动作、对象和相对时点本身均有逐字依据，只是已有目标缺少该时点，应选 additional_requirement，引用已有目标作为对照并写明时间差额；只有来源动作或适用时期自身无法从本条及其明确范围核清时才选 unresolved。"
  Validation: `UNRESOLVED_ASPECTS_MISSING` (line 1758–1761) forces the writer to enumerate the gap in `unresolved_aspects`. The decision can carry a `target_id` for cross-reference, but it does not claim coverage; the validator at line 1873–1875 only demands `target_id` when `covered` is True or a target time is asserted.

- **`decision == "unresolved"`** records that the source itself could not be grounded end-to-end. Validation: line 1746–1748 forces `unresolved` for `decision_functions == ["unclassified"]`; line 1761 lets `unresolved` (and the other open-ended decisions) pass without populating `unresolved_aspects`. `target_id = None` is permitted because the condition at line 1873–1875 only triggers on `covered` or non-null `target_time_excerpt`.

- **`decision == "potential_same_requirement"`** registers a same-requirement-to-other-unit hint for downstream re-verification (prompt line 1597–1602, validator lines 1821–1866). The validator requires the source and the other unit to share the action verbatim, the object, the time, and the exceptions; failures are rejected as `CONTEXT_RELATION_*`, not silently rewritten. `target_id` here must be the other unit's `structure_unit_id`, and the validator allows `target_id = None` only via `FROZEN_TARGET_MISSING`'s non-trigger.

- **`decision == "cited_external_rationale"`, `"background_context"`, `"definition_dependency"`, `"not_current_control"`** all leave the source verbatim record intact and only annotate classification; each `continue` block (lines 1782, 1801, 1813, 1866) bypasses the visit-scope checks so they do not over-restrict.

In every case, the validator preserves the original `statement.unresolved` flag and does not touch the source interpretation — the only `unresolved` mutations are in `unresolved_aspects` (a structured list on the review item), which is consumed separately.

### (b) Do any of these guards reject a decision merely because a single visit is not named (over-strict), or do they only reject treating a phrase match as proof of a particular visit?

Only the second.

- `FROZEN_TARGET_MISSING` (lines 1873–1875) only rejects an empty `target_id` when the decision asserts coverage or names a target time. Decisions that admit incompleteness (`unresolved`, `additional_requirement`, `not_current_control`, `potential_same_requirement`, `cited_external_rationale`, `background_context`, `definition_dependency`) are allowed to leave `target_id = None`.
- `FREQUENCY_ONLY_COVERAGE` (lines 1983–1992) only rejects `covered` decisions whose only time evidence is a frequency phrase and whose source `scope_quote` cannot be located in any of the target's `source_excerpts` or `visit_instance`. A reviewer who instead chooses `additional_requirement` or `unresolved` does not trigger this check at all (it is gated on `covered`).
- `TARGET_VISIT_SCOPE_UNPROVEN` (lines 1995–2030) only rejects `covered_by_procedure` when (i) `source_time` exists, (ii) another visit shares the same `span_id` and the same time phrase in its own excerpt, (iii) the chosen target has no other excerpt containing that time outside the shared spans, AND (iv) the source uses relative/excluded language OR its visit keys are empty OR they are not a subset of the target's visit keys. If the source names the visit directly and the visit keys align, the guard passes even with a shared span.

In short, both visit-related guards are refusal-of-coverage-without-proof, not blanket denial of unnamed visits.

### (c) What fields exist for recording the limitation, and which consumers read them?

Fields on `SourceTargetReviewItem`:

- `unresolved_aspects: list[str]` (line 861) — the primary "limitation" channel; required when the decision is `additional_requirement` (validator line 1758–1761) and forbidden (must be empty/null) for `cited_external_rationale`, `background_context`, `definition_dependency`, `potential_same_requirement`, `not_current_control` with `statement.eligibility_sequence != "after_eligibility_decision"`, and any `covered_by_*` (lines 1779–1812, 1855, 2031–2032).
- `non_control_basis_excerpt: str | None` (line 862) — for `not_current_control` only; rejected if set on any other decision (1906–1908).
- `attribution_excerpt: str | None` (line 863) — for `cited_external_rationale` only; rejected if set elsewhere (1814–1816).
- `source_object_excerpt`, `target_object_excerpt`, `target_scope_excerpt` — restricted to `potential_same_requirement` (lines 1867–1870 and prompt 1606–1608).

Consumers of `unresolved_aspects` within this file:

- `is_post_eligibility_calculation` (lines 871–883): `return bool(review.decision == "not_current_control" and … and not review.unresolved_aspects)`. Post-eligibility exclusion is suppressed whenever the reviewer recorded open aspects — the gap propagates.
- `SourceDefinitionConsumerItem` validator (lines 975–985 — read but not deeply inspected beyond the validator at 985): rejects empty strings inside `unresolved_aspects` (`if any(not aspect.strip() for aspect in self.unresolved_aspects)`).
- The `definition_consumer` build prompt at line 1194 references `unresolved_aspects` as a per-statement field that must be present when consumers exist (read in context of the definition-consumer prompt, not its runtime validator).
- `validate_source_target_review` itself reads `item.unresolved_aspects` at lines 1760, 1779, 1798, 1810, 1855, 1903, 2031 to enforce per-decision completeness.

Consumers of `non_control_basis_excerpt` and `attribution_excerpt`: read only inside `validate_source_target_review` for per-decision validation; no other consumer of these excerpt fields was identified in this file.

---

## 5. What I did NOT inspect

- The internals of `target_review_indexes` (line 1330), `_target_review_source_packet` (line 1399), `_native_table_source_packet` (line 1386), `_cell_scope_label_packet` (line 2895) — only their callers in `build_source_target_review_prompt` were read.
- `target_action_established` (line 2293), `_full_timed_official_clause_cited` (line 2273), `_statement_schedule_label_sources` (line 838), `_target_contains_row_label` (line 813) — referenced but not opened.
- `_visit_scope_keys`, which is imported from `app.protocols.protocol_control_gate` (line 22). Its semantics were inferred from usage at lines 2020–2021.
- `SourceDefinitionAtomConsumer` (line 889), `SourceDefinitionConsumerItem` (line 975), `SourceDefinitionConsumers` (line 990), and `validate_source_definition_consumers` (line 2100+) — only the `unresolved_aspects` validator at line 985 and the prompt excerpts at lines 1194–1200 were read.
- `validate_source_definition_consumers` and the rest of the file below line 2100.
- Any external callers of `SourceTargetReviewItem.unresolved_aspects` / `non_control_basis_excerpt` / `attribution_excerpt` outside this file.

Three parallel audits are back. Now verifying the decisive claims directly (2 of 8 reads).

Verifying the per-index decision branch myself (3rd read of 8).

# Conference Output: R1 adoption-boundary review (source81d31233) - evidence_single_object

## Output

### 1. Actual reason R1 cannot be used (verified in source, not inferred)

Your case is an **author-wire state**: there is a `partial_wire` with dispositions linking the statement to existing required-procedure targets, review decisions leave the correspondence unresolved, and the source interpretation carries no `source.unresolved`. Every existing R1 branch rejects that combination for the same structural reason — R1 has verdicts for "source ambiguity" and "consumer/temporal unfitness", but none for "source is clear, the author's target mapping is unproved".

Verified gates (`app/services/protocol_control_restricted_source.py`):

- Wire branch, first return (`_restricted_statement_batch_from_review`, lines 543-552): every review decision must be in `covered | {"unresolved"}` or be `additional_requirement` with `statement_index in temporal_indexes`. An `unresolved` decision *passes* this gate — so this is not the stopper by itself.
- Single-statement unit, second return (lines 599-607): when `_coexisting_statement_proofs` fails, the unit may still be restricted only if `interpretation.statements[index].unresolved` is truthy, or the index is temporal with quote == unit excerpt. Your statement has no `source.unresolved`, so this is where a **single-statement** general instruction dies. (`_temporal_restriction_indexes`, lines 51-97, cannot help: it requires `error_classes == {"TEMPORAL_SCOPE_UNRESOLVED"}` exactly, not the `SOURCE_TARGET_REVIEW_UNRESOLVED` class your run stopped on.)
- Per-index disposition branch (lines 614-636): `decision is None` + `OTHER_CONTROL_CANDIDATE` requires `coverage.status == "expressed"`; `covered_by_official` requires `OFFICIAL_ELIGIBILITY`; **everything else** requires `disposition == REQUIRED_PROCEDURE` **and** `decision.target_id` to be present in the linked procedure ids. An `unresolved` decision with `target_id = None` can never satisfy this — and note the branch is reached only for *independent* indexes, so it also cannot be the path that saves a restricted one.
- `_coexisting_statement_proofs` requires `OTHER_CONTROL_CANDIDATE` and non-empty candidates (agent-reported lines 240-242); `_whole_unit_restriction` requires each restricted unit's disposition to be `OTHER_CONTROL_CANDIDATE` and at least one restricted unit with more than one statement (verified lines 363-370). The user's unit is `REQUIRED_PROCEDURE`-labeled, so the whole-unit path returns `None` at line 370 (or line 364 if the unit has a single statement).

**Consequence (decisive contrary code to the "R1 can already do it" reading):** a review-level `unresolved` decision on a required-procedure-labeled unit, with no source ambiguity, is *not* reconcilable inside `_whole_unit_restriction` or the statement-level path as written. The nearest passing analogues in tests are (a) `test_mixed_source_review_keeps_covered_procedure_and_restricts_only_gap` (positive only when the decision is `covered_by_procedure` with a real link), and (b) `test_unresolved_review_keeps_non_enrollment_execution_from_verified_wire`, which additionally confirms that a wire-only/no-candidate-draft case with a required-procedure row raises `逐项来源核对必须且只能覆盖`. So the pipeline currently has no route that keeps the original requirement while marking the correspondence unproved.

### 2. Distinguishing the two classes (must not be merged)

- **Known wrong-source/meaning — stays rejected.** Mislinked or unsupported coverage is a semantic fault; R1 is "not repair of bad semantics" (`_whole_unit_restriction` docstring, lines 325-328). `FREQUENCY_ONLY_COVERAGE` (source interpretation lines 1983-1992) and `TARGET_VISIT_SCOPE_UNPROVEN` (lines 1995-2030) fire only on `covered` decisions and only refuse *treating a phrase match as proof of a particular visit* — they are not blanket denials of unnamed visits, and they must not be relaxed. Nothing below should let a coverage claim through.
- **Genuinely unproved target mapping — can be recorded non-executable.** The review model already has the honest label for it: `unresolved` with `unresolved_aspects` (allowed with `target_id = None`; `FROZEN_TARGET_MISSING` at lines ~1873-1875 rejects an empty target only when coverage or a target time is asserted). The gap is purely on the R1 consumer side.

### 3. Minimum change if justified (bounded, no new framework)

One gate, in `_restricted_statement_batch_from_review`: accept a restricted index whose review decision is `unresolved`, whose `target_id` is empty (an unproved mapping must not name a covering target), and whose wire disposition is `REQUIRED_PROCEDURE` **only when** all of the following hold — `not statement.unresolved`, `unresolved_aspects` non-empty, `error_classes == {"SOURCE_TARGET_REVIEW_UNRESOLVED"}`, and every actually linked target's excerpts remain frozen and untouched. Record it exactly as the existing restricted statement (`source_quote`, `source_span_ids`, `scope_quote`, `time_words`, `exception_words`, `affected_stage`, `decision_functions`, `source_force`), `independent_scope_proof = None`, `limitation_kind = "interpretation_unresolved"` (the only existing literal that says "not executable"; a distinct `correspondence_unresolved` literal is optional and would need downstream vocabulary). The same acceptance must be mirrored in `_whole_unit_restriction` if you want multi-statement units of the same shape, because its line-369 `OTHER_CONTROL_CANDIDATE` requirement blocks them today. Candidates for the restricted unit must be dropped (the existing per-index/candidate-intersection protections already forbid retaining them).

Everything else — source text, interpretation flags, review items, history, signing — stays as-is; no guards are removed, no failure is relabeled wholesale, no disease/drug phrasing rules are introduced, and the linked procedure is never claimed as covering.

### 4. Positive / unsafe-negative cases and downstream consumers

**Positive:** general instruction (daily frequency / suggested time-of-day / rest-before-exam), source interpretation without `unresolved`, wire disposition `REQUIRED_PROCEDURE` with a real linked target, review item `unresolved` with `target_id = None` and a written `unresolved_aspects` → restricted statement emitted, unit `RESTRICTED_SOURCE`, no candidate for that unit. Existing whole-mixed fixture (`_same_unit_two_requirement_review`) is the natural template.

**Unsafe negatives that must stay refused:** the same shape but with a `target_id` naming the procedure or any `covered_by_*` decision (that is a coverage claim and must be rejected); `unresolved_aspects` empty; `statement.unresolved` non-empty routed through this new gate instead of the existing interpretation path (that would blur source ambiguity into mapping uncertainty); `error_classes` not exactly `SOURCE_TARGET_REVIEW_UNRESOLVED`; any candidate retained for the restricted unit or intersecting its spans; the string-shared/duplicate-quote and "source words omitted" variants already covered by existing negative tests.

**Downstream consumers needing validation:** `protocol_control_execution.py` revalidates the saved restricted batch at several points (the checkpoint rehydrate path, the `_preserved_unresolved_review_proof` gate keyed on `SOURCE_TARGET_REVIEW_UNRESOLVED`, the deep-source and stage-assembler rebuild paths, and the definition-registration tail) — any new acceptance must round-trip identically through all of them or the run fails with a restricted-source-invalid error; plus `_validate_restricted_definition_registration`, restricted control projections (`obligations[*].status == "restricted"`, empty `fact_refs`), and signing/history records, which must remain untouched.

### 5. Unperformed checks and evidence basis

- No tests run, no product run, no clinical data; test names/line numbers for the mixed and counterexample suites come from a delegated read of `tests/v2/services/test_protocol_control_execution.py` and are not independently re-verified. Test assertions involving `_same_unit_two_requirement_review`, `_temporal_restriction_indexes`, and `_coexisting_statement_proofs` internals are agent-reported; I verified lines 504-574, 319-378 and 576-651 directly.
- I did not inspect the raw answer, original protocol, DB, env, or private material; no browsing or recursion.
- The medical claim in the frozen observation (daily frequency / suggested time / rest before exam are general instructions whose target visit is genuinely unproved) is treated as owner evidence, not clinical gold. I did not decide that they apply to every visit, nor that they are ambiguous.

### 6. Objections / decision points

1. If opening this gate is not in the current frozen window, the safe provisional state is to keep the step-23 stop and the honest `SOURCE_TARGET_REVIEW_UNRESOLVED` diagnosis — the source and the failed run remain intact — rather than widening any coverage verdict.
2. Before any change, confirm which disposition kind the affected unit actually carries in the wire (the argument above assumes `REQUIRED_PROCEDURE` with a real linked target list). If it is `OTHER_CONTROL_CANDIDATE` instead, the single-statement block is the *only* stopper and the fix is smaller (the line 601 clause alone).
3. Either fix must be paired with ledger-consumer checks (checkpoint rebuild, projections, signing) listed in §4; a source-only change without those checks would produce revalidation drift rather than a usable non-executable record.
