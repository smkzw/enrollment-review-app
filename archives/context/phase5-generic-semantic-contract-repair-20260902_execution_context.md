# Execution Context: phase5-generic-semantic-contract-repair-20260902

Created: 2026-09-02 01:50:52 CST
Objective: 修正方案语义提示合同与确定性门禁之间的通用中文表达不一致，使非限制性人群描述、结构引导语、明确“之一”替代关系、共享期间和否定对象可被正确表达与核对，同时保持所有项目特异临床规则零硬编码。
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

1. 审查并最小修订方案语义提示合同：覆盖男女不限等非限制性范围、数值 source_term 逐字要求、共享期间来源绑定和否定对象命名，不写任何项目特异规则。
2. 审查并最小修订确定性门禁：通用识别非限制性表述与结构引导语，并正确验证“之一/任一”明确替代关系，保持实质条件 fail-closed。
3. 新增反过拟合故障注入与回归测试，使用合成中文条款证明新合同消除假阳性但仍拒绝真实遗漏、虚构任选关系、跨来源和未绑定时间窗。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
