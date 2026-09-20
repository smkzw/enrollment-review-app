# Conference Context: r3-normalizer-latency-source-review-20260909

Created: 2026-09-09 04:29:23 CST
Objective: 只读审阅产品规范化提示重复、来源校验失败反馈及耗时，提出不损失来源和待核对内容的最小优化方案；不调用模型API、不修改代码、病例或默认模型。
Task type: `C03`
Risk: `medium`
Conference mode: `parallel`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `zcode/glm-5.3:max -> xai/grok-4.6:high -> xai/grok-4.6:high -> openai-codex/gpt-6-astra:low`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `r3-normalizer-latency-source-review-20260909`
- Execution evidence status: `no linked execution packet`
- Excluded provider/model nodes: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- app/agents/evidence_normalizer.py; app/agents/deepseek_evidence_normalizer_transport.py; app/projections/page_review_sources.py; app/projections/page_review_pending_normalization.py; app/services/fact_normalization_executor.py; app/services/fact_normalization_source_adapter.py; their direct source/test dependencies inside app and tests/v2 only.
- docs/REARCHITECTURE_FINAL_DESIGN_20260812.md and plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md for current clinical/product boundaries, not earlier superseded model selections.
- Owner runtime evidence: current product pair GLM low/Gemini high, Normalizer GLM high/65536. v21 group 1-2 took 684 seconds and succeeded; group3-4 spent 1744 seconds across three complete responses then failed source matching. Last response 75427 input tokens,38221 output,30714 reasoning,714 seconds,stop. No latency-based model replacement authorized.
- Reproduced source mismatch: an accepted observation excerpt joins three literal rows with ` ... `, while selected locators contain those three rows individually. Strict validator requires entire excerpt in one locator and fails. Old repair feedback was generic, so model repeated the same refs. Current code now identifies candidate/ref/page/excerpt in the failure and asks for independently source-backed refs or an explicit unresolved item. It does NOT loosen matching or rewrite facts. Current retry is running; do not access its database or interfere.

## Scope

- In scope: one read-only code/contract review, identify repeated representations in model input, why schema/source repairs are expensive, minimal source-preserving alternatives and decisive tests. Check whether granular error feedback can converge without losing unresolved information; distinguish genuine missing locator from an invalid aggregated quote. Propose improvements but do not implement or claim clinical acceptance.
- Out of scope: all writes (except runner report); subprocess model calls; network/browser; credential/env/home harness reads; databases/raw clinical artifacts; subprocess delegation; changing effort/model; benchmark; stopping any process. Read only listed app/tests/docs/plan and directly imported app code. No need to reproduce medical facts or read raw replies.

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.

## Parallel Work Rule

For logic-heavy, rigor-sensitive, or artifact-heavy tasks, each participant independently runs the whole bounded workflow and writes a separate output. Leads compare after all available participant outputs are in or explicitly marked pending.

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

- 2026-09-09 04:29:23 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
