# Metrics: enrollment_phase2_sqlite

Date: 2026-08-14

| Field | Value |
|---|---|
| Task type | `long_horizon_code` |
| Risk | `high` |
| Selected provider | `opencode-go` |
| Selected model | `deepseek-v4-pro` |
| Selected effort | `max` |
| Duration | Multi-session implementation on 2026-08-14; exact aggregate not retained |
| API calls | Not retained; runner reports preserved without raw stdout |
| Artifact size | Source and compact evidence only; temporary DB/logs cleaned |
| Result | Accepted after remediation |

## Verification Burden

High verification burden: migration rollback, normalized scope, real SQLite contention, lease recovery, SSE replay and four-viewport browser regression were all required. Delegated confidence alone was not used.

## Routing Decision

Initial route followed the long-horizon code policy. Exact worker/fallback identities are retained in execution reports; Codex remained final authority.
