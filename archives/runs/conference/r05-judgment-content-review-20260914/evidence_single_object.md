我先按会议角色做只读审阅：读取指定上下文与计划，再核对书面判定内容链与可并入正式计算的最小安全路径。不会写入 runner 报告路径。上下文已读到：这是只读审阅书面判定内容链。接下来按 Source of Truth 核对合同、生产者、回执与正式计算消费路径。CAO 记忆无命中。接下来只读 Source of Truth 与相邻合同，不读 worker 报告。合同与生产者已读完。接下来核对资格核验相邻模块、设计合同第 17 节，以及正式计算如何消费这些结果。核心链路已定位。接下来对照资格核验实现、§17.2 合同，以及正式计算当前如何消费书面判断。证据已够写完整审阅：最高风险是资格核验与内容核实共用一次模型调用，以及控制族检索会阻断谓词内容作业。开始汇总独立结论。# Conference Output: r05-judgment-content-review-20260914 - evidence_single_object

## Output

**Fallback (explicit):** Primary `zcode` / `GLM-5.3` was unavailable before a resumable session existed. This pass ran as Codex-declared `grok` fallback `grok-build` / `grok-4.6`. I did not switch routes inside the session. Capability limits: no Python/app execution, no tests, no DB, no browser, no internet, no production paths, no worker-report evidence, no clinical/regulatory/visual acceptance. Runtime behavior of JobRunner, 429/length retry, and mixed official/control review contexts is inferred from source, not observed.

**Role:** `evidence_single_object` (重要证据审阅), serial Codex-led panel. Advisory only. Codex remains final authority.

---

### 1. Highest-impact finding (do not share one model call)

**Recommendation:** Qualification and written-judgment **content must not share one model request**. Share frozen **input material only** (already done via `BindingQualificationPairContext`). Keep separate prompts, output schemas, agreement keys, dual-lane comparisons, receipts, prompt versions, and method-approval identities.

**Evidence (not inference):**

| Axis | Qualification (6 source dimensions) | Content (5 fidelity dimensions) |
|---|---|---|
| Schema | `source_admissibility`, `object_match`, `attribute_match`, `denial_scope`, `temporal_role`, `direct_operand_usable` — `app/domain/contracts/binding_qualification.py:162-201` | `explicit_written_judgment`, `investigator_attribution`, `target_correspondence`, `node_correspondence`, `encoded_value_fidelity` — `app/domain/contracts/judgment_content.py:12-25` |
| Prompt/version | `binding-qualification/v2` — `app/llm/binding_qualification.py:27,152-175` | `judgment-content/v1` — `app/llm/judgment_content.py:13-41` |
| Pair scope | **All** completed candidate pairs (value / date_range / record_time / assertion_basis; predicate **and** control families) — `binding_qualification.py:60-66` | **Subset:** `family==predicate`, `fact_attribute=="value"`, unique excerpt→fact match, explicit `predicate_id` + `source_policies.requirement_id` — `judgment_content_input.py:15-36` |
| Method identity | `EvaluatedBindingMethod` has only `qualification_*` fields; `evaluation_kind` is `Literal["binding_semantic_correspondence"]` — `review_method_adoption.py:24-37,64-66` | No content contract/prompt/route slots exist |
| Formal consumer | PJ predicates are **excluded** from fact selection: `investigator_judgment_not_deterministic_value` — `qualified_binding_selection.py:179-180` | **No consumer.** `frozen_review_calculation.py` / `frozen_review_publication.py` have zero `judgment_content` references. Found excerpts stay `OBSERVATION_UNVERIFIED` via `CANDIDATES_PRESENT` — `eligibility_review_projection.py:445-446` |

**Why a shared call loses separate evidence:**

1. **Scope mismatch is structural, not an optimization.** Merging forces either content dimensions on non-judgment pairs, or qualification-only-on-judgment-pairs (dropping the rest of the binding universe).
2. **Agreement keys are different clinical questions.** `object_match=supported` is “this fact/locator binds this predicate.” `explicit_written_judgment=supported` is “an investigator wrote a judgment.” Collapsing them into one 11-tuple means disagreement on either retries/fails both, and a consumer cannot prove which check ran.
3. **One request = one receipt chain.** `_verify_call_sequence` (`judgment_content_receipts.py:39-78`) proves *this* prompt, budget, and retry order. A shared receipt cannot later prove content fidelity independently of source qualification.
4. **Method approval cannot reuse qualification gold.** `require_evaluated_binding_method` binds `qualification_contract`, `qualification_prompt_version`, `qualification_routes` (`review_method_evidence.py:13-24`). Content would inherit a semantic-correspondence evaluation it never sat.
5. **§17.2 requires both source *and* content.** “对象、节点及来源符合要求，确认原文判断内容.” Content schema has target/node, **not** `source_admissibility`. Qualification produces source admissibility but the PJ consumer throws it away. Integration needs **both verified summaries**, not one super-JSON.

