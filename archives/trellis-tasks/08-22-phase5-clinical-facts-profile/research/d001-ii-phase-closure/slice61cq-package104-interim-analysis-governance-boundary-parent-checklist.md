# Slice61cq Package 104 期中分析治理边界 Parent Checklist

## 1. 执行身份与冻结边界

- Task: `phase5-slice61cq-20260830`
- Group: `d001-ii-package104-interim-analysis-governance-boundary`
- Frozen plan: `papl-e17d498106b6f71f440ff2be`
- Package 104: `pap-03856594c8db16e170f5a4db`
- Selected phase: `phase_ii`
- Protocol SHA-256: `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- Frozen plan SHA-256: `92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4`
- Structure blob SHA-256: `3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d`

本执行只做模型外来源闭包、所有权回归、确定性 batch/prompt 干跑和
回归测试。不得调用临床语义模型，不得发布 control point，不得读取或生成
subject、OCR、Patient Profile、浏览器或受试者级验收结论。所有产物必须保持
`claims_complete=false`；`parent_clinical_acceptance` 仍由 Codex 决定。

## 2. Package 104 的唯一 owned 闭包

冻结计划中 Package 104 只能拥有以下四个来源单元：

1. `body.p1236` — 章节标题 `期中分析`，仅结构来源。
2. `body.p1237#atom-0-15` — `本研究包含一个预设的期中分析。`
3. `body.p1237#atom-15-100` — 累积 II 期有效性/安全性数据、IDMC 向申办方正式建议、继续 III 期及 III 期剂量推荐。
4. `body.p1237#atom-160-208` — IDMC 综合疗效/安全性证据形成建议，具体细节见独立期中统计分析计划。

`body.p1237#atom-100-160` 不在冻结所有者映射中，不能因语义相邻而转移到
Package 104；`body.p537` 也不是 Package 104 owned 来源。

## 3. 研究级统计治理与受试者级控制分离

### 3.1 完整保留但不生成受试者候选

以下三个 owned 语义原子必须完整保留原文和研究级关系，但不得生成当前受试者
审核候选：

- `body.p1237#atom-0-15`: “预设期中分析”是研究级统计治理事实。
- `body.p1237#atom-15-100`: 累积 II 期数据、IDMC 正式建议对象及 III 期继续/剂量建议是研究级关系。
- `body.p1237#atom-160-208`: IDMC 综合证据形成建议及独立期中统计分析计划是研究级治理关系。

当前候选合同至少需要一个筛选、基线或 D1 等受试者审核节点，无法无损承载
研究级治理事实。把上述内容写成 `other_control_candidate` 会迫使其错误挂到受试者
工作流，因此本包六个声明来源全部禁止候选。零候选表示“不属于受试者入排控制”，
不表示系统未理解或删除了期中分析内容。

### 3.2 必须禁止的受试者级倒置

以上三个候选来源不得绑定：

- 单例受试者资格、入组/排除、筛选失败或“不得入组”；
- 筛选访视、基线访视、随机、D1 给药前访视或任何受试者程序；
- 受试者级疗效/安全性阈值、资料缺口或控制点发布；
- `IDMC` 决定单例资格，或独立期中统计分析计划决定单例入排。

`body.p1236` 只作结构来源，必须为 candidate source 禁止项；不得从标题生成
候选、流程节点、官方规则或受试者控制点。

## 4. 附加只读上下文

本次最小附加上下文仅包含两项：

- `body.p537`: 闭合 II 期约 50% 参与者完成第 12 周访视后的研究级触发、独立统计科学组（SSG）分析、IDMC 审查/剂量及新参与者入组建议，以及最终决定取决于申办方。该来源不属于 Package 104，不能作为 candidate source。
- `body.p1237#atom-100-160`: 冻结计划无所有者的同父原子，补足“II 期 50% 参与者完成第 12 周主要疗效评估后启动、独立统计团队提交 IDMC”的触发语义。它只能只读进入 prompt/QC，不能进入 owned、candidate、workflow、required procedure 或受试者义务。

