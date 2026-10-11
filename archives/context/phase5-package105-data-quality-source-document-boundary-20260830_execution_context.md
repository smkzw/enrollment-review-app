# Execution Context: phase5-package105-data-quality-source-document-boundary-20260830

Created: 2026-08-30 17:18:40 CST
Objective: 在不调用临床语义模型、不发布控制点、不进入受试者、OCR、Patient Profile或浏览器流程的前提下，核对并建立D001 II冻结计划第105包数据质量、eCRF和源数据/源文件章节的最小模型外来源闭包与确定性回归；区分研究执行和数据治理义务与入排审核证据接受边界，并严格保持第104/106包及无所有权上下文边界。
Task type: `long_horizon_code`
Risk: `medium`
Execution module trigger: Codex identified 4 independent work items, which is greater than two.
Route schedule: `unscheduled`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `openai-codex/gpt-5.6-luna:max -> codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor` -> `pi` / `openai-codex` / `gpt-5.6-luna`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- Project instructions: `AGENTS.md`.
- Active task contract: `.trellis/tasks/08-22-phase5-clinical-facts-profile/{prd.md,design.md,implement.md}`.
- Latest accepted recovery point: `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE104_INTERIM_ANALYSIS_GOVERNANCE_BOUNDARY_ACCEPTED.md`.
- Immutable candidate root: `artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/`.
- Frozen plan: `artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/frozen_phase_plan.json`, SHA-256 `92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4`.
- Coverage manifest: `artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/coverage_manifest.json`.
- Structure block: `artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/structure/blobs/protocol_blocks/3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d.json`.
- Source protocol identity: SHA-256 `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`.
- Replay implementation and deterministic gates: `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py` and `slice59n_representative_group_reject_gates.py`.
- Adjacent accepted examples: Package 103 and 104 config/checklist/test files under `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/`.

### Frozen Package 105 Identity

- Plan `papl-e17d498106b6f71f440ff2be`; package ordinal `105`; package id `pap-b8d5cdfbc6ac4c373c6576b3`; selected phase `phase_ii`.
- Owned sources are exactly `body.p1238-p1247` in source order. `p1238/p1239/p1241/p1243` are headings; `p1240` covers sponsor/site EDC data management and query resolution; `p1242` covers validated EDC, training, completion, review, electronic signature and date; `p1244-p1247` cover source-data/source-document definitions, prospectively defined source types, ALCOA-like source quality, certified copies, audit trail, source preservation and direct access.
- Package 104 owns only its four frozen interim-analysis units. Package 106 starts at `body.p1248` and owns `body.p1248-p1250`; none may migrate into Package 105.
- The frozen plan carries 37 broad context units for Package 105. They are read-only discovery context, not automatically required prompt attachments. Any attached subset must be justified by a concrete unresolved semantic boundary and must not transfer ownership.
- Current formal state before this packet is `1848` structure units, `1240` semantic targets, `131` packages, `103` packages remaining, and `claims_complete=false`.

### Parent Clinical And Product Boundary

- Do not assume either zero or nonzero candidates before reading the exact source. Separate study data-governance obligations from subject-level pre-enrollment controls.
- A source document's evidentiary acceptability, certified-copy status, audit trail, or direct-access duty can affect provenance/QC, but must not automatically become a subject eligibility criterion, missing clinical fact, or exclusion result.
- Conversely, do not erase genuinely relevant provenance constraints merely because they are not eligibility rules. Record them as research/data-governance context or a future evidence-QC boundary only if the current contracts can represent them without coercing a subject review node.
- Do not modify shared runtime code unless a project-independent defect is directly demonstrated and Codex authorizes a separate repair. For this packet, prefer the model-free package config and deterministic regression boundary.
- No clinical semantic model, publication, subject, OCR, Patient Profile, browser, visual, or external web operation is authorized.

### Worker 02 Write Authorization

Worker 02 may create or update only:

- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package105_data_quality_source_document_boundary.v1.json`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice61cr-package105-data-quality-source-document-boundary-parent-checklist.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61cr_package105_data_quality_source_document_boundary.py`
- Generated dry-run evidence under `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n-prepare/d001-ii-package105-data-quality-source-document-boundary/` by running the existing replay script.

Workers 01, 03 and 04 are read-only. Worker 04 must not be launched until Codex has reviewed and corrected Worker 02's implementation and the deterministic checks pass.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.
- Do not rewrite the immutable plan, coverage manifest, source protocol, structure block, or accepted Package 104 artifacts.

## Work Items

1. 独立核对冻结计划第105包的准确来源、原始DOCX结构、期别范围、所有权、相邻包边界和只读上下文，报告任何预期外来源缺口或所有权漂移。
2. 在父级授权的最小文件范围内实现Package105模型外配置、父级清单、确定性回归和dry-run；不得预设零候选，必须先根据源文判断数据治理条款是否属于入排控制候选。
3. 从临床医学监查和证据治理视角攻击审阅数据质量、eCRF、源数据定义、核证副本、稽查跟踪和源文件访问语义，重点查找把研究执行义务误升格为单例入排条件或把证据可接受性要求错误忽略的两类风险。
4. 待父级实现和纠错后，独立只读复核准确来源、提示最小性、候选/流程/规则/动作/程序输出、证据接受边界及相邻包隔离，并运行声明的确定性测试和dry-run。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
