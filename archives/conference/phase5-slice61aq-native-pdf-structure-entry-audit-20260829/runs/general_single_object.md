Trellis SessionStart ✓

I'll begin by reading the initial read set, then audit the codebase for the Phase 5.8d native text PDF entry.

The context/plan are mostly stubs. The substance lives in the linked execution task and the codebase. Let me orient.

Bash is not available in this read-only mode. I'll use Glob/Grep/Read only.

Found the key artifacts. Let me read the execution task context, plan, review, and metrics.

Now let me read the actual implementation files to independently verify the claims.

Now the evidence-layer primitive and the modified DOCX structure module.

The `pdf_native.py` docstring claims y-up (origin bottom-left) coordinates — critical to verify against what pdfplumber actually returns. Let me check the tests, coordinates frame, and pdfplumber's actual convention.

The coordinate convention is confirmed as y-up (PDF points) — consistent with tests. Now the modified DOCX structure module — critical for the D001 fingerprint question.

`serialize_blocks` pops None for the 4 new fields — DOCX byte-identity preserved. Now let me find the 120-page MG-K10-SAR verification evidence and read the executor integration.

The `7843e5e5...` hash appears only in Codex's review — I need to find the underlying run evidence. Let me check the worker_03 execution log.

No persisted evidence for the 120-page run — only the Codex review line. Let me now read the persistent test file and the executor integration.

Tests assert alignment precision `bbox` and identical-text pages align without collision — suggesting a native-PDF fast path in `align_blocks`. Let me read `source_alignment.py`.

The native-PDF alignment fast path is honest (exact substring verification, fail-closed otherwise). Now the executor and workbench integration.

Let me check the frontend upload boundary and the phase5 PRD requirements on frozen serialization.

Let me verify the span contract fields (bbox, precision BBOX) and then check the `ingestion.py` hash/compute functions used for identity.

Let me check the redo-select panel and the `ingestion.py` detect_format/register functions briefly.

Let me verify the replay pack determinism mechanics (created_at handling and fingerprint composition).

Let me check the phase5 design/implement docs for the PDF-entry acceptance framing.

I have completed a thorough read-only audit. Let me consolidate my findings into the plan file, then present the full report.

# Conference Participant Output: phase5-slice61aq-native-pdf-structure-entry-audit-20260829 - general_single_object

## Boundary Check

- Work confined to the worktree (`phase5-clinical-facts-profile`); read-only. No files created/modified except the plan file. No clinical models run, no control points published, no other participant outputs read (I deliberately did not read `reviews/codex_conference_phase5-slice61aq-..._review.md`).
- Read set honored: conference context + main-venue plan (both mostly TODO stubs — the substance lives in the execution task artifacts), then: execution context/plan, worker_01/02/03 reports, `app/protocols/pdf_structure.py`, `structure_dispatch.py`, `docx_structure.py`, `source_alignment.py`, `protocol_replay_harness.py`, `app/evidence/pdf_native.py`, `coordinates.py`, executor, workbench service, contracts, frontend panels, `tests/v2/protocols/test_pdf_structure_entry.py`, `tests/v2/evidence/test_pdf_native_coordinates.py`, `test_protocol_replay_harness.py`, metrics, execution log.
- Bash denied in this session (read-only mode); all verification is code-level inspection + repo grep. Where a claim depends on running tests, I say so explicitly.

## Independent Work Product

### Objective 1 — 原始 PDF 字节与来源哈希身份是否保持: **YES (entry level)**

