# Execution Context: phase5-sar-fresh-protocol-live-20260901

Created: 2026-09-01 17:47:16 CST
Objective: 在 sar31001-fresh 全新隔离数据根中启动专用 V2，使用 GLM-5.3-Flash high 主路由从哈希验证的原始 DOCX 新建 SAR III 方案作业，完成一次结构提取、全方案高召回控制点发现和候选深度解构；不得复用旧失败库、不得恢复 D001 第20包、不得加入项目特异规则，并保留模型路由、耗时、来源与门禁证据。
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `day`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `openai-codex/gpt-5.6-luna:max -> codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor` -> `pi` / `openai-codex` / `gpt-5.6-luna`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260901_FRESH_SUBJECT_RUNTIME_ROUTING_ACCEPTED.md`
- `artifacts/phase5-acceptance/20260901/manifests/sar-protocol.json`
- `artifacts/phase5-acceptance/20260901/manifests/sar-31001.json`
- `artifacts/phase5-acceptance/20260901/isolated-inputs/sar/protocol/4. Protocol/MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx`
- `artifacts/phase5-acceptance/20260901/runtime-data/fresh-subject-runtime-contract.json`
- `artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/`
- `tools/phase5_acceptance/fresh_runtime.py`
- `app/api/v2/protocols.py`, `app/api/v2/app.py`, `app/services/protocol_workbench_service.py`, `app/services/protocol_deconstruction_executor.py`
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`, `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`

## Risk Boundaries

- No production writes.
- `worker_01` and `worker_03` are read-only except their runner-managed reports.
- `worker_02` is the sole runtime writer. It may create only new business state under `artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/` and new run evidence under `artifacts/phase5-acceptance/20260901/live-runs/sar31001-fresh-protocol/`.
- `worker_02` may start/stop a dedicated local V2 process on an unused port in `8910-8919`; it must not stop or mutate services on 8900, 8000, or 8001 and must not start MTPLX unless the product route actually reaches that fallback after a terminal GLM attempt.
- No worker may edit application source, tests, prompts, clinical source files, manifests, old runtime databases, or immutable checkpoints in this pass. Unexpected product defects must be reported for Codex remediation rather than patched during the live run.
- The old `runtime-data/sar31001` database and D001 package 20 are forbidden read-only counterexamples, never retry sources.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Acceptance Signals

- Fresh runtime validation passes immediately before service start and immediately before creating the protocol job.
- A new SQLite/job identity is created only under `sar31001-fresh`; no old job id is reused.
- Register/extract/render/freeze use the verified DOCX copy once. Semantic discovery reads the frozen whole-protocol structure, while deep analysis is limited to candidates/uncertain items; no whole-document page-by-page VLM rerun.
- The persisted route audit records GLM-5.3-Flash high as route attempt 1. Any fallback must be a complete new attempt with an explicit terminal reason.
- Completion requires source closure, route audit, step timing, final gate status, and a project-neutral hardcoding scan. A transport success or parseable JSON alone is not acceptance.

## Work Items

1. 只读核对全新运行门禁、输入清单、端口、服务启动命令和数据根身份；给出可执行前置检查及污染阻断清单，不启动模型、不修改数据库。
2. 单写者在通过门禁的 sar31001-fresh 根启动专用 V2 并从哈希验证 DOCX 新建真实方案解构作业；复杂语义必须 GLM-5.3-Flash high 首选，记录作业、步骤、路由、耗时和失败恢复，不续跑任何旧 job。
3. 独立只读审计新作业的来源闭包、全方案控制点覆盖、模型身份、无项目特异硬编码及失败关闭；如结果尚未完成，明确持续观察点和不可接受条件，不修改临床候选。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
