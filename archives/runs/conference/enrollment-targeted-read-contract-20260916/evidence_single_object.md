先读指定的会议上下文和主场计划，确认双读遗漏复核入口与提示合同的审阅范围，再独立核对照证据。上下文已锁定：只读审阅入口与提示合同，不放宽采信。接下来对照指定源码核对双读遗漏、身份保留和自动采信边界。源码入口已读到。接着核对 jobs/executor/harness 与提示合同，重点看单侧选择、轮次身份和自动采信是否被放宽。入口选择和合同已经对上。接下来核对照归一化键、对账消费方和任务依赖，确认单侧遗漏会不会被当成一致。核对过任务依赖与渲染身份：第二轮摘录会把单侧读到的数值送回模型，这是当前最大的假一致通道。下面按证据/推断/建议分开给出审阅结论。# Conference Output: enrollment-targeted-read-contract-20260916 - evidence_single_object

## Output

角色：`evidence_single_object`（重要证据审阅）。只读源码审阅，未跑模型、未改源码、未读原始病例、未做临床/监管/视觉终裁。Codex 保留最终接受权。

本轮额外读取（因入口选择、轮次身份、假一致与“是否继续胀提示”无法只靠初始两份文件判定）：`app/domain/targeted_page_review.py`、`app/domain/contracts/page_review_focus.py`、`app/domain/contracts/page_review.py`、`app/domain/contracts/targeted_review_outcome.py`、`app/services/targeted_page_review_jobs.py`、`app/services/targeted_page_review_executor.py`、`app/llm/page_review_harness.py`、`app/llm/page_review_format_repair.py`，以及相邻只读消费方 `targeted_review_candidates.py`、`targeted_page_review_detail.py`、`targeted_page_review_status.py`、`targeted_handwriting_review.py`、`page_review_job_executor.py`、`page_reconciliation.py`、`page_source_association.py`、`page_normalization.py`、`api/v2/page_review.py`、`job_service.py` 幂等、`jobstore.py` 可运行依赖、`evidence/render.py`、`evidence/pdf_native.py` 旋转说明。未读 `artifacts/`、数据库、测试或病例。

---

### Evidence（观察/源码事实）

1. **原双读采信仍要求双源同键。** `reconcile_page_reviews` 只把同时出现在 A/B、带非空 `target_text`、无歧义身份、异常箭头一致的 `normalization_key` 写入 `accepted_fact_keys`。单侧事实进入 `fact_conflicts`，理由是“主读结果未形成双源一致事实”。辅助对账另有原文位置对齐路径，但仍要求两读同值、同箭头、同字段、同上下文键，且摘录在冻结文本中唯一出现。

2. **辅助入口按字段名集合选目标，不按观察身份。** `explicit_conflict_fields` 把冲突定义为：同一规范化字段 + 同一 context 键、两侧都恰好 1 条、且都是数值/日期、值或箭头不同；把遗漏定义为：两侧 **字段名集合** 的对称差，再过滤 `_structured_value`。注释写明单侧观察只是重读候选，不是“不存在”的证明。`45` 条观察压成会议所述 `35` 个目标，与“按唯一字段名而不是按行”一致。

3. **辅助比较不自动采信。** `compare_targeted_reads` 固定 `candidate_auto_accept: False`。空观察、缺 context/`target_text`、同字段多条、键集合不一致，一律 `pending`。`TargetedReviewOutcome` 把该字段锁成 `Literal[False]`，并禁止空结果冒充一致。执行器失败路径同样写死 `candidate_auto_accept: False`。证据 API 的 `TargetedReviewEvidence` 也锁死该字段。

4. **两轮身份被合同钉住，但第二轮会把第一轮摘录（含数值）送回模型。** `PageReviewFocus`：第 1 轮禁止候选摘录；第 2 轮必须绑定上一轮两条不同主读。执行器明确“只保留同轮比较，不跨轮配对”。第 2 轮 `candidate_excerpts` 取的是待核字段在 **两读全部** `region.excerpt`，不是去值后的位置/项目名。一侧 45、一侧 0 时，这等于把较完整一侧的单元格原文（通常含结果）作为第 2 轮可见候选。

