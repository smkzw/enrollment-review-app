# Execution Output: enrollment_phase2_sqlite - worker_01

## Boundary And Context Check

- Read `AGENTS.md`, execution context, Codex plan, Trellis task `08-14-phase2-sqlite-domain-jobs` (`prd.md`/`design.md`/`implement.md`), `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`, implementation plan, all `.trellis/spec/backend/*` specs.
- Authorized scope confirmed: writes confined to `app/storage/`, `alembic.ini`, `tests/v2/`, `.gitignore`, journal. `app/router/`, `app/pipeline/`, `app/models.py`, `app/shared.py`, `projects/` untouched (legacy tree hash invariance proven, see evidence).
- Environment verified: Python 3.12.13, SQLite 3.53.1 (≥ gate 3.51.3), SQLAlchemy 2.0.52, Alembic 1.19.1 — all match PRD pins. No package installs, no production writes.
- Slice = implement.md §1 (基础设施与初始迁移) + write-boundary tests. Domain ORM (§2), idempotency/concurrency (§3), Job/API/SSE (§4-5) intentionally left to worker_02/03 per serial plan.

## Work Performed

| File | Content |
|---|---|
| `app/storage/config.py` | `ENROLLMENT_V2_DATA_DIR` data-root resolution (default `<repo>/data_v2`), `DataPaths` layout (db/backups/blobs/migration-lock), SQLite ≥3.51.3 runtime gate with Chinese startup-block error, legacy-root overlap rejection via `WriteBoundary` |
| `app/storage/db.py` | Naming convention, `Base`, `build_engine`/`build_session_factory`, per-connection PRAGMA contract set+verify (`foreign_keys=ON`, `journal_mode=WAL`, `synchronous=FULL`, `busy_timeout=10000`), `PragmaError`, `wal_health` observability (passive checkpoint only) |
| `alembic.ini` + `app/storage/migrations/` | `env.py` (URL from data root unless injected, `render_as_batch=True`), `script.py.mako`, `versions/0001_baseline.py` (empty baseline, upgrade+downgrade) |
| `app/storage/migrate.py` | `MigrationLock` (fcntl.flock non-blocking), `create_backup` (passive checkpoint → `sqlite3.Connection.backup()` → `PRAGMA integrity_check` → manifest with source revision/size/SHA-256), `upgrade`/`downgrade` (backup→migrate→verify: PRAGMA + schema↔metadata + basic read/write), `restore` (verified backup → backup-API copy → stale `-wal`/`-shm` cleanup), `verify_schema_matches_metadata`, `upgrade_or_fail` startup entry |
| `app/storage/cli.py` | `python -m app.storage.cli {paths,check-runtime,backup,upgrade,downgrade,restore,verify}` |
| `tests/v2/storage/` | `conftest.py` + `test_config.py` (10), `test_db.py` (10), `test_migrations.py` (10), `test_write_boundary.py` (4) — 37 tests |
| `.gitignore` | added `data_v2/` |
| journal | Session 5 entry appended to `.trellis/workspace/smkzw/journal-1.md` |

## Artifacts And Evidence

- **Storage suite**: `.venv/bin/pytest -q tests/v2/storage tests/v2/test_architecture_boundaries.py` → **37 passed, 2 subtests passed**.
- **Full suite**: `.venv/bin/pytest -q` → **312 passed, 1 skipped (pre-existing MG-K10-SAR OCR fixture), 18 subtests passed** — no regression vs legacy baseline.
- **Failure modes exercised, not just green paths**:
  - Migration mid-failure (temp migration script raising + bad SQL): original DB still readable at pre-failure revision with data intact, backup exists with `integrity=ok` manifest, `upgrade_or_fail` refuses to start.
  - Corrupt/missing backup → `BackupIntegrityError`/`MigrationFailure`, live DB untouched.
  - PRAGMA deviation (raw connection `foreign_keys=OFF`, forced `journal_mode=DELETE`) detected and re-enforced; orphan-FK insert rejected only under our contract (raw default connection accepts it — enforcement provenance proven).
  - Runtime gate: simulated 3.50.0/3.51.2 rejected with Chinese message, boundary 3.51.3 accepted.
  - Schema↔metadata drift (missing column, extra column, unmapped table) detected.
- **Real-root closed loop** (implement.md validation commands): `uv lock --check` OK; CLI `check-runtime`/`paths`/`upgrade`(base→0001)/`verify` OK; raw `alembic downgrade base` + `alembic upgrade head` OK; `restore` from verified backup → base → re-upgrade → 0001; backup manifest `{"source_revision":"base","size_bytes":12288,"sha256":"…","integrity":"ok"}`; final state head `0001`, `verify` problems `[]`.
- **Legacy invariance**: `projects/` snapshot (8797 files) identical before/after full storage lifecycle, both in tests and real-root runs.
- `git diff --check` clean; final DB left at head `0001` in gitignored `data_v2/` (2 verified backups + manifests retained for worker_02).

## Commands And Observations

- `.venv/bin/pytest -q tests/v2/storage tests/v2/test_architecture_boundaries.py` — first run 3 fails (demo-migration tables vs empty `Base.metadata`; raw `sqlite3.DatabaseError` leak on corrupt file; downgrade-to-base compared against head metadata) — all root-caused and fixed (injectable `metadata` param, `sqlite3.Error`→`BackupIntegrityError` wrapping, `check_metadata=False` on downgrade).
- Two `edit` calls landed on stale anchors and corrupted `migrate.py`; detected immediately and rewritten cleanly with `write` — no bad code persisted.
- Alembic logging is WARNING-level (ini), so normal runs are quiet; migration INFO lines captured by pytest.

## Blockers Or Missing Environment

None. All required runtime components present and version-pinned; no external services needed.

## Rerun Requests Or Next Step

- **worker_02**: add domain ORM + `versions/0002_domain_schema.py` with `down_revision="0001"` (batch mode auto-enabled via env.py). Use `MigrationManager`/`upgrade_or_fail` as-is — schema↔metadata verification now compares real tables, and the domain migration must keep DDL aligned with metadata (types, nullability, PK/FK/unique/index) or startup verification fails by design. Temp-file DBs via `ENROLLMENT_V2_DATA_DIR` monkeypatch (`tests/v2/storage/conftest.py` pattern).
- **worker_03**: call `upgrade_or_fail()` before serving writes — it is the structural "migration failure blocks write service" gate; `build_engine` re-enforces the version gate at every engine creation. `wal_health` available for health endpoints (deferred checkpoint policy: observation only).
- **Final worker**: update `.trellis/spec/backend/database-guidelines.md` with the established PRAGMA contract, backup naming/manifest, and version gate (implement.md §6); final cleanup of `data_v2/` backups/artifacts per §6.
- Residual risk: `verify_schema_matches_metadata` compares SQLite reflected type strings; worker_02 must confirm Enum/custom-type compiles match migration DDL (report any legitimate variance instead of weakening the check).
