# Conference Output: written-judgment-scope-20260910 - evidence_single_object

## Output

只读审阅完成（未改代码、未调用产品模型、未读生产路径）。总体结论：**“研究者书面判断来源覆盖合同”的阳性证明链（双读批注 → 重建核验 → 期望覆盖）本身是诚实且失败闭合的，测试声明属实（我独立复跑三个指定测试文件：57 passed）；但发现一个更高层的确认缺陷（D1：事实修订重投影丢缺口信号，可致状态静默升级或修订整体回滚）、一个“设计了但活管线不可达”的状态（D2：PROFESSIONAL_JUDGMENT 无生产者），并确认了任务书点名的 asserted_object-only 匹配跨时间误用风险（R1）在代码层真实存在。**

---

### 一、三类区分的现状核查（客观证据）

**1. 已核实阳性证明（OBSERVED/complete）— 链路完整，且比文档声称的更严。**
覆盖 `investigator_assessment` 来源类型的唯一路径是 `EvidenceExpectationProjectionService._observations`（`app/services/evidence_expectation_projection_service.py:136-156`）调用 `written_judgment_locator_ids`（`app/projections/written_judgment_evidence.py:14-38`）。逐层核验到的确定性护栏：

- 文件类别永不证明书面判断：`document_type == "investigator_assessment"` 的类别分支被显式跳过（`evidence_expectation_projection_service.py:133-135`），`_coverage_verdict` 对要求 `investigator_assessment` 的模板只接受显式核验过的来源类型（`evidence_expectations.py:145-146`），打印的临床分析/化验单类别只能产生 weak/none 判定。
- 只有 `HandwritingKind.CS_NCS_JUDGMENT` 可作判断证明；NOTE/TABLE_CELL/SIGNATURE/OTHER 均排除（有测试覆盖，含“异常标记不足”的等价物——表格单元格批注不算）。
- 双模型独立性在物化层强制：`_validate_reading_pair` 要求 main-A/main-B 两条读道且 `(provider, model)` 身份不同（`page_review_evidence_sources.py:147-155`）；且双读的归一化键内嵌完整上下文哈希（`page_normalization.py:147-159`）——即**两条主读必须在 target_text、time_text、location_text、polarity 上完全一致才能被采信**，这比 `written_judgment_locator_ids` 里表面上的 target 匹配更强。
- 投影时不信任缓存：`rebuild_visual_sources` 从持久化主读重跑对账并要求 reconciliation_id 逐字复现（`page_review_visual_sources.py:84-86`），locator 与重建投影逐字相等才接受，权威元组/快照/规则版本任一漂移即硬失败（同文件 ：56-72）。
- 严格归一化相等（NFKC/小写/去空白，无同义词映射）意味着“WBC vs 白细胞”这类不一致会失败降级为未核实，方向安全（不会假阳性）。
- 单读/冲突不算证明、同页不外溢到其他对象：均有对应测试且我复核了断言逻辑。

**2. 未核实（OBSERVATION_UNVERIFIED）— 语义正确，且 fallback_only 撤除逻辑正确。**
活管线中 `_expectation_gap_signals`（`fact_normalization_executor.py:135-256`）为无信号的到期判断类模板补 `fallback_only=True` 的 OBSERVATION_UNVERIFIED（其余模板补 RECORD_INCOMPLETE）；`project_expectation` 中 `not signal.fallback_only or not complete_facts`（`evidence_expectations.py:256-260`）保证：已核实的完整判断事实会撤掉默认提示（→OBSERVED），非默认的未核实信号则强制 observed_weak。这与用户规则“未读/未核实不等于缺失、不得停下问用户”一致——E2E 持久化测试（`test_fact_normalization_persistence.py:1387-1429`）证实整链落地为 ABSENT/RECORD_INCOMPLETE 或判断类 ABSENT/OBSERVATION_UNVERIFIED 的“暂无法判定”，工作流不中断。

**3. 完整范围缺失 — 这是本合同当前最大的问题面（见下 D1/D2/R1/S1）。**

---

### 二、确认缺陷（按影响排序）

**D1（最高影响，确认缺陷）：事实修订重投影以 `gap_signals=[]` 调用投影服务，两个方向都出错。**
`app/services/fact_correction_service.py:1309-1316` 的 `_reproject_expectations` 在修订（fact correction）后重投影期望时传入空缺口信号：

- **静默升级方向**：此前因真实 OCR_OR_PARSE_RISK / 非默认 OBSERVATION_UNVERIFIED 信号处于 observed_weak 的模板，只要覆盖事实完整，重投影即变 OBSERVED/complete——风险发现被无声丢弃在新链头（旧 revision 保留，但 `latest_by_template` 已声称完整）。node 范围（`scope_kind == "node"`，template_ids=None）重投影全部模板，必然命中。
- **阻断方向**：被修订对象是某到期模板唯一覆盖事实时，`exclude_fact_ids` 排除后该模板无覆盖、无信号 → `ProjectionInputError`（`evidence_expectations.py:367-370` 拒绝通用回退）→ 被 ：1196-1204 捕获后**整笔修订回滚**。node 范围下只要受试者存在任一未覆盖的到期模板（真实数据几乎必有），修订功能整体不可用。

失败是闭合的（无数据损坏），但它直接违反产品边界“源保留的事实修订 + 受影响范围重跑”，属于当前必须修的工程缺陷。

