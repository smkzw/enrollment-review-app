# Codex Main-Venue Plan: enrollment_review_design_conference_20260812

Date: 2026-08-12
Objective: 独立挑战并会商入排审核本地单用户AI lead多Agent/Graph最终架构、Patient Profile、证据缺口、行动闭环、只读旧项目锚点和阶段实施计划

## Task Decomposition

1. Clinical semantics challenge: test the proposed evidence-strength model, enhanced provenance reminder, gap taxonomy, action ownership, auto-close/override, and stage snapshots against known error classes.
2. Architecture/product challenge: test the minimal local data/Graph architecture, idempotency/recovery, Patient Profile projections, visual prototype sequence, and legacy-anchor strategy.
3. Codex synthesis: reconcile conflicts against confirmed user decisions and current source/runtime evidence; select the smallest architecture that meets acceptance.
4. Produce a final design and phased implementation plan with explicit gates. Do not implement the rearchitecture during this conference.

## Source Packet

- `docs/REARCHITECTURE_DISCOVERY_20260812.md`
- Top current milestone in `docs/PROJECT_CONTEXT.md`
- `app/models.py`
- `app/router/pipeline.py`
- `app/router/subjects.py`
- `app/pipeline/ocr.py`
- `app/pipeline/reviewer.py`
- `app/processing_locks.py`
- `static/index.html`
- `tests/test_phase_workflow.py`
- `output/product_audit_20260812/`

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `general_pi_qwen38` | `alibaba` | `qwen3.8-max` | `runs/conference/enrollment_review_design_conference_20260812/general_pi_qwen38.md` |
| `general_grok45` | `grok-build` | `grok-4.5` | `runs/conference/enrollment_review_design_conference_20260812/general_grok45.md` |

- `general_pi_qwen38`: clinical evidence semantics, rule/gap/action contract, AI-lead failure modes, verification gates.
- `general_grok45`: local product architecture, Graph boundary, persistence/recovery, UI workbench, migration and implementation ordering.

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

- Start: 2026-08-12 17:43 CST.
- Wait for each runner's terminal result or explicit pending state. Do not redispatch because of latency.
- Record effective route, session ID, duration, fallback reason, and whether a same-session follow-up was needed.
- `general_pi_qwen38`: daylight routing policy replaced the declared Qwen route with `Pi/opencode-go/deepseek-v4-flash:max`; one complete pass, session `019ff55e-e542-7000-8e79-806f996f7bcb`, 158.189 seconds, no fallback.
- `general_grok45`: first call ended after a preamble with `cancelled`; Codex preserved session `a0767fec-62d3-4136-8468-93f2438b43cc` and completed the report through one same-session continuation, 160.042 seconds for the accepted continuation, no provider fallback.

## Codex Verification Checklist

- Confirm participant evidence points to actual source files/decisions.
- Reject any recommendation that creates a multi-user approval workflow, changes protocol version semantics, or writes into legacy projects.
- Check proposed entities and transitions cover full/incremental upload, stage snapshots, OCR correction, action auto-close/override, and source linkage.
- Check Agent nodes have structured I/O and deterministic gates; avoid a free-running Agent swarm.
- Check visual prototype covers project dashboard, Patient Profile, rule tree, evidence viewer, action list, and stage snapshots without fixed-width assumptions.
- Keep final implementation plan gated by interactive prototype acceptance and representative MG-K10-SAR III/D001 clinical regression evidence.

## Main-Venue Result

- Accepted: persisted Job/Checkpoint + explicit state machine as the runtime spine; typed Agent calls only at semantic nodes; deterministic gates own logic, dates, units, thresholds, conflict handling, action transitions and reports.
- Accepted: conflict is a first-class blocking state; no source is automatically selected when evidence conflicts.
- Accepted with adjustment: Safety/Provenance Critic is conditionally triggered and veto/downrank/action-only, not a mandatory third pass.
- Accepted with adjustment: auto-close remains available for all gap classes only when an exact, source-linked closure predicate is satisfied in a new ReviewRun; arbitrary uploads cannot close actions.
- Rejected: day-one LangGraph dependency, free Agent discussion, legacy write migration, continued expansion of the monolithic static SPA/reviewer, and LLM-authored blocking levels.
- Deliverables: `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md` and `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`.
