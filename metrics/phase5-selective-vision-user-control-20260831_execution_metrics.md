# Execution Metrics: phase5-selective-vision-user-control-20260831

| Role | Provider | Model | Status | Duration | Tools | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` | `codebuddy-cli` | `deepseek-v4-flash:max` | completed by declared fallback | 233.459 s | 50 | read-only boundary review; parent verified findings |
| `worker_02` | `codebuddy-cli` | `deepseek-v4-flash:max` | completed by declared fallback | 284.624 s | 53 | backend/frontend implementation review and SQL LIKE repair |
| `worker_03` | `codebuddy-cli` | `deepseek-v4-flash:max` | completed by declared fallback | 691.724 s | 70 | revision-level and job-type regression coverage |

## Route Evidence

The scheduled night route was `zcode/GLM-5.3-Flash:max`. Each primary attempt timed out before creating a resumable session (`returncode=124`, `session_id=null`). The runner then used the declared first fallback `codebuddy-cli/deepseek-v4-flash:max`; all three fallback sessions completed with `returncode=0`. Codex separately verified the code, tests and browser output because worker completion is not acceptance evidence.
