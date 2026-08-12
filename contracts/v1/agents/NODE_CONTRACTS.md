# V2 Phase 0.5 节点与确定性门控合同

## 0. 合同定位

| 项目 | 冻结内容 |
| --- | --- |
| 合同标识 | `enrollment-review/v1/agents` |
| 领域版本 | `schema_version = fixture/v1` |
| 适用范围 | 方案解构、证据规范化、入排判断候选、溯源批评、确定性 Gate、确定性 Projection、Job 运行边界 |
| 当前状态 | Phase 0.5 合同草案；须经用户批准后才可作为 Phase 1 原型的输入，不表示代码已经实现 |
| 权威来源 | 研究方案与当前正式修订案决定标准；其他解释材料只能解释歧义，不能改写标准 |
| 写入范围 | 本合同只规定允许的结构化写入；原方案、原始受试者文件、原 OCR、旧项目和既有临床报告保持只读 |
| 本阶段边界 | 不调用真实 LLM/OCR，不进行新的临床重审，不把旧结论迁移为 V2 真相 |

本文件把语义 Agent 当作受限的候选生产者，把 Gate 当作唯一的业务状态接受者，把 Projection 当作可重建的显示投影。任何“模型认为”“文字看起来合理”都不能替代结构校验、来源定位、状态一致性和阶段隔离。

## 1. 共同不变量

### 1.1 实体与版本

1. 所有合同实体必须带 `schema_version` 和稳定 ID；可编辑实体使用 `revision`，运行事件使用时间戳，来源相关实体使用显式来源引用。各类型不得为追求字段齐全而伪造不适用的时间、来源或 revision。
2. 所有受试者审核结果必须同时绑定 `project_id`、正式方案版本、`rule_set_id`、`rule_set_revision`、`review_episode_id`、`evidence_snapshot_id` 和 `review_run_id`。
3. `AssessmentCandidate` 与 `FinalAssessment` 是不同类型；候选不能通过类型转换、字段补齐、文本正则或 UI 默认值直接变成最终判断。
4. `ActionRequest.blocking_level`、节点主状态、分类计数、排序键和 Action 自动关闭结果均由确定性代码计算，不接受 Agent 自由填写。
5. 后续阶段的资料只能进入新的 `ReviewRun` 或明确的回顾重审；不得覆盖早期阶段的快照、判断或报告。
6. 任何结论性事实、判断、Action 和 Gate 结果都必须保存结构化来源 ID；自由叙述不能作为唯一来源。

### 1.2 Agent 统一写权限

Agent 只能追加以下三类记录：

- `ProtocolDeconstructionDraft`：方案解构草稿，使用 `draft` 命名空间；
- `EvidenceNormalizationCandidate`、`AssessmentCandidate` 等候选，使用 `candidate` 命名空间；
- `CriticRun`：批评运行记录，使用 `critic_run` 命名空间。

Agent 可以追加自己的 `AgentCall` 运行审计记录，但不能写入或更新：

- `FinalAssessment`；
- `ActionRequest` 的 `blocking_level`、关闭状态或转移记录；
- 节点汇总、看板状态、Patient Profile 的事实真相或报告真相；
- 已发布的 `RuleSet` revision、`EvidenceSnapshot`、原文件、原 OCR；
- 旧项目、旧报告、手工入排追踪表或任何未声明的存储根目录。

Gate 只能在输入通过相应确定性检查后写入其职责范围内的接受实体。Projection 只能写可从接受实体重建的投影版本。用户的人工修订和 override 必须通过带 revision、理由和不可变转移记录的命令完成，不能绕过 Gate。

### 1.3 不共享 scratchpad

1. Agent 之间不共享自由文本 scratchpad、隐藏推理、临时结论或未验证的上下文笔记。
2. 节点之间只传递已声明的结构化输入：实体 ID、版本、状态、枚举、来源 ID、`EvidenceSpan`、结构化错误码和范围哈希。
3. 如果需要向下一节点解释原因，只能使用结构化 `reason_code`、`source_ref`、`affected_scope` 和 `uncertainty`；不得把一段 Agent 叙述作为下一节点的事实依据。
4. 上一次失败输出不能自动成为下一次修复的事实输入；修复会话只能收到 Gate 生成的字段级错误和原始固定输入范围。

## 2. 通用版本、幂等与恢复合同

### 2.1 版本字段

所有 Agent 和 Gate 的交互输出都使用 `schema_version = fixture/v1`。节点提示词版本必须独立记录，首版候选值如下，须在实现前由用户批准：

| 节点 | `node_id` | `prompt_version` | 输出类型 |
| --- | --- | --- | --- |
| Protocol Deconstructor | `protocol_deconstructor` | `protocol-deconstructor/1.0.0` | `ProtocolDeconstructionDraft` |
| Evidence Normalizer | `evidence_normalizer` | `evidence-normalizer/1.0.0` | `EvidenceNormalizationCandidate` |
| Eligibility Assessor | `eligibility_assessor` | `eligibility-assessor/1.0.0` | `AssessmentCandidate` |
| Safety/Provenance Critic | `safety_provenance_critic` | `safety-provenance-critic/1.0.0` | `CriticRun` |
| 确定性 Gate | `deterministic_gate` | 不使用 Prompt；`gate_contract/v1` | `GateResult` 及其接受实体 |
| 确定性 Projection | `deterministic_projection` | 不使用 Prompt；`projection_contract/v1` | 可重建 Projection |