5. **提示合同现状。** 主读 `page-review-r3/v17`：输出 schema 把 `context` 列为必填键，值仍可为 `null`；域模型 `PageFactObservation.context` 仍可空，历史 v1/v2 禁止增写 context。针对性 `page-targeted-review/v5`：仅在“原件确实对应某个 targets”时沿用待核 `field_name`，完整原标签留在 `raw_text`/`context.target_text`；禁止猜测、强制二选一、补写结果。会议已声明这两版 **未实测**。格式修复只修组织错误，日期/数值歧义不可修复；修复后指纹变少会失败。

6. **本地串行依赖。** 两读都在 `omlx`/`mlx-serve`/`mtplx` 时，同轮后一读的 `depends_on` 被写成前一读，第 2 轮 B 不再直接依赖 `compare:1`。调度按直接依赖：`all(dep in completed)`。因 A 仍依赖 `compare:1`，现网传递上 B 仍会等对账完成。页图默认 `RENDER_DPI = 150`；历史 `render/v2` 才是 300。`get_pixmap` 未做额外转正；原生 PDF 文本排序有 90/180/270 还原，页图身份仍是冻结 PNG 字节。

7. **同页复测被幂等挡住。** 任务键是 `r3_targeted_page_review:{reconciliation_id}`。提示/job 版本进入 payload hash；同键不同内容 → `IdempotencyConflict`（“已有不同版本的复核任务”）。执行器遇到版本或路由变化直接 `TARGETED_REVIEW_CONTRACT_CHANGED`。

8. **会议给出的失败观察（本角色未复验病例）。** 密排横表：A 45、B 0；只读回放 35 个目标、零自动采信；两轮辅助后目标全 pending；A 有值/行错误，辅助 B 省略 context，A 第 2 轮改字段名；300DPI 增内存未提质。

---

### Inference（解释，不是证明）

最高影响缺陷不在“会不会自动采信”——合同目前挡住了——而在 **第 2 轮把单侧读到的结果原文当作可见候选**。这与“独立重读遗漏”相反：遗漏类目标的第二读不再盲读。再叠 v5“沿用 targets 字段名”，两条独立读更容易在 **错误值** 上对齐，产出 `candidate_agreement_unaccepted`（界面：“辅助读法一致，尚未采信”）。仍非采信，但会显著抬高“看起来已经对上了”的误导。

会议把 v17/v5 当作待评估修订，隐含假设是“再补提示就能修横表漏读”。源码不支持这个假设：

- 该事故的入口 **已经选中了** 单侧结构化字段；卡在重读质量，不是没进复核。
- B 整页 0 条，更像版面/朝向/密表读取失败，不是缺一句 context 必填。
- v5 要求改 `field_name`，与已观察到的“第 2 轮改标签”是同一机制，不是相反机制。
- v17 强迫输出 `context` 键，可能把“省略 context → 保持 pending”变成“编造 context → 假候选一致”。格式修复指纹能挡住 **同一次** 纠正改写，挡不住 **新的一轮** 两读同时编造相同关联。

另有真实但次要的入口缝（不是这次 45/0 的原因）：两侧都报了同一字段名、但行集合不同或都缺 context 时，`explicit_conflict_fields` 可能不选这些字段；原对账仍会因键不一致而不采信。把选择改成观察级会扩大目标数，在视觉读取未修好前，多半只是更多 pending。

本地第 2 轮 B 覆盖 `depends_on` 目前靠传递依赖成立，属于脆弱点，不是本事故机制。

---

### Recommendation（不放宽采信的最小后续；非实施令）

**不要再胀提示，也不要把 v17/v5 当成已验证修复。** 采信门保持现状：`candidate_auto_accept` 永假、空/缺关联不算一致、不跨轮配对、不把单侧当“不存在”。

