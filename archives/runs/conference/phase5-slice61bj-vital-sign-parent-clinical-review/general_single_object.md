# Conference Participant Output: phase5-slice61bj-vital-sign-parent-clinical-review - general_single_object

## Boundary Check

- **Declared fallback & capability limitation**: Codex primary `cms-router/minimax-m3:xhigh` unavailable before resumable session. This pass operates as bounded `pi` fallback `opencode-go` / `muse-spark-1.2-contributor` effort `xhigh` (per `context/phase5-slice61bj-vital-sign-parent-clinical-review_general_single_object_route_manifest.json` day branch). Tool-enabled read-only worker only; **no file edits, no production path writes, no visual/PPT/browser/PDF rendered acceptance, no clinical/regulatory final acceptance** — those remain Codex chair authority. Runner-managed report path `runs/conference/phase5-slice61bj-vital-sign-parent-clinical-review/general_single_object.md` not written via tools; report returned inline for runner persistence.
- **Workspace boundary**: Strictly `CWD = /Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`. All reads confined to authorized artifact bundle: `body.p784-p786` owned + 4 attached refs (`body.t5.r10`, `body.p321`, `body.p684`, `body.p885`), `runner-result.json`, `hydrated-batch.json`, `gate-results.json`, `agent-controls.json`, `freeze_provenance.json`, `source_rows.json`, `clinical-qc.json`, `v14 config`, `protocol_control_gate.py`, shared transport/gate code. No production writes, no MTPLX daemon restart/stop/reconfigure, no real protocol/subject reuse beyond frozen provenance. Synthetic non-clinical matrix evidence from linked execution `phase5-slice61bi` used as read-only context.
- **Output contract**: One whole-workflow pass, independent of other participants. No duplicate broad exploration; compact evidence trail preserved. Advisory to Codex, not instruction.

## Independent Work Product

### Objective audit — what was actually frozen in v14

Claim to challenge: “四类测量与五个显示读数一致保留；建议休息未强化且核对实际动作；筛选+D1基线双节点完整；p786 PK顺序正确隔离为治疗期；与流程表/EX-21未重复改写；MTPLX严格JSON改AR为项目无关且不影响DeepSeek/oMLX的系统修复”。Verification must not conflate **technical gate accepted=true** with **clinical acceptance**.

**v14 identity**: `group_id=d001-ii-vital-sign-modality-v14`, `task_id=phase5-slice61bj-20260829`, `protocol_document_sha256=362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`, `frozen_plan_sha256=f0aa7e4bccad782ad5472c1f446f079e26343f694ad3ddca401bfbef89f38250`, `coverage_manifest_sha256=89c7f00a8ed2d7eda666fb62538b1941b10c59f4375b8c4491436f66ea0b51e6`, `config_sha256=a257b977431c9b44c080f4d38ff126d0604ff635377cef90fdcdd69ac198e1fa`, `prompt_sha256=2b224a0284d397fca7aeeea052a14d03f8e28ba741f9e4be27a3a24d42ecd155`, `response_format_sha256=e1da464e843204931ac4976a8fa56002e7d4e8619260a922a37fe0e5e4e2065c`. `batch_id=pcb-512a3a7b54a7d8d2c677cd13`, `session_id=protocol-control-chat-96baec44923148dc8ab68a50cc42240d`, `transport=mtplx/mtplx-qwen38-27b-optimized-quality@http://127.0.0.1:8002/v1`, `mode=live_mtplx_runner`, `attempt_outcomes=[schema_invalid, publication_invalid, parsed]`, final `runner_status=已解析`.

### Finding matrix (6 claims)

**1. 四类/五读数 — CONDITIONAL PASS with count-fidelity risk (highest impact)**