附加上下文中的“50%参与者”“第12周访视”“停止新的参与者入组”和“申办方
最终决定”均是研究总体治理/后续研究决策，不得改写为任一受试者的资格或访视
结论。

## 5. 配置盲检

配置文件必须满足以下确定性条件：

- `owned_source_refs` 恰为上述四项；`attached_source_refs` 恰为 `body.p537` 和 `body.p1237#atom-100-160`。
- `required_candidate_source_refs` 为空。
- `forbidden_candidate_source_refs` 恰含四个 owned 与两个 attached 来源；结构标题、研究级治理原子和只读上下文均不得成为受试者候选。
- 三个 owned 语义原子的 expected disposition 均为 `administrative_statistical_background`，表示其研究级统计治理语义已被理解但不进入入排控制。
- `expected_workflow_stage_ids_by_source_ref`、`pre_enrollment_source_refs`、`known_targets.official_rules` 和 `known_targets.required_procedures` 均为空。
- `candidate_required_markers_by_source_ref` 为空；来源逐字保真由冻结 excerpt 回归负责，禁止项由来源身份覆盖全部六个声明来源。
- `claims_complete` 只能为 `false`；配置不宣称全量、受试者、Patient Profile 或 Codex clinical acceptance。

## 6. 所有权与相邻包回归

- `body.p1210`、`body.p1223` 在冻结计划中无所有者，不得误写为第102包或迁入本包。
- `body.p1224`、`body.p1235` 的 103 所有权边界不得迁移。
- Package 104 仅新增/保留 `body.p1236` 和 p1237 的三个明确原子。
- `body.p1237#atom-100-160` 必须继续无所有者；`body.p537` 必须继续无 Package 104 所有权。
- `body.p1238` 起由 Package 105 拥有；不得向前吞并。
- Prompt 只能出现声明的四个 owned 和两个 attached 来源，不得夹带相邻包或未声明来源。

## 7. 确定性干跑与预期证据

在仓库根目录运行：

```bash
.venv/bin/python \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py \
  --config \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package104_interim_analysis_governance_boundary.v1.json \
  --dry-run
```

预期观察：

- `owned_count=4`、`attached_count=2`、`unit_count=6`；
- `claims_complete=false`；不产生 hydrated Agent output、control catalog 或发布结果；
- `source_rows.json` 和 `clinical-qc.json` 按原文档顺序包含 6 项，四项 role=owned、两项 role=attached；
- `execution/batch.json` 的 owned IDs 只有四项，context IDs 只有两项；官方规则、required procedures、workflow binding、pre-enrollment 和受试者 action 映射均为空；
- `execution/prompt.txt` 保留六项声明来源和原文语义，同时不出现未声明的 p1210–p1223、`body.p1238` 或其他来源；
- QC gate 标记为 dry-run skipped，不能解释为临床验收通过。

## 8. 回归命令与停止条件

```bash
.venv/bin/python -m pytest -q \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61cq_package104_interim_analysis_governance_boundary.py
```

任一来源 SHA、frozen owner、source order、phase scope、原文摘录、候选边界或
只读无主约束失败时，停止并回报 Codex；不得通过扩大上下文、添加 workflow、
猜测 owner、把无主原子变成候选或修改冻结证据来“修复”。

## 9. Codex 最终检查

本 checklist 只证明模型外准备闭包与确定性回归路径。它不证明：

- 临床候选内容已由模型解析或接受；
- publication gate、clinical QC 或 parent clinical acceptance 已通过；
- D001 全量来源、受试者档案、Patient Profile 或浏览器流程已完成；
- 任何研究级建议已经成为受试者级控制点。

最终判定必须由 Codex 依据冻结来源、干跑证据、回归测试和 parent clinical gates
另行完成。
