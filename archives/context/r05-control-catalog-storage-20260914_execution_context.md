# Execution Context: r05-control-catalog-storage-20260914

Created: 2026-09-14 02:00:55 CST
Objective: 新增跨章控制目录的不可变版本合同与仓储；限定新文件，不迁移或运行数据库、不测试、不调用产品模型
Task type: `E03`
Risk: `high`
Execution module trigger: Codex assigned 1 bounded work item(s). Each item must identify its inputs, allowed paths, deliverable and acceptance check.
Route schedule: `off_peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> zcode/zcode/glm-5.3-flash:max -> pi/mtplx/mtplx-flash-next-optimized-speed:xhigh -> pi/openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `codebuddy` / `codebuddy-cli` / `deepseek-v4.1-flash`
- Review owner: Codex directly reviews worker outputs and final artifacts.

## Source Of Truth

- TODO: Codex must add authoritative source files, screenshots, datasets, or URLs before dispatch.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. 新增控制目录发布合同、ORM、追加写仓储和0024迁移草案；主线程负责发布服务与注册

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
