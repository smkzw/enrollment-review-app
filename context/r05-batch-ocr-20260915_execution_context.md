# Execution Context: r05-batch-ocr-20260915

Created: 2026-09-15 05:01:56 CST
Objective: 实现批量原件重新识别后台，复用现有任务恢复，不改原结果、不自动启用
Task type: `E03`
Risk: `medium`
Execution module trigger: Codex assigned 1 bounded work item(s). Each item must identify its inputs, allowed paths, deliverable and acceptance check.
Route schedule: `off_peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> zcode/zcode/glm-5.3-flash:max -> pi/mtplx/mtplx-flash-next-optimized-speed:xhigh -> pi/openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `codebuddy` / `codebuddy-cli` / `deepseek-v4.1-flash`
- Review owner: Codex directly reviews worker outputs and final artifacts.

## Source Of Truth

- Read app/services/evidence_reprocessing.py, batch_review_workflow.py, batch_review_view.py; app/workflow/jobstore.py, runner.py, recovery.py; domain contracts and repositories only as needed; .trellis/spec/backend/index.md and database guidelines. Design: docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md section 17; plan T5 batch OCR. No clinical files, secrets, or other checkout.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. 批量OCR后台服务及读取投影，所有者负责API与前端集成，禁止运行测试、模型和数据库

## Exact Implementation Contract

Allowed writes ONLY app/services/batch_evidence_reprocessing.py, app/services/batch_evidence_reprocessing_view.py (new modules), and minimal additions/refactoring within app/services/evidence_reprocessing.py for explicit batch ownership/atomic child creation. Owner handles app.py/API/UI; do not touch them, existing batch-review modules, docs, tests or other files. Use apply_patch. No dependency installs or Git cleanup. Only py_compile and diff --check allowed, no import/application/DB/model/test/browser runs. Do not call an external model as product inference. Runner is engineering delegation only.

Use existing JobStore + deferred maintenance continuation pattern from BatchReviewContinuation, not new tables/threads/scheduler nor a long-running step waiting for children. Per-project explicit 1–50 unique nodes, freeze member {subject_id,review_episode_id,snapshot_id,complete_id} and OCR profile identity. Validate all sources and current pointers before creating batch. Ordered members, one child at a time, wait child terminal via release_deferred. A terminal child failure/cancel is recorded honestly and next member continues; intake/source/profile integrity failure stops unstarted remainder explicitly. Batch completion is processing completion only, never activation or clinical acceptance. New stable job type/contract and OWNER string, stable request-key idempotency.

Expose enqueue_reprocessing_batch(session_factory,adapter,*,project_id,members,request_key), BatchReprocessingContinuation(session_factory,adapter,*,worker_id) __call__(runner), BatchReprocessingRetryService(...).retry(batch_id), change_reprocessing_batch(...operation), cancel_batch_children(session_factory,batch_id) and view/recent functions. Choose coherent exact signatures and document for owner. Recent list thin parent metadata only with bounded pagination; details must verify own member/child/frozen identity, do not replace corrupt data with empty success.

Child creation must atomically recheck parent cancellation/membership and profile and fresh source under SQLite BEGIN IMMEDIATE, following existing enqueue_reprocessing. Add optional batch_job_id to ReprocessingInput with OMIT-NONE serializer so existing single-job payloads/hash compatibility are unchanged; only for this explicit batch path. Reprocessing idempotency must distinguish independent jobs vs batch ownership and never cancel an independently created job. Existing frozen single-job semantics and original source/cache preservation must remain. Avoid duplicating all single reprocessing creation logic; a private in-session helper is acceptable, no whole-module rewrite.

Cancellation only verified owned children, corrupted member ownership must not prevent stopping other provably owned members. Do not change healthy sessions on live profile change while polling; check frozen profile only before NEW child. Manual parent retry forbidden for cancelled batch; validates same profile. Previously terminal completed members remain frozen. Original batch outcome vs child's later manual retry must not be conflated in view. Parent maintenance errors must not starve unrelated batches or break runner. Reuse runtime receipts/event/checkpoint primitives.

Keep code small but complete. Return interface summary, files, source checks and residual issues. Do not claim runtime acceptance or run staged tests. If unable to finish, exact partial scope; owner will continue same session.

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
