# Codex Main-Venue Plan: r06-inheritance-review-20260913

Date: 2026-09-13
Objective: 独立审阅事实跨运行继承实现：严格来源闭包、更正排除、重复发布及下游引用，发现具体反例；只读不修改

## Task Decomposition

One read-only reviewer challenges the frozen provenance change. Codex verifies concrete findings and implements only supported fixes; no patient data is changed.

## Source Packet

Use the source set and boundaries in the paired conference context, not earlier model recommendations.

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `grok-build` | `grok-4.6` | `runs/conference/r06-inheritance-review-20260913/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

Runner receipt owns start/end and runtime identity. Await terminal state with 7200-second limit; no redispatch of a healthy pending run.

## Codex Verification Checklist

Inspect findings against source; verify source closure, corrected fact exclusion, three-run replay and adjacent consumers with deterministic tests. Product and clinical acceptance remain open.
