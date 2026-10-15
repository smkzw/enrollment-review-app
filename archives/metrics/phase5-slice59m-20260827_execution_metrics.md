# Execution Metrics: phase5-slice59m-20260827

| Role | Effective execution route | Status | Duration | Decisive result |
|---|---|---|---:|---|
| `worker_01` | `cursor-cli/auto` | accepted after Codex review | 227.675 s | dedicated control transport and configuration |
| `worker_02` | `cursor-cli/auto` | accepted after Codex review | 102.844 s | durable same-session history, 18 focused tests |
| `worker_03` | `cursor-cli/auto` | diagnostic, superseded by Codex continuation | 392.213 s | exposed unsupported Schema conditionals; no clinical acceptance |
| Codex product replay | `MTPLX/mtplx-qwen38-27b-optimized-quality:medium` | accepted for four representative rows | 202.690 s | 2 same-session attempts; final 4/4 controls gate-accepted |

## Verification

- Product transport: strict control JSON Schema, `temperature=0`, `max_tokens=16384`, no model fallback.
- Final replay: `publication_invalid -> parsed`; outside-scope candidates and dispositions unchanged.
- Focused regression: `75 passed in 1.02s`.
- Full protocol regression: `823 passed, 58 warnings in 154.78s`.
- Scope remains bounded: 4 representative Table 5 rows only; `claims_complete=false`.
