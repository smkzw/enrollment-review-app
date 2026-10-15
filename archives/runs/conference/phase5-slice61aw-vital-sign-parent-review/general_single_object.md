Confirmed. **Attempt 1 (af91ad79)** explicitly said: "保留动作不等于把其完成强度改为必做。不得仅因动作属于建议、尽力遵循，或只读上下文出现相似表述，就降为普通说明或无控制处置；若既有流程目录未完整覆盖，必须建立补充控制候选". This is the project's contract — but it CONFLICTS with the system prompt rule for `post_treatment_execution`. Both v1 worker_03 and the project's contract argue against the v2 escalation to `screening` review node for p786.

I have enough to produce the independent review. Let me draft the report.

# Conference Participant Output: phase5-slice61aw-vital-sign-parent-review - general_single_object

## Boundary Check

- **Read-only scope**: verified. No source/protocol/clinical material outside the workspace was opened. Only workspace files read: `context/...`, `plans/...`, `.trellis/...`, `artifacts/phase5-slice61av...`, `artifacts/phase5-slice61aw...`, `artifacts/phase5-slice59i...` paths referenced via the config, and prior slice `slice61as-ecg-source-closure-parent-checklist.md`. No live MTPLX call, no file mutation, no git write.
- **Conference context and Codex main-venue plan were both TODO stubs** (`source-of-truth: TODO`, `task decomposition: TODO`). This review reconstructs the source-of-truth from `.trellis/tasks/08-22-phase5-clinical-facts-profile/{implement.md, configs/*, research/...}` and `artifacts/phase5-slice61{av,aw}-*` plus the sibling ECG closure checklist at `.trellis/.../slice61as-ecg-source-closure-parent-checklist.md`. Reviewer flag: the boundary guidance itself was missing — a defect for the runner, not for the audit subject.
- **Linked execution task**: `phase5-slice61av-vital-sign-modality-contract` (status `linked`, evidence present). Two artifacts under that link: `phase5-slice61av-d001-vital-sign-modality-20260829` (worker_03, 1 attempt, 0 candidates, gate accepted) and `phase5-slice61aw-d001-vital-sign-modality-repair-20260829` (codex-parent, 3 attempts, 2 candidates / 2 controls, gate accepted). Both `claims_complete=false`.

## Independent Work Product

### 1. What was actually shipped in slice61aw

Configuration delta: `representative_group_vital_sign_modality.v2.json` is a 9-line `extends` shim on v1 — it only changes `group_id`, `task_id`, `worker`, `artifact_dir_name`. All binding (owned/attached refs, modality expectations, dispositions, IDs, prompts) was inherited from v1. The `extends` mechanism does not introduce a new source set; the freeze provenance confirms this (`frozen_plan_sha256` and `coverage_manifest_sha256` identical to v1).

What is new in v2 is the **model output** under three attempts in the same MTPLX session `protocol-control-chat-3c8b429aedca4798b8856bb5801c51f3`:

| Attempt | Outcome | Candidates | Control count | Critical issue |
|---|---|---|---|---|
| 1 (af91ad79…) | publication_invalid | 0 | 0 | REQUIRED_ACTION_DISCARDED on `su-7a42e55b3912ac26c66747a5=sequence_before_related_procedure` |
| 2 (3127152a…) | schema_invalid | 0 | 0 | candidate_drafts.1.cross_source_relations.0 missing `affected_workflow_stage_id` |
| 3 (30938424…) | parsed | 2 | 2 | accepted |

Final published controls:

- **p785** → `pcc-e21cbe27dc79d16b7615a64d` — `kind: complete_or_verify`, `modality: recommended`, single atom (rest ≥5 min), review node `flow-screening` `decide_at_node`. `obligation_combination: "all"`. **Cross-source relation `further_explanation` to `pcm-row-aee90bcadab30a320c395d48` (流程必做生命体征)**.
- **p786** → `pcc-1a789f85bbf2f82094e76a70` — `kind: complete_or_verify`, `modality: best_effort`, single atom (尽量在PK前完成), **trigger branch `pct-42d58b36b05b849477441ae6` ("生命体征检查与PK采样时间一致")**, review node `flow-screening` `decide_at_node`. `obligation_combination: "all"`. Cross-source relation `supplementary_requirement` to the same procedure row.

Disposition for `body.p784` (章节标题) is `supporting_or_supplement` — non-candidate. EX-21 is only attached for read-only context (no candidate directly tied to it).

### 2. P785 correctness — clean

