# Codex Main-Venue Plan: r05-observation-consumer-review-20260915

Date: 2026-09-15
Objective: 只读审阅通用观察政策、逐事实范围对账、确定性排序与any/all消费、报告未选记录的来源和历史兼容；禁止运行测试、产品、模型、数据库或浏览器；不修改源码，仅出具具体证据与修订建议。

## Task Decomposition

Direct implementation plus one C03 independent source review: observation selection can change clinical interpretation, requiring an independent challenge before integration acceptance. Owner retains all edits and final checks. No product/testing calls.

## Source Packet

Use the bounded source list and requirements in the conference context. Review findings first, ranked by severity, with exact source lines, proposed minimal remedies and unverified limits. Do not infer acceptance from model agreement or compiler success.

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `zcode` | `GLM-5.3` | `runs/conference/r05-observation-consumer-review-20260915/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

Dispatch through generated runner with health check and 7200-second bound; collect actual terminal identity/fallback and report before acceptance. No repeat dispatch while progressing.

## Codex Verification Checklist

Read findings against current source, implement justified fixes only, preserve prior payload hashes, maintain claims_complete=false. No runtime or staged tests; whole-product validation remains later.
