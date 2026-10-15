# Execution Context: phase5-selective-vision-user-control-20260831

Created: 2026-08-31 22:36:25 CST
Objective: 为已冻结证据修订提供选择性视觉核验的用户可读状态、失败范围、人工重试与取消闭环，复用现有持久任务机制，不暴露模型/日志/工程字段，不改变OCR与临床语义。
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

- Product and phase contract: `.trellis/tasks/08-22-phase5-clinical-facts-profile/prd.md`, `.trellis/tasks/08-22-phase5-clinical-facts-profile/design.md`, `.trellis/tasks/08-22-phase5-clinical-facts-profile/implement.md`.
- Accepted orchestration checkpoint: `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260831_SELECTIVE_VISION_POSTFREEZE_ORCHESTRATION_ACCEPTED.md`.
- Existing backend route and state mechanisms: `app/services/selective_vision_postprocess_job_service.py`, `app/services/selective_vision_postprocess_executor.py`, `app/services/selective_vision_observation_service.py`, `app/services/job_service.py`, `app/workflow/jobstore.py`, `app/api/v2/jobs.py`, `app/api/v2/evidence_processing.py`, `app/api/v2/evidence_processing_schemas.py`, `app/services/evidence_api_read_service.py`.
- Existing frontend route and reusable task UI: `frontend/src/pages/EvidencePage.tsx`, `frontend/src/api/evidence/evidenceHttp.ts`, `frontend/src/api/evidence/evidenceProcessingViewModels.ts`, `frontend/src/api/evidence/evidenceJobHttp.ts`, `frontend/src/api/evidence/evidenceJobViewModels.ts`, `frontend/src/components/evidence-workspace/PersistentEvidenceTaskDetail.tsx`.
- Existing orchestration tests: `tests/v2/services/test_selective_vision_postfreeze_orchestration.py`.
- Worker 02 is the only production-code writer. Worker 03 may write only new test files whose names contain `selective_vision_user_control`; worker 01 is read-only.
- Do not modify source protocols, raw subject documents, legacy D001 results, `.env`, credentials, migrations already accepted in the prior slice, or unrelated frontend screenshots.
- Completion requires stable revision-to-job lookup, job-type validation before user actions, Chinese user-readable state, refresh recovery, retry/cancel through the existing Job mechanism, focused backend/frontend tests, and no model name, prompt, token, internal error classification, payload, or log text in the user interface.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 只读审阅现有Job、证据修订、观察仓储和API边界，提出最小稳定关联与失败关闭方案；不得修改任何文件。
2. 作为唯一生产代码写者，实现后端查询投影、重试/取消校验及前端证据工作台中文状态交互；复用现有任务接口和组件，不新增依赖。
3. 只新增或修改本切片专属测试文件，覆盖任务关联、错误类型、重试/取消、刷新恢复、中文文案与无内部字段泄露；不得修改生产文件。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