- Original Chinese "测量前，**建议**参与者至少休息5分钟" → modality `recommended` is the right projection. Mandatory → recommended is not an escalation.
- Four-component list is fully present as a control context (血压、脉博、体温、呼吸频率), each with units preserved (`mmHg`, `次/分`, `℃`).
- `due_stage: "screening"` matches the v1 config note "当前冻结来源适用于Ⅱ期筛选和基线入排审核".
- No `time_constraint`; `applicability_expression: null`; `trigger_expression: null` — no spurious clinical qualifier.
- No double-publication of the procedure row: the cross-source relation is `further_explanation`, not a duplicate candidate.

### 3. P786 — the high-impact defect

This is the single most important finding of this audit. Three independent lines of evidence converge on the same defect:

**a) The system prompt's own phase-binding rule forbids binding this atom to a screening review node.** The prompt body explicitly says (line 3, reproduced verbatim from `prompt.txt`):

> "首次给药后或治疗期内才执行、且不影响筛选/基线入排判定的检查或随访，应处置为 `post_treatment_execution`，**不得绑定到筛选或基线审核节点**。"

The trigger is "生命体征检查与PK采样时间一致" — this trigger can only fire after the first dose, since PK sampling is part of post-dose pharmacokinetic sampling. v1 worker_03's `disposition.notes` on the same unit said precisely: "其触发条件（生命体征检查与PK采样时间一致）为治疗期给药后场景，不影响筛选/基线入排判定". v2 promotes the same unit to a screening-bound `decide_at_node` control. This is a self-contradicting escalation.

**b) Attempt 1's rejection message encodes the project contract incorrectly relative to the prompt rule.** Attempt 1 rejected with: "保留动作不等于把其完成强度改为必做。不得仅因动作属于建议、尽力遵循，或只读上下文出现相似表述，就降为普通说明或无控制处置；若既有流程目录未完整覆盖，必须建立补充控制候选". This is a hard rule that any `best_effort`/recommended/policy instruction with no procedure-row coverage MUST be a control. But it does NOT say that the new control must bind to `flow-screening`. The v2 attempt 1 dropped `affected_workflow_stage_id` from `cross_source_relations[0]`, which triggered `WIRE_SCHEMA_INVALID` at attempt 2. Attempt 3 fixed the schema by inserting `"affected_workflow_stage_id":"flow-screening"`. That is a schema-compliance fix, not a clinical-reasoning fix — the model's choice of `flow-screening` for a post-trigger PK-time control is not derived from the source text; it is the closest schema-valid value in the menu, not a correct one.

**c) `kind: complete_or_verify` + `modality: best_effort` + `role: decide_at_node` on a `flow-screening` stage is incoherent.** "Complete or verify" implies the agent is going to assess whether the action occurred. "best_effort" means the action is non-binding. `decide_at_node` means the screener is being asked to make a binding decision at screening. These three facets together tell the screening operator "decide whether the participant has made a best-effort attempt to sequence vital signs before PK", which is impossible — at screening there is no PK sampling in play.

### 4. Mandatory/recommended/best_effort modality coverage

- `mandatory` is absent from the published controls because p784–p786 contains no mandatory language ("建议"/"尽量" only). The mandatory layer for this chapter is fully delegated to `body.t5.r10` (flow row with `X` / `(X)`) which is correctly marked `attached` and not republished.
- `recommended` is exercised exactly once (p785 atom).
- `best_effort` is exercised exactly once (p786 atom), but its review-node binding is wrong (see §3).
- All three modalities would be represented in the run; only the p786 binding is mis-located.

### 5. EX-21 (body.p684) handling — read-only and correctly kept read-only

- EX-21 is attached via `frozen_plan_owned` lookup with full rule label "检查异常、临床意义与不可接受风险", `official_code: "EX-21"`, `position: 27`, single source span.
- No candidate references EX-21 in `cross_source_relations`; no disposition attempts to convert the AND-clause ("异常且有临床意义且经研究者评估参与研究将构成不可接受风险") into an inline control. The triple-conjunction independence is preserved — the EX-21 conjunction is not weakened into OR, the professional-judgment clause is not dropped, and there is no re-promotion of vital-sign operational data into an exclusion rule.
- This satisfies the slice61as ECG parent checklist's analogous requirement ("EX-21 中心电图分支是否严格保持三项合取") at the text-binding level.

### 6. p321 / p885 attached-context — not republished

