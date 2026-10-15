This is continuation round 3 in the same session. The round-2 report inspected stale
code/evidence and repeated findings that Codex had already repaired before that round.
Do not repeat the prior report. Re-open the current files and verify the current state.

The following prior findings were repaired and have dedicated regressions:

1. `app/protocols/source_alignment.py`: exact-range collision exemption now requires
   unique source refs forming one strict linear ancestor/descendant chain. Sibling
   branches are downgraded. Verify the current implementation and
   `test_collision_exemption_allows_only_one_linear_ancestry_chain`.
2. `app/protocols/pdf_structure.py`: clinical measurement/time prefixes now include
   ng, pg, microlitre variants, dL, mmol, mol, IU, cm, mm, min, sec, frequencies,
   percent, and temperature with contextual boundaries. Verify that the regression
   also preserves genuine headings such as `分析人群` and `次要估计目标`.
3. Repeated page-edge chrome now uses a primary repeated outer-edge line and bounded
   adjacent continuation to cover tall multi-line headers, plus a one-page page-number
   fallback. Verify the current implementation and tests.
4. Caption-anchored table extraction now uses a local consumed set and returns no
   table on any partial mismatch before mutating the page-global consumed set. Verify
   that unmatched fragments cannot disappear from or escape into the body.

Current final evidence, which supersedes the older `full-backend-tests-rerun.txt`:

- `runs/verification/phase5-slice61ar-pdf-layout-structure-quality-20260829/full-backend-tests-final.txt`:
  3154 passed, 3 skipped, 141 warnings, 18 subtests passed.
- `runs/verification/phase5-slice61ar-pdf-layout-structure-quality-20260829/mg-k10-sar-v2.1-structure-quality.json`:
  accepted=true, source_immutable=true, runs_identical=true, 120 pages,
  2756/2756 bbox aligned, degraded=0, unaligned=0, anomalies=[], violations=[],
  48 tables, 158 headings.
- `d001-replay-a.txt` and `d001-replay-b.txt` retain identical fingerprints.

Re-audit current code and these final artifacts. Separate:
- defects that remain reproducible in current code;
- explicitly deferred limitations (for example cross-page table semantic stitching or
  mixed full-width/multicolumn layouts) that do not invalidate this native-text PDF
  structural-parity slice;
- speculative future hardening ideas.

Return the complete updated report in the original schema. State clearly whether any
High or Medium issue still blocks acceptance of this bounded slice. Codex remains the
final authority and you must not edit source files.
