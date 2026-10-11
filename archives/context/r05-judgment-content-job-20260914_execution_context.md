# Execution Context: r05-judgment-content-job-20260914

Created: 2026-09-14 17:28:15 CST
Objective: Implement the receipt-bound recoverable written-judgment content job using existing product JobRunner and direct dual-model reader; no model calls or clinical adoption.
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

- Read app/services/judgment_content_input.py, judgment_fact_linkage.py, judgment_content_comparison.py; app/llm/judgment_content.py; app/domain/contracts/judgment_content.py. These are source-only new modules, not accepted runtime.
- Reuse app/services/binding_qualification.py and binding_qualification_support.py patterns, app/services/job_service.py, app/workflow runner/jobstore, page_review_cancellation.py and predicate_binding_job.py. Read complete affected helpers. No app imports that start services.
- Clinical design: only content fidelity of existing facts, never create/change facts or judge eligibility. Search linkage is not clinical proof. Goal requires full product eventually; this bounded step is the official-predicate job producer/receipt path, not permission to narrow the entire product.

## Exact Write Scope And Deliverable

- Allowed new files only: app/services/judgment_content_job.py and app/services/judgment_content_receipts.py. You may fix app/services/judgment_content_input.py, app/services/judgment_content_comparison.py and app/llm/judgment_content.py only for concrete integration defects. No other source edits. Do not write tests, docs, process files, database, source clinical records, caches or credentials. Return report for runner.
- Provide enqueue_judgment_content(session_factory, candidate_job_id, context_id, routes, artifact_store, ...); JobRunner-compatible JudgmentContentJobExecutor; verify_completed_judgment_content(...) returning receipt-proven summary. Inspect analogous qualification receipt reconstruction rather than trust checkpoint booleans or summary hash alone.
- Producer loads/rebuilds input from verified completed candidate receipt and prepared context. Preserve all excerpt_coverage including empty/ambiguous rows; no pairing by fact type or disease. Candidate family control is not yet supported by linkage: explicitly reject it, do not create empty-success job for it.
- Deterministic bounded batches preserve whole source excerpts and use actual judgment prompt size; shared existing planner may need local size validation. Same-input main-A/main-B direct read only, 65536..131072 budget, no fallback/third lane, do not include peer output in prompts. Keep declared route identity. Use existing JobService, cancellation and shared admission/transport; do not create new queue or duplicate transport implementation.
- At start and apply, rebuild exact payload input hash against current context and candidate receipts. Persist raw request/response/failure receipts for attempts; include input/batch/messages/routes. Cancellation/invalid response must retain failure evidence. No final clinical acceptance flags may be true.
- Summary reconstructs completed lane outputs from actual receipt material and checks exact requests/messages/budgets/response, not asserted values. Do not mix attempts/lanes or unknown jobs. Store structural comparison plus excerpt coverage. Empty selected pairs skips models but retains unresolved coverage; no claim missing judgment merely because no pair selected.
- Do NOT register executors/API or activate consumers, run models, tests, app startup, DB, browser or pip. Only source reading, manual edits with apply_patch, py_compile and diff checks. No recursive delegation, conference, internet or personal harness calls. This engineering worker invocation is not a product VLM call.
- Keep modules focused; prefer reuse over copying giant qualification implementation. Record whether duplicate source qualification + content stage could later combine prompts without losing separate dimensions; do not change existing qualification v2 now or expand model calls.
- Completion evidence is code/read-through plus compilation only; report runtime/clinical verification as not executed. Owner will review and integrate; no product acceptance claims.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. Implement producer, executor and receipt verifier for judgment content checks from the same prepared review, preserving all excerpt coverage and existing product transport. No tests or registration.

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
