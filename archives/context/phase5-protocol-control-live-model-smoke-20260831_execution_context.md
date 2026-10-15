# Execution Context: phase5-protocol-control-live-model-smoke-20260831

Created: 2026-08-31 01:58:53 CST
Objective: 建立方案控制点通用两阶段生产链的真实独立模型冒烟能力：先验证实际服务模型身份，再以词汇中立协议完成可复现运行并输出质量与运行指标，不解释D001或SAR具体医学内容，不物化正式控制目录。
Task type: `finite_code_task`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `night`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `codebuddy-cli/glm-5.3-flash:max -> codebuddy-cli/deepseek-v4-flash:max -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> openai-codex/gpt-5.6-luna:xhigh`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `codebuddy` / `codebuddy-cli` / `glm-5.3-flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- Architecture and phase contract: `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`, `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`.
- Current accepted boundary: `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260831_PROTOCOL_CONTROL_CANDIDATE_CHAIN_ACCEPTED.md`.
- Production candidate chain: `app/agents/protocol_control_agent_transport.py`, `app/agents/protocol_control_discovery_transport.py`, `app/agents/protocol_control_deconstructor.py`, `app/services/protocol_control_execution.py`, `app/services/protocol_control_executor.py`, `app/services/protocol_control_job_service.py`.
- Deterministic regression anchors: `tests/v2/protocols/test_protocol_control_agent_transport.py`, `tests/v2/protocols/test_protocol_control_production_regressions.py`, `tests/v2/services/test_protocol_control_execution.py`, `tests/v2/api/test_protocol_control_execution.py`.
- Runtime configuration: `app/config.py`, `.env.example`. Do not read or expose local secrets from `.env`.
- Observed runtime evidence before dispatch: `http://127.0.0.1:8002/health` was healthy but reported loaded model `pocketaihub-qwen3.8-27b-abliterated-mtplx-optimized-speed`; configured protocol-control model is `mtplx-qwen38-27b-optimized-quality`. A model-name field in an OpenAI request is not proof that the loaded model changed.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.
- Do not open, interpret, copy, or modify D001, MG-K10-SAR, other real protocols, subject files, legacy reports, or source clinical artifacts in this slice.
- Do not add project-, disease-, drug-, score-, threshold-, visit-, or time-window-specific detectors to shared code or prompts.
- Do not create a formal `ProtocolReviewControl` catalog and do not claim formal publication.
- A live call is allowed only after the requested model identity is positively matched to the actually loaded runtime model. When identity is absent, ambiguous, or mismatched, fail closed with a Chinese user-facing diagnostic; do not silently continue or substitute another model.
- Preserve the one-time structural snapshot and existing production executor boundary; no shortcut that feeds hand-authored protocol text directly to a deep-analysis Agent.
- Authorized write scope for worker 01: `app/agents/protocol_control_agent_transport.py`, `app/agents/protocol_control_discovery_transport.py`, a new shared model-identity helper only if needed, and focused tests under `tests/v2/protocols/`.
- Authorized write scope for worker 02: a minimal runner under `scripts/`, focused tests under `tests/tools/` or `tests/v2/services/`, and a synthetic fixture under `tests/fixtures/` only if required. It may read but must not edit production candidate-chain modules.
- Authorized write scope for worker 03: new focused anti-overfit or acceptance tests under `tests/v2/protocols/` and a compact read-only assessment in its runner-managed report. It must not edit production modules, prompts, clinical artifacts, or peer worker files.
- All workers may run focused tests. Do not run the full repository suite inside workers; Codex owns broad verification after integration.

## Done Evidence

- Deterministic tests prove runtime model mismatch, missing identity, and ambiguous aliases are fail-closed before a semantic request; a verified matching identity is accepted.
- A vocabulary-neutral synthetic protocol can be prepared through the real frozen-source job and production protocol-control executor, with a durable run record containing model identity, discovery distribution, deep scope, schema repair count, latency, result kind, formal catalog status, and failure class.
- The runner cannot bypass the production source snapshot, cannot consume real project fixtures by default, and refuses to run while the loaded model is the observed Speed variant but the configured target is Quality.
- Static and behavioral tests demonstrate that no D001/SAR-specific vocabulary or project-specific detector was added.
- `claims_complete=false` remains explicit.

## Work Items

1. 审计并加固协议控制传输的实际模型身份校验，禁止配置模型与服务加载模型不一致时静默运行。
2. 实现最小、可复现、词汇中立的真实生产harness冒烟运行器和持久化指标，不绕过冻结结构快照与正式执行器。
3. 补充确定性测试与独立反过拟合审查，验证无D001/SAR/药物/疾病/评分/时间点硬编码，并明确异构真实协议回放前置门禁。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
