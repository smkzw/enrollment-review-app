# Conference Context: enrollment_review_design_conference_20260812

Created: 2026-08-12 17:43:54
Objective: 独立挑战并会商入排审核本地单用户AI lead多Agent/Graph最终架构、Patient Profile、证据缺口、行动闭环、只读旧项目锚点和阶段实施计划
Task type: `high_risk_contradiction_review`
Risk: `high`
Conference mode: `parallel`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

    - Visual/design/HTML/PPT tasks use a Codex-led panel with no sub-venue chair: Pi/Oh My Pi `kimi-code/k3-256k` (high). If unavailable, the runner tries Grok Build `grok-4.5`, then the distinct Cursor `cursor-grok-4.5-high` route, then the distinct Pi/OpenCode Go `gpt-5.6-luna` (max) route. The Codex subAgent Luna route remains a separate native/CLI compatibility path.
- Chinese labels or Chinese sentence review is handled directly by Codex and does not start a conference.
    - Other complex tasks use a Codex-chaired panel with no sub-venue chair. Participant 1 is Pi/Alibaba `qwen3.8-max` (xhigh) during the Beijing 22:00-07:00 window. Outside that window its exact Qwen Max node is replaced by Pi/OpenCode Go `deepseek-v4-flash` (max); during the night window, every exact Pi/cms-smk `deepseek-v4-flash` node is replaced by the same Pi/OpenCode Go route. Its remaining fallbacks are Pi/cms-smk `deepseek-v4-flash` (max), Pi/OpenCode Go `deepseek-v4-flash` (max), and Pi/DeepSeek `deepseek-v4-flash` (max), with effective-route deduplication. Participant 2 is Grok Build `grok-4.5`, with the distinct Cursor `cursor-grok-4.5-high` and Pi/cms-router `minimax-m3` as fallbacks. Codex remains the final authority. The explicit Luna native/CLI compatibility route remains available for execution roles that declare Codex subAgent.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Source Of Truth

- Primary consolidated discovery and confirmed decisions: `docs/REARCHITECTURE_DISCOVERY_20260812.md`, especially sections 4-8 and 11-17.
- Durable requirement and pitfall history: the current milestone at the top of `docs/PROJECT_CONTEXT.md`; older entries are supporting context, not current product authority.
- Current domain/state implementation: `app/models.py`, `app/router/pipeline.py`, `app/router/subjects.py`, `app/pipeline/ocr.py`, `app/pipeline/reviewer.py`, `app/processing_locks.py`.
- Current frontend/runtime implementation: `static/index.html` and six valid screenshots under `output/product_audit_20260812/`.
- Regression evidence: `tests/test_phase_workflow.py`, especially tests covering AND/OR conditions, laboratory analyte matching, syphilis exception logic, conmed denials, phase anchors, parent/child rules, OCR negation, and verdict reconciliation.
- Current launcher/runtime decision is already verified and out of conference scope.
- Do not read or modify raw subject source documents, source protocols outside this workspace, legacy project payloads, or historical session exports for this conference. The consolidated discovery contains the necessary evidence.

## Scope

- In scope: independently challenge the confirmed product model; assess the clinical-safety semantics of Patient Profile, evidence strength, gap classification, and action routing; assess whether Graph/multi-Agent boundaries are justified on a single Mac; propose a minimal durable architecture and phased implementation/acceptance sequence; identify unresolved contradictions or over-design.
- Out of scope: source-code edits, UI implementation, clinical reruns, changes to legacy projects, raw source-file inspection, final visual acceptance, or overturning explicit user decisions without evidence.

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production/source-clinical path is read or modified; Codex retains final acceptance.
- Each participant names at least one high-impact failure mode, identifies whether it is prevented by the proposed design, and gives a concrete remediation or acceptance test.
- The panel distinguishes deterministic workflow/state logic from semantic Agent work and does not assume more Agents improve quality.
- Recommendations remain compatible with local single-user, direct-launch operation, immutable raw evidence, fresh-project creation, and legacy read-only anchors.

## Parallel Work Rule

For logic-heavy, rigor-sensitive, or artifact-heavy tasks, each participant independently runs the whole bounded workflow and writes a separate output. Leads compare after all available participant outputs are in or explicitly marked pending.

## Timeout Policy

- Participant soft wait: 60 minutes.
- Large-task participant wait: 120 minutes.
- Chair hard wait: 120 minutes.
- Failure rule: Do not fail a model for slow response alone; fail only on terminal error, provider exhaustion/rate limit after controlled retry, empty/truncated retry output, or no useful progress after the high-budget same-session recovery loop. A catalog/auth/transport health preflight timeout or malformed response is diagnostic and must still allow one live route attempt; only a missing CLI or an explicitly invalid, retired, or unlisted model may block before live dispatch. If a resumable session exists after a step/size boundary, continue it before fallback; repeated identical output/tool evidence triggers the no-progress breaker.
- Pass/turn boundary: one conference prompt is one conference pass. The
  `--max-turns` value controls internal Agent tool-calling turns and is never
  set to 1 for substantive conference execution; generated participant and
  chair commands use the route budgets recorded by the guard.

## Risk Boundaries

- External Agents are advisory; Codex remains final authority.
- Codex owns visual/browser/PPT/PDF/rendered checks, live authority checks, final clinical/regulatory conclusions, and production writes.
- Do not mark a slow model failed solely due to latency.
- The product is AI-led but not the final enrollment authority. Do not redesign it into a multi-user approval system.
- Protocol/amendment is authoritative. Q&A/letters/email/medical interpretation may clarify ambiguity but cannot change or override the current protocol/amendment.
- Legacy projects are read-only counterexample anchors; the new system creates projects from scratch.
- Do not collapse record incompleteness, missing source file, required procedure not completed, professional judgment, OCR risk, conflict, and future-stage requirements into one `insufficient` status.

## Loop Log

- 2026-08-12 17:43:54: Conference initialized by `hermes_workflow_guard.py init-conference`.
- 2026-08-12: Source packet, bounded scope, confirmed user decisions, and participant challenge assignments added before dispatch.
- 2026-08-12: `general_pi_qwen38` completed through the effective daytime route `Pi/opencode-go/deepseek-v4-flash:max`; it identified the shipped conflict-precedence prompt as contradictory to the confirmed no-auto-pick requirement and proposed a deterministic judgment/gap consistency matrix.
- 2026-08-12: `general_grok45` produced only a preamble on the initial call, then completed through the same Grok Build session. It challenged mandatory multi-Agent/LangGraph use and recommended SQLite/WAL jobs, explicit state transitions, content-addressed OCR, conservative impact recomputation and a new frontend shell.
- 2026-08-12: Codex synthesis accepted the common representation/state/gate diagnosis; selected an explicit state machine with bounded typed Agent nodes and conditionally triggered veto-only Critic; rejected legacy write migration and arbitrary action auto-close.
- 2026-08-12: Final design and gated Phase 0-9 implementation plan written. Implementation remains paused pending explicit user approval.
