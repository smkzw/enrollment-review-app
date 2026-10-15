# Codex Conference Review: r05-policy-links-review-20260914

Date: 2026-09-14

## Verdict

Revised; source construction only, runtime UNVERIFIED.

## Boundary Compliance

Read-only scope observed in report; no product inference/tests/DB writes. Executor underlying model unknown, model-level independence unverified; fresh review context was provided.

## Participant Outputs Reviewed

grok/grok-build/grok-4.6 high, terminal 0, no fallback. Report SHA256 d71c512848bc0144d1c5ea6593816f47d24c796d1b67c3444b1cfacb712c60de.

## Conference Panel Review

Accepted compact-prompt clarification, local duplicate-ID rejection for linked components and removal of redundant new gate branch. Kept mixed unattributed policies visible; explicit refs are attribution, not source verification. No need to ask user to approve guessing missing attribution.

## Main-Venue Codex Review

Rejected assertion that this pass changed legacy singleton present to unattributed: that correction preceded this pass; empty predicate_ids is now omitted in policy dictionaries as well, preserving prior qualified-pair input. No old cached response is relabeled. Rejected speculative instance remap bypass: new linked semantic components reject duplicate IDs before assembly; RuleComponent now does too. Source booleans defaulting predates this change, remains an explicit unresolved design issue; do not claim no guessed policy or formal acceptance. Positional correctness does not prove semantic correctness and requires final model/source evaluation. Additive dnf-v1 IDs remain unchanged for legacy; actual prompt content hash changes for new requests, existing PromptVersion records must not be silently replaced.

## Codex Independent Verification

Owner read full affected definitions/callers and checked project-venv py_compile plus git diff --check. No staged tests, model calls, DB replay or browser acceptance per current instruction. Independent report predates final owner source fixes.

## Final Decision

Post-review repair: new linked semantic/domain requirements now require both source-policy booleans explicitly supplied; compact hydration enforces this before applying legacy defaults. Unlinked historical inputs retain old behavior. This prevents the newly attributed path from deriving policy merely from omission, but does not prove the model's declared policy is clinically correct. Source-only repair, final runtime validation pending.

Retain optional attribution chain disabled with qualification; continue formal integration, not more acceptance claims. No phase/goal closure.
