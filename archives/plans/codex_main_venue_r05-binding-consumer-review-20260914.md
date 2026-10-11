# Codex Main-Venue Plan: r05-binding-consumer-review-20260914

Date: 2026-09-14
Objective: Review receipt-derived frozen calculation selections: artifact vs logical hashes, actual persisted authorization, semantic rejection and population scope, immutable source equivalence, both official and control selection integration. Read-only source review, no tests/model/DB calls.

## Task Decomposition

One C03 read-only review of current consumer and shared receipt reconstruction; owner adjudicates findings and repairs, no runtime acceptance.

## Source Packet

Use the explicit current source set and criteria in the companion context, not worker reasoning.

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `grok-build` | `grok-4.6` | `runs/conference/r05-binding-consumer-review-20260914/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

Runner health preflight and 7200-second terminal wait. Do not redispatch progressing work. Actual result recorded after completion.

## Codex Verification Checklist

Check hashes, provenance, source-equivalence, complete identity accounting, default-disabled boundary and no silent loss of unresolved conditions. No staged tests, model calls or DB writes authorized.
