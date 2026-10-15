# Conference Participant Output: v3-abc-retro-20260918 - general_single_object

## Boundary Check

- 回退声明：原定 `zcode / GLM-5.3-Flash / max` 在可恢复会话建立前不可用，本轮由声明的 `codex-subagent` fallback 执行，实际为 `codex / gpt-5.6-sol`。因此本报告不具备原计划 Z Code 模型的独立性，实际 effort 也不能证明等同于原定 `max`。
- 本轮为只读独立设计审阅。未查看其他参会者输出，未写 `runs/conference/v3-abc-retro-20260918/general_single_object.md`，未修改源码、数据库或临床原件。
- 初始读取：
  - `context/v3-abc-retro-20260918_conference_context.md`
  - `plans/codex_main_venue_v3-abc-retro-20260918.md`
- 为补足五项问题定性的证据缺口，额外只读核查了明确列入 Source of Truth 的 `RETURN_A.md`、`RETURN_B.md`、`implement.md`、`design.md`、最新 SQLite 冻结状态、门禁实现/测试、MTPLX 日志及 B 链 API 接口。
- 实时 `127.0.0.1:8902` 在本轮不可达；先排除代理后仍为 connection refused。因此“当前 blocking=5”由最新数据库 checkpoint 复核，而非实时 API 复核。
- 不主张最终临床、监管、浏览器、视觉或用户验收；以下是给 Codex 的咨询结论。

## Independent Work Product

### 一、核心结论

主会场当前把剩余五项概括为“EX-04×3、EX-07x、IN-06”，但这五个门禁 issue 并不等于五个相互独立的问题，也不能简单二分为“临床未决”与“模型能力”。

建议重新定性为：

| 当前门禁项 | 独立定性 | 建议路径 |
|---|---|---|
| EX-04 `FREQUENCY_SOURCE_FORM_UNVERIFIED` | 高概率为门禁识别缺陷，不是临床未决 | 先修确定性门禁/反例测试，不再调用模型 |
| EX-04 `TIME_ANCHOR_UNRESOLVED` | 高概率为上述识别缺陷派生的重复误报 | 与频次识别一起修复；不要登记虚构锚点 |
| EX-04/EX-15 `OBSERVATION_POLICY_SOURCE_UNVERIFIED` | 一个 issue 同时覆盖两个谓词；含真实操作语义缺口，但当前“EX-04×3”的表述遗漏 EX-15 | 分别回源；无权威解释时保持阻塞，不做通用降级 |
| EX-07x `TIME_ANCHOR_UNRESOLVED` | 真正的方案解释未决 | 只能由有来源的解释材料闭合；不再耗模型 |
| IN-06 `PREDICATE_CLAUSE_NOT_IN_SOURCE` | 确定性的来源装配缺口，不是临床未决 | 目标化宿主/草稿修复，不必等待 GLM |

最重要的反对意见是：不应在尚未排除 EX-04 门禁误报前，把五项整体归入“原文不足或模型能力”，更不应以“unresolved_items 已显式存在”为理由将 `TIME_ANCHOR_UNRESOLVED` 通用降级为非阻塞。

### 二、EX-04 两个时间问题疑为同根工程缺陷

最新 revision 15 已经保存了：

- 原文：`定义为1周≥4天受试者无任何白天户外活动`
- `occurrence_window.duration = 1 week`
- `minimum_count = 4`
- 单位为“天”
- `scope.quantifier = every`
- horizon 显式标记 unresolved

但门禁的执行顺序是：

1. `_predicate_temporal_text()` 在谓词 identity 已含时间量时优先返回 identity。
2. EX-04 identity 只包含“1周内无任何白天户外活动的天数”等语义，没有把结构化数值 `4天` 合入。
3. `_source_frequency_specs()` 因看不到完整的“1周≥4天”而返回空。
4. 既有 `occurrence_window` 随即触发 `FREQUENCY_SOURCE_FORM_UNVERIFIED`。
5. 同一“1周内”又因未被识别为 frequency definition，被当成 unanchored lookback，触发 `TIME_ANCHOR_UNRESOLVED`。