实际使用的模型、参数或供应商不是合同真相，但必须写入 `AgentCall.model_config_id` 并引用不可变的 `ModelConfigContract`；模型切换不是同一调用的静默重试。

### 2.2 幂等键

幂等键的输入字段按稳定顺序连接，使用长度前缀或明确分隔，避免不同字符串组合产生同一键。推荐形式为：

```text
sha256(contract_id | node_id | schema_version | prompt_or_code_version |
       model_config_id | input_scope_hash | parent_revision |
       project_id | subject_id | review_episode_id | review_run_id)
```

- Agent 的 `model_config_id` 必须参与幂等键；Gate 和 Projection 使用 `code_version` 代替模型配置。
- 重试使用同一幂等键；只有输入范围、版本、模型配置或业务 revision 改变时才能产生新键。
- 同一幂等键不得产生两个生效的接受实体。重复请求只能返回既有运行记录或既有接受结果。
- `attempt_no` 不参与幂等键，它只用于运行审计和恢复判断。

### 2.3 重试、同会话修复和停止

| 情形 | 允许动作 | 上限与结果 |
| --- | --- | --- |
| 请求中断、超时、未收到完整响应 | 用同一幂等键重新取得结果 | 最多 2 次自动传输重试；不得创建第二个业务结果 |
| JSON 不完整、字段缺失、Schema 不通过 | 把 Gate 的字段级错误发送回同一会话修复 | 首次调用后最多 2 次同会话修复，合计最多 3 次语义尝试 |
| 来源范围、项目、受试者或阶段越界 | 立即停止并记录 `scope_mismatch` | 不得扩大输入范围，不得靠重试消除错误 |
| 缺少必要来源或没有可验证 `EvidenceSpan` | 停在草稿/候选，生成待补资料或解析任务 | 不生成明确判断，不生成阻断 Action |
| Gate 连续拒绝达到上限 | 停在最后一个候选并转人工处理 | 不用正则、默认值或摘要修补为通过 |
| 用户取消或 Job 到达安全取消点 | 保存当前运行记录和可恢复状态后停止 | 不删除原输入、候选或已有接受结果 |
| 服务重启或浏览器关闭 | 从最后一个已提交 Checkpoint 继续 | 不因浏览器断开而把 Job 判为失败或成功 |

同会话修复只能修正结构、枚举、字段关系和来源引用；不能改变输入范围、替换方案版本、选择另一来源、降低 Gate 要求或把候选改写为最终状态。超过上限后，下一次处理必须创建新的 `AgentCall` 或新的 `ReviewRun`，并说明触发原因。

### 2.4 通用运行审计字段

`AgentCallContract` 的机器可读字段以 `contracts/v1/schema/fixture-v1.schema.json` 为准，当前至少包括：

| 字段 | 要求 |
| --- | --- |
| `agent_call_id`、`node`、`schema_version` | 调用和节点身份 |
| `output_kind`、`write_scope` | 该节点唯一允许的候选输出类型和写域 |
| `prompt_version_id`、`model_config_id` | 分别引用不可变的 PromptVersion 与 ModelConfigContract |
| `input_scope_hash`、`input_revision_map` | 输入范围及每个实体的 revision 哈希 |
| `project_id`、`subject_id`、`review_episode_id`、`review_run_id` | 适用时必填；不适用明确写 `null` 原因 |
| `evidence_snapshot_id`、`source_ids` | 事实或判断相关步骤必填 |
| `idempotency_key` | 按 2.2 计算，重复运行必须可查 |
| `attempt`、`max_attempts`、`same_session_group_id` | 记录传输重试和同会话修复归属 |
| `started_at`、`finished_at`、`duration_ms` | 时间和耗时 |
| `outcome`、`error_codes` | `accepted / rejected / stopped / cancelled / partial` 之一及结构化原因 |
| `output_hash`、`gate_result_ids` | 输出完整性和所依赖 Gate |
| `recompute_scope` | 受影响的实体、规则组件、阶段或页面范围 |
| `trigger`、`parent_event_id` | 触发来源和事件链 |
| `input_tokens`、`output_tokens`、`estimated_cost` | 供应商可获得时记录；不可获得时保持 `null`，不补猜测 |

以上字段是运行审计，不作为 Patient Profile 或报告的可见文案。运行记录也不能成为临床判断的来源。

## 3. Protocol Deconstructor 合同

### 3.1 输入范围

允许输入：

- 一个 `Project` 草稿或项目创建请求；
- 一个正式 `ProtocolDocumentVersion` 及其文件页、文本或页面解析结果；
- 当前正式 `Amendment`（如有）；
- `InterpretationSource`（Q&A、澄清函、邮件或医学解释）作为待核对解释材料；
- 既有 `RuleSet` revision 作为只读比较对象，不作为新规则真相；
- 文档页级 `EvidenceSpan` 或待定位的原文范围。

