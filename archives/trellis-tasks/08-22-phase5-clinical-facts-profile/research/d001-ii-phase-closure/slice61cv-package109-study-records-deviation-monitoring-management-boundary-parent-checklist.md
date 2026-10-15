# Slice61cv Package 109 研究文件、方案偏离、现场监查与管理结构边界 Parent Checklist

## 1. 执行身份与冻结边界

- Task: `phase5-slice61cv-20260830`
- Group: `d001-ii-package109-study-records-deviation-monitoring-management-boundary`
- Frozen plan: `papl-e17d498106b6f71f440ff2be`
- Package 109: `pap-2101c87c43a5499476169b81`
- Selected phase: `phase_ii`
- Protocol SHA-256: `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- Frozen plan SHA-256: `92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4`
- Structure blob SHA-256: `3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d`

本执行只做模型外来源闭包、源文驱动的研究文件/方案偏离/现场监查/管理结构语义分层处置、Package 108/110
边界隔离、确定性 batch/prompt 干跑和专项测试。不得调用临床语义模型，不得发布 control point，
不得进入受试者、OCR、Patient Profile、浏览器或视觉流程。所有产物必须保持
`claims_complete=false`；`parent clinical acceptance` 仍由 Codex 决定。

## 2. Package 109 的唯一 owned 闭包与只读边界

冻结计划中 Package 109 严格且仅拥有以下十一个来源单元，按原始文档顺序恢复：

1. `body.p1270` — `研究文件、监查和管理`，章节标题，仅结构来源。
2. `body.p1271` — `研究文件`，小节标题，仅结构来源。
3. `body.p1272` — 研究者必须保存足够且准确的研究执行记录（含方案、修正案、知情同意书、IRB/EC与政府批准文件）；研究结束时可获得含完整稽查跟踪的参与者数据。
4. `body.p1273` — 研究开始时研究中心、分析检测单位、申办者三方各自建立研究文件档案管理；研究结束时监查员审核确认各方文件并妥善保存在临床研究档案卷宗。
5. `body.p1274` — `方案偏离`，小节标题，仅结构来源。
6. `body.p1275` — 方案所有要求必须严格执行；偏离须识别、记录、签字、通报伦理与申办者，并在统计总结中分析影响。
7. `body.p1276` — 偏离记入源文件并按伦理规定递交审查；严重方案偏离发生后应评估，必要时参与者退出研究。
8. `body.p1277` — `现场监查/检查`，小节标题，仅结构来源。
9. `body.p1278` — 申办者或授权代表监查研究数据、病历和 eCRFs；研究者允许卫生当局、监查员、代表、合作者及 IRB/EC 检查相关设施和记录。
10. `body.p1279` — `管理结构`，小节标题，仅结构来源。
11. `body.p1280` — 申办者项目管理能力；可使用 IWRS 进行参与者筛查和随机分组及药物申请/运输管理；样品运输前保存；eCRF/EDC 记录。

`attached_source_refs=[]`。冻结计划中的 37 项 `context_units` 仅只读，未经 Codex 另行授权不得升格为附加来源。Package 108 止于 `body.p1269`；Package 110 从 `body.p1281` 开始，不得吸入。

## 3. 先读源文，再区分四类语义

### 3.1 研究文件与档案/稽查跟踪治理

- p1270、p1271 只提供章节/小节结构。
- p1272 是研究执行记录保存与研究结束稽查跟踪数据治理。
- p1273 是研究开始档案建立与研究结束监查审核保存治理。
- 严禁把研究文件、稽查跟踪或档案管理误成单例资格。

### 3.2 方案偏离记录及严重偏离后在研退出处置

- p1274 只提供小节结构。
- p1275 保留偏离识别、记录、签字、通报与统计总结；“所有要求必须严格执行”不得脱离具体要求生成泛化单例入排控制。
- p1276 的“必要时，参与者需退出研究”是严重偏离发生并评估后的在研处置，不是筛选/基线排除标准，也不得凭“退出”二字倒置成参加研究前控制。

### 3.3 现场监查/检查与设施记录访问

- p1277 只提供小节结构。
- p1278 是现场监查/检查与设施、记录访问治理，不得误成单例资格。

### 3.4 管理结构与 IWRS/样品/EDC 基础设施用途

- p1279 只提供小节结构。
- p1280 描述项目管理、IWRS 筛查/随机/药物物流能力、样品运输前保存和 eCRF/EDC 记录能力。
- 上述是管理结构与基础设施用途，不等于该段新建筛选、随机、给药、样本或资料资格动作。

### 3.5 候选处置结论

完成源文判断后确认：本包十一项来源均未形成独立的“真实参加研究前可核验受试者动作”。

- p1270、p1271、p1274、p1277、p1279 维持结构来源；
- p1272、p1273、p1275、p1276、p1278、p1280 维持 `non_enrollment_execution`；
- `required_candidate_source_refs=[]`，`pre_enrollment_source_refs=[]`；
- 全部十一项进入 `forbidden_candidate_source_refs`；
- 零候选不是预设，而是逐项原文依据后的结论；若后续发现真实前置控制被丢失，必须停止并回退。

因此不得把研究文件、偏离记录、监查检查、研究管理或 IWRS 用途误成单例资格，也不得用 `other_control_candidate` 强挂受试者工作流，也不得丢失任何真实前置控制。

## 4. 配置盲检

配置文件：
`configs/representative_group_package109_study_records_deviation_monitoring_management_boundary.v1.json`

配置必须满足：

- `owned_source_refs` 恰为 p1270-p1280；`attached_source_refs=[]`；
- `required_candidate_source_refs=[]`；十一个来源均位于 `forbidden_candidate_source_refs`；
- `structural_only_source_refs` 恰为 p1270、p1271、p1274、p1277、p1279；
- p1272、p1273、p1275、p1276、p1278、p1280 为 `non_enrollment_execution`；
- workflow / procedure / action / visit 绑定为空；`known_targets.official_rules` 与 `required_procedures` 均为空；
- exception_semantics / clinical_qc 完整保留四类语义与 Package 108/110 边界；
- p1269 owner=108，p1270-p1280 owner=109，p1281 owner=110；
- 37 项语境中无主项精确写入 `unowned_context_source_refs`；
- `claims_complete` 只能为 `false`。

## 5. 所有权、期别与源文回归

- 覆盖清单 p1270-p1280 的 `study_phase` 均为 `phase_ii`、`phase_scopes` 均为 `unknown`、
  `unit_kind` 均为 `paragraph`，source order 为
  `31330, 31340, 31350, 31360, 31370, 31380, 31390, 31400, 31410, 31420, 31430`。
- 每个 owned 来源的 `source_span_ids` 和 `member_source_refs` 必须各自只含对应 paragraph。
- 37 项 context_units 与 owned 不相交，且不得作为本包候选、workflow binding、官方规则或必需程序来源。
- Package 108 的 p1260-p1269 与 Package 110 的 p1281 及以后内容不得出现在本包 owned/attached 或 dry-run prompt 声明来源中。

## 6. 确定性模型外 dry-run 与预期证据

在仓库根目录运行：

```bash
.venv/bin/python \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py \
  --config \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package109_study_records_deviation_monitoring_management_boundary.v1.json \
  --dry-run
