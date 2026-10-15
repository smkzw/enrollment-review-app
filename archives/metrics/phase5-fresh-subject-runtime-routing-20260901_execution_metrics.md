# Execution Metrics: phase5-fresh-subject-runtime-routing-20260901

| Role | Provider | Model | Status | Duration | Tools | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` | `cursor` | `default` | accepted after Codex verification | 1180.0 s | 526 | graded service routing and launcher integration |
| `worker_02` | `cursor` | `default` | accepted | 561.7 s | 244 | fresh-runtime gate and isolated empty root |
| `worker_03` | `cursor` | `default` | accepted after same-session continuation | 103.5 s | 54 | adversarial route and runtime-identity tests |

## Codex Checks

- Governed execution audit: passed, no fallback and no route drift.
- Focused route/runtime tests: 40 passed.
- Agent/tool combined tests: 145 passed.
- Expanded protocol/agent/tool tests: 1464 passed; one frozen D001 prompt-hash
  assertion remains intentionally unchanged.
- V2 launcher UAT: 14 passed.
- Live provider calls: not performed in this packet.
