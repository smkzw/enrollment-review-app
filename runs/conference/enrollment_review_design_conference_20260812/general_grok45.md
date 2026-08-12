I already have the discovery and core source evidence; I'll pull a few precise anchors on jobs/recovery, OCR caching, and the frontend monolith, then deliver the full report.# Conference Participant Output: enrollment_review_design_conference_20260812 - general_grok45

## Boundary Check

| Item | Status |
|---|---|
| Role | `general_grok45` / Grok Build `grok-4.5` — product-architecture and workflow critic |
| Workspace only | Observed |
| No production/source-clinical paths | Observed — no raw subject docs, protocols outside workspace, or legacy payload mutation |
| No file edits | Observed — report returned in this response only; runner owns persistence |
| No other-participant read | Observed |
| No final visual/browser acceptance claimed | Observed — Codex retains final authority |
| Tools | Targeted read of assigned packet and anchors only; no broad restart of discovery |

**Sources used this pass (session-continued):**

- `AGENTS.md` / project phase boundary  
- `context/enrollment_review_design_conference_20260812_conference_context.md`  
- `plans/codex_main_venue_enrollment_review_design_conference_20260812.md`  
- `docs/REARCHITECTURE_DISCOVERY_20260812.md` §§4–17  
- `docs/PROJECT_CONTEXT.md` (2026-08-12 milestone)  
- `app/models.py`, `app/router/pipeline.py`, `app/pipeline/ocr.py`, `app/processing_locks.py`  
- `static/index.html` (auth/SSE/phase-cell anchors)  
- Screenshots: `output/product_audit_20260812/04-current-subject-list.png`, `05-current-subject-report.png`

---

## Independent Work Product

### 1. Highest-impact objection (lead finding)

**Claim (recommendation):** On a local single-Mac / single-user app, a **three-node free Graph (Evidence Normalizer → Eligibility Assessor → Safety Critic) as the runtime spine is over-design**. Safer target is:

> **Persisted explicit state machine + durable job table + bounded typed Agent calls at semantic nodes only.**

**Why this is the highest-impact defect if left unchallenged:**

Current runtime already fails durability without any multi-Agent complexity:

| Failure mode (evidence) | Current behavior | Impact if Graph multiplies it |
|---|---|---|
| Job not durable | `/process` is request/SSE-bound; disconnect **cancels** review and sets subject to `pending` (`pipeline.py` ~366–373) | Graph checkpoints without a job table still die with the process |
| Lock not durable | `asyncio.Lock` dict in-process (`processing_locks.py`) | Restart leaves `status=processing` sticky; multi-Agent makes concurrent races worse |
| Cache not content-addressed | OCR hit is `mtime` compare (`ocr.py` `_cache_hit`) | Silent reuse after copy/replace/OCR model change; “facts” look fresh but are wrong |
| Single top-level verdict | `SubjectInfo.overall_verdict` + phase columns that still collapse risk into pass/fail/insufficient (`models.py`, subject-list screenshot) | Three Agents writing into the same collapsed field re-create today’s semantic collapse |

**Concrete remediation:** Ship **Job + Checkpoint + Domain DB first**; Agents second; LangGraph **optional later** only if the explicit state machine’s interrupt/resume code becomes painful. Do not adopt LangGraph as the clinical source of truth.

---

### 2. Minimal target architecture

#### 2.1 Runtime spine (not “Agent Graph”)

```
User action / upload
  → durable Job (queued|running|paused|succeeded|failed|cancelled)
  → explicit WorkflowState machine (versioned transitions)
  → step handlers (mostly deterministic code)
  → optional typed AgentCall records (input hash, model, prompt version, structured output, status)
  → DeterministicGate (always runs after semantic steps)
  → projections: Patient Profile, dashboard, reports, ActionRequest views
```

**Reject as default:** free multi-Agent conversation, shared mutable agent memory, or LangGraph as the only recovery mechanism.

