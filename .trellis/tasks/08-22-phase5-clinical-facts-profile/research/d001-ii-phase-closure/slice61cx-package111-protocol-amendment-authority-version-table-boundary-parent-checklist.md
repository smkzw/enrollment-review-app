# Slice61cx Package 111 方案修订授权与版本表边界 Parent Checklist

## 1. 执行身份与冻结边界

- Task: `phase5-slice61cx-20260830`
- Group: `d001-ii-package111-protocol-amendment-authority-version-table-boundary`
- Frozen plan: `papl-e17d498106b6f71f440ff2be`
- Package 111: `pap-214ce50fd89fb1998521c4c3`
- Selected phase: `phase_ii`
- Protocol SHA-256: `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- Frozen plan SHA-256: `92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4`
- Structure blob SHA-256: `3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d`

本执行只做模型外来源闭包、源文驱动的方案修订权威/版本表语义分层处置、Package 110/112
边界隔离、确定性 batch/prompt 干跑和专项测试。不得调用临床语义模型，不得发布 control point，
不得进入受试者、OCR、Patient Profile、浏览器或视觉流程。所有产物必须保持
`claims_complete=false`；`parent clinical acceptance` 仍由 Codex 决定。

## 2. Package 111 的唯一 owned 闭包与只读边界

冻结计划中 Package 111 严格且仅拥有以下四个来源单元，按原始文档顺序恢复：

1. `body.p1291` — `方案修订`，章节标题，仅结构来源。
2. `body.p1292` — 方案任何的必须的改变，都需以方案修订形式进行，并需在获得申办者、主要研究者签字同意后提交伦理委员会审批或备案。
3. `body.t15.r0` — 版本表表头，单元文本由 `body.t15.r0.c0.p0`-`r0.c3.p0` 组装：`版本 | 日期 | 变更说明 | 简要理由`。
4. `body.t15.r1` — 版本表数据行，单元文本由 `body.t15.r1.c0.p0`-`r1.c3.p0` 组装：`V1.0 | 2025年12月10日 | NA | NA`。该行只证明当前初始版本及日期，不证明存在历史修订、变更内容或修订理由。

`attached_source_refs=[]`。冻结计划中的 37 项 `context_units` 仅只读，未经 Codex 另行授权不得升格为附加来源。Package 110 止于 `body.p1290`；原始结构中的 `body.t15` 表容器、`body.t15.r2-r7` 的 24 个空单元格段落和 `body.p1293`-`body.p1294` 空白分隔均全局无主、不在冻结覆盖单元中，不得吸入本包或解释为未来修订记录；Package 112 从 `body.p1295` “参考文献”开始，不得提前吸收。

## 3. 先读源文，再区分四类语义

### 3.1 章节标题结构

- p1291 只提供“方案修订”结构与权威语境，不产生单例资格。

### 3.2 方案修订唯一授权变更机制

- p1292 规定任何必须改变都需以方案修订形式进行，并在申办者、主要研究者签字同意后提交伦理委员会审批或备案。
- 必须保留方案修订作为唯一授权标准变更形式与项目级方案权威治理。
- 申办者、主要研究者及伦理委员会义务不得候选化为受试者级入排条件。

### 3.3 版本表头结构

- t15.r0 只提供版本/日期/变更说明/简要理由表头，不得与数据行混淆，也不得误作入排控制。

### 3.4 初始版本记录而非既往修订

- t15.r1 记录 V1.0 与 2025年12月10日，变更说明与简要理由均为 NA。
- 不得把 V1.0/NA 臆造为既往修订、变更内容或修订理由。

### 3.5 候选处置结论

完成源文判断后确认：本包四项来源均未形成独立的“真实参加研究前可核验受试者动作”。

- p1291、t15.r0 维持结构来源；
- p1292、t15.r1 维持 `non_enrollment_execution`；
- `required_candidate_source_refs=[]`，`pre_enrollment_source_refs=[]`；
- 全部四项进入 `forbidden_candidate_source_refs`；
- 零候选不是预设，而是逐项原文依据后的结论；若后续发现真实前置控制被丢失，必须停止并回退。

因此不得把申办者/主要研究者/伦理委员会义务或 V1.0/NA 误成单例资格，也不得用 `other_control_candidate` 强挂受试者工作流，也不得丢失任何真实前置控制。

## 4. 配置盲检

配置文件：

`configs/representative_group_package111_protocol_amendment_authority_version_table_boundary.v1.json`

配置必须满足：

- `owned_source_refs` 恰为 p1291、p1292、t15.r0、t15.r1；`attached_source_refs=[]`；
- `required_candidate_source_refs=[]`；四个来源均位于 `forbidden_candidate_source_refs`；
- `structural_only_source_refs` 恰为 p1291 与 t15.r0；
- p1292、t15.r1 为 `non_enrollment_execution`；
- workflow / procedure / action / visit 绑定为空；`known_targets.official_rules` 与 `required_procedures` 均为空；
- exception_semantics / clinical_qc 完整保留四类语义与 Package 110/112 边界；
- p1290 owner=110，p1291/p1292/t15.r0/t15.r1 owner=111，p1295 owner=112；
- `excluded_unowned_structure_refs` 精确记录表容器、t15.r2-r7 的24个空单元格段落和 p1293-p1294，它们均不得进入 owned/attached/prompt；
- 37 项语境中无主项精确写入 `unowned_context_source_refs`；
- `claims_complete` 只能为 `false`。

## 5. 所有权、期别与源文回归

- 覆盖清单 p1291/p1292/t15.r0/t15.r1 的 `study_phase` 均为 `phase_ii`、`phase_scopes` 均为 `unknown`；
  `unit_kind` 分别为 `paragraph`、`paragraph`、`table_header`、`table_row`；source order 为
  `31540, 31550, 31571, 31611`。
- p1291/p1292 的 `source_span_ids` 与 `member_source_refs` 各自只含对应 paragraph；
  t15.r0 为 `c0.p0-c3.p0` 四格；t15.r1 为 `c0.p0-c3.p0` 四格。
- 37 项 context_units 与 owned 不相交，且不得作为本包候选、workflow binding、官方规则或必需程序来源。
- Package 110 的 p1290 及以前、Package 112 的 p1295 及以后，以及无主的表容器、t15.r2-r7 空单元格段落和 p1293-p1294 空白分隔，均不得出现在本包 owned/attached 或 dry-run prompt 声明来源中。

## 6. 确定性模型外 dry-run 与预期证据

在仓库根目录运行：

```bash
.venv/bin/python \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py \
  --config \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package111_protocol_amendment_authority_version_table_boundary.v1.json \
  --dry-run
