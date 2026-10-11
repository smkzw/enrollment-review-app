# Bounded same-session engineering review

Hard boundaries:
- Read only inside the declared worktree; no source edits, tests, credentials, clinical artifacts, network or recursive delegation.
- Do not write the runner-managed report path `runs/conference/rv1006-source-dependent-restriction-20261009/evidence_single_object_followup.md`; return the complete report for the runner.

Continue the same read-only assignment and route. No edits, tests, network, raw clinical artifacts, credential reads, or delegation. Return the report to the runner. Read only relevant complete definitions in the files below; their current code baseline is b8a6f564 (owner verifies actual HEAD). Your prior review did not verify git HEAD. Same model family means context/process separation, not model-independent clinical evidence.

Initial read set:
- `app/agents/protocol_control_deconstructor.py`
- `app/services/protocol_control_restricted_source.py`
- `app/agents/protocol_control_source_interpretation.py`
- `app/agents/protocol_control_candidate_alignment.py`

Actual new run finished, no clinical details provided: 43 success ranges reused without models; the failed range made seven calls, then stopped. Newly added co-cited context appeared only in the administrative statement request. The four exception/definition findings were reused from the older failure checkpoint as additional_requirement; they therefore never got the new context. Invalid insertion attempts followed. Current previous_covered includes cross-run non-unresolved review items regardless of whether they are positive coverage or a still-unresolved increment. Successful adopted ranges are not the proposed target.

Please challenge this minimum repair proposal:
1. Do not reuse additional_requirement as a completed comparison in a resumed partial run. Positive frozen coverage remains reusable; proven alignment removes already-complete pairs from pending review. Recheck only the still-pending increment through current prompt, no whole author/protocol read. Verify actual call sites/recovery budgets and counterexamples.
2. If additional units and unresolved units are explicitly co-cited by one current candidate, refuse unit-scoped insertion rather than pretending their meanings are independent. Retain the source and valid baseline, typed unresolved correspondence. This does not broaden all exceptions into definitions and does not promote the pending diagnostic.
3. For R1 whole-unit retention, consider a CONSERVATIVE citation closure, not selective semantic dependency inference: seed actual unresolved units; repeatedly include every owned unit of any candidate intersecting that set, including any independently-looking candidate sharing those units. Every intersecting candidate is non-executable; no purported administrative sibling is kept executable inside the closure. Outside candidates/units retain their existing verified state. Every restricted source unit must have complete literal statement coverage, owned frozen source identities, valid dispositions and hydrated author output; foreign citations, incomplete source, transport/schema/wrong-semantics failures still refuse. No atom-level independence claim, no inferred dependency_refs, no clinical decision from co-citation. Is this bounded closure safe enough to avoid the missing cross-candidate identity proof identified in your first review? Does any consumer need extra validation beyond existing source_definition consumer registration and full gate?
4. Existing whole-unit comparison requires exact source_statement_coverage equal to raw recomputation; legitimate semantically_aligned entries differ. Proposed fix verifies immutable alignment proofs with the existing validator, then reconstructs ONLY the runner's exact coverage mutation (status and candidate indexes for fully_expressed), and compares to saved coverage. Bad hashes/foreign candidates/rejected items cannot authorize mutations. Evaluate the complete validators, not mere model decisions.

The closure is broader-than-necessary non-execution when independence is not proven, NOT an assertion of medical dependency. Do not erase the existing procedure/multiple-statement proof gate without an explicit verified closure condition. Closure-added parents should be technical independence gaps; original genuine source ambiguity stays labeled as such. Preserve every quote/version, no source rewritten to manufacture closure. If any missing proof makes this approach unsafe, identify the first counterexample and the smallest alternative rather than redesigning the platform.

Return concise findings with file/function evidence, risks and positive/negative/recovery/consumer tests. Explicitly distinguish evidence, inference, recommendation and limitations. No final acceptance.