**Accept as optional later:** LangGraph-style checkpoint library *behind* the same Job/State interfaces — never as the business schema.

#### 2.2 Persistence: SQLite/WAL (justified)

For single-Mac single-user, **SQLite + WAL is the right default**. Temporal/Postgres are out of scope.

**Core tables (minimal, not FHIR warehouse):**

| Table | Role |
|---|---|
| `project`, `protocol_version`, `rule_set_version`, `rule`, `rule_component` | Official IN/EX numbering, parent/child, ALL/ANY/NOT, thresholds, windows, exceptions |
| `subject`, `review_episode` | Stage (prescreen/screen/baseline), anchors, evidence cutoff, episode status |
| `evidence_snapshot`, `source_document_version` | Full vs incremental snapshots; content hash; never overwrite prior versions |
| `ocr_page`, `evidence_span` | Page, region, excerpt, OCR model/version, confidence |
| `clinical_fact`, `clinical_event`, `medication_exposure` | Structured fact layer (source of Patient Journey) |
| `eligibility_assessment`, `component_judgment` | Per-rule-component judgment, gap reason orthogonal to verdict |
| `action_request`, `action_transition` | Open/auto-closed/override history; idempotent keys |
| `job`, `job_checkpoint` | Durable background work; step cursor; retry; cancel |
| `agent_call` | Bounded semantic I/O audit |
| `resolution_record` | OCR correction / user override / re-run scope |

Files remain for **blobs** (PDF/images/OCR markdown). SQLite holds **identity, versions, links, state**. Do not keep JSON/Markdown as business truth for rules/verdicts/actions.

#### 2.3 Job / checkpoint / idempotency (must-have; current gap)

**Evidence of gap:** SSE pipeline + in-memory lock + browser batch loop (discovery §5.4; `pipeline.py`; `index.html` `EventSource`).

**Required design:**

1. **Job row first**, then work. UI polls `/jobs/{id}` or SSE *subscribes to job events*, never owns the job lifetime.  
2. **Checkpoint after every deterministic step** (OCR page batch, fact upsert batch, gate pass). Semantic Agent steps checkpoint **inputs + structured outputs** before advancing.  
3. **Idempotency keys:**  
   - `source_document_version` = hash(bytes) + relative path policy  
   - `ocr_page` = (doc_version_id, page, ocr_model_version)  
   - `agent_call` = hash(node, prompt_version, input_payload_hash, model)  
   - `action_request` = (episode_id, rule_component_id, gap_type, open_generation)  
4. **Crash recovery:** on boot, any `running` job re-enters from last checkpoint; stuck locks are DB-owned (`locked_by`, `lease_until`), not process memory.  
5. **Cancel semantics:** cancel = job cancelled + workflow paused; **never** silently rewrite episode judgments.

#### 2.4 Three semantic Agents: justified only as *optional typed calls*, not as three always-on peers

| Proposed Agent | Keep? | Condition |
|---|---|---|
| Evidence Normalizer | **Yes (v1)** | Semantic extraction → structured facts; hard schema; fails closed to gap |
| Eligibility Assessor | **Yes (v1)** | Per episode + rule set + retrieved facts; component-level output only |
| Safety & Provenance Critic | **Defer to v1.5 / high-risk rules** | Independent context is valuable, but **double LLM cost on one Mac** and second free-text path can reintroduce contradictions unless it is **veto-only** with structured codes |

**Safer v1 policy:**

- Always run **DeterministicGate** after Assessor (logic, units, windows, parent/child AND/OR, verdict consistency, citation existence).  
- Critic is a **second pass only when gate flags risk or rule risk tier is high** — not a mandatory third agent on every subject.  
- Critic **may only** reject / down-rank certainty / open ActionRequest; **never** silent rewrite of Assessor judgments (matches discovery §7.2 intent; strengthen it as a hard code invariant).

**Inference:** “Graph organization” in discovery §8 is directionally right for **workflow topology**. Implementing it as **three always-running LangGraph agents** on day one is not justified by single-user scale.

