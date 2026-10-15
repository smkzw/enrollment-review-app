Both files are new-to-HEAD (untracked in this worktree branch) — expected; the script predates this branch's commits. Boundary is clean: only the two authorized files were touched this turn, source artifacts byte-identical.

# Execution Output: phase5-slice58r-affected-package-semantic-validation-20260826 - worker_01

## Boundary And Context Check

- Working directory: `.worktrees/phase5-clinical-facts-profile` (runner-bound). Read set consumed: `context/..._execution_context.md`, `plans/codex_execution_...md`.
- Parent review accepted the generic package-limited entry and rejected audit durability; this pass corrected exactly that.
- Edits confined to the two authorized files: `scripts/run_phase_applicability_acceptance.py`, `tests/v2/protocols/test_phase_applicability_package_selection.py`. Verified via `git status --short` (both `??` untracked in this branch — the script predates branch HEAD; no other file under `scripts/`, `tests/`, `artifacts/`, `app/` was touched this turn).
- Source authority untouched: sha256 of `artifacts/phase5-slice58q-.../frozen_phase_plan.json` (`67ffbb7c...`) and `coverage_manifest.json` (`6bcf5256...`) identical before and after all test runs.
- No semantic model run, no browser, no subject/production paths, no Trellis task created (delegated worker; not requested).

## Work Performed

Root cause fixed: the old-to-new package mapping existed only in optional `--summary`/stdout; the durable checkpoint stored only the derived plan.

1. **Durable provenance, automatic, `--summary`-free.** New in the script:
   - `PACKAGE_SELECTION_PROVENANCE_VERSION = "phase5/phase-applicability-package-selection-provenance/v1"`.
   - `_select_frozen_plan_packages(plan, requested_ordinals, run_id)` now returns a deterministic provenance payload (not just mapping): schema version, `run_id`, `source_plan_id`, `derived_plan_id`, `selected_source_ordinals` in order, `source_plan_sha256` / `derived_plan_sha256` (canonical `model_dump(mode="json")` + `sort_keys` + compact separators → SHA-256), and `package_mappings[]` with per package `source_ordinal`, `source_package_id`, `derived_ordinal`, `derived_package_id`, exact `owned_structure_unit_ids`.
   - `_package_selection_provenance_path(state_dir, run_id)` — run-id-bound `<run_id>.package-selection-provenance.json` inside `--state-dir`; file-store mode (`.json` state dir) mirrors the execution store's file layout as `<stem>-<run_id>.package-selection-provenance.json` beside it.
   - `_persist_package_selection_provenance(path, payload)` — stdlib-only atomic write (`tempfile.NamedTemporaryFile` + `fsync` + `os.replace`, same pattern as `PhaseApplicabilityExecutionStore.save`). Existing identical file → no-op (identical reruns stable). Existing conflicting payload → raises `PackageSelectionProvenanceError("PACKAGE_SELECTION_PROVENANCE_CONFLICT", ...)`; the first file is never overwritten.
2. **Ordering per required correction.** `main()` now: parse/select (invalid selection → clean stderr error, rc 2, nothing written) → `service.prepare()` (durable checkpoint persisted before any model call; conflicting run id already fails here as `EXECUTION_INPUT_CONFLICT` with first checkpoint untouched) → persist/verify provenance → then `service.execute()` for the model path. Both identity error classes caught → `error: CODE: message` on stderr, rc 2, no traceback. Full-plan runs (no `--package-ordinals`) are byte-for-byte the old behavior: no provenance file, no extra calls.
3. **Tests extended** (13 total, all in the authorized test file):
   - `test_cli_build_only_without_summary_writes_reloadable_provenance` — CLI build-only **without** `--summary` writes reloadable provenance; mapping exactly matches the execution checkpoint (derived ids/ordinals, owned unit ids against both source plan and checkpoint plan, `expected_structure_unit_ids` reconstruction) and both payload hashes re-verify via the script's canonical hasher.
   - `test_cli_identical_rerun_is_stable` — second identical run: rc 0, provenance and checkpoint bytes unchanged.
   - `test_cli_conflicting_selection_same_run_id_fails` — different selection, same run id: rc ≠ 0, `EXECUTION_INPUT_CONFLICT`, first provenance and checkpoint bytes unchanged.
   - `test_cli_conflicting_provenance_blocks_checkpoint_rebuild` — provenance-level guard: with the checkpoint deleted, a different selection is still rejected (`PACKAGE_SELECTION_PROVENANCE_CONFLICT`) and the first provenance is never overwritten.
   - `test_provenance_persistence_refuses_conflict_and_allows_identical` (unit) — identical rerun no-op; conflicting payload refused, file untouched.
   - `test_provenance_path_is_run_id_bound` (unit) — directory and file-store layouts.
   - Existing tests updated to the new signature/shape: rebuild, unknown/duplicate ordinals, all-ordinals reproduces source plan, scope isolation, scoped CLI checkpoint (now asserting provenance shape in `--summary`), invalid-selection tests additionally assert **no provenance file** is written.

