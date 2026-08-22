# WP-44A Same-Session Repair Pass 1

Codex independent acceptance result: **REJECT**. Stay within the original WP-44A write scope and repair the root causes below. Do not start WP-44B services/API/frontend. Do not read or modify clinical source material.

## Hard boundaries

- Work only inside the current isolated workspace (`.`).
- Write only the original WP-44A surfaces: `app/domain/contracts/`, `app/storage/`, `tests/v2/domain/`, `tests/v2/storage/`, and directly required existing schema/snapshot contract tests.
- Do not modify services, API, frontend, launch scripts, clinical documents, or project source records.
- Do not overwrite unrelated Phase 4.1-4.3 work.
- Runner-managed report path: `runs/execution/phase4-evidence-ocr-v2-slice44/worker_01_followup_01.md`. Return the report in the final response; do not write it with tools.

## Read these files only at minimum

- `AGENTS.md`
- `context/phase4-evidence-ocr-v2-slice44_execution_context.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/research/slice44-detailed-contract-review.md`
- The WP-44A files and tests listed in the initial assignment.
- Additional in-workspace dependencies may be read only when required to verify a concrete invariant.

## Blocking Findings To Fix

1. **Activity pointers bypass the activation transaction.** Remove both `active_evidence_*` fields from `EpisodeRepository.update()` generic mutable fields. New episode save must not establish a non-null active pair. Reserve active-pair mutation for the future WP-44B atomic activation method. Add negative repository tests proving generic save/update cannot activate, especially cannot point to a base revision. Raw SQL in migration-only downgrade tests may remain only as schema/history setup and must not be described as an allowed application path.

2. **Authenticated bbox can be fabricated and lacks an occurrence range.** A bbox locator must bind a concrete original character range, not just self-declared page dimensions and a non-empty hash. Permit and require `text_start/text_end` for both `bbox` and `text_range`; verify the range/excerpt against the source text. For native text, compare sidecar hash, page dimensions, rotation, and transform version to the persisted PageArtifact/native coordinate sidecar. For raw OCR, compare to the persisted OCRPage layout sidecar and persisted PageArtifact frame; when no same-source layout sidecar exists, bbox is impossible. Effective-text bbox must not be accepted unless the complete/effective sidecar and transform can be proven from persisted state; otherwise degrade/reject. Add mismatch tests for sidecar/source hash/frame/rotation/transform and text-only routes.

3. **Occurrence identity query ignores the occurrence.** Replace the current broad query with identity that is actually based on page artifact, source layer/hash, concrete range or replayable context anchor, sidecar/algorithm version as appropriate. Do not use only `target_id` or normalized target text. Prove two identical strings at different trusted ranges can coexist, while the same occurrence cannot be persisted again under another ID/target alias. A bbox must be identified by its source range, not by a guessed first match.

4. **Risk flags are not anchored to raw OCR.** Before persistence and on readback, verify every flag range is in bounds and `OCRPage.raw_text[start:end] == flag.text`; verify scan/flag raw hash and rule version mirrors. Add wrong-text, out-of-range, and hash/version drift tests. Scanning remains a sidecar and must not produce corrected text, facts, rules, or clinical decisions.

5. **Correction lineage/effective selection is inverted.** A superseding correction must bind the same OCR page, raw hash, and original range as its predecessor. A complete revision selects only the effective correction, not both predecessor and successor; selecting overlapping corrections is rejected even when one supersedes the other. Selecting the successor alone is valid if the external append-only lineage is valid. Require `base_processing_revision_id` for corrections and OCR risk reviews and verify it is a base revision in the same review episode/snapshot scope.

6. **Referenced-document resolutions can be orphaned or cross scope.** A resolution requires an existing referenced-document revision chain. Confirm trigger locator belongs to the same project/subject/review episode scope. In a complete revision, a `provided` source document must be a member of that revision's snapshot/manifest and same scope. Add orphan, cross-subject/episode, non-member, and cross-scope trigger tests.

7. **Incomplete complete revisions are currently activatable.** Enforce the frozen contract section 4.6 at the persistence boundary: a complete revision may be frozen only after structural closure is demonstrably complete. It must cover the snapshot member page set, have terminal successful page/OCR artifacts, bind per-page metadata and exactly one selected risk scan, resolve every blocking risk via a selected valid review/correction, require key correction confirmation, verify all locator/correction/reference scope and hashes, and verify association/payload/completion hashes. Do not create a half-complete row with `is_activatable=True`; failure stays a candidate state/event and creates no complete revision. Update the test fixture so the positive complete revision genuinely satisfies the closure instead of using empty sidecar lists.

8. Preserve all already-proven migration properties: exact 0009 payload/hash/page replay, child FK rows, WAL, FK/integrity checks, null pointer migration, and downgrade refusal. Do not weaken these tests to accommodate fixes.

## Verification Required

- Add focused regression tests for every item above, including the frozen composite sentence `ALT > 3×ULN 且 AST > 3×ULN，或总胆红素 > 2×ULN。` remaining text/hash-identical through risk persistence.
- Run the complete Slice 4.4A domain/storage/migration set, all existing 0008/0008a/0009 migration regressions, full `tests/v2`, Ruff on changed Python, best-effort production Pyright, and `git diff --check`.
- Return a compact report with exact changed files, tests/counts, any residual uncertainty, and why each root cause is now prevented. Do not self-accept or release WP-44B.
