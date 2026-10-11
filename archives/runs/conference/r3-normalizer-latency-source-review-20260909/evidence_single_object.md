所有源真文件与直接依赖已审阅完毕，测试覆盖已核对。现在整理并输出完整审阅报告。

关键结论已形成：严格校验器存在“可选中但永不可通过”的采信观察类别、校验首错即停与修复预算 2 的算术矛盾、以及修复轮全量重发生成是耗时主因。以下为完整会议输出。

---

# Conference Output: r3-normalizer-latency-source-review-20260909 - evidence_single_object

## Output

角色：`evidence_single_object`（重要证据审阅，只读咨询）。本报告为一次完整有界审阅：未调用任何模型 API，未修改代码、病例、数据库或默认模型；仅读取了指定源真文件及其在 app/tests 内的直接依赖。

### 一、审阅范围与证据基础

**已读源（evidence）**：
- `app/agents/evidence_normalizer.py`（全文 2085 行：系统合同、提示构建、解码规范化、语义门禁、修复 Runner）
- `app/agents/deepseek_evidence_normalizer_transport.py`（全文：GLM 流式传输、会话历史、receipt）
- `app/projections/page_review_sources.py`（严格来源校验器 `validate_accepted_candidate_sources`）
- `app/projections/page_review_pending_normalization.py`（pending-only 策略）
- `app/services/fact_normalization_executor.py`（持久任务执行器、修复预算）
- `app/services/fact_normalization_source_adapter.py`（冻结输入重建、定位压缩）
- 直接依赖：`app/projections/page_review_model_input.py`（compact 投影）、`app/projections/page_review_pending.py`（pending 观察）、`tests/v2/domain/test_page_review_candidate_sources.py`（现有决定性测试）
- 运行时事实引用自会议上下文（owner runtime evidence）：v21 group1-2 成功（684s）；group3-4 三次完整响应共 1744s 后来源匹配失败；末次 75427 输入 / 38221 输出 / 30714 思考 tokens、714s、finish=stop。

### 二、核心发现（按影响排序）

#### 发现 1（最高影响）：存在“可被选中但永不可能通过校验”的已采信观察 —— 结构性收敛死锁

**证据（sourced fact）**：
- `app/projections/page_review_sources.py:53-67`：对每个事实候选的每个 `source_observation_ref`，要求 `_literal_text(excerpt)` 整段出现在**同页某一个**定位的 `_literal_text(localized_text)` 中（`excerpt in locator_texts[key]`，单定位整段包含）。
- `_literal_text`（`page_review_sources.py:8-9`）做 NFKC 归一并**删除全部空白**。读片方拼接的摘录 `行1 ... 行2 ... 行3` 归一后为 `行1...行2...行3`，其中省略号 `...` 是读片插入的字符，不存在于有效文本或任何定位文本中。因此该摘录**在任何单个定位中都不可能被找到**——与运行时复现一致（上下文：三条字面行被 ` ... ` 拼接，所选定位各自含单行）。
- 该观察仍进入模型输入的 `accepted_observations`（`evidence_normalizer.py:812`，compact 仅移除 `normalization_key`，`page_review_model_input.py:13`），且系统合同（`_SYSTEM_CONTRACT`，`evidence_normalizer.py:430-583`）**没有任何关于拼接摘录不可引用的前置约束**——该规则只出现在校验失败后的修复报错文本里（`page_review_sources.py:64`“不要把带省略号的拼接摘录当作连续原句”）。
- pending 侧对此是容忍的：`page_review_pending.py:38-43` `_unique_text_anchor` 找不到就返回 `None`，不报错。不对称进一步说明：拼接摘录在系统里是已知形态，但只有 accepted→事实候选这条路径会硬失败。

**推断（inference）**：模型第一轮无从知晓该约束，按合同正常引用该观察即触发失败；修复报错虽已具体（含候选、ref、页、摘录前 240 字），但每轮修复要求全量重生成（见发现 3）。若同一调用内有多个候选引用了 doomed 观察，结合发现 2 的算术，**无论模型多顺从都不可能收敛**。

#### 发现 2：校验器“首错即停” × 修复预算 2 = 多 doomed 引用的确定性失败

**证据（sourced fact）**：
- `page_review_sources.py:46-67`：`raise` 位于候选循环内部——每次校验只报出**第一个**失败的 (candidate, ref)。
- `evidence_normalizer.py:2052-2058`：`_validate_normalizer_semantics`（含来源校验）的异常走 schema 修复路径；执行器预算 `max_schema_repairs: int = 2`（`fact_normalization_executor.py:448`，Runner 默认同值 `evidence_normalizer.py:1917`）。即最多 3 次完整响应（初始 + 2 修复），与 group3-4 的“三次完整响应后失败”完全吻合。
- 修复提示把该问题标记为“未能通过严格 JSON Schema 校验”（`evidence_normalizer.py:1868`），但来源闭包失败并非结构问题——措辞错位会诱导模型做结构修补而非改引用（问题正文本身是具体的，部分缓解）。

