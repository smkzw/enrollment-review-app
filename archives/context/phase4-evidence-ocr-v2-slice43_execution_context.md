# Execution Context: phase4-evidence-ocr-v2-slice43

Created: 2026-08-19 16:49:59
Objective: 完成 Phase 4 Slice 4.3：建立不可变页产物与 OCR 持久化、逐格式分页和识别缓存、页级租约与全局8路准入、晚到结果拒绝、限定重试取消恢复及只读进度
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `pi` / `cms-smk` / `deepseek-v4-flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `AGENTS.md` and the active Trellis task `.trellis/tasks/08-19-phase4-evidence-ocr-v2/{prd.md,design.md,implement.md}`.
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`, `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`, and `docs/PROJECT_CONTEXT.md`.
- `.trellis/spec/backend/{database-guidelines.md,persistent-jobs.md,error-handling.md,quality-guidelines.md}` plus `.trellis/spec/guides/{cross-layer-thinking-guide.md,code-reuse-thinking-guide.md}`.
- Frozen Phase 4 contracts in `app/domain/contracts/ocr.py`, `app/evidence/`, accepted migrations `0008`/`0008a`, accepted upload service/API, and the existing durable Job/Step/Checkpoint/Event implementation.
- Slice 4.0 only proved text-only GLM OCR on two synthetic pages. It did not prove the provider-reported model identity or machine coordinates. No coordinate means no red rectangle.

## Scope And Success Criteria

- Add migration `0009_ocr_artifacts`; never rewrite accepted `0008` or `0008a`.
- Persist immutable processing revisions, page manifests, page artifacts, OCR profiles/runs/attempts/pages, raw request/response references, page cache identity, and page-work leases with normalized columns cross-checked against canonical payloads.
- Page identity and cache identity must include source content hash, one-based page number or frame identity, rendering/decoding version, page input hash, and OCR profile fingerprint. File name and mtime are never identities.
- PDF, image, multi-frame TIFF, TXT, DOCX and legacy DOC must produce truthful ordered page manifests. Unsupported conversion or a failed page remains an explicit failed page; successful sibling pages cannot make the file look complete.
- Native PDF text/coordinates may be used only when genuinely extracted and mapped to the frozen coordinate frame. Scanned pages and images use the frozen text-only route; no synthetic bbox.
- Raw request, raw response, page image and native text/coordinate artifacts are immutable content-addressed files. User-facing APIs must never expose absolute local paths or raw provider errors.
- Reuse existing Job infrastructure for task truth. Add a separate persisted page-work lease only to prevent duplicate execution. The shared `/Users/smkzw/.codex/tools/omlx_workload_gate.py` OCR lease is the only global real-inference quota and must peak at no more than 8 across workers/processes.
- Fixed acquisition order: page-work lease, then shared oMLX lease for each real external inference, then inference. Both leases heartbeat and release in `finally` paths. Local rendering does not consume oMLX quota and has independent memory/concurrency backpressure.
- Result submission validates page-work owner, generation, expiry policy, input hash, profile fingerprint, and processing-revision state. A stale/late attempt may remain auditable but cannot become a successful cache entry or processing-manifest member.
- Retry only failed/affected files or pages. Cancellation takes effect at safe boundaries and preserves completed immutable artifacts. Startup recovery leaves no permanent processing state. SSE reads persistent events only and never owns/cancels work.
- Slice 4.3 produces only non-activatable basic processing revisions. Do not add or change an active evidence pointer, ActivationEvent, corrections, referenced-document resolution, risk gates, clinical facts, Patient Profile, eligibility assessment, or red-box UI.
- Use only synthetic/de-identified fixtures and isolated V2 test data. Do not read any raw clinical material outside this workspace, install dependencies silently, or write production data.
- Acceptance requires focused tests, migration upgrade/verification/downgrade safeguards, stale-generation and cache poisoning counterexamples, crash/restart/cancel/retry fault injection, a real gate contention test proving inference peak <=8, full `tests/v2`, Ruff, Pyright, and `git diff --check`.

## Execution Order And Ownership