- `pdf_structure.py:275-281` re-computes SHA-256 and compares against `source_artifact.sha256`; mismatch → `PdfHashMismatchError` before any parse/blob write (test `test_pdf_hash_mismatch_fails_before_structure_write`, `test_pdf_structure_entry.py:192-209`).
- Executor render step (`protocol_deconstruction_executor.py:350-375`): PDF → **identity render** — `page_texts` from `extract_native_pages(source_path)`, `pdf_sha256 = artifact.sha256`, `render_kind="source_pdf_identity"`, no `render_to_pdf` call; the DOCX branch is untouched (`:376-402`).
- `test_native_pdf_blocks_carry_exact_page_ranges_and_bboxes` (`:60-91`) asserts source bytes **and** `st_mtime_ns` unchanged after extraction. Blob persistence is content-addressed + atomic + post-write hash-verified (`docx_structure.py:947-975`).
- **Caveat (non-blocking):** the identity render exists only as checkpoint fields. `ProtocolRenderArtifact(` is constructed solely in the LibreOffice path (`rendering.py:258`). No domain render-artifact manifest (with `storage_ref` → source blob) is built for PDF inputs. Contract-level "identity render artifact" (worker_01 N6) is therefore only partially realized.

### Objective 2 — 页码/文本区间/坐标框可验证且不伪精确: **YES (entry level)**

- `source_alignment.py:837-867` native fast path: for PDF blocks, re-verifies `page_texts[page_index][text_start:text_end] == block.text` **exactly**; on any mismatch → `UNALIGNED` with reason "拒绝伪造精确定位". No text-guessing fallback. `render_page = page_index + 1` = physical original PDF page.
- bbox = union of real pdfplumber char boxes (`pdf_structure.py:175-193`); degenerate boxes → `bbox=None` → precision falls back `TEXT_RANGE` (`:861-865`); `BoundingBox` validator rejects inverted boxes (`evidence.py:27-31`).
- Dual validator layers: `StructureBlock` (`docx_structure.py:165-176`, all-or-none page locator, end>start, bbox requires page_index) and `ProtocolSourceSpan` (`protocol_ingestion.py:146-183`).
- Repeated text: physical page identity comes from the extraction reader, not text matching — `test_native_pdf_locator_does_not_guess_when_same_text_repeats` asserts both pages align to their own physical pages with zero degradation. Honest, no collision guessing.
- Caveats: bbox is not re-derived at alignment time (integrity rests on blob content-addressing — acceptable); multi-column pages silently interleave (see Risks).

### Objective 3 — 扫描/加密/损坏/文本不足失效关闭: **YES in code, thin in regression tests**

- Textless or <8 non-ws chars on **any** page → `PdfTextLayerInsufficientError` with `insufficient_pages` (1-based), no blob written (`pdf_structure.py:306-347`); zero-page explicit (`:283-289`); encrypted → `PdfEncryptedError` via `PDFPasswordIncorrect` (`:233-245`, never decrypts); corrupt → `PdfOpenError`; magic-not-PDF → `PdfFormatError` (`:269-274`); page-count drift between opens → `PdfTextLayerFailure` (`:298-302`).
- Executor maps to non-retryable `PDF_TEXT_LAYER_INSUFFICIENT` / `UNSUPPORTED_STRUCTURE_FORMAT` / `STRUCTURE_EXTRACTION_FAILED` / `STRUCTURE_NEEDS_REVIEW` (`protocol_deconstruction_executor.py:300-325`) — job closes as 需要核对. Dispatch is magic-based with no text fallback (`structure_dispatch.py`).
- **Gaps:** persistent tests cover only all-scanned + hash-mismatch. Encrypted/corrupt/0-page/mixed-scan were exercised only in worker_02's `/tmp` smoke script — **not in the repo**. Those fail-closed claims are code-verified, not regression-verified. Also `PdfEncryptedError`/`PdfOpenError`/`PdfFormatError` collapse to one generic `STRUCTURE_EXTRACTION_FAILED` at the API boundary, losing their specific machine codes.

### Objective 4 — DOCX 冻结序列化与 D001 指纹: **YES in code; final-state D001 pass unverified**