- `body.p321` (procedure list "筛选期、D1/D15/D29/D57/D85（当天用药前）、D113或提前退出时…建议静息至少5分钟") is `attached` via `frozen_plan_context` lookup. Final candidates do not duplicate its content; p321 is referenced only as a context anchor, not a candidate source. Correct — the procedure-row coverage is left to `body.t5.r10`.
- `body.p885` (D1给药前结果作为基线值…基线需再次审查入选和排除标准…) is `attached` via `frozen_plan_context`, `unit_kind: footnote_or_annotation`. Not republished. Correct.
- The package_ordinal drift (v1 used package31/55/55; v2 source_rows shows 67/69/69) is a real source-side drift, but the structure_unit_ids in the owned list (`su-391ac4874f8f0692ccbc3442`, `su-3edde2080d78436042ca1f50`, `su-7a42e55b3912ac26c66747a5`) match v1 byte-for-byte, and the SHA-256 of the protocol DOCX is identical (`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`). The drift is in the package layer, not in the unit or span layer.

### 7. Three-attempt model-free replay budget semantics

- `transport_call_count: 3`, `attempt_outcomes: ["publication_invalid","schema_invalid","parsed"]`.
- Serial repair budget: per project memory ("serial repair budget ≤2 (1+1 schema), separate transport budget, no retry after uncertain timeout"), attempt 3 is the **schema repair** (1+1). This is consistent.
- Two distinct failure classes were repaired (publication, schema) — not a third repetition of the same class. Budget rule respected.

### 8. Dual-gate (release/clinical-rejection) semantics

- `gate-results.json` shows publication gate accepted (0 issues).
- `clinical-qc.json` shows `clinical_gate_accepted: true` and `parent_clinical_acceptance: "pending_codex"`. The second gate is **`pending_codex`**, not accepted. Per the previous slice61at ECG checkpoint model (`CHECKPOINT_20260829_D001_ECG_CONTROL_ACCEPTED_ACTION_CONTRACT_FIXED.md`), the parent clinical gate is the gate that closes the dual-gate pair. This is **not** closed in slice61aw's artifacts.
- `structured_control_deconstruction_accepted` flips from `false` (v1) → `true` (v2). This is a real semantic gate state change but it is downstream of the parent clinical acceptance.

## Evidence And Assumptions

**Evidence (file paths, line ranges, hashes):**

- v1 (slice61av) gate accepted with 0 candidates/0 controls. Runner outcome: 1 attempt parsed, 3 dispositions all `supporting_or_supplement`. `artifacts/phase5-slice61av-d001-vital-sign-modality-20260829/gate-results.json` (lines 1–7), `execution/runner-result.json:11–110` (dispositions 14–42; final 67–110).
- v2 (slice61aw) gate accepted with 2 candidates / 2 controls. `artifacts/phase5-slice61aw-d001-vital-sign-modality-repair-20260829/gate-results.json:1–7`, `execution/runner-result.json:1–322` (attempt 1: 5–23; attempt 2: 25–42; attempt 3: 43–322), `execution/transport-calls.json` (3 calls, elapsed 159.0 + 53.6 + 256.5 = 469.2s ≈ `replay-summary.json:elapsed_seconds: 469.17`).
- Raw response SHA-256 list: `[af91ad79…, 3127152a…, 30938424…]` (`clinical-qc.json:37–41`). All three are stored verbatim in `execution/raw-responses.json`. The first response was kept (attempt 1 → rejected at publication gate). The second was kept (rejected at wire schema). The third was accepted.
- v2 prompt source text for p785 = `生命体征检查包括坐位血压（收缩压和舒张压）（mmHg）、坐位脉博（次/分）、体温（℃）、呼吸频率（次/分）。测量前，建议参与者至少休息5分钟。` and for p786 = `如果生命体征的检查与PK采样时间一致，尽量在PK样本采集之前完成生命体征检查，最大限度地提高血样采集的准确性。` (verbatim from prompt block, see `prompt.txt` line 3 + source_rows.json excerpts).
- v2 prompt's phase-binding rule: see `prompt.txt:3` ("首次给药后或治疗期内才执行、且不影响筛选/基线入排判定的检查或随访，应处置为 post_treatment_execution，不得绑定到筛选或基线审核节点").
- v1 worker_03 disposition note for p786 (verbatim): "本单元为 best_effort 强度的操作时序建议（非明确必做），且其触发条件（生命体征检查与PK采样时间一致）为治疗期给药后场景，不影响筛选/基线入排判定；其控制作用仅为操作优化建议，不构成入排审核节点上的增量控制要求，不产生候选。"
- `freeze_provenance.json` for v2 carries `frozen_plan_sha256: f0aa7e4bccad782ad5472c1f446f079e26343f694ad3ddca401bfbef89f38250`, `coverage_manifest_sha256: 89c7f00a8ed2d7eda666fb62538b1941b10c59f4375b8c4491436f66ea0b51e6`, `protocol_document_sha256: 362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`. All three identical to v1.
- Config delta: `representative_group_vital_sign_modality.v2.json` is 8 fields (extends, schema_version, group_id, task_id, worker, artifact_dir_name — plus JSON closure). No content fields changed.
- `replay-summary.json` shows `structured_control_deconstruction_accepted: true`, `gate_accepted: true`, `claims_complete: false`, `raw_response_count: 3`.
- `clinical-qc.json:35` shows `parent_clinical_acceptance: "pending_codex"` (this gate is NOT closed).

