# Codex Main-Venue Plan: enrollment-targeted-read-contract-20260916

Date: 2026-09-16
Objective: 只读审阅双读遗漏复核入口与提示合同修订，评估不放宽采信的最小后续方案；不运行模型、不修改源码、不读原始病例。

## Task Decomposition

One independent source reviewer; owner integrates. No extra executor because the changed scope shares one mutable product runtime and the patch is small. Review is needed for the interpretation of missing observations and identity guidance without weakening evidence acceptance.

## Source Packet

Use the current conference context's explicit read set and constraints. Sources are frozen while the review runs; no raw clinical records are authorized.

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `grok-build` | `grok-4.6` | `runs/conference/enrollment-targeted-read-contract-20260916/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

Runner records actual runtime and terminal evidence; 7200-second bound, no mid-run redispatch. Product model jobs are all terminal before this engineering review.

## Codex Verification Checklist

- Verify findings against full affected definitions and adjacent consumers.
- No numerical correctness or clinical acceptance inferred from schema success.
- Only justified minimum changes, compile/source checks; no new stage test suite.
