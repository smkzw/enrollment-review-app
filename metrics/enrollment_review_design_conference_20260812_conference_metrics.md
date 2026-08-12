# Conference Metrics: enrollment_review_design_conference_20260812

Date: 2026-08-12

| Role | Provider | Model | Status | Duration | API calls | Tokens | Result |
|---|---|---|---|---:|---:|---:|---|
| `general_pi_qwen38` | `opencode-go` (daytime overlay from declared `alibaba`) | `deepseek-v4-flash:max` | complete | 158.189s | 1 model response; 6 tool calls | 71,926 total (815 input, 63,360 cache, 7,751 output) | accepted with synthesis |
| `general_grok45` | `grok-build` | `grok-4.5` | complete after same-session continuation | 33.039s incomplete + 160.042s accepted | 2 calls initial + 2 calls continuation | 150,504 incomplete + 189,111 accepted | accepted with synthesis |

## Timeout And Retry Evidence

- `general_pi_qwen38`: health preflight warned, policy required one live attempt, and the live route completed in session `019ff55e-e542-7000-8e79-806f996f7bcb`; no fallback.
- `general_grok45`: initial call stopped as `cancelled` after a preamble and was rejected as incomplete. Codex resumed session `a0767fec-62d3-4136-8468-93f2438b43cc`; the continuation completed with the required schema. No provider fallback or duplicate session.
- Accepted output sizes: 21,493 characters for Pi; 28,248 characters for Grok Build.
- Recorded model cost: Pi accepted pass `$0.001230894`; Grok Build incomplete call `$0.1862608`, accepted continuation `$0.1243412`.

## Quality Decision

Both outputs materially changed the design: the clinical pass added the consistency matrix, conflict hard block, gap-specific closure semantics and visible provenance actions; the architecture pass removed day-one LangGraph, mandatory Critic and legacy write migration. Their conclusions converged on representation, durable state and deterministic gates as the highest-priority correction. No further conference pass is justified before user approval of the design packet.