**Cost that is source-evidenced vs speculative:**

- **Evidenced duplication:** two isolated dual-lane jobs; content re-sends full excerpts (`plan_judgment_content_batches` sizes with actual `build_judgment_content_messages`, no truncation — `judgment_content_receipts.py:81-134`); overlapping value-pairs are paid twice, once per schema.
- **Not evidenced:** wall-clock or token savings from merging. No timing, trace, or token ledger is in the authorized source list. Do not invent gains.

**Safe sharing (already present, keep):** reuse pair identity, frozen facts/locators/conditions, and `binding_qualification_prompt_payload` **as input projection** (`judgment_content.py:16`). That is input dedup, not output conflation. Peer `lane_declarations` stay out of the prompt (`binding_qualification.py:94`).

---

### 2. Findings by severity

#### High

**H1. Mixed-family search freeze can abort the entire predicate content input.**  
`assemble_review_context` freezes **all** `latest_entries_for_authority` searches (`review_context_assembly.py:59-90`). That repository is per `requirement_id` with no official/control split (`judgment_search_repository.py:151-189`). `load_prepared_judgment_links` then links **every** `context.judgment_search_results` against `PredicateBindingFrozenInput` (`judgment_fact_linkage.py:34-38,52-56`). If a control search’s `requirement_id` is not uniquely in predicate `evidence_requirements`, it raises `判断摘录未对应到本次审核唯一的资料要求` and **blocks the whole job**, including official excerpts that did match.  
T5/§17.3 require official and control on the same review. This is not a hypothetical edge; it is the product’s intended context shape.  
**Remediation:** filter searches to requirement IDs that uniquely exist in the consumed frozen family; record out-of-family rows in `excerpt_coverage` (do not raise, do not guess-link). Keep the existing hard reject of `family != "predicate"` at enqueue (`judgment_content_input.py:15-16`).

**H2. No path from content_supported to formal calculation; the dangerous mappings are the ones a later wire-up will reach for.**  
Today: search `CANDIDATES_PRESENT` → `GapType.OBSERVATION_UNVERIFIED` (`eligibility_review_projection.py:445-446`). Missing judgment is **only** `ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE` plus empty selections plus explicit `predicate_ids` (`judgment_gap_selection.py:34-39`; §17.2). Content job flags are forced `accepted=False` / `authorized_clinical_adoption=False` / `clinically_qualified=False` on checkpoints, artifacts, summary, and verify (`judgment_content_job.py:236-241,308-310`; `judgment_content_receipts.py:217-219,416-418`). Executor is **not** in `default_executors` (`app/api/v2/app.py:279-322`).  
**Inference:** isolated producer is correctly inert.  
**Consumer traps to forbid:**

| Producer status | Must not become | Must remain |
|---|---|---|
| `content_supported` | eligibility truth / deterministic `predicate_fact_ids` | authorized “verified written-judgment observation,” then scheme-semantic evaluation |
| `content_rejected` (e.g. only `encoded_value_fidelity=rejected`) | “missing written judgment” | found-but-unfaithful; keep unverified; do not use the stored value |
| `disagreement` / `unresolved` | either missing or verified | `OBSERVATION_UNVERIFIED` |
| empty selected pairs / `empty_selection_notes` | missing-judgment UNKNOWN | coverage retained, no PJ claim (`judgment_content_receipts.py:212-216`) |
| `no_source_match` / `ambiguous_source_match` | missing judgment | still “found excerpt, not verified” |

`compare_judgment_content` collapses a pair to `content_rejected` if **any** of the five dimensions is `rejected` once lanes agree (`judgment_content_comparison.py:27-34`). That is a polarity/encoding failure, not absence.

**H3. `quoted_evidence` is a one-character substring check.**  
`validate_judgment_content_payload`: `item.quoted_evidence not in excerpt` (`judgment_content.py:51-53`); `quoted_evidence` `min_length=1` (`judgment_content.py:19`). A quote `"临"` or `"N"` inside `"无临床意义"` / `"NCS"` passes. Dual-lane agreement on structured keys is the only remaining check; quote-in-excerpt does not prove investigator judgment, object, or polarity.  
**Remediation (minimal):** require quote length floor and that the quote is a contiguous span of **that pair’s** locator excerpt (already pair-scoped); still do not treat quote presence as clinical truth. Do not allow quoting another pair’s locator (already rejected).

