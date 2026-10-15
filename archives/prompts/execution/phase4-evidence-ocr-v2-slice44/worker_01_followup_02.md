Active task: `.trellis/tasks/08-19-phase4-evidence-ocr-v2`

# WP-44A Same-Session Repair Pass 2 (Final Recovery Pass)

Codex and a second fresh-context independent verifier both **REJECTED** repair pass 1. Resume the existing worker session `01a01a89-6f64-7000-a9bd-277ae3b884a3`; do not start over, do not fall back, and do not start WP-44B. This is the final allowed same-session recovery pass for WP-44A.

## Hard boundaries

- Keep the original WP-44A write surface only: `app/domain/contracts/`, `app/storage/`, `app/evidence/` only where a deterministic artifact decoder/proof helper is directly required, `tests/v2/domain/`, `tests/v2/storage/`, and directly required evidence contract tests.
- Do not modify services, API, frontend, launch scripts, clinical source material, legacy projects, or accepted Phase 4.1-4.3 semantics.
- Do not read other worker reports. The frozen source is `research/slice44-detailed-contract-review.md`, especially sections 4.1-4.6 and 8.
- A green existing suite is not acceptance: the verifier reproduced real counterexamples that current tests missed.
- Never weaken a gate to make a fixture pass. Unsupported proof routes must reject or honestly degrade; they must not persist authenticated bbox or an activatable complete revision.
- Runner-managed report path: `runs/execution/phase4-evidence-ocr-v2-slice44/worker_01_followup_02.md`. Return the report in the final response; do not write it with tools.

## Initial read set

- `AGENTS.md`
- `context/phase4-evidence-ocr-v2-slice44_execution_context.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/research/slice44-detailed-contract-review.md`
- Current WP-44A contracts, repositories, migration 0010, focused tests, and directly required existing Phase 4.1-4.3 dependencies.
- Additional in-workspace files may be read only when needed to prove one of the listed invariants.

## Blocking Reproductions And Root Causes

### 1. Complete page closure counts documents, not actual pages

The verifier reproduced a `SourceDocumentVersion.page_count=2` snapshot whose base/complete manifest contains only page 1; the current repository persisted it with `is_activatable=True`. Validate the exact expected page/frame set for every active snapshot member against source document `page_count` and persisted PageArtifact/base-manifest rows. Reject missing, extra, duplicate, failed, degraded-as-success, wrong-frame, wrong-document, wrong-page, or non-terminal OCR rows. Validate complete/base/snapshot/episode project, subject, review episode and study-phase scope, not only episode ID and document ID sets. Add a negative test with page_count=2 and only one manifest page; repair any positive fixture that accidentally encodes this defect.

### 2. Range-less locator identity collides

`page_excerpt` and `page_only` currently both use NULL ranges and collide on the same page/layer/algorithm. Freeze occurrence identity as the contract states:

- bbox/text_range: trusted source range plus page/layer/source hash/algorithm and the required sidecar/proof identity;
- page_excerpt: a replayable excerpt/context anchor hash and disambiguation outcome, not NULL range alone;
- page_only/not-found: stable target identity plus degradation/disambiguation proof, so distinct targets do not collide while exact aliases of the same locator request do.

Add tests for distinct excerpts, distinct page-only targets, exact alias collision, and list/dictionary order independence.

### 3. Locator authenticity is still self-asserted

The verifier proved arbitrary native/effective hashes can be persisted as text_range, and the bbox positive test only compares arbitrary 64-character strings. Enforce source proof from content-addressed artifacts:

- raw OCR text_range/bbox must re-read the immutable `OCRPage.raw_text`, hash it, and verify the exact range/excerpt. Current accepted OCR route has no persisted machine-coordinate sidecar; therefore raw bbox is unsupported and must reject/degrade until a real schema + bytes exist.
- native text must read `ArtifactStore` `native_text/<sha>` bytes, verify content hash/UTF-8 text/range/excerpt. Native bbox must additionally read and parse the real `native_coordinates/<sha>` payload, verify schema/page/text/hash/frame/rotation/transform and character-range mapping, and deterministically recompute the target bbox; arbitrary sidecar hash plus arbitrary bbox must fail.
- effective text text_range must be reconstructed from the bound complete revision's raw OCR plus selected effective correction set and its hash rechecked. If WP-44A cannot prove this without the WP-44B projection engine, reject effective-text persistence for now rather than accepting arbitrary hashes. Effective bbox remains rejected until a same-source coordinate projection is actually implemented.
- complete revision closure must call the locator repository proof path again, not trust mirror columns.

Use the existing content-addressed `ArtifactStore` and deterministic native-coordinate schema; inject a required proof reader/store where needed. Do not introduce filesystem absolute paths into contracts. Add artifact-byte tamper/missing-artifact/wrong-text/wrong-range/wrong-bbox tests. The accepted text-only OCR route must never produce a red-box-capable artifact.