- `serialize_blocks` pops the 4 new fields when `None` (`docx_structure.py:929-940`) → DOCX block blobs byte-identical to pre-change; covered by `test_docx_block_serialization_omits_unused_pdf_locator_fields`.
- `StructureBlock` new fields default `None` (`:159-163`), frozen `extra="forbid"`; DOCX dispatch path functionally unchanged.
- Replay harness is a pure function of (config, input bytes) with injected `created_at`; fingerprint = canonical SHA over the artifact table (`protocol_replay_harness.py:573-592`); path fields stripped (`:459-463`).
- **Contradiction to surface:** worker_03 recorded the D001 checkpoint test **failing** — recorded `cdb75fbc...`, actual `b68b37fd...` (`worker_03.md:93-94`). Codex's review asserts it passes "原样通过，未重锚". The current code contains the None-pop fix that restores DOCX byte-identity (code analysis supports the pass), but **no persisted re-run evidence exists in the repo**. Independent re-run is impossible in this read-only pass.

### Objective 5 — 120 页 MG-K10-SAR 重复确定性: **NOT INDEPENDENTLY VERIFIABLE — evidence gap**

- The entire claim is one line in `reviews/codex_execution_phase5-slice61aq..._review.md:21`: 120 pages, 285 blocks, content hash `7843e5e55966da24044b224e2221418d3d838bcf819cf557824702ca4ad726c3` identical across two runs, 285/285 direct bbox, no degraded/unaligned, source bytes+mtime unchanged.
- Grep across the worktree (excluding `.venv`/`logs`) finds `7843e5e5...` **nowhere else**: no verification script, no stdout log, no fixture, no persisted two-run output. worker_03 explicitly states no real PDF fixture was available and it did not run it. The source PDF is outside the worktree.
- Therefore this claim **cannot support the "工程接受" conclusion by itself**. It is a single self-reported line in the chair's own review.

### Additional structural observations

- Coordinate convention verified consistent: pdfplumber y-up PDF-points is confirmed by `coordinates.py`, `test_pdf_points_to_image_pixels_flips_y_axis`, and reading-order tests; paragraph splitting (`_split_blocks` gap formula) is correct in that frame. I initially suspected a sign bug; the y-up convention resolves it — not a defect.
- Report/code discrepancies (worker_02 report vs implementation): textless described as "0 chars" but code uses `< 8`; a claimed `degenerate_line_bbox` anomaly is not recorded anywhere (PDF success snapshot always has `anomalies=[]`). Code is stricter/authoritative; reports are not reliable verbatim.
- Whole-doc fail-closed on any single <8-char page (even 1 of 120) — far more aggressive than worker_01's two-tier design (all-textless FAILED / some NEEDS_REVIEW / thin-page ratio). It is fail-closed and safe; the SAR PDF passed it; but a single blank separator or short cover page blocks the entire protocol.
- Performance: 2–3 full pdfplumber parses per job (`_open_page_count` + extraction + render). Acceptable for 120 pages; noted.

## Evidence And Assumptions

- **Observed (code):** all file/line citations above; tests listed; checkpoint test structure; serialization filter; executor mapping.
- **Reported (worker/chair claims, not independently re-runnable here):** D001 final-state pass; 1071 passed; 120-page determinism run; 285-block count.
- **Inference:** `b68b37fd...` was produced by the pre-fix serialization (new null fields in DOCX blobs) and the current None-pop restores `cdb75fbc...` — code analysis supports this but it is not proven.
- **Uncertainty:** objective-5 real-PDF behavior; D001 final state; behavior of the production workflow end-to-end on a real multi-column PDF.

## Risks, Gaps, And Verification Needs

