# Execution Context: enrollment-protocol-benchmark-entry-20260908

Created: 2026-09-08 10:09:32 CST
Objective: 实现原始DOCX经现有产品服务的隔离方案解构横评入口，不改产品提示或生产代码；原生传输可替换配置且保留真实请求回执，无模型调用的测试验证。
Task type: `E03`
Risk: `medium`
Execution module trigger: Codex assigned 1 bounded work item(s). Each item must identify its inputs, allowed paths, deliverable and acceptance check.
Route schedule: `off_peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `zcode/glm-5.3-flash:max -> opencode-go/muse-spark-1.3-contributor:xhigh -> mtplx/qwen3.8-flash-next-mtplx-optimized-speed:medium -> openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `zcode` / `zcode` / `GLM-5.3-Flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- Read app/services/protocol_workbench.py (locate exact filename if needed), app/agents/protocol_semantic_transport.py, protocol deconstruction executor and JobRunner definitions and their focused tests. Existing scripts/run_protocol_control_smoke.py is SYNTHETIC ONLY; preserve that guard and do not use it as a real protocol test.
- Read scripts/run_frozen_product_reader.py and current DataPaths/database initialization patterns for isolation and receipts. Read the current architecture and implementation plan only for relevant protocol boundaries.
- Do not read credentials, personal harness configuration, or raw clinical artifacts. Offline tests use synthetic fixtures only. Do not browse or call any model, OCR service or external harness yourself. The owner will run real tests after verification.
- The intended live preparation takes an original DOCX/PDF through actual upload, structure and source-freeze services, with explicit phase selection. Never fabricate an accepted snapshot or pre-extract chosen clinical rules. Preparation and execution are separate commands; execution must verify hashes, use the actual product prompt/executor, and record actual route and usage without secrets. No draft_response_builder/page_texts_builder for the real execution path.
- Configurable native product transport only: unsupported providers must fail explicitly, not masquerade as another provider. Require output budget >=65536 before sending, preserve provider defaults for sampling. Data and database must be under a newly created explicit output directory, never default product database; refuse existing run directories and source/output overlap. Capture raw response/request evidence using existing product transport hooks where available; do not modify app to add hooks. Report any limitations.
- Write only scripts/run_frozen_protocol_comparison.py and tests/test_frozen_protocol_comparison.py using apply_patch. Run focused offline pytest with the existing environment; temporary test directories are allowed. No packages, live calls, user source changes, git operations, or unrelated rewrites. Keep the entry small and use existing product services, rather than recreating the protocol harness.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 仅scripts/run_frozen_protocol_comparison.py和tests/test_frozen_protocol_comparison.py：复用ProtocolWorkbenchService、create_protocol_deconstruction_executor、JobRunner建立隔离来源与真实解构，准备和执行分开，强制至少65536；禁止模型调用、个人harness、修改app或原件。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
