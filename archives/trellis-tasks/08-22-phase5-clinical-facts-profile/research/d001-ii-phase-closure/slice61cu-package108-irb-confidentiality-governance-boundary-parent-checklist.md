# Slice61cu Package 108 IRB/EC与参与者保密治理边界 Parent Checklist

## 1. 执行身份与冻结边界

- Task: `phase5-slice61cu-20260830`
- Group: `d001-ii-package108-irb-confidentiality-governance-boundary`
- Frozen plan: `papl-e17d498106b6f71f440ff2be`
- Package 108: `pap-f3fa399755a65a5a57ba306c`
- Selected phase: `phase_ii`
- Protocol SHA-256: `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- Frozen plan SHA-256: `92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4`
- Structure blob SHA-256: `3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d`

本执行只做模型外来源闭包、源文驱动的 IRB/EC 与保密语义分层处置、Package 107/109
边界隔离、确定性 batch/prompt 干跑和专项测试。不得调用临床语义模型，不得发布 control point，
不得进入受试者、OCR、Patient Profile、浏览器或视觉流程。所有产物必须保持
`claims_complete=false`；`parent clinical acceptance` 仍由 Codex 决定。

## 2. Package 108 的唯一 owned 闭包与只读边界

冻结计划中 Package 108 严格且仅拥有以下十个来源单元，按原始文档顺序恢复：

1. `body.p1260` — `机构审查委员会或伦理委员会`，小节标题，仅结构来源。
2. `body.p1261` — 研究启动前方案、知情同意书、提供给参与者的任何信息及相关支持信息须提交 IRB/EC 审查批准；参与者招募材料也必须经 IRB/EC 批准。
3. `body.p1262` — 主要研究者按 IRB/EC 要求每年或更频繁提交书面研究进展报告，并及时通知方案修正案。
4. `body.p1263` — 除向申办者报告 SAE 外，适用时还须向卫生主管部门和 IRB/EC 报告 SAE；审查处理申办者安全性报告或通信并存档。
5. `body.p1264` — `保密`，小节标题，仅结构来源。
6. `body.p1265` — 研究中心对采集信息保密；参与者通过唯一识别号参与，姓名不出现在传输数据集。
7. `body.p1266` — 医疗信息保密；除非法律允许或要求，仅在签署的知情同意书允许或单独授权使用和披露个人健康信息时才可能向第三方披露。
8. `body.p1267` — 信息妥善保管、仅研究者或授权人员可查看、数字字母编号；监查/稽查/EC/IRB 审核可审查个人医疗记录；法律允许范围内保护隐私。
9. `body.p1268` — 医疗信息可能向私人医生或其他治疗相关医疗人员提供；探究性生物标志物样本数据通常不向研究者或参与者返还（除非法律要求）。
10. `body.p1269` — 研究生成数据必须接受国家/地方卫生监管机构代表、申办者监查员、研究中心代表、合作者和 IRB/EC（如适用）检查。

`attached_source_refs=[]`。冻结计划中的 37 项 `context_units` 仅只读，未经 Codex 另行授权不得升格为附加来源。Package 107 止于 `body.p1259`；Package 109 从 `body.p1270` 开始，不得吸入。

## 3. 先读源文，再区分五类语义

### 3.1 研究启动及持续伦理治理

- p1260 只提供 IRB/EC 小节结构。
- p1261 的“研究启动前”是研究级启动门槛：方案、ICF、参与者信息材料与支持信息的 IRB/EC 批准，以及参与者招募材料审批。
- p1262 是年度或更频繁进展报告与方案修正案通知的持续伦理治理。
- 严禁把伦理报批、招募材料审批或年度进展误成单例资格；也不得把“研究启动前”误读为受试者筛选前资格。

### 3.2 SAE / 安全通信治理

- p1263 保留向卫生主管部门和 IRB/EC 报告 SAE，以及审查处理并存档申办者安全性报告或通信。
- SAE 上报与安全通信治理不得改写为单例入排不通过。

### 3.3 隐私授权与信息访问治理

- p1265 是唯一识别号与传输数据集去名的编码/资料保密治理。
- p1266 是第三方披露的法律/ICF/单独 PHI 授权条件；“签署的知情同意书允许”是披露前提，不是本包新的筛选前签署动作，也不得重复第 67/107 包知情签署控制。
- p1267 是编码化、受限访问与监查/稽查/EC/IRB 审核访问治理。

### 3.4 私人医生披露、探索性结果不返还与监管检查

- p1268 保留向私人医生或其他治疗相关医疗人员披露的可能性，以及探究性生物标志物结果通常不返还。
- p1269 是监管机构、监查员、研究中心代表、合作者和 IRB/EC 检查边界。
- 上述内容不得误成筛选/基线必做或入排不通过。

### 3.5 候选处置结论

完成源文判断后确认：本包十项来源均未形成独立的“真实参加研究前可核验受试者动作”。

- p1260、p1264 维持结构来源；
- p1261-p1263、p1265-p1269 维持 `non_enrollment_execution`；
- `required_candidate_source_refs=[]`，`pre_enrollment_source_refs=[]`；
- 全部十项进入 `forbidden_candidate_source_refs`；
- 零候选不是预设，而是逐项原文依据后的结论；若后续发现真实前置控制被丢失，必须停止并回退。

因此不得把伦理报批、年度进展、SAE 上报、资料保密、隐私授权、监查稽查、结果不返还或监管检查误成单例资格，也不得用 `other_control_candidate` 强挂受试者工作流。

## 4. 配置盲检

配置文件：
`configs/representative_group_package108_irb_confidentiality_governance_boundary.v1.json`

配置必须满足：

- `owned_source_refs` 恰为 p1260-p1269；`attached_source_refs=[]`；
- `required_candidate_source_refs=[]`；十个来源均位于 `forbidden_candidate_source_refs`；
- `structural_only_source_refs` 恰为 p1260、p1264；
- p1261-p1263、p1265-p1269 为 `non_enrollment_execution`；
- workflow / procedure / action / visit 绑定为空；`known_targets.official_rules` 与 `required_procedures` 均为空；
- exception_semantics / clinical_qc 完整保留五类语义与 Package 107/109 边界；
- p1259 owner=107，p1260-p1269 owner=108，p1270 owner=109；
- 37 项语境中无主项精确写入 `unowned_context_source_refs`；
- `claims_complete` 只能为 `false`。

## 5. 所有权、期别与源文回归

- 覆盖清单 p1260-p1269 的 `study_phase` 均为 `phase_ii`、`phase_scopes` 均为 `unknown`、
  `unit_kind` 均为 `paragraph`，source order 为
  `31230, 31240, 31250, 31260, 31270, 31280, 31290, 31300, 31310, 31320`。
- 每个 owned 来源的 `source_span_ids` 和 `member_source_refs` 必须各自只含对应 paragraph。
- 37 项 context_units 与 owned 不相交，且不得作为本包候选、workflow binding、官方规则或必需程序来源。
- Package 107 的 p1251-p1259 与 Package 109 的 p1270 及以后内容不得出现在本包 owned/attached 或 dry-run prompt 声明来源中。

## 6. 确定性模型外 dry-run 与预期证据

在仓库根目录运行：

```bash
.venv/bin/python \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py \
  --config \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package108_irb_confidentiality_governance_boundary.v1.json \
  --dry-run
