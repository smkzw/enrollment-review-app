Trellis SessionStart ✓

Reading the initial read set now.

Context is sufficient. Making the two scoped edits now — first the ORM source column and CHECK.

Both artifacts are written, compiled, and cross-checked statically. Final report below.

---

# Execution Output: r05-evidence-control-origin-20260914 - worker_01

## Boundary And Context Check

- Read the initial read set: `context/r05-evidence-control-origin-20260914_execution_context.md`, `plans/codex_execution_r05-evidence-control-origin-20260914.md`. Both confirm: 1 bounded item, high risk, no production writes, worker output is evidence only.
- Work item: 仅修改 `EvidenceRequirementRecord` 来源列 + 新增 0025 迁移草案；主线程（Codex）负责仓储发布与投影。
- Write scope respected: exactly two paths touched — `app/storage/models.py` (targeted hunk inside `EvidenceRequirementRecord` only) and new `app/storage/migrations/versions/0025_control_evidence_origin.py`. Nothing else created, modified, reset, or cleaned. No report file written via tools (this response is the report).
- Read-only adjacent source inspected (permitted): `app/domain/contracts/rules.py`, `app/domain/contracts/control_evidence_origin.py`, `app/storage/control_catalog_models.py`, `app/storage/migrations/versions/0024_protocol_control_catalogs.py`, `0006_phase3_slice4.py`, `0014`, `0016`, `0024`, `env.py`, `app/storage/migrate.py` (`verify_schema_matches_metadata`), `app/storage/db.py` (naming convention), `app/storage/__init__.py`, `app/storage/repositories.py:1499-1626`, `tests/v2/protocols/test_migration_0006.py`.
- Prohibited actions not performed: no migration execution, no SQLite (file or in-memory), no `pytest`, no app import, no model call, no browser, no installs, no clinical source queries. Only source reading + `py_compile` on the two allowed files.

## Work Performed

**1. `app/storage/models.py` — `EvidenceRequirementRecord` (lines 390-440)**

- Added ONE nullable column mirroring `control_origin.publication_id` (models.py:407-413):
  `control_publication_id: Mapped[str | None] = mapped_column(String(128), ForeignKey("protocol_control_catalog_publications.publication_id"), nullable=True)`
  With a Chinese comment stating that `protocol_control_id` / `evidence_key` / `workflow_stage_id` remain payload-only. No second control table, no extra mirror columns.
- FK target verified against actual definitions, not the guessed label: `app/storage/control_catalog_models.py:29-31` defines table `protocol_control_catalog_publications` with PK `publication_id`; 0024 creates exactly that. Actual names used.
- Replaced the two-origin CHECK `one_origin` with an exactly-one-of-three CHECK (models.py:418-426), keeping the same constraint name `one_origin`:
  `(rule_component_id IS NOT NULL AND procedure_catalog_item_id IS NULL AND control_publication_id IS NULL) OR (rule_component_id IS NULL AND procedure_catalog_item_id IS NOT NULL AND control_publication_id IS NULL) OR (rule_component_id IS NULL AND procedure_catalog_item_id IS NULL AND control_publication_id IS NOT NULL)`
  Form chosen to match the project's existing boolean OR-of-AND CHECK style (e.g. `REVIEW_EVIDENCE_LINEAGE_CHECK_SQL`), not a new arithmetic idiom.
- Unchanged: PK, `rule_sets`/`rule_components` composite FKs, `Index("ix_evidence_requirements_fact_type", "fact_type")`, `fact_type`/`due_stage` columns, mixin columns.
- All other uncommitted changes in models.py (frontend slices: review-run/candidate/final-assessment/agent-call lineage, new assoc tables) were present before this pass and were preserved untouched (diff hunk headers confirm only one hunk in the 390-440 region).

**2. `app/storage/migrations/versions/0025_control_evidence_origin.py` (new, 275 lines)**

