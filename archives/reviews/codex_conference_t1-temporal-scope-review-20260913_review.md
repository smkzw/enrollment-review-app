# Codex Conference Review: t1-temporal-scope-review-20260913

Date: 2026-09-13

## Verdict

Revise. Reviewer completed; T1 not accepted.

## Boundary Compliance

One C03 read-only zcode/zcode/GLM-5.3/max, no fallback. No product inference or clinical database access; owner retained integration.

## Participant Outputs Reviewed

Reviewed `runs/conference/t1-temporal-scope-review-20260913/evidence_single_object.md` and actual JSON runner receipt. Output SHA256 edc0f30d434a8f88b4ca2d2a49d5231c4551a28f1f4e2a323e9cbfadbc7f3ec4. Session sess_6be6d92a-310d-49ef-b9ce-f70a1628b390, one round,881.98 seconds.

## Conference Panel Review

F1 accepted: all-outside FALSE conflates stale assessments with failed temporal requirements. F3 representative value restored only for a unique normalized value. F5 six all-outside regression cases retained as strict expected failures, not acceptance. Reviewer183 tests and owner201 tests have different scopes.

## Main-Venue Codex Review

Do not weaken decision-gap matrix. Trial blanket all-outside UNKNOWN regressed nine existing calendar/interval/node contracts; removed that trial. Need a versioned temporal-purpose/evidence-selection contract preserving old rule hashes and explicit new semantic output. Reuse source_validity_window where authoritative, but never infer purpose from disease/drug/comparator alone. F2: differing values with unknown dates need not be contradictory (may be different periods), so do not add source_conflict blindly. F4: equal values alone do not prove duplicate observations; current conservative UNKNOWN is provisional pending explicit observation matching/quantifiers.

## Codex Independent Verification

Initial new suite5fail/2pass; after temporal filtering201pass. Blanket UNKNOWN trial9fail/198pass. Current six-file subset201pass/6strict-xfail, with no clinical run or UI acceptance. Current patch fixes candidate filtering and order dependence, not the full temporal contract or broad alias defect.

## Final Decision

Goal and T1 remain active. Next implement explicit temporal purpose and evidence scope across semantic contract, evaluator and expectation consumers, retaining real washout/dated-event semantics while requiring current evidence for assessments. Remove xfails only after root-cause repair; follow-up independent review must check the revised artifact. claims_complete=false.
