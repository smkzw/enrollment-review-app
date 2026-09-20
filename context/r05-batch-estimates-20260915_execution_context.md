# Execution Context: r05-batch-estimates-20260915

Created: 2026-09-15 08:17:17 CST
Objective: 实现仅从同资料同配置完整批次历史生成的只读耗时参考服务，不伪造费用；所有者负责API/UI整合。
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

- Read app/services/{batch_review_workflow,batch_review_view,batch_evidence_reprocessing,batch_evidence_reprocessing_view,evidence_reprocessing,prepared_review_workflow}.py, app/storage/models.py, app/workflow/jobstore.py, app/storage/review_context_repository.py and relevant contracts/repositories. Read reviews/codex_conference_r05-batch-estimates-design-20260915_review.md for owner limits, not the advisory as authority. Read .trellis/spec/backend/database-guidelines.md and error-handling.md.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. 只新增app/services/batch_processing_estimates.py；只读源码，禁止测试、应用、数据库、模型；返回review/OCR批量耗时参考与可比性和不可估算原因。

## Concrete Contract

- Implement `estimate_processing_batch(session, *, project_id, kind, members, routes=None, adapter=None) -> dict`. kind is review or ocr. members are ordered dictionaries with subject_id, review_episode_id, snapshot_id, complete_id (1..50, no repeated episode). Validate project/current episode/source identity using existing read validators, no prepare/write. Caller provides current routes for review or adapter for OCR; no private config discovery.
- Scan bounded recent same-project batch jobs (maximum 100, plus one to report history_truncated). Verify payload hashes and relevant existing material/owned-child/completed checkpoint validators. A historical sample is the ENTIRE completed batch created_at to its exact COMPLETED job event, includes member gaps. All owned children must be completed, with recorded completed checkpoints. Reject histories with cancellation/failure/recovery/user-wait events (parent or children), invalid or missing timestamps, ownership or hashes; never sample a currently retried child as original completed batch.
- Match exact ordered member source tuples to requested selection, exact current batch contract/routes/task_versions for review or profile_sha256 for OCR. Review contexts must also match current episode revision and authority; do not pool other subjects/stages/sizes. No summation of overlapping call durations or multiplication of per-page medians. This is conservative SAME-SOURCE historical reference, not a calibrated new-subject forecast; no compatible history must honestly return unavailable.
- Return {project_id,kind,member_count,method:'same-source-batch-history/v1',sample_count,median_seconds,lower_seconds,upper_seconds,source_batch_ids,excluded_count,history_truncated,cost:{amount:null,currency:null,reason:'no_verified_billing_basis'}}. n=0 all duration null; n=1 or2 only median, range null; n>=3 deterministic quartiles from standard library statistics.quantiles(method='inclusive') plus median. Reject nonfinite/negative durations. Limits and absence need explicit comments. Fees unknown not zero; do not claim local/free from task type. No rates table or token aggregation in this scope.
- Read only, no DB/table migration, no subprocess/model/app start, no test files or test runs, no network. Allowed checks py_compile and diff --check only. Use apply_patch; no other files touched. Owner handles API/UI and later full tests. Do not install dependencies or generate fixtures. Report exact assumptions and remaining runtime checks.

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
