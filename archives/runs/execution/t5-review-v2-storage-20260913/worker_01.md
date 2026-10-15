Trellis SessionStart ✓

I'll start by reading the initial read set.

Now I have the full picture. Let me implement the model changes.

Models are in place and construct correctly. Now the additive migration.

Implementation complete and verified at the schema-construction level. Here is the worker report.

# Execution Output: t5-review-v2-storage-20260913 - worker_01

## Boundary And Context Check

- Role: bounded first-line executor (`codebuddy` / `codebuddy-cli` / `deepseek-v4.1-flash`), admitted under current route. No recursive delegation, no conference, no peer review, no user delivery.
- Workspace: runner-provided CWD `.` (worktree `phase5-clinical-facts-profile`). All reads/writes stayed inside it. No production path read or written.
- Writes performed — exactly two, both authorized:
  - `app/storage/models.py` (modified, +150/-9)
  - `app/storage/migrations/versions/0023_review_v2_evidence_lineage.py` (new file, revision `0023`)
- Writes NOT performed (explicitly out of scope): domain contracts, repositories, service/API/UI, tests, docs, personal config, any database. No older migration touched (`git status` shows no modification under `app/storage/migrations/versions/` except the new file).
- Operations NOT run (per assignment): migrations, tests, services, models/services runtime, browser, network. No database was opened, created, or queried. Only byte-compilation and in-memory SQLAlchemy schema construction/comparison were used, which the assignment permits.
- Read set: initial read set (execution context + Codex plan), then read-only inspection of `app/storage/models.py`, `evidence_models.py`, `ocr_models.py`, `facts_models.py`, `evidence_locator_models.py`, `db.py`, `migrate.py`, migrations `0001/0002/0010/0022` + `env.py` + `alembic.ini`, `.trellis/spec/backend/database-guidelines.md`, `app/domain/contracts/review_evidence_scope.py`, `app/domain/contracts/review.py`, `runs/conference/r07-judgment-publication-boundary-20260913/evidence_v2_storage.md` (advisory), plus `app/storage/repositories.py` and `tests/v2/storage/*` read-only to identify consumer impact.
- Existing unrelated dirty changes preserved: dirty-path count is 1600 = pre-existing 1598 + the 2 authorized files. No unrelated file was staged, reverted, or reformatted.

## Work Performed

Selected approach (matches the advisory evidence and `database-guidelines.md` §40): extend the **existing** formal review chain in place with exactly one evidence lineage per row. No parallel `*_v2` review chain, no context-snapshot-only change, no fabricated legacy evidence.

### 1. `app/storage/models.py`

- Added two module-level SQL constants:
  - `REVIEW_EVIDENCE_LINEAGE_CHECK_SQL` — strict `legacy XOR (V2 + complete revision)`.
  - `AGENT_CALL_EVIDENCE_LINEAGE_CHECK_SQL` — 3-branch form that additionally allows the all-NULL protocol-only call.
- `review_runs` / `assessment_candidates` / `final_assessments` / `action_requests`:
  - `evidence_snapshot_id`: NOT NULL → **nullable**, FK to `evidence_snapshots.evidence_snapshot_id` kept unchanged (column and FK not removed).
  - Added `evidence_snapshot_v2_id` (nullable, FK `evidence_snapshots_v2.evidence_snapshot_id`).
  - Added `complete_processing_revision_id` (nullable, FK `evidence_processing_revisions.evidence_processing_revision_id`).
  - Added CHECK per table: `ck_review_runs_evidence_lineage`, `ck_assessment_candidates_evidence_lineage`, `ck_final_assessments_evidence_lineage`, `ck_action_requests_evidence_lineage` — row must have exactly one lineage; a V2 row must have `evidence_snapshot_id IS NULL`.
- `action_requests`: additionally added `trigger_locator_id` (nullable, FK `evidence_locator_artifacts.locator_id`) next to the untouched legacy `trigger_evidence_span_id`.
- `agent_calls`: added the same two V2 columns (both nullable) + CHECK `ck_agent_calls_evidence_lineage`. The all-NULL protocol-only call remains valid; a call carrying evidence pointers must still be exactly one lineage. The review-only XOR was deliberately NOT applied.
- Added 5 ordered V2 association tables via the existing `_assoc_table` helper (owner, ref, position ordering + two unique constraints + real FKs):
  - `assessment_candidate_facts_v2` → `assessment_candidates` × `clinical_facts_v2.fact_id`
  - `assessment_candidate_locators` → `assessment_candidates` × `evidence_locator_artifacts.locator_id`
  - `final_assessment_facts_v2` → `final_assessments` × `clinical_facts_v2.fact_id`
  - `final_assessment_locators` → `final_assessments` × `evidence_locator_artifacts.locator_id`
  - `action_transition_locators` → `action_transitions` × `evidence_locator_artifacts.locator_id`
- Legacy association tables (`final_assessment_facts`, `final_assessment_spans`, `action_transition_spans`) and all legacy columns are untouched; V2 ids must never be written into them.

### 2. `app/storage/migrations/versions/0023_review_v2_evidence_lineage.py`

