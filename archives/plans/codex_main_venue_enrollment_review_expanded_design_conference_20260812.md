# Codex Main-Venue Plan: enrollment_review_expanded_design_conference_20260812

Date: 2026-08-12
Objective: 对入排审核系统V2架构与实施计划进行第二轮完整扩大评审，重点审查独立Agent框架、测试LOOP、前端/交互、Patient Profile与证据溯源设计

## Task Decomposition

1. Freeze the three-round user decisions and current design as a challengeable baseline, not an assumed answer.
2. Dispatch two exact, independent, full-scope reviewers with the same source packet.
3. Require both to inspect source architecture and real screenshots, propose a concrete target product and identify baseline defects.
4. Compare recommendations across product, clinical semantics, Agent design, provenance, UI and implementation gates.
5. Codex verifies source claims and writes an accepted/adjusted/rejected decision table.
6. Only after conference acceptance, revise the final design and implementation plan; V2 implementation remains blocked pending user approval.

## Source Packet

- `context/enrollment_review_expanded_design_conference_20260812_conference_context.md`
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- `docs/REARCHITECTURE_DISCOVERY_20260812.md`
- `docs/PROJECT_CONTEXT.md`
- current backend/frontend files and `tests/test_phase_workflow.py` listed in the context
- current and comparator screenshots listed in the context

## Participant Assignments

| Role | Agent/provider | Model | Effort | Output |
|---|---|---|---|---|
| `expanded_pi_kimi_k3` | `pi/kimi-code` | `k3-256k` | `max` | `runs/conference/enrollment_review_expanded_design_conference_20260812/expanded_pi_kimi_k3.md` |
| `expanded_codebuddy_glm52` | `codebuddy/codebuddy-cli` | `glm-5.2` | `max` | `runs/conference/enrollment_review_expanded_design_conference_20260812/expanded_codebuddy_glm52.md` |

Both roles independently review the whole system. Their primary lenses guide emphasis but do not limit scope.

## Conference Coordination

- No sub-venue chair. Codex leads and decides.
- Participants do not read one another's report.
- K3 completed first. GLM-5.2 runs from a fresh independent context and does not read K3 output.
- The initial Qwen role was superseded before dispatch and is excluded from synthesis.
- The user later explicitly ended the Qwen 3.8 route; no delayed/nighttime Qwen pass is pending.
- A follow-up requires a concrete missing deliverable and resumes the same session.

## Required Deliverables From Each Role

1. Executive verdict and baseline challenge.
2. Target end-to-end user workflow and page architecture.
3. Domain/data/provenance model with immutable and projected records.
4. Agent and deterministic-node architecture with typed contracts and failure handling.
5. Patient Profile and rule/evidence/action interaction design.
6. Frontend layout and responsive interaction specification grounded in screenshots.
7. Testing/QC LOOP and measurable release gates.
8. Revised implementation phases, dependencies, rollback and observability.
9. Prioritized must/should/defer list and bounded questions for Codex.

## Codex Verification Checklist

- Confirm exact provider/model/effort and session identity from runner logs.
- Verify source citations and code claims against current files.
- Reject recommendations that violate the frozen product decisions.
- Check proposed Agent nodes have typed inputs/outputs, isolation, deterministic gates, retries and stop conditions.
- Check every user-facing risk/action can navigate to a real EvidenceSpan or an honest lower-precision locator.
- Check UI proposal supports project dashboard, protocol workbench, Patient Profile, rule/evidence workbench, action center, history and reports.
- Check testing covers clinical semantics, model variation, OCR, partial dates, conflicts, crash/recovery, incremental/full snapshots and real browser behavior.
- Ensure implementation plan has per-phase rollback and acceptance evidence.

## Hold Point

No V2 implementation begins in this conference. Codex first presents the synthesized design changes and revised implementation plan for user approval.