**Assumptions (clearly marked):**

- [INFERENCE] The schema validator's nearest-valid value for `affected_workflow_stage_id` when the model wants to bind a control to the post-dose window is `flow-screening`, since the batch.json only declares `flow-screening` and `flow-baseline` in `workflow_stages`. Without `post_treatment_execution` or `flow-treatment-day-1` in the workflow_stages menu, the model is forced into an incorrect binding. Confirm by reading batch.json `workflow_stages`: only the two screening/baseline stages are declared.
- [INFERENCE] The reviewer treats v1 (slice61av) worker_03's `0-candidate` outcome as a precedent for the modality projection in this chapter, since v1 ran cleanly under the same model, same batch_id, same protocol SHA, with the system prompt's rule being honoured. The v1 disposition text for p786 is treated as the closest available reviewer-style sanity check.
- [INFERENCE] "Successfully published" in the previous slice61at ECG checkpoint model is the precondition for "闭环". The current run has published but the parent clinical gate is `pending_codex`, so the chapter is NOT closed.

## Risks, Gaps, And Verification Needs

**Risk A — p786 binding to `flow-screening` is a stage-binding error (highest impact).**

- Failure mode: a downstream operator (Patient Profile lane `node-anchors`, fact projector, or reviewer UI) sees a `decide_at_node` obligation labelled "screening" with a "best-effort sequence before PK" trigger. At screening there is no PK sampling in flight, so the obligation is unreachable. Risk surfaces as: (a) wasted Profile lane entry that never updates, (b) a "永远等待" pseudo-status that may break Profile revision closure semantics, (c) potential false-positive duplication if Codex later decides to also re-include p786 in a treatment-period slice.
- Direct contradiction with the same prompt's `post_treatment_execution` rule and with v1 worker_03's identical-source disposition.

**Risk B — Attempt 3's `已由系统原样保留定向修订范围外的上一轮内容` issue.**

- The `issues` list of the accepted attempt contains the literal string `已由系统原样保留定向修订范围外的上一轮内容`. This is a system-side annotation, not a model error, but it implies the prior (broken) candidate was preserved verbatim into the third attempt's response object. If `cross_source_relations[0]` from attempt 2 (the schema-rejected one) is being reused in attempt 3's `disposition.notes` references, the v2 source-of-truth for `cross_source_relations` may still carry the schema-invalid root cause's residue. **Verification need**: dump the full text of the third raw response (sha256 `30938424…`) to confirm no orphan cross-source relation persists.

**Risk C — p785 cross-source relation type vs modality mismatch (low impact, cosmetic).**

- p785 atom is `modality: recommended` with relation kind `further_explanation` to the procedure row. "Further explanation" implies the new candidate extends an existing mandatory row. But the row's mandatory fields (visit schedule, completion expectation) are not extended by p785 — p785 adds **new** content (four components, rest suggestion) not present in the row. A more accurate relation kind would be `supplementary_requirement` (as p786 uses). Same applies to the `kind: complete_or_verify` atom with `modality: recommended` — recommended cannot be "complete or verify"; it is "advise or encourage". `complete_or_verify` with a `recommended` modality is logically incoherent.

**Risk D — package_ordinal drift between v1 and v2.**

