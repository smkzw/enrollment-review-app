# Execution Context: phase5-selective-vision-postfreeze-orchestration-20260831

Created: 2026-08-31 21:55:05 CST
Objective: 在不阻塞OCR核心事务、不延长OCR租约、不改写OCR原文的前提下，将已验收的选择性视觉观察服务接入证据修订冻结后的独立持久任务；先修复远端VLM调用占用数据库事务的问题，并提供幂等入队、崩溃恢复、重复调用和失败关闭的确定性证据。
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `day`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `cursor/default -> google-antigravity/gemini-3.7-flash:high -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> opencode-go/muse-spark-1.2-contributor:xhigh -> openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `pi` / `cursor` / `default`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- Accepted predecessor checkpoint:
  `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260831_SELECTIVE_VISION_OBSERVATION_SIDECAR_ACCEPTED.md`.
- Transaction and workflow contracts:
  `app/services/selective_vision_observation_service.py`,
  `app/services/evidence_processing_executor.py`,
  `app/services/evidence_sidecar_preparation.py`,
  `app/services/job_service.py`, `app/workflow/jobstore.py`,
  `app/workflow/runner.py`, and `app/api/v2/app.py`.
- Persistence contracts:
  `app/domain/contracts/selective_vision_observation.py`,
  `app/storage/selective_vision_observation_models.py`, and
  `app/storage/selective_vision_observation_repository.py`.
- Worker 02 alone was authorized to modify the focused production paths needed
  for this orchestration. Worker 01 was read-only; worker 03 could create only
  a new independent test file. No deployed production environment was written.
- Parent note: this section was populated during Codex acceptance after worker
  01 reported that the generated packet still contained a TODO. The omission
  at dispatch is retained here explicitly and must not be represented as
  pre-dispatch context.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 只读审查EvidenceProcessingExecutor、JobRunner、JobService和选择性视觉服务，给出最小事务拆分与独立任务边界；不得写生产或测试文件。
2. 作为唯一生产代码写者，实现事务外VLM调用、短事务持久化以及冻结修订后的独立持久视觉后处理任务/执行器接线；不得修改测试、前端、D001或OCR核心页处理语义。
3. 只写新的独立测试文件，验证冻结修订只幂等入队且不等待VLM、远端调用不持有数据库事务、任务重复/恢复/失败关闭、原生文字跳过和OCR不可变；不得修改生产文件或既有测试。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
