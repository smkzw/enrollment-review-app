# Conference Context: r05-formal-publication-actions-20260914

Created: 2026-09-14 15:11:10 CST
Objective: 只读源码审阅V2正式整批保存与既有ActionRequest扩展控制来源的全链。禁止测试、应用import、DB读写、产品调用、递归派发和任何文件编辑。检查原子性/幂等/历史不改写、旧载荷哈希兼容、控制来源/强度、报告办理联动、method-adoption与资格授权边界。正式HTTP入口未启用、评测批准签发未实现、临床语义完整性仍开放，不把保守UNKNOWN当完成。指出真实代码缺陷并给最小修复方案，按文件行号。
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

- Linked execution task: `r05-formal-publication-actions-20260914`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` sections 17.1-17.4; current recovery Plan T5. Source modules explicitly listed in role prompt. New path is not enabled; method approval issuance and clinical evidence validation are not proven by this review.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: source-only end-to-end inspection of new publication, shared action origin, migration draft, storage verification, history/API/frontend consumers. No deliberate narrowing to contracts alone.
- Out of scope: execution/tests/imports, databases, real clinical documents, product models, browser, credential discovery, recursive delegation, file writes.

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

- 2026-09-14 15:11:10 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
