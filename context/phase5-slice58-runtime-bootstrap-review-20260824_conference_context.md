# Conference Context: phase5-slice58-runtime-bootstrap-review-20260824

Created: 2026-08-24 00:21:43
Objective: 只读审查 Phase 5.8 个例档案整理命令闭环：重点挑战 Evidence Normalizer 运行配置注册与精确选择、前后端合同、任务恢复、真实模型可用性、自动方案信息保留及代表病例原件定位验收是否足以防止伪通过；输出按严重度排序的可验证问题，不修改任何文件。
Task type: `complex_delivery_conference`
Risk: `high`
Conference mode: `parallel`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Visual/design/HTML/PPT tasks use a Codex-led panel with no sub-venue chair: Pi/Oh My Pi `k3-256k` (high). If unavailable, the runner tries Grok Build `grok-4.6` (high), then the distinct Cursor `cursor-grok-4.6-high` route, then Pi/OpenCode Go `muse-spark-1.2-contributor` (xhigh), then Codex subAgent Luna (max). The Codex subAgent route remains a separate native/CLI compatibility path.
- Chinese labels or Chinese sentence review is handled directly by Codex and does not start a conference.
- Other complex, logic-heavy, evidence-sensitive, artifact-heavy, code-review, and high-risk contradiction work uses a Codex-chaired panel with no sub-venue chair. Participant 1 is night Pi/Alibaba `qwen3.8-max` (xhigh) -> Pi/OpenCode Go `muse-spark-1.2-contributor` (xhigh) -> Kimi Code `k3-256k` (high) -> Codex subAgent `gpt-5.6-luna` (max), and day Pi/OpenCode Go Muse (xhigh) -> Kimi Code K3 (high) -> Codex Luna (max). Participant 2 is Cursor `auto`, with Grok Build `grok-4.6` (medium) and Pi/cms-router `minimax-m3` as fallbacks. Codex remains the final authority.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Source Of Truth

- `AGENTS.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/{prd.md,design.md,implement.md}`
- `.trellis/spec/backend/quality-guidelines.md`
- `.trellis/spec/frontend/quality-guidelines.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/slice53-real-evidence-normalizer-probe.md`
- `app/config.py`
- `app/api/v2/{app.py,fact_normalization.py,fact_normalization_schemas.py,errors.py}`
- `app/services/{fact_normalization_command_service.py,fact_normalization_job_service.py,fact_normalization_executor.py}`
- `frontend/src/api/fact-normalization/`
- `frontend/src/features/fact-normalization/useFactNormalizationJob.ts`
- `frontend/src/components/profile/ProfileNormalizationStatus.tsx`
- `frontend/e2e/{phase5-real-acceptance.spec.ts,phase5-real-acceptance-support.ts}`
- Focused tests under `tests/v2/api/test_fact_normalization*.py`, `tests/v2/services/test_fact_normalization_command_service.py`, and matching frontend tests.

## Review Boundary

- Read-only conference; do not modify source, tests, reports, or raw clinical inputs.
- Verify claims against the current files rather than prior worker reports.
- Distinguish execution-model defects from product Evidence Normalizer model configuration.
- Report only concrete, reproducible defects or material acceptance gaps, ordered by severity; do not perform security testing.

- TODO: Add authoritative local files, extracts, datasets, screenshots, URLs, or user-provided materials.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: TODO
- Out of scope: TODO

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

- 2026-08-24 00:21:43: Conference initialized by `hermes_workflow_guard.py init-conference`.
