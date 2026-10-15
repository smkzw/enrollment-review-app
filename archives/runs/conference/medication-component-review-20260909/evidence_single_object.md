所有证据已收齐。以下为完整审阅报告。

# Conference Output: medication-component-review-20260909 - evidence_single_object

## Output

### 执行核验记录（证据，非推断）

- 通读 `scripts/medication_component_experiment.py`、`scripts/run_medication_component_experiment.py`、`tests/v2/scripts/test_medication_component_experiment.py`、`app/domain/page_normalization.py`，并抽查三个冻结工件目录的全部 `comparisons.json`、`contract.json`、page4 关键 request/bound 文件。
- 聚焦测试：`33 passed in 0.05s`（`-p no:cacheprovider`，未用 `--cache-clear`）。
- 纯检查器不利对复核（无模型调用）：page4 `pair-2-lane-0-bound.json`（f05，main-A，600mg/2025.4.9）对 `pair-3-lane-1-bound.json`（fact-6，main-B，300mg/2025.6.4）→ **dose=conflict（600mg vs 300mg）、administration_date=conflict（2025.4.9 vs 2025.6.4）、drug_name=agree（双侧 complete 且文本一致）、route=agree、administration_count=agree**。差异被完整保留，检查器未因同名而合并事件。
- 双读道独立性：lane-0 = zhipu-coding-plan/glm-5.3-flash/low，lane-1 = google-antigravity/gemini-3.7-flash/high；18 对响应全部 `finish_reason=stop`，无 failure 文件。
- 溯源：两份脚本的 sha256 与三份 `contract.json` 的 `code_sha256` 完全一致（`6f6c07dd…`、`00a9b2da…`）。
- OMP/Hermes：入口依赖链（`run_medication_component_experiment.py` → `app/llm/page_review_harness.py`、`scripts/evaluate_observation_alignment.py`、`app/domain/contracts/page_review.py`）rg 检索无 OMP/Hermes 引用（命中项均为 "completion"/"prompt_version" 的子串）。**新入口无私有运行时依赖，核实通过。**

### 最高影响发现（按严重度排序）

**F1（高）区间拆分守卫漏掉本语料实际使用的主记号“-”。**
`_INTERVAL_MARKS = ("至", "~", "～")`（`scripts/medication_component_experiment.py:45`，检查在 `:235-238`）不含半角连字符。本语料的区间全部用“-”书写：page4 f07 “2025.7.18-2025.7.23”、f15 “2025.6.24-2025.7.8”、page3 f23/f24 “2025.4.5-2025.4.12”。我以构造输入执行验证：单条 `{"value":"2025.7.18-2025.7.23","role":"use_start","precision":"day"}` **通过** `validate_extraction`。本次 15 对中两模型碰巧都正确拆分（见 pair-4-lane-0-bound.json:30-42），工件未受影响，但确定性兜底恰好覆盖不了最可能的真实失败形态。修复不可简单加"-"（ISO 日期 “2025-03-02” 合法含连字符，会误伤）；建议改用“双日期 token + 区间连接符”正则（如 `\d{4}[./年]\d{1,2}(?:[./月]\d{1,2}日?)?\s*[-–—~～至到]\s*\d{1,4}` 一类，日期 token 须含内部分隔符以免把 ISO 分隔符当区间）。

**F2（中高）不可能日期经回退后可得到无标记的 agree。**
`_normalized_component_value`（`scripts/medication_component_experiment.py:272-277`）吞掉 `normalize_scalar` 的 ValueError 回退纯文本比较。执行验证：“2025.4.31” 双侧一致 → times 行 `status=agree`，无任何异常标记。另外部分精度（partial）同值也直接 agree（page4 f09 “2025.04.uk”、page3 “2018.09.uk” vs “2018. 09. uk”，后者靠 `normalize_text` 去空白后相等）。建议：时间值形似日期但无法构造合法日期时，比较行降级为 unresolved 或附 `invalid_date` 标记（语义选择见决策点 Q1）。

**F3（中）模型漏提在文日期时，验证层完全不可见。**
page4 f11 lane-0 的 excerpt 为 “2023.UK.UK使用瑞舒伐他汀钙片，10mg，一日一次口服治疗，持续”（request 内 `source_record` 可见），日期明明在文，但该侧输出 `times=[]`，比较仅显示单侧 missing（comparisons.json:463-474）。“excerpt 含日期 token 而 times 为空”与“excerpt 本无日期”在现有输出中不可区分。建议加**提示级**（非拒绝、不改 status）QC 标记如 `possible_unextracted_time`：excerpt/raw_value 命中日期样正则（含 UK/uk 占位与区间）而 times 为空时触发——必须是提示，因为日期 token 可能属于摘录内的邻药行。

