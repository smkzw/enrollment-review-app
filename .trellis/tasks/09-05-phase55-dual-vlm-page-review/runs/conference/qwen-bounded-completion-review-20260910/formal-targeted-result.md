全部证据核对完毕。终稿如下。

# Conference Output: qwen-bounded-completion-review-20260910 - evidence_single_object

## Output

续审第十一遍（定向修订独立复核）。边界遵守：只读；未写库、未调模型、未读 reasoning/streams；来源经脚本 `frozen_input`（离线库、拒活动 WAL、sha256 校验、唯一输入）核验为 job `bc103cde…` 的 body.p644 原文，与组件摘录逐字一致。

### 1. 修订质量核验（证据）

**基线（response-3）**：EX-04 仅一个裸 exists 谓词（“严重带状疱疹或严重单纯疱疹既往史”），频次完全缺失、无现病史分支。**本轮**：ANY 四分支——严重带状疱疹既往史 / 严重单纯疱疹既往史 / 复发性带状疱疹发作次数 ≥2次（`occurrence_window{2年, min2}`，subject=复发性带状疱疹）/ 疱疹感染现病史；组件级 `source_span_ids`（正确 p644 id）+ 逐字摘录保留；screening 资料要求措辞无结论性预设。

**真实改进（证据）**：频次既已结构化又**独立成支**——第二遍的组级合取收窄缺陷不存在，播散型单次病史可经头分支触发；复发性定义绑定在正确的子类对象上。这是语义层实质改善，非数字凑对。

**未过（证据）**：**四个谓词全部缺失 `source_clause/source_clauses/source_term`**——形式 pydantic 契约两者皆可选，故可解析，但 (a) 原子级来源绑定/审计链断裂；(b) `_predicate_preserves_frequency`（gate:1092-1114）第一步即要求 `exact_source_clauses` 含频次片段，空子句直接 False——status 的 remaining_issues 正是如此。次要：subject 用疾病名而非“受试者”（建模口径小瑕疵，无临床扭曲）；`replacement_structural_warnings` 缺省（模型有默认，解析通过）。

### 2. gate 笼统报文丢失修订方向（证据→建议）

本轮证明报文误导：窗口**已**结构化且作用域正确，缺的是逐字片段绑定，而 `next_action` 仍说“把周期和阈值绑定到其直接限定的分支”。**最小通用修改（不硬编码疾病/阈值）**：`_predicate_preserves_frequency` 由返回 bool 改为返回原因枚举（`missing_window`/`window_mismatch`/`clause_missing_spec`/`binding_term_absent`），调用方按原因分化为两个 issue 码与对应 next_action——例如“频次窗口已结构化但未逐字绑定原文片段：为该谓词填写 source_clause/source_term”。判定条件全部复用现有 `_source_frequency_specs` 与绑定归一化，零新常量。**附带发现（同源缺陷）**：`frequency_issues` 的 spec 提取依赖**模型自报的** `source_excerpts`（本脚本 37 行、产品 gate 同型）——若模型省略含频次的摘录，spec 为空则检查静默通过；最小加固为从权威 `source_input` 按组件 span_ids 取原文提 spec。

### 3. 脚本 formal 分支忠实度（证据+限度）

忠实点：真实产品 `_repair_prompt(compact=False, include_frozen_context=True)`（含 P0 修复）、真实 transport 与 `_configure_transport_output_scope`、真实 `_parse_semantic_repair`、身份/范围校验、修复后重跑双 gate、`--max-tokens` 与产品 cap 一致性守卫（113-114，正是 request-3 的 8192 教训）、`--prepare-only` 无调用模式、离线库出处链完整。**限度**：单条 `transport.start` 合成会话，非产品中途 `continue_session` 流；无 attempt-2 结构重试、无 `_apply_semantic_repair` 合并/装配/发布门禁——**单条定向重放不等同批次续修或完整验收**；`remaining_issues` 对 replacement 单独评估，不验证其在全草稿中的合并效果。

### 4. 下一步（建议，按优先级）

1. **离线零调用**：实现第 2 节原因分化 + spec 权威来源加固后，用本轮已存 response-0 离线重跑 gate，断言报文变为“已结构化但未绑定”。
2. **单条单变量**：仅替换分化后的 next_action 重发同一定向修订（其余全部不变），判据=至少一个谓词完整通过 `_predicate_preserves_frequency`（片段含 spec+绑定词）且 ANY 结构无回归。
3. **设计注记（不实现）**：形式模式增加“每谓词至少一条非空 exact_source_clauses”的表示层校验。
4. **暂缓**：整份 17 批重跑、跨批次合并验收、任何档位排名。

### 证据局限

单条款、单档位、单运行时、单样本；基线为 8192 预算（不可比 128K，脚本已加守卫）；本复核非临床验收，手写与其余维度未涉。
