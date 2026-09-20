Trellis SessionStart ✓ — Independent conference pass for `general_grok46`. Reading the assigned context packet and then auditing the cited domain contracts, catalog builders, and publication gates.Next I’ll audit the frozen contracts, procedure-catalog builder, and publication gates cited as sources of truth.## Conference report: `general_grok46`

**Verdict:** Reject the assumption that流程表 covers all enrollment controls. Keep three first-class catalogs; do **not** extend `required_procedures` or invent fake IN/EX. Highest-impact defect is origin XOR + two-catalog freeze, which currently has no place for prose obligations without corrupting numbering or visit-matrix semantics.

---

### ISSUES_ONLY

1. **I-01 (blocker, model):** `CatalogKind` / Agent input / gate only know `official_parent_rules` + `required_procedures`. Cross-section controls (禁/限用药、洗脱、合并治疗、疗效/安全阈值、评分标准、过程性限制等) have no first-class freeze identity. Stuffing them into either catalog violates current contracts.

2. **I-02 (blocker, false completeness):** `build_required_procedure_catalog()` only emits baseline-and-earlier ops from visit matrices with `X/(X)` marks; explicitly drops post-baseline columns and non-enrollment ops. Equating “流程表必做” with “全部额外入排控制点” is false against code.

3. **I-03 (blocker, origin XOR):** `EvidenceRequirement` / draft must bind to **exactly one** of `rule_component_id` | `procedure_catalog_item_id`. A third origin cannot publish without contract+gate change; ActionRequest design is also rule-component-centric.

4. **I-04 (high, identity trap):** `RuleKind.REQUIRED_PROCEDURE` + `REQ-\d{2}` exists, while semantic Agent wire only allows `IN|EX`. Expanding REQ- for prose controls, or minting synthetic EX/IN, both conflict with “preserve official IN/EX numbering” and with procedure-catalog visit instances.

5. **I-05 (high, discovery):** Keyword/section hit ≠ control point. Without structured **obligation morphology** (应做 / 达标条件 / 禁止事件·暴露) + named review stage + named time anchor + source closure, discovery will ingest treatment logistics, background PK/PD, result interpretation, and other-phase text.

6. **I-06 (high, merge):** Text-similarity merge across IN/EX, flow ops, and prose is unsafe. Current procedure dedupe is structural (`phase+root+stage+visit+row+col`), not label-based—control-point design must keep relation types `supplement | duplicate | conflict`, never silent merge.

7. **I-07 (high, UI/product):** Final design `WorkflowStage` is defined as flow-table-derived. Monitors cannot see how official IE, flow must-dos, and other protocol controls relate (补充/重复/冲突) unless UI has three lanes + cross-links.

8. **I-08 (medium, time anchors):** Unnamed/prose-only anchors (“筛选前充分洗脱”“用药前”) must **block publication**, not be guessed into `AnchorType`. Existing `TIME_BOUND_NOT_IN_SOURCE` pattern for half-life should generalize to control-point anchors.

9. **I-09 (medium, Phase 5.8 sequencing):** implement.md 5.8 is case/tester acceptance; DNF/real oMLX probe still open. Cross-section controls must be a **gated design→contract→builder→gate** slice before D001/MG clinical parity, not folded into “tester UAT”.

10. **I-10 (medium, authority):** Interpretation sources must remain non-authoritative for inventing controls; only protocol/amendment may mint/freeze control-point catalog members.

---

### EVIDENCE_LOCATORS

| Claim | Locator |
|---|---|
| Only two catalog kinds | `app/domain/contracts/enums.py` `CatalogKind` L310–314; docstring “两份目录” |
| Frozen item kinds XOR by catalog | `protocol_ingestion.py` `FrozenProtocolCatalog.validate_catalog` L269–282 |
| Agent input requires exactly those two catalogs | `agent_io.py` `ProtocolDeconstructionInput` L163–188 |
| Evidence origin XOR | `rules.py` `EvidenceRequirement.validate_requirement_origin` L262–267; `agent_io.py` L54–59 |
| Semantic rules IN/EX only | `agent_io.py` `SemanticRule.official_code` `^(IN\|EX)-\d{2}$` L128 |
| RuleSet also has REQ- | `rules.py` `Rule.official_code` / `RuleKind.REQUIRED_PROCEDURE` L281–315 |
| Procedure builder = tables + X/(X) + pre-baseline | `procedure_catalog.py` module docstring L1–14; `_table_looks_like_flow` L689–726; post-baseline skip L790–804; `_is_non_enrollment_operation` L429–452 |
| Structural not text dedupe | `procedure_catalog.py` L1130–1141; test `test_same_operation_at_screening_and_baseline_is_not_text_deduplicated` |
| Assembly freezes only parent + required | `deconstruction_service.py` L510–525 |
| Gate exact procedure coverage | `deconstruction_gate.py` `_workflow_coverage` `PROCEDURE_CATALOG_NOT_EXACTLY_COVERED` L2339–1357 |
| Design: WorkflowStage from flow table | `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md` §4.1 L100 |
| Design: gap separates procedure vs judgment vs anchor | same doc §5.3 L189–203 |
| Phase 5.8 stop conditions / no early tester | `.trellis/tasks/.../implement.md` §5.8 L94–100; checkpoint L124–145 |
| Project boundary: preserve IN/EX; separate judgment vs gap | workspace `AGENTS.md` Clinical boundaries |