也就是说，EX-04 的“频次形式”和“回溯锚点”可能是一个检测器缺口产生的双重报错。原文中的“一周”更自然地表示频次分母，而非另一个需要筛选日/随机日锚定的既往回溯窗。

具体修复建议：

- 频次核对不要仅靠 predicate identity 的文本正则；应把 `exact_source_clauses` 与结构化 `duration/minimum_count/unit` 一起核对。
- 一旦 occurrence window 的频次结构与逐字来源闭合，就不得再把同一 duration 送入 unanchored-lookback 判定。
- 增加 EX-04 精确反例：
  - `1周≥4天` + `duration=1 week` + `minimum_count=4 days` 应同时消除 `FREQUENCY_SOURCE_FORM_UNVERIFIED` 和 `TIME_ANCHOR_UNRESOLVED`。
  - 真正的“6个月内感染”且无命名锚点仍应触发 `TIME_ANCHOR_UNRESOLVED`。
- 修复后重算完整性，再决定是否仍有 EX-04 临床解释问题；修门禁前继续换模型价值很低。

### 三、EX-07x 是真正的解释材料问题

EX-07x 原文只有“6个月内存在或疑似蠕虫感染”，未说明从筛选、随机、首次给药还是其他日期回溯。

现有实现与测试已经明确：

- 无合法解释来源时必须产生 `TIME_ANCHOR_UNRESOLVED` 且不可发布。
- 合法、版本匹配、规则范围匹配的解释来源可闭合该问题。
- `register_interpretation_sources` 只更新任务 checkpoint/source input，不修改方案原文，不自动产生草稿 revision；登记后会重新跑 gate。
- 来源被拒、越权、错版本或缺资料要求时仍失败关闭。

因此：

- EX-07x 不应再消耗 Flash/27B/GLM 生成轮次。
- 也不应由模型“猜”成 screening date。
- 应要求一份有身份、哈希、原文定位和适用规则范围的权威澄清材料，例如正式 Q&A、申办方确认函或经批准的医学解释记录。
- 普通操作者临时输入不能自动获得与方案等同的权威；解释只能澄清歧义，不能覆盖方案。

### 四、IN-06 是局部来源装配问题，不应等待 GLM

当前门禁 issue 实际同时指向 `IN-06-C2-P1` 和 `IN-06-C2-P2`，不是主会场描述中的单一 P1。

草稿中两个谓词均绑定了共同前缀：

`整个研究期间（从签署ICF到研究药物给药后6个月）`

但 IN-06b 的 `component_draft.source_excerpts` 只保存了：

`男性受试者及其伴侣同意采取有效的避孕措施且无捐献精子（男性）或卵子（女性）的计划`

门禁逐段检查 predicate clause 是否落在 component excerpt 内，因共同前缀未进入 component excerpt 而拒绝。这是可确定性定位的来源装配不闭合，临床含义并不缺失。

建议：

- 对 IN-06b 做目标化局部修订，把同一正式 source span 中的共同时间前缀作为第二段逐字 excerpt 保存，继续保持分段，禁止拼成原文不存在的新句子。
- 断言 P1、P2 的 exact clauses 都能在 component excerpts 中逐段命中。
- 断言 revision 只改变 IN-06，兄弟规则不变。
- 不建议等 GLM 配额恢复后再碰运气；已有结构足以做确定性修复。若仍走模型，也应由宿主预组装公共前缀并限定模型仅返回目标对象。

### 五、观察选择问题需要拆开，当前统计会误导

最新 gate 的 `OBSERVATION_POLICY_SOURCE_UNVERIFIED` 只有一个 issue，但 `affected_refs` 同时包含：

- `ex04-days-without-any-daytime-outdoor-activity-per-week`
- `ex15_alcohol_over_14_units_within_3_months_before_screening`

