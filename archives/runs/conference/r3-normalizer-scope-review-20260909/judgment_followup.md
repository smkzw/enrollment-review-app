# 会议输出：r3-normalizer-scope-review-20260909 - evidence_single_object

## 输出

（同会话聚焦复审：书面判断证据修正。仅静态源码核对，新增阅读集已读：`facts.py`、`evidence_expectations_v2.py`、`evidence_expectation_projection_service.py`、`test_evidence_expectations.py`。）

### 1. 源码核对与先前结论更正（已确认）

**Owner 的修正属实，我此前的"investigator written judgment gaps — 不损失"结论对混合 required_source_types 是错误的，予以更正。** 我首轮引用了单例条件 `== {"investigator_assessment"}`（旧 `evidence_expectations.py` 特判），但没有推演其混合集含义：旧 `_coverage_verdict` 用任意交集+家族展开（且旧 `病历资料` 家族含 `investigator_assessment`），`required_source_types=(lab_report, investigator_assessment)` + 真实检验事实 → complete → `OBSERVED`，判断缺口被检验事实吞掉。这正是 owner 扩展测试暴露的假阳性。

**修复已核对，两处均正确**：
- `app/projections/evidence_expectations.py:143-145`：模板要求 `investigator_assessment` 时，`source_type_matches` 必须来自 observed 集合的显式成员，不再走家族展开；`_SOURCE_TYPE_FAMILIES["病历资料"]`（85-97 行）已不含 `investigator_assessment`。
- 缺席分支（260-278 行）：判断特判由单集相等改为 `"investigator_assessment" in required_source_types`，混合集下无判断级 complete 事实 + 显式 `PROFESSIONAL_JUDGMENT` 信号 → `ABSENT/PROFESSIONAL_JUDGMENT`；带 parse_risk 时落 `OBSERVED_WEAK`/OCR 且事实仍计入 `coverage_fact_ids`。
- 扩展测试 `test_lab_result_does_not_replace_required_written_judgment`（test 文件 906-936 行）参数化覆盖 单集/混合 × 检验报告/病历资料 × parse_risk，断言与 owner 描述一致。32 通过为 owner 报告，我未运行（范围约束），静态逻辑自洽。

**遗留结构性缺口（owner 判断正确）**：`CoverageObservation.source_types` 仅由定位所属文档的 `document_type` 派生（`evidence_expectation_projection_service.py:120-131`，合同 docstring 115 行同义）。因此修复后 `"investigator_assessment" in observed_source_types` 只有当整份文档元数据字面为该类型才可能为真——检验报告批注、病历段落里的**真实**书面判断永远无法走通正向路径。文档类别既不能证明也不能证伪判断；正向路径必须建在已采信观察级证据上。

### 2. 最小类型化正向路径设计（复用现有合同，不新建大架构）

**核心**：给事实候选/发布事实增加一个可选类型化子合同，语义判定归有界主读/规范化器，结构核对归确定性代码，投影只消费通过门禁的发布事实。

**(a) 类型字段**（`ClinicalFactCandidateV2` 与 `ClinicalFactV2` 各加一个可选字段，发布事实必须保留——当前 `ClinicalFactV2` 已丢弃候选的 `source_observation_refs`，370-397 行确认，判断依据不过发布会投影就看不到）：

```
investigator_judgment: InvestigatorJudgmentBasis | None = None
  judgment_excerpt: str                      # 判断逐字原文（如"ALT升高无临床意义"、手写"NCS"）
  judgment_kind: Literal["clinically_significant",
                         "not_clinically_significant",
                         "other_written_judgment"]
  subject_target_text: str | None            # 被判断对象；优先=所引已采信观察 context.target_text
  judgment_recorded_date: PartialDateRange | None   # 缺省不造
  author_text: str | None                    # 署名/缩写原文；不可见必须为 None，不得虚构
```

复用现有机制：`source_observation_refs`（已采信观察绑定）、`AssertionBasis`（逐字摘录+哈希+定位闭包，`facts.py:188-198`）、`date_range/record_time`、`supported_requirement_ids`、`candidate_source_semantics`（转述降级照旧走 weak 规则）。**不要**把 basis 纳入 `stable_identity`（保持同内容合并语义不变，多定位合并模式不受影响）。

