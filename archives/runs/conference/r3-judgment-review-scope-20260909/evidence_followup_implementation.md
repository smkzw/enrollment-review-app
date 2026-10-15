I'll re-read the changed contracts, projection, targeted handwriting path, and tests against the unknown-versus-absent rule, without treating the earlier notes as already proven.The new gap type and handwriting scope exist; next I’ll check whether unverified reads can still collapse into a missing-judgment gap, and whether the two-round job actually keeps that distinction.# Conference Output: r3-judgment-review-scope-20260909 - evidence_single_object

## Output

同会话只读复核。未写文件、未开浏览器、未调 API、未读库/env/病例/其他评测产物。不把测试计数当验收，不声称临床通过。正向研究者来源路径仍视为未完成。

### 总判

未知 vs 确无：类型和界面标签已拆开，**不再自动写成 `professional_judgment`**。  
仍缺：适用双读完成后的**可报告确无判断**；自动填充文案仍像“没有研究者判断”；pending 手写仍不绑条款。  
手写辅助链：布尔范围、两轮、不采信、空归属≠一致，主体成立。幂等键、混合页、失败语义和次轮摘录仍有边角。

---

### 1. 未知不得标成缺失判断 — 类型已换，文案与确无路径未完成

**已证实**

- `_expectation_gap_signals`（`app/services/fact_normalization_executor.py:237-253`）对 `investigator_assessment` 模板不再填 `PROFESSIONAL_JUDGMENT`，改为 `OBSERVATION_UNVERIFIED`。规范化作业仍完成，不因缺判断停跑。
- 投影（`app/projections/evidence_expectations.py:256-283, 301-304`）：有未核实信号时，弱检验事实保留为 `OBSERVED_WEAK` + `observation_unverified`，不升格为 `ABSENT` + 研究者判断。测试 `test_lab_result_does_not_replace_required_written_judgment` 覆盖此点。
- 评估（`app/domain/gates/assessment.py:285-292`）：仅 `GapType.PROFESSIONAL_JUDGMENT` 才出组件结论“需专业判断”；未核实走 `INDETERMINATE`。行动（`app/domain/policies.py:68-72`）指向 CRA，“核实前不要求补写研究者判断”。
- 界面：`GAP_TYPE_LABELS` / `gapTypeLabel` 为「资料尚待核实」；Profile DTO 与 `mapExpectation` 在该 gap 上覆盖状态词，避免 `absent`→「未观察到」。API 测试 `test_unverified_observation_is_not_presented_as_missing_judgment` 只断言标签。

**仍有问题**

1. **自动填充仍无双读/范围前提**（同文件 `224-253`）。到期且尚无其它具体缺口的书面判断模板一律 `OBSERVATION_UNVERIFIED`。漏页、一读失败、范围不一致与“双读完整且确无批注”无法区分。对“不得把未核实写成缺失”是偏保守；对 §16「完整适用双读后可报 professional_judgment、且不阻断」则**没有生产者**。executor 不再发出 `PROFESSIONAL_JUDGMENT`；投影只在调用方显式供给时接受（`test_absent_accepts_explicit_professional_judgment_gap`）。
2. **detail 仍是旧句**（`247-249`）：「当前尚无已核实的研究者书面判断，暂无法判定」。机器类型是未核实，人读像缺失判断。测试未锁 `gap_detail`。
3. **pending 手写仍进不了信号**。`pending_retention_items` 仍无 `gap_type`；`EvidenceNormalizerUnresolvedItem` 仍禁止 `OBSERVATION_UNVERIFIED`（`app/domain/contracts/evidence_normalizer.py:431-443`）。`gap_type is None` 继续 `continue`（`150-151`）。未核实靠「整模板自动填」，不是「该页该对象待核对」。
4. **完好覆盖抢在未核实之前**（`284-295`）：`complete_facts and not ocr_risk` 直接 `OBSERVED`，不看 `unverified`。当前 `_observations` 仍剔除文件类别 `investigator_assessment`（`evidence_expectation_projection_service.py:132-134`），完好书面判断覆盖仍不可达。若以后补上正向路径而不改顺序，未核实会被吞掉。

**最小改动**

