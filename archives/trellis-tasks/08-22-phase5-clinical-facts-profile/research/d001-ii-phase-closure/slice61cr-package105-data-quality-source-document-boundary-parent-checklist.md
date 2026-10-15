# Slice61cr Package 105 数据质量、eCRF与源数据/源文件边界 Parent Checklist

## 1. 执行身份与冻结边界

- Task: `phase5-slice61cr-20260830`
- Group: `d001-ii-package105-data-quality-source-document-boundary`
- Frozen plan: `papl-e17d498106b6f71f440ff2be`
- Package 105: `pap-b8d5cdfbc6ac4c373c6576b3`
- Selected phase: `phase_ii`
- Protocol SHA-256: `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- Frozen plan SHA-256: `92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4`
- Structure blob SHA-256: `3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d`

本执行只做模型外来源闭包、源文驱动的候选处置判断、所有权回归、确定性
batch/prompt 干跑和回归测试。不得调用临床语义模型，不得发布 control point，
不得进入受试者、OCR、Patient Profile、浏览器或视觉流程。所有产物必须保持
`claims_complete=false`；`parent clinical acceptance` 仍由 Codex 决定。

## 2. Package 105 的唯一 owned 闭包

冻结计划中 Package 105 只能拥有以下十个来源单元，且按原始文档顺序恢复：

1. `body.p1238` — `数据采集与管理`，章节标题，仅结构来源。
2. `body.p1239` — `数据质量保证`，章节标题，仅结构来源。
3. `body.p1240` — 申办者/研究中心的数据管理、eCRF手动录入、数据质疑解决和中心实验室电子传输。
4. `body.p1241` — `电子病例报告表（eCRF）`，章节标题，仅结构来源。
5. `body.p1242` — 经验证EDC、指定eCRF、中心培训/手册、提交、工作人员完成、研究者审查、电子签名和日期。
6. `body.p1243` — `源数据/源文件`，章节标题，仅结构来源。
7. `body.p1244` — 源文件/源数据定义、原始医学记录及核证副本等来源类型例示。
8. `body.p1245` — 研究开始前监查计划定义源文件类型，以及直接输入eCRFs且无既有记录的数据视为源数据。
9. `body.p1246` — 源数据准确、清晰、同期、原始、可归因，电子记录/签名合规、核证副本和审核跟踪。
10. `body.p1247` — 验证eCRF的源文件保全、记录保存引用、申办方/IRB/EC/监管直接访问与检查。

Package 104 的 `body.p1236`、`body.p1237#atom-0-15`、
`body.p1237#atom-15-100`、`body.p1237#atom-160-208` 不得迁入；
`body.p1237#atom-100-160` 仍无所有权。Package 106 的
`body.p1248`、`body.p1249`、`body.p1250` 不得因 p1247 对第9.4节的引用而迁入。

本包不附加来源：冻结计划列出的广泛 context units 是只读发现上下文，不是自动
prompt 附件。没有具体未解决语义需要附加上下文时，不为增加数量而附加
Package 104、Package 106 或无所有权来源。

## 3. 先读源文，再决定候选处置

### 3.1 逐条源文判断，不预设零候选

不得沿用 Package 104 的零候选结论，也不得因为本章标题是“数据管理”就预设
零候选。必须先核对每个语义来源的责任主体、动作对象、适用人群、条件、阈值和
执行阶段：

- p1240 的主体是申办方、研究中心和中心实验室，内容是数据管理、质量检查、eCRF录入、质疑澄清/EDC解决和电子传输。
- p1242 的主体是研究中心、培训指定工作人员、研究者/指定人员，内容是EDC、培训、eCRF提交/完成/审查/电子签名/日期。
- p1244 的内容是来源类别和定义，不规定某名受试者的资料清单。
- p1245 的主体是研究监查计划和研究启动治理；直接eCRF输入数据的“源数据”是来源分类规则。
- p1246 的主体是研究者、电子记录系统和核证副本/审核跟踪，内容是证据质量与可归因性。
- p1247 的主体是研究者、机构、申办方、IRB/EC和监管当局，内容是源文件保存、监查/稽查/检查直接访问。

上述内容没有受试者级人群、入排条件、阈值或筛选/基线/D1给药前动作；因此在完成
源文判断后，才确认本包 `required_candidate_source_refs=[]`，而不是预设零候选。
不得使用 `other_control_candidate` 强行把研究执行或资料治理挂到受试者工作流。

### 3.2 研究执行与证据接受边界分开

- p1240、p1242、p1245、p1246、p1247 的研究者/申办方/机构/系统责任处置为
  `non_enrollment_execution`，不生成受试者动作，也不绑定审核节点。
- p1244 的来源类别和定义处置为 `supporting_or_supplement`，作为证据溯源/QC
  词汇，不自动创建受试者资料要求。
- p1244-p1247 的源类型、源数据定义、准确清晰同期原始可归因、电子签名、核证
  副本、审核跟踪、保存和直接访问可影响后续证据QC与溯源提示；它们不自动成为
  受试者缺失事实、入排失败、排除标准或控制点。
- p1245 仅定义研究启动期的源文件分类和直接录入eCRF数据的来源属性；不得保留
  `collect_data` 受试者动作元数据，以免将研究级数据治理误投影为筛选资料要求。

### 3.3 必须禁止的受试者级倒置

所有十个来源均为 `forbidden_candidate_source_refs`，禁止生成或绑定：

