# Conference Context: qwen-harness-iteration-20260910

Created: 2026-09-09 23:25:25 CST
Objective: 只读审阅实际产品方案解构harness的结构化输出、重复生成与纠正流程。针对MLX Serve两档重复JSON语法失效、grammar disabling mask、length非真实预算耗尽、客户端断开崩溃，提出最小通用修复及冻结同源单因素验证。不得运行本地模型、不得修改代码、不得以更换模型或补写临床答案掩盖失败。
Task type: `C03`
Risk: `high`
Conference mode: `parallel`

## Codex Main Venue

## Authorized Frozen Evidence And Concrete Questions

Repository root (read-only): /Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile . You may read only these root-relative files and their directly imported schema/transport helpers, not credentials or personal harness configuration:
- app/agents/protocol_semantic_transport.py; app/agents/protocol_deconstructor.py; app/llm/page_review_harness.py; app/llm/page_review_format_repair.py; app/llm/generation_repetition.py
- scripts/qwen_platform_measurement.py; scripts/qwen_protocol_measurement.py; scripts/qwen_request_diagnostic.py
- artifacts/qwen-three-platform-20260909-v3/mlx-serve/medium-protocol-d001/measurements/request-4.json, response-4.json, request-5.json, response-5.json
- artifacts/qwen-three-platform-20260909-v3/mlx-serve/low-protocol-sar/measurements/receipts.json
- artifacts/qwen-three-platform-20260909-v3/mlx-serve/pause-server-11234.log (large; use targeted grep/tail, never dump)
- .trellis/tasks/09-05-phase55-dual-vlm-page-review/HANDOFF_20260909_HARNESS_REPAIR.md

Sources contain real clinical excerpts; read only, no external sharing beyond this authorized model review. No browser/web or model calls. Review frozen inputs, not ongoing models. Propose a minimal experiment before wider reruns: same exact messages/schema description, change only constrained decoding versus unconstrained JSON with unchanged local strict validation. Challenge whether schema is absent from prompt if wire schema removed. Distinguish actual max-token exhaustion from platform repetition_loop returning length; current product blindly expands budget on length. Scope format repair to structure without changing legitimate facts or guessing clinical values. Evaluate context/granularity simplification as separate versioned experiment, not simultaneous changes. User explicitly wants iterative optimize-test loops before fair standardized comparison, not repeated known-bad benchmark runs. Give source-backed findings, smallest fixes/tests, and stopping criteria. Do not assert all models can necessarily be made reliable.

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `zcode/glm-5.3:max -> xai/grok-4.6:high -> xai/grok-4.6:high -> openai-codex/gpt-6-astra:low`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `qwen-harness-iteration-20260910`
- Execution evidence status: `no linked execution packet`
- Excluded provider/model nodes: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

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

- 2026-09-09 23:25:25 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
