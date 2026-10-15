Delegated read-only delta review. No writes/tests/models/browsing/clinical data/
recursion; read only worktree source/synthetic tests. Max10 focused reads.

Frozen actual code delta after f42250c6 (not clinical adoption):
- attribution delimiter may be in the frozen source rather than in the verbatim
  attribution phrase; the complete prefix and source colon must still match.
- _has_new_attribution_label checks the ENTIRE intervening source, not just the
  final clause. Balanced-parenthesis colons and digit-to-digit time/ratio colons
  are not new labels. A generic discourse enumeration ending in 包括/包含/例如/如/
  如下 is not a new scope, unless its prefix contains 要求/标准/条件. Every other
  colon still stops the source frame. There is no disease/drug/threshold mapping.
- Existing study adoption check includes eligibility requirements/conditions as
  well as standards, so 入组要求包括 does not hide a study obligation.
- validator identity v2 only; source proposal and fresh SourceTargetReview remain
  necessary; no host closure, no changed force or prior-failure success.

Owner rejected the direction report's final-clause-only proposal: a changed label
in an earlier clause still changes scope. Existing synthetic negatives preserved,
new far-scope label and “入组要求包括：” negative, list/parenthesis/time positives and
fresh-target/candidate-conflict consumer checks added. Only affected family runs
now, no per-edit full-suite repetition. Actual source-only proposal validation
is a read-only diagnostic, never target review or publication.

Read final helpers, adoption branch, validator consumers and relevant tests.
Challenge whether the correction relaxes actual source/adoption boundaries,
especially earlier new labels or nested enumeration. Give concrete must-fix or
supported no-findings plus inherent semantic/unread limitations. A source grammar
gate is not a universal natural-language meaning proof; fresh target review must
still decide cited external vs unresolved. Do not expand the product framework.
