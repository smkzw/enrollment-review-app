I'll start by reading the initial read set files.

Read-only analysis task. Let me locate the four symbols.

I have enough evidence. Composing the report.

# Execution Output: enrollment-w1-selection-review-20260922 - worker_01

## Boundary And Context Check

- **Read set honored.** Read `context/enrollment-w1-selection-review-20260922_execution_context.md` and `plans/codex_execution_enrollment-w1-selection-review-20260922.md` first, then extended only inside this worktree.
- **Extra context obtained (why):** the two initial files name four modules but define neither W1's accepted scope nor the Q1 checklist. I read the authoritative W1 definition and acceptance text: `.trellis/tasks/09-11-e2e-eligibility-review/delivery_20260922/{03_PLAN,04_WORK_PACKAGES,09_REVIEW_EVIDENCE,01_REVIEW,02_EXECUTION_RULES,06_MATERIALS}.md`. Without them the deliverable ("最小完整修订 / Q1集中验证清单") cannot be tied to the real acceptance contract.
- **No writes.** `git status --short app/ tests/` shows only pre-existing modifications from the prior W0 session (`app/config.py`, `app/llm/page_review_harness.py`, `frontend/src/*`, `tests/v2/llm/test_page_review_local_route.py`). All four W1 target modules are clean: `git status --short` lists none of `app/services/{eligibility_review_projection,qualified_binding_selection,frozen_review_calculation,review_context_assembly}.py`. I created no files, no branches, no commits.
- **No clinical originals, no keys.** No protocol DOCX, no subject documents, no `data_v2/*.sqlite3`, no `.env`, no credential value was read. All executable checks used the pytest `tmp_path`-backed V2 data root (`tests/v2/conftest.py:19-30` monkeypatches `ENROLLMENT_V2_DATA_DIR`).
- **Not done (out of role):** no implementation, no acceptance, no peer review, no conference, no model/service start.
- **Baseline is e7f34d05** with 40 dirty paths, all pre-existing; none inside the W1 edit surface.

## Work Performed

### 1. Consumer map (verified by grep, not assumed)

| Symbol | Definition | Real consumers |
|---|---|---|
| `qualified_binding_selection` | `app/services/qualified_binding_selection.py` | `frozen_review_publication.py:17,107`; `frozen_review_calculation.py:23-26,125`; `eligibility_review_projection.py:879-881,951`; `repeat_condition_selection.py:88,184,303`; `repeat_result_resolution.py:14,30`; `repeat_trigger_calculation.py:9`; `repeat_atom_calculation.py:14`; `frequency_atom_calculation.py:7`; `qualified_{proposition,frequency,observation_relation}*.py`; `predicate_proposition_calculation.py:57` |
| `frozen_review_calculation` | `app/services/frozen_review_calculation.py` | `frozen_review_publication.py:16,111` (the only `calculate_frozen_review` caller); `review_preparation_command.py:8`; `qualified_review_command.py:17`; `binding_evaluation.py:31` |
| `eligibility_review_projection` | `app/services/eligibility_review_projection.py` | `app/api/v2/eligibility_review.py`; `app/api/v2/app.py:100,262`; `control_judgment_gaps.py:7`; `frozen_review_calculation.py:18-21`; `qualified_observation_relation.py:60`; `repeat_trigger_calculation.py:10`; `repeat_atom_calculation.py:36`; `frequency_atom_calculation.py:32` |
| `review_context_assembly` | `app/services/review_context_assembly.py:23` `assemble_review_context` | `review_preparation_command.py:9,50` → `POST /api/v2/.../review-preparations` (`app/api/v2/qualified_review.py:228-247`) |

`review_context_assembly.assemble_review_context` is **not defective for W1**: it already uses `project_published_clause_pack(session, protocol.rule_set)` (`:40`), i.e. official + cross-chapter from one published revision, and already reuses `PatientProfileService._published_*` + `_validate_referential_closure` (`:42-53`). The work draft (`EligibilityReviewProjectionService.project`) uses a **different** assembler — `project_clause_pack(rule_set)` without `control_publication` (`eligibility_review_projection.py:700`). That single line is the root of C07.

