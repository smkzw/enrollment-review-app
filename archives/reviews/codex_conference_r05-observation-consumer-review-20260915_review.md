# Codex Conference Review: r05-observation-consumer-review-20260915

Date: 2026-09-15

## Verdict

Source revision integrated after three same-session reviews; whole-product/clinical acceptance remains unverified.

## Boundary Compliance

Read-only source review. No reviewer source changes reported; no staged tests or product/DB/browser calls authorized. Actual zcode/zcode/GLM-5.3/max, no fallback.

## Participant Outputs Reviewed

Read complete `runs/conference/r05-observation-consumer-review-20260915/evidence_single_object.md` and runner receipt. Session `sess_a2528a41-f1dd-496b-9ffe-07f3d26e89d9`, returncode 0, 448.226 seconds.

## Conference Panel Review

F1 verified and fixed: require review context only for ordered selection using conflict groups, not plain any/all. F2 verified and fixed: distinguish source-required order from successful selected records while retaining excluded observations. F3 remains open source-validity ordering, distinct from conditional retest; do not equate the two. F4 fact-vs-attribute conservatism intentional and documented. Broad F5/F6 PASS is only a limited source review, not runtime evidence.

## Main-Venue Codex Review

Owner checked changed definitions, preserved old optional serialization and version boundaries. Additionally rejected ordering audit in model AssessmentCandidate: only receipt-backed publisher may attach it. No clinical adoption issued. Control audit/report propagation and richer temporal/retest policy remain pending.

## Codex Independent Verification

Python compilation, TypeScript noEmit and diff whitespace checks only. User explicitly defers tests to full construction. No runtime evidence or browser/clinical acceptance claimed; final minor repairs postdate this review.

## Final Decision

Read integration.md and window-policy.md fully. R2-F1 fixed with explicit source-backed window_order rather than hardcoding either latest-valid or latest-overall; missing/unclear order remains unresolved. Consumer11 isolates old method, fields_set omission preserves historically absent selected IDs while explicit empty selections stay hash-stable. Control outcomev3 records all four layers and report/source/export includes exclusions without treating them as adopted facts. R2-F4 symmetrical fact membership check added. Third review reports no new FAIL, but semantic source accuracy and all runtime remain UNVERIFIED. Its N1 overlooks the existing control schema recursive required normalizer; nullable window_order was nonetheless removed via shared provider schema. Minor historical note contradiction also fixed after review. No extra runtime or approval. Conditional retest remains next scope; no pause or phase completion.