---

### NO_ISSUE_SCOPE

- Procedure catalog’s deliberate exclusion of post-baseline / investigational dosing / visit logistics / post-dose AE rows is **correct** for enrollment scope; do not “fix” by broadening keyword inclusion.
- Exact visit-instance coverage gate for procedures is sound and should be mirrored for any third catalog.
- Conference must not act as tester; no code edits; no out-of-workspace clinical reads — respected.
- Official parent-rule freeze + semantic Agent only structuring frozen parents is the right pattern to copy for controls.

---

### RECOMMENDED_REPAIR

#### A. Domain model (three first-class catalogs)

| Catalog | Source of freeze | Stable identity | Obligation shape |
|---|---|---|---|
| `official_parent_rules` | Official IN/EX numbering | `official_code` | Rule expression tree |
| `required_procedures` | Visit matrix `X/(X)` | `phase+table+row+col+stage+visit` | “应做检查/操作” at visit |
| **`protocol_review_controls` (new)** | Deterministic candidate freeze from allowlisted sections/tables **excluding** pure IE lists and pure flow marks already owned | `control_point_id` from snapshot+span set+obligation_kind+stage — **not** text hash alone | Structured fields below |

Do **not** extend `required_procedures` to hold prose. Do **not** emit synthetic EX/IN. Prefer **not** overloading `RuleKind.REQUIRED_PROCEDURE`/`REQ-` for prose controls (reserve REQ for flow-origin or retire ambiguity in a later cleanup).

#### B. Minimal user-visible content of one formal control point

1. **审核节点** — `ReviewStage` (+ optional `visit_instance` only if protocol names a visit; else stage-only with explicit “无访视实例”)
2. **需执行/核对事项** — what to do or verify (procedure-like or chart review)
3. **达标条件** — positive predicate tree (may be empty if pure prohibition)
4. **禁止事件/暴露** — negative/prohibition tree (may be empty if pure must-do)
5. **时间窗与锚点** — `TimeConstraint` with **named** `AnchorType` or blocked as unresolved
6. **例外** — exception expression (same ALL/ANY/NOT discipline)
7. **证据要求** — min evidence types, due stage, objective-source flags
8. **来源定位** — ≥1 formal ALIGNED locator in allowed phase projection
9. **专业判断必要条件** — `requires_professional_judgment` + what judgment is required (not free text substitute for predicates)

Obligation morphology enum (do not collapse to one blob):  
`MUST_PERFORM` | `MUST_SATISFY` | `MUST_NOT_OCCUR` | `MIXED` (MIXED requires both non-empty condition and prohibition parts or gate fail).

#### C. Candidate discovery (deterministic first)

Allowlist section/table roles (例：合并用药/禁限用药、洗脱、伴随治疗、疗效与安全评价指标定义用于入排判定、筛选期限制性操作说明).  

Hard negatives (never auto-promote):
- Treatment-period ordinary ops already excluded by procedure builder
- Background disease/drug knowledge without enrollment duty
- Result interpretation / statistical analysis prose
- Other-phase projected-out spans
- Pure duplicates of frozen IN/EX parent spans (link as `duplicate`/`supplement`, don’t mint third copy as new authority)

Pipeline: **deterministic candidates → freeze catalog → Agent fills structure against frozen IDs only → human verify → publication gate**. Agent must not invent catalog members.

#### D. Cross-catalog relations

Graph edge: `(left_id, right_id, relation)` where relation ∈ `supplements | duplicates | conflicts`.  
- `duplicates`: same clinical duty, different wording/locations → single evaluation identity, multi-source display  
- `supplements`: flow lists ECG; prose adds QTc threshold → both remain, linked  
- `conflicts`: contradictory windows/thresholds → **blocks publication** until human disposition  

Never merge by cosine/similar text.

#### E. Publication gates (mirror procedure exactness)

- Exact coverage of frozen control-point catalog (order-stable)
- Source closure ⊆ allowed phase spans; amendment authoritative over Q&A
- Stage binding present; unnamed anchor → blocking unresolved
- No new official IN/EX codes; no control disguised as child of unrelated parent
- Cross-relation conflicts blocking
- Completeness: every published control answers fields 1–8 (9 if judgment flag)

#### F. Chinese monitor UI (product, not tester)