- Source `body.p785` verbatim: `生命体征检查包括坐位血压（收缩压和舒张压）（mmHg）、坐位脉博（次/分）、体温（℃）、呼吸频率（次/分）。` — 4 categories, 5 displayed values (SBP/DBP split).
- Final candidate preserves all: atom `pca-0383fe41...` `modality=mandatory` `kind=complete_or_verify` statement: `核对生命体征检查包含坐位血压（收缩压和舒张压）（mmHg）、坐位脉博（次/分）、体温（℃）、呼吸频率（次/分）四项测量。` Source span `body.p785`, units+precision intact (mmHg, 次/分, ℃).
- **Defect**: All 4 categories + 5 values are **bundled into a single obligation atom** inside a single DNF group `pog-21ec...`. Gate check `_check_recording_precision_fidelity` + `_check_obligation_source_action_impersonation` will not fail because excerpt is present, but **user-facing item count fidelity** (`_check_user_facing_item_count_fidelity`) is at risk: string says `四项测量` while logical readings =5. `clinical-qc.rows[4].codex_clinical_checks` explicitly lists pending Codex checks: `体温、坐位血压、坐位脉搏、呼吸频率四项记录为必做且不得重复流程表=pending`, `四项记录单位与精度完整保留=pending`. No `control` splits SBP/DBP into independent atoms, so downstream fact generation cannot emit 5 independent evidence keys if needed. `agent-controls.display_ordinal=1` with `obligation_combination=all` and 2 atoms (mandatory+recommended) further bundles display count=1 vs clinical items=5.
- **Remediation proposed**: Split atom 1 into 5 fine-grained `vital_signs_components_and_rest` sub-evidence or at minimum 4 atoms (SBP/DBP together with explicit note “2 readings”). Amend statement to `四类（五项读数）` and add explicit `item_count=5` in display layer, or keep bundled but add `supplementary note` that SBP/DBP counted as 2. Add gate test `test_item_count_five_readings`.

**2. 建议休息 — PASS, correctly soft**

- Source: `测量前，建议参与者至少休息5分钟。`
- Atom `pca-91963...` `modality=recommended` (not mandatory), statement `建议项：核对参与者实际在测量前休息至少5分钟。` — captures **actual realization**, not `是否提出建议` (`_check_participant_preparation_realization_fidelity` passes).
- `minimum_evidence` both stages: `若记录存在休息时长信息，核对是否≥5分钟；无休息记录不单独构成缺口，仅在记录存在时核对。` + guidance mirrors. This is **not hardened** to mandatory; `_check_minimum_evidence_modality_fidelity` and `_check_obligation_modality_fidelity` would reject hardening.
- **Edge**: Both minimum_evidence share same `fact_type=vital_signs_components_and_rest` and `required_source_types=[vital_signs_record]` — no spurious `REST_ADVICE_GIVEN` type. Good.

**3. 筛选+D1基线双节点 — PASS after repair, fragile**

- Final `review_node_bindings`: 2 entries `flow-screening@screening` + `flow-baseline@baseline` each `role=decide_at_node`, `guidance` identical soft-rest wording. `minimum_evidence` due_stage screening + baseline likewise. Disposition note: `适用于筛选及基线访视，故保留为增量候选并绑定两个冻结节点。`
- **Repair history proves fragility**: Attempt2 was `publication_invalid: REVIEW_STAGE_SCOPE_MISMATCH body.p785 workflow stages=['flow-screening'] do not match expected stages=['flow-baseline','flow-screening']` — model initially dropped baseline (candidate `pcc-cb9baf...` rejected). Attempt1 was `WIRE_SCHEMA_INVALID: 带时间约束的新义务必须区分访视安排或结果有效期，不得使用泛化的完成/核对` — model tried generic time-constrained atom. Only Attempt3 corrected. This indicates the LLM’s prior for p785 defaults to screening-only; without deterministic gate, regression likely.
- **Remediation**: Freeze explicit test `test_vital_sign_binds_both_nodes` and keep gate `validate_protocol_control_publication` as only write boundary.

**4. p786 PK顺序 — PASS, correctly isolated**

- Source `body.p786`: `如果生命体征的检查与PK采样时间一致，尽量在PK样本采集之前完成生命体征检查，最大限度地提高血样采集的准确性。`
- Disposition `su-7a42e55b... -> post_treatment_execution` with notes `属治疗期内给药后操作细节，不影响筛选/基线入排判定`. No candidate linked, no review binding, no `minimum_evidence`. `clinical-qc.rows[5]` checks: `PK采样自W2或D15起...保留为治疗期执行=pending`, `不得绑定筛选或基线=pending`, `尽量...不得硬化为绝对先后=pending`. All honored — `尽量` preserved as best-effort, not `must`/`prohibit`.
- **Risk**: If future harness reuses p786 as pre-enrollment, would incorrectly harden PK order. Current isolation is correct but depends on disposition, not obligation modality.

**5. 流程表 (T5.R10 / p321) & EX-21 (p684) — PASS, supplementary not duplicate**