```

预期观察：

- `owned_count=4`、`attached_count=0`、`unit_count=4`，`claims_complete=false`；
- `source_rows.json` 按 p1291、p1292、t15.r0、t15.r1 顺序包含四项，全部 `role=owned` 且解析到 Package 111；
- `execution/batch.json` 的 owned IDs 只有上述四项；structural-only 为 p1291 与 t15.r0；
  pre-enrollment 为空；official rules 与 required procedures 为空；
- `execution/prompt.txt` 只出现本包四项的声明来源和逐字源文，不出现 p1290/p1295 跨包来源、无主表容器/空行/空白分隔，也不把 V1.0/NA 写成既往修订；
- `clinical-qc.json` 的所有 `agent_candidates` 仍为空，gate 标记为 dry-run skipped；零候选是源文判断结论，不是未水合借口。

## 7. 回归命令与停止条件

专项回归：

```bash
.venv/bin/python -m pytest -q \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61cx_package111_protocol_amendment_authority_version_table_boundary.py
```

父级允许的相邻包回归由 Codex 在合并后执行。任一来源 SHA、frozen owner、source order、
phase scope、原文摘录、四类语义分层、零候选逐项依据、或 Package 110/112 隔离失败时，停止并深挖。
本 worker 未被授权修改共享代码；若出现共享代码阻塞，只报告可复现证据。

## 8. Codex 独立最终检查

本 checklist 只证明模型外准备闭包、源文驱动的方案修订权威/版本表边界处置和确定性回归路径。它不证明：

- 临床候选内容已由模型解析或接受；
- publication gate、clinical QC 或 parent clinical acceptance 已通过；
- D001 全量来源、受试者档案、Patient Profile 或浏览器流程已完成；
- 真实资料中的方案修订签署、伦理审批/备案或版本历史已经验证；
- 真实受试者已经完成任何参加研究前控制。

最终判定必须由 Codex 依据冻结来源、干跑证据、专项及相邻包回归和 parent clinical gates 另行完成。
