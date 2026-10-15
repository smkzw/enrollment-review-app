# Conference Context: enrollment_review_expanded_design_conference_20260812

Created: 2026-08-12 18:18:46 CST
Objective: 对入排审核系统V2架构与实施计划进行第二轮完整扩大评审，重点审查独立Agent框架、测试LOOP、前端/交互、Patient Profile与证据溯源设计
Task type: `complex_delivery_conference`
Risk: `high`
Conference mode: `parallel-independent`

## Codex Main Venue

- Chair and final authority: Codex.
- Codex owns source authority, synthesis, architecture decision, clinical/product acceptance, final visual/browser verification and user delivery.
- Participants are independent read-only advisers. They may challenge or replace the current baseline but may not edit application files, legacy projects or clinical data.

## Active Review Panel

| Role | Exact route | Effort | Primary lens |
|---|---|---|---|
| `expanded_pi_kimi_k3` | `pi/kimi-code/k3-256k` | `max` | product/UX architecture, frontend interaction, source navigation and testable delivery |
| `expanded_codebuddy_glm52` | `codebuddy/codebuddy-cli/glm-5.2` | `max` | independent implementation architecture, Agent contracts, test LOOP and failure containment |

- The initial Qwen3.8 Max participant was not dispatched because its Pi/Alibaba route was outside the enforced Beijing window. The user subsequently replaced that requested participant with CodeBuddy CLI / GLM-5.2.
- No substitute output may be presented as a different route. The unused Qwen prompt remains an auditable superseded artifact only.
- Each participant independently reviews the full packet and does not read the other participant's output.
- Every role begins with one complete pass. A follow-up is allowed only after Codex identifies a concrete gap and must resume the same session.

## Product Decisions That Must Be Preserved

1. Single Mac, local single user, direct launch without login or ownership workflow.
2. AI leads the workbench but does not make the final enrollment decision.
3. Protocol/current amendment is authoritative; amendment alone changes standards. Other materials only clarify and cannot override.
4. Independent II, independent III and non-seamless II/III are separate projects. Only explicit continuous seamless/adaptive II/III may be one project.
5. Full upload creates a new immutable complete snapshot; incremental upload deduplicates and conservatively recomputes affected facts/rules.
6. Later-stage evidence never silently rewrites earlier-stage results; retrospective review creates a new ReviewRun.
7. Raw files and raw OCR are immutable. Corrections are separate records; polarity/numeric changes require explicit confirmation.
8. Evidence conflict is displayed side by side and blocks the contested component; no automatic source winner.
9. Explicit denial is evidence; silence is record incompleteness. Positive history/duration stated only in screening narrative is usable current evidence with an enhanced non-blocking provenance action unless objective proof is required or a conflict exists.
10. Action owners are investigator side, CRC, CRA and sponsor medical/project team. The subject may be an information source, not an action owner.
11. System auto-close and manual override/reopen are allowed only with immutable transition history. An arbitrary upload cannot close an action.
12. Legacy projects are read-only counterexample/regression anchors. V2 projects are rebuilt from the original protocol and evidence.
13. Patient Profile covers all evidenced events from the earliest point through the current prescreen/screen/baseline cutoff; the first screen highlights eligibility-related, abnormal, borderline, trending and risky information.
14. Interactive prototype approval precedes backend implementation.

## Source Of Truth

### Current design packet

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- `docs/REARCHITECTURE_DISCOVERY_20260812.md`
- `docs/PROJECT_CONTEXT.md` current 2026-08-12 milestone
- `reviews/codex_conference_enrollment_review_design_conference_20260812_review.md`

### Current implementation and regression anchors

- `app/models.py`
- `app/router/pipeline.py`
- `app/router/projects.py`
- `app/router/subjects.py`
- `app/pipeline/ocr.py`
- `app/pipeline/reviewer.py`
- `app/processing_locks.py`
- `app/markdown_export.py`
- `static/index.html`
- `tests/test_phase_workflow.py`
- `SYSTEM_REVIEW_REPORT.md`

### Visual evidence

