# Codex Main-Venue Plan: r05-observation-selection-20260915

Date: 2026-09-15
Objective: 只读设计审阅：基于现有R3来源资格/命题/确定性计算，补齐官方及跨章要求的有限观察集合、最近/最早与复查选择通用闭环，提出最小完整实现，不把永久UNKNOWN或新未消费合同当完成。

## Task Decomposition

Use one independent source reviewer because observation choice changes clinical interpretation and current code leaves multiple observations unresolved; owner integrates the minimum complete change. No staged tests or live model calls.

## Source Packet

See conference context for the authorized source set. Current predicates lack observation policy; control policy supports single/any/all/unresolved. Review both families and their consumers before recommending extensions.

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `zcode` | `GLM-5.3` | `runs/conference/r05-observation-selection-20260915/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

Initialized, not yet dispatched. Runtime receipts determine actual route and terminal state; wait up to 120 minutes without redispatching a healthy session.

## Codex Verification Checklist

Verify source citations, explicit selection authority, finite-set evidence, ambiguity retention, end-to-end consumption, and no claims of clinical acceptance. Record adopted and deferred findings after terminal output.