- 改 detail：未核实写「现有资料尚未核实是否包含本条要求的记录」，不要写「未见研究者书面判断」。
- 确无判断：仅在适用页双主读成功、范围一致、无该对象待核对手写/事实之后，才发 `PROFESSIONAL_JUDGMENT`；不要把自动未核实拿掉后变回一律缺失。
- 允许 `page_observation_unverified` 升为 `OBSERVATION_UNVERIFIED` **仅当**已有显式 `requirement_id`；未绑条款保持未核实，且阻断该模板的 professional_judgment。
- 投影：`unverified` 优先于 `complete_facts → OBSERVED`（与 OCR 并列）。

**反例**

- 双读成功、适用页无手写、无待核对：今日仍是 `observation_unverified` + 旧 detail，不是可报告确无。
- 一页失败、其它页无判断：今日也是未核实（方向对），但 detail 仍像确无。
- 一侧 “NCS/白细胞”、一侧空：pending 不绑条款，所有书面判断模板被整批标未核实。

---

### 2. 手写两轮 — 主路径成立；混合页、幂等、次轮摘录未钉死

**已证实**

- 独立模块 `app/domain/targeted_handwriting_review.py`：空对空不启动、也不当缺失（`21-24` 测试）；单侧缺、无 `target_text`、数量不一致 → 需复核且非一致；页身份走 `validate_pair`。
- 一致条件：两侧非空手写、每条已知对象、规范化多重集相等。未知归属不是一致（`23-31`）。
- 入队（`targeted_page_review_jobs.py:64-71, 88-89`）：数值冲突与手写布尔可并列；`TARGETED_REVIEW_VERSION=v2`；幂等仍 `r3_targeted_page_review:{reconciliation_id}`。
- 执行器：次轮看 `pending_targets` 或 `handwriting_pending`；读失败跳过次轮；一致亦不采信（`candidate_auto_accept` 恒 False）。手写-only 时 `facts.maxItems=0`（harness `553-554`，format_repair `135-140`）。提示 v3；普通 `PAGE_REVIEW_PROMPT_VERSION` 仍 `page-review-r3/v12`。
- 持久测试覆盖手写 CS/NCS 分歧的两轮、失败、租约恢复、不改原 coverage。

**边角 / 缺口**

1. **幂等键不含 v2**。已有 v1 同对账任务会被原样取回，执行器以 `TARGETED_REVIEW_CONTRACT_CHANGED` 失败。重启/旧任务是阻塞，不是静默回退。
2. **手写是整页布尔，不是对象级目标**。一页一条无归属便签会拖住该页全部手写复核。符合「不强配检验」，但次轮把 round1 **全部**手写摘录送出（`executor.py:65-66`），含本已多重集一致的条目。
3. **混合数值+手写**无作业测试。`focus.targets` 非空时仍允许 facts。次轮若只剩手写 pending，会变成 handwriting-only（`69`），这点对。
4. **`compare:2` 在 skip 时仍是 round_number=1 快照** + `round_skipped`。预存问题；手写失败路径靠短评 `not failures and compare_handwriting_reads`，避免未定义 `records`。
5. **一致比较不含 excerpt/raw_text**，只含 kind + `normalized_text` + context。同对象两处 “NCS” 在两侧条数相同时会当一致。页级源身份有，观察级位置没有。
6. 原读已双源接受的手写：`handwriting_needs_review` 为假，不入辅助链，也**不会**变成书面判断覆盖（正向路径未做）。正确，但条款层仍靠自动未核实。

**最小改动**

- 幂等键加 job version，或取回后若 version 不符则 `NotReady`，不要开跑再炸。
- 次轮摘录只送 round1 未达成一致的手写多重集差，不要整页倾倒。
- 补测试：混合页；无对象仍两轮且不采信；v1 任务碰撞。

**反例**

- 两侧各一条 “NCS/白细胞”，但摘录一在表内一在页边：今日 candidate agreement。
- 同页数值已一致、一条无对象手写：整页手写复核，次轮可能看到无关摘录。

---

### 3. 保真模块 — 已计新增；仍离线；旧洞还在

**已证实**（`app/llm/page_review_repair_preservation.py`）

- 仍声明离线、不作采信。
- `additional_or_changed_observations` 独立计数；改内容时 missing 与 additional 均为 1；纯新增 additional=1、missing=0。
- 非法条 uncheckable；外层坏 JSON 不称已验证。
- 比较仍用 `review_focus=None` 的单条包装，不热改 harness。

**仍有**

