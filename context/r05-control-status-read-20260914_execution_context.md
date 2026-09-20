# Execution Context: r05-control-status-read-20260914

Created: 2026-09-14 02:28:25 CST
Objective: 补充审核要求作业的只读状态与可发布检查点接口，严格绑定完成状态和版本，不调用模型、不运行测试或数据库
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

- Read app/services/protocol_control_execution.py (job payload, final checkpoint, replay validation), app/services/protocol_control_catalog_publication.py, app/api/v2/protocol_control.py, app/api/v2/protocol_control_schemas.py, app/storage/models.py job/step/checkpoint definitions and existing jobs API/query conventions. Read complete affected definitions, not full unrelated files.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. 新增只读状态服务并连接已有protocol control API/schema，供正式发布提交显式检查点；其余产品构建主线程负责

## Owner Contract

Allowed writes ONLY: new app/services/protocol_control_status.py; existing app/api/v2/protocol_control.py and app/api/v2/protocol_control_schemas.py. Do not change execution, publication, storage, models, frontend, docs, tests or any other file. Runner owns report output. Shared worktree is dirty; preserve all unrelated changes.

Implement GET /api/v2/protocol/control-executions/{job_id}. Use existing session_factory via protocol_control_job_service, keep read service separate from giant executor. Read-only response identifies exact job/source deconstruction job and state, plus final checkpoint ID and candidate count ONLY when completed, not cancelled, correct final step/checkpoint and payload hashes/version/result kind/accepted/candidate identity closure are verified. A ready candidate package is not a published catalog and not clinical approval: use candidate_ready with user-native label such as 补充审核要求已整理，等待随方案发布. Never expose credentials, payload source text or backend exception logs. Incomplete job returns no publishable checkpoint, no guessed zero count; missing/wrong-type job follows existing 404 conventions. Corrupt/ambiguous completed checkpoint must not look ready; use established error conventions. Determine proper checkpoint selection from current stored step/checkpoint schema, do not guess newest unrelated checkpoint and do not use source job's draft as candidate evidence. Preserve POST behavior. Source job ID is payload source_deconstruction_job_id; verify actual field.

No process execution other than read tools and .venv/bin/python -m py_compile or simple module import of affected modules. DO NOT run tests, including in-memory synthetic assertions, pytest, DB initialization, migration, create_app, server, browser, models, network, dependency installs, original clinical material. User explicitly defers all staged tests until complete construction. Report code paths, identity checks, unverified runtime boundaries and any unresolved API design issue. Do not mark goal/clinical acceptance. Compile-only is sufficient assignment completion; owner integrates and later full tests.

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