- v1 batch.json: package31 (p321), 55 (p684), and unknown for owned (v1 was the original ingest). v2 source_rows.json: package 67 (p885), 69 (p784/p785/p786), 31 (p321), 55 (p684). `package_ordinal: 69` is the new owning package after the most recent rebaseline (`phase5-slice59i-d001-phase-table-caption-rebaseline-20260827`).
- Structure_unit_ids and source_span_ids match v1; the chapter content is unchanged; the package id is from a later ingest. This is documented as a known artifact of recent rebaselines (`CHECKPOINT_20260829_PDF_STRUCTURAL_PARITY_ACCEPTED_NEXT_FULL_PROTOCOL_DECONSTRUCTION.md`). Not a defect, but the published `agent-controls.json` records `protocol_version_id: "D001-02-002:v1.0:phase-ii"` — needs verification that v1.0 here matches the rebaselined package ordinal69's version label, not the v1 ingest's.

**Risk E — Conference context and Codex main-venue plan are TODO stubs.**

- `context/phase5-slice61aw-vital-sign-parent-review_conference_context.md` shows `Source Of Truth: TODO`, `Scope: TODO`, `Success Criteria: TODO`. `plans/codex_main_venue_phase5-slice61aw-vital-sign-parent-review.md` shows `Date: TODO`, `Task Decomposition: TODO`, `Source Packet: TODO`, `Verification Checklist: TODO`. Both `runs/conference/phase5-slice61aw-*/general_single_object*.md` are stubs ("RUN REJECTED"). For a "high_risk_contradiction_review" packet, leaving the source-of-truth, scope, and verification checklist blank in the very document that is supposed to define the review is itself a control-point loss. This is not the audit subject's fault, but the runner's. It made this Pi review reconstruct the source-of-truth from task-internal artifacts.

**Risk F — Public-facing "技术通过" vs "临床通过" labelling.**

- `replay-summary.json:clinical_gate_accepted: true` next to `parent_clinical_acceptance: "pending_codex"` could be misread by a downstream consumer as "clinical acceptance". The two are different: the harness's clinical_qc gate accepts the wire output; Codex's parent clinical acceptance is the manual cross-check. AGENTS.md's line17 ("The application is AI-led but is not the final enrollment decision authority") requires that the published handoff not be presented as clinical acceptance. slice61aw's `compact-handoff.md` does show `Clinical closure accepted: True` — that line is the harness-level closure, not Codex's parent acceptance, but a quick reader could mistake it. Recommend renaming to "Harness clinical_qc gate accepted".

**Risk G — b785 modality="recommended" with kind="complete_or_verify" is structurally invalid in the modality ladder.**

- The project modality ladder is `mandatory < recommended < best_effort`. `kind: complete_or_verify` is the verb for "perform and confirm this was done". This verb is only coherent with `mandatory` (and arguably with `recommended` for items the operator is asked to attempt-and-confirm). It is incoherent with `best_effort`. p786's atom has exactly this issue. Risk: if a downstream filter or UI maps `kind × modality` into a check list, the `complete_or_verify × best_effort` row falls through silently or shows as a "to do" item that should not be actionable.

## Recommended Next Step

**For Codex (parent clinical acceptance decision):**

1. **Decide on the p786 stage binding before accepting the parent gate.** The minimum sufficient fix is to either:
   - (a) Re-run slice61aw with `workflow_stages` extended to include the post-dose stages (`flow-d1-pre-dose` or `flow-treatment-period`), and rebind p786 to that stage; OR
   - (b) Move p786 to `post_treatment_execution` per the same system-prompt rule, and re-publish with no `flow-screening` binding. This requires the schema to support a `post_treatment_execution` flag (verify in batch.json / config).
2. **Verify v2's attempt 3 has no residue from attempt 2's schema-invalid cross_source_relations**. Dump `raw-responses.json[2].text` (sha256 `30938424…`) full and confirm `cross_source_relations` array is exactly one entry with `affected_workflow_stage_id: "flow-screening"` and no schema-broken residue.
3. **Re-classify p785 relation kind from `further_explanation` to `supplementary_requirement`** if Codex agrees p785 adds net-new content not in the procedure row. Concurrently, decide whether `kind: complete_or_verify × modality: recommended` is acceptable for the four-component list (p785) or whether a different verb (e.g., `record_components`) is appropriate.
4. **Do not promote `compact-handoff.md`'s `Clinical closure accepted: True` line into a Codex acceptance statement** until the parent gate is actually closed.

**For Codex (governance / boundary hygiene):**

5. **Fix the conference runner**: the context and plan files for slice61aw were emitted as TODO stubs; both `runs/conference/.../general_single_object*.md` are preflight-rejected stubs. For a `high_risk_contradiction_review`, the source-of-truth, scope, and verification-checklist MUST be filled by the time the panel starts. Either the runner needs to reject TODO-stub contexts at preflight, or the chair must fill them before dispatch.

