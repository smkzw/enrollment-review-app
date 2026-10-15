# Execution Output: phase5-slice61ar-pdf-layout-structure-quality-20260829 - worker_03

## Boundary And Context Check

- Read:
  - `context/phase5-slice61ar-pdf-layout-structure-quality-20260829_execution_context.md`
  - `plans/codex_execution_phase5-slice61ar-pdf-layout-structure-quality-20260829.md`
- Scope limited to PDF structure regression tests and verification tooling.
- No production implementation files modified.
- Source plans were not modified.
- No package installation, credential handling, or external account changes.

## Work Performed

1. Updated stale scanned-page tests in `tests/v2/protocols/test_pdf_structure_entry.py`.
   - Scanned pages now use actual image-only PDF pages.
   - Mixed PDFs use one native-text page plus one image-only page.
   - Assertions verify:
     - `native_text`
     - `scanned`
     - page-level classifications
     - fail-closed behavior
     - no structure blob written

2. Added deterministic layout-quality regressions in:
   - `tests/v2/protocols/test_pdf_structure_quality.py`

   Coverage includes:

   - Two-column column-major reading order.
   - Table root and row-major cell paths.
   - Exact page text slices for table cells.
   - Table bbox/page-only downstream alignment behavior.
   - Heading outline levels from layout evidence.
   - Short native page plus blank page.
   - All-blank PDF classification.
   - Scanned-only and mixed native/scanned fail-closed behavior.
   - 90°, 180°, and 270° rotated pages.
   - Native coordinates, structure serialization, content hash, and source mtime/bytes determinism.
   - `extract_protocol_structure` dispatch compatibility.

3. Added real-plan verification script:
   - `scripts/verify_pdf_structure_quality.py`

   The script records:

   - Page kind, dimensions, rotation, text counts, image/vector marks.
   - Native text and coordinate hashes.
   - Parser/version, block/table/paragraph counts.
   - Structure content hash and serialized block hash.
   - Exact page-range invariant violations.
   - Alignment counts and precision distribution.
   - Unaligned source references and reasons.
   - Structure anomalies.
   - Source bytes and mtime immutability.
   - Two-run determinism.
   - Downstream compatibility gate.

   The script fails acceptance when completed extraction has table anomalies, degraded/unaligned spans, or range violations. `--allow-failed-closed` permits deterministic scanned/insufficient inputs for classification evidence.

## Artifacts And Evidence

Modified or created:

- `tests/v2/protocols/test_pdf_structure_entry.py`
- `tests/v2/protocols/test_pdf_structure_quality.py`
- `scripts/verify_pdf_structure_quality.py`

Real-plan inputs:

- SAR DOCX:
  - `artifacts/phase5-acceptance/20260823/isolated-inputs/sar/protocol/4. Protocol/MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx`
- D001 DOCX:
  - `artifacts/phase5-acceptance/20260823/isolated-inputs/d001/protocol/test-D001项目/CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx`

Because native SAR/D001 PDF source artifacts were not present, both real DOCX files were converted to temporary PDFs under `/tmp/phase5-pdf-quality-real/`; source files were not changed.

Real-plan evidence summary:

| Source | Pages | Blocks | Tables | Anomalies | Unaligned | Source immutable | Runs identical |
|---|---:|---:|---:|---:|---:|---|---|
| SAR | 221 | 4084 | 70 | 42 | 7 | true | true |
| D001 | 169 | 2763 | 66 | 41 | 9 | true | true |

All real-plan pages classified as `native_text`; no rotations observed.

Unaligned SAR table roots included:

- `p34.t0`
- `p154.t0`
- `p171.t0`
- `p212.t0`
- `p213.t0`
- `p214.t0`
- `p215.t0`

Unaligned D001 table roots included:

- `p22.t0`
- `p36.t0`
- `p51.t0`
- `p52.t0`
- `p53.t0`
- `p54.t0`
- `p55.t0`
- `p99.t1`
- `p148.t0`

## Commands And Observations

- `.venv/bin/pytest -q tests/v2/protocols/test_pdf_structure_quality.py tests/v2/protocols/test_pdf_structure_entry.py`
  - Result: `21 passed, 5 warnings`
- `.venv/bin/python -m py_compile scripts/verify_pdf_structure_quality.py tests/v2/protocols/test_pdf_structure_quality.py tests/v2/protocols/test_pdf_structure_entry.py`
  - Result: passed with no output.
- Synthetic verifier:
  - Two-column and table fixtures: accepted.
  - Native + blank + scanned fixture with `--allow-failed-closed`: accepted as deterministic fail-closed evidence.
- Real-plan verification:
  - Both runs deterministic.
  - Source bytes and mtime unchanged.
  - Script exit status: `1`.
  - Reason: real plans contain table-cell mismatch anomalies and unaligned table-root spans, so downstream structure compatibility is not accepted.

## Blockers Or Missing Environment

- Final real-plan quality gate remains blocked by the current PDF structure implementation:
  - SAR: 42 `pdf_table_cell_mismatch` anomalies and 7 unaligned table roots.
  - D001: 41 `pdf_table_cell_mismatch` anomalies and 9 unaligned table roots.
- The script intentionally reports these failures instead of accepting incomplete structure.
- No native PDF copies of the SAR/D001 source plans were available in the declared workspace; evidence used temporary LibreOffice-derived PDFs from the real DOCX files.
- No visual or clinical/regulatory acceptance was performed.

## Rerun Requests Or Next Step

- Codex should review the real-plan anomaly and unaligned-root evidence before final acceptance.
- After PDF structure implementation fixes, rerun:

```bash
.venv/bin/pytest -q \
  tests/v2/protocols/test_pdf_structure_quality.py \
  tests/v2/protocols/test_pdf_structure_entry.py

.venv/bin/python scripts/verify_pdf_structure_quality.py \
  "<SAR PDF>" \
  "<D001 PDF>" \
  --output <report.json>
```

- Acceptance requires deterministic runs, unchanged source bytes/mtime, zero slice violations, no structure anomalies, and zero degraded/unaligned downstream spans.
