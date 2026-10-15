# Execution Context: phase5-large-parent-semantic-segmentation-20260901

Created: 2026-09-01 09:42:12 CST
Objective: 为超大官方父规则建立项目无关的结构分段、有限并发和确定性同父规则合并合同，在保留父子编号、逻辑、例外、来源与完整性门禁的前提下降低 GLM 方案语义解构时延；不得按 D001、SAR、疾病、药物、量表、条款编号或时间点硬编码，不恢复旧 D001/SAR 作业。
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `day`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `cursor/default -> google-antigravity/gemini-3.7-flash:high -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> opencode-go/muse-spark-1.2-contributor:xhigh -> openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `pi` / `cursor` / `default`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260901_SEMANTIC_MODEL_ROUTING_GLM_PROBE_ACCEPTED.md`
- `artifacts/phase5-acceptance/20260901/glm-semantic-route-probe-ex06-20260901/REVALIDATION.md`
- Existing contracts in `app/agents/protocol_deconstructor.py`,
  `app/services/protocol_deconstruction_executor.py`,
  `app/agents/protocol_semantic_model_router.py`,
  `app/protocols/deconstruction_gate.py`, and their tests under `tests/v2/`.
- Worker 01 is design-only. Worker 02 may read worker 01's completed runner report
  before implementation. Worker 03 may read the completed implementation and
  worker 02 report only to build independent tests; it must not accept worker 02's
  claims without running those tests.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.
- Do not call GLM, MTPLX, DeepSeek or any other clinical semantic provider in this
  execution pass. Deterministic tests only; Codex owns later live probes.
- Do not read or modify the source protocol, raw subject files, the paused D001
  SQLite job, or the failed SAR SQLite job.
- Worker 02 may modify only `app/agents/protocol_deconstructor.py`,
  `app/services/protocol_deconstruction_executor.py`, `app/config.py`,
  `.env.example`, and one new project-neutral module under `app/agents/` or
  `app/protocols/` when needed. Worker 03 may modify only new or directly related
  tests under `tests/v2/agents/` and `tests/v2/protocols/`.
- All manual source edits must use the available patch/edit mechanism. Preserve
  unrelated user changes and do not clean generated/history files.

## Codex Decisions After Worker 01 Review

- Parallel-safe segments use fresh provider sessions. The deterministic merge
  assigns the final same-parent call identity; provider session ids remain in
  route/segment audit and are never represented as one shared chat session.
- Any segment schema, source-closure, dependency or transport failure triggers
  at most one whole-parent fallback under the same provider attempt. Partial
  parent publication is forbidden.
- Segmentation is enabled only when the project-neutral structural planner can
  produce at least two substantive safe segments. Token size, source-span count
  and obligation structure may trigger planning; token size alone may not force
  an unsafe cut. Ambiguous shared qualifiers, exceptions, conjunctions or
  cross-segment binders collapse to a serial cluster or whole-parent path.
- Place the planner/merge contract in one new neutral module under
  `app/protocols/`. Default bounded concurrency is 2 with a hard cap of 3.
- Preserve the existing small-parent and inter-parent path without behavior
  change. This optimization must not weaken the final deconstruction gate.

## Work Items

1. 只读审查现有方案语义提示、批次、会话、缓存、门禁和路由合同，提出超大父规则内部结构分段与同父规则确定性合并设计，重点识别不可安全并行的父级限定语、例外和跨段依赖。
2. 按经审查的通用合同实现超大父规则结构分段、有限并发调度和同父规则确定性合并，保持完整路由审计、失败关闭、缓存模型身份隔离和旧调用兼容；仅修改授权代码与配置。
3. 独立编写并运行跨项目中性样本和对抗测试，验证父级限定语继承、AND/OR、例外、跨段依赖、来源闭包、合并确定性、并发上限、失败回退及无项目特异硬编码；不得以实现者自报作为通过依据。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
