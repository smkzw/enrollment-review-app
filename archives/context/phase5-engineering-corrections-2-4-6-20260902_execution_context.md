# Execution Context: phase5-engineering-corrections-2-4-6-20260902

Created: 2026-09-02 04:50:03 CST
Objective: 按2026-09-01工程纠偏清单，以Ponytail最小改动完成生产依赖归位、方案语义传输中性命名、方案PDF入口下线及主仓旧前端副本清理，并保持受试者证据PDF路径不变
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 4 independent work items, which is greater than two.
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

1. 将openai与pymupdf从dev依赖移入主依赖，更新锁文件，并验证uv sync --no-dev环境可导入生产路径依赖
2. 将deepseek_protocol_transport.py更名为中性protocol_semantic_transport.py，提供最小兼容迁移并更新生产引用和测试
3. 仅下线研究方案PDF上传与结构分派入口，删除方案侧pdf_structure公开入口和相关测试，保持受试者证据PDF处理不变
4. 核对并删除主检出目录中明确列入纠偏清单的两个未跟踪旧前端API副本，记录worktree设计书与实施计划为权威版本

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
