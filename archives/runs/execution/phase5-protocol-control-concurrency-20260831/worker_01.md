I'll do a read-only review of JobRunner, JobStore, and the protocol-control executor/transport lifecycle. Starting with the assigned context and plan.Context is thin on source paths, so I'm locating JobRunner, JobStore, and the protocol-control executor/transport next.Located JobRunner/JobStore and protocol-control sources; reading those next for lease, cancel, and parallelism semantics.# Execution Output: phase5-protocol-control-concurrency-20260831 - worker_01

## Boundary And Context Check

- Role: `worker_01` / read-only concurrency review; **no code modified**.
- Initial reads: `context/phase5-protocol-control-concurrency-20260831_execution_context.md`, `plans/codex_execution_phase5-protocol-control-concurrency-20260831.md`.
- Context “Source Of Truth” was still `TODO`; independently located authorized in-tree sources under the worktree (no production writes).
- Explicit non-goals observed: do not resume/modify paused D001 jobs; do not write project-specific rules; parallel only for mutually independent discovery batches.

## Work Performed

Read-only review of JobRunner / JobStore / recovery / protocol-control executor & transports, focused on a **minimal in-job parallel boundary** and risks to lease, idempotency, partial success, cancel, lease-loss, and thread safety.

### Evidence — current serial contract

1. **Job-scoped lease, one step at a time**  
   `JobRunner._run_claimed` renews lease → cancel boundary → `next_runnable_step` (singular) → `start_step` → executor **outside** the write txn → commit success/failure (`app/workflow/runner.py`).  
   Persistent truth is DB state; in-process threads are not authority (module docstring + `.trellis/spec/backend/persistent-jobs.md`).

2. **Discovery batches are already independent in the DAG**  
   `ProtocolControlJobService.create_from_deconstruction` creates `discovery_NNNN` steps with **no** `depends_on` between them; only `deterministic_closure` depends on all discovery step ids (`app/services/protocol_control_execution.py` ~366–384).  
   Payload note already states: *“Current durable runner remains serial within one job.”* and warns not to resume paused fixed-unit serial discovery under a mixed adaptive config (~749–752).

3. **Deep phase is also sibling-independent after closure**  
   Closure `PreparedStepResult.apply` adds `deep_NNNN` with `depends_on=(STEP_CLOSURE,)`; hydrate waits on all deep; gate waits on hydrate (~1270–1311). Deep is a *secondary* parallel candidate; assignment scope is discovery-first.

4. **Cancel / lease / recovery semantics (serial-safe today)**  
   - Cancel is durable; running → `cancel_requested`; applied at step boundary via `cancel_at_boundary` / expired cancel recovery (`jobstore.request_cancel`, `cancel_at_boundary`, `cancel_expired_cancel_requests`).  
   - Heartbeat thread renews lease during one executor call; loss → `LeaseLostError`, discard output (`runner._lease_heartbeat`).  
   - Recovery: expired `running` → `recovering` (generation++); interrupted `running` step with checkpoint → completed; else requeue or attempt-exhaust fatal (`recovery.py`, `requeue_recovering` / `_reset_interrupted_steps`).  
   - Discovery/deep model steps are `retryable=False`; model uncertainty is terminal until **manual** job retry (create + executor comments).

5. **Transport lifecycle**  
   Discovery/deep use separate adapters; discovery forces discovery-only JSON schema (`protocol_control_discovery_transport.py`).  
   Shared base transport keeps mutable `_histories` by `session_id` and caches `_model_identity_verified` with **no lock** (`protocol_control_agent_transport.py` ~341–746). Each `start()` allocates a new session id; repair uses `continue_session` on that id. `_resolve_transport` may reuse a **singleton** `config.discovery_transport` across steps.

### Inference — minimal parallel boundary

| Layer | Parallelize? | Rationale |
|---|---|---|
| `discovery_*` siblings (deps empty / all satisfied) | **Yes — only target** | Independent frozen batches; natural wave before closure |
| `deterministic_closure` | **No** | Aggregates all discovery checkpoints; mutates step graph via `PreparedStepResult.apply` |
| `deep_*` siblings | Out of minimal scope (same pattern later) | Independent after closure; same lease/fail hazards |
| `hydrate` / `gate` | **No** | Aggregation + publication gate; must stay serial |
| Cross-job workers | Already possible via `claim_next` | Unrelated; must not double-claim one job |

**Recommended minimal shape (for worker_02, not implemented here):**

1. Freeze opt-in at job create only, e.g. payload `parallelism: {discovery_max_inflight: N}` (default `1` = today’s serial). Never rewrite paused/adaptive-mismatched jobs.  
2. Extend runner readiness to `next_runnable_steps` / wave: select up to N ready steps that are explicitly marked parallel-safe (prefix `discovery_` **and** empty depends_on **and** frozen flag).  
3. **One job lease + one wave heartbeat**; start all wave steps in short txns; run executors concurrently **outside** write lock; **serialize** `complete_step` / `fail_step` commits (SQLite + `last_event_seq`).  
4. Keep closure/hydrate/gate on the existing singular path.  
5. Per parallel discovery call: prefer `discovery_transport_factory()` / fresh transport (or lock around `_histories` + identity), never unsynchronized shared mutable transport.

### Risks (partial success / failure / cancel / lease / threads)

