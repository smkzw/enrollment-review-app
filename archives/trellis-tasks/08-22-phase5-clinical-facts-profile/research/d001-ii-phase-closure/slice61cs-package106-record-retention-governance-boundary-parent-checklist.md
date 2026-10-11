# Slice61cs Package 106 记录/文件保存治理边界 Parent Checklist

## 1. 执行身份与冻结边界

- Task: `phase5-slice61cs-20260830`
- Group: `d001-ii-package106-record-retention-governance-boundary`
- Frozen plan: `papl-e17d498106b6f71f440ff2be`
- Package 106: `pap-2bfe896140d41556d48a5132`
- Selected phase: `phase_ii`
- Protocol SHA-256: `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- Frozen plan SHA-256: `92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4`
- Structure blob SHA-256: `3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d`

本执行只做模型外来源闭包、源文驱动的记录保存治理处置、所有权/只读交叉引用
回归、确定性 batch/prompt 干跑和专项测试。不得调用临床语义模型，不得发布 control point，
不得进入受试者、OCR、Patient Profile、浏览器或视觉流程。所有产物必须保持
`claims_complete=false`；`parent clinical acceptance` 仍由 Codex 决定。

## 2. Package 106 的唯一 owned 闭包与只读交叉来源

冻结计划中 Package 106 严格且仅拥有以下三个来源单元，按原始文档顺序恢复：

1. `body.p1248` — `记录/文件的保存`，章节标题，仅结构来源。
2. `body.p1249` — GCP/法律法规下的临床研究文件保存和管理；保存期限分别以
   试验药物获批上市和临床试验结束为锚点，各至少五年并取较长者；研究文件应
   便于日后访问和数据溯源；研究中心/申办者负责保存，申办者/研究者/临床试验
   机构确认场所和条件。
3. `body.p1250` — 研究文件转移、保管人变更和销毁等均须申办者书面许可。

`body.p1247` 属于 Package 105 的 owned 来源，本包允许且只允许将其作为
`attached_source_refs` 的只读交叉引用，以闭合其对第 9.4 节记录保存要求的
引用语境。p1247 不得转移所有权、成为本包 owned 来源、吸收 p1248-p1250
的保存期限/责任主体/书面许可，或生成本包候选。

Package 105 的其他来源、Package 104 的 `body.p1236`、
`body.p1237#atom-0-15`、`body.p1237#atom-15-100`、
`body.p1237#atom-160-208`、无所有权的
`body.p1237#atom-100-160`，以及 `body.p537`、`body.p1210`、`body.p1223`
均不得附加到本包。Package 107 从 `body.p1251` 开始拥有伦理/知情同意内容，
p1251 及其后内容不得吸入第106包。

## 3. 先读源文，再决定候选处置

### 3.1 逐条源文判断，不预设零候选

不得因为“记录/文件的保存”是章节标题就预设零候选；必须先核对每个来源的
责任主体、动作对象、适用人群、时间锚点、许可条件和执行阶段：

- p1248 只提供小节标题和结构归属，不表达独立保存动作或受试者条件。
- p1249 的对象是临床研究文件，主体分别为研究中心和申办者（保存责任），
  以及申办者、研究者和临床试验机构（确认保存场所和条件）。保存期限不是
  两个期限任选其一，而是“试验药物被批准上市后至少5年”和“临床试验结束
  后至少5年”两个事件锚点分别计算后取较长者；研究文件还应合理保存以便日后
  访问或数据溯源。
- p1250 的对象是研究文件转移、保管人变更、研究文件销毁等保管治理动作，
  每项均必须得到申办者的书面许可。
- p1247 的主体和对象属于 Package 105 源文件保全/访问治理；本包只读引用
  其第9.4节交叉语境，不改变 p1247 的 owner 或处置。

上述来源没有受试者级人群、入排条件、阈值或筛选/基线/D1给药前动作。因此在
完成源文判断后，才确认本包 `required_candidate_source_refs=[]`，而不是预设
零候选。不得使用 `other_control_candidate` 强行把研究文件保存治理挂到受试者
工作流。

