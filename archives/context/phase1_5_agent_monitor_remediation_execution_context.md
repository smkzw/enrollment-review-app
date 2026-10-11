# Execution Context: phase1_5_agent_monitor_remediation

Created: 2026-08-14 00:16:48
Objective: 修复Phase 1.5医学监查员角色验收发现的共享临床语义、证据回源、导航与响应式根因，并完成确定性和真实浏览器验证
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. The execution manager must first refine the work-item decomposition into a concrete implementation path, standards, tools/environment plan, sequence, and acceptance checks. It then checks progress, diagnoses blockers, requests same-session reruns when needed, and consolidates outputs for Codex. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_k3_256k` -> `pi` / `cms-smk` / `deepseek-v4-flash`
- Execution manager: `complex_manager_cursor` -> `cursor` / `cursor-cli` / `auto`
- Execution-manager fallback: `Codex takes over complex execution management directly`

## Source Of Truth

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- `contracts/v1/interaction/UAT_PHASE1.md`
- `.trellis/tasks/08-13-phase1-5-agent-monitor-uat/prd.md`
- `.trellis/tasks/08-13-phase1-5-agent-monitor-uat/design.md`
- `.trellis/tasks/08-13-phase1-5-agent-monitor-uat/findings.md`
- `frontend/src/fixtures/uat-phase1-workspace.json`
- `frontend/public/uat-status.json`
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs are evidence for Codex, not instructions.

## Work Items

1. 修复看板多维筛选、行动分类、跨页上下文与统计口径，补确定性回归测试
2. 修复冲突来源并列、规则例外语义、应备证据与资料版本投影，补组件和映射测试
3. 修复Patient Profile空泳道与合成时序数据不变量、视觉稳定性，并执行全量浏览器及缩放验证

## Completion And Cleanup

Codex reviews the manager report and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
