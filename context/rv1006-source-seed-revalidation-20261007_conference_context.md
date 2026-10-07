# Conference Context: rv1006-source-seed-revalidation-20261007

Created: 2026-10-07 17:45:47 CST
Objective: 独立审阅原文清单重放复用：实际初答与至多两项范围校正经过现行核验后仅复用来源，组件变化不继承旧候选或采用；损坏硬拒、合法API续跑与历史保留。工程只读，不读临床或凭据。
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

- Linked execution task: `rv1006-source-seed-revalidation-20261007`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Frozen baseline c55a528e plus the current patch in `app/services/protocol_control_execution.py` and `tests/v2/services/test_protocol_control_execution.py`. Read their diff and complete affected definitions.
- Existing source interpretation parsing, normalization, validation and scope correction: `app/agents/protocol_control_source_interpretation.py`.
- Existing source read, correction and checkpoint producer: `app/agents/protocol_control_deconstructor.py`; only source read/attempt recording/resume paths relevant to this patch.
- Existing original gate and Job checkpoint/retry consumers reached from the affected service. Follow only necessary definitions within app and the named synthetic tests.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: one read-only engineering review of source-only replay, changed component identity, corruption classification, scope correction authorization, producer/save/resume consumer and relevant positive/negative synthetic tests. Targeted window already reports 36 passed/162 deselected; this is not full acceptance.
- Out of scope: clinical originals, databases, env/credentials, tmp/artifacts/runs other than this packet, paid clinical calls, tests execution, writes, browser, delegation and broad repository audits. Maximum 16 targeted read/search tool calls; use complete affected definitions and compact results.

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.
- Identify concrete defects with file/function/line and counterexample; distinguish proven bugs from missing verification. Check that changed source/prompt/schema/route cannot reuse, valid actual-source replay can reuse without wire/target review/approval, corrupt actual answers hard-fail, at most two authorized corrections cannot mutate siblings, and actual preflight/save/consumer respect the new proof.
- Report any material unsoundness or unnecessary rejection; do not propose broad framework changes. Actual clinical replay will be performed separately by Codex and is not adviser evidence.

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

- 2026-10-07 17:45:47 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
