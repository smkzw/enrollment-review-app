# Codex Execution Review: phase5-selective-vision-postfreeze-orchestration-20260831

## Verdict

ACCEPTED AFTER PARENT HARDENING.

The accepted boundary is a separate persistent post-freeze job. Evidence/OCR
processing only performs a short idempotent enqueue and never waits for VLM.

## Worker Outputs

- `worker_01` independently confirmed the pre-existing defect: the observation
  service awaited remote VLM while `session.begin()` remained open. It proposed
  the accepted short-read / transaction-free-call / short-write split and a
  separate JobRunner task.
- `worker_02` implemented the service split, idempotent job service, dedicated
  executor, post-freeze enqueue and application registration. Its persisted
  report was an incomplete status summary and was not treated as acceptance.
- `worker_03` created the independent orchestration test file covering no-TX
  remote calls, non-blocking enqueue, idempotency, closed outcomes, native-text
  skip, OCR immutability and process/lease recovery. Its persisted report was
  also an incomplete status summary; Codex reran and expanded the tests.
- Codex added two missing deterministic guards found during source review:
  reject frozen planning-version drift before any material/model access, and
  reject enqueue for a nonexistent processing revision without creating a Job.

## Manager Assessment

The live packet declared no execution manager. Codex reviewed actual files,
worker logs and runtime tests directly. All workers completed on
`pi/cursor/default`, return code 0, without fallback.

The first parent shell controller failed before substantive execution because
zsh reserves the variable name `status`; the shell SIGHUPed all three freshly
started runner processes. Codex verified no process remained and launched the
same three generated commands once more with the same prompts and route. This
was a controller failure, not a model fallback or hidden redispatch.

The generated context still contained an unfilled Source Of Truth marker at dispatch.
Worker 01 surfaced this correctly. Codex populated the exact live source list
during acceptance and retained an explicit note that it was a post-dispatch
procedural correction; it is not represented as pre-dispatch context.

No Hermes worker, manager, transport or fallback was declared for this packet;
none was dispatched or substituted. The audited execution route was Pi/Cursor.

## Codex Independent Verification

- Targeted compile: observation service, postprocess job service/executor,
  evidence executor and application registration passed.
- Focused observation/planning/orchestration suite after parent hardening:
  `45 passed`.
- Evidence executor, Job API, background registration and cold-import suite:
  `117 passed`.
- Full v2 storage/evidence/services/API regression: `1337 passed, 1 skipped`
  in 489.46 seconds. The skip is the absent real oMLX probe artifact.
- Targeted `git diff --check`: passed.
- Deterministic evidence confirms: enqueue does not call/await VLM; remote VLM
  runs without a database transaction; success is identity-idempotent; closed
  failures contain no pseudo observation; expired lease/process death recovery
  does not duplicate success; OCR text/hash remain unchanged.
- The implementation contains no D001/SAR, disease, drug, score, visit or
  protocol-specific clinical rule. D001 checkpoint state was not read or run.

## Cleanup Decision

Run review-gate and `audit-execution`, then archive prompts, worker reports,
runner logs and route manifest. Preserve all acceptance evidence, including the
incomplete worker summaries and parent-controller failure note.