**F4（中，已知边界的实证）子串绑定只证出处、不证归属。**
模块 docstring（`:7-9`）与测试 `test_adjacent_drug_substring_is_only_bound_not_clinically_accepted`（tests:108-119）已声明。真实语料存在多事件摘录：page4 `clause_signals` EX-06:08 的 span 用“；”串起三次注射事件；且同页存在同名药两条（f05/f06 司普奇拜单抗注射液 600mg/300mg）——这正是邻药错配的活体形态。本次各观察摘录恰好单事件，未发生错配，但若摘录更宽，错行引用可过绑定甚至跨读道“agree”。最小修复：比较层对同页同名药对附 `same_page_duplicate_drug: true` 提示（纯确定性，无模型调用）。

**F5（中低）配对身份是操作者供给的，比较层不设防。**
`--pair` 由人给（run 脚本 `:47-56`），`check_pairs(Proposal(pairs=[]), …)` 只校验页身份与读道（evaluate_observation_alignment.py:106-113），其事实级身份核验（field_name/target_text/time_text/polarity，`:115-143`）对本实验被跳过。不利对证明：药名 complete+complete+agree 不蕴含同一给药事件；错配只表现为 dose/date conflict，与真实转写分歧不可区分。可选最小修复：drug_name agree（双 complete）且 ≥2 个其他组件 conflict 时附 `pairing_suspect` 提示。

**F6（低）上游截断标记在 v2 层丢失。**
page3 f24 lane-0 的 `context.target_text` 为 “〔文本截断，起始为孟〕”（frozen reader 自己标注的截断），excerpt 只有单字“孟”；两侧 fragment/fragment → unresolved 正确。但 context 不进入 `BoundComponentExtraction`/comparisons，下游只见 unresolved 不见原因。可选：将本观察自身的 `context.target_text`/`time_text` 原样带入 bound 记录供 QC 展示（是本观察冻结数据，无跨观察风险）。

### 指定检查项逐项回答

- **药名/剂型忠实性**：机制正确——fragment 等文本一致只给 unresolved（`:291-295`，实测 page4 f03 “鲁司特钠片”、page3 f24 “孟”）。但 value 只须是 quote 的子串（`:224-225` 单向包含），page4 f07 lane-0 的 quote 为 “使用吸入布地奈德混悬液吸入治疗” 而 value 丢掉“吸入”前缀仍过验证并自称 complete（pair-4-lane-0-bound.json:13-17）——completeness 纯属模型断言，双侧 complete 也会 conflict，与 docstring 声明一致。
- **剂量单位**：不换算、不丢弃——"1g vs 1000mg"→conflict、"100mg vs 100 mg"→agree、“适量”逐字保留（tests:160-170；page4 pair-8）。注：普通 "mg" 不在 `_UNIT_RX`（page_normalization.py:12-17），剂量等价性靠归一化文本相等达成，效果保守正确；“100.0mg vs 100mg” 会 conflict，属可接受保守，建议测试固化意图。
- **次数 vs 每日频率**：分离正确——f04/f05/f06 的 “一次” 进 administration_count、frequency 为 null；f09/f11/f13 的 “一日三次/一日一次” 进 frequency（comparisons 全部一致）。但无确定性守卫拦截 “一日一次” 落入 administration_count，可加廉价正则拒绝（与提示词 “不写入 frequency” 对齐）。
- **多角色部分日期与缺失日期**：角色分行、单侧不借值（f11）、角色错位成两行 missing（f13 “2024.08.uk” unclear vs use_start）、partial 逐字保留、unclear 角色/精度只给 unresolved——全部实测/测试覆盖（tests:122-143, 332-349, 413-443）。
- **同读道排除**：比较层三重拒绝（同页身份/同读道/同审核记录，`:331-336`；tests:504-532），运行层另拒同 provider+model 双读道（run `:59-60`）。核实通过。
- **源引用与邻药所有权**：见 F4；绑定+unresolved+source_qc_required 的三段式是当前正确终点。
- **无跨页自动补全**：核实通过——prompt 只含本观察（tests:464-485 实测断言无他读道文本），绑定只对本 excerpt/raw_value，比较强制同页身份。page0 完整的 “孟鲁司特钠片” 从未渗入 page4 的 “鲁司特钠片” fragment。
- **数据形状/提示词系统性信息损失**：**是，但损失发生在上游冻结读道层，不在 v2 层**。上游损失实证：(1) 药名截断（“鲁司特钠片”/“孟”，后者带 reader 自标注）；(2) "UK/uk" 未知日占位符内嵌时间文本；(3) lane-B 日期内插空格（“2025. 4. 5”）；(4) 药名常不在 raw_value、只在 excerpt/context。v2 层逐字保留且比较只做 NFKC/空白/大小写归一，无新增损失；唯一 v2 层损失是 F6（截断标记不随行）。“逐字照抄”无法找回冻结片段本无的信息——这正是不利对/fragment 必须终局于页面图像源核对（Codex）的原因。
- **不利对复核**：已执行（见上），差异完整保留；该对比同时证明 drug_name agree 不携带事件身份信息。
- **双模型 complete 不足为据**：三重实证——(a) f07 双 complete 却文本不同（conflict）；(b) 不利对双 complete 同文本但剂量/日期证明是两个事件；(c) 邻药场景下两模型可引用同一邻行文本并“agree”。双 complete 一致至多是“两个模型对同一冻结片段做出了相同断言”，不能证明行归属、片段对页面图像的保真、或事件同一性。`source_qc_required=true` 必须保持为终局门。