#### 2.5 Deterministic vs Agent-owned (hard split)

**Must be deterministic code (no LLM authority):**

- Document fingerprint, dedupe, snapshot activate/retire  
- OCR cache invalidation (hash + model version)  
- Rule numbering integrity, parent/child rollup, ALL/ANY/NOT evaluation over already-extracted component results  
- Unit conversion, numeric compare, time-window math with partial-date bounds  
- Stage transitions; evidence cutoff; “baseline evidence must not rewrite screening episode”  
- Action open/auto-close/override transition graph and audit rows  
- Job scheduling, retries, concurrency leases, OCR semaphore (≤8)  
- Report/dashboard projections from structured state  
- Protocol vs Q&A authority: Q&A never mutates RuleSetVersion; conflict → warning ActionRequest only  

**May be Agent (typed JSON in/out, versioned prompts):**

- Protocol → RuleComponent draft extraction (human edit + publish required)  
- Page/section → ClinicalFact / Event / MedicationExposure candidates  
- Mapping free text to rule components and provisional component judgments  
- Gap-type *suggestion* when taxonomy needs narrative understanding (still validated against allowed enum)  
- Natural-language report narrative **as projection only**, never as source of truth  

**Uncertainty:** Exact prompt schemas and retrieval strategy for Assessor are implementation detail; the **split above is not**.

---

### 3. Evidence snapshots, stage history, OCR correction, actions

#### 3.1 Full vs incremental (confirmed product decision — implement literally)

| Mode | Behavior | Risk if botched |
|---|---|---|
| Incremental | Content-hash dedupe; merge new `source_document_version`s into **current active snapshot**; re-run **affected** facts/rules only | Wrong impact analysis → silent incomplete re-review |
| Full | New `evidence_snapshot` generation; retire previous active; **no physical delete** of old files/reports/judgments | Treating “full” as delete/overwrite → audit loss |

**Recommendation:** `evidence_snapshot.active` is a pointer, not a destructive replace. All judgments bind `snapshot_id` + `rule_set_version_id` + `episode_id`.

#### 3.2 Stage history (confirmed)

- Each stage = `review_episode` with independent judgments.  
- Baseline new evidence **never** mutates screening episode rows.  
- “Re-review screening with later evidence” is an **explicit new ReviewRun** on a new or cloned episode generation, with reason code — not an in-place overwrite of `overall_verdict`.

**Evidence current defect:** `info.overall_verdict = report.overall_verdict` on process done (`pipeline.py` ~389) and single report banner “证据不足” (screenshot 05) collapse orthogonal dimensions.

#### 3.3 OCR / fact correction (confirmed)

- Raw file + original OCR immutable.  
- Correction stores `corrected_text` / corrected fact + `resolution_record`.  
- Re-run scope = impacted fact IDs → linked rule components → actions.  
- Cache key **must include content hash + OCR model version** (replace mtime).

#### 3.4 Action auto-close / override (confirmed — high footgun)

**Product allows auto-close + user override.** Architecture must prevent silent false closure.

**Required state machine for ActionRequest:**

```
open → auto_resolved_candidate → (auto_closed | reopened)
open → user_closed_override
auto_closed → user_reopened_override
any → superseded (new snapshot/run)
```

**Hard rules:**

1. Auto-close only when **same gap_type’s required evidence predicates** are satisfied by **new** facts linked to the **same rule_component** — not when Assessor narrative says “OK”.  
2. Every transition writes `action_transition` with: before/after, trigger (`upload|ocr_correct|rerun|user`), evidence locators, job_id, actor (`system|user`).  
3. **Idempotent:** re-running the same job must not create duplicate open actions; use stable natural key + generation.  
4. Provenance-reminder actions are **non-blocking by default** and must **not** auto-close into “pass/sufficient” language on the dashboard primary status.