**H4. Upstream candidate receipts are weaker than the formal qualification consumer.**  
`load_judgment_content_input` → `load_completed_candidate_qualification_input(...)` **without** `require_route_receipts=True` (`judgment_content_input.py:12`). Qualification enqueue is the same (`binding_qualification.py:60-62`), but `publish_review_from_qualified_jobs` verifies with `require_candidate_route_receipts=True` (`qualified_review_command.py:79-80`). Content’s own lanes *are* strictly sequenced (`_verify_call_sequence`). The hole is **candidate** provenance if this job is later consumed.  
**Remediation:** pass `require_route_receipts=True` at both enqueue rebuild and `verify_completed_judgment_content` before any formal wire.

#### Medium

**M1. Dead `require_route_receipts` on content reconstruct; missing artifact `comparison_sha256` check.**  
`verify_completed_judgment_content` passes `require_route_receipts=True` (`judgment_content_receipts.py:386`) but `_reconstruct_judgment_content_lane_state` never reads the flag (`228-237`). Functionally, empty receipts already fail (`285-286`) and every receipt’s `route_identity` is checked (`52-54`). Unlike qualification reconstruct (`binding_qualification_support.py:897-904`), content reconstruct does **not** check `artifact["comparison_sha256"] == payload["comparison_sha256"]`. Lane checkpoints’ `clinically_qualified` / `authorized_clinical_adoption` are also not checked (only artifact + summary).  
**Remediation:** copy qualification’s artifact comparison-hash check; either delete the dead parameter or use it. Check checkpoint clinical flags the same way as summary.

**M2. Top-level `comparison_sha256` is the *candidate* comparison, not content dual-lane comparison.**  
Summary copies `payload["comparison_sha256"]` (`judgment_content_receipts.py:204`). Batch-level content hashes live under `comparisons[].comparison_sha256`. A consumer that keys “the” comparison hash will bind the wrong object.  
**Remediation:** name the field `candidate_comparison_sha256` in any new consumer contract; never treat summary-level `comparison_sha256` as content agreement.

**M3. `unresolved_excerpt_coverage` means “not sent to a model,” not “content failed.”**  
`judgment_content_receipts.py:192-195`: ready if `content_check_ready` and pair_ids intersect selected pairs. Dual-lane `disagreement` still counts as coverage-resolved. Consumers must read `comparisons[].records[].status`.

**M4. Incomplete search + unique match still content-checks the found excerpt.**  
`link_judgment_excerpts` walks `found_candidates` only (good: `ambiguous_channels` tentative excerpts are not promoted — matches `judgment_search.py:386-387`). It does **not** look at summary `status`. A `coverage_incomplete` search can still unique-match and be checked. That is acceptable as excerpt-level evidence; it is **not** requirement-complete. Formal consumption must not treat one `content_supported` pair as closing the requirement.

**M5. Multiple unique matches are all selected; there is no observation policy.**  
Producer behavior is correct (do not pick first/latest — §17.1 / T5). `qualified_binding_selection.py:185-186` already refuses `multiple_usable_pairs_without_selection_policy` for ordinary predicates. Content has no analogue. Two unique-matched value facts for one PJ predicate would both be content-checked and both sit in `selected_pair_ids`.  
**Remediation:** keep all; consumer stays unresolved until an **approved, source-backed** observation policy exists. Do not default ANY/ALL/latest.

#### Low / hygiene

**L1. Reconstructed `JudgmentContentRead` zeros `completions` and `budgets` (`judgment_content_receipts.py:309-310`).** Comparison does not use them; receipts do. Fine if consumers never read those fields from verify output.

**L2. `validate_judgment_content_payload` does not take `batch` (unlike qualification).** Relies on caller passing `batch_pairs`. Current compose/reconstruct filter correctly (`181, 248`).

**L3. Control family hard-fail is correct isolation, not a product close.** T5 still needs a control content path. Do not “fix” this by empty-success.

**L4. Not registered** is consistent with qualification isolation. Not a defect until evaluation + approval exist.

**L5. Exact excerpt string match** (`judgment_fact_linkage.py:70-75`) fail-closes OCR drift into `no_source_match`. That must not be reported as missing judgment; it stays “found, unmatched.”

---

### 3. Producer/receipt chain (what holds)

Trace against the assigned checklist:

