Read-only independent review of the current bounded patch against HEAD dd766bc3.

Hard boundaries:
- Do not edit, run tests/commands, access network/environment/databases/private clinical materials, or delegate. Maximum8 material reads in the seven source/test files below; return at most750 words.
- Codex owns integration and clinical acceptance. This is one reviewer, no chair/executor.
- Runner-managed report path: `runs/conference/rv1006-mixed-restricted-consumer-review-20261007/cell_label_patch_review.md`. Do not write this file; return your report.

Problem: frozen owned paragraph contains a schedule, while the immediately preceding paragraph in the exact same cell is a colon-ended project label. The source interpreter explicitly prohibited using its already-frozen context; it reported absent applicability and target review could not proceed. The patch introduces optional scope_context_unit_id, chosen by the semantic author. Physical .p indices must be adjacent, document/cell/member/heading/study identity equal, one frozen context reference only. The entire colon-ended label is quoted; action/condition-looking labels are conservatively rejected. This narrow label grammar is not proof of semantic applicability. The target reviewer must independently establish that relationship. No new object field, source concatenation, auto-filled meaning, calculation guard removal, automatic clinical adoption or old history change.

Challenge specifically: (1) Can a preceding action or another cell/phase/unknown context silently gain authority? Is any dangerous acceptance created by the syntactic predicate? (2) Do time/exception/stage remain grounded in original owned sources rather than this new context? (3) Does the reference survive correction, source serialization, restricted producer and full gate, without changing owned span closure? Same-unit executable independence cannot silently discard the new dependency. (4) Is ordinary source-target review supplied enough original context to check objects, not merely assert structural adjacency? Missing object or remaining ambiguity must stay unresolved. (5) prompt/v21 and gate/v47 change identity; no old source reuse or clinical success is yet claimed. Flag needed runtime/consumer/identity checks precisely rather than recommending a new framework or broadening guards.

Read these files only:
- `app/protocols/control_scope_sources.py`
- `app/agents/protocol_control_source_interpretation.py`
- `app/domain/contracts/protocol_controls.py`
- `app/protocols/protocol_control_gate.py`
- `app/services/protocol_control_restricted_source.py`
- `tests/v2/protocols/test_slice58c_control_deconstructor.py`
- `tests/v2/services/test_protocol_control_execution.py`

Read relevant complete definitions only: immediate_cell_scope_label; SourceStatement/SourceScopeCorrection and interpretation/correction/review prompts and validators; RestrictedProtocolControlStatement; _restricted_statement_scope_issues; independence proof and restricted_batch_from_review; _same_cell_label_source and new source/producer/gate/projection tests.

Grouped regression v1 found eleven failures: seven from owner's None normalization regression, three fixture/irrelevant schedule resolver failures, one prompt text assertion; fixes are now present, v2 is running. These are not clinical failures or grounds to loosen tests. Do not claim you ran tests, reviewed raw protocol or approved clinical meaning. Distinguish certain code defect from unproven hypothesis. At least one valid normal-result example and unsafe counterexample, plus remaining limitation, are required.
