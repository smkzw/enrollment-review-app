Continue same read-only C03 session with the same boundaries: no edits/imports/tests/app/database/model/network calls or delegation. Inspect current source.

Owner decisions on preceding review:
- F1 not adopted: different observations having different truth values is not itself a conflict under an explicit ANY/ALL policy. Per-observation truth is retained. Same-fact relation disagreement and actual source conflict groups remain UNKNOWN. Do not create a clinical conflict merely from mixed truth values.
- F2 confirmed as pending evaluation/approval; no gate signed, no application/database run, claims_complete=false.
- F4 fact check: proposition_method_evaluation.py already has independent version proposition-evaluation-manifest/v1, not the quoted judgment version.
- F5 read amplification acknowledged, not yet optimized without measured execution evidence.

F3 follow-on is now a narrow source fix: BINDING_QUALIFICATION_PROMPT_VERSION v4 explains that semantic/investigator_judgment value/assertion_basis may be a direct textual source, not a numeric operand. validate_binding_qualification_structure marks bound_assertion_for_proposition only for non-deterministic specs and value/assertion_basis with compatible declared attribute, requiring fact.assertion_basis.locator_id == pair.locator_id. Other paths unchanged. Exact body/source policy checks and every strict source rejection remain; proposition relation independently read and version-approved. This does not authorize evidence without a source or make a relation final eligibility.

Inspect app/services/binding_qualification_support.py around validate_binding_qualification_structure, app/llm/binding_qualification.py prompt and validator, app/domain/contracts/binding_qualification.py version, and qualified_binding_selection.py new relation selection. Identify real regressions/unsafe acceptance or missing adjacent version consumers. Source-only compile has passed, no staged tests. <=45 lines; distinguish evidence from advice.