### 4. Risk/review/correction closure trusts mirror rows and wrong bases

The verifier changed a blocking flag mirror column to informational and the complete revision then froze without review. It also selected a correction based on another base revision. Fix all paths:

- Complete closure must decode and hash-check every selected scan, flag, review and correction through their owning repositories, including scan/flag child-table mirrors and raw OCR anchoring.
- Every selected review/correction must have `base_processing_revision_id == complete.base_processing_revision_id`, and the anchored OCR page must be present in that exact base manifest, not merely share an episode.
- Creating a review/correction must likewise prove the OCR page belongs to the named base manifest and scope.
- A superseding correction must use the same base and must supersede the current chain head; prevent branching or skipping the latest head.
- A complete revision may select at most one valid review per selected flag and one effective correction per raw range. Reject duplicate decisions, stale predecessor selection, cross-base selection and all overlaps.
- A correction resolving a blocking flag must be selected, confirmed when required, based on the exact base, and cover the exact raw range on the same OCR page/hash.

Add persisted-payload/mirror tamper tests, cross-base page-membership tests, duplicate review tests, stale/branched chain tests and the reproduced blocking-to-informational bypass.

### 5. Referenced-document closure allows missing resolution and branched chains

For every selected logical referenced document, freeze exactly one selected current registration revision and exactly one selected current resolution revision. Require both to be the unique chain heads; predecessor, branch, skipped-head and two-head selections reject. A confirmed entry requires a selected, replayable trigger locator inside the same complete closure. A provided resolution must refer to a same-scope snapshot member; unresolved carries no document. Reject extra resolution chains not represented in selected registrations. Add the reproduced `confirmed + no resolution` failure, branch creation, stale-head selection, duplicate logical revision/resolution and cross-scope tests.

### 6. Metadata and child reference closure is not exact

Reject extra metadata revisions for non-member documents, stale/non-head metadata revisions, duplicate metadata for one document, and any child reference whose payload/hash or mirror columns drift. Complete revision readback must re-run full closure and association ordering validation. A failed create must leave no root/page/association rows in the session; test atomic no-partial persistence after flush/exception.

### 7. `completion_manifest_sha256` hashes IDs, not child canonical payload hashes

The frozen contract 4.1.5/4.6.8 requires the base, page rows and every ordered child reference **and its canonical payload hash**. Current `completion_manifest_hash()` only hashes IDs and selected page fields. Redesign the deterministic hash inputs so repository construction/readback includes:

- base revision ID + canonical payload hash;
- ordered page entry ID + canonical payload hash;
- each ordered locator/scan/review/correction/metadata/referenced-document/resolution ID + canonical payload hash.

Avoid circularly hashing the complete root payload itself. The domain contract may validate shape/format while the repository computes and verifies DB-bound material. A child payload change with an unchanged ID must invalidate readback/activation. Add order-sensitivity and child-payload-hash-drift tests for every association family.

### 8. SQL invariants are too weak

Update both ORM metadata and migration 0010 so schema parity remains exact and SQLite enforces what is locally expressible:

- `revision_kind IN ('base','complete')`;
- base rows: `is_activatable=0`, no base pointer, no completion hash;
- complete rows: `is_activatable=1`, non-null base pointer and completion hash;
- risk review/correction base-processing FK is NOT NULL;
- preserve paired episode pointer CHECK/FKs and append-only tables.

If SQLite cannot enforce a cross-table invariant, retain repository validation and document that precise boundary; do not omit local CHECK/NOT NULL constraints. Upgrade from exact 0009 must still preserve legacy payload/hash/page rows byte-for-byte and project them as valid base rows. Empty 0010 downgrade/re-upgrade must work; any 0010 history must refuse downgrade.

### 9. Correct stale documentation and test quality

- Remove the stale repository docstring saying full gates are not evaluated in WP-44A.
- Replace same-implementation bbox fixtures with real content-addressed native text/coordinate bytes and a bbox recomputed from their character mapping.
- Keep the frozen composite sentence byte/hash unchanged through risk scanning.
- Do not report `is_activatable=True` unless every 4.6 gate is actually proven.

## Verification

Run and report exact outcomes for:

1. all WP-44A domain/storage tests, including every new counterexample;
2. migrations 0008, 0008a, 0009, 0010, schema parity, upgrade/downgrade, WAL/FK/integrity and byte-identical legacy payload/hash checks;
3. full `tests/v2`;
4. Ruff on changed Python, production Pyright with the project venv, and `git diff --check`.

Return a compact execution report naming changed files, each reproduced bypass and its prevention, test counts and residual uncertainty. Do not self-accept and do not release WP-44B.
