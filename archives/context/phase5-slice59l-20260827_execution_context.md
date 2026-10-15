# Execution Context: phase5-slice59l-20260827

Created: 2026-08-27 15:57:24
Objective: 闭合D001 II期表5时间窗择长、条件性洗脱缩短与原文分支作用域，使结构化控制可执行且不把且改为或
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

- `AGENTS.md` and `.trellis/tasks/08-22-phase5-clinical-facts-profile/{prd.md,design.md,implement.md}` define the active task boundaries.
- `app/domain/contracts/rules.py` is the shared `TimeConstraint` authority; do not create a second time-window model.
- `app/domain/contracts/protocol_controls.py`, `app/agents/protocol_control_deconstructor.py`, and `app/protocols/protocol_control_gate.py` are the candidate, wire/hydration, and publication-gate authorities.
- `app/domain/contracts/protocol_control_matrix.py` is an accepted comparison-matrix reference for explicit DNF branch identities and exception scope; reuse the existing semantics where possible instead of inventing a parallel topology.
- Frozen D001 II phase inputs are under `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/`.
- Accepted Table 5 phase-applicability evidence is under `artifacts/phase5-slice59j-d001-package64-mtplx-20260827/`, `artifacts/phase5-slice59j-d001-package65-mtplx-20260827/`, and the clean package 63 rerun under `artifacts/phase5-slice59k-d001-package63-control-character-repair-20260827/`.
- The source protocol is read-only and remains identified by SHA-256 `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`.
- Clinical source logic that must remain explicit: fixed window plus five half-lives uses the longer window; leflunomide is 24 months unless clearance-agent washout supports the stated 6-month branch; Chinese herbal exception is local to its named category; all windows use the protocol-named first-dose anchor, never screening date.

## Risk Boundaries

- No production writes.
- Do not modify source protocols, legacy project data, previously accepted immutable artifacts, or old execution evidence.
- Do not run subjects, OCR, browser/visual testing, independent testers, or all remaining phase packages.
- Do not hardcode D001-specific drug names or row numbers in shared validators. Generic source-backed semantics must drive rejection.
- Worker 01 may modify only `app/domain/contracts/{rules.py,enums.py}` and focused protocol tests needed for the shared time contract.
- Worker 02 may modify only `app/domain/contracts/protocol_controls.py`, `app/agents/protocol_control_deconstructor.py`, `app/agents/protocol_deconstructor.py`, `app/protocols/protocol_control_gate.py`, exports directly required by those contracts, and focused protocol tests. The official IN/EX adapter is included only so the shared `TimeConstraint` field cannot be silently dropped on that sibling path.
- Worker 03 may write only a new immutable directory under `artifacts/phase5-slice59l-*` plus a bounded replay helper under the active task research directory if necessary. It must not modify shared source code.
- Execute workers serially in numeric order because each later item consumes the accepted state of the previous item.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 审查并最小化扩展共享TimeConstraint合同，显式保留固定窗口与半衰期取较长者语义，补确定性验证与回归测试
2. 扩展协议控制候选wire、水合合同和发布门禁，保留条件分支与对应义务/时间窗的成对作用域，覆盖来氟米特24个月与清除剂后6个月
3. 用冻结D001 II期表5来源做小范围真实回放和父级临床QC，确认较长者、条件缩短、嵌套例外及首次给药锚点均进入结构化结果

## Completion And Cleanup

Each worker runs the smallest focused tests for its scope. Codex then performs integrated focused regression, a real frozen Table 5 replay, source-level clinical QC, broader protocol regression, review gate, execution audit, Trellis validation, and `git diff --check`. A phase-applicability rationale alone is not a structured-control acceptance artifact. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete product evidence by default.
