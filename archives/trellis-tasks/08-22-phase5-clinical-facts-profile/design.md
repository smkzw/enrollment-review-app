# Phase 5 技术设计：临床事实与 Patient Profile

## 1. 架构边界

Phase 5 在 Phase 4 的活动证据修订之上新增一条独立、不可变、可重放的事实写路径：

`活动证据闭包 -> Evidence Normalizer 候选 -> 确定性门禁 -> 事实发布 -> 规则索引/资料期望 -> Patient Profile 投影`

语义模型只生成候选。活动证据身份、定位真实性、极性、日期边界、单位、重复/冲突、覆盖、发布和投影均由确定性代码负责。本阶段不创建入排结论、ReviewRun、ActionRequest 或报告。

## 2. 权威身份与存储

### 2.1 不可变权威元组

每个规范化运行、发布事实、事件、暴露、冲突、期望和 Profile revision 必须绑定：

`project_id / subject_id / review_episode_id / episode_revision / protocol_version_id / rule_set_id / rule_set_revision / evidence_snapshot_v2_id / complete_processing_revision_id`

运行开始时冻结该元组和完整处理修订的文档、页、有效文本、校对、OCR 风险及定位清单；发布事务开始前再次读取审核节点活动指针。指针或 episode revision 变化时，结果记为陈旧并拒绝发布。

### 2.2 新写表

迁移 `0013_clinical_facts_profile_v2` 新建：

- `fact_normalization_runs`、`fact_normalization_calls`、`fact_gate_results`；
- `clinical_facts_v2`、`clinical_events_v2`、`medication_exposures_v2`；
- `fact_evidence_locator_links`、`event_fact_links`、`exposure_fact_links`；
- `clinical_conflict_groups_v2` 及成员表；
- `fact_rule_links_v2`；
- `evidence_expectations_v2`；
- `patient_profile_revisions_v2`。

候选完整 JSON、原始输出哈希、输入闭包哈希和逐候选门禁结果保存在运行/调用/门禁记录中；Agent 无权写发布表。旧 `clinical_facts / evidence_expectations / patient_profiles` 保留为只读回归锚点，Phase 5 repository 不读取它们。

### 2.3 定位只有一个真相源

发布实体通过 `fact_evidence_locator_links` 引用 Phase 4 `EvidenceLocatorArtifact`。候选只能引用当前完整处理修订闭包中的 locator id；残余的新定位建议须经过 Phase 4 定位门禁后才可引用。Profile 由 locator 生成文件、页、文本范围和真实 bbox 跳转；没有坐标时按真实精度降级，绝不补画红框。

## 3. 领域合同

### 3.1 候选与发布分离

- `ClinicalFactCandidate`：被断言对象、极性、原始/规范值、单位、时间建议、定位引用、候选来源语义、模型不确定性。
- `ClinicalEventCandidate`：事件类型、发生时间范围、记录时间、事实/定位引用。
- `MedicationExposureCandidate`：原始药名、类别、适应证、剂量/单位/频次/途径、起止范围、持续状态、事实/定位引用。
- 发布合同新增 Gate id、权威元组、稳定身份、来源强度和 revision；不携带可用于临床裁决的模型置信度。

### 3.2 日期与时态

使用 `PartialDateRange {source_text, precision, lower_bound, upper_bound}`：

- 年：当年 1 月 1 日至 12 月 31 日；
- 年月：当月首日至末日；
- 日：上下界相同；
- 未知：上下界为空，不能借用筛选日、上传日或操作日。

事件发生起止、记录时间、上传时间和节点锚点是独立字段。持续状态为 `持续 / 已结束 / 间歇 / 单次 / 未知`；“既往”不等于“已结束”。Phase 5 只发布病程/暴露可判定区间，不判断洗脱是否满足。

### 3.3 极性、沉默与来源强度

否定事实必须同时满足：明确被断言对象、明确否定语句、定位原文哈希一致。未提及、空白、邻近句否定、缺页或未勾选只能生成期望缺口。

