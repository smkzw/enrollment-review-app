# Conference Metrics: phase5-clinical-facts-profile-planning

Date: 2026-08-22

| Role | Provider | Model | Status | Duration | API calls | Tokens | Result |
|---|---|---|---|---:|---:|---:|---|
| `general_pi_qwen38` | `cms-smk` | `deepseek-v4-flash` max | completed | 206.803 s | 1 | 85,674 total (66,816 cache read) | substantive; incorporated |
| `general_grok46` | `grok-build` | `grok-4.6` high | completed | 351.651 s | 1 | 1,767,400 total (1,549,184 cache read; 8,467 reasoning) | substantive; incorporated |

## Timeout And Retry Evidence

- Prompt preflight initially rejected guard-generated absolute worktree paths. The prompts were corrected to use the runner current directory and passed preflight.
- The first generated Pi launcher exited before model dispatch with a live-manifest schedule-contract conflict; rounds completed = 0. The actual daytime primary was then launched once from the live manifest and completed without fallback.
- Grok and Pi each used one complete conference pass. No optional follow-up was needed.

## Quality Decision

The two independent reports converged on the critical design defects and supplied complementary implementation detail. Codex verified the core claims in local source, adopted only in-scope remedies, and rejected phase leakage and unnecessary infrastructure.