**Highest clinical product risk (architecture-shaped):** enhanced provenance reminder + auto-close can be misread as “证据充分 / 可入组”. Dashboard primary status must never be computed from “absence of open blocking actions” alone; it must prefer **explicit obstacle / conflict / incomplete** ranks (confirmed sort order in §16.3).

---

### 4. Legacy read-only anchors vs fresh projects

**Agree with confirmed decision; strengthen the engineering consequence:**

| Legacy projects | New system |
|---|---|
| Read-only counterexamples and regression anchors | Create **new** projects from protocol/source inputs |
| Do not migrate write-path into old project dirs | Golden tests extract **error classes** (AND/OR collapse, analyte swap, syphilis exception, phase anchor abuse, negation) into deterministic fixtures |
| Keep old HTML/MD reports as historical artifacts | Do not import legacy `overall_verdict` as ground truth |

**Risk if “import adapter first” creeps back in (discovery §10.3 wording conflict with §16.5):**  
§10.3 still says “只读导入器，将旧项目投影到新模型”; §16.5 says legacy is **not** a migration write base.  

**Recommendation (resolve contradiction):**  
- **No write migration of legacy projects.**  
- Optional **read-only projection tools** for side-by-side comparison in a *separate* sandbox DB.  
- Regression value lives in **tests/fixtures and documented error classes**, not in mutating `projects/MG-K10-SAR*`.

---

### 5. Interaction architecture (prototype-first — supported)

Confirmed sequence: interactive prototype **before** data layer/Graph. That sequence is correct **if and only if** the prototype is driven by **mock structured domain objects**, not by reusing `static/index.html` report strings.

#### 5.1 Information architecture (target)

1. **Project dashboard**  
   - Per subject, per episode: **primary status** + counts  
     e.g. `明确障碍 1 | 记录不完整 2 | 需研究者 1 | 冲突 0 | 后续关注 3`  
   - Sort: obstacle > required gap > conflict > professional judgment > later-stage > clear  
   - No login chrome; no owner column as product concept  

2. **Subject header**  
   Demographics, episode, anchors, evidence cutoff, open-action count, active snapshot id  

3. **Patient Profile / Journey**  
   - Span: earliest evidenced event → current episode cutoff  
   - Lanes (disease, meds, labs/scores, history, evidence/conflict)  
   - Default filter: eligibility-relevant / abnormal / borderline / trending  
   - Click → EvidenceSpan (file, page, region, excerpt)  

4. **Rule workbench (synchronized)**  
   Rule tree ↔ component judgment ↔ fact list ↔ source viewer  
   Selection sync is the product; three always-visible dense columns are not mandatory on narrow viewports  

5. **Action list**  
   `target_party`, `missing_component`, `requested_action`, `acceptable_evidence`, `due_stage`, `blocking_level`, `source_and_rule`, status + history  

6. **Full detail / audit**  
   Jobs, agent calls, transitions, snapshot lineage, stage episodes  

#### 5.2 Responsive behavior

- CSS Grid + `minmax`, collapsible panels, container queries  
- Desktop: optional split workbench  
- Narrow: stacked tabs with **shared selection state** (rule/fact id in URL or session store)  
- Avoid fixed pixel primary layout (project rule)  

#### 5.3 Can prototype validate workflow before backend replacement?

**Yes**, for:

- density, navigation, selection sync mental model  
- status+counts comprehension  
- action card completeness  
- stage snapshot switching UX  

**No**, for:

- incremental impact analysis correctness  
- auto-close safety  
- OCR correction cascade  
- recovery after kill -9  

Those require backend acceptance tests (below). Prototype must use **fixture JSON matching target entities**, not live `ReviewReport.to_markdown()` output.

#### 5.4 Contamination risk if reusing monolith directly (critical)