因此“EX-04×3”隐去了 EX-15。问题计数是 gate issue 数，不是临床歧义数量，也不是受影响谓词数量。

两者都涉及“多条/多时点记录如何形成规则输入”的操作语义：

- EX-04：哪一周、典型周还是任意周；原文强调“常规生活作息”且需要判断。
- EX-15：筛选前3个月内“每周超过14单位”应如何跨周聚合。

如果权威来源未明确，则这类问题可视为真实操作解释缺口，而不是单纯 JSON 格式问题。但应逐谓词分别登记责任方、待补证据和解释来源，不能用一个通用“保留 unresolved 即放行”的规则掩盖。

### 六、反对“显式 unresolved 即降级非阻塞”的候选发布策略

现有测试明确把 `TIME_ANCHOR_UNRESOLVED` 定义为：

- 局部修订可以保存；
- 草稿仍不可发布；
- 合法解释来源可闭合；
- 无解释时失败关闭。

因此候选路径 c 会改变既有发布安全合同，不是“最小修复”。其主要风险是把一个无法执行的时间窗口发布为正式规则，后续审核可能在筛选日、随机日或首次给药日之间静默漂移。

安全替代：

1. 先修 EX-04 的门禁误报和 IN-06 的确定性来源装配。
2. 对 EX-07x、仍存在的 EX-04/EX-15 操作歧义走权威解释材料通道。
3. 只有在产品层明确引入新的、受约束的“不可执行但可发布”规则类别，并保证：
   - 不能产生 definitive eligibility judgment；
   - 报告显著披露；
   - 有责任人、证据要求、due stage；
   - 下游始终返回 UNKNOWN/needs evidence；
   - 正式规则集中不得静默删项；
   
   才能另立设计讨论。当前不应为了 B 链进度临时改变门禁语义。

### 七、MTPLX 改造：属主生命周期成立，语法/kernel 绕行尚未证明稳定

正面证据：

- 检查到的 lifecycle 文件均含 `started → stop_requested → process_and_port_exited → process_group_and_port_released`。
- revision 15 存在，且最新 gate 已无 IN-02 问题，证明本地语义修订链至少成功完成过一次。
- revision 14→15 的 23 条规则逐条比较显示只有 IN-02 变化，其他 22 条规则完全相同，支持该次局部范围守卫成功。

限制与反对意见：

- 24 个服务日志中有 21 个包含 server error/kernel error 标记；部分同一日志在报错前也有成功 generation，因此不能简单称“全部失败”，但足以说明 kernel 缺陷反复出现。
- 多个日志重复出现 `custom_kernel_mtplx_qsa_prefill...` Metal JIT 编译失败。
- “瘦合同入提示词”证明了可绕过部分请求形态，不等于稳定性已达成。
- 当前 `_GRAMMAR_INCOMPATIBLE_BACKENDS = frozenset({"mtplx"})`，但 `_MTPLX_BACKENDS` 同时包含 `mtplx` 与 `mtplx-api`。若运行配置使用 `mtplx-api`，它会重新携带服务端 schema，绕过合同入提示词逻辑。
- 当前聚焦测试未发现对 `_wire_contract_prompt`、两个 MTPLX alias、瘦合同注入或 host strict validation 的直接覆盖。
- 深度 3 的 schema 瘦身会丢失深层字段约束；宿主严格校验可保安全，但可能造成额外修复循环，必须记录而不能称作等价 grammar。

建议将“是否使用服务端语法约束”改成显式传输能力，而不是散落的 provider 字符串判断：

- 在受控部署清单或 transport capability registry 中使用枚举，例如：
  - `structured_output_mode=json_schema`
  - `structured_output_mode=prompt_contract_host_validate`
