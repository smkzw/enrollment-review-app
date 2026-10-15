I'll start by reading the initial read set.

Now I have the full picture. Let me write the service module.

Let me refine a couple of robustness details in the service.

Trellis SessionStart ✓

Both files are implemented, compiled, and schema-verified. Report follows.

# Execution Output: t5-frozen-review-history-20260913 - worker_01

## Boundary And Context Check

- Role: bounded first-line executor (`codebuddy` / `codebuddy-cli` / `deepseek-v4.1-flash`), admitted under the current Beijing off-peak route. No recursive agents, no conference, no peer review, no user delivery, no acceptance claim.
- Workspace: runner CWD `.` = worktree `phase5-clinical-facts-profile`. All reads/writes stayed inside it. No production path, no `.env`, no personal harness config, no raw clinical artifact, no DB file read.
- Writes performed — exactly two, both authorized and both **new** files:
  - `app/services/review_history_service.py` (new, 486 lines)
  - `app/api/v2/review_history.py` (new, 386 lines)
  - Side effect of the explicitly allowed `py_compile` check: gitignored bytecode caches `app/services/__pycache__/review_history_service.cpython-312.pyc` and `app/api/v2/__pycache__/review_history.cpython-312.pyc`. No source file was modified.
- Writes NOT performed: no tests, no test files, no migrations, no repository/contract/model edits, no `app.py` registration, no frontend, no docs, no config, no database.
- Operations NOT run: no pytest, no DB open/create/query, no `create_app`, no `uvicorn`, no model call, no git reset/checkout, no dependency install, no browser.
- Dirty-worktree preservation: total dirty paths `1622` = pre-existing `1620` + my 2 untracked files; `git status --porcelain` shows **no** tracked file modified by this pass.
- Read set: initial read set (execution context + Codex plan), then read-only inspection of `app/domain/contracts/review.py`, `review_context_v2.py`, `review_evidence_scope.py`, `clause_pack.py`, `common.py`, `facts.py` (FactAuthority), `enums.py`, `app/storage/repositories.py` (`AppendRepository`, `REVIEW_RUN_CONFIG`, `FINAL_ASSESSMENT_CONFIG`, `ActionRequestRepository`, `EpisodeRepository`, `get_rule_set`, scope checks), `review_context_repository.py`, `review_reference_validation.py`, `models.py` (review/assessment/action/context rows), `fact_authority.py`, `app/api/v2/eligibility_review.py`, `patient_profiles.py`, `errors.py`, `app.py` (routes/state, read-only), `app/services/evidence_app_errors.py`, `eligibility_review_projection.py`, `frozen_review_calculation.py`, `component_review.py`, `review_context_assembly.py`, `patient_profile_service.py` (pattern), `.trellis/spec/backend/{index,directory-structure,quality-guidelines}.md`, `tests/v2/test_architecture_boundaries.py`, plus prior sibling evidence `runs/execution/t5-review-v2-storage-20260913/worker_01.md` and `docs/PROJECT_CONTEXT.md` (recent entries).
- Source-authority note (evidence): the execution context's "Source Of Truth" block is still `TODO`; I derived all authority from the repository's frozen contracts/repositories and `.trellis/spec` rather than from any newly added packet source. Flagged for Codex rather than silently assumed.

## Work Performed

### Service `app/services/review_history_service.py` (read-only, `session` passed in)

Public API exactly as contracted: `list_runs(session, subject_id, review_episode_id)` (`:409`) and `get_run(session, subject_id, review_episode_id, review_run_id)` (`:445`).

