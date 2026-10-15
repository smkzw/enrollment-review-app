# Execution Context: enrollment-w1-selection-review-20260922

Created: 2026-09-22 15:45:12 CST
Objective: 为W1设计最小完整修订：工作稿与正式审核复用完整资格选择和跨章要求计算，但工作稿无批准副作用，正式发布仍须授权
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex assigned 1 bounded work item(s). Each item must identify its inputs, allowed paths, deliverable and acceptance check.
Route schedule: `peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> pi/cursor/default -> pi/openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor` -> `codebuddy` / `codebuddy-cli` / `deepseek-v4.1-flash`
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

1. 只读分析 qualified_binding_selection、frozen_review_calculation、eligibility_review_projection、review_context_assembly 及其消费者；给出函数级最小修改方案、合同边界、应删除死代码和Q1集中验证清单。不得修改文件，不得读取临床原件或密钥。

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
