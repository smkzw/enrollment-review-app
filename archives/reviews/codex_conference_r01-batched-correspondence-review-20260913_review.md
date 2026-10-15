# Codex Conference Review: r01-batched-correspondence-review-20260913

Date: 2026-09-13

## Verdict

Revise. Independent advisory pass completed; R01 and clinical acceptance remain open.

## Boundary Compliance

Read-only engineering review; no product model calls or clinical database changes. Runner reported grok/grok-build/grok-4.6 high, one round, no fallback, exit 0. The report identified the placeholder context correctly and used the concrete source set appended to its prompt.

## Participant Outputs Reviewed

Reviewed runs/conference/r01-batched-correspondence-review-20260913/evidence_single_object.md against the candidate code and r4 immutable artifacts. r4 is v2; parallel scheduling was v3 at review time, not the behavior measured in r4.

## Conference Panel Review

Accept: reference agreement does not establish object/attribute/time/source correctness; dates and excerpt text cannot be substituted for numeric values. Accept cancellation receipt gap and lack of real parallel latency evidence. Do not accept a blanket permanent ban on professional-judgment predicates or a new clinical unit mapping based on this review alone. Source degradation alone is not equivalent to unusable clinical evidence. Expanding isolated counterexamples is within existing authority, not a new user approval requirement.

## Main-Venue Codex Review

Retain current prompts and recorded model outputs. Add deterministic operand-shape audit to persisted unverified candidates; do not feed these into the evaluator. No clinical aliases, derived ages/durations, or auto-acceptance added. Do not rerun expensive models just to demonstrate scheduler overlap.

## Codex Independent Verification

85 focused tests passed (24.27s, five third-party SWIG warnings), including real JobRunner parallel barriers, local serial execution, cancellation receipt persistence, frozen-input contracts and operand shape. r4 read-only replay: 34 numeric values, 10 nonnumeric values, 10 time operands, one context-only reference; all 55 remain accepted=false, five carry unverifiable source. Replay artifact: r4/operand-shape-replay-v1.json. git diff --check passed. No new original-document clinical QC, UI acceptance or live model speed claim.

## Final Decision

Advisory findings integrated into isolated candidate job v5. Continue source-bound semantic verification and held-out assessment before any new automatic adoption. This is not R01/T1/Phase5.5 completion. No user decision is required to continue the already authorized isolation work.
