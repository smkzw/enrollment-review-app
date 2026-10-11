# Codex Execution Review: phase5-slice60zn-authoritative-target-excerpts-20260828

## Verdict

Accept after Codex remediation. This accepts the authoritative-target excerpt
pipeline only; it does not accept or publish the D001 laboratory group.

## Worker Outputs

- Worker 01 correctly located the missing catalog-to-planner handoff and the
  legacy catalog-hash migration risk.
- Worker 02 implemented the optional catalog excerpts and both builder paths.
- Worker 03 added the initial span/excerpt, legacy and planner regression set.

## Manager Assessment

No execution manager was declared. Codex retained acceptance ownership and
revised two worker assumptions after real-protocol verification:

- source IDs and excerpts must be sorted as pairs, never independently;
- a textless table-root span is a valid structural locator, so a partial target
  uses a `null` placeholder instead of dropping the locator, fabricating text,
  or clearing every exact excerpt.

Legacy catalogs without the new field retain their previous content hash.
New catalogs hash non-empty or partially populated excerpt arrays.

## Codex Independent Verification

- Focused catalog/planner/Agent/schema regression: `143 passed`.
- Full protocol and contract-artifact regression: `974 passed, 58 warnings`.
- Direct DOCX chains for CMS-D001 and MG-K10-SAR both completed extraction,
  rendering, source alignment, phase projection, catalog freezing, control
  planning and Agent prompt construction.
- D001 EX-20 prompt context contains the exact ALT/AST/total-bilirubin threshold
  and the investigator unacceptable-risk conjunction; GGT is absent from that
  official rule text.
- The first broad run exposed MG-K10 table-root excerpt loss and failed. The
  structural-null repair was applied before the successful broad rerun.
- Python compilation, generated contract parity and `git diff --check` passed.
- Governed execution route audit passed; all three workers used
  `cursor-cli/auto` without fallback.

## Cleanup Decision

Archive runner-owned prompts, logs and worker reports after the checkpoint and
review gate pass. Retain the compact review, checklist, checkpoint and real
protocol regression. No model response or clinical acceptance artifact exists
for package 70-71 yet.

## Boundary

The Hermes-governed execution accepts only the shared source-excerpt transport
mechanism. D001 package 70-71 has not called the semantic Agent, package 68
remains unaccepted, and Phase 5 remains incomplete.
