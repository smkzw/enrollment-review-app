# Execution Context: phase5-package112-reference-list-evidence-authority-boundary-20260830

Created: 2026-08-30 20:38:38 CST
Objective: 在D001 II期当前不可变131包计划中，完成Package112 body.p1295-p1306的参考文献与方案正文权威边界语义闭环；逐项判断文献题录是否形成参与研究前控制，保留方案正文为执行权威，不从题录反向虚构评估阈值或程序，保持Package111/113边界，产出最小配置、父级临床清单、确定性回归、独立攻击验收和可恢复记录，不进入临床语义模型发布、受试者、OCR、Patient Profile、浏览器或视觉阶段。
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 4 independent work items, which is greater than two.
Route schedule: `day`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `cursor/default -> google-antigravity/gemini-3.7-flash:high -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> opencode-go/muse-spark-1.2-contributor:xhigh -> openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `pi` / `cursor` / `default`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- 当前任务与可恢复状态：`.trellis/tasks/08-22-phase5-clinical-facts-profile/task.json`、`.trellis/tasks/08-22-phase5-clinical-facts-profile/implement.md`、`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE111_PROTOCOL_AMENDMENT_AUTHORITY_VERSION_TABLE_BOUNDARY_ACCEPTED.md`。
- 当前不可变计划：`artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/frozen_phase_plan.json`，plan id `papl-e17d498106b6f71f440ff2be`，Package112 id `pap-fa6b2b871b90b62bbfe81775`。
- 当前覆盖清单：`artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/coverage_manifest.json`。
- 结构化方案原文：`artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/structure/blobs/protocol_blocks/3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d.json`。
- 模型外准备器：`.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py`。
- 相邻可复用范式：Package111的配置、父级清单、专项测试及乾跑产物；它们只是实现模式，不是Package112临床语义的替代来源。
- 不得读取本工作区之外的原始临床资料，不得修改任何源方案、原始受试者文件或旧项目报告。

## Frozen Package 112 Boundary

- Package112严格且仅拥有 `body.p1295-p1306` 十二个结构单元；`attached_source_refs=[]`。
- `body.p1295` 是标题“参考文献”，处置为 `structural_only`。
- `body.p1296-p1306` 是逐条参考文献题录，处置使用既有 `non_enrollment_execution`，语义说明必须明确“参考文献题录、非方案执行条款”；不新增领域枚举。
- 题录中的银屑病指南、JAK/STAT、TYK2、Deucravacitinib FDA审评、PASI/BSA/PGA、handprint和 `1%` 均不能反向生成受试者阈值、评分公式、诊断标准或执行程序；方案正文仍是执行权威。
- 38个 `context_units` 全部只读：26个全局无owner，12个分属Package45/46/47/48/50/75/113；其中 `body.p1307` 只是Package113的前向语境，不得升格为Package112来源或候选。
- Package111止于 `body.p1291`、`body.p1292`、`body.t15.r0-r1`；Package113 `pap-d042355fa4845796808fa256` 拥有 `body.p1307-p1308`。`body.p1293`、`body.p1294`和 `body.p1309` 是全局无owner空白分隔，只作精确排除，不转移所有权。
- 父级初步判断：十二项拥有来源不形成独立可核验的受试者筛选、基线、随机或给药前动作。这一零候选结论必须由逐条原文处置证明，不得仅以“参考文献”章节名得出。

## Authorized Write Scope

- Worker02仅可创建或修改：
  - `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package112_reference_list_evidence_authority_boundary.v1.json`
  - `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice61cy-package112-reference-list-evidence-authority-boundary-parent-checklist.md`
  - `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61cy_package112_reference_list_evidence_authority_boundary.py`
  - 由上述配置乾跑生成的 `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n-prepare/d001-ii-package112-reference-list-evidence-authority-boundary/`
- Worker01、Worker03、Worker04只读，除runner托管的各自报告外不得写任何工作区文件。
- 不授权修改共享解析器、冻结计划、覆盖清单或Package111/113产物。如果确证需要共享修正，停止写入并向Codex报告可复现证据。
- 所有产物必须保持 `claims_complete=false`；不调用临床语义模型，不发布控制点，不进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. worker_01：只读核对冻结计划Package112身份、12项拥有来源原文、38项只读语境及Package111/113边界；逐项判断文献题录与方案正文控制的权威层级。
2. worker_02：在Package112授权路径内创建最小配置、父级临床清单和专项回归，运行模型外dry-run；不得从参考文献题录自由生成受试者阈值、量表算法或执行程序。
3. worker_03：只读独立攻击Package112来源闭包、文献/正文权威分层、题录原子化及相邻包边界；寻找引用题名候选化、正文要求丢失、参数臆造、Package111/113吸收和空白结构未处置等漏洞。
4. worker_04：待父级复核后只读验收实际工件；复跑专项、Package103-112和共享语义回归及dry-run，核对所有权、38项语境隔离、Package111/113不吸收、文献题录不反向生成控制、每项处置有原文依据、claims_complete=false及无跨包污染。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
