# Codex Main-Venue Plan: r3-reread-evidence-audit-20260906

Date: 2026-09-06
Objective: 只读审查两轮冲突复核隔离证据、严格事实计分原语和产品结束状态处理；提出最小必要修订及是否具备自动采信接入依据，不作临床签收、不改文件、不调用产品模型、不读取外部原始临床资料或凭据。

## Task Decomposition

One read-only engineering reviewer examines frozen pilot evidence and code; Codex verifies findings and integrates only reproducible in-scope fixes. This is conference mode because clinical evidence acceptance and comparison semantics have material interpretive uncertainty.

## Source Packet

The adjacent conference_context.md contains the exact initial source allowlist. Workspace sources stay unchanged during review. No raw-image or clinical approval is delegated.

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `general_single_object` | `cursor` | `default` | `runs/conference/r3-reread-evidence-audit-20260906/general_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

Prepared; primary route from current manifest, no automatic fallback requested. Runner timeout7200, await terminal. Actual model identity must be distinguished from cursor/default selector and verified from receipt when available.

## Codex Verification Checklist

Check actual receipt/route and source access; independently reproduce concrete counterexamples; reject unsupported clinical acceptance; record unknown identity or missing evidence rather than invent it.
