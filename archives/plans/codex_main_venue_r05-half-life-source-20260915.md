# Codex Main-Venue Plan: r05-half-life-source-20260915

Date: 2026-09-15
Objective: 只读审阅新增半衰期来源合同、方案解构来源验证、冻结计算及报告衔接；不得运行产品、模型、数据库、浏览器或测试；指出确切源码问题和最小修订建议，不作临床验收

## Task Decomposition

Owner source integration followed by bounded independent source review, targeted same-session corrections, owner source checks. No product run or staged tests.

## Source Packet

See context/r05-half-life-source-20260915_conference_context.md for exact files and authority. Reviewed artifacts and final limitations are in reviews/codex_conference_r05-half-life-source-20260915_review.md.

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `grok-build` | `grok-4.6` | `runs/conference/r05-half-life-source-20260915/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

Primary CLI exit1 with no session, declared pi/cursor fallback used. Three completed passes in same session. Metrics and receipts recorded; no active wait. First failed child attempt rejected as boundary violation; follow-ups direct only.

## Codex Verification Checklist

Python compile, frontend TypeScript, diff checks passed; no clinical/runtime acceptance. Missing timestamp consumption and complex PK scope remain explicit. Continue construction, not pause.
