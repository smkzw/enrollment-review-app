# Slice61cw Package 110 数据发布、研究结果发表与商业秘密治理边界 Parent Checklist

## 1. 执行身份与冻结边界

- Task: `phase5-slice61cw-20260830`
- Group: `d001-ii-package110-data-publication-commercial-secret-governance-boundary`
- Frozen plan: `papl-e17d498106b6f71f440ff2be`
- Package 110: `pap-7358ad349433c3c08aacc5f1`
- Selected phase: `phase_ii`
- Protocol SHA-256: `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- Frozen plan SHA-256: `92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4`
- Structure blob SHA-256: `3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d`

本执行只做模型外来源闭包、源文驱动的数据发布/研究结果发表/商业秘密与专利治理语义分层处置、Package 109/111
边界隔离、确定性 batch/prompt 干跑和专项测试。不得调用临床语义模型，不得发布 control point，
不得进入受试者、OCR、Patient Profile、浏览器或视觉流程。所有产物必须保持
`claims_complete=false`；`parent clinical acceptance` 仍由 Codex 决定。

## 2. Package 110 的唯一 owned 闭包与只读边界

冻结计划中 Package 110 严格且仅拥有以下十个来源单元，按原始文档顺序恢复：

1. `body.p1281` — `数据发布和商业秘密的保护`，小节标题，仅结构来源。
2. `body.p1282` — 应按现行法规要求将临床研究结果记录在完整的临床研究报告中。
3. `body.p1283` — 研究资料所有权属于申办者；除国家药品监督管理局要求外，未经书面同意不得向第三者提供；申办者可将收集数据用于药品注册、科学产品记录和出版物发表。
4. `body.p1284` — 无论研究结果如何，申办者致力于通过科学大会和同行评审期刊公开研究相关信息，并遵守研究结果出版要求。
5. `body.p1285` — 通常仅支持基于完整研究的多中心研究结果发表，而非单个中心数据发表；经相互同意可能指定协调研究者。
6. `body.p1286` — 参与中心在完成本研究、数据解读以及发布最终报告之前，不得发表、介绍或讨论本研究数据/结果相关文章。
7. `body.p1287` — 公开或提交发表前，研究者须向申办者提供原稿供审核并告知发表意愿；程序目的是防止提前泄露商业秘密或其他受专利保护材料，而非限制公开结果或观点。
8. `body.p1288` — 申办者有权将实质性贡献人员加入作者并决定作者姓名先后顺序；发表费用可通过书面协议规定。
9. `body.p1289` — 若研究结果文章由申办者撰写，会以书面形式询问研究者是否同意列为作者；研究者应在合理时限（例如30个日历日）内书面答复。
10. `body.p1290` — 出版物或手稿不得包含申办者商业秘密、专有或机密信息；含可申请专利主题时，申办者可要求研究者在发表前协助专利申请（申办者承担费用）。

`attached_source_refs=[]`。冻结计划中的 37 项 `context_units` 仅只读，未经 Codex 另行授权不得升格为附加来源。Package 109 止于 `body.p1280`；Package 111 从 `body.p1291` 开始，不得吸入。

## 3. 先读源文，再区分两类语义

### 3.1 小节标题结构

- p1281 只提供“数据发布和商业秘密的保护”小节结构，不产生单例资格。

### 3.2 数据发布、研究结果发表与商业秘密/专利治理

- p1282 是完整临床研究报告记录治理，不是入排控制。
- p1283 是申办者资料所有权、第三者披露限制、药监局要求例外与注册/发表使用治理。
- p1284 是无论结果如何的研究结果公开与出版要求治理。
- p1285 是多中心发表偏好与协调研究者安排治理。
- p1286 是对研究中心/研究者的最终报告前发表时序限制，不是筛选/基线排除，也不得倒置为参加研究前控制。
- p1287 是原稿提交申办者审核与商业秘密/专利保护治理，不是限制公开结果或研究者观点，也不是单例入排。
- p1288 是作者署名顺序与发表费用安排治理。
- p1289 是申办者撰文情形下的作者邀请与合理时限答复治理。
- p1290 是出版物排除商业秘密/专有机密信息及发表前专利合作治理，不得误成单例资格。

### 3.3 候选处置结论

完成源文判断后确认：本包十项来源均未形成独立的“真实参加研究前可核验受试者动作”。

- p1281 维持结构来源；
- p1282-p1290 维持 `non_enrollment_execution`；
- `required_candidate_source_refs=[]`，`pre_enrollment_source_refs=[]`；
- 全部十项进入 `forbidden_candidate_source_refs`；
- 零候选不是预设，而是逐项原文依据后的结论；若后续发现真实前置控制被丢失，必须停止并回退。

因此不得把数据归属、发表限制、原稿审核、作者署名或知识产权保护误成单例资格，也不得用 `other_control_candidate` 强挂受试者工作流，也不得丢失任何真实前置控制。

## 4. 配置盲检

配置文件：
`configs/representative_group_package110_data_publication_commercial_secret_governance_boundary.v1.json`

配置必须满足：

- `owned_source_refs` 恰为 p1281-p1290；`attached_source_refs=[]`；
- `required_candidate_source_refs=[]`；十个来源均位于 `forbidden_candidate_source_refs`；
- `structural_only_source_refs` 恰为 p1281；
- p1282-p1290 为 `non_enrollment_execution`；
- workflow / procedure / action / visit 绑定为空；`known_targets.official_rules` 与 `required_procedures` 均为空；
- exception_semantics / clinical_qc 完整保留两类语义与 Package 109/111 边界；
- p1280 owner=109，p1281-p1290 owner=110，p1291 owner=111；
- 37 项语境中无主项精确写入 `unowned_context_source_refs`；
- `claims_complete` 只能为 `false`。

## 5. 所有权、期别与源文回归

- 覆盖清单 p1281-p1290 的 `study_phase` 均为 `phase_ii`、`phase_scopes` 均为 `unknown`、
  `unit_kind` 均为 `paragraph`，source order 为
  `31440, 31450, 31460, 31470, 31480, 31490, 31500, 31510, 31520, 31530`。
- 每个 owned 来源的 `source_span_ids` 和 `member_source_refs` 必须各自只含对应 paragraph。
- 37 项 context_units 与 owned 不相交，且不得作为本包候选、workflow binding、官方规则或必需程序来源。
- Package 109 的 p1270-p1280 与 Package 111 的 p1291 及以后内容不得出现在本包 owned/attached 或 dry-run prompt 声明来源中。

## 6. 确定性模型外 dry-run 与预期证据

在仓库根目录运行：

```bash
.venv/bin/python \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py \
  --config \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package110_data_publication_commercial_secret_governance_boundary.v1.json \
  --dry-run