**推断（inference）**：若一次输出里有 ≥3 个 doomed 引用，即便模型每轮完全服从报错修改，预算内也不可能全部暴露并修复。这是与模型能力无关的**结构性收敛上限**，直接把 ~1750s 耗费在必然失败的路上。

#### 发现 3：耗时结构 —— 修复轮的全量重发 × 全量重生成

**证据（sourced fact）**：
- 传输层会话在进程内保存完整消息历史，每次 `continue_session` 把 [初始提示, 全部历史助手回复， 修复提示] 整体重发（`deepseek_evidence_normalizer_transport.py:451-464`）；API 无状态，每次都重新完整思考（`clear_thinking: False` 只影响输出保留思考，不减少再思考）。
- 修复提示要求“重新输出完整 JSON 对象”（`evidence_normalizer.py:1874`）——末次 38221 输出 tokens 即整份候选 JSON 的全量重生成，30714 思考 tokens 为整任务重思考；输入增长到 75427 tokens 主要来自历史中累积的助手巨型回复。
- GLM 路由（zhipu-coding-plan）用 `json_object` response_format（`deepseek_evidence_normalizer_transport.py:566`），schema 必须完整内嵌提示（`enforces_output_json_schema` 为假时 Runner 保留内嵌，`evidence_normalizer.py:1934-1943`）——这是设计使然，非缺陷。
- R3 输入**没有提示体积上限**：`_MAX_PROMPT_CHARS` 守卫仅作用于 `page_review is None` 的 legacy 路径（`evidence_normalizer.py:892`）；R3 仅受 `max_pages_per_call=20` 约束。

#### 发现 4：提示重复的真实形态（含对我初始假设的否定）

**经核验不成立的重复（challenge 结果）**：
- 我最初怀疑 `accepted_facts` 与 `accepted_observations` 双份转储同一事实。**已证伪**：`compact_page_review_input` 明确弹出 `accepted_facts`/`accepted_clause_signals`/`accepted_handwriting` 三个冗余列表（`page_review_model_input.py:10-11`），`accepted_observations` 是唯一载体。
- schema 在提示与 response_format 的重复**已解决**：仅 omlx `json_schema` 受限解码路由去内嵌（`evidence_normalizer.py:869-872`、`transport:537-545`）；GLM/DeepSeek 的 `json_object` 路由结构不受服务端约束，内嵌是必要的，保留正确。

**确实存在且属设计取舍的重复（observation）**：
- 页有效文本全文（`ocr_sidecar_pages[].sidecar_transcription`，`evidence_normalizer.py:770-776`）+ 各定位的 `localized_text`（其并集近似覆盖页文本）≈ 页内容约 2 份。侧车是 R3 合同明示的“文字锚定位与核对”用途，且跨行药名还原依赖连续上下文，**不建议为省 token 去掉**。
- 修复轮内，初始提示（含系统合同+schema）每轮重发；助手自身的巨型回复累积重发——这是发现 3 的主因，非独立缺陷。

### 三、最小优化方案（不损失来源与待核对内容；均为建议，不实施）

方案按“不动匹配语义 → 动提示合同 → 动校验合同”递进，A+B 为最小组合，C 为低成本增强，D 为需 Codex 裁定的合同变更。

**方案 A（首选，确定性预检与三态分类，消除 doomed 类别本身）**
在冻结输入投影时（`_model_input_payload` 处，`evidence_normalizer.py:798-815`，此时 `evidence_input.available_locators` 就在手上）对每个 accepted observation 用**与校验器完全相同的** `_literal_text` 包含检查做确定性预判，三态分类：
1. **可验证**：摘录整段出现在同页某定位中 → 维持现状，可选为事实来源；
2. **拼接摘录**：整段不可见，但按省略号（`...`/`…`）切分后各段均能在同页定位/页文本中逐字找到 → 在输入中明确标记为“不可作为事实来源，须以未解决项保留该内容”（结构上移出可选集合，或加确定性布尔标记），内容与观察 ref 原样保留，页面闭合由未解决项 `affected_pages` 覆盖（`validate_output_page_closure` 已支持，`evidence_normalizer.py:1848-1855`）；
3. **文本不匹配**：切段仍找不到（读片文本与有效文本漂移）→ 同样降级保留，并带专用 code（如 `observation_excerpt_text_mismatch`）回流页级判读核对。

效果：把“模型花 700s 发现一个必然失败”变为“构建输入时零成本拦下”；不放松任何匹配，不删任何来源或待核对内容（downgrade 后仍在输入与未解决项中可见）。这同时回答了任务书要求的“区分真缺定位与无效拼接摘录”。

