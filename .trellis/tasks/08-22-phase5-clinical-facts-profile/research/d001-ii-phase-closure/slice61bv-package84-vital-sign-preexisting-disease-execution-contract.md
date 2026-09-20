# D001 II 第 84 包模型外来源闭包执行合同

## 目标

为冻结计划第 84 包 `pap-ab31cb1fdc0643d57a0a41a2` 的 `body.p1043-p1054` 建立可恢复、零入排候选的模型外来源闭包。只处理来源、所有权、语义边界、父级清单、准备证据和确定性回归，不调用临床语义模型，不发布控制点。

## 权威来源

1. 原始 D001 DOCX 及其冻结 SHA-256。
2. `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/frozen_phase_plan.json`。
3. 同目录 `coverage_manifest.json` 与结构块 `structure/blobs/protocol_blocks/3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d.json`。
4. 已接受的第 80-83 包检查点、配置和测试仅作为相邻实现模式，不得覆盖原始方案。

## 拥有与边界

- 第 84 包仅拥有 `body.p1043-p1054`：生命体征异常 `p1043-p1048` 与既存（合并）疾病 `p1049-p1054`。
- `p1043/p1049` 为标题，不独立形成控制点。
- `p1044-p1048` 是治疗期生命体征异常归类和强制报告规则；保持研究者判断层、任一标准即必须报告的外层 OR，以及 `p1047` 示例、`p1048` 内部 OR。
- `p1050` 定义筛选访视或首次给药前既存疾病，并要求记录于病史和基线状况；这是资料记录边界，不得升格为入排标准或缺失即不通过。
- `p1051-p1053` 必须解析为同时满足的条件：研究期间发生频次/严重程度/特征恶化或改变，并且该恶化或改变不是疾病预期进展，才将既存疾病记录为 AE。不得把相邻两个列表项错误改成 OR。
- `p1054` 只要求用适当描述体现既存疾病变化；“偏头痛频次增加”是示例，不得升格为唯一表达或通用病种条件。
- 第 83 包实验室异常规则只读防混同；第 85 包 `p1055-p1066` 及以后特殊肝功能 SAE/报告流程不得进入所有权或提前处置。

## 最小闭包要求

- 拥有来源 12 个必须逐字进入提示。
- 只读闭包应包含必要的 AE 定义、收集/记录时间、D1 给药前后锚点、第 83 包实验室异常平行结构及第 85 包必要防吞并边界；不得注入无关疗效、Ⅲ期或后续报告流程文本。
- `required_candidate_source_refs=[]`，所有拥有来源均不得发射预筛、筛选或基线入排候选。
- `claims_complete=false`，正式矩阵与程序目录保持不变。

## 执行角色

1. `worker_01`：只读核对原始 DOCX、结构块、冻结计划、列表层级及第 83-85 包所有权。
2. `worker_02`：在本合同范围内创建第 84 包配置、模型外准备、父级清单和专项测试。
3. `worker_03`：只读挑战判断/强制报告混同、OR/AND 反转、既存疾病升格入排门槛、示例升格和跨包吞并。

## 写入范围

仅允许 `worker_02` 新建或修改：

- `configs/representative_group_package84_vital_sign_preexisting_disease_boundary.v1.json`
- `test_slice61bv_package84_vital_sign_preexisting_disease_boundary.py`
- `slice61bv-package84-vital-sign-preexisting-disease-boundary-parent-checklist.md`
- `slice59n-prepare/d001-ii-package84-vital-sign-preexisting-disease-boundary/`

`worker_01/03` 只读。所有工作均限当前工作树；不得修改方案、受试者资料、正式矩阵、应用代码或既有检查点。

## 完成证据

- 模型外准备通过，来源数量、提示哈希、配置哈希可复核。
- 专项、Phase 闭包、方案与 Agent、治理工具测试通过。
- 提示最小性、零候选、正式矩阵零写入与执行审计通过。
- Codex 父级独立审阅并记录拒绝/采纳的语义建议后，方可形成检查点。