- `mtplx` 与 `mtplx-api` 必须解析为同一已验证能力，除非有不同服务版本的实际证据。
- 默认失败关闭；不允许任意环境变量把宿主严格校验关掉。
- receipt 中记录 mode、完整 schema hash、瘦合同 hash、服务版本、prompt tokens 和是否发生 kernel 500。
- 增加最少三类测试：
  1. 两个 MTPLX alias 均不发送 `json_schema` response format；
  2. start/continue/repair 都注入同一合同；
  3. 缺字段、多字段和深层错误仍被 host 严格拒绝。
- 运行验收至少做多次相同长提示和不同长度桶重复试验，分别记录成功率与 kernel error；一次 revision 15 不能代表稳定。

### 八、B 链最短路径需要补齐 commit、episode/snapshot 与激活边界

主会场概括的：

`发布 → 建 subject 31001 → 上传血常规 → original-page-images/v1 → OCR → 事实发布 → 原件回看`

缺少至少以下明确接点：

1. 创建 subject 后取得正式 review episode/workflow stage。
2. 创建 `evidence-upload-preview`。
3. 核对 preview 的 upload mode、base revision、文件 identity/hash 和去重结果。
4. 调用 `/evidence-upload-previews/{preview_id}/commit`；只有 commit 才创建/复用 snapshot 与 processing job。
5. 观察 snapshot `processing` 状态及 job checkpoint。
6. 生成 `original-page-images/v1`，验证页数、页图 hash、方向与原 PDF 页映射。
7. 经共享 oMLX gate 使用 `GLM-OCR-bf16`，保存 OCR 请求/响应与输入图身份。
8. 完成页级风险/局部人工复核以及处理 revision 冻结。
9. fact normalization 后由 `FactPublicationService.publish` 发布事实。
10. 验证活动 snapshot/revision 指针、Patient Profile、事实 locator 和原件回看一致。

B 的正式真实验收仍依赖 A 发布；不建议改 subject 依赖以绕过门禁。可以并行实现/测试读取策略和接口接线，但只能在隔离 fixture 或新鲜测试项目上标记为工程验证，不能冒充 31001 正式 P1 验收。

### 九、C 包前还缺的 A/B 证据

除“十五次局部修订兄弟零变化”外，至少还缺：

- 最新发布前 gate 的可重放证据及 gate version。
- EX-04 门禁修复后的反例与完整性重算。
- EX-07x/观察选择问题所用解释来源的身份、版本、哈希、定位及授权边界。
- UI 共同发布真实执行，而非仅代码路径核实。
- `control_job_id + checkpoint_id` 对应控制目录保存成功。
- 发布后的 RuleSet revision、规则数、workflow stages 和控制目录身份。
- B 至少一个 commit 后 snapshot、处理 revision、OCR/页图 provenance、一个已发布事实及其原件 locator。
- Profile/原件回看能够从已发布事实回到正确 PDF 页。
- A/B 工件版本绑定；后续草稿变化必须重验受影响标准。

## Evidence And Assumptions

### 已核事实

- SQLite 最新草稿是 revision 15：
  - `revision_id=draft-revision:draft:all:15`
  - `created_at=2026-09-18 00:57:17`
  - reason=`source_error_feedback`
- 最新 integrity checkpoint：
  - gate version=`protocol-deconstruction-gate/2026-09-16.3`
  - `publishable=false`
  - blocking issues=5
- 五个 issue 为：
  - `FREQUENCY_SOURCE_FORM_UNVERIFIED`
  - `TIME_ANCHOR_UNRESOLVED`（EX-04）
  - `TIME_ANCHOR_UNRESOLVED`（EX-07x）
  - `OBSERVATION_POLICY_SOURCE_UNVERIFIED`（同时影响 EX-04、EX-15）
  - `PREDICATE_CLAUSE_NOT_IN_SOURCE`（同时影响 IN-06-C2-P1、P2）
