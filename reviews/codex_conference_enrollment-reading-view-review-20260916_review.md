# Codex Conference Review: enrollment-reading-view-review-20260916

Date: 2026-09-16

## Verdict

Revise. Advisory completed; formal view integration and clinical acceptance are not approved by this report.

## Boundary Compliance

Read-only engineering review, no clinical source or product-model call authorized. Participant expanded into adjacent source consumers; do not treat this as a clinical or visual inspection.

## Participant Outputs Reviewed

`runs/conference/enrollment-reading-view-review-20260916/evidence_single_object.md`; runner terminal exit 0, one round, codebuddy/deepseek-v4.1-flash, requested max, no fallback. Receipt remains in the task log directory.

## Conference Panel Review

Accepted: source hash and request-image hash must be separate when views are integrated; do not weaken repository source validation; persist view identity in jobs/records/recovery; declare coordinate units before any bbox use; add constructor invariants.

Rejected/corrected: experiment importer does exist in artifacts/mtplx-dual-basic-20260916/compare_effort.py, outside the reviewer's app/tests grep. No importer in those two roots does not prove none in the workspace. ReadingView already includes a version plus actual output hash, so absence of encoder-version field alone does not prove identity collision. Do not universally assert PageArtifact dimensions equal decoded pixels: page_processor may use native-page dimensions. Do not blindly adopt global historical invalidation or permanently remove bbox capability merely to simplify integration.

## Main-Venue Codex Review

Added direct-construction geometry/direction/hash-format/zero-turn checks and explicit image-pixel space. This is a deterministic precondition only. Source image bytes are verified by the factory; a directly constructed rotated view alone does not authenticate its relationship to source bytes. A future repository binder must re-derive/verify from the source. No formal consumer has been enabled.

## Codex Independent Verification

Earlier four-way pixel and full-bound checks plus actual frozen-image byte equality retained; current inline malformed-constructor checks pass. No new suite, browser, clinical QC or model run. Reviewed actual harness input hash checks and locator coordinate handling; record/job/recovery changes still pending.

## Final Decision

Proceed only with connected source/view identity and coordinate contract work. Keep original page authority, raw model responses and historical records. No automatic orientation claim and no publication of transformed model boxes as authenticated locators.
