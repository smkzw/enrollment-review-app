# Execution Context: phase5-ex07-issue-refinement-20260902

Created: 2026-09-02 03:45:03 CST
Objective: 修复局部方案语义修订把同一来源的覆盖缺失精化为未解析时间锚点时误判为无关新问题的通用边界；不得削弱发布门禁、不得写入 SAR/D001 特异逻辑。
Task type: `finite_code_task`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `night`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `zcode/glm-5.3-flash:max -> codebuddy-cli/deepseek-v4-flash:max -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> openai-codex/gpt-5.6-luna:xhigh`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `zcode` / `zcode` / `GLM-5.3-Flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- TODO: Codex must add authoritative source files, screenshots, datasets, or URLs before dispatch.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 在 app/agents/protocol_deconstructor.py 设计并实现最小问题精化比较，仅允许由同一父规则和同一来源定位证明的 PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING 到 TIME_ANCHOR_UNRESOLVED 精化；保留其余新指纹拒绝。
2. 在 tests/v2/protocols 增加服务级和比较器级反例，证明合法精化可保存但仍不可发布，外来来源、不同规则、不同未解析问题和普通新问题继续被拒绝。
3. 只读核查 app/protocols/deconstruction_gate.py 与现有跨项目测试，提出是否需要给 TIME_ANCHOR_UNRESOLVED 增加稳定来源定位；扫描新增实现不得包含项目、疾病、药物、评分或具体时间点硬编码。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