- revision 14→15 逐规则 JSON 比较：只有 IN-02 changed；其他 22 条规则均 same。
- `RETURN_A.md` 的首页最终增量仍停留在 28→6/revision 14；revision 15/28→5 只在 conference context、数据库和后续描述中体现，任务 durable handoff 存在滞后。
- `register_interpretation_sources` 会在版本、范围、等待边界通过后更新 source input 并重跑 gate，不会改写协议原文。
- B 正式上传为 preview→commit 两步；commit 创建/复用候选 snapshot 与 processing job。
- MTPLX lifecycle 释放路径有完整记录；kernel 错误也在多个服务日志重复出现。

### 代码证据

- `app/agents/protocol_semantic_transport.py:55-63`：MTPLX alias 集合与 grammar-incompatible 集合不一致。
- `app/agents/protocol_semantic_transport.py:442-455`：grammar-compatible local backend 才发送完整 schema。
- `app/agents/protocol_semantic_transport.py:679-728`：MTPLX 瘦合同入提示词及深度裁剪。
- `app/protocols/deconstruction_gate.py:2142-2188`：频次识别和未锚定回溯判定使用同一 predicate temporal text。
- `app/protocols/deconstruction_gate.py:2278-2302`：频次未识别但存在 occurrence window 时直接报 `FREQUENCY_SOURCE_FORM_UNVERIFIED`。
- `app/protocols/deconstruction_gate.py:2384-2393`：`TIME_ANCHOR_UNRESOLVED` 的阻止逻辑。
- `tests/v2/protocols/test_node_relative_lookback_contract.py:719-727`：无解释来源时不可发布。
- `tests/v2/protocols/test_node_relative_lookback_contract.py:755-765`：合法解释来源闭合后可发布。
- `tests/v2/protocols/test_issue_refinement_counterexamples.py:1-8`：unresolved 可保存但继续阻止发布。
- `app/api/v2/evidence.py:375-412`：preview commit 是 snapshot/job 创建边界。

### 运行证据

- `data_v2/enrollment-review-v2.sqlite3`：revision 15、最新 integrity checkpoint、规则内容和 affected refs。
- `artifacts/mtplx-owned-runtime-20260918/logs/*.lifecycle.jsonl`：装卸与端口释放。
- 多个 `artifacts/mtplx-owned-runtime-20260918/logs/*.log`：反复出现 qsa_prefill Metal JIT 错误。
- `enrollment-9fbfa9749bd44d8a8a07c72f1072bdff.log`：27B Quality 有多次真实 generation，亦显示多轮输出修复，说明“生成成功”与“修订合规成功”必须分开统计。

### 推断

- EX-04 两个 temporal issue 同根，属于工程缺陷：由草稿结构、门禁执行顺序和正则输入共同推断，尚需新增反例测试正式证实。
- EX-04/EX-15 observation selection 是真实操作歧义：依据原文未明确选择/聚合方式推断，仍需医学/方案责任方确认。
- IN-06 可确定性修复：依据 exact source clauses 与 component source excerpts 的直接差异推断。
- 瘦合同绕行“不稳定”：依据多次 kernel 错误和有限成功混合出现推断；尚未完成控制变量重复试验。

## Risks, Gaps, And Verification Needs

1. **最高影响缺陷：EX-04 可能被错误送入解释材料流程。**  
   如果把 frequency denominator 误当回溯锚点，用户可能被要求提供方案原本不需要的筛选/随机锚点，形成新语义而非澄清。

2. **通用降级会破坏现有发布安全合同。**  
   `unresolved_items` 是问题的持久化表达，不是问题已解决的证据。把它作为非阻塞条件会倒置当前设计。

3. **门禁 issue count 不能直接作为临床问题 count。**  
   一个 issue 可影响多个谓词；同一根因也可产生多个 issue。当前“剩余5项”的管理表述会低估 EX-15、重复计算 EX-04。

4. **任务文档已滞后。**  
   `RETURN_A.md` 和 `implement.md` 仍主要写 28→6/revision 14；下一接手者可能错误重跑 IN-02 或误读剩余项。Codex 应在综合后更新 durable checkpoint。

