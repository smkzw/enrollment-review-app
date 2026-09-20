# Execution Context: phase5-protocol-control-discovery-production-integration-20260831

Created: 2026-08-31 00:04:26 CST
Objective: 将已验收的通用两阶段方案控制点发现与深析合同接入可持久化生产执行链：原始DOCX/PDF结构化一次，全清单由独立模型高召回发现，只有候选/不确定单元进入深析，确定性代码负责身份、闭包、上下文、重试与发布门禁；不得加入任何项目、疾病、药物、量表、时间点或阈值硬编码。
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 4 independent work items, which is greater than two.
Route schedule: `unscheduled`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `openai-codex/gpt-5.6-luna:max -> codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor` -> `pi` / `openai-codex` / `gpt-5.6-luna`
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

1. 审计现有 discovery/deep transport、runner、executor、jobstore、API 调用链，提出并实现最小通用接入边界；不得手工解释协议内容。
2. 实现 discovery 专用严格结构化 transport/runner 与有限同会话修复，使模型输出仅能提交四类处置、理由和必要上下文，身份与闭包由系统掌控。
3. 实现可恢复的 protocol-control executor/job/API 编排，复用一次性 DOCX/PDF 结构快照，串接 discovery→deterministic closure→deep→hydrate→gate，禁止回落到 legacy reviewer。
4. 增加合成与异质只读回归测试，证明无 D001/SAR 特例、无词表过滤、无全文反复深析；用 fake transport 验证失败/修复/恢复/门禁路径，并明确真实模型运行仍属后续验收。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