- **Stored `review/v2` only.** Runs decoded through `AppendRepository(REVIEW_RUN_CONFIG)` (payload hash + column mirrors, `:432`); context through `ReviewContextV2Repository` (`:207`); assessments through `AppendRepository(FINAL_ASSESSMENT_CONFIG)` (`:300`); actions through `ActionRequestRepository.get` (`:357`, includes transition-history/mirror verification). No raw payload parsing of my own.
- **Frozen binding validation** (`_load_frozen_context :207`): `context.review_run_id == run.review_run_id`; `authority.episode_revision / protocol_version_id / rule_set_revision / evidence_snapshot_v2_id / complete_processing_revision_id` each equal to the run's frozen fields; frozen `review_episode.revision == run.episode_revision`; identity (`project_id`/`subject_id`/`review_episode_id`) checked against the path and the episode row. Current mutable episode fields (stage, active pointers, rule set revision) are **never** used to validate or reinterpret a frozen run, so later uploads/corrections cannot rewrite or block history.
- **Expected component identities from the pinned revision** (`_pinned_clause_identities :247`): loads `RuleSet` by `(frozen authority.rule_set_id, run.rule_set_revision)`, rejects identity/protocol mismatch, requires `canonical_hash(rule_set.model_dump(mode="json")) == context.rule_set_sha256`, then `project_clause_pack(rule_set)` (pure function, no DB/model/service) and requires `pack.clause_pack_sha256 == context.clause_pack_sha256`. Identities come from that verified pack; no active project pointer is consulted and no expression is evaluated.
- **`completed` vs `in_progress`** (`_run_status :174`): status is derived **only** from persisted `started_at`/`completed_at`. No `utc_now()`, no browser time. A run without `completed_at` is never presented as a completed report.
- **Explicit completeness failure**: a completed run missing any expected component assessment raises `ReviewHistoryIncompleteError` (500, `REVIEW_HISTORY_INCOMPLETE`, `context = {review_run_id, missing_rule_component_ids}`) instead of emitting a “complete but empty” report (`:471`). An in-progress run may return partial stored results but carries `status="in_progress"` plus `missing_rule_component_ids`.
- **Legacy is never recast**: `list_runs` returns only `review/v2` rows (legacy rows skipped, documented at `:409`); `get_run` on a legacy identity raises `ReviewHistoryUnsupportedError` (409, `REVIEW_HISTORY_UNSUPPORTED`, Chinese title/detail/recovery) via `_require_v2_run :201`.
- **Per-row closure checks**: each stored assessment must match run/episode/subject/project/protocol/rule-set/rule-set-revision and the run's exact 3-slot evidence lineage (`_evidence_lineage :178`), must be inside the pinned clause pack, and must be unique per component; each action must additionally reference a stored assessment of the same run with the same `rule_component_id`. Unknown/duplicate/orphan records fail loudly.
- **No recalculation, no publication, no current-pointer lookup**: nothing calls `assemble_review_context`, `calculate_frozen_review`, `calculate_component_review`, `EligibilityReviewProjectionService.project`, `FactAuthorityValidator.validate`, any prepare/activation service, or any model. `evaluator_version` is reported, deliberately **not** compared to the live evaluator constant (a frozen report must stay readable after the evaluator changes).
- **Unresolved stays unresolved**: stored `decision`/`gap_types`/`blocking_level`/`state` are passed through verbatim; there is no eligibility mapping, no label invention, no confidence field, no fabricated record.

### API `app/api/v2/review_history.py` (thin)

- GET `/api/v2/subjects/{subject_id}/review-episodes/{review_episode_id}/review-runs` (`:328`) and `…/review-runs/{review_run_id}` (`:353`), both `response_model`-typed.
- Explicit `ConfigDict(extra="forbid")` Pydantic DTOs with domain enum types for closed vocabularies (`ComponentDecision`, `GapType`, `BlockingLevel`, `ActionState`, `ActionTarget`, `RuleKind`, `DeterminationMode`, `ReviewStage`), hex-pattern checks on the three frozen hashes, and unique-component / action-reference validator on the detail response (`:186`).
- Returns IDs needed for navigation (`review_run_id`, `context_id`, `assessment_id`, `action_id`, `gate_result_id`, `used_fact_ids`, `locator_ids`, `trigger_locator_id`, transition ids, evidence snapshot + processing revision ids); stored context is exposed as identity + provenance hashes + stage/workflow + counts (facts/expectations/conflicts/judgment searches) instead of shipping the whole frozen fact set.
- Uses `request.app.state.session_factory()` + the module-local `_raise_translated` (`translate_storage_error`, unknown → re-raise for the 500 fallback) exactly like `patient_profiles.py`. No app registration, no mutations.

## Artifacts And Evidence

| Artifact | Change | Key locations |
|---|---|---|
| `app/services/review_history_service.py` | new, read-only frozen V2 history service | `list_runs:409`, `get_run:445`, `_load_frozen_context:207`, `_pinned_clause_identities:247`, `_stored_assessments:300`, `_stored_actions:357`, errors `:83` / `:97` |
| `app/api/v2/review_history.py` | new, thin GET adapter | DTOs `:54–199`, mappers `:215–321`, routes `:324` / `:349` |

