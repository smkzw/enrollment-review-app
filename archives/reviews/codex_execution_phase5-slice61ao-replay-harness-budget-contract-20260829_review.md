# Codex Execution Review: phase5-slice61ao-replay-harness-budget-contract-20260829

## Verdict

Accept after Codex revisions. The model-free DOCX replay harness and repair-budget observability contract are accepted as engineering infrastructure. PDF structural ingestion and any live clinical replay remain incomplete.

## Worker Outputs

- `worker_01`: audited the temporary p803-p805 chain, identified the hidden human-matrix inheritance and reconstructed the product source-of-truth set.
- `worker_02`: added the model-free replay-pack builder, CLI, deterministic verifier, and focused tests.
- `worker_03`: made the global repair budget explicit and added per-attempt error-class accounting and regressions.
- The CodeBuddy primary returned an explicit 429. Codex preserved it, verified the declared MTPLX fallback constraints, and used only that declared fallback for the three work items.

## Manager Assessment

No execution manager was declared for this finite-code route. Codex directly reviewed all three outputs and revised the harness where worker assertions exceeded the actual contract.

## Boundary

No clinical LLM/VLM replay, control publication, raw-protocol mutation, subject processing, OCR, or frontend work occurred. The real D001 DOCX was read only through the existing authorized regression source. PDF structural ingestion remains out of scope because the product chain does not yet provide it.

## Codex Independent Verification

- Added mandatory source SHA-256 and pinned timestamp to make a named replay reproducible.
- Removed local filesystem paths from persisted replay inputs.
- Changed the external pack fingerprint to hash actual on-disk files, including the summary, instead of trusting self-reported hashes; verification can now compare a checkpoint fingerprint.
- Kept the default repair budget at two global rounds rather than increasing it silently. Higher live budgets must be explicit and recorded.
- Fixed the MTPLX transport test's ambient-key isolation without changing runtime key precedence.
- Focused replay/authority/budget regressions: `66 passed`.
- Full protocol suite: `1026 passed, 58 warnings in 128.39s`.
- Real D001 model-free double build from the raw DOCX: 3 owned refs, 7 attached refs, 3581 blocks, 1848 units, identical batch/manifest/snapshot/prompt and identical external pack fingerprint `993594302ea9dd7c1037c28afc60e1fc228133e47d6e71a2e9766a961a7d1a5c`.
- Python compilation, JSON validation, and `git diff --check` passed. No clinical model was called.
- Hermes execution audit passed with all three worker reports present and route identities preserved; the primary 429 and declared-fallback use remain explicitly recorded.
- PDF remains explicitly rejected because the current product has no PDF-to-structure ingestion chain. This is an honest product gap, not accepted completion of the raw-PDF requirement.

## Cleanup Decision

Run execution audit first, then archive runner prompts/logs/reports with `cleanup-execution`; preserve immutable v8 evidence, the new checkpoint, and source changes.
