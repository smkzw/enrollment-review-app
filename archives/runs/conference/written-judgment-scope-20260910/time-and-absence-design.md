# Conference Output: written-judgment-scope-20260910 - evidence_single_object

## Output

D2/R1 实现前调查完成（只读，未改代码/未联网/未调用模型）。以下先给出两个日期语义的审计结论（这是任何比较方案的前提），再区分“现有 schema 已能证明”与“需要新的来源绑定合同”，最后给出三项最小设计与测试/上线序列。

---

### 一、语义审计结论（比较方案的地基）

**`ObservationContext.time_text`（page_review.py:61-67）**：合同自述为 "Source-written association, not an inferred clinical determination"——它是读道模型从页面上**逐字摘出的、与批注目标相关联的打印时间文字**，经 `observation_context_key` 用 `normalize_scalar_v4` 归一化后进入手写归一化键（page_normalization.py:147-159），因此双读采信已要求两道对此文本一致。规范化器提示词明示（evidence_normalizer.py:580-581）：“context.time_text 仅是页读关联，不自动证明事件时间”。关键区分：**它不是签署日期**——签署/缩写/日期类手写是独立的 `HandwritingKind.SIGNATURE_INITIALS_DATE`，被排除在 CS/NCS 证明之外；CS/NCS 批注的 time_text 是“批注所锚定的那次测量的打印时间文字”。它可选、可为非日期文本、每批注一条。

**`ClinicalFactV2.date_range`（facts.py:122-171）**：`PartialDateRange` 是**事实所指事件/测量的发生日期**（精度+确定上下界，“绝不借用筛选日、上传日或操作日”；`source_text` 仅展示、不入身份）；`record_time` 是独立的记录时间。对一条 investigator_assessment 事实（判断本身），合同**没有任何条款**规定其 date_range 必须等于被判断测量的日期——提示词反而要求严格区分事件时间与记录时间。

**审计结论**：`fact.date_range`、`annotation.context.time_text`、签署日期是**三个不同断言**。任何“判断事实日期 vs 批注日期”的直接比较（含签署日期比较）在语义上不成立，正是任务书禁止的方向。正确的绑定物是**来源书写的关联本身**（批注的双读一致 context 五元组），以结构化副本的形式被冻结并被门禁全等校验——而非日期对日期。

---

### 二、现有 schema 能证明 / 不能证明

**已能证明（无需新合同）**：
1. 一条批注是 CS/NCS、且两道独立模型（main-A/main-B，不同模型身份）在其完整 context（target_text/time_text/location_text/polarity）上逐字一致（归一化键全等 + 物化器校验，page_review_evidence_sources.py:147-155, 246-279）。
2. 判断事实的定位**就是**某条已采信批注的读道定位（locator 身份内嵌 source_set/target/page_review/excerpt 哈希；`validate_accepted_candidate_sources` 进一步强制候选定位与所引观察 page_review_id+kind+摘录全等，page_review_sources.py:53-71）。
3. 候选引用了哪条已采信观察（`source_observation_refs`，facts.py:242）——**但只在候选层**。
4. 定位所属资料的冻结类型/来源方（Phase 4 元数据）与重建核验失败闭合（reconciliation_id 复现，page_review_visual_sources.py:84-86）。
5. 对账冲突的存在（`handwriting_conflicts`）。

**不能证明（缺口即所有权/粒度缺失）**：
- **G-R1**：`source_observation_refs` 在发布时被丢弃——`ClinicalFactV2`（facts.py:377-397）与发布服务均无此字段。于是期望期重校验（written_judgment_locator_ids）只剩 asserted_object ↔ target_text 的名字等值，无法核对“这条判断事实出自**哪一次**同名测量”。
- **G-D2**：读道 payload（facts/clause_signals/handwriting，page_review.py:217-235）**没有肯定性否定断言**——“本页无 CS/NCS 判断”无法表达；空手写列表不是断言（用户规则：未读≠无）。clause_signals 的 `signal=NONE` 是现成的双读否定先例（对账接受模式：两道同值即接受，page_reconciliation.py:126-134），但语义属于入排证据，不能挪用。
- **G-P3**：打印的对应节点临床分析无分类通道——`PageFactObservation` 无“此句为研究者分析”的判定字段；文件类别（`derive_source_strength_from_metadata` 无 investigator_assessment 分支 → UNVERIFIABLE）按设计永不证明。