Evidence for the two hard contract risks:

1. **`indeterminate` is reachable in a stored formal assessment.** `app/domain/gates/assessment.py:310 _decision_for_unknown` returns `ComponentDecision.INDETERMINATE`, so a completed run can store `indeterminate`. The eligibility-review DTO's decision `Literal` list (`app/api/v2/eligibility_review.py:43`) omits `indeterminate`; copying that list here would have produced a runtime validation failure (or a silent coercion if typed loosely). My DTOs therefore use the **domain enum type**, and I proved all values pass by constructing a stored `FinalAssessment` with `decision=indeterminate` through `_assessment_dto` → serialized `"indeterminate"` (see Commands).
2. **Thin-API boundary is enforceable.** `tests/v2/test_architecture_boundaries.py:116` fails any `app/api/v2/*.py` importing `sqlalchemy` or `app.storage`. My API module imports only FastAPI/Pydantic, domain contracts and the service; I re-ran the same AST check inline → `THIN_API_BOUNDARY_OK`.

## Commands And Observations

| Command | Observation |
|---|---|
| `.venv/bin/python -m py_compile app/services/review_history_service.py app/api/v2/review_history.py` | `FINAL_COMPILE_OK` (run after every edit; last run on final content) |
| AST scan of `app/api/v2/review_history.py` for `sqlalchemy*` / `app.storage*` imports | `THIN_API_BOUNDARY_OK` |
| `FastAPI()` + `include_router(rh.router)` + `app.openapi()` | exactly 2 paths, both `['get']`: `…/review-runs`, `…/review-runs/{review_run_id}` |
| Contract+DTO construction script (no DB, no `create_app`): built valid `ReviewEpisode`, `FactAuthority`, `ReviewContextSnapshotV2` (hash computed), `ReviewRun(review/v2)`, `FinalAssessment(decision=indeterminate)`, `ActionRequest(open)`; ran `_run_dto`, `_context_dto`, `_assessment_dto`, `_action_dto`, `ReviewHistoryRunResponse` | `status="in_progress"`; assessment decision round-trips as `indeterminate` with `blocking_level=BLOCKING`; action `state="open"`, `record_revision=1`; run/context key sets match the DTO definitions; `fact_count=0`, `judgment_search_count=0`; `missing_rule_component_ids=["cmp-2"]` |
| `map_exception()` on the new errors + `translate_storage_error()` passthrough | `409 REVIEW_HISTORY_UNSUPPORTED`; `500 REVIEW_HISTORY_INCOMPLETE` with `context={"review_run_id":…, "missing_rule_component_ids":[…]}`; `NotFoundError → AppNotFoundError` |
| `import app.api.v2.app` (import only, no app creation) | `APP_MODULE_IMPORT_OK True` — no circular import introduced, `create_app` untouched |
| Manual unused-import scan (AST) on both files | only `__future__.annotations` reported (noise); no unused imports |
| `git status --porcelain` | `?? app/api/v2/review_history.py`, `?? app/services/review_history_service.py`; total dirty 1622 = 1620 baseline + 2; **0** tracked files modified |
| Env observation | `.venv/bin/python` (CPython 3.12) executed every check successfully; `uv run` was not required for compile/import/schema checks in this session. No ruff/mypy/pyflakes binary exists in `.venv/bin`. |

Tools used: Read, Write (2 authorized file creations), Edit (2 edits inside my own new service file), Grep/Glob, Bash for the `.venv` compile/import/schema/AST/`git status` checks. No browser, web, network, MCP, or agent tool was used or needed.

## Blockers Or Missing Environment

No blocker; nothing is missing to build against. Items below are owner decisions/risks, not blockers.