1. **BLOCKING (evidence):** 120-page determinism claim unsupported by any inspectable artifact. Fix: persist script + two-run outputs + source PDF sha256 under `runs/verification/`, or downgrade acceptance wording.
2. **BLOCKING (evidence):** D001 final-state pass is asserted, not evidenced (worker_03 observed a failure). Fix: log one clean `pytest test_protocol_replay_harness.py::test_d001_p803_p805_read_only_checkpoint_rebuilds` run.
3. **HIGH risk (silent corruption):** multi-column/side-note pages interleave into one x-sorted line (`pdf_native.py _group_lines`) → COMPLETED snapshot with scrambled text; worker_01's D5 `ambiguous_reading_order` closure was **not implemented**. Not in the objective's fail-closed list, but it is the sharpest entry-vs-semantics boundary issue: the entry accepts, and content is wrong. Fix: informational anomaly now, `NEEDS_REVIEW` on internal-gap signature in a follow-up slice.
4. **MEDIUM (test gap):** encrypted/corrupt/0-page/mixed-scan fail-closed paths have no persistent regression tests.
5. **MEDIUM (product behavior):** flat <8-char whole-doc fail-closed — confirm intended; consider the two-tier policy.
6. **LOW:** no `ProtocolRenderArtifact` manifest for PDF identity render; generic error codes for encrypted/corrupt; worker-report/code drift; 2–3 parses per job.

## Recommended Next Step

1. Codex runs and persists the two-run 120-page determinism verification (script + outputs + source hash) — this is the single evidence item that objective 5 demands.
2. Codex runs and logs the D001 checkpoint test in the final tree state.
3. Codex decides multi-column closure severity (anomaly vs NEEDS_REVIEW) and confirms the <8-char whole-doc policy.
4. Persist the smoke-script fail-closed cases as regression tests.
5. Then finalize acceptance: **entry accepted with follow-ups; title/table semantic recovery remains below DOCX equivalence and is explicitly not claimed.**

**Boundary questions for Codex** (precise, answerable same-session):
- Q1: Persist the 120-page evidence, or downgrade the claim? (blocks unconditional acceptance)
- Q2: Provide the D001 final-state re-run log?
- Q3: Multi-column: implement `ambiguous_reading_order` NEEDS_REVIEW now, or accept as known gap for this slice?
- Q4: Confirm whole-doc fail-closed on any single <8-char page is intended product behavior?
- Q5: Persist encrypted/corrupt/0-page/mixed regression tests?
- Q6: Is a domain `ProtocolRenderArtifact` (with `storage_ref`) required for the PDF identity render, or are checkpoint fields sufficient for this slice?
- Q7: Add distinct error codes for encrypted/corrupt at the API boundary?

**My most important objections:** (1) the acceptance conclusion leans on two unverifiable claims (120-page determinism, D001 pass) — evidence first, then accept; (2) silent multi-column interleaving is a worse failure mode than any of the listed fail-closed items because it passes as COMPLETED with corrupt content; it should at minimum produce an anomaly and be tracked explicitly; (3) worker reports overstate test coverage — the persistent suite is 6 unit tests plus API/replay tests; the claimed fail-closed matrix is largely code-visible but not regression-locked.

Trellis SessionStart context loaded; this is my one bounded conference pass (tools: read/grep/glob only; no writes beyond the plan file; no tests run).

ExitPlanMode is not available in this non-interactive session — that's fine, since this was a read-only review task with no implementation to approve. The complete report has been returned above, and the audit record is persisted at `/Users/smkzw/.codebuddy/plans/toasty-nebula-einstein-DB3vLgQm.md`.

**One-line summary:** Entry capability is sound and fail-closed where claimed (hash identity, exact-substring locator verification, scanned/encrypted/corrupt/insufficient-text closure, DOCX byte-identity preserved via `serialize_blocks` None-pop); **accept with follow-up**, blocked only by two unverifiable evidence claims — the 120-page MG-K10-SAR determinism run (no inspectable script/log/output anywhere in the repo) and the final-state D001 fingerprint pass (worker_03 recorded a failure; the code fix is visible but the re-run is asserted, not evidenced). Highest-risk silent issue: multi-column pages interleave without detection, yielding COMPLETED snapshots with scrambled text — a follow-up closure, not an entry blocker.