来源强度由文档类型、来源方和定位元数据确定性派生：`同期客观结果 / 既往原始资料 / 当前研究病历直接记录 / 筛选病历转述 / 无法确认来源`。筛选病历转述的阳性长期史可发布为较弱事实并产生溯源提醒；后续原始资料并列增加覆盖，不删除转述。

### 3.4 重复与冲突

稳定重复键包含审核节点、处理修订、事实类型、极性、规范值/单位、日期范围和持续状态，不包含模型置信度或 locator id。键相同则合并全部 locator；语义对象相同但值、极性、日期或持续状态不兼容时建立未解决冲突组。冲突只有在来源校对或有理由的人工事实修订生成新 revision 后才能变化，不能由 Agent 选择赢家。

## 4. 运行图与门禁

### 4.1 FactNormalizationRun

复用现有持久 Job、步骤、检查点、租约、重试和幂等设施，不引入新编排框架。幂等键包括完整处理修订、PromptVersion、ModelConfig、文档切片哈希和合同版本。

默认每个逻辑文档一个调用；超长文档按连续页组切片并保留文档级合并。每个调用显式声明页清单，覆盖门禁要求所有页已处理或有逐页未解决原因。整页遗漏、空输出、跨节点定位、虚构定位或活动指针变化均失败，不生成空 Profile。

### 4.2 门禁顺序

1. 合同与枚举；
2. 权威元组和活动完整处理修订；
3. 页覆盖与引用闭包；
4. locator、有效文本及原文哈希；
5. 极性与断言对象；
6. 值、单位、日期边界、记录时间与来源强度；
7. 文档内重复与冲突；
8. 跨文档合并与冲突；
9. 事务发布和发布后指针复核。

关键 OCR 风险只拒绝受影响候选并记录原因；其他候选仍可发布。任何失败不覆盖上一活动 Profile。

## 5. 下游投影

### 5.1 FactRuleLink

只基于已发布 `fact_type / RuleComponent / EvidenceRequirement` 的明确身份和版本化映射建立双向索引。禁止自由文本模糊相似度，索引可完全重建且不写回方案规则。

### 5.2 EvidenceExpectation

从当前审核节点模板确定性投影 `已观察 / 较弱证据 / 已引用未提供 / 未观察到 / 尚未到期`，并分别保留“病历描述不完整、源文件未提供、检查未执行、专业判断待补、来源需追溯、OCR 风险、未来节点复核”等原因。一个较弱事实可以同时覆盖当前描述并产生溯源提醒，但不能再被重复标成完全无证据。

### 5.3 Patient Profile

后端生成不可变 Profile revision 和首屏突出集合。首屏仅纳入：未解决冲突、当前到期资料缺口、较弱来源阳性长期史、原报告异常/临界、基于同一检查参考范围的趋势变化、受 OCR/解析风险影响的候选。单纯存在 FactRuleLink 不自动进入首屏。

Profile 保留 13 条主题泳道、事件时间与记录时间、部分日期范围、阶段标签、来源强度、冲突并列和证据深链。运行时使用真实 HTTP API 与严格解码；fixture 仅用于隔离前端测试。本阶段不显示入排主结论、行动数或通过/不通过标签。

## 6. 增量、人工修订与历史

- OCR 校对或增量上传先按 locator/文档/事实反向索引确定影响范围；无法证明局部范围时保守重算整个审核节点。
- 新结果生成新事实和 Profile revision，旧 revision 可按原权威元组回放。
- 人工事实修订记录旧值、新值、理由、来源定位、操作者、时间和影响范围；不改原 OCR、候选或旧发布事实。
- 后续审核节点可读取既往事实作为历时输入，但不得重写早期节点的活动 Profile。

## 7. 兼容、回滚与验收所有权

- 新 repository/API 只读取 v2 写表；旧占位表不迁移、不重定向外键。
- 数据迁移前使用现有数据库备份机制；回滚为停止 Phase 5 新写入口并保留 Phase 4 活动证据，不删除已发布 revision。
- 实现者不得自行关闭验收。确定性测试、数据库状态、真实模型运行、真实浏览器和代表病例逐事件核对分别留证。
- 会商与测试角色分离；测试阶段按用户届时指定路线先做连通性，再使用真实隔离项目从入口操作系统内独立 Agent。
