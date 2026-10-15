# Conference Metrics: enrollment_review_expanded_design_conference_20260812

Date: 2026-08-12

| Role | Provider | Model / effort | Status | Duration | Tool calls | Tokens | Accepted output | Result |
|---|---|---|---|---:|---:|---:|---:|---|
| `expanded_pi_kimi_k3` | `kimi-code` via Pi | `k3-256k / max` | complete, no fallback | 1140.931s | 86 | 113,690 total | 52,178 chars | accepted with synthesis |
| `expanded_codebuddy_glm52` | `codebuddy-cli` | `glm-5.2 / max` | complete, no fallback | 374.613s | 30 | not exposed by conference runner | 68,797 chars | accepted with synthesis |

## Route And Recovery Evidence

- K3 session: `019ff580-3595-7000-bc4c-2ab69f8ee01c`; one full pass, return code 0, stop reason `stop`. Its catalog/auth health preflight timed out after 90.008s, but policy correctly allowed the live attempt and that attempt completed on the requested model.
- GLM-5.2 session: `6bce0b95-89e9-49e3-85e9-6f08f18b1e7c`; one full pass, return code 0. Health preflight returned the authenticated marker in 7.032s.
- Both runner records show requested route = effective route and `fallback: null`.
- Qwen 3.8 was never dispatched and is not included in metrics. The user explicitly requested no later Qwen conference.

## Quality Decision

Both reports independently identified the same architecture gaps: an underspecified prototype gate, absent-evidence representation, non-enforceable evidence localization, incomplete deterministic rollup, weak Job UX and insufficiently measurable testing. Codex verified the relevant current-code claims and accepted the convergent corrections. K3's out-of-list source/web read is retained as a disclosed process deviation; its accepted claims were independently checked. No rerun is justified.