---

### 三、最小实现设计

#### (1) R1：同名列出的跨测量误绑定

**核心修法：把“来源书写关联”作为来源绑定副本持久化到已发布判断事实上，门禁做五元组结构全等。**
- 新增 `ClinicalFactV2.judgment_source_association: HandwritingAssociationCopy | None`（additive，None=旧数据/非判断事实）。副本内容 = 发布时从被引用的已采信批注源**逐字冻结**的 `{handwriting_source_id, target_text, time_text, location_text, polarity}`（与 `VisualHandwritingSource.readings` 双读一致 context 全等，由发布路径从候选的 `source_observation_refs` 解析取得——引用链已存在且已被校验，只差不丢弃）。
- `written_judgment_locator_ids` 增强：除现有条件外，要求事实携带的副本与重建批注的双读一致 context **五元组全等**（同用 canonical 序列化比较，与 D1 修复的 `_signal_key` 同风格）。名字等值降级为必要非充分条件。
- **旧行处理**：无副本的旧判断事实 → 不再计入 certified 来源类型（回到未核实），**不自动迁移证明**；下一次修订重投影按既有 provenance/pad 机制自然保守。
- 模板粒度：`EvidenceRequirement/EvidenceExpectationTemplate` 增 `judgment_binding: "requirement" | "occurrence"`（默认 requirement，向后兼容；进 `projection_sha256` 稳定身份）。`occurrence` 模式要求覆盖判断事实的关联副本时间/定位能对应到该要求下已发布测量事实的同一来源观察（通过测量事实自身的 locator/context 对应，**不做日期对日期比较**）；无 time_text 的副本在 occurrence 模式下判未核实（失败方向保守）。requirement 模式保持现状语义但校验副本全等，并把副本 time_text 透出到期望输出供人工核对。
- **明确不做**：date_range vs time_text vs 签署日期比较；不自动推断任何缺失日期（用户未授权伪造日期）。

#### (2) D2：充分来源复核后的“缺研究者书面判断”

**核心修法：双读肯定性否定断言 + 确定性生产者，不放开规范化器枚举。**
- `PageReviewPayload` 增 `judgment_absence: list<JudgmentAbsenceAssertion>`（page-review 合同升 v7；断言 = 页级全局“本页不存在任何 CS/NCS 判断手写”，携带读道身份）。自洽门禁：若该读道同页 handwriting 含 CS_NCS 观察则 payload 拒绝——断言必须与自身观察矛盾不可能。
- 对账（reconciliation v5）沿用 clause-signal 先例：两道都断言且一致 → `accepted_judgment_absence`；仅一道 → 不成立（不视为缺失证据）；与任一 CS/NCS 观察冲突 → 记冲突（走未解决/OCR 风险，而非缺失）。
- 确定性生产者（放在 `fact_expectation_gaps` 层，读取对账后的覆盖记录，**非模型**）：对要求 R——令 P = R 的已发布测量事实的已采信视觉定位所在页集合（覆盖页）。当且仅当：P 非空、P 中每页 disposition=ACCEPTED 且双读 absence 均被接受、且不存在任何绑定 R 对象的已采信/冲突 CS/NCS → 产出 `CoverageGapSignal(PROFESSIONAL_JUDGMENT, detail 列出页集合与两读道 review id, applies_to_template_id=R 模板)`，非 fallback。任何条件不满足 → 维持现有 `observation_unverified` 兜底。P 为空（连测量都没有）时**不触发**（那是 required_procedure_not_done/record_incomplete 的领域）。
- 用户规则对齐：这是**可报告的未决判据**（缺口行 + 责任方/动作），工作流继续，不停下问用户；不从空手写/单页/文件类别推断。D1 修复的 provenance 机制天然冻结该具体信号，后续修订可精确重放。

