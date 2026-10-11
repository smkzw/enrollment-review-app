Trellis context noted; this remains a bounded delegated review, no task creation. Locating the delta.

# 工程审查报告：来源归因边界 delta（源自 HEAD 7a902e87 的工作树状态，只读，未运行测试）

先说明证据边界：Bash 被拒，无法计算 7a902e87 的精确 diff；本轮读取了 3 个源文件的关键定义/消费者与 2 个测试文件的新增用例（共 9 次聚焦读取）。不声称模型独立性，不构成临床或验收结论。

## 必须修复（1 项）

**F1（高）· 段首冒号标题的新跨句授权缺"研究侧内容"的结构性断点，可隐藏真实研究要求**
- 位置：`app/agents/protocol_control_source_interpretation.py:86-112`（新路径 `:104-112`）；断点词表 `:67-71`；配套检测 `:115-130`；消费者 `:2952-2960`、`:1838-1858`。
- 首因：新路径的研究侧保护只有两个词表检测——`_STUDY_ADOPTION_RE`（仅"本研究/本方案/本试验/本项目+规定/要求/…"、"入选/排除/入组标准"等固定搭配）与 gap 内"另一外部归因"正则。**普通祈使句与段内小标题都不构成断点**，而同一代码库在 `:1090` 已存在祈使词表（`(?:受试者|患者|研究者)[^。；;]{0,32}(?:须|应|需)|必须|不得|…`），新路径未复用。
- 具体反例（逐条按代码推演可确认通过）：
  - 单元原文＝`某指南推荐：一般人群处理原则。入组要求：受试者须完成筛选期全部访视。`
  - 陈述＝`受试者须完成筛选期全部访视`，`force="required"`，`decision_functions=["action"]`，`control_authority="cited_external_rationale"`，`attribution_quote="某指南推荐："`；review 决策 `cited_external_rationale`，无 target 字段、无 `unresolved_aspects`、coverage 无候选。
  - 判定链：外部正则命中（指南+推荐）→ `basis_at==0`、以冒号结尾（`:107`）→ gap=`一般人群处理原则。入组要求：` 无另一外部归因（`:111`）→ `text[:end]` 无模式命中（"入组要求"不是"入组标准"，动作句无"本研究"）→ `_attribution_in_source_scope` 返回 True → `validate_source_interpretation:2952` 与 `validate_source_target_review:1838` 双双确认 → 该必做动作不产生候选控制（`:1849-1851`；deconstructor `:8179-8191` 反向还会拒绝其为控制）→ **研究要求被当作外部说明关闭**。prompt `:3045-3046` 自述"一个段落同时有外部说明与本研究要求时必须拆成不同陈述"，证明混合段落在设计上存在，此通道不是理论构造。
- 加重项（同一首因）：该单元形若不声明归因，`_has_external_attribution_before_action:127-130`（首个冒号前缀走同一 helper）同样返回 True → `:2965-2968` 报 `SOURCE_ATTRIBUTION_MISSING`。即：**模型在该形态下没有"研究侧陈述"选项，被迫声明外部归因**，而确认门又接受之。
- 最小修正方向（不代改）：在 `:104-112` 增加结构断点——(a) header 与动作之间出现新的冒号结尾前缀（另一段落标签）即视为授权中断；(b) 对动作句或 `header_end..动作结束` 复用 `:1090` 的祈使词表强制非外部处理；同步改 `:115-130` 保持两向一致。已核正例（`:3997-4036` 三条）gap 内无冒号标签、动作句无"主体+须/应/需"，不会被该修正误伤；属 validator 侧改动（该身份本次已变更），不动 prompt/schema/compiler。

## 其余挑战项：支持无发现

- **拒绝源支持型段首归因**：未发现越界拒绝。保留的拒绝形态（非单元起点前置任何文本、basis 无转述动词、gap 出现另一外部归因、basis 含句读、动作不唯一）均由 `:104-112` 与测试 `:4039-4059`（六型）、`:3950-3969`（采纳/同句/无据）显式断言，且与冻结说明逐条一致。
- **陈旧复用/失败归因变成功回执**：仅 validator 身份变（`:2069-2088`，新常量入列 `:2072`；prompt/schema/compiler 未动）；`_same_deep_components_with_current_gate:2095-2109` 使仅 validator 差异允许复用但必须过当前门：已完成批次 `:3199-3213` 先 `_validate_saved_source_review`（内含新归因规则）再 `_validate_deep_batch_output`，失败即 `refresh_required`；受限结果由 `restricted_batch_from_review` 重推（`:3178-3195`）。身份断言测试 `tests/v2/services/test_protocol_control_execution.py:6200-6250` 覆盖"仅门版本变化→reusable 且无模型调用→记录 `revalidated_from_gate_version` 与含新常量的完整 validator 串"。失败回执侧：`_preserved_unresolved_review_proof` / `_preserved_temporal_restriction_proof`（`execution.py` 约 `:2832-2917`）分别要求当前 `validate_source_target_review`/受限重推通过，失败归因输出不能被固化为既有回执。
- **下游一致性**：`EXTERNAL_RATIONALE_AS_CONTROL`（deconstructor `:8179-8191`）、对应恢复排除（`:8915-8920`）、`SOURCE_ATTRIBUTION_DECISION_INVALID`（`:1893-1896`，外部权威陈述不得改判为覆盖/已有目标）、`target_review_indexes:1411-1416`（外部权威仍须核对）——权威必须由来源陈述与 SourceTargetReview 双向显式提出，未见单侧采纳。

## 残余限制（非 must-fix）
1. 裸文档标签标题（`说明书：`、`按说明书：`、`参考文献：`，无转述动词）仍被 `:90` 拒绝；方向保守（要求留在研究侧/未决），但该形态无正/负用例，是否属"源支持的段首归因"建议 owner 明确。
2. prompt `:3039-3040` 仍写"同一句动作之前"，未随新跨句路径更新（身份纪律要求 prompt 不变）；门与提示暂时不一致：守规模型可能不提议该路径，越界模型提议后又被新门确认——F1 修正后此不一致的危害降为阻塞/修复回路问题而非隐藏。

## 未读依赖
`_validate_saved_source_review`/`_validate_deep_batch_output`/`_saved_deep_run_result` 内部；`validate_source_interpretation` 全文（本轮覆盖归因相关块及 `SourceStatement` 模型校验 `:220-228`，并已全量 grep `control_authority` 站点，未见"权威 vs action 功能"交叉校验）；无 git diff 校验"execution.py 仅身份变更"的穷尽性。合成证据仅代表测试口径；真实最新作业在本修复前已停止，无生产证据，无联合发布结论。
