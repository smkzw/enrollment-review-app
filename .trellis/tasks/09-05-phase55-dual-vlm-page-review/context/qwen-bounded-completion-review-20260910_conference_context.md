# Conference Context: qwen-bounded-completion-review-20260910

Created: 2026-09-10 00:21:32 CST
Objective: Read-only review of bounded missing-field repair and local early length guards; inspect frozen source and repeat diagnostic outputs, identify preservation, clinical-warning instability and minimal next verification. No model calls or service control. No implementation.
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

- Linked execution task: `qwen-bounded-completion-review-20260910`
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

- 2026-09-10 00:21:32 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
# Frozen Review Scope

Read-only fresh review. Repository root is three parent directories above this task workspace. Read only these repository-relative files: app/llm/json_missing_fields_repair.py, app/llm/generation_completion.py, app/llm/page_review_harness.py, app/agents/protocol_semantic_transport.py, scripts/qwen_request_diagnostic.py, tests/v2/llm/test_json_missing_fields_repair.py, tests/v2/scripts/test_qwen_request_diagnostic.py. For adjacent validation inspect app/agents/protocol_deconstructor.py only targeted schema/parser/validation and warning consumers.

Frozen original input and outputs under artifacts/qwen-three-platform-20260909-v3: mlx-serve/medium-protocol-d001/measurements/request-4.json; diagnostic-schema-prompt-d001-medium-01/response-0.json; diagnostic-missing-fields-d001-medium-01 and diagnostic-missing-fields-d001-medium-02 (response-0.json, completed_object.json, status.json). For response files extract only text, usage and timings; do not read private reasoning. Original request contains source excerpts. Independently assess source-to-rule preservation and whether schema completion can conceal semantic errors. Do not infer clinical acceptance from schema validity. These are diagnostic only; missing-fields repair is not integrated into formal product.

No writes, server calls, model requests, credential reads, outside clinical documents or service lifecycle operations. Return findings with file references, minimal fixes and next controlled validation criteria. Review does not authorize product acceptance. Main thread owns sequential local resources; conference is justified by material clinical interpretation and repair-boundary uncertainty.
