# Conference Context: r3-visual-publication-review-20260909

Created: 2026-09-09 06:36:49 CST
Objective: 只读审阅新视觉摘录来源从双读对账到Normalizer及正式事实发布、回放、原件回查的完整接线，识别实际缺陷与最小修复建议，不修改文件不读取凭据不调用病例模型。
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

- Linked execution task: `r3-visual-locator-contract-20260909`
- Execution evidence status: `linked`
- Excluded provider/model nodes: `zcode/glm-5.3-flash`
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Read docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md visual source section, then app/domain/page_review_evidence_sources.py, app/projections/page_review_visual_locators.py, app/services/page_review_visual_sources.py, app/storage/page_review_visual_locator_validation.py, app/storage/evidence_locator_repositories.py, app/storage/fact_authority.py, app/domain/gates/fact_evidence_closure.py, app/projections/page_review_sources.py, app/services/fact_normalization_source_adapter.py, app/services/fact_normalization_job_service.py, app/services/fact_normalization_executor.py, app/services/fact_normalization_replay_sources.py, app/services/fact_normalization_command_service.py and relevant contracts/tests. Read consumers as needed. Do not read previous worker/reviewer reasoning.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: frozen working-tree source, typed visual locator identity, exact excerpt hash distinct from image hash, observation binding, publication/replay validation, historical compatibility, formal API and original-page lookup. Run focused tests if useful. Report concrete file/line findings with reproduction and minimal proposed fix; no broad rewrite. Check unhandled exceptions and redundant reconstruction costs. Existing old text revision must not be mutated or refer recursively to its own visual source coverage.
- Out of scope: edits, personal harness configuration, credentials, databases/raw clinical files, model calls, benchmark tasks, clinical acceptance. Only read source and use isolated synthetic tests. No fallback authorization in this pass. Return report to runner; do not write report yourself.

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

- 2026-09-09 06:36:49 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
