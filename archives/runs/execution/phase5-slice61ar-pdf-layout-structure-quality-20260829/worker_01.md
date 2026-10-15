Audit complete — all evidence gathered. Composing the full report.

# Execution Output: phase5-slice61ar-pdf-layout-structure-quality-20260829 - worker_01

## Boundary And Context Check

- Worked strictly read-only inside the runner worktree plus one explicitly task-authorized read outside it: the real SAR protocol PDF, located by exact hash match with the already-accepted verification record (see Evidence). No files created, modified, or deleted anywhere. All probes ran in-memory via `.venv/bin/python -c` (zero writes; the app's blob persistence was monkeypatched to a no-op only inside probe processes, and `output_dir="/dev/null"` was never reached).
- Environment confirmed: project venv `.venv` = Python 3.12.13, pdfplumber 0.11.10, PyMuPDF 1.26.4 (matches `pyproject.toml` pins). System `python3` 3.9.6/pdfplumber 0.9.0 is NOT the runtime and was not used.
- No D001 protocol PDF exists in any accessible location (searched project tree, 康哲项目资料). D001 evidence = its DOCX (in worktree) plus DOCX-channel fingerprints.
- Prior-slice artifacts read as context: 61aq execution review (acceptance of the flat PDF entry), persisted two-run verification record, `scripts/verify_native_pdf_structure.py`, `tests/v2/protocols/test_pdf_structure_entry.py`, `tests/v2/evidence/goldgen.py`.

## Work Performed

### 1. Current-state audit (with evidence)

**Native layer `app/evidence/pdf_native.py`** — pdfplumber chars → canonical (rotation-inverted) coords → y-overlap line grouping (1.5 pt tolerance) → x-ordered lines → space insertion at 0.5× median char width → single canonical page text (`NativePage.text`) + per-char `start` offsets + words. Rotation 0/90/180/270 handled for ordering only; char bboxes stay in the display frame for page-image mapping. `serialize_native_coordinates` = deterministic content-addressed JSON, schema `native_coordinates/v1`.
- **No column awareness**: chars of different columns sharing a y-band merge into one "line" and interleave by x → true two-column pages get column lines interleaved (reading order broken).
- **No per-line canonical geometry exposed** → structure channel cannot paragraph-split rotated pages (currently: all lines of a rotated page become one block, per `_split_blocks` docstring).

**Structure channel `app/protocols/pdf_structure.py`** (parser `pdf-native-text` v1.0.0) — fail-closed ladder with stable codes (format/hash/encrypted/corrupt/page-failure/text-layer-insufficient); page = hard boundary; block split = paragraph gap (≥2 pt AND >1.6× median line height); every block is `PARAGRAPH`/`BODY`/`outline_level=None`/`numbering=None`/`table_path=None`, ref `p{n}.b{m}`, exact `page_index`+text range+bbox; `MIN_PAGE_TEXT_CHARS=8` non-ws chars, any below-threshold page aborts the whole extraction **without distinguishing blank from scanned** (no image check); coverage `table_count=0`, `section_count=page_count`, `header/footer_detected=False`, `anomalies=[]`; content-addressed blob + SHA-256 post-write verify; deterministic.

**Accepted baseline reproduced exactly** (in-memory, zero writes): SAR PDF → 285 blocks, `content_sha256 = 7843e5e55966da24044b224e2221418d3d838bcf819cf557824702ca4ad726c3` — identical to the accepted two-run record; 0 tables, 0 headings, 0 chrome parts; 6 pages have ≤1 block (14, 32, 49, 61, 88, 89); largest block = 3462 chars (`p3.b0`, an entire page merged); avg 2.4 blocks/page. The gap rule barely fires in this document (sample pages: 1–2 qualifying gaps out of 30–37 line gaps).

**Real SAR PDF ground truth** (`MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .pdf`, sha256 `b387807997fb76dd782f2cc1a7bf15ec474d8cc096d1b5d660ca28fb2a1bc606`, 2,210,360 B, 120 pp):
- 100% native text: **no blank, no scanned, no rotated pages**; p30 has 2 inline images + 173 non-ws chars (figure page with caption — proves `images>0` alone must not classify "scanned"; the classifier must be `nonws<8 AND images>0`).
- Tables: 0 `lines`, 6,613 `rects` (grid borders are rectangles) → `find_tables(lines,lines)` (edges include rects) detects **38 ruled pages**; `find_tables(text,text)` fires on **every** page — false positives on justified body and dot-leader TOC (p3). **Lines strategy is mandatory; text strategy is untrustworthy here.**
- Fonts: body SimSun 12 pt (43.7k chars); **bold exists only on Latin fonts** (TimesNewRomanPS-BoldMT 12 pt ≈2.8k, Arial-BoldMT 137); SimSun 14 pt/18 pt = centered titles. Heading evidence verified on real lines: `"1 方案摘要"`, `"1.1 摘要"` (p14) = **bold leading number token + regular SimSun title**; `"方案签署页"` centered SimSun 14 pt (p8–13); cover SimSun 18 pt. Chinese heading text is never bold → detection must key on the bold leading number / centered-large typographic evidence, not title-text font.
- Running chrome: header `"湖南麦济生物技术股份有限公司 方案编号：MG-K10-SAR-001"` at top ≈30–44 pt on all pages; footer `"第N页/共120页"` at bottom ≈791.6 pt on all pages (page number varies → repetition test must digit-normalize).
- Cell extraction works on ruled grids (p20 3×2; p89 two 6×2; p117 5×8 scale tables); wrapped narrow columns insert mid-word spaces (`"没有困 扰"`); the synopsis table **spans 17 pages (14–30)** — row detection is per-page.
- Shortest page = 152 non-ws chars (p112): this document never approaches `MIN_PAGE_TEXT_CHARS=8` → blank/scanned handling is **not exercised by SAR**; only synthetic fixtures can verify it.

**DOCX baselines (same protocol, worktree files)**:
- SAR DOCX: 3,280 blocks (3,254 para + 26 table roots), **154 headings** (L0:21, L1:47, L2:55, L3:25, L4:6), 4 header/footer parts, `section_count=21` (OOXML sections).
- D001 DOCX: 3,581 blocks (3,556 + 25 tables + 1 nested), 231 headings (incl. 61 at outline_level 9 — pre-existing OOXML oddity), replay fingerprint `cdb75fbc…` must stay byte-identical.
- Gap: the PDF channel currently recovers **none** of the headings/tables/chrome that downstream consumes.

**Downstream contract compatibility (what the improved parser must respect)**:
- Ref grammar: `p{n}.t{m}.r{r}.c{c}.p{k}` satisfies the existing `_CELL_REF_RE` (`^(?P<table>.+?\.t\d+)\.r\d+\.c\d+(?:\.p\d+)?$`) and `_TABLE_ROOT_RE` in `phase_detection`/`section_index`/`full_protocol_coverage`/`procedure_catalog` — verified by regex inspection.
- `procedure_catalog._root_for_cell` requires the table root ref to be a prefix of the cell ref + `.r` → **per-page table roots `p{n}.t{m}`** are the compatible shape.
- `source_alignment._align_block`: any block with `page_index` set passes a **strict verbatim-substring check** against `page_texts[page_index]` ("拒绝伪造精确定位"). Consequences: (a) a PDF table root must carry `page_index=None` and align through its cell anchor needles (→ PAGE_ONLY ALIGNED, exactly the DOCX table-span pattern); cell paragraphs carry the precise bbox. (b) cell text must be a verbatim contiguous slice of the assembled page text (derive it from the assembly lines, never from `find_tables().extract()` normalization); non-contiguous → `page_index=None` fallback (UNALIGNED, no fake precision). (c) header/footer blocks with `page_index` aligning precisely is truthful (the original PDF is the source), not pseudo-precision.
- `protocol_deconstruction_executor` (lines 357–360) freezes the invariant: PDF-source `page_texts` = `extract_native_pages(...).text`; **不得混用两套页文本装配** → column-aware assembly must live in `pdf_native` (single source), not in a structure-channel private text.
- `page_processor.decide_route_detailed` (evidence channel) currently routes blank and scanned pages identically to VISION_OCR; the structure channel should diverge: blank = tolerated + anomaly, scanned = fail-closed.
- `full_protocol_coverage` degrades gracefully without headings (`"（无标题）"` paths, no table-row atomization) — it will *work* but produce a near-useless manifest; with headings + table refs it becomes genuinely usable.
- No persisted references to the old hash `7843e5e5…` exist in this worktree's project data.

### 2. Minimal generic implementation proposal (for worker_02)

**B0. Versioning / contract posture**
- Bump `PARSER_VERSION` to **2.0.0** (block-set semantics change for all PDF inputs). Existing snapshots remain immutable 1.0.0 artifacts; nothing is rewritten. The new SAR output gets a fresh accepted hash via the same two-run verification. The "hash contract" (content addressing, validators, determinism, exact page/text-range/bbox) is preserved mechanically; only the frozen *value* moves under a new parser version. See Q1.
- No changes to `StructureBlock`, `ExtractionCoverage`, `ProtocolExtractionSnapshot` models. Blank pages recorded via existing `anomalies` (`kind="blank_page"`, `scope_ref="p{n}"`); `PdfTextLayerInsufficientError` gains additive attributes `scanned_pages`/`blank_pages` (backward-compatible). `native_coordinates/v1` serialization stays byte-identical (no new payload fields); per-line canonical geometry, if needed, is exposed on `NativePage` as internal-only, never serialized.

**B1. Page classification (blank vs scanned)** — per page: `nonws < 8` → `images == 0` ? **BLANK** (no blocks; anomaly; non-blocking) : **SCANNED/figure page** → whole extraction fail-closed `pdf_text_layer_insufficient` with the message and attributes distinguishing scanned from blank. `nonws ≥ 8` → NATIVE regardless of inline images (SAR p30 case). No OCR.

**B2. Column-aware reading order (inside `pdf_native`, single source)** — after canonical line grouping, split a page into left/right columns only when ALL hold: (1) multi-column signature: ≥70% of lines are fully contained in one half (with margin), each side ≥8 lines, sides' y-ranges interleave; (2) grid guard: no ruled-grid region on the page (edge counts from already-extracted `page.rects/lines/curves`: ≥2 vertical + ≥4 horizontal edges sharing a common span → table page → no split); (3) column stability (low variance of per-side x-ranges). Otherwise single flow (current behavior — safe). Reorder = left column top→bottom, then right column top→bottom. Deterministic. **If this changes any page's text bytes, the evidence-channel decoder identity `DECODER_VERSION_BY_KIND["pdf"]` ("slice4.3/pdfplumber/v1") must be bumped** so old artifact identities are never reused (Q2). Known residual risk: borderless two-column tables — guard (2) can't fire; strictness of (1)+(3) makes mis-split unlikely; cover with synthetic regression.

**B3. Table structure (structure channel)** — per page: `find_tables(lines, lines)` only. Emit one table root per page occurrence: ref `p{n}.t{m}`, kind=TABLE, `text=""` (DOCX-root parity: structural anchor, no prose), `table_rows/cols` from grid, `page_index=None`, `bbox=None`, aligns via cell anchor needles → PAGE_ONLY. Cell paragraphs for non-empty cells: ref `p{n}.t{m}.r{r}.c{c}.p{k}`, `table_path=(r,c)`, text derived from assembly lines (verbatim contiguous slice), precise `page_index`+range+bbox; non-contiguous → `page_index=None` (UNALIGNED). Empty cells skipped. Body paragraphs exclude lines inside table bboxes; the root sits at the table region's first-line position in reading order. **No cross-page merging** (downstream groups by ref table identity); document the limitation (Q3). Nested tables: pdfplumber has no native nested-grid support; D001 has exactly one — v1 may document "no PDF nested tables" unless a cheap recursive in-cell `find_tables` guard is verified deterministic.

**B4. Headings (typography evidence only, no text rules)** — a non-table, non-chrome body line is a heading iff:
- **H1 bold-leading-number**: line starts with `^(\d+([.．]\d+)*)\s*` where the number chars' fontname contains "Bold", line non-ws ≤ 30, line does not end with sentence punctuation (。！？；，、…); `outline_level = number_depth − 1` (capped 9) — "1"→0, "1.1"→1, matching the DOCX L0/L1 convention (SAR DOCX chapters are L0).
- **H2 centered title**: line center within ±4% of page center AND (max char size ≥ 1.15× body median size OR bold) AND non-ws ≤ 20 → level 0 (recovers 方案签署页/目录/方案修订史 class).
- else `outline_level=None` (never fabricate). Record the evidence class in `style_name` (`"pdf-bold-leading-number"` / `"pdf-centered-title"`) — metadata only, consistent with the rule that `style`/`style_name` must not be the heading criterion (downstream uses `outline_level`).
- Calibration target: SAR DOCX = 154 headings; expect ≥90% recovery (numbered + centered); misses = unnumbered non-centered Chinese headings; measured false positives on short bold numbered list items bounded by the length/punctuation filters.

**B5. Running header/footer** — top band (`top ≤ 10%` page height) / bottom band (`bottom ≥ 90%`): digit-normalized line repeated on ≥ max(3, 25%) of pages in the same band → those lines become `HEADER`/`FOOTER` blocks, refs `p{n}.h0`/`p{n}.f0`, real per-page text, precise locators; excluded from body paragraphs; `header_detected`/`footer_detected` true. Pure geometry+repetition, no content rules. Variant headers stay BODY (conservative).

**B6. Rotated pages** — expose per-line canonical top/bottom (internal-only) so `_split_blocks` runs for all rotations; final bboxes remain display-frame (page-image mapping invariant).

**B7. Do-not list**: no second page-text assembly (frozen invariant, 61aq warning); no text-strategy table detection (proven false positives); no project-specific text rules; DOCX parser untouched (D001 fingerprint guard); no `native_coordinates/v1` payload change; no OCR.

### 3. Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | Literal reading of "不破坏…哈希契约" (freeze `7843e5e5` forever) makes structural improvement impossible — the hash is over the block set | Q1: confirm 7843e5e5 stays the 1.0.0 fingerprint; 2.0.0 gets a new accepted hash via identical two-run verification; old snapshots immutable |
| R2 | Block growth + per-page `find_tables` cost | SAR adds a few hundred cell blocks (DOCX parity is 3,280); probe showed 120-page table detection takes seconds — acceptable |
| R3 | Heading false positives (short bold numbered list items) | DOCX-ground-truth comparison gate (≥90% recall, ≤5% FP on SAR); thresholds are generic typography constants |
| R4 | Two-column split on borderless two-column tables | grid guard + signature strictness + synthetic regression (two-column text must split; two-column ruled table must NOT) |
| R5 | Cell text non-contiguity → UNALIGNED cells | SAR single-column expected 0 failures (measured); fallback never fakes precision |
| R6 | Stale evidence-channel artifact identities if page text bytes change | decoder identity bump (Q2) |
| R7 | Per-page table identity breaks cross-page row context (visit-table detection, flow catalog spanning tables) | documented v1 limitation; possible follow-up slice (Q3) |
| R8 | Existing test pins encode flat behavior (`outline_level is None`, `table_count 0`, `p1.b0` refs, mixed-page single error) | worker_03 updates: keep all fail-closed tests; change mixed-case semantics (blank tolerated / scanned fail-closed); keep source-unchanged + determinism tests |
| R9 | D001 DOCX `outline_level=9` (61 blocks) pre-existing | PDF cap is also 9 — consistent, no action |

### 4. Acceptance matrix

| # | Criterion | Evidence / how |
|---|---|---|
| A1 | SAR PDF source unchanged (sha/mtime/bytes) | before/after stat+sha in verify script (pattern: `scripts/verify_native_pdf_structure.py`) |
| A2 | Determinism: two runs → identical content hash, block set, alignment counts | same two-run verify; persist new accepted hash under `runs/verification/…` |
| A3 | Blank vs scanned: (a) native+blank → success + `blank_page` anomaly; (b) native+scanned → fail-closed naming scanned; (c) native+blank+scanned → fail-closed, both categories distinguishable; (d) all-blank → no-content failure | new `goldgen.py` deterministic fitz fixtures + pytest |
| A4 | Two-column reading order: synthetic 2-column page blocks ordered left-then-right; SAR single-column page texts byte-identical to 1.0.0 output | pytest + SAR page-text comparison |
| A5 | Ruled two-column table NOT column-split | synthetic fixture + pytest |
| A6 | SAR tables: all 38 ruled pages → roots + cells; every cell text verbatim page-text slice (0 contiguity failures); `align_blocks` → cells BBOX-precision ALIGNED, roots PAGE_ONLY ALIGNED, `unaligned==0` | verify script + pytest |
| A7 | Headings: SAR recovers ≥90% of DOCX's 154 headings (number-stripped text match); outline_level matches number depth; measured FP ≤5% | DOCX-vs-PDF heading comparison script |
| A8 | Chrome: `header_detected`/`footer_detected` true on SAR; body blocks no longer contain the repeated lines; per-page footer text exact | verify script + unit test |
| A9 | Rotated: existing rotated gold fixture still orders text correctly AND now paragraph-splits when gap evidence exists | existing test + new assertion |
| A10 | Downstream: D001 DOCX replay fingerprint `cdb75fbc…` unchanged; backend full suite green; smoke `build_full_protocol_coverage_manifest` on new SAR-PDF blocks yields non-`（无标题）` heading paths and table-row units | replay harness + pytest |
| A11 | Fail-closed codes unchanged: encrypted/corrupt/zero-page/hash-mismatch/format tests pass | existing pytest |
| A12 | No shared-contract model changes; `native_coordinates/v1` payload unchanged | diff review |

## Artifacts And Evidence

- No files written (read-only mandate). All findings above are grounded in:
  - Source reads: `app/protocols/pdf_structure.py` (full), `app/evidence/pdf_native.py` (full), `app/protocols/structure_dispatch.py`, `app/protocols/docx_structure.py` (StructureBlock contract), `app/protocols/source_alignment.py` (`align_blocks`/`_align_block`), `app/protocols/full_protocol_coverage.py` (builder + ref regexes), `app/services/protocol_deconstruction_executor.py` (page-text invariant), `app/evidence/page_processor.py` (route decision), `app/domain/contracts/protocol_ingestion.py` (artifact/coverage/snapshot contracts), `app/domain/contracts/enums.py` (DocumentPart), `app/protocols/{phase_detection,section_index,procedure_catalog,metadata}.py` (ref-grammar consumers).
  - Accepted-record reads: `runs/verification/phase5-slice61aq-…/mg-k10-sar-v2.1-two-run.json` (SAR sha `b3878079…`, 120 pp, 285 blocks, hash `7843e5e5…`), `reviews/codex_execution_phase5-slice61aq-…_review.md` (accept_with_followup; "PDF 标题/表格结构恢复仍是后续质量切片"; D001 fingerprint `cdb75fbc…`; 2,977-pass backend baseline).
  - In-memory reproduction: 285 blocks + `content_sha256 7843e5e5…` reproduced byte-for-byte in the project venv → environment parity with Codex's acceptance run.
  - Real-PDF probes (SAR, read-only): page class profile (120 NATIVE, 0 blank/scanned/rotated, p30 2 images), edge counts (0 lines / 6,613 rects), lines-vs-text table strategy (38 ruled pages vs false-positive-everywhere), font histogram (41 styles; bold only Latin; SimSun 14/18 pt titles), heading samples (bold-leading-number + centered-title evidence), running header/footer geometry (top ≈30–44 pt / bottom ≈791.6 pt), per-page line-gap distributions (gap rule fires 1–2× per 30–37 gaps), table grid extraction (3×2, 6×2, 5×8; wrapped-cell space artifacts; 17-page synopsis span), short-page stats (min 152 non-ws).
  - DOCX probes (in-memory, persistence no-op): SAR 3,280 blocks/154 headings/26 tables/4 chrome; D001 3,581/231/25+1 nested/11 chrome; DOCX heading list (levels, numbering-in-text vs numbering-in-OOXML difference).
- SAR PDF read location: `/Users/smkzw/Documents/康哲项目资料/模版/方案模版/研究方案库/MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .pdf` — identity-verified (sha256 + size + name) against the accepted verification record; only file read outside the worktree, and only because the assignment explicitly requires real-SAR evidence.

## Commands And Observations

- `.venv/bin/python -c` probes (pdfplumber page profile; find_tables strategies; font histogram; line-gap distributions; header/footer geometry; table extraction; in-memory `extract_pdf_structure` with `_persist_block_blob` no-op; in-memory `extract_docx_structure` for both DOCX) — observations as itemized in Artifacts And Evidence.
- `shasum -a 256` + `stat` on the SAR PDF: `b387807997fb76dd782f2cc1a7bf15ec474d8cc096d1b5d660ca28fb2a1bc606`, 2,210,360 B — matches accepted record.
- `find`/`mdfind` for SAR and D001 protocol files: SAR PDF found (above); D001 PDF not found anywhere accessible; both protocol DOCXs present in worktree `artifacts/phase5-acceptance/20260823/isolated-inputs/`.
- No test suites were run (not required by this read-only audit item; 61aq's baseline `2,977 passed` recorded as context).

## Blockers Or Missing Environment

- No environment blockers: `.venv` (Python 3.12.13 / pdfplumber 0.11.10 / PyMuPDF 1.26.4) is complete and matches pins.
- No missing-tool gaps for worker_02/03: everything needed (pdfplumber table API, fitz for gold fixtures, goldgen pattern) is present.
- One evidence gap: blank/scanned behavior is untestable on SAR itself (no such pages); synthetic fixtures (A3) are mandatory, not optional.
- One decision blocker for the implementation slice: Q1 (hash-contract interpretation) — see below.

## Rerun Requests Or Next Step

Precise questions for Codex:

1. **Q1 (decision-gating):** Confirm that `7843e5e5…` remains the fingerprint of parser v1.0.0 output and that the reworked parser (proposed v2.0.0) establishes a *new* accepted content hash for the SAR PDF via the same two-run verification — i.e., "不破坏已验收…哈希契约" binds the mechanism (content addressing, exact page/text-range/bbox, determinism, immutability of old snapshots), not the literal value. If the literal value must be frozen, this slice cannot change the PDF block set and must be re-scoped.
2. **Q2:** Approve bumping the evidence-channel decoder identity `DECODER_VERSION_BY_KIND["pdf"]` (`slice4.3/pdfplumber/v1` → v2) whenever the `pdf_native` page-text assembly changes (column-awareness), to prevent stale artifact identities; single-column bytes are unchanged but the identity must be unambiguous.
3. **Q3:** Accept **per-page table identity** (no cross-page table merging) as v1, with the documented limitation for spanning tables (visit-table detection / flow-catalog row context)? Or require cross-page merging now (larger downstream impact, larger test surface)?
4. **Q4:** The real SAR PDF was read from `模版/方案模版/研究方案库` (hash-verified identical to the accepted verification input). Confirm that path as the authorized read source for worker_02/03, or direct Codex to stage a copy into the worktree (e.g. `artifacts/…/source-input/`) so the implementation slice never reads outside the workspace.

Next step (no rerun of this worker needed): with Q1–Q4 answered, worker_02 implements B0–B6 against the real SAR PDF + goldgen fixtures, and worker_03 lands the A1–A12 acceptance matrix (deterministic tests + two-run verification + D001 fingerprint guard + backend full suite).
