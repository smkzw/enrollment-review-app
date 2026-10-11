# Execution Context: phase5-package106-record-retention-governance-boundary-20260830

Created: 2026-08-30 18:11:29 CST
Objective: 在 D001 II期冻结候选计划中完成第106包 body.p1248-p1250 的记录文件保存治理语义闭环：严格保持第106包所有权，允许将第105包 p1247 作为只读交叉引用，保留保存期限取较长者、责任主体和书面许可原义，禁止将研究文件保存治理提升为单例受试者入排条件；产出最小配置、父级清单、确定性回归、独立验收和可恢复记录。
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

- 冻结候选计划：`artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/frozen_phase_plan.json`。计划身份必须为 `papl-e17d498106b6f71f440ff2be`；第106包必须为 `pap-2bfe896140d41556d48a5132`，且只拥有 `body.p1248-p1250`。
- 冻结覆盖清单：`artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/coverage_manifest.json`。
- 冻结结构块：`artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/structure/blobs/protocol_blocks/3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d.json`。
- 协议文件 SHA-256：`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`；研究期别为 `phase_ii`。
- 上一包已验收边界：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE105_DATA_QUALITY_SOURCE_DOCUMENT_BOUNDARY_ACCEPTED.md`、对应配置/清单/测试，以及共享模型外回放帮助程序 `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py`。
- 第106包逐字原文：`body.p1248` 为“记录/文件的保存”；`body.p1249` 为“临床研究文件需按照GCP等相关法律法规的要求进行保存和管理。研究中心和申办者应保存研究必备文件至试验药物被批准上市后至少5年或至临床试验结束后至少5年（以较长时间为准）。研究文件应合理保存，以便日后访问或数据溯源。申办者、研究者和临床试验机构应当确认均有保存临床试验必备文件的场所和条件。”；`body.p1250` 为“研究文件的转移、保管人的变更、研究文件的销毁等，必须得到申办者的书面许可。”
- `body.p1247` 由第105包拥有，只可作为第9.4节显式交叉引用的只读附加来源；不得迁移所有权、生成候选或改变其第105包处置。第107包从 `body.p1251` 开始，伦理/知情同意内容不得吸入第106包。
- 冻结计划中37项语境均为只读；除 `body.p1247` 外不得附加到第106包。不得读取或修改工作区外的原始临床资料、生产数据或旧项目。

## Authorized Implementation Files

- Worker 02 只可创建或修改：
  - `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package106_record_retention_governance_boundary.v1.json`
  - `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice61cs-package106-record-retention-governance-boundary-parent-checklist.md`
  - `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61cs_package106_record_retention_governance_boundary.py`
  - 由模型外 dry-run 在 `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n-prepare/d001-ii-package106-record-retention-governance-boundary/` 生成的标准回放产物。
- Worker 02 不得修改共享回放帮助程序、应用代码、其他包配置/测试、任务记录、review/metrics、runner 管理的报告或提示词。若专项测试复现共享根因，只在报告中给出证据和最小修复建议，由 Codex 决定。
- Worker 01、03、04 全部只读；不得修改任何文件。

## Semantic Acceptance Boundary

- `body.p1248` 仅为结构标题。`body.p1249-p1250` 属于研究文件保存、可访问/溯源、保管与销毁治理，预期不产生受试者候选、正式入排规则、流程必做项、受试者动作、访视或预筛选来源。
- 保存截止不是两个期限任选其一，而是 `max(试验药物获批上市日期+至少5年, 临床试验结束日期+至少5年)`；未知任一锚点时不得凭另一个较早期限声称保存义务已经结束。
- p1249 的保存责任主体为研究中心和申办者；保存场所和条件的确认主体为申办者、研究者和临床试验机构。不得合并、遗漏或互换主体。
- p1250 的研究文件转移、保管人变更和销毁均须得到申办者的书面许可；不得弱化为口头同意、一般知会，或替换为研究者/伦理委员会/监管机构许可。
- 记录保存问题可影响来源可访问性、数据溯源或未来证据质量，但不能自动转成某名受试者资料缺失、筛选/基线不通过或不得入组。
- 输出继续保持 `claims_complete=false`，不调用临床语义模型，不发布控制点，不进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

## Allowed Checks

- 使用项目 `.venv/bin/python` 运行 Package106 专项测试、Package103-106 相邻包及共享回放回归、模型外 dry-run 和 `git diff --check`。
- 不安装依赖，不访问互联网，不调用外部或本地临床语义模型。

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 只读核对冻结计划第106包身份、p1248-p1250逐字原文、37项语境、Package105/107边界，并判断p1247是否仅作为只读交叉引用附加；输出来源闭包和语义风险，不修改文件。
2. 在父级授权的精确路径内创建Package106配置、父级临床清单和专项回归测试，并运行模型外dry-run；只实现第106包记录保存治理边界，不修改共享代码，除非可复现的根因证明不可避免且先报告父级。
3. 独立攻击审阅Package106语义：重点检查至少五年与两个事件取较长者的合取/最大值语义、研究中心与申办者保存责任、申办者/研究者/机构场所条件确认责任、转移/保管人变更/销毁须申办者书面许可，以及任何资格倒置或跨包吸收。只读输出。
4. 待父级合并修正后独立验收实际文件：复跑专项及相邻包回归和dry-run，核对零候选、包身份、附加来源只读、claims_complete=false、中文临床语义和无跨包污染；只读输出。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