5. **MTPLX 特例存在 alias 漏洞与测试缺口。**  
   `mtplx-api` 可能不走 prompt-contract fallback；当前未见直接测试保障。

6. **kernel 绕行没有稳定性验收。**  
   需要固定模型、固定服务版本、固定请求、多个 prompt-length bucket 重复测试；记录成功、500、耗时与内存释放。

7. **解释来源的权威级别未定义清楚。**  
   需要明确哪些材料可解析方案歧义、谁批准、如何绑定版本；不能让任意用户文本静默成为规则来源。

8. **B 链当前计划遗漏 commit 与冻结/激活状态。**  
   只观察 original-page-images 或 OCR 成功不足以证明事实链已经形成。

9. **实时服务不可用。**  
   本轮只能以 00:57 的最新 SQLite checkpoint 为准。Codex 恢复服务后需用相同 job id 重读 integrity，并核对响应与数据库 hash。

10. **回退模型独立性有限。**  
    本报告不是原定 GLM-5.3-Flash 的意见；若 Codex 认为跨模型独立性是本会商成立条件，应记录为未满足，而不是把 fallback 输出标作原路由结果。

### 给 Codex 的 bounded questions

1. 是否同意先把 EX-04 两个 temporal issue 暂定为“门禁缺陷待反例证实”，停止对它们追加模型调用？
2. EX-07x 目前是否已有正式 Q&A、申办方函件或批准的医学解释材料？若没有，安全路径是保持阻塞，而不是临时降级。
3. live route 是否可能使用 `mtplx-api` alias？若可能，当前 grammar fallback 存在确定性漏口，应在下一次 MTPLX 调用前修复。
4. B 包是否允许在隔离 fixture 上继续工程接线、但把正式 31001 P1 验收保持为等待 A 发布？这是当前最安全的并行方式。
5. 对 observation selection，产品要求是“规则发布前必须完全决定聚合方式”，还是允许发布一个永远只能产生 UNKNOWN/研究者待确认的非执行性规则类别？后者是新产品合同，不能作为本轮小修默认引入。

## Recommended Next Step

建议按以下顺序推进：

1. **冻结当前 revision 15 与 integrity checkpoint**，记录 hash、gate version 和五项 affected refs；更新 `RETURN_A.md`/`implement.md`，避免继续沿用 28→6。
2. **先修 EX-04 门禁识别缺陷**：
   - 增加 `1周≥4天` 精确反例；
   - 修 frequency source verification；
   - 排除同一 occurrence duration 被重复当成 lookback；
   - 重算 integrity。
3. **确定性修复 IN-06**：
   - 为 IN-06b component source excerpts 补入逐字公共时间前缀；
   - 同时验证 C2-P1、C2-P2；
   - 断言仅 IN-06 改变。
4. **重新盘点剩余 issue，而不是机械沿用“5”**：
   - 若 EX-04 temporal 两项消失，剩余应重新按受影响谓词列账。
5. **对真正的未决项走来源通道**：
   - EX-07x 必须取得权威解释来源；
   - EX-04/EX-15 observation selection 分别确认聚合/选择政策；
   - 无来源则继续阻止发布。
6. **不实施通用 unresolved→nonblocking 降级。**
7. **补强 MTPLX transport**：
   - 用显式 capability 替换裸 frozenset；
   - 覆盖 `mtplx`/`mtplx-api`；
   - 增加 prompt-contract/host-validation 测试；
   - 做重复长提示稳定性试验。
8. **A gate 真正清零后执行共同发布**，保存 RuleSet、控制目录、workflow stage 与时间证据。
9. **B 可先做隔离工程接线；正式 P1 顺序使用**：

   `发布 → subject/review episode → upload preview → preview核对 → commit → snapshot/job → original-page-images/v1 → OCR及页级复核 → processing revision冻结 → fact normalization/publication → active snapshot/profile/原件回源`

10. **只有 A 发布证据和 B 至少一条可回源已发布事实齐备后，才启动 C 的真实消费验收。**
