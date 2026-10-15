# Serial Lifecycle Review: Dual MTPLX Adapter

Date: 2026-09-16  
Worker: `worker_01` / `enrollment-mtplx-serial-adapter-20260916`  
Mode: read-only audit (no app edits, no model start, no product inference, no new tests)

## 1. Evidence summary

### Source files read

| File | Role |
|---|---|
| `app/llm/page_review_harness.py` | Route resolve, preflight, `direct_completion`, `read_page` |
| `app/llm/page_review_admission.py` | Process-local shared local-provider slot |
| `app/llm/page_reader_capabilities.py` | `LOCAL_PAGE_PROVIDERS` vocabulary |
| `app/llm/page_review_transport_options.py` | MTPLX response_format / generation_mode only |
| `app/services/page_review_runtime.py` | One-shot prepare: preflight + shared admission injection |
| `app/services/page_review_execution.py` | Dual-lane gather + page-level semaphores |
| `app/services/page_review_job_service.py` | Step DAG + `execution_control` parallelism |
| `app/services/page_review_job_executor.py` | Per-step read via `run_cancellable` + injected completion |
| `app/services/page_review_cancellation.py` | Durable cancel poll + task cancel |
| `app/services/omlx_gate.py` | Existing cross-process lease pattern (OCR only; reference) |
| `.env.example` | Current product default: A=cloud GLM, B=`mtplx` |
| Tests: `tests/v2/llm/test_page_review_admission.py`, `test_page_review_local_route.py`, `tests/v2/services/test_page_review_cancellation.py` | Intended serial admission / cancel semantics |

### What exists today (facts)

1. **Resource ownership**
   - Routes: constructed by `require_page_reader_routes` in harness (`PageReaderRoute` frozen dataclass).
   - Preflight: `PageReviewRuntime._prepare` runs `asyncio.run(preflight_page_reader_routes(...))` once under `threading.Lock`, then caches `_routes` + executors.
   - Admission: single `PageReviewAdmission(routes)` instance injected as `completion=` into page-review, targeted, judgment-search, and prepared-review executors.
   - HTTP clients: **per call** in `direct_openai_completion` (new `httpx.AsyncClient` + `AsyncOpenAI`); no long-lived MTPLX client in the page-review path.
   - Model process / weights: **outside product ownership**. Product only talks OpenAI-compatible HTTP. No load/unload/swap API is called from page-review code.

2. **Local admission (request mutex only)**
   - `_admission_key`: providers `mlx-serve|mtplx-gui|mtplx|omlx` → one key `("local","shared")` with `BoundedSemaphore(1)`.
   - Non-local: per `(provider, model)` using `route.max_concurrency`.
   - Acquire is non-blocking poll + `asyncio.sleep(0.02)`; release always in `finally` (cancel-safe for waiters that never acquired).
   - Evidence: `app/llm/page_review_admission.py:9-33`; tests prove peak==1 across local platforms and release on cancel/fail.

3. **Local concurrency caps**
   - If provider ∈ `LOCAL_PAGE_PROVIDERS` (`omlx|mlx-serve|mtplx`), route `max_concurrency` forced to `1` (`page_review_harness.py:238,253`).
   - Note: `mtplx-gui` is in admission local set but **not** in `LOCAL_PAGE_PROVIDERS` (inconsistency / latent gap).

4. **Preflight**
   - Both lanes resolved in **parallel** (`asyncio.gather` over MAIN_A/MAIN_B).
   - `mlx-serve`: requires `loaded is True` and `state == "ready"`; explicit fail-closed: “不自动加载或替换模型”.
   - `mtplx`: only requires `supports_vision is True`; **no** loaded/state check; **no** load.
   - Dual-resident assumption is therefore stronger for mlx-serve than for mtplx, but neither path performs product-owned load/unload.

5. **Call graph**
   - Product job path (authoritative):
     `Runtime.enqueue` → `plan_page_review_payload` → steps `read:{i}:main-A`, `read:{i}:main-B` (no mutual depends) → `reconcile:{i}` → `coverage`.
     `execution_control.max_parallel_steps = sum(lane.max_concurrency)` → dual-local becomes **2**.
     `parallelizable_step_ids` includes **all** read steps for both lanes.
     Executor runs one step at a time *per started step*, but runner may start a parallel wave of multiple reads; each call goes `run_cancellable` → `read_page` → injected `PageReviewAdmission` → `direct_completion`.
   - Helper path `review_page`: `asyncio.gather` both lanes concurrently (`page_review_execution.py:70-76`).
   - Helper path `review_pages`: per-lane asyncio.Semaphore(max_concurrency) wrapping completion, still gathers pages/lanes concurrently.

