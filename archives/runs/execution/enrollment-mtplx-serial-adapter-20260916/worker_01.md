只做本轮分配的只读串行适配审查；先读执行上下文与计划，再定位相关源文件。接下来定位并只读审查三类 page-review 源文件及相关本地资源准入逻辑。已定位核心文件；接下来通读 harness、execution、runtime 与 admission，并检索加载/释放/取消相关符号。子代理失败了；我改用本地检索与分段通读继续审计。正在写入只读审查产物 `serial-review.md`。# Execution Output: enrollment-mtplx-serial-adapter-20260916 - worker_01

## Boundary And Context Check
- Read `context/enrollment-mtplx-serial-adapter-20260916_execution_context.md` and `plans/codex_execution_enrollment-mtplx-serial-adapter-20260916.md`.
- Scope honored: read-only audit only; no app edits, no model start, no product inference, no new tests.
- Authorized artifact written: `runs/execution/enrollment-mtplx-serial-adapter-20260916/serial-review.md`.
- Did not write runner-managed `worker_01.md`.

## Work Performed
Audited page-review local/MTPLX ownership and concurrency:

- Routes/preflight/completion: `app/llm/page_review_harness.py`
- Process-local shared slot: `app/llm/page_review_admission.py`
- Runtime injection: `app/services/page_review_runtime.py`
- Dual-lane gather helpers: `app/services/page_review_execution.py`
- Job DAG / `execution_control`: `app/services/page_review_job_service.py`
- Step execution + cancel wrapper: `page_review_job_executor.py`, `page_review_cancellation.py`
- Related: `page_reader_capabilities.py`, `page_review_transport_options.py`, `omlx_gate.py` (cross-process lease reference), `.env.example`, admission/cancel/local-route tests

**Key findings**
1. Admission only serializes local **HTTP completions** (`("local","shared")` semaphore=1); it does **not** own load/unload/swap.
2. Product job path can co-start A/B reads when both local (`max_parallel_steps = 1+1 = 2`).
3. `mtplx` preflight checks vision only; `mlx-serve` requires already loaded and forbids auto-load.
4. Cancel releases admission slots; no model unload.
5. Minimal fix: new lifecycle adapter + wrap admission; dual-local `max_parallel_steps=1`; soft dual-MTPLX preflight; no clinical/data changes.

## Artifacts And Evidence
- Deliverable: `runs/execution/enrollment-mtplx-serial-adapter-20260916/serial-review.md`
- Contains: call graph, ownership, gaps, file→change map, Codex decision points, later verification needs.

## Commands And Observations
- `rg` over harness/admission/runtime/execution/job/cancel for `mtplx|admission|preflight|cancel|max_parallel`.
- `rg` for load/unload APIs in app/tests/docs/context: **no product page-review load/unload implementation found**.
- File reads as listed above.
- `pi-worker` subagent failed to start (`Worker exited 1`); continued with direct reads/`rg`.

## Blockers Or Missing Environment
- Blocker for implementation (not for this audit): MTPLX admin API for load/unload/resident/abort is not evidenced in product page-review code; Codex must supply/confirm before coding.
- Topology undecided: one shared host vs independent base_urls; unload policy; whether mutex must also cover protocol-control MTPLX on `:8002`.

## Rerun Requests Or Next Step
Codex next:
1. Accept/revise `serial-review.md`.
2. Confirm MTPLX control-plane API + mutex topology.
3. Dispatch implementation worker for: `mtplx_serial_lifecycle` + admission wrap + dual-local `max_parallel_steps=1` + preflight softening; keep clinical surfaces untouched.