### 2. Confirmed defects (evidence-first)

**D1 — Parallel, degraded selector in the work draft (P1, W1 item 1/6).**
`eligibility_review_projection.py:865-970` `_load_binding_predicate_fact_ids` is a second selector. It calls `pair_direct_selection_rejection_reasons(record)` with **default** `written_content_verified=False, source_validity_calculable=False` (`:951` vs defaults at `qualified_binding_selection.py:62-65`). Since only `{"semantic_correspondence_unverified","temporal_applicability_unverified"}` are ever resolved under those defaults (`:83`), any pair carrying `pending:professional_judgment_applicability_unverified` or `pending:source_validity_requires_policy_evaluation` is **rejected in the work draft** while the formal path resolves and accepts it (`:526-529` passes the real `content_verified` / `source_validity_calculable`). Same input, different selection ⇒ violates the W1 exit criterion.
It also never calls `_select_facts_for_identity` (`:224`), `_select_with_ordering` (`:287`), `_semantic_ordering` (`:347`), nor any of the proposition/frequency/observation consumers; and it appends **any** fact_attribute that passed the coarse filter (`:956-957`) into an operand list, so `date_range`/`record_time`/`assertion_basis` ids can enter value arithmetic.

**D2 — `None` collapse re-opens the legacy category path (P1, expert R2-02, W1 item 4).**
`:958-960` `if not any(result.values()): return None`; `:763-767` clears empty lists to `None`; `_filter_for_component` returns `None` for a `None` input (`:974-976`). `_evaluate_atomic` then takes `fact_ids is None` and, **only when the predicate has no `observation_policy`**, falls through to type-alias matching (`app/domain/expression.py:524-535`). The evaluator documents this explicitly: *"None retains the legacy category path; an empty selection for an atom does not use it"* (`expression.py:648-652`). So "all pairs rejected" and "no policy" both end as category-guess evaluation. `tests/v2/test_predicate_semantic_binding_boundary.py` marks this as known: two `xfail` "category aliases lack verified predicate-specific semantic binding".

**D3 — Discovery conflates "incomplete", "malformed", and "absent" (P1, W1 item 5).**
`:899-904` filters `state = 'completed'` in SQL and orders by `created_at DESC` **before** any scope filter; `:911-912` `except Exception: continue` swallows malformed payloads. Consequences: (a) a newer in-scope in-flight job is invisible, so an older completed job is silently presented as current; (b) a corrupt payload is reported as "no task"; (c) the 9-field authority scope is only applied after fetch. Also `:938` constructs a fresh `ArtifactStore(resolve_data_paths())` inside the read model, bypassing `app.state.artifact_store` — the read path is coupled to process env. And `:937` omits `require_candidate_route_receipts=True`, which the formal path sets (`:416`) and which `build_binding_evaluation_manifest` also sets (`binding_evaluation.py:169-172`) — weaker proof than formal for the same records.

**D4 — Work draft silently rewrites stale fact ids (P1, W1 item 5).**
`:756-762` drops frozen selection fact ids that are not in the live `context.accepted_fact_ids`. A stale selection is thus rendered as a smaller valid selection instead of an explicit stale state. Note `expression.py:661-668` already rejects out-of-scope ids when a mapping is supplied, so the silent drop is masking a condition the evaluator would otherwise surface.

**D5 — Work-draft evaluator call omits 6 parity parameters (P1, W1 item 6).**
`calculate_component_review` is documented as *"One component calculation shared by projections and formal review assembly"* (`component_review.py:1-5`). The two call sites diverge:

| parameter | frozen (`frozen_review_calculation.py:352-373`) | work draft (`eligibility_review_projection.py:781-795`) |
|---|---|---|
| `predicate_fact_ids` | per-predicate choices | coarse loader / `None` |
| `unverified_predicate_ids` | computed (`:323-334`) | **absent** |
| `missing_judgment_predicate_ids` | `missing_judgment_predicates(...)` (`:360-366`) | **absent** |
| `judgment_gap_by_requirement` | `judgment_gaps` (`:367`) | **absent** (work draft instead passes `source_gaps=frozenset(judgment_gaps.values())`, `:792`) |
| `verified_judgment_requirement_ids` | `frozenset(verified_for_clause)` (`:368`, computed `:336-350`) | **absent** |
| `proposition_evaluations` / `repeat_evaluations` / `frequency_evaluations` | present (`:356-358`) | **absent** |

`source_gaps` is a plain union (`assessment.py:290`), whereas `requirement_gap_overrides` + `verified_judgment_requirement_ids` interact per requirement and can **suppress** a `PROFESSIONAL_JUDGMENT`/`OBSERVATION_UNVERIFIED` expectation (`assessment.py:304-320`). Result: a requirement whose written judgment was verified appears resolved in the frozen report and still "研究者专业判断缺失" in the work draft. This is the user-visible half of C01.

**D6 — Cross-chapter requirements absent from the work draft (P2→P1, C07, W1 item 7).** `:700` omits `control_publication`; there is no control branch at all in `project()`. `calculate_frozen_review` has the full control path (`:56-91,198-216,303-305`). Additionally `EligibilityReviewResponse.clauses` requires `min_length=1` (`app/api/v2/eligibility_review.py:93`), so a project whose published pack has only cross-chapter requirements cannot be read at all — W1 item 7 says that case must be an explicit not-ready state, and "总要求为零不能算审核成功".

**D7 — Unreachable code (W1 item 6 "删除return后旧逻辑").** AST-confirmed: `eligibility_review_projection.py:961-967` is unreachable after the `return` at `:960`. It is a second, weaker selection loop (`structurally_valid and dual_agreement` only) — the strongest evidence that the function was superseded mid-edit and never finished.

### 3. Function-level minimal change plan

**P0 — Contract: `app/domain/contracts/qualified_binding_selection.py`**
- Add `QUALIFIED_BINDING_SELECTION_WORK_DRAFT_VERSION = "qualified-binding-selection/v6"`; extend the `version` literal (`:175`) with `v6`.
- Add `selection_mode: Literal["authorized","work_draft"] = "authorized"`, popped by the existing wrapper serializer (`:209-221`) when `version not in {...v5, v6}` so stored v1–v5 payload hashes stay byte-identical.
- Make `authorization_id` (`:181`), `authorizing_service` (`:182`), `approved_evaluation_evidence_sha256` (`:187`) optional; extend `validate_material` (`:223-286`) with a two-branch invariant: `authorized` ⇒ all three non-null (current behavior); `work_draft` ⇒ all three `None` **and** `judgment_content`/`proposition_evidence`/`observation_relation`/`frequency_evidence` all `None` **and** the four derived evidence lists empty.
- Extend the literal sets at `:218`, `:264`, `:272` to include `v6` where the intent is "current version".
- `accepted` / `authorized_clinical_adoption` / `clinically_qualified` stay `Literal[False]` (`:204-206`) — **no new field may weaken this**.
- One material type, no parallel truth table (W1 item 3).

