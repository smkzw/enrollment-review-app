# Conference Output: written-judgment-scope-20260910 - evidence_single_object

## Output

接受全部四条反例。以下先撤回上一稿的错误部分，再以当前源码为据给出修正后的更小第一步。未改代码、未联网、未调用模型；非临床验收。

---

### 一、撤回与更正（对照反例逐条）

**撤回 1（对反例 2 成立）：`judgment_source_association` 事实字段是冗余设计。** 决定性源码：发布事实携带 `source_candidate_ids`（`fact_publication_service.py:414`，且重放校验事实↔候选集全等 ：330-342），候选合同持久化完整 payload（含 `source_observation_refs`，`facts.py:242`），而 `source_observation_ref = "page-observation:" + canonical_hash({review_id, kind, index})`（`page_review_sources.py:27-31`）——期望路径已有的 `rebuild_visual_sources` 重建（评审+对账）之上重跑 `accepted_observations`（同文件 ：12-32，纯函数）即可反解引用到具体已采信观察及其 context。**引用链现在就可完整重建，不需要任何新存储。** 更重要的是：把关联副本抄到事实上“并不连接判断与被判断的测量”——真正的新不变量必须建立在**两条被引用的已采信观察之间**（见第二节），不是事实与副本之间。

**撤回 2（对反例 1 成立）：以测量页集合 P 作为缺失证明的覆盖域是错的。** 对应节点的打印临床分析可以在另一页/另一份文件；页级“无 CS/NCS”对打印叙述性判断零信息量。同时决定性源码：`SourceDocumentMetadataRevision` 只有 `document_type` + `source_party`，**没有文档日期字段**（`evidence_ingestion.py:132-140`）——快照成员资格既不给出作者身份，也不给出时间适用性；时间适用性只能按要求的 `source_validity_window`（`rules.py:288`）在搜索时对候选页的来源日期逐页证明，**证不出的文档不得被排除出搜索域**（不确定性只能扩大搜索域，绝不能缩小）。

**撤回 3（对反例 3 成立）：我对 time_text 的语义断言超出合同。** 可执行的语义只有：可选文本（min_length 1）、经 `normalize_scalar_v4` 归一化进入 context 哈希、双读相等被强制（`page_review.py:61-67` 自述仅 "Source-written association"；`page_normalization.py:147-159`）。正确分类：**未知性质的关联文字**——只能作两个观察 context 之间的**不透明相等判别器**；绝不上浮为事件日期、绝不与 `fact.date_range` 比较、**不相等也绝不解释为“不同次测量”**（只能得出“同锚不可证”）。

**撤回 4（对反例 4 成立）：`judgment_binding` 可配置开关。** 默认 requirement 即默认放行未证明的完备性，方向性错误，整体撤回。逐测量完备性语义只能来自方案解构产出的、绑定方案原文摘录的结构化 `judgment_scope`（模型产出、来源绑定、任务特定）；在它存在之前，完备性判定一律“未知”（呈现为未核实），不存在用户风险偏好问题。

---

### 二、修正后的第一步（现有持久化即可达成，不新增合同）

**核心：把“批注存在性证明”与“对某要求的适用性证明”拆成两个独立判定，新增的只是第二个确定性判定，零新存储。**

**存在性（今日已可证，保持不变）**：双读独立采信的 CS/NCS 批注 + 判断事实定位身份绑定该批注读道定位（候选期已被 `validate_accepted_candidate_sources` 强制：定位↔所引观察 page_review_id+kind+摘录全等，`page_review_sources.py:53-71`）+ `asserted_object == context.target_text`。