| Concern | Source | Verdict |
|---|---|---|
| Frozen source/excerpt identity | `assertion_basis` must match locator id, object, `source_text_sha256`, `assertion_text==excerpt`; match key is `(doc, page_artifact, page, excerpt)` — `judgment_fact_linkage.py:59-75` | Holds. Match ≠ authorship ≠ truth (docstring 46-48). |
| Dedup | `selected[pair.pair_id]` (`judgment_content_input.py:35`); batch fields sorted unique (`binding_qualification.py:152-155`) | Holds for pairs. Coverage rows are per excerpt, not per pair. |
| Pair scoping | Same frozen + candidate job (`receipts.py:91-94`); prompt payload requires `sorted(indexed)==batch.pair_ids` | Holds. |
| JSON persistence | Artifacts via canonical `json.dumps`; payload hash idempotency (`job.py:97`); verify rebuilds summary equality (`receipts.py:395-396`) | Holds at source level. |
| Calls/receipts | Full 429/length sequence, not last receipt (`receipts.py:39-78`); aligned with `read_candidate_payload` (`predicate_binding_candidates.py:274-300`) | Holds in source. **Unverified at runtime.** |
| Cancellation/retry | `run_cancellable`; incomplete ≠ `unverified`; verify requires completed + last checkpoint `unverified` | Fail-closed. Last checkpoint is latest by `created_at` (`jobstore.py:311-327`). |
| Route/resource | Two lanes, distinct models at compare (`comparison.py:18-19`), 65536–131072 tokens, local parallel cap (`job.py:54-57,113-117`) | Holds. |
| Clinical flags | Forced false end-to-end | Holds. |
| Empty selection | Summary-only job; no missing-judgment claim | Holds. |
| Registration / adoption | Absent | Intended isolation. |

Do **not** assume reused qualification code is correct: content reconstruct is a stricter retry replay than qualification’s last-receipt path, but **weaker** on artifact `comparison_sha256` and upstream candidate route receipts (M1, H4).

---

### 4. Minimal safe integration sequence

Smallest producer→consumer path that does not conflate dimensions or skip authorization:

1. **Keep two jobs.** Content remains `purpose=isolated_written_judgment_content_check`. Do not merge prompts.
2. **Fix H1** (family filter on searches) and **H4** (candidate `require_route_receipts=True` on verify) before any consumer.
3. **New evaluation kind**, e.g. `written_judgment_content_fidelity`, with its own contract `judgment-content-job/v1`, prompt `judgment-content/v1`, dual routes, gold split, and scoring report. Do not extend `binding_semantic_correspondence` or reuse qualification approval.
4. **New consumer** (do not overload `qualified_binding_selection`):
   - Input: `verify_completed_judgment_content` **and** (for source policy) the qualification summary’s `source_admissibility` / structural checks on the **same pair_id**, as separate records.
   - Require recorded `ReviewMethodApproval` that names the content method; `clinical_case_signoff` stays false.
   - `content_supported` + unique match + explicit predicate attribution + current-node search coverage **for that excerpt** → “verified written-judgment observation.” Still **not** IE truth (`encoded_value_fidelity` ≠ 符合标准 — `judgment_content.py:34`).
   - Multiple supported observations → unresolved until an approved observation policy exists.
   - Never write `content_supported` into PJ `predicate_fact_ids` as a deterministic value (`qualified_binding_selection.py:179-180` must stay).
5. **Leave missing-judgment production on the search path** (`missing_judgment_predicates` + `ALL_SUPPLIED_PAGES_...`). Content empty/unlinked/rejected must not enter that set.
6. **Register executor and HTTP only after** isolated evaluation + user method approval + the consumer above. Same rule as qualification (`qualified_review_command.py` is unregistered).
7. **Control family:** keep the hard reject; ship a separate control content job later against control frozen input, not by relaxing predicate linkage.

This can finish as a **review** once Codex decides H1 filter vs raise, shared-call ban, and consumer mapping. Implementation and runtime proof are out of this conference pass.

---

### 5. Clinical requirement check (source-level only)

| Requirement | Source evidence | Status |
|---|---|---|
| Missing investigator judgment is reported, not user reconfirmation | Search path + §16/§17.2; content empty path explicitly avoids the claim | Producer does not regress this **if** consumers do not misuse empty jobs |
| Found content is not eligibility truth | Flags false; no calc wire | Holds while isolated |
| No new fact construction / disease shortcuts | Prompt forbids creating facts/dates; model-neutral | Holds in prompt contract; **clinical correctness unproven** |
| Full source/node/object applicability + recorded authorization before positive consumption | Content has node/target, not source_admissibility; no approval slot | **Not met** for positive consumption — correctly blocked today |
| Positive written judgments and multiple observations, not permanent unknown-only | Search-found stays unverified forever until a consumer exists | **Product gap** (T5). Isolation prevents the worse bug (auto-true). |

