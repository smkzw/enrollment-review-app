All verification complete. Final state: 19/19 tasks done, full suite green, legacy tree invariant, real data root at head 0002 with verified backup. Producing the report.

# Execution Output: enrollment_phase2_sqlite - worker_02

## Boundary And Context Check

- Read `AGENTS.md`, `context/enrollment_phase2_sqlite_execution_context.md`, Codex plan, Trellis `08-14-phase2-sqlite-domain-jobs/{prd,design,implement}.md`, all `.trellis/spec/backend/*` specs, worker_01 report.
- Authorized slice = implement.md §2 (领域表与仓储) + §3 (幂等/乐观并发/stale). Job 状态机/租约/API/SSE (§4-5) intentionally left to worker_03 per serial plan; storage primitives for jobs provided as agreed foundation.
- Writes confined to: `app/storage/*` (new: `models.py`, `codecs.py`, `concurrency.py`, `idempotency.py`, `staleness.py`, `repositories.py`; modified: `__init__.py`), `app/storage/migrations/versions/0002_domain_schema.py` (new), `tests/v2/storage/*` (6 new test files + conftest extension), journal. `tests/v2/storage/test_migrations.py` head constant updated 0001→0002 (worker_01's handoff anticipated this).
- Worker_01's verified work not redesigned: `MigrationManager`/`upgrade_or_fail`/`verify_schema_matches_metadata` used as-is; domain migration keeps DDL aligned with metadata (verified, 0 problems).
- Read-only anchors untouched: `projects/`, `app/router/`, `app/pipeline/`, `app/models.py`, `app/shared.py`, domain contracts (frozen Phase 0.5) — zero diffs.

## Work Performed

| File | Content |
|---|---|
| `app/storage/models.py` | 51 tables: 5 revisioned mutable roots (projects/subjects/review_episodes/evidence_expectations/action_requests/jobs/job_steps with mapper `version_id_col`), append-only records with canonical JSON payload+sha256+created_at (protocol chain, rule set tree, evidence chain, review/action, agent/gate, projections), 9 ordered association tables, `entity_staleness`, `idempotency_records`; episode↔snapshot cycle broken by **both** FKs `DEFERRABLE INITIALLY DEFERRED`; composite natural PKs ordered (rule_set_id, rule_set_revision, id) |
| `app/storage/codecs.py` | canonical encode/decode (identical to `canonical_hash` algorithm), hash verification, `PersistedContractInvalid` on tamper/schema failure, column↔payload mirror cross-check with dotted paths, UTC-naive datetime helpers |
| `app/storage/concurrency.py` | `StaleRevisionError` (code `STALE_REVISION`) carrying expected/current revision + JSON field diff + full current record; `apply_revisioned_update`: check → contract rebuild → single-flush with payload revision synced to the version_id bump; `StaleDataError` (ORM backstop) converted to the same envelope |
| `app/storage/idempotency.py` | `(scope, idempotency_key)` unique + request sha256: same key+hash returns original result, same key+different hash → `IdempotencyConflict` (code `IDEMPOTENCY_CONFLICT`), concurrent duplicate insert mapped likewise |
| `app/storage/staleness.py` | open (idempotent per source revision), `list_open` filters, `close_covered` closes only `(target_type, target_id)` in the completed ReviewRun's coverage — out-of-coverage entries stay open |
| `app/storage/repositories.py` | generic `AppendRepository` (config registry per contract: normalized columns, mirrors, assoc tables, scope checks), `ProjectRepository`/`SubjectRepository`/`EpisodeRepository`/`EvidenceExpectationRepository`/`ActionRequestRepository` (mutable, expected-revision updates; action replace appends transitions, history cross-checked on read), rule-set tree + protocol authority chain composed writes, projections, Job storage primitives (`create_job/step/checkpoint`, `append_event` with per-job monotonic seq, `list_events(job_id, after_seq)`), `persist_fixture` full seeding. Scope violations (cross-project/version/run/component) rejected as `ScopeViolationError`; FK rejects as `InvalidReferenceError`; duplicates as `DuplicateRecordError` |
| `app/storage/migrations/versions/0002_domain_schema.py` | Frozen DDL generated from ORM metadata (same naming convention); upgrade creates 51 tables + indexes, downgrade drops in reverse |
| `app/storage/__init__.py` | imports `models` so every storage entrypoint (CLI, `upgrade_or_fail`, verify) sees the full metadata — fixes startup verification after 0002 |
| `tests/v2/storage/` | `test_codecs.py` (10), `test_domain_schema.py` (10), `test_repositories_roundtrip.py` (16), `test_idempotency.py` (5), `test_optimistic_concurrency.py` (5), `test_staleness.py` (5) + conftest `migrated_engine`/`session_factory`/`session` fixtures |
| journal | Session 6 appended to `.trellis/workspace/smkzw/journal-1.md` |

## Artifacts And Evidence

- **Storage suite**: `.venv/bin/pytest -q tests/v2/storage` → **106 passed**.
- **Full suite**: `.venv/bin/pytest -q` → **387 passed, 1 skipped** (pre-existing MG-K10-SAR/06003 OCR fixture), 18 subtests passed. No regression vs worker_01 baseline (312).
- **Round-trip**: all three Phase 0.5 fixtures (subject-barrier/clear/gap_conflict) persist and read back equal — every collection: protocol doc, authority record/command/confirmation/manifest/source records, rule set tree (rules/components/requirements incl. expression hash columns), workflow stages, project, subject, episode, snapshot (ordered doc assoc), spans, facts (ordered span assoc), conflict groups, expectations, prompts, models, gates, agent calls (sources+gates assoc), normalization candidates, patient profile, runs, candidates, final assessments (fact/span assoc), actions (incl. transition history equality), rollup, job events (seq 1..N, `after_seq` resume ordered, no dupes).
- **Failure modes exercised, not just green paths**:
  - Tampered payload JSON / sha256 column / schema-invalid payload / corrupt JSON → `PersistedContractInvalid`; column↔payload mirror drift → rejected.
  - Cross-scope negatives rejected: cross-subject fact, wrong run rule_set_revision/protocol, cross-rule-set component, cross-episode action/assessment, mismatched subject↔project episode, unknown rule set revision, foreign requirement, orphan project FK, duplicate PK/rule-set revision.
  - Duplicate fixture re-persist → `DuplicateRecordError` (one record, never duplicated).
  - Idempotency: same key+hash → single record (created=True then False); same key+diff hash → conflict with hashes, no second row; scopes independent; raw unique constraint enforcement.
  - Concurrency: two sessions at revision 1 — winner commits, loser gets `STALE_REVISION` with current_revision=2, `field_diff.current/submitted`, `current_record`; DB not silently overwritten (verified via third session). Project rule_set change re-scopes columns + re-validates; expectation update replaces span assoc atomically.
  - Staleness: open idempotent, filters, `close_covered` clears exactly 2/3 covered targets with `cleared_by_review_run_id`, empty coverage closes nothing.
  - Migration lifecycle: empty→0001→0002, downgrade to base (only `alembic_version`), re-upgrade; `verify_schema_matches_metadata == []` (51 tables, all constraints/indexes reflected exactly); PRAGMA contract measured on migrated engine; deferred-FK cycle proven in-transaction; `upgrade_or_fail` startup gate from empty temp root reaches head 0002.
- **Real root**: `data_v2/enrollment-review-v2.sqlite3` at revision 0002, `integrity_check=ok`, CLI `verify` passes ("验证通过：PRAGMA、schema 与基础读写均符合基线"). The 0001→0002 transition backup (`20260814T010521160348Z-0001.sqlite3`, integrity=ok manifest) preserved after a verification failure of the earlier run — matching PRD "迁移失败保留原库和备份".
- **Legacy invariance**: `projects/` = 8797 files, zero `git status` entries before/after all work; `git diff --check` clean; `uv lock --check` OK.

## Commands And Observations

- `.venv/bin/pytest -q tests/v2/storage` / `.venv/bin/pytest -q` — as above.
- `PYTHONPATH=. .venv/bin/python -m app.storage.cli upgrade|verify` — real-root lifecycle.
- Notable defects found and fixed during implementation (evidence of real failure modes):
  1. Core DML statements skip SQLAlchemy autoflush → assoc inserts raced ahead of parent rows (FK failures). Fixed by explicit flushes before interleaved Core DML (`AppendRepository.save`, `_insert_transitions`, `create_step`, `save_rule_set` per-level).
  2. `INSERT … DEFAULT VALUES` emitted for empty ref lists (executemany with no params). Fixed with empty guards in `_write_assoc`/`_replace_assoc`.
  3. `version_id_col` as string breaks SQLAlchemy 2.0.52 RETURNING path (`Textual column expression 'revision'`). Fixed with `@declared_attr.directive` passing the real Column.
  4. Composite PK column order (id first) mismatched `session.get` lookups → silent `None`. Reordered PKs to `(rule_set_id, rule_set_revision, id)` and regenerated frozen DDL.
  5. Payload `revision` diverged from version_id column on update (double bump). Fixed: payload revision synced to `checked+1` in a single flush; contracts without a revision field (EvidenceExpectation) use the column only as a concurrency token.
  6. `persist_fixture` ordering: agent calls scope-check their ReviewRun before runs existed; gates→runs→calls→candidates reordered.
  7. CLI/startup verification saw empty metadata (models module never imported) → package `__init__` registration.

## Blockers Or Missing Environment

None. Python 3.12.13 / SQLite 3.53.1 / SQLAlchemy 2.0.52 / Alembic 1.19.1 all as pinned; no installs, no production writes.

## Rerun Requests Or Next Step

- **worker_03 (Job workflow + API/SSE)**: build on the storage primitives — `JobRepository` (`create_job/create_step/create_checkpoint/append_event/list_events/get_job/get_step`), monotonic `(job_id, event_seq)` unique, `last_event_seq` watermark updated in the same transaction; call `upgrade_or_fail()` before serving writes (structural gate, verified at 0002). Compose user actions as: idempotency resolve → repository writes in one `session.begin()`.
- **Contracts to consume**: `StaleRevisionError.as_dict()` (code `STALE_REVISION` + current/submitted revision + field diff + current record) and `IdempotencyConflict.as_dict()` (code `IDEMPOTENCY_CONFLICT`) map 1:1 to the design §8 error envelope — API layer adds the Chinese problem/impact/recovery wording only.
- **Caveats to preserve**: (a) ORM models intentionally declare no `relationship()` objects — repository calls flush per entity; raw multi-entity batch inserts need dependency-ordered flushes; (b) episode↔snapshot FKs are `DEFERRABLE INITIALLY DEFERRED` (both directions) — violations on those columns surface at commit as raw IntegrityError, scope checks give the typed errors first; (c) mutable roots' payload `revision` is kept equal to the version_id column by the update path; EvidenceExpectation carries revision only on the column (contract frozen without a revision field — Phase 0.5).
- **Residual**: `EntityStaleness`/`IdempotencyRecord` DTOs are dataclasses (not contracts) — intentional, storage-internal; worker_03 shouldn't serialize them directly into API payloads.
- **Final worker**: update `.trellis/spec/backend/database-guidelines.md` with the established payload/codec/mirror pattern, revision semantics, and 0002 table inventory (implement.md §6); final cleanup of `data_v2/` backups/artifacts per §6.