**P1 — Kernel extraction: `app/services/qualified_binding_selection.py`**
- Add module-private frozen dataclass `QualifiedSelectionEvidence` carrying the five adoption-derived inputs: `binding_method`, `approved_evaluation_evidence_sha256`, `judgment_content: tuple[content, frozenset[supported]] | None`, `proposition`, `observation`, `frequency` (the verified-evidence dicts, not the selections).
- Add `_assemble_selection(*, session, artifact_store, verified, evidence, review_context_id, review_context_sha256, selection_mode) -> QualifiedBindingSelectionMaterial` containing lines **433-847 verbatim**, with only these seams rewired: `:419-420` (manifest/method), `:421-432` (content/supported), `:444-481` (proposition relations), `:482-511` (frequency/observation), `:814-822` + `:829-846` (material identity/echoes). The `verify_*` calls move **out**; the `select_*` halves (`select_qualified_relations` `:476-481`, `select_qualified_frequency_sources`, `select_qualified_observation_relations`) stay **in** — they are the selection semantics W1 must share.
- `build_receipt_verified_qualified_binding_selections` keeps its exact public signature; body becomes verify (`:414-417`, unchanged, `require_candidate_route_receipts=True`) → `_validate_authorization` (`:418`, unchanged) → build the four verified evidences → `_assemble_selection(..., selection_mode="authorized")` → seal. **No behavior change for the formal path.**
- New public `build_work_draft_qualified_binding_selections(session, artifact_store, *, qualification_job_id) -> ReceiptVerifiedQualifiedBindingSelections`: same verify call, `QualifiedSelectionEvidence()` all-`None`, `selection_mode="work_draft"`, seal. **No gate lookup, no authorization object, no write, no `authorization_id` fabrication** (W1 item 2: 禁止伪seal或批准对象).
- Add `ReceiptVerifiedQualifiedBindingSelections.selection_mode` property and `assert_authorized_selection(selections)` used only by formal-only guards. Keep `require_unchanged()` untouched (`:388-390`).
- Factor the binding body of `assert_qualified_selections_match_review_context` (`:859-925`) into `_assert_selections_match(*, authority, review_episode, facts, clauses, control_publication, rule_set, selections, context_id, context_sha256)` and add `assert_work_draft_selections_match_live_state(...)` over the same body. One binding implementation, two callers.
- Delete the stale question-comment at `:655-657`.

**P2 — Cross-chapter extraction: `app/services/frozen_review_calculation.py`**
- Change `_calculate_controls(frozen, ...)` (`:56`) to keyword-only explicit inputs: `publication, facts, authority, review_episode, control_input, control_selections, conflict_groups, expectation_templates, judgment_search_results, unverified_atom_reasons, proposition_relations, proposition_pair_gaps, repeat_evaluations, frequency_evaluations`. Body of `:59-91` unchanged otherwise. Replaces the positional call at `:303-305` (also removes the `unverified_atom_reasons` positional hazard).
- Change `missing_control_judgments(frozen, selections)` (`control_judgment_gaps.py:10`) to the same explicit keyword inputs; update its two callers (`frozen_review_calculation.py:80`, and the new work-draft caller). It already reads only `frozen.clause_pack.control_publication`, `.review_episode`, `.expectation_templates`, `.judgment_search_results` (`:11-27`).
- `calculate_frozen_review`: add the authorized-only guard right after `_resolve_selection_inputs` (`:193`):
  `if qualified_binding_selections is not None and any(item.selection_mode != "authorized" for item in _qualification_inputs(...)): raise ValueError(...)`. This is the enforcement point for "正式发布仍须授权": a work-draft selection can never enter the publish-path calculation. (`publish_frozen_review` already rebuilds selections itself at `:107-111` and never accepts caller calculations, so publication is structurally safe — the guard closes the `calculate_frozen_review` loophole only.)
- `_resolve_selection_inputs` (`:94-135`) unchanged; it is the authorized path and its `assert_qualified_selections_match_review_context` calls (`:124-127`) stay.