输入必须带项目、方案版本、文件哈希和页范围。不得混入受试者资料、旧项目结论或未经声明的其他方案。

### 3.2 结构化输出

`ProtocolDeconstructionDraft` 至少包含：

| 字段 | 内容要求 |
| --- | --- |
| `draft_id`、`schema_version` | 草稿身份和 `fixture/v1` |
| `protocol_metadata_draft` | 项目名称、方案编号、版本、日期、研究期别候选及其来源 |
| `rule_drafts[]` | 官方 IN/EX 父级编号、原文、适用范围、父子关系候选 |
| `rule_component_drafts[]` | 子组件、有限 `ALL/ANY/NOT` 表达式、阈值、单位、时间锚点/窗口、例外树、研究者判断要求 |
| `workflow_stage_drafts[]` | 预筛、筛选、导入/洗脱、基线/随机等节点候选、锚点和最晚完成点 |
| `evidence_requirement_drafts[]` | 每个组件在各阶段应有的事实、文件、检查、评分或判断 |
| `coverage` | 输入父级、组件、阶段和页范围的覆盖情况；必须能发现漏项和重复 |
| `source_refs[]` | 每个规则、组件、阶段和要求对应的页码/文本定位 |
| `unresolved_items[]` | 不能由方案确定的期别、逻辑、单位、时间窗或解释冲突，使用结构化错误码 |
| `draft_revision`、`created_by_agent_call_id` | 草稿 revision 和运行关联 |

草稿可以提出候选结构，但不得写 `FinalAssessment`、`ActionRequest`、`blocking_level`、节点汇总或正式发布状态。

### 3.3 Gate、恢复和停止

- 先过 `ContractSchemaGate`，再过 `ProtocolIntegrityGate`；缺失官方父级编号、重复编号、父子错位、表达式不闭合、单位/时间锚点不合法或解释材料与正式方案冲突时拒绝发布。
- 同会话修复只接受结构化字段错误；仍不通过时保留草稿并停在“待人工核对”，不自动猜期别、单位、时间窗或例外。
- 只有用户在方案工作台确认修改、且 `ProtocolPublishGate` 通过后，才能产生绑定正式方案版本的新 `RuleSet` revision；Agent 无发布权。
- 不允许读取旧 Markdown 作为业务真相，不允许用项目特异正则补齐漏项，不允许把 Q&A/邮件写成新的方案版本。

### 3.4 幂等键和审计

输入范围哈希覆盖正式方案版本、当前修订、页范围和解释材料版本；同一方案版本、同一提示词/模型配置和同一输入范围重复触发必须复用同一草稿运行。审计字段按第 2.4 节完整记录，另加 `official_rule_ids_seen`、`official_rule_ids_missing`、`phase_candidates` 和 `interpretation_conflict_ids`。

## 4. Evidence Normalizer 合同

### 4.1 输入范围

允许输入一个 `EvidenceSnapshot` 中明确划定的文件/页范围，包括：

- `SourceDocumentVersion`、文档分类、受试者 ID 和上传方式；
- 原始 `OCRPage`、页图、原生 PDF 文本和 OCR 质量信息；
- 已确认的 `CorrectionRecord`，原值不被覆盖；
- 已存在的 `EvidenceSpan` 或待定位文本；
- 可选的 `ReferencedDocument` 线索和当前 `ReviewEpisode`，用于判断来源阶段。

不得输入或修改方案规则；不得读取其他受试者或未声明快照中的资料。

### 4.2 结构化输出

`EvidenceNormalizationCandidate` 至少包含：

| 字段 | 内容要求 |
| --- | --- |
| `candidate_id`、`schema_version` | 候选身份和 `fixture/v1` |
| `clinical_fact_candidates[]` | 对象、属性、值、单位、否定/阳性/未知、时态、确定性、日期精度、来源强度 |
| `clinical_event_candidates[]` | 事件类型、事件时间上下界、记录时间、主体、阶段候选 |
| `medication_exposure_candidates[]` | 药物/类别、剂量、频次、途径、起止范围、适应证和来源 |
| `referenced_document_candidates[]` | 病历中明确引用但未提供的文件及引用位置 |
| `evidence_span_candidates[]` | `bbox / text_range / page_excerpt / page_only` 候选之一、原文摘录、定位置信度、降级原因候选 |
| `conflict_candidates[]` | 同一事实的冲突候选，不选择任何一方 |
| `uncertainty_codes[]` | 否定范围、数值、单位、日期、OCR 或解析风险 |
| `source_refs[]` | 文件、版本、页码、文本范围和页图引用 |
| `coverage`、`unresolved_items[]` | 已处理页范围、未覆盖部分和不能确认的字段 |

输出可以提出 `negated` 或 `unknown` 候选，但“完全未提及”只能提出记录完整性缺口线索，不能提出否定事实。

### 4.3 Gate、恢复和停止

