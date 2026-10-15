# Conference Context: r3-normalizer-prompt-cost-review-20260909

Created: 2026-09-09 09:20:34 CST
Objective: 基于真实耗时与当前源码独立审阅Normalizer提示职责及输入冗余，提出不损失原始证据、缺口、阶段判断的最小降本方案；重点已核实事实少但待核对观察多的输入，给具体实现与验收测试。
Task type: `C03`
Risk: `high`
Conference mode: `parallel`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `zcode/glm-5.3:max -> xai/grok-4.6:high -> xai/grok-4.6:high -> openai-codex/gpt-6-astra:low`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `r3-normalizer-prompt-cost-review-20260909`
- Execution evidence status: `no linked execution packet`
- Excluded provider/model nodes: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Read app/agents/evidence_normalizer.py; app/projections/page_review_model_input.py; app/projections/page_review_pending.py; app/projections/page_review_pending_normalization.py; app/projections/page_review_sources.py; app/services/fact_normalization_executor.py; app/services/fact_normalization_replay_sources.py; app/domain/contracts/evidence_normalizer.py; docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md; artifacts/phase55-takeover/20260909/glm-gemini-product-runtime-03/normalizer-input-size-audit.json. Relevant synthetic tests may be read/run. No credentials or raw clinical database/files needed.
- Measured runtime: e5c3b71c53894aa7b37a85a0570644f8 ran42.87min to transport failure at tenth group. Four successful GLM high/65536 requests elapsed621.145/428.927/519.225/461.477 seconds; prompt tokens38441/56606/27570/46780; completion45770/32077/37021/32223; reasoning35487/27236/32120/27434. All stop and one receipt each, no format retries. Five other completed groups made no model call, ~6.5sec each. One failed stream incomplete_chunked_read after480sec. No model substitution authorized.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: read-only bounded engineering/clinical-semantics design review. Compare safe reversible ID aliases/audit metadata removal vs separating deterministically preserved pending observations from semantic normalization. Must not lose gaps, cross-source conflicts, required investigator written judgment, stage scope, provenance, medication/event connections. Explain whether pending entries must remain model context for interpretation; define minimal preserved summaries and original-source binding, and where complete pending records should enter final report. Propose specific test criteria and small module boundaries, not general advice. No writes. Return advice to runner, not final project acceptance.
- Out of scope: source edits, medical judgments from raw cases, personal harness/OAuth/keys, model calls, broad benchmarks, automatic lower effort/output cap, changing published history. Do not read prior worker reasoning; this is fresh independent review. No fallback this pass.

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

- 2026-09-09 09:20:34 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
