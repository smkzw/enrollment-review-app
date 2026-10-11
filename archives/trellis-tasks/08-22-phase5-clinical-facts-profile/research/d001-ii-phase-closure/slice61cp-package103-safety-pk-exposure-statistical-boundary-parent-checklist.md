# D001 II 第103包安全性、PK、PopPK与暴露-效应统计边界父级检查清单

## 本轮边界

- 活动候选计划：`papl-e17d498106b6f71f440ff2be`；第103包：`pap-e965d4d93dad672cc906240d`。
- 拥有来源严格为 `body.p1224`、`body.p1226-p1235`；只读附加来源严格为 `body.p1225`，按 `body.p1224-p1235` 原始顺序恢复。
- `body.p1225` 的 `Ⅲ期临床阶段` AE/TEAE 统计仅作期别隔离的只读语境，不得进入Ⅱ期控制；其所有权不属于本包。
- 第102包 `body.p1197-p1209` 保持所有权；`body.p1210-p1223` 是当前冻结计划中无拥有权的后续Ⅱ/Ⅲ期疗效统计语境，不进入本包。
- Package 104 拥有 `body.p1236` 及 `body.p1237#atom-0-15`、`body.p1237#atom-15-100`、`body.p1237#atom-160-208`；`body.p1237#atom-100-160` 是无所有权的只读期中分析上下文，均不进入本包。
- 本轮仅做模型外来源闭包、临床语义边界和确定性合同设计；不调用临床语义模型、不发布控制点、不运行受试者/OCR/Patient Profile/浏览器流程，`claims_complete=false`。

## 父级盲态检查

1. 十一个拥有来源与一个只读来源是否逐项且仅处置一次，配置及准备提示是否保持 `body.p1224-p1235` 的稳定来源顺序。
2. `body.p1224`、`body.p1230`、`body.p1232`、`body.p1234` 是否仅作安全性、PK、PopPK、暴露-效应章节结构；标题不独立产生候选、流程节点或程序。
3. `body.p1225` 是否严格保持Ⅲ期只读语境；Ⅲ期基础期/整个研究期的AE/TEAE统计、MedDRA SOC/PT、严重不良事件和死亡事件不得倒灌Ⅱ期。
4. `body.p1226` 的血常规、血生化、生命体征及治疗前后/基线变化是否仅作治疗后安全性统计汇总；异常结果列表不得变成筛选、基线缺口、异常即不得入组或D1给药前必查。
5. `body.p1227` 的体格检查列表、交叉表和异常结果是否仅作安全性统计输出，不形成体格检查筛选义务或异常排除规则。
6. `body.p1228` 的具有生育能力女性血妊娠检查结果是否仅作安全性列表；不得从结果列表倒置新增妊娠筛查时点、阳性处置、入排规则或访视义务。妊娠资格控制若存在，须来自冻结的官方流程来源。
7. `body.p1229` 的合并用药及治疗是否仅作按组别统计汇总和列表，未生成合并用药禁限、病史筛查、证据完整性或资格决定。
8. `body.p1231` 的PKCS、计划/实际PK采样时间、CMS-D001及代谢产物血药浓度、描述性统计和曲线是否仅作PK分析数据/输出；不得变成PK采样必做、浓度阈值、筛选或D1给药前控制。
9. `body.p1233` 的本研究与前期研究血药浓度合并、NONMEM PopPK模型和另行定量药理计划/报告是否保持模型分析语义；不得变成模型纳入资格、缺失证据不足或必需程序。
10. `body.p1235` 的“如数据允许”、个体暴露参数和暴露/疗效、暴露/安全性相关性探索是否保持后续探索性统计语义；不得变成疗效/安全性入选阈值、基线要求或发布控制点。
11. `required_candidate_source_refs` 是否为空，且12个声明来源全部位于 `forbidden_candidate_source_refs`；`expected_workflow_stage_ids_by_source_ref`、`pre_enrollment_source_refs`、官方规则和必需程序是否全部为空。
12. 是否没有吸收第102包来源、无拥有权的 `body.p1210-p1223` 后续疗效统计语境、无拥有权的 `body.p1237#atom-100-160` 期中分析上下文，或Package 104拥有的 `body.p1236`/其余 `body.p1237` 原子；`body.p1225` 仅作为本包边界所需的Ⅲ期只读上下文。
13. 是否保留安全性、妊娠、合并治疗、PKCS、CMS-D001、`C_trough`、`C_max`、PopPK、NONMEM、暴露/疗效、暴露/安全性及“如数据允许”等原始表达和时间/条件锚点；不得以模型摘要代替逐字来源或所有权。
14. 是否保持零候选、零工作流绑定、零官方规则和零必需程序；任何“筛选必做”“基线必做”“证据不足”“不得入组”“PK采样必做”“发布控制点”均视为越界反向推理。

## 确定性证据

- 配置：`configs/representative_group_package103_safety_pk_exposure_statistical_boundary.v1.json`
- 测试：`test_slice61cp_package103_safety_pk_exposure_statistical_boundary.py`
- 模型外准备命令：

  ```bash
  .venv/bin/python .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py \
    --config .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package103_safety_pk_exposure_statistical_boundary.v1.json \
    --dry-run
  ```

- 专项测试必须证明：配置零候选/零工作流绑定；冻结计划包103所有权精确；Ⅲ期 `body.p1225` 与Ⅱ期拥有来源隔离；安全性、妊娠、合并治疗、PK、PopPK和暴露-效应统计摘录保真；第102包、无拥有权的 `body.p1210-p1223` 及Package 104相邻边界排除；准备提示仅含12个声明来源；统计域不得反向推理为入排义务；冻结计划和结构块指纹未漂移。

## 成功与停止条件

- **通过模型外闭包**：11个拥有来源和1个Ⅲ期只读来源均由稳定 `source_ref` 唯一恢复；来源顺序、所有权、期别、统计语义、跨包边界和零候选同时成立。
- **立即停止**：来源或计划指纹漂移；Ⅲ期 `body.p1225` 内容进入Ⅱ期；治疗后安全性统计、血妊娠列表、合并治疗编码、PK采样/浓度、PopPK或暴露-效应探索被前置为单例入排义务；第102包、`body.p1210-p1223` 或Package 104进入提示；出现候选、工作流绑定、官方规则、必需程序或模型调用。
- **不能宣称**：本包通过不代表第102/104包、安全性或统计章节全部内容、D001全方案、受试者资料、临床结论或Patient Profile完成。

## 不可变来源

- 原始 DOCX SHA-256：`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- 冻结候选计划 SHA-256：`92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4`
- 结构块 SHA-256：`3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d`
