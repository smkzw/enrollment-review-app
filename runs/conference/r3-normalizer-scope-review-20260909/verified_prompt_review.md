# 会议输出：r3-normalizer-scope-review-20260909 - evidence_single_object

## 输出

（同会话第三轮：accepted-observation 提示评审。已读 `verified_evidence_prompt.py`、`normalizer_reference_aliases.py` 及其测试、adapter 聚焦测试，并复核当前 `evidence_normalizer.py` 的 builder/runner/hash 与 `page_review_model_input.py` 现状。静态审阅，未运行。）

### 裁决（仅针对隔离真实回放，非正式/临床验收）

**GO，附条件。** 门禁与合规面成立：`verified_scope_prompt` 未被任何 service/api 调用方传入（rg 全库确认），正式作业不启用；builder 对“无 page_review 或无 pending 保全”fail-closed（`evidence_normalizer.py:892-893`，测试覆盖两种非法组合）。别名机制可逆、按类型映射、不改临床文本、未知 ID 仍被来源校验拒绝——owner 的四条声明均与代码一致（展开发生在 parse 入口 1482-1483 行，先于全部未改动的校验器）。但 D1 会直接扭曲回放对修复路径的测量，应在回放前或随回放修复；D3 是可预测的抽取完整性回归点，回放协议须专项查看。

### 缺陷（按重要性，均附最小补救）

**D1（中高）修复路径合同与新提示直接冲突。** `_SCHEMA_REPAIR_CONTRACT` 仍含“若输入有效文本包含明确事实，必须重新阅读原始页文本并恢复对应候选”（`evidence_normalizer.py:415`），verified 模式下修复 prompt 原样复用它；而新合同规定“唯一事实来源是 accepted_observations…OCR侧车…不可用来补充未经双读核实的事实”（`verified_evidence_prompt.py:9-11`）。模型按修复指令从侧车文字恢复的候选会被 `validate_accepted_candidate_sources` 确定性拒绝 → 白耗有界修复轮 → 抬高“需要核对”率，污染回放的核心测量。补救：verified 模式修复 prompt 仅替换该句为“从 accepted_observations 恢复对应候选”（其余逐字对象/持续状态/规范值规则保留）。

**D2（中）signal_conflicts 保全无确定性兜底。** “条款分歧仍为未解决项”目前只靠提示义务（新合同§一与结尾段）；`retained_pending_summary` 保留 signal_conflicts 在模型视图（已核实，仅弹 fact/handwriting conflicts），但模型若漏写，无校验器失败——`validate_output_page_closure` 接受同页任意候选/未解决项闭合。补救（一行级）：在 `_validate_normalizer_semantics` 加检查——凡 `evidence_input.page_review.reconciliations[].signal_conflicts` 非空的页，模型输出须含至少一条该页未解决项，否则失败进修复。回放可先带风险运行，但正式启用前应补。

**D3（中，抽取完整性遗漏——与“不减抽取完整性”的目的相抵）**
- (a) **既往实际用药归档规则丢失**：旧合同明文“原文明确记载既往某次实际给药…即使来自筛选病历对既往史的转述，也必须归入 actual_exposure_fact_refs”；新文“明确已使用、正在使用、已给药或已经生效医嘱”读作现势语境，洗脱期相关的既往用药易漂入 non_exposure。schema 只校验划分闭合，查不出语义错放。
- (b) **换行药名相邻定位还原指令丢失**：确定性机制仍在（`_is_source_backed_cross_locator_span`、`drug_name_split_across_lines` 消解），但新合同只剩“残缺药名保留未解决项”——模型不再被指示做同页相邻定位还原，可预期多余 `medication_name_incomplete` 与漏药。
- (c) 次要：虚词逐字对象示例与 page_only 定位禁用语句从首答合同消失（前者仍存于修复合同，后者由 `validate_accepted_candidate_sources` 对 page_only（localized_text 为空）确定性拒绝兜住）。
回放协议应在 dense 页专项核对 (a)(b) 两类。