| Contaminant | Source | Why toxic for new design |
|---|---|---|
| Auth/login/admin/owner | `index.html` localStorage + screenshots | Violates single-user direct-launch decision |
| `overall_verdict` / five-way enum | `models.py` `ReviewVerdict` | Collapses judgment × gap × stage |
| Narrative “证据不足” hero | report UI | Hides action contract |
| SSE-owned process | `processSubject` EventSource | Teaches wrong recovery model |
| Regex post-guards in reviewer | `reviewer.py` (discovery scale) | Encodes clinical patches in text repair instead of RuleComponent+Gate |
| Markdown rules as truth | `criteria_rules.md` | Re-breaks AND/OR/exceptions |
| mtime OCR cache | `ocr.py` | Fake reproducibility |

**Recommendation:** New prototype and new write-path are a **greenfield shell** that may **call** existing upload/OCR adapters as libraries. Do **not** extend `static/index.html` or `reviewer.py` into the target architecture by accretion.

---

### 6. Bounded implementation phases

| Phase | Deliverable | Exit gate |
|---|---|---|
| **P0 — Freeze design** | Codex synthesis of conference; user approval of minimal architecture | Written acceptance of entity list + Agent split + no-login + legacy read-only |
| **P1 — Interactive prototype (mock data)** | Dashboard, Profile, rule/evidence workbench, action list, stage snapshot switch; desktop + narrow | User accepts density/navigation; no backend claim |
| **P2 — Domain DB + jobs** | SQLite/WAL schema, Job/Checkpoint, snapshot/version, stage episodes; adapter wrappers for OCR/upload | Kill process mid-job → resume; no sticky processing without lease |
| **P3 — Structured rules + DeterministicGate** | RuleComponent model, publish RuleSetVersion, gate tests ported from known error classes | Golden tests for AND/OR, analyte, syphilis exception, anchors, negation **without** LLM |
| **P4 — Evidence Normalizer + Assessor (typed)** | AgentCall audit; fact layer; component judgments; ActionRequest generation | One fresh pilot project end-to-end; actions complete contract fields |
| **P5 — Patient Profile projection + OCR correction** | Journey lanes, source navigation, correction + scoped rerun | Correction does not mutate raw OCR; impact scope limited |
| **P6 — Auto-close/override + optional Critic** | Action transition machine; optional veto Critic on high-risk | No silent auto-close without predicate; override audited |
| **P7 — Hard cutover of write path** | New projects only on new path; legacy remains read-only anchors | Parallel comparison on fixture error classes meets bar; user approval |

**Rollback / migration:**

- Feature-flag **new write path** per project.  
- Never delete legacy project trees.  
- Schema migrations versioned; WAL backup before migrate.  
- If P4 quality fails: fall back to P3 + manual structured entry; do not re-enable free-text reviewer as authority.  
- Prototype (P1) is disposable UI; do not “promote” mock handlers into production without schema.

---

### 7. Decisive acceptance tests (architecture-level)

**Non-LLM (must pass first):**

1. **Content-hash OCR:** same bytes → cache hit; bytes change → miss; model version change → miss.  
2. **Job durability:** start job, kill server, restart → job resumes at checkpoint; subject not permanently `processing` without live lease.  
3. **SSE disconnect:** closing browser does **not** cancel job (opposite of current).  
4. **Stage isolation:** baseline upload leaves screening episode judgments byte-identical.  
5. **Full snapshot:** activate new snapshot; old snapshot judgments and files still readable.  
6. **Incremental dedupe:** re-upload identical file → no new doc version; new file → impact set recompute.  
7. **Action idempotency:** double job completion → one open action per natural key.  
8. **Auto-close predicate:** action closes only when required structured evidence appears; narrative-only “pass” does not close.  
9. **Override audit:** user reopen after auto-close retained with reason.  
10. **Gate regression pack:** port critical cases from `tests/test_phase_workflow.py` error classes into component/gate unit tests.  
11. **No-login path:** direct entry to project list without auth storage.  
12. **Legacy write guard:** API refuses mutating methods on legacy-marked projects.

**Semantic (bounded, with fixtures):**