**P3 — Live work draft: `app/services/eligibility_review_projection.py`**
- `EligibilityReviewProjectionService.project(self, session, review_episode_id, *, artifact_store=None)`. Update the single route call (`app/api/v2/eligibility_review.py:135-137`) to pass `request.app.state.artifact_store`, and the wiring default (`app/api/v2/app.py:262`) can stay. When `artifact_store is None`, skip discovery and emit an explicit preparation state — never a silent "no requirement".
- `:700` → `project_published_clause_pack(session, rule_set)` (fixes D6 at the source; same one-published-revision contract as `review_context_assembly.py:40`).
- Replace `:754-767` with `_load_work_draft_selections(session, artifact_store, *, authority, rule_set, facts, control_publication)`:
  1. **Scope filter pushed into SQL** using the idiom already in production at `prepared_review_progress.py:31-39`: `func.json_extract(JobRecord.payload_json, "$.frozen_input.authority.<f>")` for predicate and `"$.frozen_input.evidence_input.authority.<f>"` for control, over all 9 `FactAuthority` fields (`:888-892`), plus `job_type in ('predicate_binding_candidates'|'control_binding_candidates')`. **No `state='completed'` filter, no SQL `ORDER BY`**; sort in Python by `(created_at, job_id)` descending *after* the scope filter (W1 item 5 "先scope过滤再排序").
  2. Newest in-scope row not completed → `state="pending"` **and** fall back to the newest completed in-scope row marked `stale=True, stale_reasons=("newer_task_incomplete",)`. Malformed payload → raise a typed `WORK_DRAFT_TASK_INVALID` error (no fallback to an older row).
  3. Call `build_work_draft_qualified_binding_selections(...)`, then the live binding check from P1; additionally call `require_prepared_candidate_scope` (`review_candidate_scope.py:26-50`) when the payload carries `review_context_id` — it already proves authority + live facts + rule-set digest + components + control publication.
  4. Live facts/components differ from the frozen job → `stale=True` with the concrete reason; do not drop ids (fixes D4).
  5. Controls: run only when `control_publication is not None and catalog.controls`; a published control exists with no in-scope control selection → `state="pending_control"`, explicit.
- **Pass the parity parameters (fixes D5)** using the same expressions as `frozen_review_calculation.py:323-373`: `unverified_predicate_ids` from work-draft outcomes where `status=="unresolved"`, `missing_judgment_predicate_ids=missing_judgment_predicates(...)`, `judgment_gap_by_requirement=judgment_gaps`, `verified_judgment_requirement_ids`, and `proposition_evaluations` via `calculate_predicate_propositions(item, context)` (`:315-316`) with repeat/frequency keys popped exactly as `:317-322`.
- **Never pass `None`** for a component whose predicates are covered by the current frozen scope: build `{pid: []}` for unresolved predicates. `expression.py:656-660` requires complete per-component coverage, and `:670-675` requires `unverified_predicate_ids` to be explicit empty selections. Then remove the `_component_candidate_types` alias feed (`:674-688`, `:779-780`) for covered components so `expression.py:529-535` cannot be reached for them.
- Add `controls: tuple[EligibilityControlProjection, ...]` to `EligibilityReviewProjection`, produced by the P2 shared `_calculate_controls(...)` + `project_control_review_outcomes(...)` (`app/projections/control_review_outcome.py:10`), with field names/semantics copied from `ReviewHistoryControlDTO` (`app/api/v2/review_history.py:243-261`). Controls must **not** be pushed into `clauses` (W1 item 7).
- Add `selection_state` / `selection_stale` / `selection_job_id` to `EligibilityClauseProjection` (additive).
- `app/api/v2/eligibility_review.py:93`: relax `clauses` to `default_factory=list` and add the zero-requirement not-ready state (W1 item 7).

**P4 — `app/services/review_context_assembly.py`: no change.** Report only: it is the correct assembler for the frozen path; the work draft must reach parity by using `project_published_clause_pack`, not by calling `assemble_review_context` on every read (that would persist a snapshot per read and defeat "工作稿无副作用").

### 4. Dead code to delete
1. `eligibility_review_projection.py:961-970` — unreachable after `:960` (AST-confirmed). Delete.
2. `eligibility_review_projection.py:865-970` `_load_binding_predicate_fact_ids` — after P3 it has **zero** callers (grep: only `:754`). Delete the whole parallel loader including the `ArtifactStore(resolve_data_paths())` bypass at `:938` and the `except Exception: continue` at `:911-912`.
3. `eligibility_review_projection.py:478-480` `_summary_gaps` — app-code-dead; only `tests/v2/services/test_judgment_summary_gap_states.py:11,34,61` consumes it. Delete together with those three call sites, or keep with a recorded reason. **Codex decision** (it is test-consumed).
4. `qualified_binding_selection.py:655-657` — stale question comment. Delete.
5. `frozen_review_calculation.py:56-58` positional defaults of `_calculate_controls` — eliminated by the P2 keyword-only signature (removes the `:303-305` positional coupling).
6. Not dead, do not delete: `_primary_gap` `:258`, `_decision_for_wire` `:265` (identity function; test-consumed at `tests/v2/test_component_decision_blocking_gaps.py:10-12`), `_used_fact_ids` `:517`, `_action_directive_fields` `:527`.

