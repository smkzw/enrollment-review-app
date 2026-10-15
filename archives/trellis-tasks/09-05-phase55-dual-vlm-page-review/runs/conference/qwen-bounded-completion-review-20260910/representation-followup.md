All evidence is gathered and verified. The final synthesis follows.

# Conference Output: qwen-bounded-completion-review-20260910 - evidence_single_object

## Output

续审（同会话第二遍）。边界遵守：只读；无模型/服务调用、无写入、无凭据；未读任何 `reasoning`/`stream-*`；新增读取均在新授权清单内（provenance 侧车与哈希比对用途已注明）；本遍在内存中用产品 gate helper 重放了两份草稿（`.venv/bin/python`，无副作用），属诊断评估、非产品路径。

### 核心结论（对 Codex 问题的直接回答）

**Q：最终修复的逻辑作用域是否正确？——不正确，且方向危险。** 最终修复（`diagnostic-product-semantic-repair-d001-medium-01/response-0.json`，finish=stop，`schema_valid:true`）把 EX-04 编成两个替代组：

- group[0]（ALL）：`既往史`存在原子（头谓词"有严重带状疱疹或严重单纯疱疹既往史"）**∧** `复发次数`≥2次/window 2y（source_term 复发性带状疱疹）**∧** `带状疱疹亚型 ∈ {播散型,泛发型,CNS,眼,复发性}`
- group[1]（ALL）：`感染现病史` ∧ `感染类型 ∈ {单纯疱疹,带状疱疹}`

原文语义是"[严重带状疱疹或严重单纯疱疹既往史（括注内为非穷尾示例，复发性=2y≥2次为其定义）] 或 [现病史]"。修复把**定义性括注内容提升为头谓词的必要合取项**：仅患一次播散型带状疱疹（无复发次数记录）的受试者不满足 `复发次数≥2`，group[0] 不触发 → **排除标准漏触发（假阴性），不可入组者可能被入组**——本域最高严重度错误方向。同时 `包括但不限于`（非穷举）被变成穷举 membership 合取（`亚型∈{5}`），双重收窄。

**Q：wire 表示/提示词是否在混合“解释性子类定义”与“必要触发条件”？——是，且已双向实证：**

1. 初稿（schema-prompt 响应）：定义的 occurrence_window 挂到上位头谓词集合原子 → 定义被上扩为必要条件（原子级错误挂载）；
2. 再生稿（repaired-completion 的 completed_object，sha `d168c5…` 已验证为语义修复的 candidate）：occurrence_window 全空 → 定义整体丢失（gate 以 `FREQUENCY_WINDOW_NOT_STRUCTURED` 正确拦截，我在本地重放 gate helper 复现：pre-repair 不通过 / final 通过）；
3. 最终修复：原子级挂载正确（source_term=复发性带状疱疹），但被放进与头谓词同一 ALL 组 → 组级合取错误，**gate 通过而逻辑错误**（同样本地重放证实，通过原子为 `复发次数|term=复发性带状疱疹|win=2year|val=2次`）。

根因是表示层的：**扁平 DNF 里组内原子一律是必要条件，没有“非触发定义”的槽位**。`rules.py:222-234` 已有半个概念——`occurrence_window.minimum_count` 无计数值时被接受为“括号定义的最小次数”（nested_definition 形式，初稿误用、终稿弃用）——但没有任何组级作用域约束，提示词只约束原子级挂载（“只能附着于该子类的谓词”，`protocol_deconstructor.py:272-278`），模型满足其字面而违反其精神（“不能把示例的频次变成上位条件的必要条件”同在 275 行，组级无对应可判定规则）。`_repair_prompt` 的 next_action（“绑定到其直接限定的事件或示例分支，不得套到无关兄弟分支”）同样只到原子级，缺“不得与上位头谓词同组合取”一句。

### 窄推荐（Option A：保留 DNF，修组级边界；零 schema 变更）

**表示/提示词修正（一句话规则）**：由 包括/包括但不限于/例如/如 引出的定义性括注，其内部条件只能（i）与括注 governing 头词自成一个**替代组**（组内可合取，如 {复发性带状疱疹存在 ∧ 复发次数≥2次@2y} 单独成组——对“示例型”定义是语义冗余但无害的替代路径，且满足频率 gate），或（ii）保持为上位谓词 source 文本内的匹配参考；**绝不可与上位头谓词同组合取，括注清单不得转成穷举 membership 合取**。

**确定性 harness 修正（通用、源绑定、无疾病/数字硬编码）**：括注作用域 gate——对组内每个原子，取其 exact source clause 在组件摘录中的位置；用括号匹配+引入词（包括/例如/如/即）识别“定义性括号链”；若某原子的 clause 含频率 spec（复用 `_source_frequency_specs`，本身已是通用正则）而同组其他原子的 clause 位于该原子所属括号链之外 → 报 `FREQUENCY_WINDOW_SCOPE`（沿用现有 `_issue` 结构）。本反例即被抓获：`复发次数` 的 clause 在内层括号链 `复发性带状疱疹（2年内…）` 内，同组 `既往史` clause 在链外。正确编码（定义自成一组）不受影响。