- `EvidenceSpanLocatorGate` 必须先验证来源、页码和实际定位精度；没有可靠坐标不得输出 `bbox`。
- `EvidenceNormalizationGate` 再验证字段、单位、日期精度、主体、否定范围、重复和冲突；未通过的候选不能进入事实真相。
- 低质量 OCR、关键小数/单位/否定词不稳定、来源主体不一致或同一事实冲突时，停在候选并生成解析/补证线索，不形成明确临床判断。
- 不得覆盖原文件、原 OCR 或已确认的校对记录；不得把引用未提供当作正常或阴性；不得把相似指标、其他受试者日期或文件版本日期串入候选。

### 4.4 幂等键和审计

输入哈希覆盖文件内容哈希、页码、OCR/解析参数版本、校对 revision、受试者 ID 和阶段。另加 `source_document_hash`、`page_ids`、`locator_precision_candidates`、`parse_risk_codes` 和 `conflict_group_candidate_ids`。重试不重复创建事实；同一输入的不同校对 revision 必须产生可区分的新候选和影响范围。

## 5. Eligibility Assessor 合同

### 5.1 输入范围

输入严格限制为一个 `Project`、一个已发布 `RuleSet` revision、一个 `ReviewEpisode`、一个 `EvidenceSnapshot` 和该范围内已经通过 Gate 的：

- `Rule`、`RuleComponent`、有限表达式和 `EvidenceRequirement`；
- `ClinicalFact`、`ClinicalEvent`、`MedicationExposure`、`ReferencedDocument`；
- `EvidenceExpectation`、`ConflictGroup`、相关 `EvidenceSpan`；
- 受影响范围内的前一 `ReviewRun` 只读差异，用于判断增量重算范围。

Assessor 不读取其他受试者、其他项目、未绑定阶段的资料、模型自由叙述或旧项目结论。

### 5.2 结构化输出

每个 `RuleComponent` 生成一个 `AssessmentCandidate`，至少包含：

| 字段 | 内容要求 |
| --- | --- |
| `candidate_id`、`schema_version` | 候选身份和 `fixture/v1` |
| `rule_component_id`、`review_episode_id`、`evidence_snapshot_id` | 目标范围，必须唯一对应 |
| `candidate_state` | 入选/排除组件的候选状态；不是 `FinalAssessment` |
| `fact_refs[]`、`evidence_span_refs[]` | 实际使用的事实和证据定位 |
| `candidate_gap_types[]` | 结构化缺口建议；不计算阻断等级 |
| `predicate_observations[]` | 原子谓词、阈值、单位、时间锚点、例外和研究者判断的逐项观察 |
| `coverage` | 规则组件覆盖、缺失、重复和越界引用 |
| `uncertainty_codes[]`、`reason_codes[]` | 证据不足、冲突、OCR/解析风险或来源较弱等结构化原因 |
| `candidate_confidence` | 仅为候选质量字段，不得成为临床状态阈值 |
| `unresolved_items[]` | 仍需 Gate 或研究者处理的字段 |

Assessor 不得输出或写入 `FinalAssessment`、`ActionRequest.blocking_level`、节点汇总或报告。候选中的状态、缺口和理由均须由 Gate 重新计算，不能照抄为最终值。

### 5.3 Gate、恢复和停止

- `EligibilityAssessmentGate` 逐组件检查输入范围、事实引用、表达式、阈值/单位、时间窗、例外完整性、状态与缺口矩阵和 EvidenceSpan。
- 任何跨组件串项、漏规则、未知来源、冲突被自动择一、沉默被当作否认、缺锚点借用其他日期或不合法状态/缺口组合都会拒绝候选。
- Gate 失败可请求同会话修复；修复只能补齐结构化引用和观察，不得直接修改最终状态。超过上限停在候选，转人工处理或补证。
- 没有足够证据时允许候选“暂不能明确”，但最终的 `gap_type`、`blocking_level`、责任方和到期节点必须由确定性代码生成。

### 5.4 幂等键和审计

输入范围哈希覆盖规则模型 revision、规则组件集合排序、ReviewEpisode、EvidenceSnapshot、接受事实 revision、期待证据 revision 和前一 ReviewRun revision。另加 `rule_component_ids_seen`、`rule_component_ids_missing`、`fact_dependency_ids`、`candidate_gap_type_codes` 和 `cross_component_reference_codes`。

## 6. Safety/Provenance Critic 合同

### 6.1 触发与输入范围

由 `CriticAdmissionGate` 只在以下情况触发：高风险规则、来源冲突、低质量 OCR/关键字段风险、评估 Gate 异常或预先登记的错误族。输入只包括触发范围内的一个或多个 `AssessmentCandidate`、已接受事实、规则组件、EvidenceSpan、ConflictGroup 和相关 GateResult。

Critic 不接受全项目自由文本，不读取 Agent scratchpad，不读取与触发范围无关的受试者或阶段资料。

### 6.2 结构化输出

`CriticRun` 至少包含：

