Trellis SessionStart ✓

Let me read the initial read set.

Now let me explore the existing conventions.

Now I have enough context. Writing the four new files.

The content-addressed id must be derived from *canonical* model JSON, but a caller's raw payload (e.g. `+00:00` vs `Z`) hashes differently. Fixing the contract so the identity is derived from the model's canonical body instead of being hand-computed by callers.

Contract checks pass. Let me verify the observed rejection messages are the intended Chinese ones, and re-read the repository file I wrote.

The project convention names unique constraints explicitly in both ORM and migration (e.g. `uq_prr_link_position`). Aligning.

# Execution Output: r05-control-catalog-storage-20260914 - worker_01

## Boundary And Context Check

- Route/session boundary: acknowledged. The packet branch was created under `off_peak`; this session was admitted after the Beijing `off_peak` boundary and was not previously started, so the current route `codebuddy/codebuddy-cli/deepseek-v4.1-flash` applies. I executed as that role only, with no rerouting, no conference, no peer review.
- Initial read set: read `context/r05-control-catalog-storage-20260914_execution_context.md` and `plans/codex_execution_r05-control-catalog-storage-20260914.md`.
- Did **not** read `/Users/smkzw/.codex/AGENTS.md` or `/Users/smkzw/.hermes/SOUL.md`. The worktree `AGENTS.md` and the CodeBuddy home `AGENTS.md` were pre-loaded by the harness (not read by me) and were treated as context, not as this role's instructions.
- Narrow extra reads (justified, all in-workspace): `.trellis/spec/backend/database-guidelines.md`, `error-handling.md`; `app/domain/contracts/protocol_controls.py` (catalog/control/relation/binding contracts), `rules.py` (RuleSet/WorkflowStage), `agents.py` (GateResult), `enums.py`, `common.py`, `publication.py` (`canonical_hash`); `app/storage/models.py` (mixin + RuleSet/WorkflowStage/GateResult/Job/JobCheckpoint), `repositories.py` (`_config`, `AppendRepository`, `_flush_guarded`, error classes, `get_rule_set`, `WORKFLOW_STAGE_CONFIG`, `GATE_RESULT_CONFIG`), `codecs.py`, `db.py`, `migrate.py` (`verify_schema_matches_metadata`), `review_context_repository.py`, `judgment_search_models.py`, `judgment_search_repository.py`, `migrations/versions/0022`, `0023`; `app/protocols/control_catalog_materialization.py` (`bind_control_workflow_stages` namespacing contract), `app/services/review_protocol_source.py`, `review_action_publication.py` (gate signing pattern).
- Allowlist respected: only the 4 authorized new files were created. No edits to `models.py`, `env.py`, `app/storage/__init__.py` registration, tests, or any other path. No test run, no DB read/write/migration, no `create_app`, no install, no network/model call. The worktree was already dirty (53 modified + many untracked owner files); I changed none of them.

## Work Performed

### 1. `app/domain/contracts/control_catalog_publication.py` (168 lines, new)

Public symbols: `ControlCatalogPublication`, `control_catalog_publication_id`, `CONTROL_CATALOG_PUBLICATION_ID_PREFIX = "control-publication:"`, `CONTROL_CATALOG_PUBLICATION_GATE_NAME = "protocol-control-catalog-publication-gate"`; private `_ControlCatalogPublicationBody`, `_require_utc`.

