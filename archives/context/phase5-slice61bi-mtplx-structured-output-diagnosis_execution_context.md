# Execution Context: phase5-slice61bi-mtplx-structured-output-diagnosis

Created: 2026-08-29 21:03:27 CST
Objective: 定位 MTPLX 长提示词与严格结构化输出组合导致 500 的真实边界；仅使用非临床诊断夹具，保留服务端证据，必要时实施最小系统修复并验证，不运行真实方案重放。
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `day`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `cursor/auto -> google-antigravity/gemini-3.7-flash:high -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> opencode-go/muse-spark-1.2-contributor:xhigh -> openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `pi` / `cursor` / `auto`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- Active recovery checkpoint: `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260829_VITAL_SIGN_MODALITY_INFRASTRUCTURE_BLOCKED.md`.
- Product transport contract: `app/agents/protocol_control_agent_transport.py` and its focused tests.
- Failed replay evidence: `artifacts/phase5-slice61bh-d001-vital-sign-modality-closure-20260829/`; workers may inspect request metadata and error summaries but must not read or reuse clinical prompt/source content.
- Read-only MTPLX runtime sources: `/Users/smkzw/Library/Application Support/MTPLX/runtime-venv/lib/python3.14/site-packages/mtplx/server/openai.py` and `/Users/smkzw/Library/Application Support/MTPLX/runtime-venv/lib/python3.14/site-packages/mtplx/server/flight_recorder.py`.
- Read-only local service endpoints: `http://127.0.0.1:8002/health` and `http://127.0.0.1:8002/v1/chat/completions`.
- Diagnostic inputs must be synthetic, non-clinical, and contain no protocol, subject, center, or patient text.

## Risk Boundaries

- No production writes.
- Do not restart, stop, unload, or reconfigure MTPLX; do not modify its installed package or session bank.
- Do not execute a real protocol-control replay and do not read raw protocol or subject material.
- Repository writes are limited to a compact diagnostic fixture/result under the active Trellis task and a root-cause patch plus focused tests when directly proved necessary.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 检查 MTPLX 服务端 response_format、异常处理和 flight recorder 路径，形成可验证故障假设。
2. 运行非临床诊断矩阵，隔离提示长度、Schema 大小和严格结构化输出的影响。
3. 依据证据实施最小修复或记录外部基础设施阻断，并完成确定性回归与恢复检查点。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
