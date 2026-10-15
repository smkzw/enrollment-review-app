# Conference Context: phase5-clinical-facts-profile-planning

Created: 2026-08-22 21:23:56
Objective: 只读审查 Phase 5 临床事实与 Patient Profile 规划。依据 context/phase5-clinical-facts-profile-planning_context.md 和当前 PRD/代码，分别挑战领域溯源、Agent/Gate/Job 运行图、临床用户体验与切片验收；主席综合必须修订、延后和拒绝项。不得修改文件或读取工作区外临床资料。
Task type: `complex_delivery_conference`
Risk: `high`
Conference mode: `parallel`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Visual/design/HTML/PPT tasks use a Codex-led panel with no sub-venue chair: Pi/Oh My Pi `kimi-code/k3-256k` (high). If unavailable, the runner tries Grok Build `grok-4.6` (high), then the distinct Cursor `cursor-grok-4.6-high` route, then the distinct Pi/OpenCode Go `gpt-5.6-luna` (max) route, then Codex subAgent Luna (max). The Codex subAgent route remains a separate native/CLI compatibility path.
- Chinese labels or Chinese sentence review is handled directly by Codex and does not start a conference.
- Other complex, logic-heavy, evidence-sensitive, artifact-heavy, and high-risk contradiction work uses a Codex-chaired panel with no sub-venue chair. Participant 1 is night Pi/Alibaba `qwen3.8-max` (xhigh) -> Codex subAgent `gpt-5.6-luna` (max), and day Pi/CMS-SMK `deepseek-v4-flash` (max) -> Pi/OpenCode Go `gpt-5.6-luna` (max) -> Kimi Code `k3-256k` (high). Participant 2 is Grok Build `grok-4.6` (high), with the distinct Cursor `cursor-grok-4.6-high` and Pi/cms-router `minimax-m3` as fallbacks. Codex remains the final authority.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Source Of Truth

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`: approved architecture boundary.
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`: approved phased sequence and Phase 5 exit gates.
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/prd.md`: current Phase 5 requirements and acceptance criteria.
- `context/phase5-clinical-facts-profile-planning_context.md`: current-state findings and four review questions.
- Existing contracts, storage models/repositories, Phase 4 evidence-processing runtime, and Profile frontend components inside the current worktree may be read as implementation evidence.
- Do not read raw clinical material or any path outside the current worktree.

## Scope

- In scope: source/version identity, normalization candidate and deterministic gate, fact/event/exposure publication, conflict and partial-date semantics, fact-rule index, evidence expectations, Patient Profile projection/API/UI, persistent jobs, focused clinical regression and implementation slicing.
- Out of scope: Phase 6 rule assessment, Phase 7 action/report workflow, project-specific medical hardcoding, security testing, raw external clinical materials, and file modification by conference participants.

## Success Criteria

- Identify any design that could publish facts from a stale evidence revision, fabricate a negative fact from silence, hide contradictory evidence, or lose source location.
- Produce concrete, implementable revisions and a dependency-ordered slice plan without expanding into Phase 6 or Phase 7.
- Distinguish clinical source strength, missing-record expectations, unresolved conflicts, event time versus record time, and partial-date bounds.
- Challenge whether the first-screen Profile supports a time-poor senior medical monitor while retaining complete source-linked detail.
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

- 2026-08-22 21:23:56: Conference initialized by `hermes_workflow_guard.py init-conference`.
- 2026-08-22: Generated prompts initially failed preflight because the generated absolute worktree path matched the production-path heuristic; changed the boundary to the runner current directory and added the real source packet. Both prompts then passed.
- 2026-08-22: Initial Pi launcher failed before model dispatch because generated schedule arguments conflicted with the live role manifest. Retried the same role once using the manifest's active daytime primary, `pi/cms-smk/deepseek-v4-flash` max; no silent substitution or fallback occurred.
- 2026-08-22: DeepSeek V4 Flash max and Grok Build 4.6 high completed independent first passes. Codex reviewed both and found no need for same-session follow-up.
