# Conference Context: r3-normalizer-input-review-20260906

Created: 2026-09-06 23:26:14 CST
Objective: 只读审查R3事实规范化输入契约和最小优化方案：保留已采信原文与来源，待核对观察不重复语义处理，不能以工程成功冒充临床采信。禁止修改文件和读取病例、凭据；不改变模型与阈值。
Task type: `code_scoped_patch_plan`
Risk: `high`
Conference mode: `parallel`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`general_single_object`) with no sub-venue chair. Its effective `CST` route chain is `zcode/glm-5.3-flash:max -> opencode-go/muse-spark-1.3-contributor:xhigh -> codebuddy-cli/deepseek-v4-flash:max -> openai-codex/gpt-5.6-sol:medium`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `r3-normalizer-input-review-20260906`
- Execution evidence status: `no linked execution packet`
- Excluded provider/model nodes: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Paths below are relative to the application worktree, not this task directory: `app/projections/page_review_model_input.py`, `app/projections/page_review_sources.py`, `app/agents/evidence_normalizer.py`, `app/services/fact_normalization_executor.py`; relevant tests discovered by filename under `tests/`.
- Design authority: `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md` R3 sections 5.4 and 7.4; `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md` Phase 5.5. Read scoped sections only.
- Owner-measured aggregate evidence: isolated page recovery reached 24/24 coverage, reusing 47 prior lane checkpoints exactly. Subsequent formal Normalizer job 7c81237d1a24462f91223b36ca0960e9 processed three groups with respectively 0,1,0 candidates and 10,11,12 unresolved items. Fourth group failed at the 600-second client timeout. No clinical acceptance.
- GLM high requests had 35,608 / 40,102 / 54,401 / 36,284 prompt tokens. Three 16,384-output attempts ended length with reported reasoning tokens 16,346 / 16,336 / 16,334; retries used 32,768. First three groups took about 1,915 seconds combined, fourth about 994 seconds including timeout. Pending observations remain in semantic input despite being forbidden candidate sources. This is measured input/output behavior, not proof of the underlying transport cause.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: read-only challenge of normalization input contract, provenance validation, whether pending observations can be preserved deterministically outside semantic generation, minimum coherent remediation and regression tests. Examine accepted clause excerpts as candidate sources rather than assuming their removal is safe. Identify whether empty accepted input can bypass a model call without losing gaps or weakening acceptance.
- Out of scope: all artifacts, runtime databases, raw clinical files, .env or credentials, external harness configuration, network/model calls, writes, clinical extraction, changed model/effort/budgets, product integration of semantic alignment. No destructive cleanup or automatic clinical acceptance.
- Required result: source/line-grounded findings, minimal proposed files and tests, distinguish safe input projection from changed clinical semantics; unresolved design questions explicitly stated. Do not assume 24/24 page coverage proves facts are accepted.

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

- 2026-09-06 23:26:14 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
