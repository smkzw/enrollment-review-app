# Execution Context: r06-source-inheritance-20260913

Created: 2026-09-13 17:09:05 CST
Objective: 修复后续事实发布丢失既往已验证来源，保留严格跨运行来源与更正边界
Task type: `finite_code_task`
Risk: `high`
Execution module trigger: Codex assigned 1 bounded work item(s). Each item must identify its inputs, allowed paths, deliverable and acceptance check.
Route schedule: `peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `pi/cursor/default -> codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> pi/openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `pi` / `cursor` / `default`
- Review owner: Codex directly reviews worker outputs and final artifacts.

## Source Of Truth

- Read app/services/fact_publication_service.py, app/storage/fact_repositories.py, their referenced domain contracts and correction services, tests/v2/services/test_fact_publication_service.py (especially test_later_run_preserves_fact_identity_and_sources). Follow only adjacent consumers as needed.
- Read-only source analysis only: no file edits, database access, model calls, network, dependency installation or test execution. Report an implementable minimal design with concrete definitions and positive/negative tests. Do not assume a source union is valid: current repository enforces current-run candidates/gates. Preserve authority, stable identity, immutable history, corrections and source closure. Compare explicit inheritance proof with alternatives; identify affected event/exposure consumers.
- Existing working tree is shared and dirty. Do not reset, clean, or alter it. Product clinical acceptance remains open.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. 只读分析R06并提出最小可验证修复设计，不修改应用文件或数据库；重点审阅事实发布仓库同运行校验与显式继承证明，给出正反例测试清单

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