1. **No formal write entry point exists yet** (restated from the contract): no `ReviewRun`/`FinalAssessment`/`ActionRequest` V2 publisher or app registration exists, so `list_runs` currently returns `[]` in practice and no end-to-end HTTP read is possible until the owner wires a writer and `include_router`.
2. **No failure marker in the frozen chain.** `ReviewRun` has only `started_at`/`completed_at`; there is no failed/attempt state (I found no formal-review job type either). I therefore mapped persisted timestamps to exactly `completed` / `in_progress` and never claim completion otherwise. If a *failed* formal review must be distinguishable in history, the freeze/write path must record it — I did not invent a state.
3. **`ActionRequest` is a mutable root.** The history view shows the stored *current* revision and full transition history, not a run-time snapshot; an action closed after the run appears closed. Per the contract (“actions through existing ActionRequestRepository”) this is intended, but confirm the UI wording does not read “closed” as “rule passed”.
4. **Referential closure of frozen fact/locator references is not re-verified at read time.** Existence is structurally guaranteed (association tables `final_assessment_facts_v2` / `final_assessment_locators` carry real FKs and are verified against the payload by `AppendRepository._decode`), but the write-time authority equality per fact (`validate_review_references`) is not re-run — deliberately, because the instruction allowed only run/context/assessment/action reads and closure validation pulls the locator/visual validation path. If Codex wants it added, it is a small, contained extension of `_stored_assessments`.
5. **`project_clause_pack` usage.** I used this pure projection (no DB, no model, no service call) because the frozen context pins `clause_pack_sha256`; the pack hash is required to match before identities are derived, alongside `rule_set_sha256`. If Codex prefers traversal of the pinned `RuleSet` tree instead, the change is local to `_pinned_clause_identities`.
6. **New app-error subclasses live in the service module** (`ReviewHistoryUnsupportedError`, `ReviewHistoryIncompleteError`) — precedent: `TargetedReviewNotReady` (`app/services/targeted_page_review_jobs.py:21`), `PageReviewUnavailable` (`app/services/page_review_runtime.py:21`). Moving them into `app/services/evidence_app_errors.py` was out of my two-file authorization; it is a copy/paste for the owner if desired.
7. **Response/status decisions to confirm**: 409 for legacy-identity reads; 500 (not 409) for frozen-record incompleteness; legacy runs excluded from the list; no per-run decision counts in the list (avoiding an N+1 read of conclusions); output ordering = persisted `started_at` then id (list) and pinned clause-pack order (assessments).
8. **Deviation to note**: the routes do **not** call `EvidenceApiReadService.require_subject_episode` (as `eligibility_review.py` does); the subject/episode/run scope check happens inside the service in the same session/transaction as the read (like `patient_profiles.get_patient_profile_revision`). This avoids a second session whose check could disagree with the read; the service is the only scope gate.
9. **Write-path gap observed (not fixed)**: `review_reference_validation.review_authority(run, episode)` (`app/storage/review_reference_validation.py:12`) takes `rule_set_id` from the *current* episode row; adopting it for reads would re-couple frozen history to mutable episode state, so I did not use it. Also `ReviewRun` carries `rule_set_revision` but no `rule_set_id`, so the run row alone cannot pin rule-set identity — the frozen context authority is the only source, which is what I used.

## Rerun Requests Or Next Step

No rerun of this pass is needed; no budget or tool boundary was hit. Nothing here is runtime or clinical acceptance.

Owner integration sequence (my recommendation, in order):

1. Register the adapter: `from app.api.v2.review_history import router as review_history_router` + `app.include_router(review_history_router)` in `app/api/v2/app.py`. No other wiring is required (no `app.state` entry; the routes use the existing `session_factory`).
2. Add a runtime check through the existing harness pattern (`tests/v2/api/`): seed a V2 run with context, one `FinalAssessment` per pinned clause and a matching `ActionRequest`, then assert (a) list ordering and `status`, (b) detail payload contract, (c) legacy run by id → 409 `REVIEW_HISTORY_UNSUPPORTED`, (d) completed run with one assessment removed → 500 `REVIEW_HISTORY_INCOMPLETE` with missing ids, (e) later upload/correction (episode pointer/revision bump) leaves the frozen read unchanged, (f) empty history → `items: []`. These are the paths I could not execute without a database.
3. Decide items 2–7 of the previous section (failed-state representation, action-snapshot semantics, referential closure at read, clause-pack derivation, error-class location, status codes, list exclusions) before the UI binds to this wire shape.
4. Keep `indeterminate` (and every future `ComponentDecision` member) in any wire validator; a subset `Literal` would break stored formal reports.

Resume point if this session is continued: files are final and compiled; the next action is an owner-run runtime verification (item 2) — no further source changes are proposed from my side.
