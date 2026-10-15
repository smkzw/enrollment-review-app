# Enrollment Review App Model Audit Consensus

Date: 2026-07-02

Inputs:

- Qwen 3.7 Plus: `runs/hermes_enrollment_audit_qwen37_20260701.md`
- MiniMax M3: `runs/hermes_enrollment_audit_minimaxm3_20260701.md`
- MIMO V2.5: `runs/hermes_enrollment_audit_mimo25_20260701.md`
- Codex live evidence: Playwright snapshots under `output/model_audit_20260701/`

## Route Notes

- Qwen completed the full visual/text review and wrote its target file. It was slow and produced minimal stdout, but the output was usable.
- MiniMax and MIMO long file-reading prompts both timed out in the tool/file-write style. They were rerun in fallback no-tool mode with the same bounded evidence summarized in the prompt. Their outputs are advisory but still useful for consensus.
- Codex treats all model output as critique, not final authority.

## Consensus Findings Accepted

1. Mobile subject list and report tables were not usable.
   - Evidence before patch: `sar_subjects 390x844` and `sar_subject_31001_screening 390x844` both had overflow elements while page overflow was hidden.
   - Fix accepted: make `.table-wrap` horizontally scrollable, keep desktop width behavior, and add mobile scroll hints.

2. User-facing text still exposed technical terms.
   - Evidence: `LLM` appeared in progress, help, workbench labels, and chat role. `Markdown` appeared in primary export labels.
   - Fix accepted: replace visible `LLM` with system/智能审核/解析 wording, and replace primary `Markdown` labels with `导出报告` / `报告导出`.

3. The global phase selector was confusing after per-phase cells were added.
   - Evidence: subject list already shows screening and baseline cells, but the card above was labeled `审核阶段`.
   - Fix accepted: relabel it to `批量操作阶段` and explicitly state that it affects batch actions only; each row can still enter the specific phase directly.

4. Desktop density should be preserved.
   - Evidence: desktop 1440 view has no horizontal overflow and uses width effectively.
   - Fix accepted: avoid broad desktop table/card redesign in this pass.

## Findings Rejected Or Deferred

1. "Move baseline/randomization anchor date to project-level metadata."
   - Rejected. In real clinical review, each subject can have a different baseline/randomization date. The correct model is subject-level phase anchor dates, not one project-level date.
   - Current improvement keeps per-subject anchor dates and clarifies the batch-stage selector.

2. "Hide or rename username `smkzw`."
   - Deferred. The creator/uploader column is required for ownership and permission transparency. For production, display-name support could be added later, but hiding ownership would weaken auditability.

3. "Convert Markdown export to Word/PDF."
   - Deferred. The user explicitly requested Markdown reports. The current fix changes visible copy to `导出报告` while preserving `.md` export behavior.

4. "Accordion/help rebuild."
   - Deferred. The help page loads without overflow, already has process sections, and a full restructure is larger than the current bug-fix loop.

5. "API permission risk."
   - Rejected as an open bug after source review. Mutating project, subject, OCR/review, upload, delete, and rule endpoints already call project/subject modify guards; unit tests cover ownership/shared-read behavior.

## Codex Verification After Patch

- `python3 -m compileall app tests scripts`: passed.
- JS extraction from `static/index.html` plus `node --check`: passed.
- `python3 -m unittest discover -s tests`: 130 tests passed, 1 skipped fixture.
- Playwright metrics after patch:
  - mobile subject table: `.table-wrap` `clientWidth=362`, `scrollWidth=1741`, `scrollLeft` changed from `0` to `1379`, `overflowX=auto`.
  - mobile report table: `.table-wrap` `clientWidth=362`, `scrollWidth=904`, `scrollLeft` changed from `0` to `542`, `overflowX=auto`.
  - desktop subject table: `clientWidth=1376`, `scrollWidth=1376`, no horizontal scroll needed.
  - visible page text in checked routes had no `LLM` and no `Markdown` labels.

## Residual Risk

- oMLX was `false` in the health check during this audit. This was not fixed in this patch because the task focused on app/UI review, and starting oMLX is a runtime/launcher concern. It should be checked in the next full launcher test.
- Mobile now supports horizontal table access, but a native card/table hybrid layout would be easier for touch users. This is product work, not a small bug fix.
- Model fallback outputs can contain overreaching suggestions. They should remain advisory and not be treated as source of truth without Codex verification.
