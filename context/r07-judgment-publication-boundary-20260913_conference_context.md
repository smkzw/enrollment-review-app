# Conference Context: r07-judgment-publication-boundary-20260913

Created: 2026-09-13 14:55:30 CST
Objective: 只读审阅研究者判断未核实与已确认缺失进入正式审核合同的最小修复方案；不得为测试放宽采信或重写临床历史
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `grok/grok-build/grok-4.6:high -> pi/cursor/cursor-grok-4.6:high -> codex-subagent/codex/gpt-6-astra:low`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `r07-judgment-publication-boundary-20260913`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Current user requirement: missing investigator judgment may be reported only after complete valid source review; absent facts alone mean unverified. Two readers finding no required judgment does not require another user confirmation. Do not weaken this boundary to green tests.
- Read app/domain/gates/assessment.py, app/domain/expression.py, app/domain/contracts/context.py, app/domain/contracts/evidence.py, app/domain/contracts/uat.py; scripts/generate_v2_contracts.py; tests/v2/test_contract_artifacts.py; app/services/investigator_judgment_summary.py (discover actual filename if absent), judgment search summary contracts/repository/eligibility projection as needed.
- Design docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md section17.2 and recovery Plan T1. Current code is dirty, frozen for this review; no production DB/source documents or credentials permitted.
- Full test evidence artifacts/review-20260912/full-suite-20260913-binding-v6.xml: 4859 pass/14 fail/9 xfail. Eight stale page prompt fixtures now fixed, two budget tests fixed. Four historical contract artifact failures remain due evaluator professional_judgment_missing becoming professional_judgment_unverified. Do not assume they are only stale JSON.
- Generator was minimally adjusted to make the gap_conflict synthetic candidate indeterminate + observation_unverified rather than declaring missing judgment. In-memory three basic fixtures validate. build_uat_workspace now fails its required PROFESSIONAL_JUDGMENT coverage because there is no confirmed-missing fixture route. No generated fixture files have been overwritten. Attempt to use ABSENT EvidenceExpectation+PROFESSIONAL_JUDGMENT was rejected and reverted; do not relax that schema as a shortcut.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: source-bound diagnosis and minimal proposal for formal verified judgment absence/unknown handling, fixture generation and historical read compatibility. Identify existing reusable proof contracts and exact producer/consumer changes; give tests and rollout order. Challenge whether immediate fixture refresh is appropriate before the formal route exists.
- Out of scope: all edits, model calls, network research, databases, clinical source files, broad redesign, automatic semantic adoption or task acceptance.

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

- 2026-09-13 14:55:30 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