13. Fresh project from protocol → published RuleSetVersion with official IN/EX numbers.  
14. Assessor output validates against schema; missing citation → gate fail, not dashboard pass.  
15. Provenance-reminder item never becomes primary status “clear” without explicit non-blocking classification.

**Prototype (user/Codex visual authority):**

16. Desktop + narrow: selection sync rule↔evidence without horizontal page scroll traps.  
17. Dashboard shows primary status + counts, not single badge only.

---

### 8. Over-design registry (cut or defer)

| Item | Verdict |
|---|---|
| Always-on 3-Agent Graph / LangGraph day-one | **Defer** — explicit state machine first |
| Temporal / Postgres | **Out** for local single-user |
| Full FHIR resource server | **Out** — borrow field ideas only |
| Multi-user approval / RBAC | **Out** (confirmed) |
| Import-write of legacy projects | **Out** (confirmed; override soft wording in §10.3) |
| Critic on every rule | **Defer** — risk-triggered |
| Perfect complete timeline of all normal labs on first screen | **Out** — store all, show eligibility-relevant default (confirmed) |
| Reusing 3,115-line SPA as base | **Out** — contamination risk |

---

### 9. Active peer objections / solutions / decision points / questions for Codex

#### Objections

1. **Graph framing invites framework lock-in** before durable jobs exist.  
2. **Auto-close + provenance reminder** is the highest product-safety footgun under AI-lead.  
3. **§10.3 vs §16.5** migration wording can reintroduce write-import of legacy.  
4. **Monolith reuse** will smuggle login, overall_verdict, and SSE job ownership into the “new” system.  
5. **Mandatory Critic** doubles cost/latency on one Mac without guaranteed safety unless veto-only and gated.

#### Proposed solutions

1. Codify **Job/State/Gate** as architecture spine; Agents as `agent_call` rows.  
2. Auto-close only via **structured predicates**; dashboard rank ignores non-blocking provenance for primary status.  
3. Strike write-import; keep read-only compare tools + fixture extraction.  
4. Greenfield UI shell + library adapters.  
5. Critic optional / risk-tiered in v1.

#### Decision points for Codex synthesis (not reopening frozen user product choices)

| ID | Decision | Provisional safe path if undecided |
|---|---|---|
| D1 | LangGraph in P2 vs pure custom state machine | **Custom state machine + SQLite jobs in P2**; evaluate LangGraph only if interrupt UX becomes costly |
| D2 | Critic mandatory vs risk-triggered | **Risk-triggered / veto-only** |
| D3 | Prototype tech (new static shell vs separate HTML kit) | **New shell**; zero copy of auth/SSE process ownership |
| D4 | Scope of “affected” recompute after incremental upload | Start conservative: recompute all components linked to changed doc’s facts; optimize later |

#### Bounded questions for Codex (only if needed to close design)

1. **D1 confirmation:** Is day-one implementation allowed to ship **without** LangGraph if Job+State+Gate acceptance tests pass?  
2. **Action auto-close predicates:** Should Codex freeze a **machine-checkable predicate catalog** per gap_type before P6, or allow Assessor-suggested close with gate confirmation only? (Matters for false auto-close risk.)  
3. **Legacy fixture extraction:** Who owns extracting MG-K10-SAR III / D001 error cases into anonymized structured fixtures without reading raw clinical payloads in conference follow-ups?

---

## Evidence And Assumptions

### Evidence (direct observation)

- Discovery confirms single-Mac single-user, AI-lead non-final authority, full+incremental snapshots, stage history isolation, OCR correction, auto-close+override, legacy read-only, prototype-first (`docs/REARCHITECTURE_DISCOVERY_20260812.md` §§11–16; `PROJECT_CONTEXT.md` milestone).  
- Domain model today is thin: `SubjectInfo.overall_verdict`, no fact/action/episode entities (`app/models.py`).  
- Pipeline durability: SSE `/process`, disconnect cancels review (`app/router/pipeline.py`).  
- Locks are in-process only (`app/processing_locks.py`).  
- OCR cache uses mtime (`app/pipeline/ocr.py` `_cache_hit`).  
- Frontend is ~3115-line SPA with login token state and EventSource processing (`static/index.html`).  
- UI audit: subject list still shows collapsed badges; report hero is narrative “证据不足” with soft reminders, not structured ActionRequest cards (`output/product_audit_20260812/04`, `05`).  
- Discovery still lists LangGraph as early candidate while also saying explicit state machine remains open (`§8.4`).  
- Internal tension: §10.3 import projection vs §16.5 no legacy write migration.

