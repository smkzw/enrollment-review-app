# Codex Conference Review: r05-control-publication-20260914

Date: 2026-09-14

## Verdict

Revise and implement; independent source review received, not product acceptance.

## Boundary Compliance

Read-only advisory pass, no clinical files, database access, model recognition or tests authorized. Runner terminal 0; actual zcode/zcode/GLM-5.3 max, no fallback, session sess_89d216c1-814d-4852-83f5-dc2792cf835f. Parent wait 12367/2575 completed. Report is engineering advice, not clinical sign-off.

## Participant Outputs Reviewed

`runs/conference/r05-control-publication-20260914/evidence_single_object.md`; actual route receipt in `logs/conference/r05-control-publication-20260914/evidence_single_object_stdout.txt`.

## Conference Panel Review

Confirmed candidate-only final checkpoint and lack of persisted formal control consumption. Accepted preservation of applicability/trigger/obligation/exception DNF and modality; do not flatten controls into new official IN/EX rules or generic exists predicates. Shared requirements and page-reading inputs must eventually include controls; side-only display is not sufficient.

## Main-Venue Codex Review

Further source inspection corrected the owner's initial namespace assumption: control source nodes use a hashed stage/visit ID, whereas deconstruction drafts use a separate stage ID; publication namespaces the draft ID, not the control ID. The bridge now uses frozen procedure item identities, ProcedureCatalogMapping source references and requirement membership, with stage/visit consistency checks and exact draft-to-published content verification. Original catalog IDs remain unchanged. Matching by labels alone is rejected. Also rejects treating nonempty catalog validation alone as clinical approval or omitting failed candidates with a scope note to obtain a passing catalog. The materializer copies all hydrated candidates without semantic rewriting and reuses the existing full gate; any rejected candidate fails construction. Storage and an optional atomic publication path have since been implemented; downstream consumers and final verification remain required.

## Codex Independent Verification

Read complete relevant candidate semantics and control/catalog definitions, _execute_gate, _validate_control and final gate source loop, and _published_workflow_stages. New materializer only compiled; no staged tests per user instruction. Its implementation postdates this advisory pass and is not covered by reviewer acceptance. No original DB or protocol changed.

## Final Decision

Proceed with existing immutable publication and full-fidelity controls, not a replacement rule engine or queue. Do not mark R05, T3/T5 or claims_complete closed. Whole-system runtime, model and clinical checks remain pending.