### 5. Q1 concentrated verification checklist (W1 item 29, mapped to real service paths)

Harness rule: every case must enter through `EligibilityReviewProjectionService().project(...)` / `calculate_frozen_review(...)` / `publish_frozen_review(...)` with a seeded DB + completed job receipts — **no copied private-helper probes** (W1: "用现有服务路径而非抄函数独立probe").

| # | W1 checklist item | Service-path case | Expected observable |
|---|---|---|---|
| 1 | 日期单独通过 | predicate with `time_constraint`; only a qualified `date_range` pair | identity `unresolved`, reason contains `no_usable_qualified_pair`; never `usable` |
| 2 | 值无合格日期 | qualified `value` + non-qualified `date_range` | `event_date_not_qualified_for_selected_value`; map key present with `[]` |
| 3 | single 多值（含两条同值） | `observation_policy.mode="single"`, two usable `value` pairs of the same value | `multiple_usable_pairs_without_selection_policy`; must not silently pick one |
| 4 | 正常值+日期 | qualified `value` + qualified `date_range` | `usable`; `used_fact_ids==[value_fact]`; `observation_ordering` present when `policy.selection` is set |
| 5 | 全部拒绝 | every candidate pair rejected | identity `unresolved` + concrete rejection reasons; the component's `predicate_fact_ids[pid] == []`; evaluator returns UNKNOWN(`observation_unverified`), **no category fallback** |
| 6 | 未完成/陈旧 | newer in-scope job in `queued/running`; and (separately) live facts changed vs frozen job | `state="pending"` / `stale=True` with reasons; the older completed job is never presented as current; no silent id dropping |
| 7 | 坏载荷不借旧任务 | newest in-scope payload invalid JSON/schema | typed `WORK_DRAFT_TASK_INVALID`; must NOT fall back to the older completed job |
| 8 | 无policy反例 | `observation_policy is None` + multiple usable values; and `mode="unresolved"` | `multiple_usable_pairs_without_selection_policy` / `observation_selection_unverified`; `fact_ids is None` must never reach `expression.py:529-535` for a covered predicate |
| 9 | 频次 / 复查 / 例外 / 命题 / 跨章 正反例 | one positive + one negative each for `frequency_statements`, `observation_relations`, exception expressions, `semantic_proposition` predicates, and `control_publication` controls | frequency/observation positive ⇒ usable; negative ⇒ explicit unresolved. Proposition in **work draft** ⇒ `semantic_evidence_unverified` (never FALSE), matching `predicate_proposition_calculation.py:89-95`. Controls present ⇒ `controls` non-empty with per-obligation `status`; controls absent ⇒ explicit "no cross-chapter requirement" evidence, not zero |
| 10 | 工作稿/正式语义一致（新） | same frozen input + same jobs, both entry points | identical `predicate_fact_ids_by_component`, `usable_pair_ids`, control obligation statuses; differences limited to `selection_mode` and the four adoption-bound layers |
| 11 | 无批准副作用（新） | call the work-draft path, then compare row counts of `job_records / job_steps / gate_results / idempotency / review_context / review_run / final_assessment` | **zero** delta; no `binding-adoption-authorization` gate created |
| 12 | 工作稿不得发布（新） | pass a `work_draft` selection into `calculate_frozen_review`; and into `publish_frozen_review` | both raise; `FrozenReviewCalculation.accepted is False` always |
| 13 | 零要求不得成功（新） | published pack with no official clauses and no controls | typed not-ready state / HTTP error; must not render an empty successful report |