### 下一步最小修订（按序，非新框架；均限于 `medication_component_experiment.py` 数行级改动）

1. F1 区间守卫改双日期正则（含 `-–—~～至到`，ISO 安全）。
2. F2 形似日期不可构造时比较行降级/标记。
3. F3 `possible_unextracted_time` 提示级标记。
4. F4 `same_page_duplicate_drug` 提示级标记。
5. （可选）administration_count 含每日频率样式的确定性拒绝；F6 context 随行。

### 扩测测试标准（具体）

- 单条 "2025.7.18-2025.7.23"（use_start）被拒；单条 ISO "2025-03-02" 不被误拒；“2025-03-02至2025-03-15” 被拒（现测试只用 “至”+点分，tests:399-403）。
- "2025.4.31"/"2025.02.30"/"2023.13.01" 双侧一致不得为无标记 agree。
- excerpt 含 “2023.UK.UK” 而 times=[] → 出 `possible_unextracted_time`；无日期摘录不出；该提示永不改变 status（用 f11 形状回溯夹具）。
- 同页同名药两对 → `same_page_duplicate_drug: true`；唯一名页无标记。
- 不利对回溯夹具（page4 f05/fact-6 形状）：断言 dose conflict + administration_date conflict + drug_name agree——锁定“差异保留”属性。
- administration_count 写入 “一日一次”/“qd” → 拒绝。
- “100.0mg vs 100mg” → conflict，注释性断言固化保守意图。
- f13 形状（同值异角色）→ 恰两行 missing（现有单测已覆盖，补真实语料变体）。

### 决策点与有界问题（致 Codex）

- **Q1（F2 语义）**：不可能日期双侧一致，建议**降级 unresolved 并附原因**（与 fragment 等文本只给 unresolved 的既有保守惯例一致），而非 agree+标记。请确认；若选 agree+标记请说明下游消费方。
- **Q2（F1 严格度）**：连字符区间建议与 “至” 同为严格拒绝（现语义）。请确认正则边界（是否覆盖 “到”、无年份短形式如 “7.18-7.23”）。
- **Q3（F6 范围）**：将本观察 `context.target_text/time_text` 带入 bound 记录是否属于本实验授权范围，还是留给后续正式 facts 契约？

### 不确定性与未核验项

- 未查看任何页面图像；所有“残缺/截断/UK 占位”判断均以冻结 reader 片段为源，页面图像级真值核对属 Codex。药名 “鲁司特钠片” 高度疑似 “孟鲁司特钠片” 截断（page0 有完整名对照），此为推断非源结论。
- lane-B request 负载仅抽查（pair-2-lane-1 等经 comparisons/bound 交叉印证），未逐字通读全部 18 份。
- 本次 15 对中两模型均正确拆分区间，F1 为构造输入证实的守卫缺口而非已发生的工件缺陷。