- `cross_source_relations[0]`: `kind=supplementary_requirement`, `left_target_kind=control_candidate`, `right_target_kind=required_procedure`, `right_target_id=pcm-row-aee90bcadab30a320c395d48`, `affected_workflow_stage_id=flow-screening`, note `流程必做目标仅覆盖筛选访视执行...未规定具体测量组分...本候选补充操作细节`. This correctly models **supplement** not duplicate-cover. Gate `_check_supplementary_procedure_stage_alignment` passed.
- `body.t5.r10` / `body.p321` rows `role=attached` `codex_clinical_checks` pending but disposition not candidate — no double-publish.
- `body.p684` EX-21: `筛选或基线时，生命体征、体格检查、12-导联心电图、胸部CT...异常且有临床意义，经研究者评估如果参与研究将可能对参与者构成不可接受的风险` — kept as `frozen_plan_owned` attached target `su-5c242dd0...`, **no link** from vital-sign candidate, so not rewritten. Check `异常且有临床意义与研究者不可接受风险判断必须同时成立=pending` respects conjunctive gate.
- **Minor gap**: `cross_source_relations.affected_workflow_stage_id` is only `flow-screening`, yet candidate `review_node_bindings` covers `flow-baseline` as well. Strict `_check_supplementary_procedure_stage_alignment` expects affected stage ∈ candidate stages; single-screening is subset, allowed, but documentation should clarify baseline supplement is not via procedure catalog but via p885 note. No blocker.

**6. MTPLX严格JSON改AR — CONDITIONAL PASS, mislabeled as AR; true fix is prelude unbounded (project-agnostic but under-verified)**

- **What changed**: v13 (`phase5-slice61bh`) had 2× `transport_failed` HTTP 500 `internal_error request_id=e0c906e5d034 / c283bba62027`, `gate accepted=false`. v14 (`61bj`) same `prompt_char_count=31241` but with infra fix succeeded `200 OK` in 180–211s. Linked diagnosis (`phase5-slice61bi` workers 01-03) proves root cause is **not** prompt length (200–31k chars all 200 OK), **not** schema size (full 17.2KB wire_v1 200 OK with concise reasoning), **not** KV cache (24.1GB free still crashed), but deterministic `mtplx/constrained.py: _THINK_PRELUDE_DEFAULT_MAX_CHARS=4000` with Lark `PRELUDE_TEXT: /(.|\n){0,4000}/`. At step 2150 token `109064/110227` crosses 4001 chars → `llguidance Stop: ParserTooComplex` → `GrammarConstraint.advance()` → `RuntimeError: constrained decoding desync` → unhandled exception → `flight.sweep(reason=orphaned)` → HTTP 500. Verified fix: `MTPLX_THINK_PRELUDE_MAX_CHARS=0` (`PRELUDE_TEXT: /(.|\n)*/`) passes 5000 steps/9306 chars; `=16000` passes 3000 steps. Checked file `/Users/smkzw/Library/Application Support/MTPLX/runtime-venv/lib/python3.14/site-packages/mtplx/constrained.py` lines 293-322.
- **Is it project-agnostic?** YES in code: env var gating `_think_prelude_max_chars()` affects only Qwen thinking prelude grammar (`<think>` 248068/ `</think>` 248069) for `mtplx` backend. `DeepSeek`/`oMLX` backends use different `constrained.py` path or no prelude cap; transport `_SUPPORTED_BACKENDS={mtplx,mtplx-api,omlx,local-omlx,deepseek...}` keeps backends isolated. No repo prompt change (v14 notes: `冻结来源、临床问题和父级核对要求与v13完全一致，本轮仅验证MTPLX严格结构响应改为逐token生成后的真实承载能力`). `response_format` remains `type=json_schema, name=protocol_control_agent_wire_v1, strict=true` — **not** switched to `json_object` or plain text. So claim “改用AR” is terminology confusion: refers to `scheduler-mode ar_batch` / gradual generation, not relaxing strict schema. True fix does not relax strictness.
- **Does it affect DeepSeek/oMLX?** Diagnosis synthetic matrix showed no 500 when using same strict schema with concise reasoning; but **no dedicated DeepSeek/oMLX regression** was run with 31k+17.2KB+deep reasoning. Risk low but unverified. `CHECKPOINT_20260829` correctly states external infra, not repo, and recommends `export MTPLX_THINK_PRELUDE_MAX_CHARS=0` before official replay.
- **Remediation**: Document env var persists across daemon restarts (macOS `MTPLXApp` pipe), add synthetic DeepSeek (`deepseek-chat` strict) + oMLX (`mlx-community`) probe with same wire_v1 to prove no regression, add health-check `GET /health` before replay.

