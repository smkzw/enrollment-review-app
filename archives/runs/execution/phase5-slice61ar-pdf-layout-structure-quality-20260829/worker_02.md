# Execution Output: phase5-slice61ar-pdf-layout-structure-quality-20260829 - worker_02

## Boundary And Context Check

- Continued the existing bounded worker session on the declared `openai-codex/gpt-5.6-luna` fallback after the `mtplx` route became unavailable.
- Scope remained limited to generic PDF page classification and layout structure recovery.
- No source protocol file was modified.
- No OCR, LLM/VLM, clinical interpretation, publication decision, or final acceptance was performed.
- Runner-managed report file was not written directly.

## Work Performed

Completed `app/protocols/pdf_structure.py`:

- Repaired the interrupted import block and removed duplicate imports.
- Added deterministic page classification:
  - `native_text`
  - `scanned`
  - `blank`
  - `insufficient`
- Blank pages are skipped and recorded as `pdf_blank_pages`.
- Image/vector-only pages and short/undecidable text-layer pages fail closed with `PdfTextLayerInsufficientError`.
- Added complete heading evidence recovery:
  - page-local median font-size baseline;
  - larger-font evidence;
  - generic bold/short-line evidence;
  - document-level descending font-size to 0-based `outline_level` mapping.
- Added ruled-table recovery through pdfplumber:
  - table root blocks;
  - row/column cell blocks;
  - `(row, col)` `table_path` values compatible with downstream consumers;
  - converted table/cell bboxes to the existing PDF y-up coordinate frame;
  - exact page-text ranges for emitted cell blocks;
  - fail-closed cell mismatch anomalies with precise `scope_ref`.
- Added table/body separation:
  - fully consumed table lines are excluded from body blocks;
  - forced paragraph breaks prevent body ranges from swallowing table rows.
- Added whitespace- and compact-text comparison for table cells to tolerate layout-generated spacing without relaxing non-whitespace character identity.
- Preserved the existing `StructureBlock` contract; table roots remain unbound structural anchors while cells carry exact page ranges and bboxes.
- Verified the existing `pdf_native.py` layout implementation:
  - gutter-based multi-column ordering;
  - font size/bold metadata;
  - non-text mark counting;
  - unchanged `native_coordinates/v1` serialized payload fields.

## Artifacts And Evidence

Modified or completed:

- `app/protocols/pdf_structure.py`
- Existing related implementation verified in `app/evidence/pdf_native.py`
- Existing deterministic fixture set under `scripts/worker02_pdf_quality/`

Deterministic fixture observations:

- `single_column.pdf`: 2 paragraph blocks, 2 aligned.
- `multi_column.pdf`: header followed by left-column content then right-column content; 3 blocks, all aligned.
- `heading.pdf`: 6 paragraph blocks; heading levels `0`, `1`, and `2` recovered from generic typography.
- `table.pdf`: 1 table root, 6 cell blocks, 7 paragraph blocks total; all 8 alignment spans aligned.
- `blank_scanned.pdf`: page classifications:
  - page 1: `native_text`
  - page 2: `blank`
  - page 3: `scanned`
  - extraction fails closed on page 3, not on the blank page.

## Commands And Observations

- `.venv/bin/python -m py_compile app/protocols/pdf_structure.py app/evidence/pdf_native.py`
  - Passed after final edits.
- `.venv/bin/python -m pytest -q tests/v2/protocols/test_pdf_structure_entry.py -k 'not scanned and not mixed'`
  - `9 passed, 2 deselected, 5 warnings`.
- `.venv/bin/python -m pytest -q tests/v2/evidence/test_pdf_native_coordinates.py`
  - `10 passed, 5 warnings`.
- Deterministic fixture capture executed twice and compared with `cmp`.
  - Captures were byte-identical.
- Real SAR PDF read-only verification:
  - Source: `MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .pdf`
  - SHA-256: `b387807997fb76dd782f2cc1a7bf15ec474d8cc096d1b5d660ca28fb2a1bc606`
  - Size: `2,210,360` bytes
  - Pages: `120`
  - Two extraction runs were identical.
  - Final structure:
    - `1,382` blocks
    - `1,337` paragraph blocks
    - `45` table roots
    - `992` table-cell blocks
    - `33` typography-derived heading blocks
    - `34` table mismatch anomalies, all fail-closed and source-scoped
  - Alignment:
    - `1,374` aligned
    - `0` degraded
    - `8` unaligned
    - `1,337` bbox-aligned
  - Source bytes and mtime unchanged.

## Blockers Or Missing Environment

- Two legacy entry tests still encode the previous behavior:
  - an empty page is named/treated as a scanned page;
  - native text plus an empty page is expected to fail.
- Under the completed implementation, empty pages are classified as `blank`; actual image/vector-only pages are `scanned`. These tests require the regression-test update owned by the separate quality-test worker.
- Remaining SAR unaligned spans are table roots whose anchor text repeats across multiple pages. They remain unaligned rather than receiving guessed page locations.
- The SAR PDF still exposes 34 table-cell text mismatches caused by source layout ordering/interleaving; those cells are discarded rather than fabricated.
- No native-text D001 protocol PDF was available in the authorized workspace for direct verification. D001 evidence available locally is DOCX and rendered derivative PDF, not an original native PDF.
- Final visual/layout/regulatory acceptance remains with Codex.

## Rerun Requests Or Next Step

1. Update the legacy scanned/mixed tests to use an actual image/vector-only scanned fixture and add explicit blank-page success/error cases.
2. Re-run the full PDF-quality regression set, including rotated-page and source-invariance cases.
3. Codex should review whether the SAR table mismatch and repeated-anchor counts satisfy the final structural-quality gate before accepting the slice.