```

预期观察：

- `owned_count=10`、`attached_count=0`、`unit_count=10`，`claims_complete=false`；
- `source_rows.json` 按 p1260-p1269 顺序包含十项，全部 `role=owned` 且解析到 Package 108；
- `execution/batch.json` 的 owned IDs 只有 p1260-p1269；structural-only 为 p1260/p1264；
  pre-enrollment 为空；official rules 与 required procedures 为空；
- `execution/prompt.txt` 只出现 p1260-p1269 的声明来源和逐字源文，不出现 p1259 回吸或 p1270 提前吸收；
- `clinical-qc.json` 的所有 `agent_candidates` 仍为空，gate 标记为 dry-run skipped；零候选是源文判断结论，不是未水合借口。

## 7. 回归命令与停止条件

专项回归：

```bash
.venv/bin/python -m pytest -q \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61cu_package108_irb_confidentiality_governance_boundary.py
```

父级允许的相邻包回归由 Codex 在合并后执行。任一来源 SHA、frozen owner、source order、
phase scope、原文摘录、五类语义分层、零候选逐项依据、或 Package 107/109 隔离失败时，停止并深挖。
本 worker 未被授权修改共享代码；若出现共享代码阻塞，只报告可复现证据。

## 8. Codex 独立最终检查

本 checklist 只证明模型外准备闭包、源文驱动的 IRB/EC 与保密边界处置和确定性回归路径。它不证明：

- 临床候选内容已由模型解析或接受；
- publication gate、clinical QC 或 parent clinical acceptance 已通过；
- D001 全量来源、受试者档案、Patient Profile 或浏览器流程已完成；
- 真实资料中的 IRB/EC 批准、招募材料、SAE 上报、保密授权或监管检查已经验证；
- 真实受试者已经完成任何参加研究前控制。

最终判定必须由 Codex 依据冻结来源、干跑证据、专项及相邻包回归和 parent clinical gates 另行完成。
