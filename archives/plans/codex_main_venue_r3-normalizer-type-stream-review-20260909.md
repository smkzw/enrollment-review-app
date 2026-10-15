# Codex Main-Venue Plan: r3-normalizer-type-stream-review-20260909

Date: TODO
Objective: Read-only scoped engineering review of app/agents/evidence_normalizer.py (new identifier value_kind v21), app/agents/deepseek_evidence_normalizer_transport.py (GLM streaming), app/services/fact_normalization_job_service.py retry, scripts/run_isolated_page_revision.py and focused tests. Challenge identifier strings retaining leading zeros without weakening numeric measurement unit checks, partial stream rejection and resource release, request identity, retry state correctness, historical compatibility. Do not read clinical artifacts, env or credentials; do not call models/API or modify files. Report concrete severity/file/line findings and minimal fixes; no clinical acceptance. Product remains own HTTP harness GLM+Gemini. One independent reviewer only, no fallback.

## Task Decomposition

TODO

## Source Packet

TODO

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `zcode` | `GLM-5.3` | `runs/conference/r3-normalizer-type-stream-review-20260909/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

TODO: Record start/end time, pending/failed/incorporated status, retry reason, and whether late outputs were used.

## Codex Verification Checklist

TODO