- `ControlCatalogPublication` is a frozen, `extra="forbid"` Pydantic `ContractModel` with `schema_version: Literal["control-catalog/v1"] = "control-catalog/v1"` and exactly the assigned fields: `publication_id`, `project_id`, `protocol_version_id`, `rule_set_id`, `rule_set_revision` (`ge=1`), `rule_set_sha256`, `source_job_id`, `source_job_payload_sha256`, `source_checkpoint_id`, `source_checkpoint_sha256`, `catalog` (existing `PublishedProtocolControlCatalog`), `workflow_stage_map: dict[str,str]`, `gate_result_id`, `created_at`.
- SHA256 fields use `pattern=r"^[0-9a-f]{64}$"` (rule set, job payload, checkpoint). `created_at` is validated UTC-aware (naive and non-zero offsets rejected, matching `_require_utc` in `review.py`/`facts.py`).
- Checks implemented: `protocol_version_id == catalog.protocol_version_id`; every catalog-referenced node maps — `review_node_bindings[].workflow_stage_id`, relation `left/right_target_id` where kind is `WORKFLOW_STAGE`, and `affected_workflow_stage_id`; each map value is exactly `f"{rule_set_id}:{rule_set_revision}:{source_id}"`; no blank IDs; no duplicate targets.
- `publication_id` is content-addressed `"control-publication:" + canonical_hash(model JSON excluding publication_id)`, full 64 hex. It is **derived**, not hand-written: the `mode="before"` validator normalizes the body through `_ControlCatalogPublicationBody`, dumps canonical JSON, derives the id, and rejects any caller-supplied id that differs. No clinical evaluation, no catalog rewriting, no RuleSet mutation, no import of this model into `rules.py`.
- Decision made and worth Codex confirmation (see Rerun Requests): a caller-computed id from a raw payload is *not* stable (`"+00:00"` vs `"Z"`, enum objects vs values, model instances vs dicts). My first implementation (caller-supplied id compared against the canonical dump) failed exactly that way in the in-memory check, which is a trap for the owner's publication service. I therefore made the model derive the identity from its own canonical JSON; a supplied id is still verified, never trusted.

### 2. `app/storage/control_catalog_models.py` (69 lines, new)

`ProtocolControlCatalogRecord(AppendedRecordMixin, Base)` → table `protocol_control_catalog_publications`: `publication_id` PK; mirror columns `project_id` (FK `projects`), `protocol_version_id` (FK `protocol_document_versions`), `rule_set_id`, `rule_set_revision`, `catalog_id`, `source_job_id` (FK `jobs`), `source_checkpoint_id` (FK `job_checkpoints`), `gate_result_id` (FK `gate_results`); plus mixin `payload_json`/`payload_sha256`/`created_at`. Constraints: `UniqueConstraint("rule_set_id","rule_set_revision", name="uq_pccp_rule_set_revision")` and composite `ForeignKeyConstraint((rule_set_id, rule_set_revision) → rule_sets(rule_set_id, revision))`. Table and column names match the real existing parents.

### 3. `app/storage/control_catalog_repository.py` (216 lines, new)

`ControlCatalogPublicationRepository(session)` with `save(publication)`, `get(publication_id)`, `get_for_rule_set(rule_set_id, rule_set_revision) -> publication | None`; private `_verify_persisted_basis`, `_verify_workflow_stages`, `_verify_gate`; module config `_CONTROL_CATALOG_PUBLICATION_CONFIG = _config(...)` (AppendRepository + mirrors + `created_at_key="created_at"`), so serialization, payload-hash verification and column/payload mirror cross-checks are the existing ones.

