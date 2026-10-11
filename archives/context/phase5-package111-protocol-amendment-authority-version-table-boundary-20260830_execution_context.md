# Execution Context: phase5-package111-protocol-amendment-authority-version-table-boundary-20260830

Created: 2026-08-30 20:12:23 CST
Objective: 在D001 II期当前不可变131包计划中，完成Package111 body.p1291、body.p1292和body.t15.r0-r1的方案修订授权与版本表语义闭环；保留方案/现行修订案的权威变更机制，区分V1.0初始版本记录与实际修订，不把申办者、主要研究者及伦理委员会的治理义务误成受试者级入排条件，保持Package110/112边界，产出最小配置、父级临床清单、确定性回归、独立攻击验收和可恢复记录，不进入临床语义模型发布、受试者、OCR、Patient Profile、浏览器或视觉阶段。
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

- 当前任务与可恢复状态：`.trellis/tasks/08-22-phase5-clinical-facts-profile/task.json`、`.trellis/tasks/08-22-phase5-clinical-facts-profile/implement.md`、`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE110_DATA_PUBLICATION_COMMERCIAL_SECRET_GOVERNANCE_BOUNDARY_ACCEPTED.md`。
- 当前不可变计划：`artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/frozen_phase_plan.json`，plan id `papl-e17d498106b6f71f440ff2be`，Package111 id `pap-214ce50fd89fb1998521c4c3`。
- 当前覆盖清单：`artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/coverage_manifest.json`。
- 结构化方案原文：`artifacts/phase5-slice58r6-d001-phase-handoff-atomization-20260827/structure/blobs/protocol_blocks/3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d.json`。
- 模型外准备器：`.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py`。
- 相邻可复用范式：Package109/110的配置、父级清单、专项测试及乾跑产物；它们只是实现模式，不是Package111临床语义的替代来源。
- 不得读取本工作区之外的原始临床资料，不得修改任何源方案、原始受试者文件或旧项目报告。

## Frozen Package 111 Boundary

- Package111严格且仅拥有四个结构单元：`body.p1291`、`body.p1292`、`body.t15.r0`、`body.t15.r1`；`attached_source_refs=[]`。
- `body.p1291`：标题“方案修订”，只提供结构和权威语境。
- `body.p1292`：“方案任何的必须的改变，都需以方案修订形式进行，并需在获得申办者、主要研究者签字同意后提交伦理委员会审批或备案。”
- `body.t15.r0`：版本表表头，单元文本由`body.t15.r0.c0.p0-r0.c3.p0`组装：“版本”、“日期”、“变更说明”、“简要理由”。
- `body.t15.r1`：版本表数据行，单元文本由`body.t15.r1.c0.p0-r1.c3.p0`组装：“V1.0”、“2025年12月10日”、“NA”、“NA”。该行只证明当前初始版本及日期，不证明存在历史修订、变更内容或修订理由。
- 37个`context_units`全部只读：26个全局无owner，11个由Package45/46/47/48/50/75拥有；不得升格为本包附加来源或候选条件。
- Package110止于`body.p1290`；`body.p1293-p1294`是全局无owner的空白分隔；Package112 `pap-fa6b2b871b90b62bbfe81775`从`body.p1295`“参考文献”开始。不得跨包吸收。
- 父级初步判断：方案修订是授权的标准变更机制，应保留为项目级方案权威/版本治理语义；该包四项原文未形成独立可核验的受试者筛选、基线、随机或给药前动作。这一零候选结论仍必须由逐条原文复核证明，不得以章节标题或预设候选数直接得出。

## Authorized Write Scope

- Worker02仅可创建或修改：
  - `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package111_protocol_amendment_authority_version_table_boundary.v1.json`
  - `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice61cx-package111-protocol-amendment-authority-version-table-boundary-parent-checklist.md`
  - `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61cx_package111_protocol_amendment_authority_version_table_boundary.py`
  - 由上述配置乾跑生成的`.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n-prepare/d001-ii-package111-protocol-amendment-authority-version-table-boundary/`
- Worker01、Worker03、Worker04只读，除runner托管的各自报告外不得写任何工作区文件。
- 不授权修改共享解析器、冻结计划、覆盖清单或Package109/110产物。如果确证需要共享修正，停止写入并向Codex报告可复现证据。
- 所有产物必须保持`claims_complete=false`；不调用临床语义模型，不发布控制点，不进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 只读核对当前重基线冻结计划Package111身份、四项拥有来源的完整原文、37项只读语境及Package110/112边界；逐项判断修订签署/伦理审批治理、版本表头与V1.0初始记录是否形成任何参加研究前动作，不修改文件。
2. 在父级精确授权路径内创建Package111配置、父级临床清单、专项确定性回归并运行模型外dry-run；必须保留方案修订作为唯一授权标准变更形式，不得把V1.0/NA臆造为既往修订，也不得把申办者、主要研究者、伦理委员会义务候选化为受试者资格。
3. 独立攻击审阅Package111来源闭包、方案修订权威、版本表头/数据行原子化和相邻包边界；只读输出，重点寻找修订权威丢失、V1.0误读为修订、治理义务候选化、表头数据混淆、Package110/112跨包吸收等漏洞。
4. 待父级完成来源与临床语义复核后，独立验收实际文件：复跑专项、相邻包和共享语义回归及dry-run，核对所有权、37项语境隔离、Package110/112未吸收、方案修订权威与V1.0初始版本区分、每个零候选或候选处置均有逐项原文依据、claims_complete=false、中文临床语义和无跨包污染；只读输出。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
