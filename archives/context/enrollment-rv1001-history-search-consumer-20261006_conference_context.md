# Conference Context: enrollment-rv1001-history-search-consumer-20261006

Created: 2026-10-06 16:13:43 CST
Objective: 只读审阅新病史范围检索实际接线：逐页来源覆盖、预算和失败续跑、只工作稿消费、原件提及不误转未发生、官方与跨章同政策、更正和定义未知限制；不调用产品模型不读临床或凭据不写源码，最多一名顾问
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `grok/grok-build/grok-4.7:high -> pi/cursor/grok-4.7-high:high -> pi/openai-codex/gpt-6.1-sol:high`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `enrollment-rv1001-history-search-consumer-20261006`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- User policy: routine event history may use no-record treatment only within reviewed supplied material, no invented negative fact. Known missing/unreadable/conflicting material and required positive tests or investigator written judgment stay specific gaps. Prescription/purchase supports history, not actual dosing duration/last use.
- HEAD 023342f3 plus these exact owner patches; no clinical files or credentials are authorized.

| Authorized file | Frozen SHA256 |
|---|---|
| app/domain/contracts/history_source_search.py | 4c621882b328cacb8cb741019f1c0a0230cc05cff9a127221e8f32d875e29e04 |
| app/llm/history_source_search.py | 1796fc539125d689e1003a45d19d18a1fed8898435fda0bab6d5d47cde986909 |
| app/services/history_source_search_input.py | b35e100e71f9aefd2ac10f53669dc8c226bd9b3cf4bf96a643e3db9d4caabd1e |
| app/services/history_source_search_job.py | dca8aa4cd12f52a9b8f61852afb8f8aceab855b37d5823ebb1598d83a855effa |
| app/services/history_source_search_calculation.py | 5aae6950f30ad6ec9878a1dbad6bc0b7c72f3a89de612f3593d776fb9145ce3c |
| app/services/control_history_search_calculation.py | 39c73992fc0618a766163bac3de6aa560e658bd575e4a3b3299618187c3c06d7 |
| app/services/qualified_binding_selection.py | f92734a804ba3ffc472d550ae32fbddeb0a3615a81f51d5d7ece98bf325c1182 |
| app/services/predicate_proposition_calculation.py | bee5e4ff61aeaa80cf824d257daa94530e8797456fc7c1fb03ddad327e685f67 |
| app/services/frozen_review_calculation.py | 47b2e637ed1c146a5541620be2091c48d86f695f11334e138b523aa0c8facfeb |
| app/services/eligibility_review_projection.py | 3ba5bf56fc9a5d9b395b5b670bc4f122bfd4cc7a82a9612c9db5f902449b64cf |
| app/services/prepared_review_workflow.py | cea95507b3d3c625e62176552753a4a4e9cdfa0e298670c374484c5dfe313bf4 |
| app/services/page_review_runtime.py | 1493a2227f2d14ad5e755f1c4d35710597015c213384551495d7ee29637f999a |
| app/services/fact_normalization_source_adapter.py | 3c355fc085607ee50987f4b1bb7702c2340a9e03bcc40b1ace0c897eed78b5bf |
| tests/v2/services/test_history_source_search.py | 61a545fdf803fd8b20083483a05bdf67716bc95221a18b5c315fe545392c9df4 |
| tests/v2/services/test_computation_input_workflow.py | 2c0c1f23e539d3bf42374f6bae7a7051ca510e805ddcee80359b3f5e86b8c504 |

Owner evidence: connected v2 147 passed/54.03 s; v3 154 passed/5 failed from new fixture preserving old publication ID; v4 154 passed/5 failed actual unsupported ControlObligationAtom.prospective_window access. Fixed typed obligation-only future policy; v5 source/job/sealed factory/control projection module 36 passed/7.11 s. These are synthetic software checks, not source closure, live clinical or final UI acceptance. Final connected window pending. Do not run tests yourself.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: first causal defects in production-source closure, wrong negative inferences, consumer gaps, restoration/identity and immutable budget recovery. Inspect source definitions and actual callers, not only rejection cases.
- Out of scope: clinical materials, DBs, .env, private outputs, product endpoints, source edits, broad architecture or extra readers. No runtime commands. Up to four additional directly referenced source definitions may be read with paths and reasons reported; no broad repository scan.
- Tool budget: 30 materially useful read/search/hash calls, plus at most two harness-mandatory memory reads. Read complete changed definitions and decisive adjacent consumers. Return exact coverage and missing checks rather than overrun or claim complete review.

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.

## Conference Pass Rule

This packet uses one serial Codex-led conference object. Each declared role receives one complete prompt and may use multiple internal tool turns. Codex decides whether a same-session follow-up is needed after reviewing the result; follow-ups do not create a new conference or change the route identity.

## Timeout Policy

- Participant soft wait: 60 minutes.
- Large-task participant wait: 120 minutes.
- Chair hard wait: 120 minutes.
- Failure rule: Do not fail a model for slow response alone; fail only on terminal error, provider exhaustion/rate limit after controlled retry, empty/truncated retry output, or no useful progress after the high-budget same-session recovery loop. A catalog/auth/transport health preflight timeout or malformed response is diagnostic and must still allow one live route attempt; explicit user routes also proceed when the catalog is stale or incomplete, while a genuinely missing CLI or native transport boundary may block. If a resumable session exists after a step/size boundary, continue it before fallback; repeated identical output/tool evidence triggers the no-progress breaker.
- Pass/turn boundary: one conference prompt is one conference pass. The
  `--max-turns` value controls internal Agent tool-calling turns and is never
  set to 1 for substantive conference execution; generated participant and
  chair commands use the route budgets recorded by the guard.

## Risk Boundaries

- External Agents are advisory; Codex remains final authority.
- Codex owns visual/browser/PPT/PDF/rendered checks, live authority checks, final clinical/regulatory conclusions, and production writes.
- Do not mark a slow model failed solely due to latency.

## Loop Log

- 2026-10-06 16:13:43 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
