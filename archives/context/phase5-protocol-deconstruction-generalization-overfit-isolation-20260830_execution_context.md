# Execution Context: phase5-protocol-deconstruction-generalization-overfit-isolation-20260830

Created: 2026-08-30 22:45:27 CST
Objective: 建立原始DOCX/PDF方案到入排控制点的跨项目通用独立模型解构链：全文只做一次结构化读取和高召回候选定位，仅对候选及必要上下文进行深度语义解构；隔离旧版项目特异正则，禁止Codex手工逐段替代模型，使用D001与MG-K10-SAR只读语料及合成反例证明无项目硬编码。
Task type: `long_horizon_code`
Risk: `medium`
Execution module trigger: Codex identified 4 independent work items, which is greater than two.
Route schedule: `unscheduled`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `openai-codex/gpt-5.6-luna:max -> codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor` -> `pi` / `openai-codex` / `gpt-5.6-luna`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- Architecture and phase contract: `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`, `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`, `.trellis/tasks/08-22-phase5-clinical-facts-profile/{prd.md,design.md,implement.md}`.
- Shared deconstruction runtime: `app/agents/protocol_control_deconstructor.py`, `app/agents/protocol_control_agent_transport.py`, `app/domain/contracts/protocol_controls.py`, `app/protocols/protocol_control_planning.py`, `app/protocols/protocol_control_gate.py`, `app/services/protocol_deconstruction_executor.py`.
- Legacy comparison path: `app/pipeline/reviewer.py` and its callers. This is a compatibility surface, not the V2 semantic source of truth.
- Read-only heterogeneous protocol fixtures: `artifacts/phase5-acceptance/20260823/isolated-inputs/d001/protocol/` and `artifacts/phase5-acceptance/20260823/isolated-inputs/sar/protocol/`. Subject source files are outside this slice and must not be opened.
- Existing protocol-control tests under `tests/v2/protocols/` are the baseline. D001/SAR names, rule numbers, diseases, drugs, scales, time values and thresholds may appear only in read-only fixtures or regression assertions, never in shared production branching.

## File-Level Write Authorization

- `worker_01`: read-only; no source or test edits.
- `worker_02`: may modify only `app/agents/protocol_control_deconstructor.py`, `app/domain/contracts/protocol_controls.py`, `app/protocols/protocol_control_planning.py`, `app/protocols/protocol_control_gate.py`, and may create or update focused files matching `tests/v2/protocols/test_*generalization*.py`.
- `worker_03`: may modify only `app/pipeline/reviewer.py` and create or update `tests/v2/test_legacy_reviewer_boundary.py`. Preserve all current legacy behavior unless a focused compatibility test proves a smaller safe removal; the preferred result is an explicit one-way boundary preventing V2 imports, not a rewrite.
- `worker_04`: may create or update only `tests/v2/protocols/test_protocol_control_anti_overfit.py`; it must review the actual parent-visible diff after workers 02 and 03 finish and must not edit production code.
- All workers may run focused tests and read additional workspace code needed to trace callers. No worker may modify protocol files, raw clinical material, existing accepted artifacts, task history, reports owned by the runner, frontend, storage, migrations, environment configuration or launch scripts.

## Required Technical Boundary

- Raw DOCX/PDF is fully ingested into an immutable structural manifest once. Full structural coverage is not equivalent to sending the whole protocol to every semantic call.
- Candidate discovery must be high recall and model-driven across the full manifest. Deep semantic calls receive owned candidates plus only the necessary heading, table, cross-reference and neighboring context; every structural unit still receives an explicit final disposition.
- Deterministic code validates identity, source closure, structured AND/OR/NOT, exceptions, named time anchors, modality, professional judgment, recommendation versus mandate, phase and cross-section deduplication. It must not infer clinical meaning from project-specific keywords.
- The independent Agent proposes structured candidates and dispositions. Codex and deterministic gates do not manually author missing protocol controls.
- D001 and MG-K10-SAR are acceptance corpora only. A solution that depends on their identifiers or particulars fails this slice even when their tests pass.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 只读审计现有方案解构、控制Agent、发布门禁和legacy reviewer调用链，列出真正共享根因、可复用合同、项目特异耦合及最小迁移边界；不得修改文件。
2. 在现有独立protocol-control Agent链上实现通用提示与输入合同：原始DOCX/PDF完整结构清单、高召回候选定位、候选与必要上下文深度分析、全文处置闭包，明确官方入排和其他章节控制、AND/OR/例外、时间锚点、模态、专业判断、建议与强制、跨章节去重；不得写入D001/SAR专属事实。
3. 以兼容方式隔离app/pipeline/reviewer.py中的项目/疾病/指标/历史文案正则，不扩展特例；将共享新架构路由到结构化合同，并用调用链证据决定保留、退役或加明确legacy边界。
4. 建立反过拟合验收：D001和MG-K10-SAR只作只读异质回归语料，增加重命名/扰动/AND-OR/时间锚点/专业判断/建议模态变异测试，证明代码不依赖项目号、规则号、药物、疾病、量表或固定阈值；独立复核实际差异和测试。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
