# Execution Context: phase5-slice61ao-replay-harness-budget-contract-20260829

Created: 2026-08-29 00:02:33 CST
Objective: 在不运行临床模型重放的前提下，将 p803-p805 不可变重放路径固化为可提交、可重现、不依赖人工矩阵的产品级 harness，并建立修订类串行后的明确预算合同与确定性验证。
Task type: `finite_code_task`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `night`; resolved once at packet creation in `Asia/Shanghai`.
Effective worker chain: `codebuddy-cli/glm-5.3-flash:max -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> openai-codex/gpt-5.6-luna:xhigh`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `codebuddy` / `codebuddy-cli` / `glm-5.3-flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- Shared product chain: `app/protocols/`, `app/agents/protocol_control_deconstructor.py`, `app/protocols/protocol_control_repair_errors.py`, and their current tests.
- Generic patterns only from `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py` and `build_d001_phase_closure.py`.
- Frozen plan, coverage manifest, source/block blobs, and immutable v8 failure artifacts are regression anchors; they are not accepted clinical outputs.
- The human control matrix, D001-specific reject gates, hardcoded source paths/hashes/counts, and legacy `span-*` identities are forbidden product dependencies.
- The default harness path must be model-free and must not instantiate a transport. Live replay remains a separate explicit action and is out of scope for this execution packet.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 审计现有 p803-p805 临时重放脚本、产品执行链和不可变工件，输出最小可提交 harness 的复用路径、禁止依赖与验收点。
2. 实现通用且项目无关的重放 harness，从原始 DOCX/PDF 产品结构化链构建指定稳定 source_ref 范围，保存不可变输入、输出和指纹，默认不调用模型。
3. 建立串行修订类的预算合同与回归，防止默认2次在多类错误时产生偶然失败，同时保持严格上限、无限循环防护和不变输出。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.

## Route Event

- The declared CodeBuddy primary returned an explicit `429` rate-limit response on worker 01, but the runner misclassified the text response as success and did not activate fallback.
- Codex preserved that output and log, verified AC power and more than 50 GB available memory, then used the packet-declared MTPLX fallback directly. The same verified provider unavailability applies to the remaining work items; no undeclared model substitution is allowed.