```

预期观察：

- `owned_count=10`、`attached_count=0`、`unit_count=10`，`claims_complete=false`；
- `source_rows.json` 按 p1281-p1290 顺序包含十项，全部 `role=owned` 且解析到 Package 110；
- `execution/batch.json` 的 owned IDs 只有 p1281-p1290；structural-only 为 p1281；
  pre-enrollment 为空；official rules 与 required procedures 为空；
- `execution/prompt.txt` 只出现 p1281-p1290 的声明来源和逐字源文，不出现 p1280 回吸或 p1291 提前吸收；
- `clinical-qc.json` 的所有 `agent_candidates` 仍为空，gate 标记为 dry-run skipped；零候选是源文判断结论，不是未水合借口。

## 7. 回归命令与停止条件

专项回归：

```bash
.venv/bin/python -m pytest -q \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61cw_package110_data_publication_commercial_secret_governance_boundary.py
```

父级允许的相邻包回归由 Codex 在合并后执行。任一来源 SHA、frozen owner、source order、
phase scope、原文摘录、两类语义分层、零候选逐项依据、或 Package 109/111 隔离失败时，停止并深挖。
本 worker 未被授权修改共享代码；若出现共享代码阻塞，只报告可复现证据。

## 8. Codex 独立最终检查

本 checklist 只证明模型外准备闭包、源文驱动的数据发布/发表/商业秘密边界处置和确定性回归路径。它不证明：

- 临床候选内容已由模型解析或接受；
- publication gate、clinical QC 或 parent clinical acceptance 已通过；
- D001 全量来源、受试者档案、Patient Profile 或浏览器流程已完成；
- 真实资料中的临床研究报告、发表安排、原稿审核或专利申请已经验证；
- 真实受试者已经完成任何参加研究前控制。

最终判定必须由 Codex 依据冻结来源、干跑证据、专项及相邻包回归和 parent clinical gates 另行完成。
