# Codex Main-Venue Plan: r07-judgment-publication-boundary-20260913

Date: 2026-09-13
Objective: 只读审阅研究者判断未核实与已确认缺失进入正式审核合同的最小修复方案；不得为测试放宽采信或重写临床历史

## Task Decomposition

One read-only reviewer: audit the evidence boundary and smallest complete integration; owner implements only after source verification. No new manager or worker.

## Source Packet

See the concrete source set and reproduced failures in the conference context. All paths are in this worktree; real clinical records excluded.

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `grok-build` | `grok-4.6` | `runs/conference/r07-judgment-publication-boundary-20260913/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

Runner timeout7200, current state prepared. Actual terminal identity and decisions will be recorded in owner review/metrics after completion; no repeated dispatch while progressing.

## Codex Verification Checklist

Verify reviewer claims against source, preserve explicit unknown and confirmed-missing distinction, no acceptance based on tests alone. Retain historical artifacts; evaluate proposals before writes.
