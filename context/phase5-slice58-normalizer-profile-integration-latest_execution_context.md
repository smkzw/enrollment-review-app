# Execution Context: phase5-slice58-normalizer-profile-integration-latest

Created: 2026-08-23 23:33:03
Objective: 补齐真实证据启用后事实规范化任务创建、任务完成后 Patient Profile 生成及前端可见状态，使 Phase 5.8 能用真实隔离项目运行；不得生成入排结论，不得绕过权威元组、活动资料和定位门禁。
Task type: `finite_code_task`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor_cms` -> `cursor` / `cursor-cli` / `auto`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- Product contract: `.trellis/tasks/08-22-phase5-clinical-facts-profile/{prd.md,design.md,implement.md}`.
- Runtime integration: `app/api/v2/app.py`, `app/api/v2/evidence_processing.py`, `app/services/fact_normalization_job_service.py`, `app/services/fact_normalization_executor.py`, `app/services/patient_profile_service.py`, `app/workflow/{jobstore.py,runner.py}`.
- Frontend and real-browser orchestration: `frontend/src/api/`, `frontend/src/pages/`, `frontend/src/features/`, `frontend/e2e/evidence-live-backend.spec.ts`, `frontend/e2e/phase5-real-acceptance-support.ts`, `frontend/e2e/phase5-real-acceptance.spec.ts`.
- Existing Phase 5 tests are executable evidence, not permission to weaken contracts. Legacy projects and real clinical source files remain read-only.
- Do not add production paths, mutate `data_v2`, or inspect clinical source outside the prepared isolated acceptance dataset.

## Cross-Worker Contracts And Authorized Writes

- Worker 01 owns only the backend command/API boundary and its focused tests: new `app/api/v2/fact_normalization*.py` and/or new `app/services/fact_normalization_command_service.py`, the minimal router/service registration in `app/api/v2/app.py`, and focused `tests/v2/api/test_fact_normalization*.py` / command-service tests. It must not edit the executor, Patient Profile service, frontend, or E2E files.
- Worker 02 owns only `app/services/fact_normalization_executor.py` plus focused executor/Profile integration tests. It may call the existing `PatientProfileService` but must not edit API, app registration, frontend, storage migrations, or Profile contracts/repository. Successful Profile generation must occur inside the finalize `PreparedStepResult.apply` transaction after publication/index/expectation projection and final authority revalidation. Do not invent a separate failure-status transaction in this worker; Codex will integrate failure projection only if the existing runner lifecycle supports it without corrupting the latest successful Profile.
- Worker 03 owns only new/shared frontend fact-normalization API/view-model files, the smallest relevant evidence/profile page or feature integration, focused frontend tests, and the two `frontend/e2e/phase5-real-acceptance*` files. It must not edit backend Python. Assume the backend exposes a subject/episode command returning a persistent job id and standard `/api/v2/jobs/{id}` recovery semantics; isolate endpoint naming in one frontend repository file so Codex can align it after worker 01.
- All workers may read adjacent code and tests needed to follow established patterns. They must not write runner-managed reports, generated screenshots, artifacts, task plans, or Trellis specifications.

## Non-Negotiable Product Semantics

- The client sends subject/episode and an idempotency intent only. The server derives the entire `FactAuthority` from the current `ReviewEpisode`, active `EvidenceSnapshotV2`, active complete processing revision, and the episode's frozen protocol/rule identities. Client-supplied authority, prompt id, model id, page plan, or hash is forbidden.
- PromptVersion and ModelConfig must be server-selected from registered immutable configuration for `EVIDENCE_NORMALIZER`; do not accept arbitrary client ids and do not seed test-only configuration in production request paths.
- Repeated commands for the same active authority/config/input must return the same run/job. Changed activity creates a new authority/run; stale publication remains rejected.
- A successful finalize must atomically persist facts, links, expectations, a succeeded Patient Profile revision, run status, and checkpoint. Any failure leaves the previous succeeded Profile revision readable and unchanged.
- UI text must be native Chinese clinical workflow language. Do not expose PromptVersion, ModelConfig, Agent, provider, schema, pipeline, internal error codes, or logs.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 实现后端事实规范化命令入口与应用注册：只从当前审核节点活动证据派生 FactAuthority，使用注册的 PromptVersion/ModelConfig 幂等创建持久任务，提供自然中文错误与恢复动作。
2. 在事实规范化 finalize 事务中生成不可变 Patient Profile，明确记录生成中/失败/成功，保持幂等、陈旧权威拒绝和上一活动版本不受失败影响。
3. 实现前端在资料版本启用后自动发起个例档案整理、展示持久任务状态并恢复；更新真实验收编排以等待实际 OCR、事实规范化、Profile、定位与历史，不使用 fixture。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
