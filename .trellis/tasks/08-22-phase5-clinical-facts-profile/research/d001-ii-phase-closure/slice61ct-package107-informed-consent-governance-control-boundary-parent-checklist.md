# Slice61ct Package 107 伦理与知情同意治理控制边界 Parent Checklist

## 1. 执行身份与冻结边界

- Task: `phase5-slice61ct-20260830`
- Group: `d001-ii-package107-informed-consent-governance-control-boundary`
- Frozen plan: `papl-e17d498106b6f71f440ff2be`
- Package 107: `pap-b119517783facd407b628e1e`
- Selected phase: `phase_ii`
- Protocol SHA-256: `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- Frozen plan SHA-256: `92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4`
- Structure blob SHA-256: `3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d`

本执行只做模型外来源闭包、源文驱动的伦理/知情同意语义分层处置、第67包控制去重、
Package 106/108 边界隔离、确定性 batch/prompt 干跑和专项测试。不得调用临床语义模型，
不得发布 control point，不得进入受试者、OCR、Patient Profile、浏览器或视觉流程。所有产物
必须保持 `claims_complete=false`；`parent clinical acceptance` 仍由 Codex 决定。

## 2. Package 107 的唯一 owned 闭包与只读边界

冻结计划中 Package 107 严格且仅拥有以下九个来源单元，按原始文档顺序恢复：

1. `body.p1251` — `伦理考虑`，章节标题，仅结构来源。
2. `body.p1252` — `遵守法律法规`，小节标题，仅结构来源。
3. `body.p1253` — 研究按 ICH E6、我国 GCP、赫尔辛基宣言、相关法律法规及伦理委员会审核意见执行。
4. `body.p1254` — 研究开始前伦理材料审阅批准；批准件后方可提供研究药物；增补/SAE 告知；进展报告；通讯副本；批准确认项；修订书面核准。
5. `body.p1255` — `知情同意`，小节标题，仅结构来源。
6. `body.p1256` — ICF（和研究方案一起）必须经伦理委员会审查及批准。
7. `body.p1257` — 口头和书面告知；无阅读能力时公正见证人；可理解解释；持续新信息告知与记录。
8. `body.p1258` — 最终 ICF 文本及其他资料应包含的模板内容清单。
9. `body.p1259` — 充分时间与机会；参与者或监护人与执行知情同意研究者分别签名并注明日期；非本人签署注明关系；双方各留存 1 份；重要新资料书面修改经伦理批准后再次同意。

`attached_source_refs=[]`。冻结计划中的 41 项 `context_units` 仅只读，未经 Codex 另行授权不得升格为附加来源。Package 106 止于 `body.p1250`；Package 108 从 `body.p1260`（机构审查委员会或伦理委员会）开始，不得吸入。第 67 包 `body.p768` 的筛选前解释与自愿签署权威只对照去重，不转移所有权。

## 3. 先读源文，再区分四类语义

### 3.1 研究级伦理治理

- p1251/p1252 只提供结构归属。
- p1253 是整项研究的伦理/法规合规框架，不是单例入排条件。
- p1254 是研究开始前与进行中的伦理委员会治理：材料批准、药物放行、增补/SAE 告知、进展报告、通讯副本、标题/编号/文件/日期确认、修订书面核准。
- 严禁把伦理报批状态误成单例资格。

### 3.2 ICF 文件治理与模板内容

- p1256 是 ICF 与方案一并伦理审查批准的文件治理。
- p1258 是最终 ICF 文本应含内容的模板清单。
- 严禁把 ICF 模板内容缺项误成单例资格、排除标准或入排不通过。

### 3.3 知情过程

- p1257 保留口头和书面两种告知、无阅读能力时公正见证人、可理解方式和措词、持续新信息告知与记录。
- 持续告知是过程义务，不得改写为单例入排不通过。
- 不得重复第 67 包已接受的“筛选前解释所有研究程序”。

### 3.4 签署与重新同意控制

- p1259 必须保留：充分的时间和机会；分别签名并注明日期；非本人签署注明关系；研究者与参与者各保留 1 份；重要新资料书面修改送伦理委员会批准后再次同意。
- 不得把这些过程控制丢失，也不得压缩成第 67 包已覆盖的通用自愿签署/筛选前签署知情同意书控制。

### 3.5 候选处置结论

完成源文判断后确认 p1257、p1259 同时包含“参加研究前可核验动作”和“研究进行期治理”，
不能按整段一律降为非入排执行：

- p1257 作为筛选期补充候选，保留口头与书面告知、无阅读能力时公正见证、可理解解释；
- p1259 作为筛选期补充候选，保留充分考虑时间、参与者或监护人与研究者分别签名并注明日期、非本人签署注明关系；
- 两项均关联第67包既有 `procedure:d001-icf-screening`，只发布既有流程未覆盖的动作，不重复通用解释或 `obtain_signature`；
- p1257 的持续新信息告知，以及 p1259 的双方留存、重要新资料后伦理批准与再次同意，仍按研究进行期治理保留，不强挂到筛选期候选；
- p1253、p1254、p1256、p1258 维持 `non_enrollment_execution`，标题维持结构来源。

因此 `required_candidate_source_refs=[body.p1257, body.p1259]`，其余七项进入
`forbidden_candidate_source_refs`。不得把研究治理候选化，也不得因去重而丢失独立的知情过程动作。

## 4. 配置盲检

配置文件：
`configs/representative_group_package107_informed_consent_governance_control_boundary.v1.json`

配置必须满足：

- `owned_source_refs` 恰为 p1251-p1259；`attached_source_refs=[]`；
- `required_candidate_source_refs` 恰为 p1257、p1259；其余七个来源位于 `forbidden_candidate_source_refs`；
- `structural_only_source_refs` 恰为 p1251、p1252、p1255；
- p1253、p1254、p1256、p1258 为 `non_enrollment_execution`；p1257、p1259 为 `other_control_candidate`；
- p1257、p1259 均绑定 `flow-screening`、`informed_consent` 和既有
  `procedure:d001-icf-screening`；已覆盖动作仅为 `obtain_signature`；
- p1257 必须保留 `communicate_with_participant`、`explain_information`、`witness_consent`；
  p1259 必须保留 `allow_informed_decision_time`、`obtain_signature`、
  `record_signature_date`、`record_signer_relationship`；
- `known_targets.official_rules` 为空；`known_targets.required_procedures` 仅含既有 ICF 签署流程；
- exception_semantics / clinical_qc 完整保留四类语义和第 67 包去重边界；
- p1250 owner=106，p1251-p1259 owner=107，p1260 owner=108，p768 owner=67；
- `claims_complete` 只能为 `false`。

## 5. 所有权、期别与源文回归

- 覆盖清单 p1251-p1259 的 `study_phase` 均为 `phase_ii`、`phase_scopes` 均为 `unknown`、
  `unit_kind` 均为 `paragraph`，source order 为
  `31140, 31150, 31160, 31170, 31180, 31190, 31200, 31210, 31220`。
- 每个 owned 来源的 `source_span_ids` 和 `member_source_refs` 必须各自只含对应 paragraph。
- 41 项 context_units 与 owned 不相交，且不得作为本包候选、workflow binding、官方规则或必需程序来源。
- Package 108 的 p1260 及以后内容不得出现在本包 owned/attached 或 dry-run prompt 声明来源中。

## 6. 确定性模型外 dry-run 与预期证据

在仓库根目录运行：

```bash
.venv/bin/python \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py \
  --config \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package107_informed_consent_governance_control_boundary.v1.json \
  --dry-run