| 字段 | 内容要求 |
| --- | --- |
| `critic_run_id`、`schema_version` | 不可变批评运行身份 |
| `target_refs[]` | 目标 `rule_component_id`、`candidate_id` 和相关事实/Span |
| `trigger_codes[]` | 触发原因和风险类别 |
| `disposition` | 仅允许 `veto / downrank / open_action / none` |
| `reason_codes[]`、`source_refs[]` | 可核验的批评原因和证据定位 |
| `required_followup[]` | 需要补充的证据或人工核对，不含自由行动命令 |
| `affected_scope` | 受影响组件和需要重算的范围 |
| `input_scope_hash`、`gate_result_refs[]` | 输入和门控关联 |
| `critic_revision`、`created_by_agent_call_id` | 运行版本和调用关联 |

`veto` 只是 Gate 的否决信号，不是最终“不满足”；`downrank` 只是证据强度/优先级信号；`open_action` 只是开行动候选。任何最终状态、Action 阻断等级和节点汇总仍由 Gate/Projection 计算。

### 6.3 Gate、恢复和停止

- 无可靠 `EvidenceSpan` 时不得产生 `veto`；没有来源只能记录“无法确认”，不能凭批评文本否决。
- Critic 失败、超时或输出不完整时保留原候选和 Gate 结果，记录待重试，不静默覆盖原判断。
- 同会话修复只接收字段级 Gate 错误和固定目标范围；不因批评失败扩大为全项目重跑。
- Critic 不得自动选择冲突来源、编辑规则、关闭 Action 或把 `provenance_followup` 提升为阻断。

### 6.4 幂等键和审计

输入哈希覆盖触发规则、候选 revision、相关事实/Span revision、GateResult 和风险触发版本。另加 `admission_gate_result_id`、`triggered_by_error_codes`、`disposition`、`veto_evidence_refs` 和 `critic_outcome`。同一候选 revision 和同一触发条件不得重复产生生效批评结果。

## 7. 确定性 Gate 合同

### 7.1 GateResult 统一结构

所有 Gate 返回 `GateResult`，至少包括：

```text
gate_result_id
gate_name
schema_version = fixture/v1
code_version = gate_contract/v1
input_scope_hash
input_revision_map
result = accepted | rejected | blocked
input_entity_refs[]
accepted_entity_refs[]
rejected_entity_refs[]
error_codes[]
affected_scope
recompute_scope
idempotency_key
parent_event_id
created_at
output_hash
```

GateResult 是不可变审计事实。后续修正必须产生新 GateResult 和新 revision，不能修改旧结果。

### 7.2 Gate 清单

| `gate_id` | 输入实体范围 | 结构化输出 | 可写实体 | 重试/停止 | 禁止动作 |
| --- | --- | --- | --- | --- | --- |
| `contract_schema_gate` | 任一 Agent draft/candidate/CriticRun、fixture 或 Job 事件 | `GateResult`、字段级错误、接受/拒绝引用 | `GateResult`；通过后只允许建立对应 draft/candidate/critic 记录 | 纯函数重算；Schema 失败即拒绝，不能靠默认值补齐 | 不把非法 JSON 或未知枚举修成合法业务含义；不产生 FinalAssessment |
| `protocol_integrity_gate` | `ProtocolDeconstructionDraft`、正式方案版本、Amendment、来源定位 | 父级编号/数量、树、逻辑、期别、阈值、单位、时间窗、例外和阶段覆盖的 `GateResult` | 通过的规则/组件/阶段草稿接受记录；不发布正式规则 | 错误修复后按同一输入重算；缺官方来源、编号或逻辑不完整即停 | 不猜期别、不合并独立期别、不弱化 AND/OR、不把解释材料改成方案版本 |
| `protocol_publish_gate` | 用户已确认的规则草稿、`protocol_integrity_gate` 结果、正式方案版本 | 新 `RuleSet` revision 发布资格和差异摘要 | 绑定正式方案版本的新 `RuleSet` revision | 任何发布条件不满足即拒绝；只能重新编辑草稿后再提交 | 不由 Agent 发布；不覆盖旧 revision；不在发布时新增项目特异规则 |
| `evidence_span_locator_gate` | 文件版本、页图/原文/OCR、Span 候选、校对 revision | 一个实际存在的定位层级、原文、降级原因和 `GateResult` | `EvidenceSpan` 接受记录 | 定位失败停在候选并生成解析待办；不得循环猜坐标 | 无坐标不得输出 bbox；不得用装饰性高亮伪造定位 |
| `evidence_normalization_gate` | `EvidenceNormalizationCandidate`、已接受 `EvidenceSpan`、文件/页、校对记录 | `ClinicalFact`、`ClinicalEvent`、`MedicationExposure`、`ReferencedDocument` 或拒绝结果 | 只写接受的事实/事件/用药/引用文件和依赖关系 | 字段、来源、主体、单位、日期、极性或冲突失败即拒绝相应候选；不影响无关范围 | 不覆盖原 OCR；不把沉默写成否认；不自动择一冲突来源 |
| `critic_admission_gate` | 风险旗标、候选、GateResult、错误族登记 | 是否触发 Critic、触发码、固定输入范围 | 触发记录和 `GateResult` | 条件不满足则跳过并记录；条件满足但输入缺失则阻断 Critic 运行 | 不强制所有规则运行 Critic；不把触发判断当最终临床判断 |
| `eligibility_assessment_gate` | 已发布规则、一个 Episode、一个 Snapshot、接受事实/Span/Expectation、AssessmentCandidate、CriticRun | 逐组件 `FinalAssessment` 资格、状态/缺口一致性、阻断计算输入 | 仅在全部条件通过后写 `FinalAssessment`；拒绝只写 GateResult | 表达式、阈值、时间窗、证据、冲突或状态矩阵失败即停；不以文本修补 | Agent 不得写 FinalAssessment；不从 narrative/reasoning 或相似指标推导状态 |
| `action_gate` | `FinalAssessment`、同组件 gap、EvidenceExpectation、规则要求、Critic信号和用户操作 | `ActionRequest`、`ActionTransition`、确定性责任方/证据/到期节点/阻断等级 | 写 Action 及不可变转移记录 | 自动关闭必须满足同组件专属谓词和新 ReviewRun；人工 override 需理由并记录 | 无关上传不得关闭；关闭不等于规则通过；不接受 Agent 的 blocking_level |
| `stage_run_isolation_gate` | Project、正式方案、RuleSet revision、ReviewEpisode、EvidenceSnapshot、既有 ReviewRun | 新 `ReviewRun`、阶段隔离结果或 stale/diff 范围 | 只追加新的 ReviewRun、差异和 stale 标记 | 输入阶段/快照不一致即停；后续资料只能新运行或显式回顾重审 | 不覆盖早期运行；不借用其他阶段日期/文件名；不静默改写历史报告 |
| `job_event_recovery_gate` | Job 命令、JobStep、Checkpoint、租约状态、幂等键和上一个事件 | 合法 Job 状态转移、`JobEvent`、Checkpoint、可恢复点、重试/取消结果 | 只写 Job 运行记录和 Checkpoint，不写临床真相 | 从最后成功 Checkpoint 恢复；非法转移、重复事件或租约失效即停并保留原因 | 不让浏览器/SSE拥有 Job 生命期；不产生永久 processing；不重复应用 Action |

