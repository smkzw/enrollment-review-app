# Codex Execution Review: phase5-slice59l-20260827

## Verdict

`revise`

Worker 01 and the corrected Worker 02 are accepted for their bounded contract,
wire, hydration and publication-gate scope. Worker 03 is rejected as completion
evidence for a real Agent replay: it created a deterministic source-backed
control fixture and never invoked the product's MTPLX protocol-control Agent.

## Worker Outputs

- `worker_01`: accepted. Added explicit longer-of selection to the shared
  `TimeConstraint` contract; parent focused regression passed.
- `worker_02`: first result rejected because the six-month substitute window
  was attached to the exception condition. Same-session repair accepted after
  adding explicit exception-condition to alternative-obligation activation;
  parent focused regression passed 145 tests.
- `worker_03`: rejected as a real Agent replay. Its four-row deterministic
  fixture is retained only as a diagnostic contract/gate artifact. The emitted
  `structured_control_deconstruction_accepted=true` is not accepted by Codex.

## Manager Assessment

No execution manager was declared. Codex reviewed all worker outputs directly.
The decisive missing layer is a concrete OpenAI-compatible
`ProtocolControlAgentTransport` using the strict protocol-control wire schema;
the existing official IN/EX transport uses a different response schema and
cannot be silently reused.

## Boundary And Hermes Route Review

All edits stayed inside the declared worktree and worker write boundaries.
No production, source protocol, subject, OCR, browser or broad-package action
occurred. Hermes was not a declared execution transport for this packet. The
guard-recorded resource fallback from the requested Pi/MTPLX worker route to
Cursor CLI `auto` is retained in runner logs and metrics rather than relabeled.

## Codex Independent Verification

- Exact MTPLX model identity is currently exposed by
  `http://127.0.0.1:8002/v1/models` with 262144 context length.
- Parent focused protocol tests: 145 passed.
- `git diff --check`: passed.
- Source protocol SHA remains
  `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`.
- Deterministic replay correctly exercises four positive and four negative
  gate shapes, but is not evidence of Agent extraction quality.

## Cleanup Decision

Archive this execution packet after audit. Preserve the deterministic artifact
as a labeled diagnostic counterexample; do not promote it to accepted Agent
deconstruction evidence. Continue in a fresh governed slice that implements
the missing transport, runs the real MTPLX harness on the same frozen rows, and
performs parent source/clinical QC.