- 筛选必做、基线必做、入组前必查、不得入组、排除标准、入排不通过或发布控制点；
- “数据质疑未解决”“EDC不一致”“培训/eCRF未完成或未签名”“源文件缺失/未保存/不可访问”“核证副本不合格”“审核跟踪缺失”作为单例资格结论；
- 把申办方、研究中心、研究者、机构、IRB/EC或监管当局的研究治理责任变成受试者义务；
- 把 p1244 的参与者日记、病历、医学图像、实验室记录等例示来源改写为普遍必交材料；
- 把 p1247 对第9.4节的引用倒置为本包拥有 p1248-p1250 的保存期限或销毁许可。

## 4. 配置盲检

配置文件：
`configs/representative_group_package105_data_quality_source_document_boundary.v1.json`

配置必须满足：

- `owned_source_refs` 恰为 p1238-p1247 十项，`attached_source_refs` 为空；
- `required_candidate_source_refs` 为空，且十个 owned 来源全部位于
  `forbidden_candidate_source_refs`；
- `structural_only_source_refs` 恰为 p1238、p1239、p1241、p1243；
- p1240、p1242、p1245-p1247 的预期处置为 `non_enrollment_execution`；
  p1244 的预期处置为 `supporting_or_supplement`；
- `expected_workflow_stage_ids_by_source_ref`、`pre_enrollment_source_refs`、
  `known_targets.official_rules` 和 `known_targets.required_procedures` 均为空；
- `candidate_required_markers_by_source_ref` 为空；逐字来源保真由冻结覆盖清单
  和 source-row 回归负责，研究执行/证据治理倒置由每来源 forbidden markers 负责；
- `owned_required_action_kinds_by_source_ref={}`，本包不生成受试者资料采集动作；
- 配置中的源文判断、研究执行与证据接受边界、Package 104/106 隔离说明完整存在；
- `claims_complete` 只能为 `false`，不得宣称 D001 全量、受试者、Patient Profile
  或 Codex clinical acceptance 完成。

## 5. 所有权、期别与源文回归

- 覆盖清单 p1238-p1247 的 `study_phase` 均为 `phase_ii`、`phase_scopes` 均为
  `unknown`、`unit_kind` 均为 `paragraph`，source order 为 `31010, 31020, ..., 31100`。
- source excerpts 必须逐字保留：p1240 的申办方/研究中心/EDC/数据质疑/中心实验室
  传输关系；p1242 的经验证EDC、培训、eCRF审查签名日期；p1244 的源文件/源数据
  定义及核证副本；p1245 的研究监查计划与无既有记录的直接eCRF输入；p1246 的
  准确清晰同期原始可归因、电子记录/签名、核证副本、审核跟踪；p1247 的保全、
  第9.4节、监查/稽查/IRB/EC/监管访问。
- Package 103 的 p1224、p1235 所有权保持为 103；Package 104 四个 owned 原子
  保持为 104；Package 106 的 p1248-p1250 保持为 106。
- p537、p1210、p1223、p1237#atom-100-160 没有所有权，不能作为本包候选、
  workflow binding、官方规则或必需程序来源。

## 6. 确定性干跑与预期证据

在仓库根目录运行：

```bash
.venv/bin/python \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py \
  --config \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package105_data_quality_source_document_boundary.v1.json \
  --dry-run
```

预期观察：

- `owned_count=10`、`attached_count=0`、`unit_count=10`；
- `claims_complete=false`；不产生 hydrated Agent output、control catalog 或发布结果；
- `source_rows.json` 与 `clinical-qc.json` 按 p1238-p1247 顺序包含十项，全部
  `role=owned`、`lookup=frozen_plan_owned`；
- `execution/batch.json` 的 context IDs、official rules、required procedures、
  workflow binding、pre-enrollment 和 subject action 映射均为空；结构标题 IDs
  仅为 p1238、p1239、p1241、p1243，且没有受试者 action metadata；
- `execution/prompt.txt` 只出现 p1238-p1247 十项和逐字源文，不出现 p1236/p1237、
  p1248-p1250、p537、p1210、p1223 或其他未声明来源；
- QC gate 标记为 dry-run skipped，不能解释为临床验收通过；
- p1240/p1242/p1245-p1247 的预期非入组执行和 p1244 的 supporting/supplement
  处置只在模型外配置中记录，不能被误报为受试者控制点。

## 7. 回归命令与停止条件

```bash
.venv/bin/python -m pytest -q \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61cr_package105_data_quality_source_document_boundary.py
```

任一来源 SHA、frozen owner、source order、phase scope、原文摘录、责任主体/对象
判断、证据接受边界、候选处置、p1245 非受试者动作边界或 Package 104/106 隔离失败时，
停止并回报 Codex；不得通过扩大上下文、添加 workflow、猜测 owner、把数据治理
义务变成候选、把证据可接受性误报为入排失败，或修改冻结证据来“修复”。

## 8. Codex 最终检查

本 checklist 只证明模型外准备闭包、源文驱动的候选处置和确定性回归路径。它不证明：

- 临床候选内容已由模型解析或接受；
- publication gate、clinical QC 或 parent clinical acceptance 已通过；
- D001 全量来源、受试者档案、Patient Profile 或浏览器流程已完成；
- 源数据/源文件的质量属性已在真实资料中验证；
- 任何研究执行、证据保存、核证副本、审核跟踪或直接访问义务已经成为受试者级控制点。

最终判定必须由 Codex 依据冻结来源、干跑证据、回归测试和 parent clinical gates
另行完成。