### Inferences

- Current clinical errors are primarily **representation and gate** failures, not “insufficient number of agents.”  
- Three always-on Agents would amplify cost and contradiction risk without fixing durability/fingerprint/stage isolation.  
- Prototype-first works only if mock data matches target schema; otherwise it validates the wrong product.

### Recommendations (summary)

1. Minimal spine: **SQLite/WAL + Job/Checkpoint + explicit state machine + DeterministicGate + 1–2 typed Agents**.  
2. Critic deferred/risk-triggered, veto-only.  
3. Greenfield UI/prototype; adapters only from OCR/upload.  
4. Legacy read-only anchors + fixture extraction; no write migration.  
5. Auto-close by structured predicates; provenance never masquerades as sufficiency.  
6. Phased P0–P7 with kill-and-resume and stage-isolation as hard gates before LLM expansion.

### Uncertainties

- Exact gap_type → auto-close predicate catalog not yet frozen.  
- Whether user-visible “主状态” enum labels are fully locked beyond the six stage-judgment categories in §13.7.  
- Performance envelope for local LLM on full subject corpora (not measured this pass).  
- Final visual acceptance of density — Codex/user authority, not this participant.

---

## Risks, Gaps, And Verification Needs

| Risk | Severity | Prevented by current proposal? | Remediation / test |
|---|---|---|---|
| False “证据充分” via auto-close + provenance | **Critical** | Partially named, not fully engineered | Predicate catalog + dashboard rank tests |
| Sticky `processing` / lost work on restart | **Critical** | Not prevented today | Job lease + boot recovery test |
| Stage silent rewrite | **Critical** | Product decision yes; code no | Episode immutability test |
| mtime OCR wrong reuse | **High** | No in current code | Hash+model cache test |
| Monolith contamination | **High** | Not if reuse SPA/reviewer | New shell rule in P1 exit gate |
| LangGraph/framework overfit | **Medium–High** | Challenged here | D1: state machine first |
| Legacy write-import drift | **High** | §16.5 yes; §10.3 muddy | Codex strike import-write; API guard |
| Mandatory third Agent cost/contradiction | **Medium** | Deferred here | Risk-tier Critic only |
| Incremental impact under-compute | **High** | Named, algorithm open | Conservative recompute first |
| Prototype validates cosmetics only | **Medium** | If mock schema used, OK | Fixture-driven prototype checklist |

**Verification not performed this pass (by design):** live browser acceptance, clinical re-run, reading other participant output, raw subject files, implementing code.

---

## Recommended Next Step

1. **Codex synthesis:** adopt **persisted explicit state machine + SQLite/WAL jobs** as the architecture spine; treat three Agents as **typed optional nodes**, with Critic **not** mandatory in v1.  
2. Resolve **§10.3 vs §16.5** in the final design text: **no legacy write migration**.  
3. Freeze **auto-close predicates** and **dashboard primary-status ranking** before any implementation of action closure.  
4. After user approval of the final design packet: execute **P1 mock-data interactive prototype** (new shell), then **P2 Job/DB**, then gates — do **not** start LangGraph or reviewer rewrite first.  
5. Keep this participant output advisory; Codex owns final design acceptance and all visual/browser authority.

---

**Role completion status:** complete conference pass for `general_grok45` (standalone report). No source edits performed. Ready for same-session Codex follow-up on D1–D4 or predicate-catalog depth if requested.
