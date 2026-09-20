# Execution Context: phase5-slice58-runtime-bootstrap-20260824

Created: 2026-08-24 00:02:04
Objective: 为 Phase 5.8 建立 Evidence Normalizer 的生产可用、不可变且可验证的运行配置注册，确保全新数据库能够实际启动规范化任务，同时不误选其他 Agent 的配置。
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `codex-subagent` / `codex` / `gpt-5.6-luna`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `AGENTS.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/{prd.md,design.md,implement.md}`
- `.trellis/spec/backend/{index.md,quality-guidelines.md,error-handling.md}`
- `.trellis/spec/guides/{index.md,cross-layer-thinking-guide.md,code-reuse-thinking-guide.md}`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/slice53-real-evidence-normalizer-probe.md`
- `app/config.py`
- `app/api/v2/app.py`
- `app/services/fact_normalization_command_service.py`
- `app/domain/agent.py`
- `app/storage/sqlite/repositories.py`
- existing PromptVersion/ModelConfig registration and application-lifespan tests under `tests/v2/`
- Do not add production paths without explicit Codex authorization.

## Write Boundaries

- `worker_01`: read-only audit; no source or test edits.
- `worker_02`: may edit only `app/config.py`, `app/api/v2/app.py`, `app/services/fact_normalization_command_service.py`, and one new narrowly scoped service module if the existing ownership boundary demonstrably requires it.
- `worker_03`: may edit only focused tests under `tests/v2/` for Evidence Normalizer runtime registration, application startup, and command-service selection; do not edit production code.
- All workers must preserve the already dirty worktree and must not revert or reformat unrelated files.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 审计现有 PromptVersion、ModelConfig、应用 lifespan 与 FactNormalizationCommandService 的真实运行路径，确认全新数据库配置缺口及共享模式。
2. 实现 Evidence Normalizer 专属运行配置的确定性注册和精确选择，配置变化追加新身份、合同漂移失败关闭，不修改临床规则。
3. 补充全新应用启动、不可变身份、配置变化追加、错误配置拒绝及命令路径的聚焦回归测试，并执行相关测试。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
