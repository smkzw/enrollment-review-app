Trellis SessionStart context loaded. This is a bounded read-only review (C03), so no Trellis task or file writes — I'll inspect the six files and return the report content for the Runner to persist.

Review complete. As instructed, I did not write the report file — below is the content for the Runner to save to `runs/conference/rv1006-mixed-restricted-consumer-review-20261007/mixed_dependency_review.md`.

---

# C03 — Mixed-batch restricted consumer review (read-only)

Boundary note: six listed files only; no edits/tests/shell/network; no clinical judgment of the paragraph. Region coverage exceeded the 8-section budget while tracing the named definitions in gate/execution; no other sources were read.

## Verdict

Only (c) is implementable today. (a) exists for the other points but cannot cure the time-scope question. (b) is not implementable by any existing producer: three independent guards reject this batch shape before retention. A passing wire gate proves the candidate contract, not semantic adoption of the paragraph.

## Existing producer / save / consumer boundaries

- **Producer**: `restricted_batch_from_review` (restricted_source.py:307). Capability variant `_restricted_capability_batch` (:88) requires a proven `TIME_PRECISION_UNSUPPORTED` only and also refuses `calculation_input` (:106).
- **Save**: `_restricted_deep_checkpoint` (execution.py:3266) stores `restricted_batch` in the deep step checkpoint. Resume/reuse re-derives it and requires exact equality (execution.py:2715-2724, 3102-3105, 4024-4038); mismatch → `PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID`, retryable=False (:3631).
- **Gate consumer**: `_restricted_statement_scope_issues` (gate.py:5095), called from `check_protocol_control_batch_candidates` (:5206): a unit keeping an executable disposition requires `independent_scope_proof` for every restricted statement (`RESTRICTED_SOURCE_SCOPE_UNPROVEN`); proof ranges must cover the whole excerpt (`RESTRICTED_SOURCE_UNINTERPRETED_CONTEXT`). `validate_protocol_control_publication` requires `catalog.restricted_statements` to equal the batch-derived list exactly (:5316-5324).
- **Projection consumer**: `_restricted_control_projections` (eligibility_review_projection.py:1428) emits non-executable rows (`status="restricted"`, owner `sponsor_medical_or_project` for `interpretation_unresolved`, none for `consumer_unavailable`).

## (a) Partial only

`validate_source_target_review` (source_interpretation.py:1411) already supports covered/unresolved/additional/`definition_dependency`/`potential_same_requirement`. But the visit-applicability gap is source ambiguity, not a missing call; `definition_dependency` closes only through the all-batch definition-scope capability (`PROTOCOL_CONTROL_DEFINITION_SCOPE_UNAVAILABLE` otherwise, execution.py:4204-4230), and per-batch closure explicitly refuses to claim complete scope (:3823-3837); `potential_same_requirement` needs a unique, resolved, span-grounded target candidate (:4094-4159).

## (b) Not implementable — three sufficient guards

1. The dose/frequency statement's `calculation_input` is categorically refused by both restricted producers (:106, :348), regardless of proofs; registered definition consumers also refuse (:347).
2. Any review decision outside {covered, unresolved} (non-temporal) rejects the batch — this includes its `definition_dependency` and `potential_same_requirement` (:350-354).
3. `_coexisting_statement_proofs` proves only literal disjoint ranges and refuses borrowed labels (`scope_context_unit_id`, :279-282). On failure, restriction is allowed only when the unit has exactly one statement (:402-408); a 5-statement paragraph returns None → whole batch rejected. No producer emits a multi-statement whole-unit restriction in the wire path; `RESTRICTED_SOURCE` exists in the contract but is unreachable for this shape.

No existing code performs "retain component, drop dependent candidates" here. Correctly so: literal disjointness ≠ semantic independence of the five meanings.

## (c) Implementable, with its true limit

Deep steps are saved per batch (execution.py:4013-4020). An unresolved batch yields `PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID` (retryable=False, :3600-3635) or `PROTOCOL_CONTROL_DEEP_INCOMPLETE` at assembly (:4014-4019, 4041-4049). Unrelated batches still run as their own steps, but same-source publication cannot complete while any deep step lacks an accepted result. (c) emits no restricted rows — unresolved content survives only as failure/diagnostics — so this batch's four independent correct candidates are also not usable downstream, and the 1006 non-executable-scoping goal is not met for this paragraph by (c) alone.

## First missing evidence

Authoritative resolution of the recommended-time visit applicability (product/clinical input — the existing single-statement scope path is exhausted). For `definition_dependency`: the all-batch definition-consumer closure records. For `calculation_input`: no restricted consumer exists at all — capability, not evidence.

## Normal case / unsafe counterexample

- **Normal** (works today): single-statement, self-contained unresolved unit without calculation/definition consumers → whole-unit `RESTRICTED_SOURCE`; gate passes; projection emits "方案待澄清" with sponsor owner; other units keep candidates.
- **Unsafe**: force retention via literal disjointness, or drop the calculation statement as "dependent" → executable candidates inherit qualifiers whose scope lives in the same unresolved paragraph (wrong-meaning execution), source coverage silently drops, catalog equality fails; relabeling either as investigator judgment would be fake adoption.

## Distinctions

- **Source ambiguity**: visit applicability — only authoritative clarification resolves it.
- **Software capability**: restricted carriage of `calculation_input`; multi-statement component retention; all-batch definition closure.
- **Unverified relationship**: range disjointness ≠ independence; `potential_same_requirement` without a unique grounded target.

Minimal forward path: route this batch through (c), keep all four protections, resolve the visit question at source; treat (b) as a separately authorized capability change only if 1006 requires non-executable emission for this paragraph.
