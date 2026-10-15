# Conference Context: enrollment-memory-settle-review-20260916

Created: 2026-09-16 21:38:03 CST
Objective: 只读审阅本系统MTPLX串行装卸的内存回收等待修复：进程退出后内存滞后、取消和失败保锁、全机计数误阻断、历史身份兼容；禁止加载模型或修改产品，只输出证据支持的缺陷与最小修正建议。
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> zcode/zcode/glm-5.3-flash:max -> grok/grok-build/grok-4.6:high -> pi/cursor/cursor-grok-4.6:high -> pi/openai-codex/gpt-5.6-sol:medium`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `enrollment-memory-settle-review-20260916`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- `app/llm/mtplx_owned_server.py` and `app/llm/mtplx_model_lifecycle.py`, complete definitions.
- `app/services/page_review_job_service.py` deployment identity consumers; `app/api/v2/app.py` shutdown owner.
- `artifacts/mtplx-dual-basic-20260916/continuous-switch-memory-settle-v2/events.json` and `samples.jsonl` (bounded time window, not all large output).
- `artifacts/mtplx-dual-basic-20260916/owned-lifecycle-models-direct-cli.json` identifies log directory. Read latest lifecycle receipts for PIDs29237/29350 only. Do not load models.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: resource cleanup correctness, cancellation, failure retention, memory polling and identity compatibility. Review conservative baseline+1GiB/two-sample heuristic critically; no claim of exact per-model memory attribution.
- Out of scope: clinical records, new architecture, unrelated files, private configs, external network, any writes or model service calls.

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

- 2026-09-16 21:38:03 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