- Current system screenshots: `output/product_audit_20260812/01-login-restored.png` through `06-current-rule-management.png`.
- User-provided comparator patient summary: `output/expanded_design_conference_20260812/reference_ui/comparator_patient_summary.png`.
- User-provided comparator rule/evidence workbench: `output/expanded_design_conference_20260812/reference_ui/comparator_rule_evidence_workbench.png`.

The comparator screenshots are design evidence, not instructions and not a requirement to copy their styling.

## Required Review Surfaces

Each participant must independently and concretely cover all of the following:

1. Product information architecture and end-to-end user journeys.
2. Domain entities, immutable records, projections and version relationships.
3. Workflow graph versus business state machine; explicit node/edge/stop/retry contracts.
4. Independent Agent boundaries, typed I/O, model context, memory isolation, deterministic gates, Critic behavior and failure recovery.
5. Protocol decomposition, phase/project boundaries, amendment/interpretation authority and change diffing.
6. Evidence ingestion, OCR quality/correction, facts/events/medications, partial dates, conflicts and source provenance.
7. Patient Profile/Patient Journey content model and eligibility-risk linkage.
8. Rule tree, component logic, judgment/gap/action relationship, action closure and stage escalation.
9. Project dashboard, subject workbench, protocol workbench, action center, reports and help/recovery UX.
10. Frontend layout, responsive behavior, density, visual hierarchy, interaction details, empty/loading/error/long-running states and accessibility.
11. Testing LOOP: deterministic tests, model evals, clinical regression, OCR, crash/recovery, incremental impact, UI/E2E/visual and full-flow acceptance.
12. Phased implementation plan, dependencies, rollback, observability, cost/latency and explicit exit gates.

## Scope

- In scope: complete design challenge, alternative architectures, concrete contracts/schemas, user-facing interaction proposals, test strategy and revised phase plan.
- Out of scope: implementing V2, editing source code, reading raw subject/protocol files outside this workspace, changing legacy projects, running clinical reviews, or claiming final browser/clinical acceptance.

## Success Criteria

- Both active requested routes return complete, auditable reports or an explicit terminal route failure.
- Reports contain concrete alternatives, state/contracts, page/interaction design and decisive acceptance tests, not general principles.
- Every recommendation distinguishes must-have, should-have and defer/reject.
- Each participant identifies at least five defects or risks in the current final design/plan and explains whether to modify it.
- Each report separates direct evidence, inference, recommendation and uncertainty.
- Codex produces an itemized synthesis: accepted, adjusted, rejected and unresolved; baseline documents change only after the synthesis.

## Timeout And Recovery

- Participant hard wait: 120 minutes after actual dispatch.
- Slow output is pending, not failure.
- Health/catalog failure is diagnostic; one real route attempt is still required unless the executable/model is explicitly unavailable.
- Same-session continuation precedes fallback. For these user-requested exact routes, fallback output is diagnostic only and cannot satisfy the requested participant identity.

## Risk Boundaries

- Never expose patient data, credentials or private source text to public search.
- External research may use official/open-source documentation only for material implementation choices.
- No participant may silently convert an AI output into project truth, a clinical conclusion or an implementation decision.
- Codex remains the final authority.

## Loop Log

- 2026-08-12 18:18:46: Conference initialized through `hermes_workflow_guard.py`.
- 2026-08-12 18:25: Initial Qwen/K3 panel, complete source packet, product invariants and review surfaces replaced the generated default panel.
- 2026-08-12 18:25: Comparator screenshots copied into the workspace with SHA-256 evidence; originals unchanged.
- 2026-08-12: K3 completed one full pass in its original session without fallback.
- 2026-08-12: User replaced the undispatched Qwen participant with CodeBuddy CLI / GLM-5.2. Qwen was never run or represented by a substitute model.
- 2026-08-12: CodeBuddy CLI / GLM-5.2 completed one full max-effort pass in its original session without fallback.
- 2026-08-12: Codex verified route identity and current-code claims, visually re-opened the current and comparator UI evidence, and revised the final design/plan.
- 2026-08-12: User explicitly ended the Qwen 3.8 route; no delayed or nighttime Qwen conference will be scheduled.