### 3.2 研究文件治理与受试者控制严格分开

- p1249、p1250 的预期处置为 `non_enrollment_execution`；它们约束研究文件
  保存、访问/溯源、场所条件、责任主体和书面许可，不生成受试者动作，也不绑定
  筛选、基线或 D1 给药前审核节点。
- p1248 是 `structural_only_source_refs`，仅提供章节结构，不生成候选、官方
  规则、必需程序或流程节点。
- p1247 是 Package 105 的只读附加来源；它仅帮助理解第9.4节交叉引用，不是
  Package 106 的保存期限或许可规则来源。
- 研究文件治理可能影响后续证据可访问性、数据溯源和证据 QC，但保存期限、
  场所条件、访问状态或许可状态不能自动变成某名受试者资料缺失、筛选/基线
  不通过、不得入组或发布控制点。

### 3.3 必须保留的保存期限逻辑与责任主体

- 保存截止必须表达为两个独立事件锚点的最大值：
  `max(试验药物被批准上市日期 + 至少5年, 临床试验结束日期 + 至少5年)`。
- 不得把“以较长时间为准”改成两个期限任选其一、较早日期优先或任一锚点
  未知时仍宣称保存义务已结束。
- “研究中心和申办者应保存研究必备文件”与“申办者、研究者和临床试验机构
  应当确认均有保存场所和条件”是两个责任主体集合；不得合并、遗漏或互换。
- p1250 的研究文件转移、保管人变更、研究文件销毁等均须申办者书面许可；
  不得弱化为口头同意、一般知会，或替换为研究者、伦理委员会、监管机构许可。

### 3.4 必须禁止的受试者级倒置

p1247-p1250 均位于 `forbidden_candidate_source_refs`，禁止生成或绑定：

- 筛选必做、基线必做、入组前必查、不得入组、排除标准、入排不通过或发布
  控制点；
- “保存期限不足”“研究文件未保存”“保存场所和条件不足”“不能直接访问
  源文件”“转移/保管人变更/销毁未获申办者书面许可”作为单例资格结论；
- 将研究中心、申办者、研究者、临床试验机构、IRB/EC或监管当局的研究文件
  治理责任变成受试者义务；
- 将 p1247 第9.4节引用倒置为本包拥有 p1248-p1250，或把 p1251 起伦理/
  知情同意内容吸入本包；
- 以 `other_control_candidate`、workflow binding、required procedure
  或受试者动作元数据绕过研究级/受试者级层级边界。

## 4. 配置盲检

配置文件：
`configs/representative_group_package106_record_retention_governance_boundary.v1.json`

配置必须满足：

- `owned_source_refs` 恰为 `body.p1248`、`body.p1249`、`body.p1250`；
  `attached_source_refs` 恰为 Package 105 的 `body.p1247`，且 attachment 只读；
- `required_candidate_source_refs=[]`；四个声明来源（p1247-p1250）全部位于
  `forbidden_candidate_source_refs`；
- `structural_only_source_refs` 恰为 `body.p1248`，
  `attached_structural_only_source_refs=[]`；
- p1249、p1250 的预期处置均为 `non_enrollment_execution`；
- `expected_workflow_stage_ids_by_source_ref`、`pre_enrollment_source_refs`、
  `known_targets.official_rules`、`known_targets.required_procedures` 和
  `owned_required_action_kinds_by_source_ref` 均为空；
- `candidate_required_markers_by_source_ref` 为空；逐字来源保真由冻结覆盖清单
  和 source-row 回归负责，研究文件治理倒置由每来源 forbidden markers 负责；
- 配置中的保存期限最大值、未知锚点、研究中心/申办者保存责任、申办者/研究者/
  临床试验机构场所条件确认责任、p1250 三类保管动作及申办者书面许可语义完整；
- p1247 的 owner 仍为 105，p1248-p1250 的 owner 仍为 106，p1251 起的
  伦理/知情同意内容不进入配置；