- 版本号仍 `page-repair-preservation/v1`，结果形状已变。
- `facts`/`handwriting` 非 list：uncheckable+=1，missing/additional 不增，整场可丢。
- 非法条消失不进 missing。
- 不比 `clause_signals`。
- `protected` 仍是「旧答可独立解析条数」，不是「新答保住条数」。接线若只看 `protected` 会假过。

**最小改动：** 保持离线直到单独闸。若接：用 missing/additional，`protected` 不当通过条件；bump preservation 版本；不改普通纠正预算。

---

### 4. UI 数据

**已证实**

- 前后端口径都有 `observation_unverified` 计数位（`GapCountsWire`、`mapGapCounts`、rollup `gap_counts`）。
- `professional_judgment_count` 仍只数组件结论，不把未核实算进「待研究者判断」。
- 未核实期望的展示词覆盖为「资料尚待核实」。

**未钉死**

- Profile 仍下发 `gap_detail`。自动填充旧句可出现在详情，测试没查。
- `derive_expectation_blocking_level`（`policies.py:254-264`）把未核实与记录缺失一样标 `BLOCKING`，进 `current_gap_count`。不是「待研究者判断」，但仍像当前硬缺口。是否要降为 attention，属产品选择。
- fixture/`labels.test.ts` 只确认枚举键存在，不证明运行时 rollup 真有该计数。

---

### 按严重度

| 级 | 位置 | 机制 | 类别 | 最小建议 |
|---|---|---|---|---|
| **P0** | `fact_normalization_executor.py:247-249` | 未核实 detail 仍写「尚无研究者书面判断」 | 已证实 | 改文案；测试锁 detail |
| **P1** | 同函数 `237-253` | 无双读闭合就整模板未核实；确无 PJ 无生产者 | 已证实 | 保留未核实默认；仅双读完整后才 PJ |
| **P1** | `evidence_expectations.py:284-295` | 将来完好覆盖会吞未核实 | 已证实（潜伏） | unverified 与 OCR 同级优先 |
| **P1** | UnresolvedItem + pending_retention | 待核对手写不能成为绑定信号 | 已证实 | 仅显式 requirement 才绑；禁止猜绑 |
| **P1** | `targeted_page_review_jobs.py:89` vs `VERSION=v2` | 旧 v1 幂等碰撞后执行失败 | 已证实 | 键含版本或取回即 NotReady |
| **P2** | `executor.py:65-66` | 次轮倾倒全部手写摘录 | 已证实 | 只送多重集差 |
| **P2** | `_index` 不含 excerpt | 同对象同文不同位置可假一致 | 已证实 | 至少纳入 excerpt 或位置 |
| **P2** | preservation 仍 v1、未接线 | 非 list/非法条/条款信号 | 已证实 | 离线；接线时独立版本 |
| **P2** | `policies.py:264` | 未核实=BLOCKING | 设计 | 与 CRA 核对行动对齐，考虑 attention |
| **P3** | 测试缺口 | 无混合页、无 detail、无 v1 碰撞 | 已证实 | 补最小测 |

正向 `investigator_assessment` 覆盖：**未实现**（`_observations` 仍排除文件类别，匹配仍不按 `fact_type`）。弱检验 + 未核实保留实验室事实：投影在**显式**同时给 PJ+unverified 时测过；线上 executor 只给 unverified，行为应对应为 `OBSERVED_WEAK`。

---

### 对本次改动的异议

1. 把自动 PJ 换成自动未核实，修了误标，**没有**实现「完整适用双读后的可报告确无」。不要把当前状态当成 §16 完成。
2. 未核实 detail 仍用判断缺失句，标签层的拆分会被详情句抵消。
3. 整页手写布尔 + 次轮全摘录，比「已知对象的多重集」粗。
4. 不要为了继续流程去绑所有 pending 手写到全部书面判断模板。

---

### 给 Codex 的决策点

1. 双读完整且适用页无该对象手写/事实：保持未核实，还是发 `professional_judgment`（不暂停作业）？今日是前者。
2. 未核实阻断级：维持 BLOCKING，还是 ATTENTION（与「先核对应、不补写判断」一致）？
3. v1 辅助任务：新幂等维度，还是碰撞即 NotReady？

**临时安全路径：** 保持自动未核实（不要恢复自动 PJ）；先改 detail；辅助手写继续不采信；保真继续离线；正向覆盖未做就不要当已观察。

未跑全量测试。证据来自指定源码与相邻测试阅读。
