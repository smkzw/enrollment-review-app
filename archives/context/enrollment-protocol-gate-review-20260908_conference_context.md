# Conference Context: enrollment-protocol-gate-review-20260908

Created: 2026-09-08 11:28:59 CST
Objective: 只读独立核对已结束D001 low方案解构：对照正式DOCX、实际草稿和校验实现，区分真实语义错误与校验误报，审阅修复循环的代价；不修改、不调用临床模型、不发布规则。
Task type: `C01`
Risk: `medium`
Conference mode: `parallel`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`general_single_object`) with no sub-venue chair. Its effective `CST` route chain is `zcode/glm-5.3-flash:max -> opencode-go/muse-spark-1.3-contributor:xhigh -> codebuddy-cli/deepseek-v4-flash:max -> openai-codex/gpt-5.6-sol:medium`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `enrollment-protocol-gate-review-20260908`
- Execution evidence status: `no linked execution packet`
- Excluded provider/model nodes: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Frozen completed run: artifacts/phase55-model-comparison/20260907/protocol-native-runs/d001-glm-low-v1. Read execute/execute_record.json then SQLite in mode=ro, tables protocol_draft_revisions and job_checkpoints (freeze_deconstruction_input, generate_draft, integrity_check). Use structured queries with selective output, never print entire checkpoints (large).
- Authoritative original DOCX: artifacts/phase5-acceptance/20260823/isolated-inputs/d001/protocol/test-D001项目/CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx. Do not alter. May read with python-docx or source-preserving tools. Phase II explicitly selected. Read relevant source original text, not filename date as authority.
- Relevant code: app/protocols/deconstruction_gate.py and modules it imports for boolean/source/temporal validation; app/agents/protocol_deconstructor.py; app/agents/protocol_semantic_transport.py. Allowed offline read-only diagnostics with .venv/bin/python, no files written except isolated /tmp synthetic fixtures if essential.
- Do not read other artifacts, owner comparison findings, credential files, personal harness configs, patient data or other task context. No API/model/OCR calls, no source/production/database writes, no service lifecycle changes. Final response only; runner persists report. No recursive delegation.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: independently assess whether remaining checks for IN-06, EX-02, EX-14 are justified by original source and actual structured draft; examine raw request/response budget and context growth to distinguish model errors from contract/checker failures. You may inspect another remaining clause if essential to avoid cherry-picking. For each issue cite exact source locator and code line, explain false-positive/true-error/uncertain and minimal general fix plus regression examples. Do not assume the owner's interpretation, all checks, or the model are correct. Clinical criteria are not to be silently weakened.
- Out of scope: final model ranking, product release, changing records, rewriting rules yourself, new clinical decisions or treating this one protocol as universal proof. This is review of a frozen completed run, not a clinical model benchmark candidate.
- Scope restriction: scheduled packet fallback lists were intentionally narrowed to none before dispatch, retaining the approved primary. No contributor or other fallback receives these sources. If primary fails, preserve result and return limitation. Same family as the tested GLM is reduced model independence and must be acknowledged, though review context is fresh.

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

- 2026-09-08 11:28:59 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
