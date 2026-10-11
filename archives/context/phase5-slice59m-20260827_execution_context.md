# Execution Context: phase5-slice59m-20260827

Created: 2026-08-27 16:39:37
Objective: 打通其他方案控制Agent的MTPLX严格Schema传输，并对冻结D001 II期表5代表控制进行真实Agent回放与父级临床验收
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor_cms` -> `pi` / `mtplx` / `mtplx-qwen38-27b-optimized-quality`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `AGENTS.md` and `.trellis/tasks/08-22-phase5-clinical-facts-profile/{prd.md,design.md,implement.md}` remain the task boundary.
- `app/agents/protocol_control_deconstructor.py` owns the provider-neutral control wire, strict response schema, prompt, parser, hydration and bounded same-session runner.
- `app/agents/deepseek_protocol_transport.py` is a comparison reference only. It serves the official IN/EX schema and must not be silently reused for protocol controls.
- `app/config.py` is the MTPLX identity/budget authority. Product calls must use `http://127.0.0.1:8002`, exact model `mtplx-qwen38-27b-optimized-quality`, reasoning `medium`, temperature `0`, and the existing MTPLX protocol output budget.
- Frozen D001 II-phase inputs remain under `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/`; accepted phase applicability is under the slice59j/k artifacts.
- The rejected deterministic replay under `artifacts/phase5-slice59l-d001-table5-structured-control-replay-20260827/` is a diagnostic contract fixture, not Agent extraction evidence and must not be overwritten or promoted.
- Protocol source SHA-256 remains `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`.

## Risk Boundaries

- Execute workers serially. Worker 02 depends on Worker 01; Worker 03 depends on accepted code/tests.
- Worker 01 may write only a new focused transport module under `app/agents/`, the minimal direct export/config integration required, and no tests.
- Worker 02 may write focused transport/runner tests and may repair Worker 01 files only when a test exposes a root defect. It must not create clinical artifacts.
- Worker 03 may write only a bounded helper in the active task research directory and a new `artifacts/phase5-slice59m-*` directory. It must invoke the product `ProtocolControlAgentRunner` through the new real MTPLX transport; deterministic fixture construction or the worker model's own reasoning is not a substitute.
- The product-internal local MTPLX/VLM context is not capped by the execution worker's 32K policy. The endpoint currently advertises 262144 tokens; preserve the application's configured batch budget instead of inventing a new cap.
- Preserve raw response SHA, exact requested model/backend/effort, attempts and same-session repairs. Never persist hidden reasoning content or credentials.
- No production, protocol source, legacy data, subjects, OCR, browser/visual tests, independent testers, or broad remaining-package run.
- Missing transport/schema/harness behavior must fail visibly; no fallback from product MTPLX to another semantic model.
- Shared validators must remain project-neutral; no D001 drug names or row numbers in shared code.

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 实现独立的OpenAI兼容ProtocolControlAgentTransport，使用protocol_control_agent_response_format严格Schema、MTPLX medium和同会话修复历史
2. 为新传输和ProtocolControlAgentRunner补齐真实路径的配置、严格Schema、同会话、长度与错误回归，确保不复用官方IN/EX错误Schema
3. 使用系统内置MTPLX独立Agent/harness对冻结D001 II期表5代表行进行真实小范围回放，保留原始wire哈希/修复/门禁证据并供Codex逐条临床QC

## Completion And Cleanup

Codex accepts this slice only when the real product MTPLX call produces a strict protocol-control wire for the frozen representative scope, the runner hydrates it, publication gates it, and parent source/clinical QC confirms the original Table 5 logic. A deterministic replay remains supporting contract evidence only. `claims_complete=false` throughout.

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
