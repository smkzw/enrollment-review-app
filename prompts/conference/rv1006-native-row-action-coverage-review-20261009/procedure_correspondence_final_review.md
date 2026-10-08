# C03 final bounded delta review

Read-only, no recursive delegation, tests, shell, writes, browser, or clinical source. Approved same-session engineering route, not new-model independence or clinical approval. Use at most eight direct reads. Previous report is evidence, not authority. No need to ask the user, create a task, or draft repairs.

Owner has addressed your mixed-sibling finding and did not accept the assumption that an empty early source question proves the later review has no source ambiguity.

Read complete affected definitions in:
- `app/agents/protocol_control_source_interpretation.py`: `SourceTargetReviewItem`, `validate_source_target_review` relevant new typed-cause gate, `build_source_target_review_prompt` and source-prompt context guidance.
- `app/services/protocol_control_restricted_source.py`: `_unit_statements_cover_source`, `procedure_correspondence_source_gaps`, `_whole_unit_restriction` and its actual caller.
- `app/services/protocol_control_execution.py`: `_validated_deep_partial_source` source-seed branch, `_deep_component_identity`.
- New procedure-correspondence/source-context tests in `tests/v2/services/test_protocol_control_execution.py`.

Changes: explicit optional `unresolved_cause` (source_ambiguity/target_correspondence/null), omitted on legacy serialization. A source question cannot be relabeled target_correspondence; non-unresolved items cannot carry a cause. Old/uncategorized new reviews remain interpretation_unresolved. Clear correspondence gaps can use consumer_unavailable only with explicit typed cause; a previously covered sibling retains its independence limitation instead of a false mapping failure. No adoption, copied approval, or invented dates.

Source-prefix omission stays refused: the same literal-range proof is used for whole-unit restriction and preflight. Only a witnessed, validated saved failed source/wire/review which lacks required source context is not reused as a complete source seed; only that failed batch is refreshed. Successful sibling receipts revalidate normally. New source reading is by the existing product reader, told to preserve directly applicable project labels/context or split independent statements, not code-filled scope. Old artifacts and calls remain immutable. Do not claim the private clinical failure is solved: a fresh read still has to pass current source and consumer gates.

Challenge: can the new source-gap detection hide damaged receipts as a miss, invalidate unaffected successes, label a real source uncertainty as software, or release an executable target accidentally? State exact code evidence/counterexample. Report unverified consumers honestly. A changed validator/compiler is recorded in current component identity, not substituted into old hashes; no version-string whitelist. Do not recommend increasing full-run budget to solve structure.