Commands (per `06_MATERIALS.md:36-46`, unchanged contract):
```
uv run pytest tests/v2/services/test_eligibility_review_projection.py tests/v2/test_predicate_semantic_binding_boundary.py tests/v2/protocols/test_control_candidate_evaluation_scope.py -q
cd frontend && npm run build
```
`timeout(1)` is unavailable on this macOS shell; use `uv run` directly or the Bash tool's own timeout.

## Artifacts And Evidence

No artifacts were produced; this is a read-only analysis item. Evidence is source-anchored:

| Claim | Evidence |
|---|---|
| Work draft uses a second, degraded selector | `eligibility_review_projection.py:754`, `:865-970`, `:951` vs `qualified_binding_selection.py:62-65`, `:83`, `:526-529` |
| `None` re-opens the legacy alias path | `eligibility_review_projection.py:958-960,763-767,974-976`; `app/domain/expression.py:524-535,648-652` |
| Discovery conflates incomplete/malformed/absent | `eligibility_review_projection.py:899-912,937-938`; contrast `:416`; `binding_evaluation.py:169-172` |
| Silent stale-fact rewriting | `eligibility_review_projection.py:756-762`; `expression.py:661-668` |
| 6 missing parity parameters | `component_review.py:26-40` vs `frozen_review_calculation.py:352-373` vs `eligibility_review_projection.py:781-795` |
| `source_gaps` cannot be suppressed per requirement | `assessment.py:290,304-320` |
| Cross-chapter absent from work draft; `min_length=1` blocks the zero-official case | `eligibility_review_projection.py:700`; `frozen_review_calculation.py:56-91`; `app/api/v2/eligibility_review.py:93` |
| Frozen assembler is already correct | `review_context_assembly.py:40-53`; `published_clause_pack.py:10-14` |
| Unreachable block | AST scan (see Commands) |
| Approved evaluation evidence is structurally unavailable without a manifest | `qualified_{judgment_content,proposition_evidence,observation_relation,frequency_evidence}.py` all require `binding_method`; `review_method_evidence.py:13-29,32-38` |
| Cross-chapter display structure to reuse | `app/api/v2/review_history.py:243-261` |
| Existing SQL scope-filter idiom | `app/services/prepared_review_progress.py:31-39` |
| Existing frozen-context binding check to reuse | `app/services/review_candidate_scope.py:26-50` |

## Commands And Observations

1. `git log --oneline -8` / `git status --short` — HEAD `e7f34d05`; 40 dirty paths, all pre-existing (W0 frontend/config/tests + task/docs). None of the four W1 modules is dirty ⇒ W1 unimplemented.
2. `python3 - <<AST scan>>` over the four modules — exactly one unreachable region: `eligibility_review_projection.py` `_load_binding_predicate_fact_ids` lines **961-967** after the `return` at `:960`. No unreachable code in the other three.
3. `python3 - <<module-level reference scan>>` — `_load_binding_predicate_fact_ids` has **0** references outside its own module; `_summary_gaps` has **0** app-code consumers (tests only).
4. `uv run pytest tests/v2/services/test_eligibility_review_projection.py tests/v2/test_predicate_semantic_binding_boundary.py tests/v2/protocols/test_control_candidate_evaluation_scope.py -q` → **14 failed, 20 passed, 2 xfailed, 5 warnings, 10.52s**. Matches `09_REVIEW_EVIDENCE.md:16` exactly (reproducible).
5. `uv run pytest "tests/v2/services/test_eligibility_review_projection.py::test_projection_without_published_fact_is_unknown_not_negative" -q` → failure raised at `component_review.py:49` → `assessment.py:277` `AssessmentGateError("审核节点或资料要求的到期节点不完整")`, i.e. **before** any binding code runs. **Classification: the 12 projection failures are fixture staleness** (`_seed_chain` does not seed `requirement_workflow_stage_ids`), not W1 product defects. Q1 must not "fix" them by weakening assertions.
6. `uv run pytest "tests/v2/test_predicate_semantic_binding_boundary.py::test_isolated_selection_keeps_one_fact_for_two_bounds_and_detects_conflict" -q` → `assert 'source_conflict' in ['observation_selection_unverified']`. **Classification: unresolved test-vs-design boundary** — `expression.py:600-604` only emits `source_conflict` when a `conflict_group_id` is present, and `_phase3_conflict_groups` builds those only from *published* conflict groups. Needs an explicit Codex decision (either seed the conflict group in the test, or make two explicitly-selected differing values a `source_conflict`).
7. `grep -rn` consumer sweeps for the four symbols, `selections.` attribute usage in `repeat_*`/`frequency_*`/`control_repeat_trigger_calculation`, and job-type discovery — all results in the tables above. No model call, no network, no service start, no DB open outside pytest tmp paths.