**Overall technical vs clinical**: `gate-results.json accepted=true`, `replay-summary gate_accepted=true, technical_replay_accepted=true`, BUT `clinical-qc.parent_clinical_acceptance=pending_codex`, `claims_complete=false`, `structured_control_deconstruction_accepted=false`, 7 rows all `codex_accepted=null` and 8 `codex_clinical_checks=pending`. **Technical pass ≠ clinical accept**. Limited acceptance boundary is warranted, not full.

## Evidence And Assumptions

**Evidence (grounded)**

- Owned spans: `body.p784` (`生命体征检查` title), `body.p785` (4 measurements+5min), `body.p786` (尽量 PK前) — `source_rows.json` `frozen_plan_owned`, `freeze_provenance claims_complete=false`, `hydrated-batch owned_source_span_ids=[body.p784,p785,p786]`.
- Attached spans: `body.t5.r10` flow table, `body.p321` 摘要静息, `body.p684` EX-21, `body.p885` D1基线注 — `source_rows`, `freeze_provenance attached`, `clinical-qc rows`.
- Hydrated batch: `pcb-512a3a7b54a7d8d2c677cd13` candidate `pcc-60a07e196afde7730702bbcb` title `生命体征检查组分及测量前休息建议`, `semantics.obligation_expression.groups[0].atoms[0] mandatory / [1] recommended`, `minimum_evidence 2× vital_signs_components_and_rest due_stage screening/baseline`, `review_node_bindings 2× decide_at_node`, `cross_source_relations supplementary_requirement -> pcm-row-aee90bcadab30a320c395d48`, dispositions `su-391... supporting_or_supplement`, `su-3edd... other_control_candidate`, `su-7a42... post_treatment_execution`.
- Runner: `execution/runner-result.json` 3 attempts (schema_invalid wiring, publication_invalid stage mismatch, parsed), `transport-calls.json` 3× ok 180/173/211s, `raw-responses.json` 3 texts, `replay-summary.json technical_replay_accepted true`.
- Gate: `gate-results.json accepted true gate_version phase5/control-publication-gate/v1 issues []`, `clinical-qc.gate same`.
- Prior failure: `phase5-slice61bh` 2× transport_failed 500 `e0c906e5d034/c283bba62027`.
- MTPLX diagnosis: `logs/execution/phase5-slice61bi/worker_01-03` + `CHECKPOINT_20260829_MTPLX_STRUCTURED_OUTPUT_PRELUDE_DIAGNOSED_RECOVERY.md`, `mtplx/constrained.py _THINK_PRELUDE_DEFAULT_MAX_CHARS=4000`, `mtplx/server/openai.py unhandled_exception`, `flight-8002.jsonl gen ~3990 acc ~1321-1333`.
- Configs: `representative_group_vital_sign_modality.v14.json extends v13`, notes identical except infra probe.

**Assumptions (inferred, not observed)**

- [INFERENCE] `pcm-row-aee90bcadab30a320c395d48` = vital-sign row in procedure catalog for screening only — inferred from cross-relation note, not re-fetched catalog JSON here.
- [INFERENCE] `MTPLX_THINK_PRELUDE_MAX_CHARS=0` already applied in v14 live replay environment — inferred because v14 succeeded vs v13 failed with same prompt; no direct env dump in `freeze_provenance`, but transport succeeded.
- [INFERENCE] “改用AR” in objective = `prelude unbounded` token-by-token generation, not switch to `stream=true` or `json_object` — inferred from `replay-summary batching_mode single_batch_with_known_targets` still strict.

## Risks, Gaps, And Verification Needs

**Blockers (must resolve before clinical accept)**

1. **parent_clinical_acceptance=pending_codex, 8 codex_clinical_checks pending, claims_complete=false** — Codex final QC not done. Technical gate pass explicitly must not be equated to clinical accept (quality gate `clinical-qc.notes: Agent wire/hydration/gate evidence only; Codex owns clinical QC`).
2. **Item-count fidelity** — Likely reviewer objection: UI showing `方案控制 01` but 5 values bundled; if downstream fact projection emits 1 fact for 4 categories, count mismatch will be flagged. Need Codex ruling on `四项 vs 五项`.

**Gaps / risks**