**方案 B（校验器错误聚合，修掉发现 2 的算术死锁）**
`validate_accepted_candidate_sources` 收集**全部**失败的 (candidate, ref, page, excerpt) 后一次性抛出（确定性排序、截断上限如 20 条并标注剩余数，配合 `_schema_repair_prompt` 的 `problem[:12000]`），使一轮修复可覆盖全部 doomed 引用。现有测试 `test_source_failure_identifies_candidate_reference_and_preserves_strict_match` 断言单条信息包含候选与 ref，聚合形态需同步扩展该测试。附带微修：修复提示对来源类失败不再称“JSON Schema 校验”失败，避免诱导结构性修补。

**方案 C（系统合同前置声明）**
在 `_SYSTEM_CONTRACT` 中前置一句：“摘录含省略号拼接的已采信观察不得作为事实候选来源，只能进入未解决项”（或直接依赖方案 A 的输入标记，则无需改合同）。属于提示合同变更：会改变 `evidence_normalizer_prompt_template_sha256`，需要任务侧提示版本升级；对正在运行的 v21 重试无影响（其输入与配置已冻结）。

**方案 D（决策点：多定位精确重构放行）**
替代“降级”的另一种处理：校验器接受**精确重构**作为单定位包含的等价形式——摘录按省略号切段后，各段逐字出现于所引的不同定位、页序不回退、覆盖完整。代码库已有同型先例：`_cited_source_text_in_page_order` + `_is_source_backed_cross_locator_span`（`evidence_normalizer.py:1633-1692`）已为药名实现多定位页序精确重构。逐字性、页序、完整性均保持，不引入模型新文本；但审计粒度从“单一连续高亮”变为“多段拼接”，是否算“放松匹配”属于合同语义变更，**应由 Codex 裁定，我不替位决策**。

### 四、决定性测试提案（与现有测试风格一致）

1. **拼接摘录 doomed 类**：构造页含三条行定位，accepted 摘录为 `行1 ... 行2 ... 行3`（复制运行时复现形态），断言现状校验必失败（锚定缺陷）；方案 A 后断言该观察被标记/移出可选集且页面仍闭合；方案 D 后断言三段各归其定位且**乱序/缺段/换页仍失败**。
2. **错误聚合**：两个候选分别引用两个 doomed 观察，断言一次校验抛出的信息同时含两个 candidate_id（修复预算 2 内可收敛的充分条件）。
3. **分类边界**：切段后任一段在页文本中也找不到 → 归入“文本不匹配”而非“拼接摘录”（防止把读片漂移误放行为可重构）。
4. **回归锚**：现有四条测试（`tests/v2/domain/test_page_review_candidate_sources.py`）必须原样通过，确保 A/B 不改变任何现可通过/应拒绝 case 的语义。

### 五、风险与边界

- 方案 A/B/C 均不触碰匹配语义、不删候选、不生成替代文本、不改模型/强度/端点，符合“不损失来源和待核对内容”与“不做基于耗时的模型替换”。
- 未验证项（uncertainty）：`...` 拼接的确切产生位置在读片/判读侧（不在本审阅六文件内，我未追出具体插入行）；group3-4 的 doomed 观察是否为唯一失败模式只能由运行时数据证实，我按上下文复现接受；正在运行的修复重试我未接触其数据库与会话。
- 方案 A 需要提示/输入投影变更，落地时属受控变更：需提示版本 bump、冻结配置一致性检查（`_load_frozen_agent_config` 会拒绝哈希漂移，`fact_normalization_executor.py:542-549`）与新旧任务兼容策略。

### 六、给 Codex 的质疑、决策点与有界问题

1. **质疑（最重要）**：当前设计让“accepted 但拼接摘录”的观察进入可选集合、又在门禁处必然拒绝——接受侧与规范化侧对同一事实形态意见相反。若 Codex 认定拼接摘录本质上非法，最小修正是接受侧（判读调和）不再产出此类 accepted key 或落库时即标记；这超出本审阅文件范围，请裁定修正落点（读片侧 / 调和侧 / 规范化输入侧）。我的安全暂定路径：规范化输入侧预标记（方案 A），因为它不动读片与调和的冻结语义。
2. **决策点**：方案 D（多定位精确重构）是否踩“不放松匹配”红线？我的判断是不引入新文本、强度等价，但审计粒度改变，需明示裁定后才有决定性测试基线。
3. **有界问题**：错误聚合的每轮上限（我建议 20 条、确定性排序截断并标注剩余数）是否符合产品对修复反馈的展示预期？
4. **次级观察（供记录，不建议现在动）**：R3 提示无体积上限（仅 legacy 有 100k 守卫）；若未来页组持续变大，可在规划层加确定性字符预算，属规划层变更，超出本次六文件范围。

**结论（recommendation）**：group3-4 的 1744s 失败不是模型能力或纯耗时问题，而是“doomed 可选观察 + 首错即停 + 修复预算 2”三个确定性因素叠加的结构性结果。最小且不损失信息的修复组合是 **A + B**（可加 C 增强，D 待裁定）；预计可把该失败类别从“三轮约 1750s 后必然需要核对”变为“首轮构建输入时零成本降级保留”，并使多 doomed 引用场景在预算内可收敛。