## Blockers Or Missing Environment

- **Not a blocker, an informational gap:** the execution context's Source Of Truth is still `TODO` (`..._execution_context.md:22`) and the Codex acceptance section is `TODO` (`plans/codex_execution_....md:13`). My plan is anchored to the W1 text in `04_WORK_PACKAGES.md:18-30` because that is the only authored W1 contract available.
- **No environment blocker.** `uv run pytest` works; the single macOS quirk is that `timeout(1)` is absent (use the Bash tool timeout).
- **Two items need a Codex ruling before implementation** (see Next Step). I did not decide them unilaterally because they change contract scope, not just code.

## Rerun Requests Or Next Step

**Rerun request for this worker:** none required; the pass is complete and self-contained. If Codex wants the type/attribute-provenance layer (W1 item 3: "selected pair+fact+attribute、日期来源") specified to field level, dispatch a bounded follow-up with the decision on question 2 below — the answer determines whether `QualifiedBindingRejectedPair` needs `fact_attribute` or whether the UI joins on `pair_id`.

**Two decisions block implementation (each changes contract scope):**

**Q1 — Can the work draft read an existing approved evaluation manifest when one exists for the current scope?**
Fact: all four evidence verifiers structurally require `binding_method`, which only comes from an approved evaluation manifest (`review_method_evidence.py:13-38`). Without it the work draft cannot produce proposition/frequency/observation/written-content relations at all, so "work draft ≡ formal except authorization" holds for the deterministic core but **not** for those four layers. Reading the manifest is read-only and creates no gate, so it does not violate "无批准副作用"; but it couples the live read route to `ENROLLMENT_REVIEW_METHOD_APPROVAL_GATE_ID`.
- Option A (recommended, smaller): work draft never touches approval artifacts; the four layers render as explicit unresolved, never as absent/negative. Matches "无资格不作阴性".
- Option B: read the method-approval gate read-only when configured, maximizing parity, with a documented config dependency.
Either way the four layers must never silently become "no evidence".

**Q2 — Which calculation entry does the work draft reuse?**
- Option A (recommended, minimal): share the **selection kernel** (P1) and the extracted **cross-chapter calculation** (P2), and keep the projection's own display loop, which adds reason/label/action/locator fields the frozen report does not have. Requires the live-binding adapter (P1) because the read model has no `ReviewContextSnapshotV2`.
- Option B: make `GET .../eligibility-review` accept an optional `context_id` and, when a frozen context exists for the current authority, call `calculate_frozen_review` with work-draft sealed selections. Gives literal parity, but changes the route contract, needs a new `ReviewContextV2Repository` lookup by authority (today only `get(context_id)`, `review_context_repository.py:27`), and creates a "frozen vs live" dual reading path.
Recommendation: ship Option A in W1 and treat Option B as an explicit W4 read-model upgrade, so W1 stays one bounded change.

**Falsifiable check for Codex acceptance of my plan:** after P1, for a fixed frozen input and job set, `build_work_draft_qualified_binding_selections(...).material.predicate_fact_ids_by_component` must equal `build_receipt_verified_qualified_binding_selections(..., authorized).material.predicate_fact_ids_by_component` for every component whose predicates carry no proposition/repeat/frequency/adoption-bound predicate — and must differ only inside those bound predicates. If it differs elsewhere, P1's extraction is wrong, not the test.

Codex remains the authority for source correctness, clinical/regulatory interpretation, production writes, and user delivery. I claim no acceptance.