**D2（合同级缺口，确认）：“双模型确立无书面判断”状态在活管线不可达。**
`EvidenceNormalizerUnresolvedItem` 合同（`app/domain/contracts/evidence_normalizer.py:431-441`）与生成 schema（`app/agents/evidence_normalizer.py:665-700`）的允许缺口类型**均不含 PROFESSIONAL_JUDGMENT 与非默认 OBSERVATION_UNVERIFIED**；拒候选路径只产 OCR_OR_PARSE_RISK；兜底循环只产 fallback 两种。因此 `project_expectation` 的 judgment 专项分支（`evidence_expectations.py:261-285`，含“检验事实不替代书面判断”的 ABSENT/PROFESSIONAL_JUDGMENT）在真实管线中是死分支，仅测试可达。后果：用户规则要求的区分“已检查并确认无判断（→因缺判断无法判定入排）”与“尚未核实”**永远停留在后者**；责任方/待办动作也无法按更精确状态给出。

**R1（点名风险，确认真实存在）：CS/NCS 匹配只对 asserted_object，时间/测量绑定无确定性校验。**
`written_judgment_locator_ids` 只比较 `context.target_text == asserted_object`（`written_judgment_evidence.py:29-32`）。虽然双读采信已要求两道在完整上下文（含 time_text/location_text/polarity）上一致，但**没有任何代码核对批注的 time_text 与事实的 date_range/record_time 的一致性**：同一页同名分析物多次测量（如筛选两日的白细胞）时，规范化器若把判断事实的定位绑到锚定另一次测量的批注，门禁不会发现，覆盖照样判 complete。现有护栏（定位身份绑定 + 严格对象名相等 + 双读上下文一致）大幅收窄但不消除该风险。

**T1（测试缺口）：阳性证明链没有种子库集成测试。**
`test_expectation_document_categories.py` 对 `_observations` 的视觉重建路径全部 monkeypatch（伪造 rebuild_visual_sources 与 locator 仓储），未验证 `EvidenceLocatorRepository.get` 真实返回 `page_review_visual` 溯源、locator 与重建投影在持久层逐字相等这一接线。三个文件 57 通过（我已复跑）证明的是合同语义，不是 DB 接线。

**次要发现**：① `_ABSENT_GAP_PRECEDENCE` 把 OBSERVATION_UNVERIFIED 排在 PROFESSIONAL_JUDGMENT 之前（`evidence_expectations.py:101-110`），若两者并存（当前仅手工信号可造出），“尚未核实”会掩盖“已确认无判断”，语义可议；② `derive_source_strength_from_metadata` 无 `investigator_assessment` 分支 → 该类文档派生 UNVERIFIABLE（`fact_evidence_closure.py:769-777`），即“研究者评估文件”整份上传对判断覆盖完全惰性——这是有意的保守设计，但值得在用户可见文档写明。

**范围缺口（未来项，非缺陷）**：S1 用户规则允许的第二来源“对应审核节点的病历分析（chart analysis）”完全未实现，仅有批注通道；S2 判断完整性按 requirement 级建模，不区分多次测量各自是否被判断；S3 NOTE 类手写的“单独语义适用性评审”无通道（docstring 已声明留待）。

---

### 三、最小可实施方案（不改旧行、全部追加式，按优先级）

- **P0（修 D1）**：`_reproject_expectations` 不再传空信号。首选方案：用持久化的未解决项 + 候选 + 门禁结果重放 `_expectation_gap_signals`（全部 append-only 可重放，与原运行同一冻结输入），再叠加兜底循环。决定性合成测试两条：修订使唯一覆盖事实被取代 → 新 revision 为 ABSENT/未核实类缺口而非回滚；修订前 observed_weak(OCR 风险) 的模板 → 修订后链头仍是 observed_weak（除非事实完整且信号确已消失）。
- **P1（修 R1，最小闭环）**：在书面判断核验处加“矛盾守卫”——仅当两条读道的 time_text 与事实 date_range 都可规范化为可比日期且矛盾时，拒绝计入判断覆盖（降级为未核实）；time_text 缺失时维持现状（避免杀死大多数阳性覆盖），但把批注 time_text 透出到期望/观察输出供人工核对。双向合成测试。
- **P2（修 T1）**：补一条种子库集成测试：持久化双主读 → 对账 → `persist_visual_locators` → 发布 investigator_assessment 事实 → `project()` → 断言 OBSERVED 且 locator 闭包正确；再断言权威漂移时失败闭合。
- **P3（D2/S1）**：需 Codex 决策后再动（见下），不建议本轮实现。

---

### 四、给 Codex 的决策点与有界问题

1. **D1 修复路线**：重放原运行信号（我推荐，确定性同源） vs 沿用上一 revision 的 gap_type 逐模板承接？后者在原信号引用的候选被修订取代时有陈旧风险。
2. **D2**：PROFESSIONAL_JUDGMENT 是“合同预留待双读负断言生产者”（则应文档化，且可考虑收紧死分支），还是现在就扩展规范化器 schema/prompt 允许产出？注意扩展会改变提示词哈希 → 需新 prompt_version_id，属显式版本决策。
3. **R1 矛盾时的处置层级**：覆盖层排除（我推荐，追加式、影响面小） vs 候选发布门禁直接拒绝该事实（更严但会否决可能其余部分有效的事实）？

### 证据与不确定性声明

- 证据（读码+测试）：上述全部 file:line 均经本会话直接读取；57 passed 独立复跑确认。D1 的两个方向由代码路径推导（`_reproject_expectations` → `project_expectation` 分支 + :1196 回滚捕获），未实际构造修订用例执行——这是推断强度最高的部分，但建议 P0 测试先行验证再合入修复。
- 观察 vs 推断 vs 建议已分节标注；医疗层面仅为工程/合同评估，最终临床与用户验收归 Codex。未读生产路径、原始临床数据、家庭配置；未联网。
- 本角色无阻塞问题导致的中止；三个有界问题（决策点 1-3）不阻塞 P0/P1/P2 的建议方向，仅影响实现细节选择。
