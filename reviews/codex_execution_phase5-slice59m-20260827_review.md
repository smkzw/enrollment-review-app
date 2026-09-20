# Codex Execution Review: phase5-slice59m-20260827

## Verdict

Accept this bounded slice after Codex remediation and independent runtime verification. This does not close Phase 5.8d or the D001 protocol corpus; `claims_complete=false` remains mandatory.

## Worker Outputs

- Worker 01 established the dedicated strict-Schema MTPLX control transport. Codex retained its route, model identity, zero temperature, no-fallback and same-session history boundaries.
- Worker 02 corrected durable history so internal length/empty-body retries cannot create an invalid `user,user,assistant` sequence. Its focused tests passed.
- Worker 03 correctly reported the first live Schema blocker and did not claim clinical acceptance. Its initial replay was diagnostic only; Codex repaired the shared Schema path and continued the same bounded representative scope.

## Manager Assessment

No execution manager was declared for this route. Codex performed the required integration review. The delegated workers used the effective `cursor-cli/auto` execution route; the product-internal semantic call independently used the exact `mtplx-qwen38-27b-optimized-quality` model with `medium` reasoning. These identities are not conflated.

## Codex Independent Verification

1. The final immutable replay is `artifacts/phase5-slice59m-d001-table5-mtplx-control-replay-bounded-repair-20260827/`.
2. Product MTPLX returned two responses in one session. Attempt 1 was rejected with `PROSPECTIVE_PERIOD_UNSUPPORTED`; attempt 2 repaired the direct source for the unchanged study-period endpoint. Final publication gate: 4 candidates, 4 controls, accepted, zero issues.
3. Codex rejected an earlier technically green replay because the repair rewrote three unaffected candidates. The shared runner now compares hydrated output against the pre-repair snapshot and raises `REPAIR_SCOPE_ESCAPE` for any unapproved candidate or disposition drift.
4. In the accepted replay, all three unaffected candidates and dispositions are field-for-field identical before and after repair.
5. Frozen Table 5 rows were checked directly: 6-month IL-12/17/23 biologic window; leflunomide 24-month default and clearance-activated 6-month substitute; 3-month or 5-half-life longer-of rule; 4-week systemic-treatment default and 2-week herbal local substitute. All use the first-dose anchor, lower-bound semantics and study-period endpoint.
6. Focused regression: `75 passed`. Full protocol regression: `823 passed, 58 warnings`. Compilation and JSON validation passed.

## Cleanup Decision

Archive governed process files after review-gate and execution-audit acceptance. Preserve immutable success and rejected diagnostic replay artifacts. Remove only the unregistered follow-up prompt and ordinary caches; do not delete clinical failure evidence.

## Boundary And Hermes Accounting

- This execution packet declared no separate manager and did not route a worker through Hermes; the guard-selected effective worker route was `cursor-cli/auto`.
- Product MTPLX calls are application runtime evidence, not execution-worker identity and not a Hermes fallback.
- Acceptance is limited to the dedicated transport, bounded repair behavior and four frozen Table 5 representatives. It does not authorize the remaining 128 packages, subject review, browser work or visual testing.
