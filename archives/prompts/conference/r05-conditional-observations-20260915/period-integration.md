Same-session read-only source review under the original bounded role and applicable instructions. Do not edit files, run/write tests, import code, access DBs, call product models, start services/browser, or inspect raw clinical records. Return the report to the runner.

A narrower adjacent complete producer-to-consumer slice is now implemented before larger retest relation work:
- app/domain/contracts/proposition_evidence.py v5 adds required nullable prospective_evidence: protocol requirement kind statement_of_intent/ongoing_conduct/unresolved + original protocol quote + statement period correspondence supported/partial/unresolved and quote. Non-period pairs must return null.
- app/llm/proposition_evidence.py puts the actual atom prospective_period in input and identity; verifies quoted protocol/record sources. Only an explicit intention requirement with supported entire period can return a definite relation. Ongoing conduct cannot be established by a promise and is unresolved. Original investigator/proposition/scope rules retained.
- job and summary v2, comparison v2, qualified proposition consumer v4 bind new method version. No new adoption approval, no calls.
- qualified_proposition_evidence.py retains specific period/conduct gap reasons per pair.
- control_calculation_experiment.py v10 checks both lanes for period proof before truth; records a statement-only note on definite result. control_operand_calculation.py still rejects future deterministic fulfillment; semantic time operand can be computed separately, never used as statement-period proof. Frozen evaluator v15.
- frontend/src/domain/reviewConditionNotes.ts renders specific Chinese notes, including definite statement != future completed action.

Audit exact full affected definitions and adjacent consumers. Focus on bypass of period guard, historical hash/read behavior, source/identity binding, current method authorization isolation, whether unresolved proof reaches the report and whether a statement can be misreported as continuous compliance. A passing source review is NOT product/clinical acceptance.

This slice intentionally does NOT implement official predicate prospective, event counting or retest relations. Do not present those as completed. Retest needs explicit source relationship, event counting needs occurrence semantics beyond stable_identity (two diagnoses might be the same episode despite different source dates; do not assume stable identity alone settles clinical dedup). Return actionable defects and minimum corrections, not proposals for a new parallel system.
