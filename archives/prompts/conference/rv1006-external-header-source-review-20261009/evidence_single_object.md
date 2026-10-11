Delegated bounded read-only engineering review. No edits, model calls, browsing,
clinical data, tests or recursive delegation. Use only this worktree's source and
synthetic tests. Do not retrieve private reasoning or read /Users/smkzw/tmp.

Question: does the proposed source-attribution boundary incorrectly hide this
study's requirements, or reject source-supported paragraph-header attribution?

Frozen delta from HEAD7a902e87:
- app/agents/protocol_control_source_interpretation.py: document-type attribution
  now includes package inserts and generic reporting verbs. The common helper
  _attribution_in_source_scope retains the old same-sentence path; a second path
  accepts a unique, verbatim colon-ended prefix at the start of the same owned
  source unit, only before the unique statement, without intervening study
  adoption or another external attribution. Source authority must still be
  explicitly proposed and confirmed by existing SourceTargetReview. Candidate
  conflicts, source ambiguity and target fields remain rejected.
- app/services/protocol_control_execution.py: only the validator identity changes,
  not prompt/schema/compiler identity. Successes must undergo current gates;
  failed attribution output is not turned into a prior successful receipt.
- tests/v2/protocols/test_slice58c_control_deconstructor.py: existing dangerous
  negatives retained; synthetic colon-header sentences/semicolons/whitespace,
  changed authority, study adoption, duplicate statement, missing attribution,
  and actual Runner/target review consumers added.
- tests/v2/services/test_protocol_control_execution.py: exact identity expectation.

Read complete affected definitions and necessary consumers, max16 focused reads.
Challenge source boundaries, header scope, falsely omitted obligations, stale
reuse, and downstream review consistency. No need to repeat previous temporal
recommendation review or redesign the general framework. Report severity/file/
line with a concrete positive or negative case for must-fix findings, or supported
no-findings with residual/unread limitations. Do not claim clinical acceptance or
model independence. Real latest job stopped before this fix; no joint publication.