#### (3) 打印的对应节点临床分析

**核心修法：读道级分析分类 + 双读一致 + 文档方元数据三重来源证明，类别永不单独生效。**
- `PageFactObservation` 增 `assessment_role: Literal["investigator_analysis"] | None`（exclude_if None，不入归一化键——旧 payload 解码为 None，键稳定）。双读对同一观察（同键）都分类 investigator_analysis 才在物化源上冻结该分类；不一致 → 不算分析（保守，可选记冲突）。
- 新投影 `printed_analysis_locator_ids(source_set, asserted_object)`：已采信**事实**源中两读道 observation 均带 investigator_analysis 且 context.target_text == asserted_object（结构全等风格同上）。
- `_observations` 第二证明路径：事实 fact_type=investigator_assessment 且 requirement 绑定、定位属上述集合、**且**该定位文档的冻结元数据满足研究者方 + 病历family（即 `derive_source_strength_from_metadata` 会给 CURRENT_STUDY_CHART 的组合）→ 计入 investigator_assessment 来源类型。“对应审核节点”由活动权威下的本研究病历文档界定；类别（document_type=investigator_assessment 的文件）路径维持永不证明。

---

### 四、测试与上线序列

**上线序列（每步独立合成测试门控，全程追加式）**：
1. **R1 副本持久化 + 门禁**（不动 page-review 合同；facts 合同 additive）。测试：同页两条同名测量（不同 context）+ 一条锚定其一的批注——引用错误侧的判断事实不再 certified（期望 observed_weak/未核实）；副本全等 → observed；旧行无副本 → 未核实且不自动升级；occurrence 模式无 time_text → 未核实。
2. **打印分析通道**（page-review v7 前置或并行；物化器/投影/`_observations`）。测试：病历family 文档 + 双读一致分类 + 目标绑定 → 计入；同摘录在检验报告文档 → 不计入；仅类别 → 不计入；两道分类不一致 → 不计入。
3. **D2 双读缺失断言**（payload v7 + reconciliation v5 + 生产者）。测试：全覆盖页双读 absence → ABSENT/PROFESSIONAL_JUDGMENT（detail 含页集）；单道 → 不成立；含 failed_pending_reread 页 → 不成立；P 空 → 不触发（维持兜底）；同页存在 CS/NCS 观察与 absence 断言 → payload 自洽拒绝/冲突路径。
4. 收尾：期望输出透出副本 time_text / 页集证据；回归三套现有判断类测试。

### 五、未决解释性问题（需用户/Codex 裁决，不阻塞 1-3 步编码设计）

- **缺失断言的作用域**：页级全局 v1（断言强、误建立罕见、实现最小）vs 对象级（更细但要求读道理解对象）——我建议 v1 页级全局，对象级留待证据。
- **time_text 缺失的证明力**：requirement 模式下无 time_text 的副本是否允许 complete（当前设计允许，靠定位+对象绑定），还是一律 weak——涉及真实批注多无关联时间的普遍性，需用户确认风险偏好。
- **判断完整性按测量计**（“每次结果均需判断”类方案要求）：本设计明确不建模 occurrence 完备性清点，只做绑定正确性；是否需要逐测量清点是独立产品决策。
- **打印分析的“分析者身份”**：双读分类 + 文档方元数据的组合是否足以对应“研究者分析”，或需要页内署名/角色文字的额外证据。

### 六、边界

本报告为工程实现设计（源码锚定：page_review.py:61-67/184-204/217-235、page_normalization.py:147-159、page_review_evidence_sources.py:147-155/246-279、page_review_sources.py:12-71、facts.py:122-171/188-198/242/370-397、evidence.py:138-162、rules.py:279-297、page_reconciliation.py:114-134、fact_normalization_source_adapter.py:599-654、written_judgment_evidence.py、evidence_expectation_projection_service.py:133-156）。未实现、未调用模型、未触真实数据；非临床验收。D1 已按窄义验收，与本轮相互独立。
