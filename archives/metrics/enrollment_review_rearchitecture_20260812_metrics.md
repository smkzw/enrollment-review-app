# Metrics: enrollment_review_rearchitecture_20260812

Date: 2026-08-12 discovery checkpoint

| Field | Value |
|---|---|
| Task type | `long_horizon_code` |
| Risk | `high` |
| Selected provider | `cms-smk` |
| Selected model | `deepseek-v4-flash` |
| Selected effort | `max` |
| Duration | Multi-session discovery; final duration pending |
| API calls | Not used as a completion metric; one independent reviewer plus bounded primary-source research |
| Artifact size | Discovery document, task records, launcher repair, one regression test, six valid runtime screenshots |
| Result | Launcher restored; discovery accepted; design awaiting user decisions |

## Verification Burden

High. Claims were checked against source code, live service identity, browser-rendered pages, project artifacts, prior histories, independent review, and deterministic tests. Clinical rerun acceptance is deferred until the new design is confirmed and implemented.

## Routing Decision

The initial task route was recorded by the workflow guard. A fresh-context Luna reviewer was used for independent architecture and clinical-safety challenge because the task crosses workflow, provenance, UI, and high-risk clinical decision boundaries. Codex retained final acceptance.
