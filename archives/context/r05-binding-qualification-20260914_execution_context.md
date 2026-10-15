# Execution Context: r05-binding-qualification-20260914

Created: 2026-09-14 12:36:45 CST
Objective: Implement source-qualified binding production and integrate with existing candidate JobRunner, without enabling clinical autoacceptance. Follow current design 17.1.1 and frozen inputs; preserve existing work.
Task type: `E03`
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

- 来源与允许路径在派发前已完整写入worker_01.md具体合同；本处事后补齐索引，不声称此模板当时已填写：工程设计§17.1.1/17.2、恢复Plan T5、既有predicate/control binding jobs、冻结合同与回执格式。仅新增binding_qualification命名模块及必要生产者接线；产品DB/原件/模型调用及阶段测试禁止。
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. Build a complete versioned qualification stage for existing predicate/control candidate jobs; preserve provenance and unresolved cases; no product calls or staged tests.

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
