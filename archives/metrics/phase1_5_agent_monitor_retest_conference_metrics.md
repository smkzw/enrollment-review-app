# Conference Metrics: phase1_5_agent_monitor_retest

Date: 2026-08-14

| Pass | Actual provider | Actual model | Status | Duration | Recorded tokens | Result |
|---|---|---|---|---:|---:|---|
| fresh retest | `kimi-code` | `k3-256k` | completed | 539.813 s | 73762 total | original findings closed; F1 found |
| F1 evidence-label follow-up | `kimi-code` | `k3-256k` | resumed/completed | 168.148 s | 83654 total | F1 core closed; target residual found |
| F1 target follow-up | `kimi-code` | `k3-256k` | resumed/completed | 81.346 s | 87376 total | pass |

## Timeout And Retry Evidence

All three passes used session `019ffc30-6124-7000-bc66-7115e64877ad`; no fallback. Total observed runner duration was 789.307 s. Token counters are session snapshots and are not summed.

## Quality Decision

Independent reviewer and Codex deterministic/browser evidence agree that Phase 1.5 blockers are closed. Phase 2 gate may open with the recorded carryovers.