- `claims_complete` 只能为 `false`，不得宣称 D001 全量、受试者、Patient
  Profile 或 Codex clinical acceptance 完成。

## 5. 所有权、期别与源文回归

- 覆盖清单 p1247-p1250 的 `study_phase` 均为 `phase_ii`、`phase_scopes`
  均为 `unknown`、`unit_kind` 均为 `paragraph`，source order 为
  `31100, 31110, 31120, 31130`。
- p1248-p1250 的 `source_span_ids` 和 `member_source_refs` 必须各自只含
  对应 paragraph source ref；p1247 附加行保留其 Package 105 的结构身份和逐字
  excerpt。
- p1249 必须逐字保留 GCP/法律法规、研究中心/申办者、两个保存期限、以较长
  时间为准、日后访问/数据溯源、申办者/研究者/临床试验机构、保存场所和条件。
- p1250 必须逐字保留研究文件的转移、保管人的变更、研究文件的销毁、申办者的书面许可。
- Package 105 的 p1247 owner 保持为 105；Package 106 的 p1248-p1250 owner
  保持为 106；Package 107 从 p1251 起的伦理/知情同意 owner 不得提前吸收。
- p537、p1210、p1223、p1237#atom-100-160 没有所有权，不能作为本包候选、
  workflow binding、官方规则或必需程序来源。

## 6. 确定性模型外 dry-run 与预期证据

在仓库根目录运行：

```bash
.venv/bin/python \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py \
  --config \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package106_record_retention_governance_boundary.v1.json \
  --dry-run
```

预期观察：

- `owned_count=3`、`attached_count=1`、`unit_count=4`，`claims_complete=false`；
- `source_rows.json` 按 p1247-p1250 顺序包含四项：p1247 为
  `role=attached` 且仍通过 `frozen_plan_owned` 解析到 Package 105，p1248-p1250
  为 `role=owned` 且解析到 Package 106；
- `execution/batch.json` 的 owned IDs 只有 p1248-p1250，context IDs 只有 p1247；
  structural-only 只有 p1248；pre-enrollment、workflow binding、official rules、
  required procedures、受试者 action 映射均为空；
- `execution/prompt.txt` 只出现 p1247-p1250 的声明来源和逐字源文，不出现
  p1251、p1236/p1237、p537、p1210、p1223 或其他未声明来源；p1247 只在 prompt
  context 出现，不进入 owned manifest；
- `clinical-qc.json` 的所有 `agent_candidates` 为空，gate 标记为 dry-run
  skipped，不能解释为临床验收通过；
- 保存期限和责任主体/书面许可只作为模型外配置、QC和测试语义保留，不误报为
  受试者控制点；不产生 hydrated Agent output、control catalog 或发布结果。

## 7. 回归命令与停止条件

专项回归：

```bash
.venv/bin/python -m pytest -q \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61cs_package106_record_retention_governance_boundary.py
```

父级允许的相邻包/共享回放回归由 Codex 在合并后执行；本专项不得修改共享
回放帮助程序或应用代码。任一来源 SHA、frozen owner、p1247 只读角色、source
order、phase scope、原文摘录、保存期限最大值、责任主体、书面许可、候选处置或
Package 105/107 隔离失败时，停止并回报 Codex；不得通过扩大上下文、猜测 owner、
把记录保存治理义务变成候选，或修改冻结证据来“修复”。

## 8. Codex 独立最终检查

本 checklist 只证明模型外准备闭包、源文驱动的记录保存治理处置和确定性回归
路径。它不证明：

- 临床候选内容已由模型解析或接受；
- publication gate、clinical QC 或 parent clinical acceptance 已通过；
- D001 全量来源、受试者档案、Patient Profile 或浏览器流程已完成；
- 真实资料中的研究文件保存、访问、溯源、场所条件或书面许可已经验证；
- 任一保存期限、研究责任主体、保管变更许可或证据可访问性义务已经成为受试者
  级控制点。

最终判定必须由 Codex 依据冻结来源、干跑证据、专项及相邻包回归和 parent
clinical gates 另行完成。