6. **Cancel**
   - Step wrapper: `run_cancellable` polls durable job cancel; cancels asyncio task; preserves completed results if operation already returned.
   - Runner also cancels at lease/step boundaries.
   - Admission releases slot if acquire succeeded and completion raises/`CancelledError`.
   - **No** model unload, abort-of-load, or cross-process lease revocation for MTPLX weights.

7. **Current default config (`.env.example`)**
   - MAIN_A: cloud `zhipu-coding-plan` / GLM.
   - MAIN_B: `mtplx` at `http://127.0.0.1:8002/v1`.
   - “双MTPLX” is an objective beyond the current default (both lanes `mtplx`, likely different models/ports). Existing code can configure both lanes local via env, but lifecycle is incomplete for that topology.

## 2. Gaps vs explicit dual-MTPLX serial lifecycle

Desired lifecycle (product objective):  
`mutex → load A → infer A → release/unload A → load B → infer B → release/unload B`  
plus cancel mid-load/mid-infer and cross-job exclusion.

| Concern | Current state | Gap |
|---|---|---|
| Serial infer | In-process shared slot=1 for all local providers | Only serializes **HTTP completions**, not model residency |
| Load | None in page-review; mlx-serve forbids auto-load | Dual MTPLX cannot rely on both models being co-resident; no adapter to swap |
| Unload/release | None | Memory/GPU can remain occupied after cancel or lane switch |
| Preflight | Parallel identity probe; mtplx ignores loaded | Dual-MTPLX preflight must not require both models loaded at once |
| Cross-lane scheduling | Job DAG allows A+B reads parallel (`max_parallel_steps=2` when both local) | Steps may both “start”; only admission queues infer — still no swap orchestration |
| Cross-job mutex | Process-local `threading.BoundedSemaphore` | Second app process / OCR / protocol MTPLX users are not coordinated by page-review admission |
| Cancel mid-load | N/A (no load) | Future load must be cancellable and must release mutex |
| Cancel mid-infer | Task cancel + slot release | Does not guarantee server-side abort/unload |
| Clinical/data | Unchanged by admission | Must remain unchanged by any adapter |

**Inference (not proven by code):** Dual different MTPLX weights on one machine likely cannot be co-resident; product therefore needs explicit swap ownership. Exact MTPLX admin endpoints for load/unload are **not present in product page-review code** (unknown API surface; must be confirmed by Codex before implementation).

## 3. Minimal complete modification proposal (no code applied)

Constraint: do **not** change clinical prompts, clause packs, reconciliation, source data, or vote cardinality (still exactly two main readers).

### 3.1 New ownership module (recommended)

Add a dedicated adapter, e.g. `app/llm/mtplx_serial_lifecycle.py` (name flexible), owned by transport/lifecycle only:

- `acquire_lane(route) -> lease`: process-safe (prefer file/SQLite lease patterned after `app/services/omlx_gate.py`, scoped to page-review local VLM, not OCR).
- `ensure_model(route)`: load/activate configured `route.model` on `route.base_url` if not resident; unload conflicting resident model for the same hardware pool.
- `release_lane(lease, *, unload_policy)`: always drop mutex; unload on `always` / `on_switch` / TTL (policy explicit).
- Fail closed if admin API unavailable; never fall back to a different clinical model.

Do **not** put load/unload inside `build_page_review_messages` / `reconcile_*`.

### 3.2 Concrete integration points

1. **`app/llm/page_review_admission.py` — primary hook**
   - Today: request semaphore only.
   - Change: for dual-local / mtplx-shared hardware pool, wrap `completion` with lifecycle:
     - acquire mutex → ensure_model(route) → `await completion(...)` → finally release/unload.
   - Keep existing cancel-safe non-blocking acquire pattern for waiters.
   - Preserve cloud behavior unchanged (per-provider concurrency).
   - Optionally split keys: shared hardware pool vs independent endpoints if Codex later proves two MTPLX hosts are independent.

2. **`app/services/page_review_runtime.py::_prepare`**
   - Keep single shared admission object injection (already correct ownership boundary).
   - Preflight change when both mains are MTPLX/local-shared:
     - Probe endpoint + vision/capability only.
     - **Do not** require both models `loaded/ready` simultaneously.
     - Do not eagerly load both during prepare (would defeat serial swap and hold memory before jobs).

3. **`app/llm/page_review_harness.py::resolve_route_model` / `preflight_page_reader_routes`**
   - Keep identity fail-closed.
   - For `mtplx` under serial adapter mode: treat “not loaded” as acceptable at preflight; defer to lifecycle.
   - Keep mlx-serve’s current “不自动加载” unless Codex explicitly expands that provider into the same adapter.
   - Avoid parallel preflight side effects that load models.