建议的最小合同修正（若 Codex 进入编辑轮）：

1. **遗漏类目标第 2 轮保持盲读。** 仅当两侧第 1 轮都对该字段有观察时，才允许 `prior_excerpts_visible`。单侧/字段名 XOR 进来的目标：`candidate_excerpts` 为空，或不含结果/数值，只保留项目名或位置标签。这是与本次失败机制直接对应、且不放宽采信的最小改动。
2. **不要用“沿用 targets 名称”换独立身份。** `field_name` 继续抄原件；targets 只作查找提示。比较已用 `normalize_field_name`，不必让模型改名。
3. **下一孤立实验：源保全朝向/整页转正视图，而不是 300DPI 或病种裁剪。** 冻结 `page_image_sha256` 仍必须作为权威原图发送；任何转正/局部视图只能是额外、非采信输入，且不得改 DPI 默认。禁止按检验单/病种做专用裁剪。
4. **不要** 为测新提示而改幂等键、加第 3 轮、做自动语义对齐、或把候选一致升级为采信。
5. 可选稳健性：第 2 轮串行 `depends_on` 显式保留 `compare:1`，避免以后并行化时丢对账门闩。字段名 vs 行级选择对齐可另立缺陷，不作为本事故最小补丁。

---

### Uncertainty（未核实）

- 会议中的 45/0、35 目标、两轮全 pending、A 改名、B 省略 context、300DPI 无效：本角色未读病例与回放产物，当作 **陈述观察**，不是独立复验。
- 辅助 B“省略 context”是有观察但 `context=null`，还是仍接近空页，源码无法区分；两者对 v17 的预期效果不同。
- 该横表是 PDF 旋转元数据未反映到页图，还是肖像页上的横向表，未看图不能判定；这决定转正实验是否有依据。
- v17/v5 对假一致率的方向未测。
- 用户是否会把“辅助读法一致，尚未采信”当成临床确认，本角色无界面终裁权。

---

### 对主场计划的异议

主场把范围写成“审阅单侧数值/日期重选 + 提示合同，提出最小一般修正”。计划可成立，但有三个过强假设需要 Codex 明确否决或采纳：

1. **把未实测的 v17/v5 当作前进方向。** 尤其 v5 与已见表白失败同向。
2. **认为入口选择不足是主因。** 45/0 已被字段 XOR 选中；真正危险的是第 2 轮答案泄漏 + 改名。
3. **继续在同一 `reconciliation_id` 上“再跑一遍新提示”。** 现网幂等会拒绝，除非先做新的原页双读（那是另一份身份，不是同一辅助任务的续测）。

---

### 给 Codex 的决策点

| 决策 | 建议默认 | 若选反面的代价 |
|---|---|---|
| 遗漏类第 2 轮是否仍展示含值摘录 | 否（盲读） | 保留则继续制造假候选一致 |
| 是否落地/测量 v5 改名 | 否 | 与已观察失败同向 |
| 下一实验 | 源保全朝向/整页转正，原图哈希不变 | 继续胀提示，对横表漏读无源码依据 |
| 是否按观察级扩大入口 | 本次不做 | 目标膨胀，读取未修好则全是 pending |
| 候选一致是否更接近采信 | 否 | 直接违反本任务“不放宽采信” |

---

### 给 Codex 的有界问题

1. 该页辅助第 1 轮 B 是 **零条 facts**，还是 **有 facts 但 context 全空**？前者支持朝向实验；后者才使 v17 的必填键有针对意义。
2. 第 2 轮可见摘录：是否接受“仅真冲突展示、遗漏类保持盲读”作为唯一最小合同修正？
3. 朝向实验若做，是否允许在 **同一冻结页图之外** 增加一张非采信转正图，还是必须新开 processing revision（会换 `page_image_sha256`，超出针对性复核）？

**在 Codex 回答前的安全暂定路径：** 不采信、不改源码、不跑模型、不把 v17/v5 当已验证；若只做一件事，先去掉遗漏类目标第 2 轮的含值摘录。