- Execute sequentially: worker 01 -> Codex review -> worker 02 -> Codex review -> worker 03 -> Codex final acceptance. Later workers must read the accepted prior worker report and actual diff.
- Worker 01 owns OCR persistence contracts/ORM/migration/repositories and their storage/domain tests.
- Worker 02 owns deterministic format paging/rendering, artifact storage, native-PDF extraction, text-only OCR adapter/cache and focused evidence tests. It may extend worker 01 persistence only when required by the accepted schema and must report the reason.
- Worker 03 owns processing-job executors, page-work lease orchestration, shared oMLX gate integration, rendering backpressure, recovery/retry/cancel/progress and fault/concurrency tests. It must not replace the shared gate with an in-process semaphore.
- Workers return compact reports; Codex owns acceptance and may request a same-session repair. No worker closes Slice 4.3 itself.

- TODO: Codex must add authoritative source files, screenshots, datasets, or URLs before dispatch.
- Do not add production paths without explicit Codex authorization.

## Accepted Handoff Before Worker 03

- Worker 01 final accepted reports: `runs/execution/phase4-evidence-ocr-v2-slice43/worker_01_followup_02.md`; Worker 02 final accepted report: `runs/execution/phase4-evidence-ocr-v2-slice43/worker_02_followup_02.md`. The original reports are superseded where they conflict.
- Codex aligned the final page-artifact identity after both handoffs: successful page identity and database uniqueness include source document, page, page input, renderer version, decoder version and coordinate-transform version; distinct failed reasons use deterministic IDs and may coexist.
- `PageArtifact.page_input_sha256` is the stable render/decode input identity. `OCRPage.page_input_sha256` is the exact immutable stored page-image hash. The processing-revision closure enforces this.
- Use the staged OCR seam: commit `prepare` request/attempt state, call the shared oMLX gate outside the database transaction, then run `commit_guard` plus OCRPage/result attempt writes in one transaction. Late rejected audit attempts use a separate transaction.
- `PageArtifactOutcome.technical_detail` and `OcrRecognition.technical_detail` are internal diagnostics only. Persistent/SSE/API user text uses stable Chinese reasons and must never expose those details.
- `process_source` is a convenience integration path, not the durable executor. The worker 03 executor must preserve the single-route decision and exact stored-page-image input while decomposing per-page checkpoints.
- Codex verification before worker 03: focused `141 passed`; full V2 `1187 passed, 58 warnings, 2 subtests passed`; Ruff, Pyright and diff check clean.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 实现0009_ocr_artifacts迁移、ORM与仓储：EvidenceProcessingRevision基础修订、页清单、OCRProfile、PageArtifact、OCRRun/Attempt/Page、原始请求响应工件、缓存唯一键、页工作租约及完整迁移反例测试
2. 实现逐格式分页与页产物生成、原生PDF文本坐标、扫描页路由、不可变页图/原始工件保存、OCRProfile指纹和页级缓存适配；只采用已冻结text-only路线，无真实坐标不画框
3. 将证据处理Job接入页级持久工作项、共享oMLX OCR门禁、租约代次与晚到拒绝、渲染背压、文件页检查点、限定重试取消恢复和SSE只读进度，并完成故障注入与多进程峰值测试

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.

## Final Acceptance — 2026-08-19

- Slice 4.3 accepted after worker 01–03 execution, same-session repairs, and a fresh `trellis-check` pass.
- Codex verification: focused `172 passed`; V2 `1233 passed, 58 warnings, 2 subtests passed`; focused Ruff, production Pyright, script syntax, and diff checks passed.
- Live synthetic probes: 2/2 sequential pages exact; 12/12 concurrent requests exact; shared gate peak 8 and residual leases 0; response model `GLM-OCR-bf16`; no machine coordinates.
- Correctness repairs include cancel/finalization races, job-to-snapshot cancellation projection, model drift and response validation, raw rejected-response preservation, and removal of premature risk scanning from 4.3.
- Accepted boundary: basic processing revisions remain non-activatable; no locator, correction, risk gate, ActivationEvent, red box, clinical fact, Patient Profile, or eligibility judgment was introduced.
- Next safe action: plan and implement Slice 4.4 `0010_evidence_locator_corrections`; do not start external visual medical-monitor trials until Slice 4.6.
