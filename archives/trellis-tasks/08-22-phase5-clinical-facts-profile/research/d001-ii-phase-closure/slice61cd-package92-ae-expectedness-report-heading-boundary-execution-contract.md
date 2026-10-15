# D001 II 第 92 包不良事件预期性与报告章节入口边界执行合同

## 目标

为当前 131 包冻结计划第 92 包 `body.p1098-p1101` 建立最小模型外来源闭包、确定性反例门禁和可恢复准备产物。只处理治疗后不良事件预期性参照及后续报告章节结构入口，不发布预筛、筛选或基线控制点，不进入受试者、OCR、Patient Profile 或前端。

## 当前权威来源

- 冻结计划：`artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/frozen_phase_plan.json`
- 计划标识：`papl-40b1237a22e538a278b4fd5e`
- 计划 SHA-256：`f0aa7e4bccad782ad5472c1f446f079e26343f694ad3ddca401bfbef89f38250`
- 当前包：ordinal `92`，package id `pap-c6c57a2734d51175bf06d031`
- 前包：ordinal `91`，package id `pap-87e89271165354d285b2faa1`
- 后包：ordinal `93`，package id `pap-2815c9e5b343ac6d7663ae21`
- 原始 DOCX SHA-256：`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- 结构块 SHA-256：`3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d`

## 拥有来源

- `body.p1098`：“不良事件预期性评估”标题，仅作结构。
- `body.p1099`：本研究 CMS-D001 片不良事件预期性见 CMS-D001 片《研究者手册》，保持治疗后执行职责。
- `body.p1100`：“不良事件的报告”标题，仅作结构。
- `body.p1101`：“研究者向申办者报告不良事件等信息的要求与途径”标题，仅作结构。

## 必须核对并保留的语义

1. `p1099` 只确定预期性判断需参见 CMS-D001 片《研究者手册》。当前方案句子没有提供手册版本、风险条目或个例结论；不得补写版本、默认最新版本、凭常识判定预期/非预期或把缺少手册内容改成确定结论。
2. 可按最小必要性只读附加第 80 包 `p1019` 非预期不良反应定义及《研究者手册》主要参考地位；若为分离 SUSAR 三维关系确有必要，可同时只读附加 `p1018`，但所有权不得转移，不得吞并整个第 80 包。
3. 第 90/91 包“是否符合已知作用机制、特性或已知不良反应”只是因果关系综合评价输入，不能替代预期性评估；已知性不等于预期性，因果相关性、严重性和预期性也不得互相推出。
4. 若引用 `p1018`，SUSAR 必须保持“可疑（因果）+非预期+严重”三维合取；单独非预期、单独严重或单独相关均不足以构成 SUSAR。
5. `p1100/p1101` 只闭合后续报告章节层级，不独立产生报告对象、报告时限、表单、途径或新信息随访义务。
6. 第 93 包 `body.p1102-p1112` 拥有具体应报告事件、24 小时期限及新信息类型，不进入本包拥有或附加提示；只保留所有权元数据以防吞并。
7. `required_candidate_source_refs=[]`；拥有和只读附加来源均不得发射入排候选。

## 允许写入

- `configs/representative_group_package92_ae_expectedness_report_heading_boundary.v1.json`
- `test_slice61cd_package92_ae_expectedness_report_heading_boundary.py`
- `slice61cd-package92-ae-expectedness-report-heading-boundary-parent-checklist.md`
- `slice59n-prepare/d001-ii-package92-ae-expectedness-report-heading-boundary/`

以上路径均位于 `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/`。

## 禁止事项

- 不修改共享运行器、正式入排矩阵、冻结计划、方案解析、受试者、OCR、Patient Profile 或前端。
- 不调用临床语义模型，不发布控制点，不改变第 80/91/93 包所有权。
- 不把已知性等同预期性，不从因果关系或严重性推导预期性，不把非预期单独等同 SUSAR。
- 不虚构研究者手册版本、条目或判定结论，不把报告章节标题改成具体报告义务。
- 不提前吞并第 93 包事件类型、24 小时时钟或新信息随访流程。

## 完成证据

- 当前计划、包标识、4 个拥有来源及最小只读来源逐项一致。
- 专项反例覆盖手册版本/内容虚构、无手册结论化、已知性替代预期性、因果/严重性/预期性互推、SUSAR 合取弱化、标题义务化、24 小时时钟提前吞并及候选升级。
- dry-run prepare、专项/相邻/Phase、方案与 Agent、治理、JSON、差异与执行审计通过。
- `claims_complete=false`，明确下一包和未完成边界。
