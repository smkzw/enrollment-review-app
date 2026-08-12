# Codex Review: enrollment_fullflow_model_audit_20260701

Date: 2026-07-02

Hermes outputs:

- `runs/hermes_enrollment_audit_qwen37_20260701.md`
- `runs/hermes_enrollment_audit_minimaxm3_20260701.md`
- `runs/hermes_enrollment_audit_mimo25_20260701.md`
- Consensus: `runs/hermes_enrollment_model_consensus_20260702.md`

## Verdict

Pass after Codex verification and a narrow patch round.

## Boundary Check

- Qwen produced the requested output file under `runs/`.
- MiniMax and MIMO full prompts timed out; fallback no-tool outputs were written under `runs/`.
- No raw clinical source folders outside the workspace were read by Hermes in the fallback prompts.
- Codex made all source changes; Hermes did not edit source files.

## Codex Verification

- Source review confirmed project/subject write operations use authorization guards; the broad "API permission missing" model concern was not accepted as an open bug.
- Source review confirmed prior path traversal and upload filename guards remain present.
- Browser visual review confirmed the original mobile table problem and confirmed the post-patch scroll behavior.
- Tests:
  - `python3 -m compileall app tests scripts` passed.
  - frontend JS extracted from `static/index.html`, then `node --check /tmp/enrollment_index.js` passed.
  - `python3 -m unittest discover -s tests` passed: 130 tests, 1 skipped fixture.
- Post-patch Playwright metrics:
  - mobile subject list table scrollable: `clientWidth=362`, `scrollWidth=1741`, `scrollLeft=1379` after programmatic scroll.
  - mobile report table scrollable: `clientWidth=362`, `scrollWidth=904`, `scrollLeft=542` after programmatic scroll.
  - desktop subject list had no body overflow and no required horizontal scroll.
  - checked visible text contained no `LLM` or `Markdown` labels.

## Hermes Output Review

Accepted:

- mobile table clipping as the highest-priority real UI bug;
- user-facing technical terminology cleanup;
- clarifying that the phase dropdown is for batch operations only;
- preserving desktop density.

Rejected or deferred:

- MiniMax recommendation to move baseline/randomization anchor date to project-level metadata was rejected because each subject can have a different baseline/randomization date.
- hiding `smkzw`/creator username was deferred because ownership visibility supports the current permission model.
- converting Markdown exports to Word/PDF was deferred because Markdown output is an explicit user requirement.
- help page accordion rewrite was deferred as larger product work.

## Residual Risk

- oMLX was not ready during this audit (`omlx=false` health), so a separate launcher/oMLX startup test is still needed.
- Mobile tables are now reachable by horizontal scrolling. A more touch-native mobile card layout remains a future UX improvement.
- The app still has a single large frontend file; this remains a maintainability risk but was not refactored in this patch.