```

预期观察：

- `owned_count=9`、`attached_count=0`、`unit_count=9`，`claims_complete=false`；
- `source_rows.json` 按 p1251-p1259 顺序包含九项，全部 `role=owned` 且解析到 Package 107；
- `execution/batch.json` 的 owned IDs 只有 p1251-p1259；structural-only 为 p1251/p1252/p1255；
  pre-enrollment 为 p1257/p1259，两者绑定筛选访视与知情同意动作；official rules 为空，
  required procedures 仅含既有 ICF 签署流程；
- `execution/prompt.txt` 只出现 p1251-p1259 的声明来源和逐字源文，不出现 p1260、p1248-p1250 未声明吸入，或不正当重复第 67 包控制发布；
- `clinical-qc.json` 的所有 `agent_candidates` 仍为空，gate 标记为 dry-run skipped；这只表示尚未水合，
  不得据此把 p1257/p1259 再次降为零候选。

## 7. 回归命令与停止条件

专项回归：

```bash
.venv/bin/python -m pytest -q \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61ct_package107_informed_consent_governance_control_boundary.py
```

父级允许的相邻包/ICF 既有回归由 Codex 在合并后执行。为修复通用动作语义缺口，父级可在
`app/protocols/protocol_control_planning.py` 增加不含项目编号的知情同意动作识别，并以专项测试冻结。
任一来源 SHA、frozen owner、source order、phase scope、原文摘录、四类语义分层、第 67 包去重、
签署/日期/充分理解保留或 Package 106/108 隔离失败时，停止并深挖。

## 8. Codex 独立最终检查

本 checklist 只证明模型外准备闭包、源文驱动的伦理/知情同意边界处置和确定性回归路径。它不证明：

- 临床候选内容已由模型解析或接受；
- publication gate、clinical QC 或 parent clinical acceptance 已通过；
- D001 全量来源、受试者档案、Patient Profile 或浏览器流程已完成；
- 真实资料中的伦理批准、ICF 文件、知情过程或重新同意已经验证；
- 真实受试者已经完成上述知情过程，或持续告知、双方留存、重新同意已经成为筛选期控制点。

最终判定必须由 Codex 依据冻结来源、干跑证据、专项及相邻包/ICF 回归和 parent clinical gates 另行完成。