**(b) 确定性门禁**（在 `_validate_normalizer_semantics` 内紧邻 `validate_accepted_candidate_sources` 处实施，同源数据在手，失败即闭合，不进存储）：
1. `source_observation_refs` 非空且 ⊆ 已采信引用（现有校验已覆盖，判断候选复用）；
2. `judgment_excerpt` 逐字出现在所引已采信观察的 `region.excerpt`/`raw_text` 内（沿用 `page_review_sources.py:85-98` 的摘录锚定模式）；手写 CS/NCS 用已采信 `HandwritingObservation(kind=cs_ncs_judgment)`（读道已分类，合同现成），excerpt=其 `raw_text`；
3. `author_text` 必须是所引观察摘录的逐字子串，否则必须为 None（防虚构，可验证）；
4. `subject_target_text` 若来自观察 context 必须逐字相等；否则必须出现在同页已采信摘录内——**同页/同对账绑定即防跨节点借用**的确定性代理（不引入不存在的节点锚点推断，判断日期随 basis 保留供人看陈旧性）；
5. **箭头≠判断**：所引观察 `raw_value` 仅由数值+异常标记构成（复用 `app/domain/page_normalization.source_arrow_marks`）且 `judgment_excerpt` 未增加超出值/标记的书面表述 → 拒绝；提示词侧同步一句"仅有异常标记、无书面意义表述的不是判断"。无散文正则。
投影侧再便宜复核一次（projection service 有 session，可取 PageReviewRepository 做包含性复验），实现"终局投影不单独依赖模型措辞、也不依赖文档类型"。

**(c) 投影接线（一行级）**：`_observations` 组装时，`fact.investigator_judgment is not None`（且过 (b)）→ `source_types.add("investigator_assessment")`。文档类型永不添加它（假阳性保持关闭），模型声明单独也永不添加它（须过结构门禁）。`_coverage_verdict` 现行显式成员规则不动；混合集下判断事实 complete → `OBSERVED`，转述判断照旧 weak。一个注意点（不改，仅登记）：模板若同时 `requires_contemporaneous_objective_source`，病历书面判断会落 `OBSERVED_WEAK`——属模板编写语义，非本改动职责。

**(d) 阶段/上下文与缺失路径**：`current_review_stage/workflow_stage_id` 由冻结输入系统注入（非模型），权威元组绑定节点；缺判断时现有 `_expectation_gap_signals` 默认信号 → `ABSENT/PROFESSIONAL_JUDGMENT`，可报告的无法判定、不阻断（§16 不变）。类型化路径不新增任何等待用户状态。

**(e) 提示词**：并入既定 v24 bump，一段话：判断仅可从已采信观察经类型字段记录；标记值非判断；author 仅逐字可见才填；不虚构对象/日期。

### 3. 最小测试计划

1. 正向（新）：检验报告文档内判断批注 → 过门禁 → observed 含 `investigator_assessment` → 单集与混合模板均 `OBSERVED`；与现有反假阳性测试成对。
2. 门禁单测：excerpt 非逐字→拒；author 不在摘录→拒或强制 None；纯箭头值→拒；pending（未采信）引用→拒；手写 `cs_ncs_judgment`→过；判断与对象跨页且 target 不匹配→拒。
3. 持久/回放：basis 过候选→发布→投影存活；`stable_identity` 不含 basis、合并行为不变；重放一致。
4. 回归：现 32 项全部保持（含 病历资料 假阳性用例）；`_expectation_gap_signals` 对已有判断覆盖的模板不改变信号集合。

### 4. 其他

- **计时记录（不构成行动建议）**：dense v24 回放 677.7s vs 621.1s（15 facts 1 event）、sparse 428.9→190.7s，与"dense 页成本由已采信观察侧主导、pending 计数化不降 dense"的结构预期一致；书面判断改动只加一个类型字段、不新增调用，与此成本结构正交。按指示不建议重跑全样、不建议换模型/强度。
- **未验证/归属**：测试执行数（32）为 owner 报告；发布路径与存储字段迁移由 owner 实现并验证；我未读 DB/运行代码（范围约束）。
- 对现有结论的唯一更正即第 1 节；第 2 节为最小方案建议，最终裁量在 Codex/owner。