### 7.2.1 Gate 与 Projection 的逐项运行字段

上表的每一次 Gate 运行都必须实例化 7.1 的 `GateResult`，不能因“确定性代码”而省略：

- `schema_version = fixture/v1`，`code_version = gate_contract/v1`；Gate 不使用 Prompt 或模型配置，也不伪造这两个字段；
- `idempotency_key` 必须覆盖 Gate 身份、合同版本、输入范围哈希和输入 revision map；同一输入重算只能复用同一键；
- Gate 不做语义同会话修复；字段级错误由 `error_codes` 返回给上游，修复后以新输入 revision 重新执行；
- `input_entity_refs / accepted_entity_refs / rejected_entity_refs / affected_scope / recompute_scope` 必须明确记录本次处理的实体和影响范围；
- Gate 失败只产生 `GateResult = reject/blocked`；Projection 输入不完整只产生不完整投影或停止记录。二者都不能用默认值补齐临床字段，不能把失败显示成成功。

下表进一步固定每一个确定性 Gate/Projection 的幂等输入和专属审计字段。输入、输出、可写实体、禁止动作和停止条件仍以 7.2 与 8 节为准。

| 处理单元 | 幂等输入范围 | 专属审计字段 | 重算/停止边界 |
| --- | --- | --- | --- |
| `contract_schema_gate` | 输出类型、原始输出哈希、输入实体 revision | `schema_errors`、`unknown_fields`、`unknown_enums` | 同输入纯函数重算；Schema 不通过即停，不修补业务语义 |
| `protocol_integrity_gate` | 方案版本、修订案版本、页范围、解构草稿 revision | `official_rule_ids_seen`、`missing`、`duplicate`、`parent_child_errors`、`interpretation_conflict_ids` | 结构错误由上游修复后重算；来源或父级不全即停 |
| `protocol_publish_gate` | 用户确认草稿 revision、完整性 GateResult、正式方案版本 | `confirmed_by`、`confirmation_revision`、`publish_diff_hash` | 未确认或版本不一致即拒绝；不覆盖旧规则 revision |
| `evidence_span_locator_gate` | 文件内容哈希、页码、原文/OCR版本、校对 revision、Span 候选 | `locator_precision`、`degradation_reason`、`anchor_hash` | 不能稳定定位时保留候选并停在页码/摘录级，不猜坐标 |
| `evidence_normalization_gate` | 候选 revision、接受的 Span revision、文件/页、校对 revision | `fact_refs`、`subject_match`、`unit_checks`、`polarity_checks`、`conflict_group_ids` | 单条候选失败不影响无关范围；关键字段风险阻止进入事实真相 |
| `critic_admission_gate` | 风险旗标 revision、候选 revision、相关 GateResult | `trigger_codes`、`admission_scope`、`skipped_reason` | 条件不满足记录跳过；输入不足时停，不扩大全项目范围 |
| `eligibility_assessment_gate` | RuleSet revision、Episode、Snapshot、事实/Expectation revision、候选、CriticRun | `rule_component_ids`、`fact_dependency_ids`、`state_gap_matrix_result`、`blocking_calculation_inputs` | 任一组件结构不一致即拒绝该组件；不生成默认 FinalAssessment |
| `action_gate` | FinalAssessment revision、同组件缺口、Expectation、用户命令、关闭谓词版本 | `closure_predicate_id`、`target_party`、`due_stage`、`transition_type`、`override_reason_ref` | 关闭谓词不满足即保持开放；人工 override 缺理由即停 |
| `stage_run_isolation_gate` | Project、Episode、Snapshot、RuleSet revision、既有 Run revision | `stage_id`、`snapshot_id`、`prior_run_id`、`stale_scope` | 阶段或快照不一致即拒绝；早期 Run 不可覆盖 |
| `job_event_recovery_gate` | Job ID、命令 ID、上一个事件、Checkpoint revision、租约和幂等键 | `event_type`、`previous_state`、`next_state`、`checkpoint_id`、`retry_reason` | 非法转移、重复副作用或无法恢复即停并保留已完成部分 |
| `patient_profile_projection` | Subject、接受事实/事件/用药 revision、Span、Conflict、Expectation、Episode/Action | `theme_order`、`risk_filter`、`source_link_count`、`unresolved_source_count` | 来源缺失显示缺口；不补事实，不隐藏冲突 |
| `node_rollup_projection` | Episode、全部 FinalAssessment revision、gap、blocking、Expectation、Action 计数 | `state_counts`、`blocking_counts`、`sort_key`、`expectation_counts` | 只读结构状态；发现输入不全即停止投影，不降级为“未发现障碍” |
| `project_board_projection` | Project、Subject、Episode、EpisodeRollup 和阶段 revision | `stage_columns`、`filter_revision`、`sort_revision`、`entry_refs` | 视图变化不写业务；阶段缺失即不显示虚假单元格 |
| `action_center_projection` | ActionRequest/Transition、组件、Span、Episode、责任方和到期节点 revision | `open_count`、`closed_count`、`owner_counts`、`deep_link_refs` | 只投影已接受 Action；不重新判断关闭条件 |
| `review_run_diff_projection` | 显式选择的同主体/同项目 Run A、Run B 及其实体 revision | `run_a_id`、`run_b_id`、`changed_entities`、`stale_scope` | Run 不可比较或主体不一致即停；不写回旧 Run |
| `report_projection` | 指定 ReviewRun、方案版本、RuleSet revision、Snapshot、FinalAssessment、Action 和输出格式 | `report_revision`、`source_coverage`、`included_sections`、`output_hash` | 来源覆盖不完整即标记未完成，不创建新临床判断 |