- `revision = "0025"`, `down_revision = "0024"` (0024's actual revision string verified in `0024_protocol_control_catalogs.py:23`).
- Upgrade: rebuilds `evidence_requirements` using 0006's proven SQLite pattern (build temp table → explicit-column copy → drop old → rename → `PRAGMA foreign_key_check`), with FK pragma off/on on the raw DBAPI connection. Copies by explicit column list with `NULL` for `control_publication_id`, so all historical component-origin and procedure-origin rows survive with `payload_json`/`payload_sha256` unchanged (no hash recompute, no payload rewrite). No rows inserted; no other table touched.
- New physical table shape matches the ORM exactly: 11 columns in the same order as ORM + mixin, PK (rule_set_id, rule_set_revision, requirement_id), three FKs — `rule_sets(rule_set_id, revision)`, `rule_components(rule_set_id, rule_set_revision, rule_component_id)`, and the single-column FK `protocol_control_catalog_publications(publication_id)` — plus index `ix_evidence_requirements_fact_type`. This is what `verify_schema_matches_metadata` compares (columns/types/nullability, PK, uniques, FKs, indexes; it does NOT compare CHECK constraints).
- Downgrade: first `SELECT COUNT(*) ... WHERE control_publication_id IS NOT NULL`; if `> 0` raises `RuntimeError` naming the count and states no destructive downgrade to 0024 is allowed. Only on an empty control-origin set does it rebuild back to the 0006/0024 two-origin shape (no `control_publication_id`, old CHECK). Sources are never dropped or converted silently.
- Parent-table stubs (`rule_sets`, `rule_components`, and `protocol_control_catalog_publications` only for the upgrade shape) mirror 0006's stub approach so FKs resolve without creating parent tables; downgrade uses a separate `MetaData` to avoid same-name stub conflicts (0006 precedent).
- Migration docstring records: column semantics, payload-only fields, rebuild rationale, FK-check, and the downgrade refusal contract.

## Artifacts And Evidence

| Artifact | State | Evidence |
|---|---|---|
| `app/storage/models.py` | Modified (pre-existing dirty state preserved) | `git diff` hunk `@@ -347,21 +394,34 @@ class EvidenceRequirementRecord`; my change only |
| `app/storage/migrations/versions/0025_control_evidence_origin.py` | New, untracked | `git status --porcelain` → `?? .../0025_control_evidence_origin.py` |

Static ORM↔migration cross-check (regex extraction from source, no imports):
- ORM explicit cols: `['rule_set_id','rule_set_revision','requirement_id','rule_component_id','procedure_catalog_item_id','control_publication_id','fact_type','due_stage']` + mixin `payload_json, payload_sha256, created_at` = 11.
- Migration three-origin table cols: identical 11, same order.
- Upgrade copy lists pair 11↔11 (`…, procedure_catalog_item_id, NULL, fact_type, due_stage, payload_json, payload_sha256, created_at`); downgrade copy 10↔10 (no undefined column referenced).
- `down_revision: 0024` matches `0024` file `revision: "0024"`; 0024 really creates `publication_id` PK.
- Head becomes 0025; tests resolve head dynamically (`resolve_head_revision()`), no hardcoded 0024 reference found in tests.

## Commands And Observations

1. `python3 -m py_compile app/storage/models.py app/storage/migrations/versions/0025_control_evidence_origin.py` → `PY_COMPILE_OK` (exit 0). Byproduct `__pycache__/` is gitignored (`.gitignore:10`), no unignored artifacts.
2. `git status --porcelain -- app/storage/models.py app/storage/migrations/versions` → ` M app/storage/models.py`, `?? 0023…`, `?? 0024…` (pre-existing), plus my `?? 0025…`.
3. `git diff --stat -- app/storage/models.py` → 180 insertions / 13 deletions total (mine ≈ +14/−2 of that; the rest predates this pass).
4. Read-only greps: no existing `control_publication_id` in `app/storage`; the only raw SQL against `evidence_requirements` is inside `0006`; `_save_requirement_row` (`repositories.py:1597-1626`) still writes only the two origin columns.
5. Observation (tooling): the delegated instruction said "manual edits use apply_patch". I used the CodeBuddy native `Edit`/`Write` patch tools (exact-string replacement, no shell `sed`), since this harness has no guaranteed `apply_patch` binary. Result is verifiable via the scoped `git diff` above; flagging for Codex in case literal `apply_patch` provenance is required.
6. Observation (import graph, unchanged behavior class): `models.py` now resolves an FK to a table owned by `control_catalog_models`. `app/storage/__init__.py:3-9` imports `control_catalog_models` before/with `models`, and the same cross-module pattern already exists (`evidence_locator_artifacts`), so mapper configuration under the normal package import path is unaffected. No import was executed in this pass.
7. Observation (cosmetic, inherited from 0006): because the temp table is named `evidence_requirements_new`, the generated CHECK name inside the rebuilt table may remain `ck_evidence_requirements_new_one_origin` after rename (SQLite CHECK-name rewrite behavior unverified; 0006 has the identical artifact). Startup verification does not compare CHECK names.

## Blockers Or Missing Environment

- None blocking. No environment or tool was missing; all in-scope tools (read/search/terminal/py_compile) worked.
- Explicitly forbidden by the assignment, therefore NOT the source of any failure: DB access, migration run, tests, imports.

## Rerun Requests Or Next Step

**Deferred by user instruction — NOT passed, NOT claimed as verified:**
- 0025 upgrade on a real DB (row preservation, payload hashes, `PRAGMA foreign_key_check`, child-table references from `evidence_expectations` etc.).
- Downgrade refusal with control-origin rows present, and clean downgrade when absent; upgrade→downgrade→upgrade roundtrip.
- `verify_schema_matches_metadata(engine, Base.metadata) == []` after 0025 (columns/FKs/index parity ORM↔rebuilt table).
- Runtime proof that the new three-origin CHECK rejects all four invalid origin combinations and accepts each single origin.

**Owner (Codex) residual work, outside my allowed scope — recorded for coordination:**
1. `repositories.py::_save_requirement_row` (≈line 1597) still enforces two-origin validation and never writes `control_publication_id`; control-origin requirements will raise `ScopeViolationError` there until the owner updates repository + publication/projection paths.
2. Any downgrade-below-0025 test that seeds control-origin rows will now fail by design (explicit refusal); tests must expect `RuntimeError` in that case.
3. Suggested owner check: an insert test asserting the CHECK rejects `rule_component_id` + `control_publication_id` and all-NULL triples (startup verification does not validate CHECKs).

**Precise questions for Codex:**
- Q1: Is the single-column FK (`control_publication_id → protocol_control_catalog_publications.publication_id`) the intended storage-level integrity, with source/control/node integrity checked in the repository against the immutable catalog + node mapping (as the assignment states), rather than a composite FK with rule-set scope?
- Q2: Is the potential cosmetic CHECK-name residue (`ck_evidence_requirements_new_one_origin`) acceptable for 0006 parity, or should a follow-up migration rename it?