- Revision `0023`, `down_revision = "0022"` (discovered head was `0022`; `ScriptDirectory.get_heads()` now returns exactly `['0023']`).
- `upgrade()`:
  1. Rebuilds the five chain tables with the 0010 convention: drop the old named indexes → create `<name>_0023_new` → `INSERT … SELECT` (legacy columns mapped by name, 0023-only columns as `NULL`) → `DROP TABLE` old → `ALTER TABLE … RENAME TO` original name. `PRAGMA foreign_keys` is toggled on the raw DBAPI connection (0010 helper pattern) and `PRAGMA foreign_key_check` runs after every rebuild; failure raises.
  2. Creates the five V2 association tables.
  3. Final `PRAGMA foreign_key_check`.
  - No row is created, deleted, or updated; `payload_json`, `payload_sha256`, `created_at`, `revision`, and all child rows are copied verbatim; no V2 pointer is backfilled.
- `downgrade()`: refuses lossy downgrade when any V2 lineage data exists, then drops the five link tables and rebuilds the five chain tables back to the exact 0022 shape (drops `evidence_snapshot_v2_id`, `complete_processing_revision_id`, `trigger_locator_id`, drops the CHECK, restores `evidence_snapshot_id` NOT NULL for the four formal tables, keeps `agent_calls.evidence_snapshot_id` nullable).
  - Guard SQL (verified by printing):
    - `review_runs` / `assessment_candidates` / `final_assessments`: `evidence_snapshot_v2_id IS NOT NULL OR complete_processing_revision_id IS NOT NULL OR evidence_snapshot_id IS NULL`
    - `action_requests`: same `OR trigger_locator_id IS NOT NULL`
    - `agent_calls`: only the two V2 columns (all-NULL protocol-only rows do not block downgrade)
    - plus: any row in any of the five link tables blocks downgrade.

## Artifacts And Evidence

| Artifact | Change |
|---|---|
| `app/storage/models.py` | 5 chain tables get nullable legacy FK + 2 V2 lineage FKs + CHECK; `action_requests.trigger_locator_id`; `agent_calls` 3-branch CHECK; 5 new association tables |
| `app/storage/migrations/versions/0023_review_v2_evidence_lineage.py` | additive migration, revision 0023 (`down_revision 0022`), rebuild-based upgrade, guarded downgrade |

FK / CHECK inventory added (all against real parent keys, no generic `kind`+`id`):

- `review_runs.evidence_snapshot_v2_id → evidence_snapshots_v2.evidence_snapshot_id`
- `review_runs.complete_processing_revision_id → evidence_processing_revisions.evidence_processing_revision_id`
- same two FKs on `assessment_candidates`, `final_assessments`, `action_requests`, `agent_calls`
- `action_requests.trigger_locator_id → evidence_locator_artifacts.locator_id`
- `assessment_candidate_facts_v2.fact_id → clinical_facts_v2.fact_id`; `assessment_candidate_facts_v2.assessment_candidate_id → assessment_candidates.assessment_candidate_id`
- `assessment_candidate_locators.locator_id → evidence_locator_artifacts.locator_id`
- `final_assessment_facts_v2.fact_id → clinical_facts_v2.fact_id`; `final_assessment_facts_v2.assessment_id → final_assessments.assessment_id`
- `final_assessment_locators.locator_id → evidence_locator_artifacts.locator_id`
- `action_transition_locators.transition_id → action_transitions.transition_id`; `.locator_id → evidence_locator_artifacts.locator_id`

Migration assumptions (explicit, for Codex review):

1. At 0022 every existing row of the four formal tables has `evidence_snapshot_id` NOT NULL and the V2 columns do not exist, so the copy-into-new-table step satisfies the new strict CHECK without any backfill; `agent_calls` may already be NULL and stays legal.
2. Parent tables `evidence_snapshots_v2` (0008), `evidence_processing_revisions` (0009/0010), `clinical_facts_v2` (0013), `evidence_locator_artifacts` (0010), and `action_transitions` (0002) all exist by 0022; no new parent table is created.
3. This migration writes no rows: V2 rows are expected only from later repository/gate work; no fake `evidence_snapshots` row is ever needed and no V2 id is written into a legacy column.
4. `complete_processing_revision_id` is only FK-checked for existence; the "must be `revision_kind='complete'`" rule is a cross-table domain condition that DDL cannot express and stays with the domain gate.
5. Self-FK `review_runs.supersedes_review_run_id` is declared against the final name `review_runs` (not the temp name) because SQLite does not rewrite REFERENCES clauses during `RENAME` while `foreign_keys=OFF`; pointing at the temp name would leave a dangling target after the rename.
6. The rebuild keeps physical FK/index names only cosmetically different from a fresh create (`…_0023_new_…` inside constraint names), identical to the existing 0010 convention; `verify_schema_matches_metadata` compares referred table/columns, not constraint names.

## Commands And Observations

All executed with the repo virtualenv (`.venv/bin/python`); no migration, service, network, or database access.

