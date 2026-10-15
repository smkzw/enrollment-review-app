证据链闭合。整理最终评审结论。

# 会议输出：qwen-bounded-completion-review-20260910 - evidence_single_object

## 输出

续审第三遍（运行时证据审查）。边界遵守：只读；未调用模型/服务、未写文件、未读凭据（`settings.json` 两处均未读）、未读 `reasoning` 字段与 `stream-*.jsonl`；外部仅读授权的三个 oMLX/xgrammar 源文件。

### 核心裁定：既往“严格 grammar 生效”与“已配置思考预算”两项主张均不成立

**1. 严格 grammar 从未生效（证据链完整闭合）。**
- reasoning 运行时配置 `reasoning_parser = "qwen"`（`omlx-diagnostic-runtime-reasoning/model_settings.json`）；xgrammar 注册表只有 `qwen_3 / qwen_3_5 / qwen_3_coder` 等键，**无 `"qwen"`**，且 `get_builtin_structural_tag` 是无别名归一化的直接别名（`builtin_structural_tag.py:1942`）→ 调用必抛 `ValueError: Unknown format type`。
- `server.log` 逐条对上两次新运行：01:27:32 降级警告（strict 未强制、回退 prompt 注入）→ 01:34:36 完成记录（14074 tok / prompt 14261 / 423.02s，**与 open-scope 回执完全一致**）；01:40:07 同样警告 → 01:50:40（21118 tok / 14261 / 633.59s，与 explicit-thinking 回执一致）。该会话内**每一条 json_schema 请求都降级**（另有两更早请求同罚）。
- 因此该运行时上一切“strict grammar”表述（含更早的 strict-scope 类运行）实际都是 prompt 注入 + 无约束解码；open-scope 输出 schema 违规（`unresolved_items` 放错层级）、explicit-thinking 输出根本不可解析（char 1601，finish=stop），均为无约束的直接佐证。

**2. 配置的思考预算是死配置。**
- `_resolve_thinking_budget`（`server.py:1630-1642`）只认：请求级 `thinking_budget` > 模型设置 `thinking_budget_enabled && thinking_budget_tokens`。reasoning 运行时写的每模型字段是裸 `thinking_budget: 131072`——`ModelSettings` 无此字段（`model_settings.py:226-227`），被静默忽略。open-scope 运行时**没有任何思考预算**，思考仅受共享 `max_tokens=131072` 约束（回执：14074 completion tokens 对 4331 字符正文，思考占了大多数）。
- grammar 编译成功时的自动预算 `min(max_tokens//2, 4096)`（`server.py:3850-3858`）在本服务器永不触发（编译必失败）。
- 共享总预算语义获双重确认：usage 把思考+正文计入同一 `completion_tokens` 池；自动预算设计即按 max_tokens 取半。
- explicit-thinking 的请求级 `thinking_budget=131072` 是唯一真正生效的预算变量，但等于全额上限，**不给正文保留任何保证份额**（观测：21118 总 token 中正文仅 1601 字符且畸形、finish=stop、总量远低于 131072——是自停止而非预算耗尽；成因不作推理循环归因，仅记录为未解释观测）。按 Codex 界定：这是“隔离预算变量、保留不支持 parser”的对照实验，**不构成合格基准**——两组均无 enforcement，parser 混杂未消除。

### 新诊断与捕获代码的缺陷（不重构，只列窄项）

- **B1｜警告捕获失灵（最重要）**：服务端日志确证降级发生，客户端回执 `response_format_warning` 却为 `null`（两次均是）。源码该路径确会设置 SSE `Warning` 头（`server.py:3910-3911`）——要么运行版本与所读源在该头存在漂移，要么中间层丢失；`qwen_platform_measurement.py:115` 的捕获**无任何测试**。缺一个 mock Warning 头→回执断言的测试 + 一次 curl 实测仲裁。
- **B2｜文档/注册表漂移**：`model_settings.py` 文档字符串把 `"qwen"` 列为合法 `reasoning_parser` 值，注册表无此键——正是本次死配置的来源（外部项目缺陷，仅记录）。
- **B3｜`_patch_output_format` 失败的静默通道**（`server.py:4271-4277`）：找不到 any_text 槽位时仅记日志、“as-is”编译**不含用户 schema** 且不触发 Warning 头。本次未触发（ValueError 在先），但换用 `qwen_3_5` 后是下一个可预期的静默不强制通道（外部项目缺陷，仅记录）。
- **B4｜诊断工件不记录生效值**：diagnostic.json 只存请求侧意图；建议回执把服务端已解析的 parser 名/预算/降级信号并排落盘，否则每次都要人工拼日志。测试已有 `thinking_budget` 快乐路径与非法拒绝（`test_qwen_request_diagnostic.py:12,80`），缺 B1/B4 对应用例。
- **B5（次要）**：脚本校验 `0 < thinking_budget <= max_tokens` 允许等于上限；若目的在对照，应记录“无预算 vs 全额”这一事实标签。

### 可信基准的最小证据契约

1. **请求与生效并记**：response_format(type,strict)+schema 哈希、请求与**服务端实际解析**的 thinking_budget、parser 名（以服务端日志/状态为准，非配置文件——validated 运行时的 `qwen_3_5`+enabled/tokens 写法正确但**无运行证据，不视为已生效**）、模型回显一致（measurement 已有强校验）。
2. **降级双信号**：Warning 头（修复 B1 后）与服务端 "not enforced" 日志同 request/时间戳对齐；单信号不足。
3. **parser 兼容静态预检**：parser ∈ xgrammar 注册表（可离线断言），避免再花 7–10 分钟跑一次必败请求。
4. **enforcement 正控制**：一个小 schema 的正控请求，证明无效 token 被 logit 层拒绝——这是 grammar 真正激活的唯一直接证明；尤其 `vlm_mtp` 旁路 BatchGenerator 处理器的记载（`model_settings.py:37-51`）意味着 MTP 下 per-request grammar 是否强制**在授权源内无法证实**，必须以正控兜底。
5. **共享预算并记**：max_tokens、thinking_budget、usage 的思考/正文拆分同盘，且要求正文必需时 `thinking_budget < max_tokens`。

### 格式成功 ≠ 临床逻辑完整

本家族证据现在覆盖全阶梯的分离性：可解析 ⊂ schema 合法 ⊂ gate 通过 ⊂ 逻辑正确。open-scope 可解析但 schema 违规；explicit-thinking 不可解析；前两遍已证 schema 合法且 gate 通过仍可犯组级合取错误（EX-04）。任何层级的形式通过都不携带临床结论——`clinical_acceptance:false` 全程标注正确，应继续保持。

### 不确定性

运行版本与所读 server.py 是否完全同构无法从只读位置证明（B1 的两头各有可能）；explicit-thinking 的 1601 字符自停止成因未定（不做循环归因）；MTP+grammar 的引擎内部行为未授权核查；validated 运行时无任何运行工件。以上不影响两条核心裁定。
