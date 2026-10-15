# Execution Context: phase5-selective-vision-single-page-e2e-20260901

Created: 2026-09-01 01:34:45 CST
Objective: 在全新隔离数据目录中，以一页内容中立的风险资料验证冻结证据修订到选择性视觉任务、智谱Coding Plan GLM-5.3-Flash真实调用、不可变观察落盘和用户查询投影的完整闭环；不得读取或修改D001/SAR旧结果，不得新增项目特异规则，不得以流程返回成功替代来源、观察正文与OCR不变性核对。
Task type: `finite_code_task`
Risk: `medium`
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

1. 只读审阅现有独立VLM真实连通测试、证据修订种子、视觉后处理执行器和观察仓储，提出最小单页隔离端到端验证方案、必要输入和失败判据；不得修改文件。
2. 作为唯一代码写者，在不新增依赖、不修改既有临床来源的前提下，优先复用测试夹具建立可显式启用的单页真实视觉端到端测试；只有发现通用根因时才做最小生产修复，并运行聚焦检查。
3. 只读独立攻击端到端验收设计与写者产物，重点核对是否真的走zhipu-token-plan等价Coding Plan端点、是否形成非空且来源匹配的观察、OCR原文/哈希是否不变、失败是否关闭、状态投影是否反映落盘结果；不得修改文件。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