### 7.3 FinalAssessment 的唯一生成路径

1. `AssessmentCandidate` 进入 `eligibility_assessment_gate` 前必须已经通过 Schema、来源定位、事实接受和阶段隔离检查。
2. Gate 只读取结构状态、事实引用、`gap_type` 候选、EvidenceExpectation、ConflictGroup、CriticRun 和规则表达式；不读取自由叙述来决定状态。
3. Gate 通过后，确定性 Evaluator 写入一个绑定 `review_run_id` 的 `FinalAssessment`，并由 `action_gate` 计算 Action。
4. Gate 不通过时，只能得到 `GateResult = reject/blocked` 和待处理范围；不得生成“默认通过”“默认不满足”或隐含阻断。
5. 任何人工修改都产生新 revision 或新 ReviewRun；旧 `FinalAssessment` 不被覆盖。

### 7.4 状态与缺口一致性矩阵

| 最终状态 | 必要条件 | 允许/要求的 `gap_type` |
| --- | --- | --- |
| `满足` / `未触发` / `不满足` / `已触发` | 必要事实完整、确定性可计算、来源可追溯、无争议冲突 | 无阻断缺口；可有 `provenance_followup` |
| `暂不能明确` | 证据或事实不足，或关键解析不可靠 | 必须有具体缺口，如记录不完整、引用文件未提供、必做检查未完成、结果字段缺失、日期锚点缺失或 OCR/解析风险 |
| `需专业判断` | 客观事实充分，但方案要求的研究者判断尚未记录 | `professional_judgment` |
| `存在冲突` | 同组件的来源或权威解释尚未解决 | `source_conflict` 或 `interpretation_conflict` |
| `尚未到期` | 当前 Episode 尚不要求完成 | `future_stage_not_due` |
| `不适用` | 规则结构明确证明该组件不适用于本 Episode | 仅允许 Gate 计算出的适用性结果，不得由 Agent 自由填写 |

不符合矩阵的组合直接拒绝；`provenance_followup` 默认非阻断且可计数，不能被合并成“证据不足”。

## 8. 确定性 Projection 合同

Projection 是只读展示或导出数据的重建结果，不是业务真相。每个 Projection 都记录 `projection_revision`、输入 revision map、输入哈希、生成时间、`projection_contract/v1`、幂等键和 `recompute_scope`。

