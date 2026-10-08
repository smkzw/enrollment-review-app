# Codex Conference Review: rv1006-unexecuted-source-lineage-20261008

Date: 2026-10-08

## Verdict

Revise; independent pass completed. Owner adopted checkpoint pin and no-call-on-lost-proof, with connected verification pending.

## Boundary Compliance

Actual Grok/grok-build/grok-4.7/high, session 7ded3405-597e-4010-a17a-79c4b643daaf, 733.312s, exit0, no fallback. Runner receipt records end_turn and a resident actor warning; useful complete report exists. No clinical/runtime reads or test execution claimed. The report gives bounded code reads; exact tool/read count was not independently extracted. Owner waited through completion without redispatch.

## Participant Outputs Reviewed

runs/conference/rv1006-unexecuted-source-lineage-20261008/evidence_single_object.md, reviewed as advice against source, not approval.

## Conference Panel Review

Accepted concrete gap: root latest-checkpoint identity must remain frozen from intake to execution. Added source_checkpoint_proof from the actual raw checkpoint, current payload hash verification, explicit refusal if reusable revalidation returns no result. Added valid failed_final/queued shape, substituted otherwise-valid receipt identity, and lost validation counterexamples. No sibling history search.

## Main-Venue Codex Review

Not adopted: a hypothetical newer off-pointer sibling should veto declared provenance; that would require arbitrary history selection. Actual read-only preflight resolves step12 to the declared ancestor's failed_final partial proof, not completed. A new intake may revalidate actual current root state; no queued row is itself acceptance. Integrity mismatches remain hard failures. Objective pin/normal usability checks are owner-verifiable; no further interpretive uncertainty currently requires an additional model pass.

## Codex Independent Verification

Read-only actual latest-job preflight: 10 reusable (2-11), two partials (1 and12), 78 refresh; all 11 inherited ranges point only to declared bb59749a root, zero calls/writes. Six original synthetic JobStore/Runner cases passed before pin; extended connected window initially 1099pass/15fail: ten raw-vs-derived checkpoint pin defects fixed in product; five old FakeStore instances lacked payload_sha256 and were fixed without relaxing validators. First collection attempt had wrong test-directory names (exit4), not tests. New final connected window pending. No UI or clinical acceptance for this patch.

## Final Decision

Owner integrates bounded recovery: connected v3 1098pass/16fail were two FakeStore families missing hashes, fixed; affected final31passed/15.95s/exit0, includes all failed families and normal/negative runtime consumers. Root-corrupt test now injects immediately before the deep step, not discovery. No claim of a full final-suite rerun. Next new legal isolated Job must independently freeze actual raw checkpoints at intake. claims_complete=false, no joint publication/activation/signature implied.