```

预期观察：

- `owned_count=11`、`attached_count=0`、`unit_count=11`，`claims_complete=false`；
- `source_rows.json` 按 p1270-p1280 顺序包含十一项，全部 `role=owned` 且解析到 Package 109；
- `execution/batch.json` 的 owned IDs 只有 p1270-p1280；structural-only 为 p1270/p1271/p1274/p1277/p1279；
  pre-enrollment 为空；official rules 与 required procedures 为空；
- `execution/prompt.txt` 只出现 p1270-p1280 的声明来源和逐字源文，不出现 p1269 回吸或 p1281 提前吸收；
- `clinical-qc.json` 的所有 `agent_candidates` 仍为空，gate 标记为 dry-run skipped；零候选是源文判断结论，不是未水合借口。

## 7. 回归命令与停止条件

专项回归：

```bash
.venv/bin/python -m pytest -q \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61cv_package109_study_records_deviation_monitoring_management_boundary.py
```

父级允许的相邻包回归由 Codex 在合并后执行。任一来源 SHA、frozen owner、source order、
phase scope、原文摘录、四类语义分层、零候选逐项依据、或 Package 108/110 隔离失败时，停止并深挖。
本 worker 未被授权修改共享代码；若出现共享代码阻塞，只报告可复现证据。

## 8. Codex 独立最终检查

本 checklist 只证明模型外准备闭包、源文驱动的研究文件/偏离/监查/管理边界处置和确定性回归路径。它不证明：

- 临床候选内容已由模型解析或接受；
- publication gate、clinical QC 或 parent clinical acceptance 已通过；
- D001 全量来源、受试者档案、Patient Profile 或浏览器流程已完成；
- 真实资料中的研究文件、偏离记录、监查检查、IWRS 或 EDC 记录已经验证；
- 真实受试者已经完成任何参加研究前控制。

最终判定必须由 Codex 依据冻结来源、干跑证据、专项及相邻包回归和 parent clinical gates 另行完成。
