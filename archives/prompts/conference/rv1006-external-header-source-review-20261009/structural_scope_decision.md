Delegated read-only engineering judgment. No writes/tests/models/browsing/clinical
data/recursion; only source and synthetic text here. Max12 focused reads.

New actual production observation (not acceptance): HEAD f42250c6 preserved26
completed batches zero-call, one new call stopped the same unit at statement1.
The source is one paragraph with an external-document colon header followed by
several population-specific lists containing “包括：”, then further warnings.
The author gives the same entire header WITHOUT its final colon for each list.
Our header gate currently treats every colon as a new title and requires the
attribution to end in a colon. Thus a true listing colon and harmless punctuation
omission stop a legitimate externally attributed paragraph. Old failures remain.

Synthetic faithful shape (no original names/medical values):
“某说明书安全性信息提示：甲类人群的常见反应包括：反应甲；乙类人群的常见反应包括：
反应乙。此外需特别注意其他风险（如：某风险）。”
Statement “乙类人群的常见反应包括：反应乙”, attribution “某说明书安全性信息提示”.
Required negative remains “注：某指南推荐：背景。入组要求：受试者须完成筛选期全部访视。”
Do not create a drug/disease-specific patch or presume every imperative is this
study's requirement. The existing fresh SourceTargetReview still must decide
external vs study meaning; source proposal or policy text alone cannot close it.

Examine current source-attribution validators and their direct review consumer.
Recommend the smallest coherent correction of source scope: distinguish sentence
enumeration punctuation from new scope labels, and attribution text from its
terminal delimiter, without forcing all external warnings into patient duties.
Consider whether an existing structural contract can express it more faithfully
than another ever-growing disease/heading regex. No new framework/model/DB or
wide prompt upgrade that forces26 success rereads. Give decisive positive and
dangerous negative examples, actual code touchpoints, and remaining semantic
uncertainty. This is a constrained direction review, not a repair or clinical
approval; no source data outside worktree may be read. Owner integrates/validates.
