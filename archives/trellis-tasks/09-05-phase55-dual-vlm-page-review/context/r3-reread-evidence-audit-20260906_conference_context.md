# Conference Context: r3-reread-evidence-audit-20260906

Created: 2026-09-06 12:39:01 CST
Objective: 只读审查两轮冲突复核隔离证据、严格事实计分原语和产品结束状态处理；提出最小必要修订及是否具备自动采信接入依据，不作临床签收、不改文件、不调用产品模型、不读取外部原始临床资料或凭据。
Task type: `C01`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`general_single_object`) with no sub-venue chair. Its effective `CST` route chain is `cursor/default -> cms-router/cms-model:high -> openai-codex/gpt-6-astra:low`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `r3-reread-evidence-audit-20260906`
- Execution evidence status: `no linked execution packet`
- Excluded provider/model nodes: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Runner workdir is the phase5 worktree. Read only these relative files and their directly imported non-secret source/tests if necessary:
  - scripts/score_exact_fact_keys.py and tests/v2/evidence/test_exact_fact_scoring.py
  - scripts/evaluate_observation_alignment.py and tests/v2/services/test_observation_alignment_experiment.py
  - scripts/evaluate_conflict_reread.py and tests/v2/services/test_conflict_reread_experiment.py
  - app/llm/page_review_harness.py (read_page and direct_openai_completion) and tests/v2/llm/test_page_review_harness.py
  - app/domain/page_normalization.py
  - artifacts/phase55-takeover/20260906/conflict-reread-blind-02/assessment.md
  - artifacts/phase55-takeover/20260906/conflict-reread-second-layout-02/assessment.md and main-B-length-retry.json
  - .trellis/tasks/09-05-phase55-dual-vlm-page-review/BENCHMARK_SCORING_AUDIT_20260906.md
  - docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md (targeted reread proposal only)
- Do not read .env, credentials, other harness settings, outside-worktree raw clinical files, or other conference results. Source-image QC in assessment files is Codex's report, not your independent image verification. Do not claim independent clinical sign-off.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: challenge engineering inference from the isolated pilot; exact-key scorer correctness/limits; distinguish observation correspondence from value agreement; normal-finish acceptance; minimum next implementation/verification action.
- Out of scope: product model calls, running live tests, database access/writes, UI or clinical acceptance, new protocols or model substitutions, editing any files. Read-only deterministic checks may run with bytecode/cache writes disabled.
- User authorized isolated pairing evaluation only, not product integration. Their newest proposal permits max two targeted business reread rounds (GLM high/MiniMax high) before unresolved items go to user. A length retry is not a third business round. Initial formal main-A remains low; do not silently upgrade it. Claims complete remains false.
- Required finding quality: reference a concrete file/line and counterexample; distinguish proved bug from proposed policy. Do not require workflow machinery for an explicitly isolated scoring primitive, but state which missing pieces prevent formal acceptance. No arbitrary numerical threshold approval.

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

- 2026-09-06 12:39:01 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