| Risk | Severity | Evidence / effect |
|---|---|---|
| **Orphan `running` steps on fatal mid-wave** | **Critical if naive parallel** | `fail_step` fatal path cascades dependents + `_finalize_job_failure` (clears lease) but **does not** `_cancel_steps` non-dependent siblings. Serial: only one running step. Parallel: siblings stay `running` on `failed_final`; `mark_expired_running` only selects `state=="running"` **jobs**, so orphans are not recovered. |
| Lease cleared while siblings in-flight | High | Sibling commits hit `LeaseLostError` (discard OK) but leave step state `running` (above). |
| Shared transport `_histories` / identity cache | High | Concurrent `start`/`continue_session` without locking → dict races; identity probe not thread-safe. |
| Multiple heartbeats per wave | Medium | N× `_lease_heartbeat` on same lease is racy/wasteful; use one wave heartbeat. |
| Cancel mid-wave | Medium | Today cancel is next-boundary. Wave should: allow in-flight finish; commit success only if lease+not-cancelled fence holds; then `cancel_at_boundary` for remainder. Completed discovery checkpoints stay (matches durable cancel). Failure+`cancel_requested` already `_cancel_steps` — safer than bare fatal. |
| Partial success meaning | Medium | Sibling discoveries can complete while one is `failed_final`; closure depends on all → cascade-fails. Job-level “partial success” = some discovery checkpoints committed + job not completed catalog. Parallel must not invent formal catalog success. |
| Retryable failure (future deep/other) | Medium | `fail_step` → `failed_retryable` clears lease immediately; incompatible with live sibling runners unless wave-drain-first or multi-running cleanup. Discovery is non-retryable today. |
| Event seq / SQLite writers | Low if serialized commits | `append_event` uses atomic `last_event_seq+1`; concurrent sessions need commit serialization. |
| Result order | Low for correctness | Checkpoints keyed by `step_id`/`discovery_batch_id`; closure reads by plan order, not completion order. Events may interleave — acceptable if seq monotonic. |
| Idempotent replay | Low | `_replay_checkpoint` if `last_checkpoint` present; recovery-with-checkpoint marks completed without re-calling model. Parallel must not start a step that already has an accepted checkpoint. |
| Fake concurrency | Process | Cap `discovery_max_inflight`; prove overlapping transport calls in tests (worker_03). Config default 1 preserves serial compatibility. |
| D001 / adaptive resume | Process | Do not migrate paused serial jobs onto parallel/adaptive; honor payload freeze notes. |

### Recommendation summary for Codex / worker_02

1. Parallel **only** frozen, independent `discovery_*` waves inside one claimed job.  
2. Before enabling N>1: fix JobStore so any path that clears the lease while other steps are `running` either **waits for wave drain** or **atomically terminalizes those running steps** (cancel or recovery-reset) in the same txn as failure/finalize.  
3. Single heartbeat; serialized store commits; fresh/locked transport per concurrent discovery.  
4. Default serial; opt-in frozen flag; no D001 resume; no project-specific rules.

## Artifacts And Evidence

- No new files written (read-only assignment; runner persists this report).  
- Primary sources reviewed:
  - `app/workflow/runner.py`, `jobstore.py`, `recovery.py`, `states.py`
  - `app/services/protocol_control_execution.py` (job create, executor, discovery/closure/deep)
  - `app/agents/protocol_control_discovery_transport.py`, `protocol_control_agent_transport.py`
  - `.trellis/spec/backend/persistent-jobs.md`
- Supporting: `app/services/protocol_control_executor.py` (re-export), `protocol_control_job_service.py` (re-export).

## Commands And Observations

| Tool | Target | Observation |
|---|---|---|
| Read | execution context/plan | Work item 1 = read-only review; SoT paths TODO |
| Glob / Shell `rg` | app tree | Located `app/workflow/{runner,jobstore,recovery}.py`, protocol_control execution/transports |
| Read / eval | JobStore/Runner APIs | Singular `next_runnable_step`; job-level lease; heartbeat; cancel/fail/recovery paths |
| Read | `protocol_control_execution.py` | Discovery siblings independent; closure barrier; payload admits serial-only runner |
| Shell `rg` | transport | Unlocked `_histories` + `_model_identity_verified` |

No tests executed (not authorized for this work item).

## Blockers Or Missing Environment

- Context SoT list was empty; review used in-tree paths above — Codex should confirm these as authoritative if another package tree was intended.  
- No blocker to completing this **read-only** item. Implementation/tests belong to `worker_02` / `worker_03`.

## Rerun Requests Or Next Step

- **Codex:** accept this boundary/risk analysis (especially orphan-`running`-on-fatal) before `worker_02` implements.  
- **Precise decision needed:** on first fatal discovery in a wave, prefer (A) drain in-flight and discard their results after lease clear, with explicit sibling terminalization in `fail_step`, or (B) keep lease until wave drains, commit earlier successes, then fail job without orphaning `running` steps?  
- **worker_02:** implement opt-in discovery wave + JobStore safety + transport isolation + unit tests; do not touch paused D001 data.  
- **worker_03:** concurrency acceptance covering peak inflight, event order, partial success, fatal/retryable, cancel, lease loss, recovery, serial `max_inflight=1` compatibility, anti-fake-concurrency / anti-overfit.
