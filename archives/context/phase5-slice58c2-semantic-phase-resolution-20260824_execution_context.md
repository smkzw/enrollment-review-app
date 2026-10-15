# Execution Context: phase5-slice58c2-semantic-phase-resolution-20260824

Created: 2026-08-24 23:03:03
Objective: 实现独立、可回源的方案期别语义适用性解析层，使全文控制单元在选定项目期别、对侧期别、跨期共用或仍待确认之间有显式处置和证据，未知不默认共享且未决继续阻止发布。
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `codex-subagent` / `codex` / `gpt-5.6-luna`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `AGENTS.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260824_DOCX_HEADING_RECOVERY_ACCEPTED.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/slice58-d001-phase-applicability-gap.md`
- `app/domain/contracts/protocol_controls.py`
- `app/protocols/full_protocol_coverage.py`
- `app/protocols/phase_detection.py`
- `app/protocols/protocol_control_planning.py`
- `app/protocols/protocol_control_gate.py`
- `app/agents/protocol_control_deconstructor.py`
- `app/agents/deepseek_protocol_transport.py`
- `tests/v2/protocols/`
- Worker 03 only may read the user-authorized real protocol at `/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx`; it is strictly read only.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.
- Workers run serially in one authorized worktree. Worker 02 must consume Worker
  01's accepted-in-worktree contracts; Worker 03 must consume both prior slices.
- Do not start the user-declared independent tester routes. Execution, conference,
  and testing roles remain distinct.
- Never infer `SHARED` from missing phase text, proximity, a generic protocol-wide
  section, or the absence of contradictory evidence. Unresolved results must
  remain publish-blocking.
- System-owned stable IDs and source membership are deterministic. The Agent may
  only assess frozen source units and cite provided source references.
- Do not hardcode D001 table numbers, medicine names, official codes, section
  titles, or known outcomes in shared implementation.
- The semantic layer must distinguish: selected-phase applicable, opposite-phase
  applicable, cross-phase shared, and unresolved. It must retain supporting,
  opposing, and unresolved evidence plus a concise Chinese rationale.
- No database migration or UI is authorized in this slice. Manual override is a
  typed immutable contract/history boundary only; persistence and UI remain later work.

## Work Items

1. 建立期别语义解析领域合同、系统稳定身份与确定性门禁，表达逐单元候选期别、支持/反对/未解决来源、最终处置、人工覆盖历史；不得写项目特例。
2. 建立中文原生期别适用性独立Agent输入输出、冻结分批、提示词与严格结构化水合，使Agent可结合上位章节、研究设计、各期方案、流程表、表题表头和交叉引用判断；模型不得创建来源或稳定身份。
3. 将解析结果接入全文清单与发布控制门禁，增加通用反例和D001 II只读前后复测；证明表5及跨章节控制不丢失、未决不发布，并记录后续人工矩阵边界。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