**适用性（新判定，纯重建+比较）**：经第一节验证的重建链取回判断事实所引的已采信手写观察（含双读一致 context），与**同要求绑定**的已发布测量事实所引的已采信事实观察（同法重建）比较 `observation_context_key` 全等：
- 全等 → 适用（两条双读一致的来源书写关联指向同一锚）；
- 任一侧 context 缺失（time_text/location_text 为 None 属合法常态）或键不等 → **适用性未知** → 期望呈现 observed_weak / observation_unverified，detail 明示“判断存在但与该测量的来源关联不可证”；
- 该要求下**不存在任何测量事实**时无消歧对象，存在性单独足够（与今日一致）。
明确不做的：不等→不同测量（time_text 语义升级）；日期对日期比较；完备性清点。

**发现的真实接线缺陷（决定性源码）**：修订路径丢弃引用链——`_build_new_fact` 的 candidate_payload **不含 `source_observation_refs`**（`fact_correction_service.py:736-759` 逐字段可见），修订事实只指向合成 fcorr 候选（:613）。即判断事实一经数值修订即落入“适用性未知”。修正方向：`_build_new_fact` 从目标的原始候选继承 refs（`target.source_candidate_ids` → 原候选 → refs，链路现成，纯接线）。旧数据（候选无 refs）：适用性未知 → 未核实，**不自动迁移证明**——与 D1 修复的 provenance-None 保守处理一致。

**测试**（合成，复用现有 fixture 风格）：同页两条同名测量（不同双读 context）+ 锚定其一的批注——判断引用另一侧 → weak/未核实（适用性未知）；context 全等 → observed；修订后继承 refs → 仍可证；无 refs 旧候选 → 未核实；同要求无测量事实 → 存在性单独足够。

### 三、D2 修正框架（本轮不实现，只定义到位）

在跨文档搜索/覆盖域可证明之前，**D2 维持且仅维持未核实兜底**（现状即正确）。目标态的充分条件（取代上一稿的 P 集合）：

- **合格来源域** = 活动完整处理修订内的文档，其冻结元数据落入研究者方分析-capable family（作者身份来自 source_party+document_type，**不来自快照成员资格**）；时间适用性按 `source_validity_window` 在搜索时逐页对来源书写日期证明，证不出者**留在域内**。
- **来源绑定搜索报告** = 按（权威， 要求）持久化的报告，枚举实际搜索过的文档版本/页单位，每单位分类：`found_handwritten(ref) / found_printed_analysis(ref) / none / unreadable / ambiguous`，**同时覆盖手写与打印两通道**。仅当每一合格单位均为 none 且已搜索集合可证等于合格域时，才产出 PROFESSIONAL_JUDGMENT；任一 unreadable/ambiguous/未搜索单位 → 维持未核实。空手写列表永远不是输入——"none" 是搜索断言的结果，不是从缺席推断。单页天然不足（域为权威级）。
- 打印叙述性判断的识别（读道级 `assessment_role` 分类 + 双读一致 + 文档方元数据三重证据）并入该搜索合同作为第二通道的判定器，不再挂在 R1 下。
- 用户规则不变式：确认缺失 = 可报告的未决判据（缺口行 + 责任方/动作），工作流继续，**绝不因确认缺失停下问用户**。

### 四、遗留解释性事项

- 适用性判定依赖“测量事实也引用其来源观察”——今日候选校验已强制引用，但测量与判断引用的观察 context 若都无 time_text/location_text，区分度退化为纯名字（即现状），此时保持未核实是否可接受属产品裁决（建议：保持未核实，理由同撤回 4）。
- `judgment_scope`（逐测量完备性的方案语义）由解构链产出的具体合同形态，需与规则解构层另行设计，本稿不预设。

### 边界

源码锚定：`fact_publication_service.py:314-357/414`、`facts.py:242/377-397`、`page_review_sources.py:12-32/35-71`、`fact_correction_service.py:613/736-765`、`evidence_ingestion.py:125-149`、`rules.py:279-297`、`page_review.py:61-67`、`page_normalization.py:147-159`。本稿为设计修正，未实现；R1 原框架按反例收窄（存在性/适用性分离，撤回冗余字段与配置开关）；D2 未动、维持未核实。