- **Repair brittleness**: Model needed 2 corrective turns to achieve correct stage binding and schema validity. Without gate, would have published screening-only or generic time-constraint atom. Harness `bounded-repair` saved it, but indicates prompt sensitivity; future slices may regress without same repair loop.
- **Prelude fix persistence**: `MTPLX_THINK_PRELUDE_MAX_CHARS` is daemon env; macOS `MTPLXApp` restarts may reset to 4000. No `freeze_provenance` env capture. Unverified on DeepSeek/oMLX strict path — need dedicated probe.
- **Cross-relation stage subset** (flow-screening only vs candidate baseline also) — low risk but may be flagged as `RELATION_STAGE_MISMATCH` if gate tightens.
- **No structured_control_deconstruction_accepted** (false) — expected for representative group, but confirm not required for publication.
- **Tracer**: `raw-responses.json kind start/repair` shows candidate_side vs left_target_kind naming drift (`candidate_side:left` vs `left_target_kind:control_candidate`) — harmless but shows wire migration.

**Verification needs (concrete checks)**

- Codex visual check of `body.p784-p786` bbox/text-range/bbox vs hydrated spans (already proof via `source_rows`), but member re-read of `frozen_phase_plan.json` for `package_ordinal 69`.
- Run `check_protocol_control_publication` on hydrated batch + `coverage_manifest.json` + `frozen_plan.json` offline to re-issue gate report (should be `accepted true, issues []`).
- Non-clinical probe matrix with `MTPLX_THINK_PRELUDE_MAX_CHARS=0` vs 4000 for DeepSeek `deepseek-chat` and oMLX `local-omlx` with `protocol_control_agent_wire_v1 strict true` to prove no side effect.
- UI count: assert `agent-controls Obligations.length == clinical-qc rows[4].agent_candidates[0].obligation_time_atoms.length` and display respects 5 readings.

## Recommended Next Step

- **Limited acceptance boundary (do not publish as final)**: Accept v14 as **technical replay closed** with `gate accepted true` but **clinical pending**. Allow `claims_complete=false` to remain, keep `parent_clinical_acceptance=pending_codex` until Codex clears 8 `codex_clinical_checks`. Record this as `d001-ii-vital-sign-modality-v14 — technical pass, clinical hold`.

- **Concrete remediation before Codex sign-off**:
  1. Patch display/count: either split SBP/DBP into explicit sub-atom or amend statement + guidance to `四类（收缩压/舒张压分计五项读数）` and add `item_count=5` annotation; update `minimum_evidence` to reference 5 readings.
  2. Persist infra fix: set `MTPLX_THINK_PRELUDE_MAX_CHARS=0` in MTPLX daemon launch plist/env, log `MTPLX_THINK_PRELUDE_MAX_CHARS` in `freeze_provenance.transport_identity` for next replay, run DeepSeek/oMLX synthetic strict probes (31k prompt, wire_v1) and archive results.
  3. Keep bounded-repair loop mandatory for this packet (at least 2 repair turns) — do not reduce to single-shot.

- **Bounded questions for Codex (answer blocks clinical accept)**:
  1. **Item count**: Should user-facing count be `4项` or `5项`? `body.p785` lists 4 categories but 5 values; current `四项测量` will be audited against `p321`摘要 `体温、血压（坐位）、脉博（坐位）、呼吸频率` (also 4). Confirm acceptable wording or require `五项读数`?
  2. **MTPLX env**: Is `MTPLX_THINK_PRELUDE_MAX_CHARS=0` the intended permanent value (unbounded) or `16000`? Should it be captured in `app/config.py`/`MTPLX_PROTOCOL_BATCH_MAX_TOKENS` or only daemon env? Confirm persistence across restarts.
  3. **“改用AR” semantics**: Does objective expect `response_format` to stay `strict:true` with prelude unbounded (current), or switch transport to `stream:true` AR batch? Confirm no `response_format` change needed.
  4. **p786 modeling**: Is `post_treatment_execution` disposition sufficient, or should `尽量` be retained as a separate `recommended` post-treatment control (with `temporal_scope=treatment_period`) for audit completeness?
  5. **Baseline supplement via procedure catalog**: Cross-relation currently `affected_workflow_stage_id=flow-screening` only; should it be `flow-screening, flow-baseline` or keep single-screening and rely on `body.p885` note for baseline authority?

- **Safe provisional path until answers**: Keep hydrated batch unchanged, do not relax `strict` schema, do not add p786 baseline binding, treat item count as `4 categories / 5 readings` with explicit note in Codex review — enables deterministic re-validation without re-prompting.