**D4（低中）短引用漏入临床文本无确定性拦截。** 别名只在 10 个 `_REFERENCE_FIELDS` 展开；模型把 "@L1" 写进 message/reason/assertion_text/raw_value 会原样进入持久化用户可见内容（别名测试自己展示了 raw_value 保留 "@L1"）。提示有禁令、代码无守卫。补救：展开后扫描文本字段中的别名模式（`^@+[LOR]\d+$`）→ 报错进修复，而非静默通过。

**D5（低，回放审计）** `evidence_normalizer_prompt_template_sha256`（v24，606-617 行）只覆盖旧 `_SYSTEM_CONTRACT`；verified 实际 prompt（新合同+别名头+verified 尾段）不在任何注册哈希内，回执仅记输出哈希。正式作业不受影响（仍走旧合同），但隔离回放应在回执记录 prompt 哈希、`VERIFIED_EVIDENCE_PROMPT_VERSION` 与别名映射身份，符合项目冻结审计惯例。

**D6（登记）** 模型视图标记 `pending_retention.policy="code-retained/v1"` 与作业级 `preserve-pending/v2` 是两套"policy"词汇；实验期可接受，正式启用时应统一或互相引用。

### 与原始边界逐项核对（证据，已核对源码）

接受 facts/handwriting 为唯一事实来源 ✓（且比旧合同更强：旧合同允许 effective_text 驱动候选，新合同将侧车降为仅辅助并有确定性拒绝兜底）；普通 pending 由代码保全 ✓（`retained_pending_summary` 仅留 per-page (kind, review_status) 计数+标记；逐字保留仍由 `pending_retention_items` 承担，未动）；条款分歧仍待解决 ✓（但见 D2）；实际用药 vs 计划 ✓（发放/领取/携回/退回/持有/清单→非暴露；除 D3a 既往实际用药）；时间/事件/记录区分 ✓（就诊/报告/处方/发药/用药/停药不互换、时区规则、context.time_text 需原句支持）；不虚构来源 ✓（不猜页码/定位/日期/署名/单位；药名字段逐字；无法确认来源不生成暴露）；不出入排结论 ✓（开头声明+`_check_forbidden_top_level` 不变）；无项目特异硬编码 ✓（全通用措辞）；零已核实页的逐页闭合 ✓（`page_pending_observations` 一条/页，与我在第一轮建议的最小方案一致，runner 级 `validate_output_page_closure` 仍生效——第一轮 Objection 1 的失败模式已处理）。别名按类型映射不跨类型猜测、前缀防与真实 ID 冲突、确定性排序、payload 不被修改 ✓（三个别名测试+adapter 2133-2160 行往返/未知引用测试与声明一致）。

### 书面判断提案更正（按要求确认）

我第二轮提出的“同页/同对账绑定作为跨节点借用防线的确定性代理”不成立：**同页或同权威元组不是同一临床节点的证明**，不再重复该断言。类型化来源证据与适用性判定仍悬置；通用文档类型不能独立证明书面判断——本提示未声称修复该特性（它只加了守卫句“检测结果不能代替…研究者书面判断，异常箭头不能代替临床意义判断”“来源类型…不靠文档标题单独认定”，是防误用，不是正向路径），此定位准确。

### 回放前置清单（建议）

1. 修 D1（一行句替换）；2. 回放协议专项查看 D3a 既往用药归类与 D3b 换行药名；3. D2/D4 可随回放带上或登记为剩余风险；4. 回执按 D5 记录 prompt/版本/别名映射哈希；5. 112 项聚焦测试通过为 owner 报告，我静态核对了其中别名与 verified 门禁测试的逻辑一致性，未运行。

**不确定性**：未实测模型在修复轮对 D1 冲突指令的实际行为（推断，基于两份合同文本矛盾）；D3 影响程度为基于合同差异的预测，需回放证实；不做全模型横评、不建议重跑全样或更改模型/强度（按指示）。
