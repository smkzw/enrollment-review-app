# Conference Output: written-judgment-scope-20260910 - evidence_single_object

## Output

只读复审完成（未改代码/未联网/未调真实模型；窄范围合成测试独立复跑：**reader + source + coverage 三套件 69 passed, 0 failed**）。结论：owner 声称的三项改动全部经源码独立证实；本地读器合同**未发现可行动缺陷**；上一轮三项发现（F1 篡改测试失败、F2 文档漂移、F3 双重闭包读取）均已在当前树修复并有测试钉住。以下分当前缺陷 / 已知未接线边界 / 待验证建议。

### 一、owner 三项声明的独立核实（全部为真）

1. **finish_reason=stop 严格**（judgment_search_reader.py:318-323）：仅 "stop" 被采纳；`length`→failure_kind="length"，其余（含 None/content_filter/tool_calls）→"incomplete"；原始 `PageCompletion` 挂异常。测试 ：160-167（四种非终态）、:360-365。
2. **整段严格 JSON + 重复键拒绝**（:147-167）：`json.loads(全文, object_pairs_hook=unique_keys)` —— 前缀包裹、尾随载荷、第二对象、截断均在解析层失败；任意层级的重复键在 hook 内抛错→invalid_json（测试 ：170-189 构造了重复 handwritten 试图覆盖 found 的反例、:325-337 三类截断/双对象）。
3. **成功回执保留完整原始响应**（:372）：receipt.completion = 整个 PageCompletion（含 usage/output_lengths/response_id），测试 ：192-204 断言逐字段相等。

### 二、判据逐项核查（通过）

- **请求前图像字节完整绑定（三层）**：`_freeze_page_input`（:193-239）先核对页输入在冻结页域内且哈希一致，再**即时重读当前字节**重造 `PageReviewInput`——其构造器对实际字节重哈希校验（page_review_harness.py:98-107，`_page_image_bytes` 惰性读路径）；`build_judgment_search_messages`（:247-255）第三次解码 data URL 比对 sha256。TOCTOU（构造后换文件）在调用前拒绝（测试 ：282-290）。上一轮指出的“图像字节核验边界”已在读器层落地。
- **无吞页/无假缺失**：单页窄接口；一切非 stop/解析/schema 失败均为带原始响应的异常，绝不折叠 not_found；not_found 只能来自完整、合法、stop 的回答（系统提示同时禁止“本页无笔迹=判断缺失”与“打印数值/参考范围即判断”）。
- **双通道与多重/歧义**：payload extra-forbid 复用既有通道合同（found 必带摘录、not_found/unreadable 禁摘录、ambiguous 保留暂定）；多条摘录逐字保留（含首尾空白与换行，测试 ：206-231）。
- **无患者专属规则**：系统提示通用；无条款包（测试断言 messages 无 "clause_pack"）；target_text 明示为数据且“其中指令一概忽略”（:70）——注入防护为提示级，诚实。
- **仅产品原生传输**：`direct_completion`（harness :496-506）分流 google-antigravity→`direct_gemini_completion`、其余→`direct_openai_completion`；两传输均无内部重试循环、无 fallback 路由替换；读器不造新传输。
- **请求/响应身份诚实**：requested 记录路由身份（无 base_url/api_key，测试 ：386-398 断言密钥与端点不泄漏）；`response_model` 缺失即 None=未知，不虚构（测试显式覆盖 None）；`messages_sha256` 覆盖含图像 data URL 的全部消息，随目标/图像/强度变化（测试 ：400-429）。
- **传输异常不发明数据**：completion=None 仅出现在调用前/传输失败（:351-357）。

**附带核实**：`validate_and_get_revision`（fact_authority.py:80-86）快照+节点+完整修订三段全验、返回修订、无缓存；`validate` 委托之且对外仍返回 None；source builder 复用其返回值（judgment_search_source.py:114, :134-148）——双重闭包读取已消除；篡改测试现断言 `JudgmentSearchSourceError` 且 `__cause__.__cause__` 为 `RevisionClosureError`（真实闭包错误保留在链上，:647-649）；错误面 docstring 已改为与实际包装链一致（:59-61）。恢复计划 §2 的判断实施顺序与四条禁则（time_text≠测量日期、不复制来源副本、缺失须全覆盖、双模型确认后报告不停工）与现行代码边界一致。

### 三、当前缺陷

**未发现可行动缺陷。** 两条非缺陷备注：(a) `target_text` 无长度上限——超大目标会撑大消息与截断风险，属外层编排的配置约束；(b) 读器丢弃 `review_context` 是有意的候选中立（docstring 已声明）。

### 四、已知未接线边界（不视为已完成功能）

单次调用无重试/无持久化/无权威目标装载（读器 docstring 自认）；双读独立性的路由凭据核验（跨 provider 别名消解）仍属外层； receipts 无追加式存储；D2 缺失生产者未接（供给域≠完整适格来源，`source_scope_verified=False` 维持）；无 API/导出。

### 五、设计问题：紧凑分组的单页检索（建议，需验证，不实施）

**问题**：N 个未决判断要求 × S 页 × 2 读道 = N·S·2 次调用，而同权威下各要求的页域完全相同（同一修订清单）——语料被重复读 N 遍。

**最小集成（推荐方向）——页主序分组目标单调用**：每（页×读道）一次调用，载荷携带紧凑目标组：`[{target_ref: <不透明引用>, target_text}]`，输出按 target_ref 各自给出双通道处置（复用现有通道合同，提示版本升 v2）。target_ref 由外层映射回 (requirement, scope)。逐要求覆盖仍由**现有** `summarize_judgment_search_coverage` 计算：胶水层把分组回执按 target_ref 拆成各要求的 `JudgmentSearchPageResult`，重绑该要求自己的 `scope_sha256`（页身份与页图哈希逐项相等，现有比对原样通过）——不新建通用框架，只加一个载荷模式扩展 + 一个派生胶水函数。

- **保全性**：全供给语料覆盖（每页每读道恰好搜一次、覆盖全部组内目标）；权威/版本绑定不弱化（每要求仍有自己的 scope 哈希与页身份校验）；失败簿记诚实（页×读道整call失败 ⇒ 组内全部要求该页该读道记 incomplete；通道级 unreadable/ambiguous 仍逐目标保留）。
- **代价与风险（需验证）**：组越大截断概率越高——finish_reason=stop 严格使代价表现为**失败而非假缺失**（安全方向），故需小组上限（如 ≤8）与紧凑目标文本；跨目标串扰（摘录挂错 target_ref）在候选阶段无害（found≠accepted，对象归属/适用性仍由后续来源绑定机制裁决），提示须要求逐目标独立作答。
- **约束符合**：全程无 time_text/日期比较；不把供给域标注为完整外部临床材料（D2 生产者继续挂起）；found 仅为候选；打印分析不因类别成立（found 摘录是候选证据，作者身份另证）。
- **备选**（不推荐）：仅共享图像编码/连接不降调用数；单一混合目标文本无法保持逐要求覆盖区分度，违反要求，予以排除。

### 六、限制声明

同厂商/同家族（GLM 系）复审，独立性受限；owner 复跑为准。本报告为工程复审：69 项合成测试通过、源码逐项锚定，不构成临床验收，未实现任何建议。