**源绑定负向测试（Codex 所问）**：合成夹具条款取泛化形状 `HEAD（包括但不限于 A、B、C（N单位内发生M次或以上））或 CURRENT`（合成词项，非真实疾病/数字），断言编译后规则的四类行为：仅 HEAD 事实（无复发）必须触发；仅 C-定义事实必须触发；仅 CURRENT 必须触发；皆无不得触发。这是行为锚点，不依赖字符串结构启发。注：本遍未读 `app/domain/expression.py`（不在授权清单），若求值器接口不适配，可先落括注作用域 gate + 结构断言，行为测试进 phase-5。

**修复管线的最小触及排序（新增，串起两段诊断）**：本次链路里 schema 整批再生（scope-schema-repair，全批重写）导致 EX-05/06 同胞漂移——EX-05 的集合值变成 `严重细菌感染/严重真菌感染/严重病毒感染`、EX-06 变成 `细菌感染/…`，均非原文连续片段（原文“严重细菌、真菌或病毒感染史”），违反 system contract 的 verbatim-values 规则，fact_type 也从 `medical_history` 漂移为自造类型；只有 targeted replacement 路径保同胞。而触发整批再生的原因恰是顶层字段缺失导致草稿不可解析。**建议顺序：先做有界补答（使草稿可解析），再走 targeted replacement**——补答工具已经存在且本遍证明其保真。这直接回答“是否应向语义模型请求有界作用域理由”：请求，但以**结构化输出**形式（每个替代组申报 governing source span，逐原子 clause 须为其子串、span 须为摘录子串），使其可被机器核查并进入审计链；局限：模型申报可错可谎，行为负向测试仍是锚，申报是审计面不是证明。

### DNF vs 独立非触发定义（Option B）评估

- **B 的收益**：语义诚实，一次性解决全部定义性括注（频率、严重度释义、单位注释）的归属；gate 可断言“每个定义性括注都有定义条目、触发树内无括注内文本被引为必要条件”。
- **B 的迁移面**：wire schema + `rules.py` 域模型 + `_parse_wire_semantic_candidate/repair` 解析 + system contract + gate 新增完整性检查 + 确定性装配/发布 + 事实匹配消费方（示例/同义扩展消费定义——当前不存在该路径）+ 测试全集。跨层契约变更，应入 phase-5 authority-contracts 设计轨道，单独设计与会议。
- **B 的新风险**：定义区成为反向泄漏通道（模型把真实必要条件藏进定义以绕 gate），需要自己的完整性 gate——同型问题上移一层。
- **裁定**：现在做 A（提示词一句 + 括注作用域 gate + 负向测试，消费方零迁移，仅需 prompt 版本升级与审计哈希更新）；B 记为 phase-5 候选并附泄漏风险注记。

### 接受 Codex 更正与既有结论状态

- 撤回我第一遍 V1 的“≥5 次重复”要求：单个已核实反例（最终修复 group[0]）即足以要求 gate 修正；重复重放仅留作可选的翻转率估计。
- 第一遍的 PLD 混杂在新增运行中已消除（四条 runtime_note 均"Same server 78116; PLD off"，cache 差异不影响本遍结论；prefix cache 仅计延迟面）。
- V3 已被采纳且生效：repaired-completion 的 status.json 现记录 `completion_merged:true / fields_added:[…] / semantic_verification:"not_performed"`，审计面成立。
- 顶层字段缺失在本语料为系统性（json_object 下 4/4 次省略三字段：schema-prompt、scope-contract、scope-schema-repair 及其补答源），补答路径在诊断层仍是承重件；`original_schema_valid:true` 现可与 `completion_merged` 区分，掩盖面已收窄。

### 给 Codex 的有界问题

- **Q1**：`diagnostic-scope-schema-repair` 的整批再生是否镜像产品 `_repair_prompt(parsed_draft_available=False)` 回退路径（我从 repair_source 的 validator_errors 与策略名推断，未逐行追产品调用方）？若是，“补答先行→targeted 修复”应作为管线顺序要求写入候选方案。
- **Q2**：括注作用域 gate 与负向测试落在本次任务的 diagnostic 清单，还是挂 phase-5 candidate gates 待办（与第一遍 Q2 合并等待裁定）？

### 不确定性登记

最终修复未在产品上下文经 `_apply_semantic_repair` 实际合并（我的合并模拟仅内存评估）；`app/domain/expression.py` 未读（授权外），行为测试的求值器接口未核实；`_predicate_preserves_frequency` 的两种通过形态（direct-count / minimum_count）在 gate 中等价，本遍未穷举其对其他括注形态的假阳性。以上不影响核心结论：**gate 验证的是存在性，不是逻辑位置；本反例已证明二者可分离。**