## Artifacts And Evidence

- `scripts/run_phase_applicability_acceptance.py` — modified (provenance entry, `--package-ordinals` help text updated, error handling).
- `tests/v2/protocols/test_phase_applicability_package_selection.py` — modified (13 tests).
- Evidence:
  - Focused suite: `13 passed in 17.85s` (`.venv/bin/python -m pytest tests/v2/protocols/test_phase_applicability_package_selection.py -v`, Python 3.12.13, pytest 9.0.2).
  - Regression: `tests/v2/protocols/test_phase_applicability_contract.py` + `tests/v2/protocols/test_slice58c2_phase_applicability_agent.py` → `52 passed in 0.09s`.
  - Smoke (temp state dir, removed after): CLI with `--package-ordinals 67,78,79,80,111`, no `--summary` → status `planned`, `batch_count=5`, `expected_agent_unit_count=36` (12+5+8+7+4), derived `plan_id=papl-bdddaa9c30e35dffb08ca09f` equal in checkpoint and provenance, `input_scope_sha256=6e1a8144...` (≠ legacy full-plan run `d001-ii-phase-closure-20260826-slice58q.json`, asserted in test), provenance file contains full `package_mappings` with exact owned unit ids.
  - `py_compile` clean on both files.

## Commands And Observations

- `.venv/bin/python -m pytest tests/v2/protocols/test_phase_applicability_package_selection.py -v` → 13 passed (all listed above).
- `.venv/bin/python -m pytest tests/v2/protocols/test_phase_applicability_contract.py tests/v2/protocols/test_slice58c2_phase_applicability_agent.py` → 52 passed.
- `sha256sum` of the two 58q source artifacts before/after → identical.
- CLI smoke run as above; `/tmp/prov-smoke` removed after evidence capture.
- `git status --short -- scripts/ tests/ artifacts/ app/` → my two files untracked; all other `M` entries pre-existing worktree changes from earlier branch work, untouched this turn.

## Blockers Or Missing Environment

- None blocking.
- `ruff` is not installed in `.venv` → lint not run; style follows existing in-file patterns manually. Smallest remediation if wanted: `pip install ruff` (not done — no silent installs).
- `tests/v2/protocols/test_phase_applicability_live_execution.py` deliberately NOT run: it has no skip guard and would invoke a real semantic model (parent forbids model runs this slice).

## Rerun Requests Or Next Step

- Remaining limitation (by constraint, not defect): the non-build-only execute path's prepare→provenance→execute ordering is structurally in place and its two failure modes are covered (checkpoint conflict test at service level; provenance conflict test), but a real model run through that path has not been exercised — it is the natural next step for the slice58r parent after Codex authorization (five packages 67/78/79/80/111, fresh run id, fresh state dir; claims_complete=false).
- Suggested parent acceptance check: re-run the focused suite (`13 passed` expected) and review the provenance JSON schema against the audit contract (fields listed under "Work Performed" item 1).
- No further worker action requested from this role; no rerun inputs missing.
