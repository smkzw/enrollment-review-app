# Conference Context: r3-targeted-durable-review-20260906

Created: 2026-09-06 18:46:33 CST
Objective: 只读审查两轮辅助原件复核：持久上限、来源绑定、无自动事实采信、失败与缺研究者判断分离。禁止修改应用或原始资料。
Task type: `code_open_audit`
Risk: `high`
Conference mode: `parallel`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`general_single_object`) with no sub-venue chair. Its effective `CST` route chain is `cursor/default -> cms-router/cms-model:high -> openai-codex/gpt-6-astra:low`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `r3-targeted-durable-review-20260906`
- Execution evidence status: `no linked execution packet`
- Excluded provider/model nodes: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- User-approved boundary: targeted source reread by GLM high and MiniMax high, maximum two rounds; first blind, second candidate excerpts allowed, no automatic fact rewriting. Both missing investigator written judgment is a nonblocking report finding, never inferred from a failed or uncovered page. This implementation covers factual conflicts only; the clause/report judgment flow is not claimed implemented.
- Read app/domain/contracts/page_review_focus.py; app/domain/targeted_page_review.py; app/services/targeted_page_review_jobs.py; app/services/targeted_page_review_executor.py; app/services/page_review_runtime.py; app/services/page_review_job_executor.py; app/llm/page_review_harness.py; app/api/v2/page_review.py; tests/v2/services/test_targeted_page_review_jobs.py; tests/v2/llm/test_targeted_page_review.py; tests/v2/api/test_page_review.py. Adjacent contracts/runner/storage source may be inspected as needed.
- Design authority: docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md section 16 and latest user boundary above. Product data, raw clinical documents, env files, external harness settings and credentials are excluded. No model inference calls in this review.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: source-based read-only engineering review of this frozen change; find concrete defects with file/line references and remedies. Focus round persistence, source/context binding, failure handling, candidate independence, source-preserving records and API behavior. Owner test run: 96 passed, 5 warnings; this is not clinical acceptance.
- Out of scope: editing any files, executing product jobs, real API requests, reading private source data or credentials, broad repo audit. Do not duplicate implementation. No claims of clinical or rendered UI acceptance.

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

- 2026-09-06 18:46:33 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
