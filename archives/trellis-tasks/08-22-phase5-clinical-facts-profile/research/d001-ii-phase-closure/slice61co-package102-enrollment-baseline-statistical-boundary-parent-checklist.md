# D001 II 第102包参与者入组、基线与合并治疗统计边界父级检查清单

## 本轮边界

- 活动候选计划：`papl-e17d498106b6f71f440ff2be`；第102包：`pap-ad0c757625a628fce5c7ed7c`。
- 拥有来源严格为 `body.p1197`、`body.p1200-p1205`；只读附加来源严格为 `body.p1198`、`body.p1199`、`body.p1206-p1209`，按 `body.p1197-p1209` 原始顺序恢复。
- `body.p1198` 是Ⅱ期统计语境，`body.p1199` 是Ⅲ期统计语境；Ⅲ期基础期、扩展期和完成试验描述不得进入Ⅱ期控制。
- 第101包 `body.p1179`、`body.p1186-p1196` 保持所有权；`body.p1210-p1223` 是当前冻结计划中无拥有权的后续Ⅱ/Ⅲ期疗效统计语境，Package 103 实际从 `body.p1224` 的安全性分析开始拥有来源，均不进入本包。
- 本轮仅做模型外来源闭包、临床语义边界和确定性合同设计；不调用临床语义模型、不发布控制点、不运行受试者/OCR/Patient Profile/浏览器流程，`claims_complete=false`。

## 父级盲态检查

1. 七个拥有来源与六个只读来源是否逐项且仅处置一次，配置及准备提示是否保持 `body.p1197-p1209` 的稳定来源顺序。
2. `body.p1197` 的“参与者入组分析”是否只解释为总体入选、完成、提前结束和分析集分布的事后统计总结，而未变成新的入组标准、筛选动作或个例入组决策入口。
3. `body.p1198` 的Ⅱ期统计与 `body.p1199` 的Ⅲ期统计是否严格分开；Ⅲ期完成16周基础期、扩展期治疗及完成试验信息不得倒灌Ⅱ期。
4. `body.p1200-p1201` 的“基线”是否保持人口统计和ITT描述性统计语义，未变成基线访视项目、基线资料要求、证据缺口或不得入组判定。
5. `body.p1202-p1204` 的药物/非药物治疗、WHO Drug、MedDRA SOC/PT是否仅用于合并治疗的编码及例数/百分比汇总，未生成合并用药禁限、病史筛查或证据完整性义务。
6. `body.p1205-p1209` 是否保持Ⅱ期疗效统计分支；PASI-75、CMH、多重填补、LOCF、NRI及敏感性分析不得改写为筛选、基线、随机或D1给药前义务。
7. `required_candidate_source_refs` 是否为空，且13个来源全部位于 `forbidden_candidate_source_refs`；`expected_workflow_stage_ids_by_source_ref`、`pre_enrollment_source_refs`、官方规则和必需程序是否全部为空。
8. 是否没有吸收第101包来源、无拥有权的 `body.p1210-p1223` 后续Ⅱ/Ⅲ期疗效统计语境，也没有提前吸收Package 103从 `body.p1224` 起的安全性分析正文；附加来源只作本包边界所需只读统计上下文。
9. 是否保留WHO Drug、MedDRA、SOC、PT、ITT、PASI-75、CMH、LOCF、NRI等原始统计语义和时间锚点；不得以模型摘要代替逐字来源或所有权。
10. 是否保持零候选、零工作流绑定、零官方规则和零必需程序；任何“筛选必做”“基线必做”“证据不足”“不得入组”“发布控制点”均视为越界反向推理。

## 确定性证据

- 配置：`configs/representative_group_package102_enrollment_baseline_statistical_boundary.v1.json`
- 测试：`test_slice61co_package102_enrollment_baseline_statistical_boundary.py`
- 模型外准备命令：

  ```bash
  .venv/bin/python .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py \
    --config .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package102_enrollment_baseline_statistical_boundary.v1.json \
    --dry-run
  ```

- 专项测试必须证明：配置零候选/零工作流绑定；冻结计划包102所有权精确；Ⅱ/Ⅲ期隔离；逐字统计摘录保真；相邻包排除；准备提示仅含13个声明来源；统计域不得反向推理为入排义务；冻结计划和结构块指纹未漂移。

## 成功与停止条件

- **通过模型外闭包**：7个拥有来源和6个只读来源均由稳定 `source_ref` 唯一恢复；来源顺序、所有权、期别、统计语义、跨包边界和零候选同时成立。
- **立即停止**：来源或计划指纹漂移；p1199的Ⅲ期内容进入Ⅱ期；“入组”“基线”“合并用药/治疗”或疗效缺失方法被前置为单例入排义务；p1210以后进入提示；出现候选、工作流绑定、官方规则、必需程序或模型调用。
- **不能宣称**：本包通过不代表第101/103包、统计章节全部内容、D001全方案、受试者资料、临床结论或Patient Profile完成。

## 不可变来源

- 原始 DOCX SHA-256：`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- 冻结候选计划 SHA-256：`92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4`
- 结构块 SHA-256：`3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d`