Three lanes: **官方入排 | 流程必做 | 其他方案控制点**.  
Each control shows 审核节点 / 应做·达标·禁止 / 时间锚点 / 证据 / 来源.  
Badge on related items: 补充 / 重复 / 冲突.  
Conflict items elevate to blocking gap, not silent green.

#### G. Phase 5.8 implementation order (incremental)

1. Contract enums + `FrozenCatalogItem` variant / new catalog kind + EvidenceRequirement third origin XOR→exactly-one-of-three  
2. Deterministic candidate builder + tests (fixtures only; no real protocol in conference)  
3. Agent IO: third frozen catalog; semantic fill mapped 1:1  
4. Gate coverage + conflict + unnamed-anchor blocks  
5. Authority/publication + ActionRequest origin for control points  
6. UI three-lane + relation badges  
7. Isolated D001 II + MG-K10-SAR III human parity matrix (IN/EX vs flow vs controls)  
8. Only then independent tester routes  

Stop if: inventing IN/EX numbers; keyword→formal without freeze; text-merge; guessing anchors; reading out-of-tree clinical files in conference/implement before Codex isolation harness.

---

### QUESTIONS_FOR_CODEX

1. **Q1:** Confirm third catalog name/kind (`protocol_review_controls` vs other) and whether `RuleKind.REQUIRED_PROCEDURE`/`REQ-` stays flow-only or is deprecated for this slice. *Matters for ID stability and UI labels.*  
   **Safe provisional:** new catalog kind; never mint IN/EX; keep REQ semantically = flow until explicit redesign.

2. **Q2:** For prose washout “距首次给药前 ≥X 个半衰期” with no explicit calendar anchor in text—block as `date_or_anchor_missing` at **rule publish**, or allow publish with runtime gap only? *Matters for gate strictness.*  
   **Safe provisional:** block publish if anchor not mappable to `AnchorType` + source-backed bound.

3. **Q3:** Should flow-table rows that are semantically prohibitions (rare) stay in `required_procedures` as must-perform marks, or migrate to control-points when prose restates them?  
   **Safe provisional:** keep matrix marks in procedures; link `supplements/duplicates` to prose control; do not delete procedure item.

4. **Q4:** Is Phase 5.8 slice for this conference a **design approval + implement.md amendment**, or an immediate code slice after chair synthesis?  
   **Safe provisional:** chair synthesis → amend task artifacts → contract-first slice; no tester until D001/MG matrix.

---

### RESIDUAL_RISK

- Without real D001/MG in this pass, section-allowlist recall/precision unknown; false negatives on oddly titled chapters remain.  
- `MIXED` obligation items may push Agent to free-text; schema must force split trees.  
- Cross-relation Agent labeling of supplement vs duplicate is semantic—needs human confirm before non-blocking duplicate collapse.  
- Expanding EvidenceRequirement origins touches Profile expectations / ActionRequest; regression surface is large—needs focused contract tests before UI.  
- Final visual/browser and clinical acceptance remain Codex-owned.

---

### Active peer: highest-impact objection

**Do not “extend `required_procedures`.”** That catalog’s identity, gate, and builder are visit-matrix enrollment ops. Putting禁用药/洗脱/阈值 prose into it either (a) invents fake visits, or (b) drops visit requirements and breaks `PROCEDURE_VISIT_INSTANCE_MISMATCH` semantics. The only coherent fix is a **third frozen catalog** with obligation morphology and cross-links, copying the parent-rule pattern: freeze IDs first, Agent structures second, exact coverage gate third.

**Challenged acceptance gaps in the conference success criteria / plan:**
- Plan says prove against code that “流程表 ≠ 全部额外控制点” — **confirmed by builder**.  
- Success criteria demand three obligation forms — **current `FrozenCatalogItem` only has `label`+visit; insufficient**; new item schema required.  
- Plan checklist forbids disguising controls as EX/IN — good; also forbid disguising as `REQ-` without chair decision.  
- Missing AC: explicit negative tests that keyword-only candidates never publish; unnamed anchors block; text-similar IE+prose yield `duplicates` relation not one merged rule.

---

### Draft output plan (for chair synthesis)

1. Chair adopts three-catalog model + field list above.  
2. Amend Phase 5 implement slice checklist with contract→builder→gate→UI→D001/MG order and stop conditions.  
3. Fixture-only deterministic tests before any real protocol.  
4. Codex-owned isolated D001/MG human matrix; conference advice ≠ acceptance.

**Verification needs (Codex, not this role):** contract unit tests; gate issue codes; fixture matrices for supplement/duplicate/conflict; later isolated real-protocol parity—not browser UAT by conference.

**Role health:** primary `cursor`/`cursor-cli`/`auto` completed independent pass; no fallback used; no other participant outputs read; no workspace writes; no out-of-tree clinical reads.
