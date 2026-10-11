# Codex Conference Review: r3-normalizer-input-review-20260906

Date: 2026-09-06

## Verdict

Pass as engineering advice only; clinical acceptance remains incomplete.

## Boundary Compliance

Read-only source-code review; no product inference, patient artifacts or credentials requested. One declared node completed, no fallback.
Hermes was not used as the product harness or reviewer; the legacy-named workflow guard dispatched ZCode for engineering advice only.

## Participant Outputs Reviewed

general_single_object.md, SHA256 139fe7ad56fe8a141263a6700fa23e5354a30b7c2035dc6fecb4d2592c69d448; session sess_60219b2b-2872-41c3-be3f-f1ca9017058c, model/effort verified by runner.

## Conference Panel Review

Confirmed H1 missing real-runner source validator directly in code. H2 input duplication confirmed; contributor's causal ranking remains a hypothesis, not proof of the timeout cause.

## Main-Venue Codex Review

Shared post-parse validator implemented, including explicit accepted-source checks. Adopted conservative pending-input compression first, not automatic bypass or new persisted gap semantics. Model and budgets unchanged. JSON-schema transport change not adopted without capability verification.

## Codex Independent Verification

113 regression tests passed. Real-runner-shaped tests reject empty/pending/fabricated refs and accept bounded repair with valid refs. Read-only live frozen-input audit reconstructed all 14 groups; the single persisted candidate passes source-reference checks, not clinical QC. No UI changes in this revision, no clinical acceptance claimed.

## Final Decision

Accept H1 fix and source-preserving compression. Larger deterministic pending-item preservation plus explicit no-model audit path requires a coherent contract revision before implementation; do not blindly resume failed old job under changed prompt behavior. Preserve failed response evidence and claims_complete=false.
