# Codex Execution Review: phase5-slice58a-full-protocol-contracts-20260824

## Verdict

Accept with Codex remediation. Phase 5.8a is accepted; Phase 5.8b is accepted only for the deterministic full-structure inventory skeleton, not candidate disposition or publication.

## Worker Outputs

- `worker_01` created the coverage/candidate/published domain separation, six typed obligation atoms, explicit review-node roles, cross-source relations, source closure and pseudo-official-code rejection.
- `worker_02` created the deterministic inventory builder but incorrectly used the single-phase projection as a membership filter and retained only the first cell locator for a table row.
- `worker_03` added focused counterexamples and correctly surfaced that a BODY source-span override could hide a missing phase-graph block.

## Manager Assessment

Codex rejected projection-filtered membership. The selected phase now fixes project identity only; all non-empty BODY paragraphs and supported annotations enter the inventory. Projection-external `UNKNOWN` and `MIXED` units remain visible for disposition. BODY omissions from the phase graph fail even if a source-span override exists; footnote/endnote/textbox units may enter as `UNKNOWN` only with explicit source spans.

Codex also replaced first-cell table provenance with complete row member refs, cell paths and source spans, preserved multi-level heading paths, and fixed innermost nested-table root parsing after the real D001 document exposed outer/inner row merging.

## Boundary

This acceptance is limited to deterministic domain contracts and the unclassified full-structure inventory skeleton. It does not accept Agent candidate disposition, publication, persistence, APIs, UI, subject assessment, or clinical conclusions.

## Hermes

Hermes was not used. The live route selected Cursor CLI `auto` for three bounded execution workers; all completed without fallback. Codex independently reviewed and remediated their output.

## Codex Independent Verification

- Focused full-protocol contract suite: `24 passed`.
- Complete `tests/v2/protocols`: `512 passed, 58 warnings`.
- Real read-only D001 II inventory: 3,581 extracted blocks, 3,405 phase-graph blocks, 513 projected blocks, 1,689 inventory units; all 13 rows of table 5 retained. The inventory deliberately preserves 785 `UNKNOWN` and 25 `MIXED` units for later disposition and does not claim completion.
- `compileall`, `git diff --check`, and Trellis task validation passed.
- No Agent semantic extraction, published control catalog, database write, browser acceptance, subject review, or independent tester run is claimed.

## Cleanup Decision

Run execution audit and review gate. Preserve compact runner reports and the acceptance checkpoint; process cleanup may archive redundant stdout after audit according to the workflow guard.
