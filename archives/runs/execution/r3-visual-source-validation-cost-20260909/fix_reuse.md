# Execution Output: r3-visual-source-validation-cost-20260909 - worker_01

## Boundary And Context Check

- Worked only inside the runner-provided worktree (`.`); no production paths touched.
- Edits stayed within the authorized set: `app/domain/gates/fact_evidence_closure.py` (batch threading; Codex-authorized via "same verified batch context" wiring), `app/storage/fact_authority.py` (batch routing), `app/storage/page_review_visual_locator_validation.py` + `tests/v2/storage/test_page_review_visual_locator_batch.py` (both untracked new files already present in the dirty worktree — extended, not created). No model transport, prompt, runtime config, clinical schema, or frontend changes. No new dependencies. No network/model calls. Pre-existing worktree dirt (315 files) preserved untouched.
- Final acceptance, real-source timing, rendered/clinical review: left to Codex per boundaries.

## Work Performed

**Problem.** `verify_visual_locator` ran the full complete-revision closure (`CompleteEvidenceProcessingRevisionRepository.get`, ~22K `Session.get`) plus a full `page_association_sources` rebuild for *every* visual locator in a transaction. Evidence: isolated runtime05 task `ecf027d8` spent 55m45s on finalize alone.

**Decision.** Explicit bounded batch context (`VisualLocatorBatchContext`, single-session, no globals) reusing only the two revision-wide inputs (verified revision contract + full page-association map). Per-locator fidelity (binding, cycle probe, coverage entry, reconciliation, materialize-and-compare against the artifact) still runs fresh every call. Reuse is guarded by an opaque DB-generation token `(open txn identity, DBAPI connection identity, SQLite data_version, total_changes)` plus clean ORM state (`new/dirty/deleted` empty) and SQLite backend; anything else — writes, commit/rollback, nested rollback, cross-connection commits, pending state, non-SQLite, introspection failure — evicts and full-verifies. Failed verifications never leave entries behind.

**This pass (rework of review findings):**
1. Replaced content fingerprints with the generation-token guard (exact artifact equality stays inside the full-verify path; no hash-equality shortcut).
2. Threaded `visual_batch` through all gates paths: `batch_gate_evidence_closure` (creates one context per batch call), `gate_evidence_closure_for_candidate`, `validate_locator_and_text_hash`, `validate_blocking_ocr_for_candidate`, `_fetch_cached`/`derive/resolve/validate_source_strength*`, `EvidenceLocatorRepository.get/get_many(batch=...)`.
3. `FactAuthorityValidator.validate_locators` now verifies all ids through one shared `VisualLocatorBatchContext`; `_validate_locator` accepts and forwards it.
4. Added 6 regression tests (all in `tests/v2/storage/test_page_review_visual_locator_batch.py`): metadata-child drift rejection + eviction, same-session raw-SQL UPDATE + commit invalidation, nested-rollback forces full re-verification (count 1→2), non-SQLite backend falls back with identical results and no caching, authority shares one revision check across ids, gates batch shares one revision check across candidates with outcome/reason equivalence.
5. Repaired two defects I introduced: (a) an eaten `elif basis.asserted_object not in source:` + misindentation in `_validate_assertion_text_closure` (caught by gates suite, all 41 pass after restore); (b) missing `SourceDocumentMetadataRevisionRepository` import in `batch_gate_evidence_closure` (NameError broke product-job finalize; fixed with function-local import per file convention).

## Artifacts And Evidence

- Modified (tracked): `app/domain/gates/fact_evidence_closure.py`, `app/storage/fact_authority.py`.
- Extended (untracked, pre-existing in worktree): `app/storage/page_review_visual_locator_validation.py`, `tests/v2/storage/test_page_review_visual_locator_batch.py` (11→17 tests).
- Verification, all green:
  - `test_page_review_visual_locator_batch.py`: **17 passed** (incl. tamper/source/recon/coverage/cycle/foreign-session/x-session tests from prior pass).
  - `test_page_review_visual_sources.py` + `test_fact_evidence_closure.py`: **46 passed** (includes `test_visual_fact_publishes_through_product_job` end-to-end through finalize gates).
  - `test_r3_page_review_normalizer_wiring.py` + `test_fact_repositories.py`: **59 passed**.
- Count reduction pinned: N unbatched verifies → N revision gets + N association builds; batched → 1 + 1 (`test_batch_rebuilds_shared_revision_once`, gates/authority equivalents).

## Commands And Observations

- `.venv/bin/python -m pytest tests/v2/storage/test_page_review_visual_locator_batch.py -q` → 17 passed (~35s).
- Same for the two suite pairs above (60s / 156s / 140s). Full-suite run explicitly out of scope; not run.
- Intermediate failures and their meaning: `assert 6 == 2` (complete-repo `get` recurses into history verification — asserts made relational/direct instead of assuming 1 get per candidate); `Can't operate on closed transaction` (manual `commit()` inside `session.begin()` block — test restructured into sequential explicit transactions); `NameError` import (fixed, see above).
- `git diff --stat` shows 315 dirty files (pre-existing); my tracked footprint is only the two files above. `evidence_locator_repositories.py` shows `M` but I never edited it — pre-existing dirt.

## Blockers Or Missing Environment

- None. `.venv/bin/python` present; no installs performed.

## Rerun Requests Or Next Step

- No rerun needed for the assigned item. Remaining verification is Codex-owned: fresh real-source read-only timing on the finalize path, and final clinical/regulatory acceptance.
- Known limitations (reported, not claimed): (1) same-session Core DML with `synchronize_session=False` and no commit/expire leaves stale identity-map state that even the *unbatched* path reads — batch is never weaker than fresh verification, but not omniscient; (2) non-SQLite backends always full-verify (no caching); (3) cross-process concurrent writers on the same DB file are caught via `data_version` only at the next call boundary, same as any read-committed check — no locking added by design.
- Suggested Codex check: real-source finalize timing comparison pre/post, and confirming no other caller constructs `VisualLocatorBatchContext` with a wrong session (only gates batch, authority, `persist_visual_locators`, and `EvidenceLocatorRepository.get_many` do).
