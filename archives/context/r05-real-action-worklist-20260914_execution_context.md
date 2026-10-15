# Execution Context: r05-real-action-worklist-20260914

Created: 2026-09-14 15:41:21 CST
Objective: 实现正式待办只读清单服务和薄API，复用已有冻结审核历史与ActionRequest，不读trial，不新建状态机。
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

- Read .trellis/spec/backend/index.md; app/services/review_history_service.py; app/api/v2/review_history.py; app/api/v2/review_actions.py; app/services/evidence_app_errors.py; relevant ActionRequestRecord/ReviewRunRecord models and project lookup in app/storage/repositories.py; docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md section17.6 only.
- Allowed writes ONLY the two NEW files named below. Manual edits use apply_patch. Do not edit shared files, frontend, tests, migrations, docs, or runtime data. Do not run tests, imports/application, DB queries, models or browsers. Source inspection and py_compile of your two new files are allowed. No recursive dispatch.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. 新增app/services/review_action_worklist.py及app/api/v2/review_action_worklist.py：项目作用域、分页、真实冻结审核来源、历史未办结不静默消失；仅源码实现，禁止测试/数据库/模型/浏览器，不注册应用、不改既有文件。

Concrete contract:
- GET /api/v2/projects/{project_id}/review-actions. Query mode open (OPEN/REOPENED) or all; limit 1-100 default50; after_action_id optional for stable action-id keyset. Response includes project_id, mode, items, next_after_action_id. Do not invent global total or clinical completion from this page.
- Validate project existence using existing repository patterns. Only review/v2 actions with actual frozen run/context are eligible; no fixture/trial or current derived projection. Never select only latest run and hide unresolved older actions.
- Candidate query is bounded limit+1 with deterministic action-id order. Group visible rows by run; use existing get_run exactly once per needed run to verify stored action, gate, frozen sources. Any inconsistent visible record fails the request with existing Chinese error handling; do not omit it as empty success. No imports of SQLAlchemy/storage in thin API.
- Each item supplies existing ReviewHistoryActionDTO (reuse _action_dto if appropriate) plus frozen context project name, subject code, review_episode_id, review_run_id, workflow stage label, completed_at/started_at needed to link original report. Do not assemble another clinical opinion or duplicate ActionRequest schema. Service may return dataclass wrapping the verified action/context/run metadata; API maps it.
- Preserve current manual response command separately. This endpoint is read-only and is NOT permission to approve methods or publish results. Owner will register and build frontend after reviewing your artifacts.
- Keep files compact and no broad repo scan. If existing models lack needed columns, inspect payload strategy and report precise limitation; do not alter schema.

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
