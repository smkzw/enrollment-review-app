# Metrics: enrollment_fullflow_model_audit_20260701

Date: 2026-07-02

| Field | Value |
|---|---|
| Task type | `visual_report_structure` |
| Risk | `high` |
| Requested model routes | `qwen3.7-plus`, `minimax-m3`, `mimo-v2.5` |
| Successful model outputs | 3 |
| Full prompt outputs | Qwen completed; MiniMax/MIMO required fallback no-tool prompts |
| Main implemented fixes | mobile table scrolling, visible technical-label cleanup, batch-stage selector clarification |
| Tests | compileall pass; JS syntax pass; unittest 130 pass / 1 skipped |
| Browser verification | desktop and mobile Playwright checks passed for patched surfaces |
| Duration | Not precisely captured; multi-stage run crossed 2026-07-01 to 2026-07-02 because two model routes required timeout fallback |
| Result | accepted after Codex review |

## Verification Burden

- High because the user requested full-flow/product/UI critique and this app supports clinical eligibility review.
- Codex performed source checks, browser screenshots, browser metrics, JS syntax check, Python compile check, and unit tests before accepting the patch.

## Routing Decision

- The initial guard route for high-risk visual/product structure would normally escalate to a stronger model, but the user explicitly requested Qwen 3.7 Plus, MiniMax M3, and MIMO V2.5.
- Qwen was usable with the bounded prompt and visual contact sheet.
- MiniMax and MIMO were usable as no-tool advisory reviewers after tool/file-writing prompts timed out.
- Final acceptance stayed with Codex per Hermes SOUL.