4. **`app/services/page_review_job_service.py::plan_page_review_payload`**
   - When both MAIN_A and MAIN_B are in the shared local/MTPLX pool:
     - Set `execution_control.max_parallel_steps = 1` **or** remove cross-lane pairs from `parallelizable_step_ids` so A/B reads are not co-started.
   - Rationale: admission alone can serialize infer, but parallel step start amplifies cancel races, receipt concurrency, and encourages overlapping load attempts.
   - Do not change step IDs, reconcile dependencies, or clinical payload fields.
   - Legacy resume already tolerates adding `execution_control` (`page_review_job_service.py:185-187`).

5. **`app/services/page_review_execution.py`**
   - Product job path does **not** need gather for lanes (executor is per-lane step).
   - For helper `review_page` / `review_pages` (tests/tools): either document that callers must pass lifecycle-aware `completion`, or sequentially read local dual lanes when both routes share the pool. Smallest fix: rely on admission lifecycle wrapper; optional sequential gather for clarity.

6. **`app/services/page_review_job_executor.py` + `page_review_cancellation.py`**
   - Keep `run_cancellable` outside transactions as today.
   - Ensure lifecycle `finally` runs on task cancel (admission already does for slot; extend for unload).
   - On cancel during `ensure_model`, abort load wait and release mutex without marking clinical failure beyond existing `PAGE_REVIEW_CANCEL_REQUESTED`.
   - Do not discard completed lane checkpoints (already preserved).

7. **Cross-job / cross-feature mutex**
   - Minimum for page-review-only dual MTPLX: one durable lease for “local vision weights pool”.
   - If protocol-control / OCR also use same MTPLX host, Codex must decide whether to reuse/extend `omlx_gate`-style coordination or a new `mtplx_workload_gate`; current page-review admission is insufficient across processes.

### 3.3 Explicit non-goals (this adapter)

- No clinical prompt / schema / reconciliation / association changes.
- No third reader / handwriting-C restoration.
- No silent provider fallback or effort downgrade.
- No automatic model replacement during mlx-serve preflight unless intentionally brought under the same lifecycle contract.
- No new tests in this worker pass (implementation workers should add focused admission/lifecycle/cancel tests later).

## 4. Suggested implementation order for Codex

1. Confirm MTPLX admin API for list/load/unload/abort (external to this audit).
2. Implement lifecycle module + admission wrap (request + residency).
3. Adjust dual-local `execution_control` to `max_parallel_steps=1`.
4. Softening dual-MTPLX preflight so prepare does not demand co-residency.
5. Cancel paths: unload/lease release proofs.
6. Focused tests only after Codex authorizes implementation (admission peak, swap order A→B, cancel mid-wait/mid-infer, cross-thread mutex).

## 5. File → change map (minimal)

| File | Change type | Purpose |
|---|---|---|
| `app/llm/mtplx_serial_lifecycle.py` (**new**) | add | load/unload/lease ownership |
| `app/llm/page_review_admission.py` | modify | call lifecycle around local completion |
| `app/llm/page_review_harness.py` | modify (small) | dual-MTPLX preflight: identity/vision without dual-loaded requirement |
| `app/services/page_review_runtime.py` | modify (small) | keep shared admission; avoid eager dual load in `_prepare` |
| `app/services/page_review_job_service.py` | modify (small) | dual-local `max_parallel_steps=1` |
| `app/services/page_review_execution.py` | optional | sequential local dual helper path |
| `app/services/page_review_cancellation.py` | likely unchanged | already cancels task; lifecycle must honor `CancelledError` |
| `app/services/page_review_job_executor.py` | likely unchanged | already injects admission + `run_cancellable` |
| Clinical/domain/storage modules | **none** | boundary |

## 6. Uncertainty / Codex decisions needed

1. **MTPLX control plane**: which HTTP/admin calls load, unload, report resident model, and cancel load? Not evidenced in page-review product code.
2. **Topology**: dual MTPLX = two models on one server, or two base_urls? Mutex scope depends on answer.
3. **Unload policy**: always unload after each page vs unload only on lane/model switch vs warm TTL.
4. **Cross-feature sharing**: must page-review mutex also block protocol-control MTPLX on `:8002`?
5. **Provider scope**: apply serial lifecycle only to `mtplx`, or also `mlx-serve`/`omlx`/`mtplx-gui`?

## 7. Verification needs (for later implementation; not run here)

- Unit: admission still peak=1; lifecycle order loadA→inferA→unloadA→loadB…
- Cancel: waiter never loads; mid-infer releases lease; completed lane retained.
- Job: dual-local payload `max_parallel_steps==1`; resume identity still matches.
- No clinical golden diff in prompts/records.
- Live smoke only under Codex authority (this worker did not start models).