- `get`/`save` both run `_verify_persisted_basis`: persisted `RuleSet` loaded via `get_rule_set` (hash + mirror verified) and compared to `publication.rule_set_sha256` via `canonical_hash`; `rule_set.protocol_version_id`/`study_phase` matched to publication/catalog. Mapped `WorkflowStageRecord` rows are batch-loaded (one SELECT), decoded and mirror-checked through `WORKFLOW_STAGE_CONFIG`, then checked for `protocol_version_id` scope, optional `study_phase` scope, payload id == map target, and `stage == binding.review_stage` for every catalog-bound source node (conflicting stages for one node are rejected). `GateResult` must be `ACCEPTED`, named `CONTROL_CATALOG_PUBLICATION_GATE_NAME`, contain `publication_id` in `accepted_entity_refs`, contain `source_job_id` and `source_checkpoint_id` in `input_entity_refs`, and have `output_hash == canonical_hash(publication.model_dump(mode="json"))`.
- Idempotency/immutability: same `publication_id` + same content returns the stored row; same id with different content raises `DuplicateRecordError`; a second catalog for the same `(rule_set_id, rule_set_revision)` raises `DuplicateRecordError` before any insert (DB unique constraint is the backstop). No update, no commit — only `AppendRepository`'s `_flush_guarded`; transaction ownership stays with the caller.
- Uses only existing exception classes (`DuplicateRecordError`, `ScopeViolationError`, `InvalidReferenceError`, `NotFoundError` from `AppendRepository.get`). No schema auto-create, no raw DB file access, no job/checkpoint content verification (explicitly the owner service's duty, per the assigned boundary).

### 4. `app/storage/migrations/versions/0024_protocol_control_catalogs.py` (73 lines, new)

`revision="0024"`, `down_revision="0023"`; `upgrade()` creates the table with the same columns/types/nullability, PK, `uq_pccp_rule_set_revision`, and 6 FKs as the ORM; writes no rows and does not read or rewrite existing protocol/rule/job/checkpoint/gate rows. `downgrade()` raises `RuntimeError` when the table is non-empty, otherwise drops the table. No migration was executed.

## Artifacts And Evidence

| Artifact | Status | Evidence |
|---|---|---|
| `app/domain/contracts/control_catalog_publication.py` | new, 168 lines | `git status --porcelain` shows `??`; py_compile + import OK |
| `app/storage/control_catalog_models.py` | new, 69 lines | same; table dumped from live metadata |
| `app/storage/control_catalog_repository.py` | new, 216 lines | same; import OK, config resolves `ControlCatalogPublication` |
| `app/storage/migrations/versions/0024_protocol_control_catalogs.py` | new, 73 lines | py_compile OK; `0024`/`0023` strings verified |

Static ORM-vs-migration equivalence (dumped from `ProtocolControlCatalogRecord.__table__`, SQLite dialect): columns `VARCHAR(128)×8 / INTEGER / TEXT / VARCHAR(64) / DATETIME`, all `nullable=False`, PK `publication_id`; UQ name `uq_pccp_rule_set_revision` over `(rule_set_id, rule_set_revision)`; FKs `project_id→projects.project_id`, `protocol_version_id→protocol_document_versions.protocol_version_id`, `(rule_set_id, rule_set_revision)→rule_sets.(rule_set_id, revision)`, `source_job_id→jobs.job_id`, `source_checkpoint_id→job_checkpoints.checkpoint_id`, `gate_result_id→gate_results.gate_result_id`; indexes `{}`. All match `0024`'s `op.create_table` declaration line-for-line — which matters because `verify_schema_matches_metadata` compares columns/types/nullability, PK, unique column-sets, FK tuples and index names at startup.

## Commands And Observations

All commands from the worktree root; no DB file was read, created, or migrated (`data_v2/` listing identical before and after).

1. `.venv/bin/python -V` → `Python 3.12.13` (system `python3` lacks alembic; the repo venv is required, consistent with prior notes).
2. `.venv/bin/python -m py_compile <4 files>` → `PY_COMPILE_OK`.
3. `.venv/bin/python -c "import ..."` (contract, models, repository) → `IMPORT_OK`; `GATE protocol-control-catalog-publication-gate`; `PREFIX control-publication:`; `TABLE protocol_control_catalog_publications`; `CONFIG ControlCatalogPublication`; `data_v2` unchanged.
4. In-memory contract checks (stdlib heredoc via stdin, no files written, no DB): happy path builds a publication and derives `control-publication:a891a003df406f…`; identity stable across `created_at` given as UTC object, `"+00:00"` string and `"Z"` string, and across `catalog` given as model instance vs JSON dict; `publication_id` computed from the canonical dump equals the model's. Rejected as intended: wrong map target, unmapped binding node, duplicate map target, `protocol_version_id` ≠ catalog, malformed SHA256, unknown extra field, naive `created_at`, `+08:00` `created_at`, tampered `publication_id`, mutation of the frozen model (`ValidationError`), and relation `right_target_id`/`affected_workflow_stage_id` nodes not in the map. Error text is the intended Chinese message labelled `ControlCatalogPublication` (no private class name leaks).
5. ORM shape dump (command 4 of the static comparison above) → see Artifacts.
6. AST unused-import scan on the 4 files → clean after removing an unused `PAYLOAD_SHA_LEN` import from the models module.
7. `git status --porcelain -- app` → only the 4 allowlisted paths added by me; `reviews/codex_execution_r05-control-catalog-storage-20260914_review.md` is still the untouched template (Codex's file, not mine to write).

## Blockers Or Missing Environment

No blockers. No missing tooling (venv + uv present). Two limits were self-imposed by this packet, not environmental failures:

- No runtime repository/migration verification is possible under this packet: exercising `save`/`get`, `op.create_table` or `verify_schema_matches_metadata` requires DB initialization or migration execution, which the packet forbids. Verification here is py_compile + import + in-memory contract validation + static ORM/migration comparison.
- The repository's SQL statements (`select(...).where(...)`, `payload_get("catalog.catalog_id")`) were not executed against real rows; their correctness rests on the shared `AppendRepository`/`_config`/`check_column_mirrors` machinery and on the same dot-path mirror pattern already used by `PROTOCOL_DOC_CONFIG`.

## Rerun Requests Or Next Step

Unresolved integration requirements for Codex / the owner (codex-inline, per this packet's split — my write allowlist excludes these files):

1. **Register the ORM.** Add `control_catalog_models` to the import-for-registration list in `app/storage/__init__.py`. Without it, the migration-created table is absent from `Base.metadata` and `verify_schema_matches_metadata` will report `存在未映射的表 protocol_control_catalog_publications` and block startup.
2. **`rule_set_sha256`** must be `canonical_hash(rule_set.model_dump(mode="json"))` (identical to the persisted `rule_sets.payload_sha256`). Any other derivation will be rejected by `_verify_persisted_basis`.
3. **Gate signing recipe (ordering matters).** `publication_id` is derived from content that contains `gate_result_id`, so the gate id must be chosen without depending on publication content (e.g. `f"gate:control-publication:{rule_set_id}:{rule_set_revision}"`). Then: build the publication body with that gate id (the model derives `publication_id` — do not hand-compute), build `GateResult` with `gate_name=CONTROL_CATALOG_PUBLICATION_GATE_NAME`, `result=ACCEPTED`, `accepted_entity_refs` containing `publication_id`, `input_entity_refs` containing `source_job_id` and `source_checkpoint_id`, `output_hash=canonical_hash(publication.model_dump(mode="json"))`, non-empty `affected_scope`/`recompute_scope` and an `idempotency_key`, save the gate first, then `repository.save(publication)`.
4. **Owner-side provenance.** The repository deliberately does not verify job payload, checkpoint content or catalog source closure; the publication service must prove `source_job_payload_sha256`, `source_checkpoint_sha256` and the catalog's source/spans before signing the gate.
5. **`workflow_stage_map` provenance.** Pass the output of `bind_control_workflow_stages` (full published node set, per-field content identity). Storage re-checks namespace, scope and bound `review_stage` only — relation-only workflow nodes carry no `review_stage` in the catalog, so full content identity for those remains the publisher's proof.
6. **Migration head is now `0024`** (`down_revision="0023"`); update anything asserting the head, and run the real migration plus startup verification in the owner pass (not run here).
7. **Confirm one design decision** (recommendation, not a blocker): `publication_id` is derived inside the model from the canonical body rather than accepted from the caller, because a caller-side pre-image hashing (`"+00:00"` vs `"Z"`, model vs dict, enum vs value) silently produces a different id — the first implementation failed exactly this way. If Codex instead wants a strict caller-supplied id, that is a one-validator change, but the owner service would then have to pass an already-canonical body.
8. Deferred by design: no tests were added or run, no stage/system/clinical acceptance is claimed, and this does not complete R05 — the materializer/publication service, gate issuance, `ClausePack`/expectation consumption and whole-system validation remain with the owner.