| Command | Observation |
|---|---|
| `python -m py_compile app/storage/models.py` | `COMPILE_OK` |
| `python -m py_compile app/storage/migrations/versions/0023_review_v2_evidence_lineage.py` | `COMPILE_OK` |
| `python -m compileall -q app/storage` | `STORAGE_COMPILE_OK` |
| `import app.storage` + `CreateTable(...).compile(sqlite)` for the 10 changed/new tables | DDL constructed; `TABLES_OK 137` registered tables (132 previously + 5 new) |
| Structural diff: migration-built 0023 shape vs `Base.metadata` for 5 chain + 5 link tables (columns, type, nullability, PK, FKs, indexes, unique constraints) | `SCHEMA_MATCH_OK chain+link` — no mismatch |
| Structural diff: migration-built 0022 legacy shape vs module-level tables of `0002_domain_schema.py` | `LEGACY_SHAPE_MATCH_0002_OK` — downgrade restores the exact pre-0023 shape |
| Check-constraint SQL text comparison ORM vs migration | `CHECK_SQL_IDENTICAL` |
| `ScriptDirectory.get_heads()` / `get_revision('0023')` | `heads: ['0023']`, `down_revision: 0022`, walk `0023→0022→0021→0020→0019` |
| `git status --porcelain` (scoped and global) | only `M app/storage/models.py` and `?? …/0023_review_v2_evidence_lineage.py`; total dirty 1600 = baseline 1598 + 2 |
| `grep "INSERT INTO (review_runs|action_requests|agent_calls|final_assessments|assessment_candidates)"` in `tests/ app/ tools/ scripts/` | no raw inserts exist into the rebuilt tables; ORM inserts always include the new columns as NULL |

Tools/targets used: Read + Grep + Glob on the files listed in the Boundary section; Bash for `.venv/bin/python` compile and schema-construction inspection, `git status`. Browser/web/network tools were not needed and not used.

## Blockers Or Missing Environment

- No blocker. No missing tool or environment; `.venv` Python 3.12 + Alembic/SQLAlchemy were sufficient.
- Deliberately unverified (instruction boundary): the migration was never executed, so runtime behavior on a populated 0022 database, the backup/restore orchestration, WAL behavior, and `PRAGMA foreign_key_check` at runtime are not proven here. Schema construction is proven to match the ORM exactly, and the 0022 legacy shape is proven to match the frozen 0002 definitions.
- Expected test breakage that I could not fix (tests are outside the allowed writes, so the owner must update them):
  - `tests/v2/storage/test_migration_0008.py`: historical metadata snapshots copy the current `Base.metadata`. The five new tables must be added to `PHASE5_V2_TABLES`, and `_SLICE44_STRIP_COLUMNS` / `_copy_table_without_slice44` must strip `evidence_snapshot_v2_id`, `complete_processing_revision_id` (and `trigger_locator_id` for `action_requests`) from the five chain tables and restore `evidence_snapshot_id` NOT NULL for pre-0023 targets. Without this, `test_migration_0008/0008a/0009/0010` fail at their old-target schema checks.
  - `tests/v2/storage/test_migration_0021.py`: the inline pre-0022 metadata builder has the same problem; it should reuse the updated helpers instead of duplicating the exclusion list.
- No repository/gate wiring was done (not authorized), so no V2 review row can yet be written end-to-end. `_action_columns` currently uses `payload["evidence_snapshot_id"]` and will `KeyError` for a V2 payload; `_check_*_scope` compares only the legacy column. These are required follow-up work items owned by Codex.

## Rerun Requests Or Next Step

Precise owner integration checks (in order):

1. Update the two historical-metadata test helpers as described above, then run `tests/v2/storage/test_migration_0008*.py`, `test_migration_0009/0010/0011/0013/0018–0022` plus the new migration test.
2. Add `tests/v2/storage/test_migration_0023.py` covering: head upgrade + `verify_schema_matches_metadata`; legacy rows preserved bit-for-bit (payload/hash, child rows, `revision`); CHECK rejects mixed lineage (V2 id + legacy id, V2 without complete revision); `agent_calls` all-NULL accepted; downgrade refused with a V2 row and with a link-table row; empty downgrade restores the 0022 shape (`evidence_snapshot_id` NOT NULL, no 0023 columns).
3. Repository/gate follow-up (separate item): `_check_run_scope` / `_check_assessment_scope` / `_check_action_scope` / `_check_agent_call_scope` lineage branching (V2 compares episode's active snapshot + active complete revision); CONFIG column mirrors for the new columns with missing-key-as-NULL; `_action_columns` → `payload.get(...)`; V2 association read/write for the five tables; `ActionRequestRepository.get` mirrors; `publish_assessment` / `RegisteredReviewScope` V2 branch.
4. Decide whether the three extra link tables (`assessment_candidate_facts_v2`, `assessment_candidate_locators`, `action_transition_locators`) are in the intended slice. I added them because the work item asked for candidate/transition references with real parents; if Codex scopes only assessments + action trigger, remove them from both files (they have no consumers yet).
5. Open question: naming `final_assessment_locators` / `*_facts_v2` follows the r07 advisory; confirm before consumers bind to the names in a later item.

No rerun of this pass is needed; no budget stop occurred. I make no claim of migration or clinical acceptance — that remains Codex's decision.
