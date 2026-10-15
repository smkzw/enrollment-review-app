# Conference Context: r05-observation-selection-20260915

Created: 2026-09-15 08:27:41 CST
Objective: 只读设计审阅：基于现有R3来源资格/命题/确定性计算，补齐官方及跨章要求的有限观察集合、最近/最早与复查选择通用闭环，提出最小完整实现，不把永久UNKNOWN或新未消费合同当完成。
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `zcode/zcode/glm-5.3:max -> grok/grok-build/grok-4.6:high -> pi/cursor/cursor-grok-4.6:high -> pi/openai-codex/gpt-5.6-sol:medium`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `r05-observation-selection-20260915`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Current workspace docs/REARCHITECTURE_FINAL_DESIGN_20260812.md, docs/PROJECT_CONTEXT.md and plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md; read relevant current sections, not full historical logs.
- app/domain/contracts/rules.py; app/domain/contracts/control_evaluation_spec.py; app/services/qualified_binding_selection.py; app/llm/proposition_evidence.py; their direct producers and consumers in app/.

## Scope

- In scope: source-only independent review of a minimum complete generic observation-selection policy spanning official predicates and cross-chapter controls; identify exact producer, projection, selector and explanation changes.
- Out of scope: all writes; databases; raw clinical originals; network; product model calls; tests; browser; new agents. The runner alone persists the response.
- Check finite-set completeness, partial dates, ties, latest/earliest versus protocol-authorized retests, and source citation requirements. No default favorable/latest result and no project-specific rules. Preserve existing any/all semantic scope proof where valid. A policy object without working consumers is not completion.
- Give file/line findings and a bounded implementation sequence. Distinguish achievable source-contract work from clinical acceptance still needing final real-material testing. Do not treat reviewer confidence as acceptance.

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

- 2026-09-15 08:27:41 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