**For Codex (downstream consumer safety):**

6. **Add a defensive field to gate-results.json**: `parent_clinical_acceptance` (mirrored from clinical-qc.json) should appear in the gate JSON. Currently it is only in clinical-qc.json; the gate JSON claims `accepted: true` without distinguishing harness-level vs parent-level.

**For Pi session — bounded question to Codex if available:**

Q1. The system prompt's `post_treatment_execution` rule and the publication-gate rejection rule on attempt 1 directly conflict for p786 (one says "post-treatment → no screening binding"; the other says "best_effort with no procedure-row coverage → must produce a control"). Was this contradiction resolved at the contract layer between slices61at (ECG) and 61aw (vital sign), or does the prompt still contain both rules verbatim? If both are still present, the next round must resolve it; otherwise slice61aw v3 will hit the same wall.

Q2. The schema validator's `affected_workflow_stage_id` menu is restricted to `flow-screening` and `flow-baseline` in the current `workflow_stages`. Was this menu intentionally narrowed, and is the project now committed to "all controls must bind to screening/baseline" regardless of post-dose applicability? If so, the system prompt's `post_treatment_execution` rule is dead code and should be removed; otherwise the menu must widen.

Q3. The v2 prompt was created via `extends` only, but the contract rule set (publication-gate `REQUIRED_ACTION_DISCARDED`) was apparently updated between v1 and v2 runs (v1 had no such rejection in attempt 1). Was the rule update shipped as a code change, or was it a model-side variance? If the former, the prompt template SHA-256 (`b17ddc6f43c37636589d2fe0b3b2d3a5dee2897ed7fff503f95a7d30a5e7e98f`) should NOT match v1's. Verification: confirm v1 and v2 prompt_template_sha256 differ; if identical, the rule change is silent and the contract is unfrozen.

## Bounded Questions for Codex

Same as Q1–Q3 above. The most important single question is **Q2** — the menu-versus-rule mismatch is the root cause of the p786 binding defect, and no amount of re-prompting will fix it if the schema menu is the binding constraint.

## Top Objections and Decisions

1. **Objection**: The compact handoff claims `Clinical closure accepted: True` while parent clinical acceptance is `pending_codex`. This is a single line of text that, if surfaced to a downstream user as "this group has been clinically accepted", materially misrepresents the state. Decision: Codex should rename the handoff field to `Harness clinical_qc gate accepted` and require `parent_clinical_acceptance == "accepted"` before promoting the handoff to a clinical-acceptance surface.

2. **Objection**: p786 was correctly treated as non-control by v1 worker_03 (same model, same batch_id, same prompt source text, same protocol hash). v2 escalated it to a control with the wrong review-node binding. The only difference between v1 and v2 prompts is the `extends` shim and the model temperature/sample variance. If the same source text is producing opposite gate outcomes under the same model+prompt base, the contract is no longer reproducible at the source-text level. Decision: Codex must re-run v1 (slice61av) under the same harness and confirm it still produces 0 candidates. If it does, the v2 escalation is a model-side drift and the contract is not reproducible; if it does not, the prompt contract was changed silently.

3. **Objection**: The `extends` config (v2) inherits every binding from v1, including the `required_candidate_source_refs` / `forbidden_candidate_source_refs` / `structural_only_source_refs`. The fact that the same configuration yields0 candidates in v1 and 2 candidates in v2 is not a config change — it is a model-side divergence. The published controls in v2 may be correct or wrong, but the **audit chain** for the published controls is broken. Decision: Codex should not accept the parent gate until a third independent run on the same prompt base reproduces the same 2 candidates.

4. **Objection**: slice61aw's `compact-handoff.md` carries `Overall accepted: True`, but the parent clinical gate is `pending_codex`. The risk is that the handoff will be persisted as "complete" and consumed downstream as authoritative before Codex's parent acceptance. Decision: rename or add a `parent_clinical_acceptance_state` field that mirrors clinical-qc.json, and reject any downstream consumer that does not check it.

5. **Objection**: The conference context and plan are TODO stubs. For a high-risk review, the source-of-truth must be pinned before the panel runs. This is a runner-side defect; it should be raised independently as a separate concern rather than allowing this Pi session to silently fill the gaps. Decision: report this as a separate runner defect and recommend the runner preflight-reject any TODO-stub context/plan pair.
