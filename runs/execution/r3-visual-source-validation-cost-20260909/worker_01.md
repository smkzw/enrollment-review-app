# Execution Output: r3-visual-source-validation-cost-20260909 - worker_01

## Boundary And Context Check
- Work confined to runner CWD; edited only authorized paths: `app/storage/page_review_visual_locator_validation.py`, `app/storage/evidence_locator_repositories.py`, `app/services/page_review_visual_sources.py` (usage only), new `tests/v2/storage/test_page_review_visual_locator_batch.py`. No model transport/prompt/config/schema/frontend changes; no new dependencies; no network/model calls. All three source files were already untracked phase-work in this dirty tree; unrelated changes untouched.
- Read contract files plus direct callers (`fact_evidence_closure.py` gates, `fact_authority.py`, `fact_normalization_source_adapter.py`, `fact_normalization_job_service.py`), `.trellis/spec/backend/quality-guidelines.md` (batch-read rule + constant-query test rule directly support this design), and test fixtures only. No clinical raw files inspected.
- Report returned inline; runner persists to `runs/execution/r3-visual-source-validation-cost-20260909/worker_01.md`. No clinical/regulatory acceptance claimed; Codex owns final review and real-source timing.

## Work Performed
Problem: `verify_visual_locator` ran a full `CompleteEvidenceProcessingRevisionRepository.get` (entire §4.6 closure: scope/page/terminal/metadata/risk/locator/docs/manifest/candidate checks) plus a full `page_association_sources` rebuild (all pages' OCR + corrections) for EVERY visual locator. Repetition multiplies across `EvidenceLocatorRepository.create/get/get_many`, gates `validate_locator_and_text_hash` per candidate, and `persist_visual_locators` per locator.
Decision: explicit bounded `VisualLocatorBatchContext` (single-session, no globals) that verifies the revision fully once, then reuses it after cheap DB-bound fingerprint checks; per-locator inputs (cycle probe, coverage, reconciliation, reviews, this page's OCR/correction projection) are always read fresh and the exact-artifact comparison is unchanged.
- `page_review_visual_locator_validation.py`: added `VisualLocatorBatchContext` + `_load_verification_inputs` / `_materialize_and_compare` shared by batched and legacy paths; `verify_visual_locator(..., batch=None)` and `verify_visual_locator_authority(..., batch=None)` keep byte-identical legacy behavior when `batch` is omitted. Reuse fingerprints: revision-root `payload_sha256`, raw page-manifest rows `(position, page_artifact_id, ocr_page_id, doc_version, page_number)`, ordered correction membership, plus fresh single-page OCR+correction reprojection vs cached `text_sha256`. Any drift evicts and reruns the full path (fail-closed); cross-session use raises `InvalidReferenceError`.
- `evidence_locator_repositories.py`: `_verify_source/create/get/get_or_none` accept keyword-only `batch`; `get_many` builds an internal context for its loop when none is passed (single-get default behavior unchanged to avoid adding fingerprint overhead to one-shot calls).
- `page_review_visual_sources.py`: `persist_visual_locators` shares one context across its create/get loop (only change in that file).
- Tests: 11 regression tests covering result equivalence (incl. authority check), rebuild-count reduction (revision-get K→1, association-build K→1, `Session.get` strictly fewer), `get_many` batching, persist batching, tampered-locator rejection pre/post reuse, source/reconciliation/coverage mutation rejection after reuse, cycle rejection, foreign-session rejection, cross-session committed-mutation rejection, post-rejection context health.

## Artifacts And Evidence
- New tests: `tests/v2/storage/test_page_review_visual_locator_batch.py` — 11 passed.
- Existing affected suites: `test_page_review_visual_sources.py` + `test_page_review_visual_locators.py` + `test_page_review_repository.py` + `test_r3_page_review_normalizer_wiring.py` — 41 passed; `test_slice44_repositories.py` + `test_fact_normalization_source_adapter.py` — 103 passed.
- Measured on 4-locator single-page fixture: unbatched 4 revision-closure verifications + 4 full association builds → batched 1 + 1 with identical coverage results. Persist path: rebuild contributes 2 revision gets (authority validation + source rebuild, out of authorized scope), locator loop contributes 1 (was 4).
- Key evidence from trace: `rebuild_visual_sources` itself issues 2 revision gets per call (`FactAuthorityValidator._validate_complete_revision` + `_rebuild_visual_sources`) — the remaining per-call repetition across the 14 finalize calls lives in non-authorized files (gates/authority/adapter) and is NOT fixed here.

## Commands And Observations
- `.venv/bin/python -m py_compile` on the 3 edited modules: OK.
- `.venv/bin/python -m pytest tests/v2/storage/test_page_review_visual_locator_batch.py -q`: 11 passed.
- Affected suites as above: 41 + 103 passed. No DB writes to artifacts (test chains use unique prefixes; suite's own transactional fixtures).
- Notable behavior (parity, not regression): OCR-text mutation surfaces as `PersistedContractInvalid` from the OCR mirror check in both batched and legacy paths (identical error either way); tests accept `(InvalidReferenceError, PersistedContractInvalid)`.
- Two self-inflicted edit-range mistakes during the pass (truncated `_verify_source` body; misplaced test hunks) were detected via immediate compile/test failures and repaired; final files compile and all tests pass. Throwaway trace test created and removed.

## Blockers Or Missing Environment
- None. `.venv/bin/python` present as required.

## Rerun Requests Or Next Step
- Codex should: (1) run fresh real-source read-only timing to confirm finalize improvement; (2) decide whether to extend the batch context into the non-authorized repetition points (`validate_locator_and_text_hash` direct `verify_visual_locator` call per visual candidate, `FactAuthorityValidator.validate_locators`, per-call `rebuild_visual_sources` in `_build_input`) — these need Codex authorization to edit gates/authority/adapter files; the context API already supports it (`batch=` kwarg threads through `verify_visual_locator_authority` and repository methods).
- Residual risk: cache reuses the verified revision contract within one session; cross-page row mutations that don't touch root/manifest/corrections/this-page-source are not re-verified on reuse — by construction they cannot alter this locator's materialization inputs, but Codex may want a second pair of eyes on that argument before acceptance.
