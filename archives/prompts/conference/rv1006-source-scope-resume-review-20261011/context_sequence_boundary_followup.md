# Existing source relation boundary review

Continue this approved read-only C03 session. No writes, product calls, clinical files, databases, env or personal history; no browsing or delegation. Return a compact source-based report, not a file. Same model family as product: engineering/context independence only, not clinical approval.

Owner has now replayed actual saved failure without new model or database writes. The action numeric guard is genuinely reached, but a prior source-purpose issue exists. The frozen batch has a preceding paragraph describing eligibility then randomized research treatment, followed by a table with study-treatment and ongoing background-treatment columns. The failed row contains a merged study-treatment cell and a separate background cell. No frozen pre-enrollment mapped target exists for this row. Original fields remain current_or_unknown. Current validate_source_interpretation and validate_source_target_review require the eligibility boundary quote to precede the action inside the SAME owned unit. The read-only context already includes the paragraph, but cannot form such a proof. Do not infer all treatment instructions are after eligibility or delete the numeric guard. Do not infer source ambiguity merely because the software cannot represent a relation.

Synthetic structurally similar source, not clinical text:
- Prior paragraph: "确认符合资格后，受试者随机接受试验制剂或对照制剂。背景治疗在筛选前已经开始并继续保持。两类用药见表甲。"
- Table headers: 项目 / 试验制剂 / 对照制剂 / 背景治疗.
- Row: 给药部位 / merged columns1-2: "给药者应在3个区域轮换" / column3: "指定区域".
- Counterfactual: same layout, but prior paragraph requires a study-treatment operation BEFORE eligibility confirmation; or the owned quote belongs to background rather than merged study cells; or table reference is to another table; or object/header source is missing; or genuine wording leaves timing unknown.

Minimal candidate approach to challenge (not implemented): extend the existing source sequence witness, not a new graph store, with explicit context-unit identity, exact boundary/object excerpts and the owned member/column source relationship. Host checks frozen identities, exact text, source order, table/member provenance and scope; a fresh source-target review independently challenges whether the quoted preceding qualification boundary actually governs THIS object/action. Author-only labels, headings, same visit date, a shared paragraph, or literal agreement cannot exclude a requirement. Unknown/capability gaps remain scoped non-executable only under existing R1 boundaries; known bad meaning is rejected.

Read complete affected definitions, not whole history:
- app/agents/protocol_control_source_interpretation.py: SourceStatement, validate_source_interpretation, build_source_interpretation_prompt; SourceTargetReviewItem, target_review_indexes, build_source_target_review_prompt, validate_source_target_review.
- app/domain/contracts/protocol_controls.py: ProtocolStructureUnit, TableCellContext and frozen batch.
- app/protocols/control_scope_sources.py: current native relation helpers; app/protocols/procedure_catalog.py only relevant row/member/header helpers.
- app/services/protocol_control_restricted_source.py: relevant whole-unit and statement restriction paths, to assess whether a precise unsupported relationship can legally use current R1 rather than masquerade as source ambiguity.
- nearest existing post-eligibility tests in tests/v2/protocols/test_slice58c_control_deconstructor.py.

Questions:
1. Is there already a usable source/consumer route that the owner overlooked? Cite it; prefer reuse to a new witness.
2. What is the smallest sufficient relation contract, if needed? Which checks prove only location and which still require source-based semantic review? A shared heading or exact drug name alone is NOT enough.
3. Is table-specific relation support actually necessary for this frozen window, or can the current source/target review plus precise R1 non-execution record avoid inventing a parameter consumer? Do not recommend fabricating unresolved fields or recategorizing a known erroneous candidate.
4. Identify positive, same-meaning layout, object/timing counterfactual and resumed-proof-invalidated checks. Name production/save/consumer requirements; a helper-only pass is insufficient.

Do not propose a new framework, queues, database, model or full-plan rerun. If this candidate is too broad, say why and propose a bounded alternative. Separate decisive source observations, uncertainty and optional improvements.
