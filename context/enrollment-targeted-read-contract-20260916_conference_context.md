# Conference Context: enrollment-targeted-read-contract-20260916

Created: 2026-09-16 16:57:09 CST
Objective: 只读审阅双读遗漏复核入口与提示合同修订，评估不放宽采信的最小后续方案；不运行模型、不修改源码、不读原始病例。
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `grok/grok-build/grok-4.6:high -> pi/cursor/cursor-grok-4.6:high -> pi/openai-codex/gpt-5.6-sol:medium`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `enrollment-targeted-read-contract-20260916`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Source definitions: app/domain/targeted_page_review.py; app/services/targeted_page_review_jobs.py; app/services/targeted_page_review_executor.py; app/llm/page_review_harness.py; app/llm/page_review_format_repair.py; app/domain/contracts/page_review_focus.py; app/domain/contracts/page_review.py; app/domain/contracts/targeted_review_outcome.py.
- Adjacent read-only source consumers may be inspected when needed. No artifacts/raw clinical files, databases, credentials, external browse, or other workspace reads. No tests, model calls, or application startup.
- Observed failure, not an acceptance claim: a real dense sideways table produced 45 observations in A and zero in B. New candidate selection includes one-sided structured values; readonly replay yielded 35 targets and zero automatic acceptance. Two formal auxiliary rounds completed with all targets pending. A made value/row errors; B omitted context; A changed field labels in round two. No clinical facts were accepted. 300DPI increased memory use and did not improve quality, so default remains 150DPI.
- Latest unmeasured prompt v17 makes context required on the wire but nullable, leaving historical domain records compatible; targeted v5 requests reusing target field labels only when the original visibly matches, retaining original label in raw_text/context.target_text. It does not authorize guessing, automatic pairing, or acceptance.

## Scope

- In scope: source-based review of one-sided numeric/date reread selection, local serial step dependencies, wire context requirement and conditional target-name guidance. Check preservation of two-round identity, no automatic acceptance, historical record reading, false agreement risks. Propose smallest general correction where evidence supports it.
- Out of scope: clinical acceptance, new model selection, new OCR stage, automatic semantic mapping, extra round budgets, editing any file, running inference/tests, rebuilding the architecture.
- Assess whether source-preserving orientation/local views are justified as a next isolated experiment versus further prompt inflation; do not design a disease- or report-specific crop. State unresolved decisions, not an implementation mandate.

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

- 2026-09-16 16:57:09 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
