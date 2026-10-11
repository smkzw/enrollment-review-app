# Slice 61bw Package 85 严重肝损伤与肝功能异常 SAE 边界执行合同

## 目标

为 D001 II 当前冻结计划第 85 包 `body.p1055-p1066` 建立模型外、可恢复、可审计的来源闭包和确定性反例门禁。不得调用临床语义模型，不得发布控制点，不得修改原始方案、正式矩阵、受试者、OCR、Patient Profile 或前端。

## 权威来源

1. 原始方案 DOCX 及冻结 SHA-256。
2. `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/frozen_phase_plan.json`。
3. `coverage_manifest.json` 与结构块 `structure/blobs/protocol_blocks/3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d.json`。
4. 已验收 Package 83、84 配置、专项测试、父级清单和检查点，仅作实现模式与相邻所有权参考。
5. 当前任务 PRD、设计、实施计划及项目 AGENTS 边界。

## 冻结所有权

- Package 85：`pap-be8085a9fd5705e64525e8e8`，拥有 `body.p1055-p1066` 共 12 个来源。
- Package 86：`body.p1067-p1073`，DILI 介绍、复查、调查、潜在/确诊 Hy's law 流程；只能作为必要防吞并边界，所有权不得转移。
- Package 84：`body.p1043-p1054`，生命体征和既存疾病记录规则；只允许最小相邻只读语境。

## 必须保真的临床逻辑

1. `p1055` 是标题，不独立形成控制点。
2. `p1056-p1058` 是严重肝损伤指征：
   - `p1057` 为 `ALT或AST >3×ULN` 与 `总胆红素 >2×ULN 或 黄疸` 的合取；同时保留“无胆汁淤积或其他高胆红素血症病因”的限定。
   - `p1058` 为 `ALT或AST高值 / ALP高值 >=5` 的独立替代指征。
3. `p1059` 的“以下任一肝功能检查异常”保持外层 OR；满足时必须按 SAE 在 eCRF 记录最恰当诊断，无法确定诊断时才记录实验室检查值异常，并立即报告申办者，时间为获知后不超过 24 小时。不得把诊断优先级、立即报告和 24 小时边界丢失或弱化。
4. `p1060-p1062` 仅适用于 AST/ALT 与总胆红素基线均正常的参与者，研究治疗后两个分支为 OR；不得把基线正常条件拆散或把两个分支改成 AND。
5. `p1063-p1066` 仅适用于 AST/ALT 与总胆红素基线高于 ULN 的参与者，研究治疗后三个分支为 OR。
6. `p1064` 必须保留 `(ALT或AST >2×基线 且 >3×ULN) 或 >8×ULN`，并保留“以较小者为准”；不得把内层合取弱化为 OR，也不得把较小者改成较大者或全部满足。
7. `p1065` 必须保留 `总胆红素较基线升高至少1×ULN 或 总胆红素>3×ULN` 及“以较小者为准”。
8. `p1058/p1062/p1066` 的比值均为 ALT或AST高值与 ALP高值的比值，不得把 GGT、总胆红素或其他指标混入。
9. Package 85 全部属于治疗后 SAE 记录/报告规范，禁止升格为预筛、筛选或基线入排门槛；零候选、`claims_complete=false`。
10. 不得提前吸收 Package 86 的复查、病因调查、潜在/确诊 DILI 或 Hy's law 确诊流程，也不得吸收后续因果关系共同判断或通用 SAE 报告流程。

## 允许写入

- Package 85 配置：`configs/representative_group_package85_hepatic_injury_sae_boundary.v1.json`
- Package 85 专项测试：`test_slice61bw_package85_hepatic_injury_sae_boundary.py`
- Package 85 父级清单：`slice61bw-package85-hepatic-injury-sae-boundary-parent-checklist.md`
- Runner 生成目录：`slice59n-prepare/d001-ii-package85-hepatic-injury-sae-boundary/`
- 各 worker 仅在分配到实现任务时写上述路径；来源核对与反例挑战角色只返回报告。

## 完成条件

- 12 个拥有来源逐字恢复且仅处置一次；必要只读来源实际进入准备证据。
- 零候选、零正式矩阵行、零流程目录新增。
- 上述 AND/OR、阈值、基线分层、诊断优先级、24 小时和跨包边界均有正例与误触反例回归。
- 模型外准备和专项测试通过；父级再决定是否接受并运行更广回归。