| `projection_id` | 输入实体范围 | 结构化输出 | 可写实体 | 停止与禁止动作 |
| --- | --- | --- | --- | --- |
| `patient_profile_projection` | 一个 Subject、按时间排序的接受 ClinicalFact/Event/MedicationExposure、EvidenceSpan、ConflictGroup、EvidenceExpectation、ReviewEpisode 和 Action | `PatientProfileView`：主题泳道、事件时间/记录时间、日期精度、风险过滤、证据覆盖、关联规则/Action/来源 | 只写可重建的 `ProjectionRevision` 或缓存；不写事实真相 | 缺来源时显示缺口/未定位，不补事实；不得把未记录显示为否认，不得隐藏冲突 |
| `node_rollup_projection` | 一个 ReviewEpisode 下全部 `FinalAssessment`、`gap_type`、`blocking_level`、`EvidenceExpectation` 和确定性 Action 计数 | `EpisodeRollup`：主状态、分类计数、阻断级别、最晚完成节点、固定排序键 | 只写可重建的 `EpisodeRollup` 投影 | 不读取 narrative、候选、模型信心或 Critic 叙述；不得改变组件状态；排序和计数必须纯函数重建 |
| `project_board_projection` | Project、Subject、ReviewEpisode、EpisodeRollup、Action 摘要和阶段信息 | 受试者×阶段看板行、筛选/排序字段、阶段入口和风险计数 | 只写可重建看板投影 | 不把多个阶段压成一个结论；不隐藏阶段入口；不因排序/筛选改变业务 revision |
| `action_center_projection` | ActionRequest、ActionTransition、RuleComponent、EvidenceSpan、ReviewEpisode、责任方和到期节点 | 可按责任方/到期节点/gap/阻断筛选的行动清单及深链 | 只写可重建行动投影 | 不重新计算关闭条件；不将系统关闭、人工 override 和重开混为一种状态 |
| `review_run_diff_projection` | 两个同一 Subject/Project 下、显式选择的 ReviewRun 及其接受实体 | 前后事实、组件状态、Action、EvidenceSpan 和 stale 影响范围差异 | 只写 `ReviewRunDiffProjection` | 不跨主体/跨项目静默比较；不把差异写回任一旧运行 |
| `report_projection` | 指定 ReviewRun、正式方案版本、RuleSet revision、EvidenceSnapshot、FinalAssessment、Action 和来源 | 个人/中心/项目报告底稿及 HTML/Markdown 数据 | 只写报告投影或新报告版本 | 不展示内部运行审计、模型名称、指令性措辞；不能在报告生成时创建新的临床判断 |

### 8.1 Patient Profile 首屏投影规则

- 默认优先展示入排相关、异常、临界、趋势变化、冲突、资料缺口和当前节点待办；无关正常结果仍可进入完整明细。
- “未记录”显示为可行动的 `EvidenceExpectation` 状态，不生成“正常”“否认”或“未发现异常”的事实。
- 每个事件必须显示来源文件、版本、页码和实际 `EvidenceSpan` 定位精度；冲突事实并列显示。
- 后续阶段事件必须带阶段标签和 ReviewRun 关联，不得混入早期运行的结论区。

### 8.2 节点汇总规则

`node_rollup_projection` 只使用结构化状态，主状态顺序固定为：

1. `明确障碍`：入选组件确定不满足或排除组件确定触发；
2. `当前节点缺口`：到期必需资料、记录、检查、评分、锚点或结果字段不足；
3. `存在冲突`：争议组件不能明确；
4. `需专业判断`：客观事实齐全但研究者判断缺失；
5. `后续节点关注`：只有尚未到期项目；
6. `未发现明确障碍`。

`溯源待办 n` 单独计数，不提升主状态；OCR/解析风险若影响当前明确化，计入当前节点缺口并保留自己的分类计数。主状态、计数和排序不读取 Agent 总结文本。

## 9. 责任边界与禁止动作总表

| 角色 | 可以做什么 | 明确禁止 |
| --- | --- | --- |
| 语义 Agent | 在固定输入范围内生成 draft/candidate/CriticRun，并追加 AgentCall | 直接写 FinalAssessment、Action blocking、rollup、报告真相；共享 scratchpad；改原资料 |
| Schema/Protocol/Evidence/Assessment Gate | 校验结构、来源、逻辑、阶段、状态矩阵并追加接受实体/ GateResult | 通过正则修复临床语义；猜测缺失事实；自动选择冲突来源 |
| Action Gate | 根据最终组件状态和专属关闭谓词创建 Action、计算阻断等级和转移 | 接受 Agent 的阻断等级；无关上传自动关闭；把关闭当作规则通过 |
| Job Gate | 管理幂等、Checkpoint、重试、取消和恢复事件 | 让浏览器断开取消业务；重复执行副作用；用运行状态代替临床状态 |
| Projection | 从接受实体重建 Profile、看板、行动、差异和报告 | 发明事实；改变业务状态；把内部审计显示为用户结论 |
| 用户/医学监查员 | 查看来源、编辑允许的草稿、填写专业判断、执行人工 Action override 并留理由 | 在没有来源或理由时确认结论；删除原始证据或旧运行 |

任何未在本表明确授予的写权限都视为禁止。合同通过后仍需由后续实现、Gate 测试、真实浏览器和 Phase 1.5 UAT 分别证明行为；本文件本身不是实现完成证明。