---

### 6. Assumptions challenged

1. **“Reuse qualification pairs, so reuse the qualification call.”** False. Input reuse is already done; output dimensions, scope, and approval identity diverge.
2. **“Dual-lane content_supported is enough to enter `calculate_component_review` as a fact.”** False. PJ is excluded from deterministic selection; §17.2 still requires scheme-semantic evaluation after content confirmation.
3. **“Empty content job means the judgment is missing.”** False. Empty means no unique-matched **value** pair. Search-not-found is a different receipt chain (`professional_judgment_absence_proven` is even locked `False` on the search summary — `judgment_search.py:400`).
4. **“Qualification dual-agreement should gate content enqueue.”** I challenge this. Qualification consumer ignores PJ pairs; content must still run on unique-matched value pairs. Gate **consumption** on both summaries, not enqueue.
5. **The main-venue plan file is still TODO stubs** (`plans/codex_main_venue_r05-judgment-content-review-20260914.md`). This pass used the conference context + source list, not that plan, as source of truth.

---

### 7. Evidence / inference / recommendation / uncertainty

- **Evidence:** file:line citations above; design §17.2 table (`docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md:334-341`); T5 remaining work (`plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md:107-111`).
- **Inference:** mixed official/control contexts will hit H1 in real reviews; substring quotes will over-accept weak spans; a hurried consumer will map `content_rejected` → missing or `content_supported` → eligible.
- **Recommendation:** ban shared calls; filter H1; keep content isolated until a new evaluation kind + dual-summary consumer exist; do not register.
- **Uncertainty:** runtime retry/cancel; whether current projects already store control searches on the same episode; quote-length policy; whether Codex wants source_admissibility AND-ed at consumption. No tests were run (forbidden). CAO memory search returned no hits.

---

### 8. Objections, proposed solutions, Codex decision points, bounded questions

**Objections**

- Sharing one call to “save a round-trip” destroys the only receipt proof that content fidelity was asked independently of source qualification, and the method-adoption contract has no place to record that hybrid.
- Wiring content into `qualified_binding_selection` would either keep PJ as permanent unknown (no product progress) or treat encoded values as deterministic operands (clinical defect).
- Treating `quoted_evidence in excerpt` as provenance is weaker than the search pipeline’s refusal to promote `ambiguous_channels`.

**Proposed solutions**

- Two jobs, two agreement keys, two evaluation kinds, one frozen pair identity.
- Family-filter coverage rows for out-of-scope searches.
- Consumer matrix in H2 as a hard contract before any `frozen_review_calculation` edit.
- Strengthen quote validation without turning it into eligibility.

**Decision points for Codex (not claimed here)**

1. Confirm **ban** on shared qualification/content completion calls (this review’s default).
2. H1: **skip+record** out-of-family searches vs keep raise (raise is safer for a single-family fixture, unsafe for T5 mixed contexts).
3. At consumption, AND content five-key agreement with qualification `source_admissibility` on the same `pair_id`, or treat content as sufficient for node/target only.
4. Quote policy: length floor only vs require quote == full locator excerpt vs keep substring and rely on dual-lane keys.

**Bounded questions**

1. May a later consumer AND `source_admissibility=admissible` (qualification) with `agreement_key` all `supported` (content) on the same `pair_id` without a new evaluation that scores that conjunction? **Why it matters:** §17.2 lists 来源 and 内容 together; today’s approval object cannot name the conjunction. **Provisional path:** consume the two summaries as separate proofs; do not invent a combined score; do not enable publication.
2. For H1, is skip+coverage the accepted repair, or must content jobs be scoped to a declared requirement-id list at enqueue? **Why it matters:** skip preserves official excerpts; a declared list changes the job payload identity. **Provisional path:** fail closed on mixed unfiltered contexts until Codex picks; do not guess-link control requirement IDs onto predicate facts.
3. Is any positive `content_supported` consumption in scope for the next implementation packet, or is this review allowed to conclude “producer isolated, consumer forbidden”? **Why it matters:** T5 asks for semantic verification of found judgments; isolation alone leaves permanent unknown. **Provisional path:** review can finish on source evidence; positive consumption stays unauthorized.

**Resume point if follow-up is needed:** H1 family-filter design, quote-validation floor, and the exact consumer module boundary (new file vs `frozen_review_calculation.py` gap hook). Do not start implementation in this conference role.

**Not claimed:** clinical PASS, runtime PASS, visual/browser PASS, method approval, or final Codex acceptance.
