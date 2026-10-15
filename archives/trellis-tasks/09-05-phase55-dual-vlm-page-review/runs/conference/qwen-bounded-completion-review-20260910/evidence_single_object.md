All evidence is in hand. The two sent requests are byte-identical (sha256 `be5ea0ec…`), which makes the divergent clinical-warning content between the two runs the decisive finding. Compiling the full conference output now.

# Conference Output: qwen-bounded-completion-review-20260910 - evidence_single_object

## Output

角色：`evidence_single_object`（重要证据审阅，advisory，无最终验收权）。边界遵守情况：只读，无写入、无模型调用、无服务操作；未读取任何 response 的 `reasoning` 字段与 `stream-*.jsonl`；未写 runner 管理的报告路径；除冻结清单外仅读取了 provenance 侧车文件（`diagnostic.json`、`completion_source.json`）与两次补答的 `request-0.json` 哈希比对，用途均在证据链中标明。

### 结论（TLDR）

1. **补答机制本身的保真性成立**：两次 `completed_object.json` 中 `proposed_rules` 与补答源对象逐字节一致，仅新增缺失字段；"禁止改写已有字段”是结构保证（patch schema `additionalProperties:false` + `required`=缺失字段），不是提示词约定。
2. **最高影响缺陷（证据确凿）**：同一条字节级相同的补答请求（sha256 `be5ea0ec…`，两次 `request-0.json` 哈希一致），run-01 返回 1 条 `OCCURRENCE_WINDOW_SCOPE_MISMATCH`（EX-04，p644），run-02 返回空 `structural_warnings`；两个 status.json 均为 `state=completed, original_schema_valid=true`。**schema 有效性完全掩盖了临床警示内容的不稳定**——这正是任务目标里问的问题，答案是：会掩盖，且已有实证。
3. **独立核实：run-01 的警告在临床上是对的，run-02 的沉默是退化**。p644 原文"复发性带状疱疹（2年内发生2次或以上）"中的频率窗只定义"复发性带状疱疹"这一示例分支，而基础响应把 `occurrence_window{2y, min 2}` 挂到了整个"严重带状疱疹或严重单纯疱疹既往史”集合原子上——原运行提示词明文禁止此做法（“频次定义只绑定其直接限定的事件或示例分支，不得套到同一父条款的其他兄弟病史"）。run-02 丢掉的不是一个随机噪声，而是一条正确的缺陷标记。
4. **但"repeat=不稳定"这一归因目前证据不足**：run-02 的 runtime_note 为 "PLD disabled…warm cache"，run-01 无此标注；cached_tokens 4715 vs 8909。两次运行的服务端解码配置可能不同（混淆变量），n=1 且受混杂——不能写成"相同条件下警示不稳定"。

### 证据（按主张分组）

**E1 保真性（sourced fact）**
- `diagnostic-missing-fields-d001-medium-{01,02}/completed_object.json` 与 `diagnostic-schema-prompt-d001-medium-01/response-0.json` 的 `text` 解析后比对：`proposed_rules` 完全相等；差异仅 `structural_warnings`（1 条 vs 0 条）；`wire_version/candidate_id/batch_id/unresolved_items/created_by_agent_call_id` 一致。
- `app/llm/json_missing_fields_repair.py:9-40`：仅当全部错误为顶层 `required` 且缺失字段在 `properties` 有显式契约时才允许补答；嵌套缺失、类型错误一律拒绝；`merge_completion` 先验 patch 再验全量 schema。`tests/v2/llm/test_json_missing_fields_repair.py` 覆盖禁改写、嵌套拒绝、深拷贝无别名。

**E2 警示不稳定 + 掩盖（sourced fact + 独立推断）**
- 两次补答 response `text`（249 vs 108 字符）全文比对其内容即上文差异；`status.json` 双双 `original_schema_valid:true`；`request_sha256` 均为 `be5ea0ec…`。
- 掩盖路径是结构性的：wire 层 `structural_warnings.code` 仅 `{"type":"string","minLength":1}`（`app/agents/protocol_deconstructor.py:811-836`，冻结请求内嵌 schema 同样），空数组恒合法；“不能因字段缺失默认无问题”只存在于 `completion_messages` 的提示词文本（`json_missing_fields_repair.py:29-31`）。
- p644 原文与 EX-04 编码比对（请求末条 user 消息 `source_materials` vs 基础响应）：频率窗作用域扩大（见 TLDR-3）。

**E3 混杂（sourced fact）**
- run-01/02 `diagnostic.json.intervention.runtime_note` 差异如上；`usage.prompt_tokens_details.cached_tokens` 4715 vs 8909；elapsed 60.1s vs 43.7s。

**E4 源→规则保真的其他独立发现（observation/inference）**
- (a) EX-04 五个枚举重症亚型（播散型/泛发型/CNS/眼/复发性带状疱疹）在规则中无任何载体（values 仅 [严重带状疱疹，严重单纯疱疹]）——**两次运行都没报这条**，说明模型自报警示对编码偏差覆盖不全，支持确定性校验优于模型共识。
- (b) EX-05/EX-06 编码忠实：`first_dose_date/before` + `upper_bound{value,unit}` 保留原文单位（符合提示词“不得换算成 *_days"）；住院/静脉与病原体分解、screening+baseline 资料要求均与原文及提示词规则一致。
- (c) 基础响应本身缺 3 个顶层必填字段：注意该次运行的干预是 schema-in-prompt + `json_object`（推断自目录命名与脚本逻辑 `scripts/qwen_request_diagnostic.py:48-53`；该目录 `diagnostic.json` 不在冻结清单内，此归因标注为 inference）——**不是** strict `json_schema` 服务端强制失败的证据，不能据此下“服务端 strict 模式失效”的结论。

**E5 代码审查（observation）**
- `generation_completion.local_early_length`：`type(count) is int` 拒绝 bool（好）也拒绝 float（部分网关发 float → 判为真耗尽 → 多烧一次翻倍重试，方向保守可接受）；`count==0` 判为非 early → 走重试；若本地服务器把隐藏推理耗尽表现为可见 token=0，"reasoning loop"守卫永不触发（uncertainty，需一个实测案例）。守卫排除云厂商、只认 `{mlx-serve,omlx,mtplx}`，与"本地 usage 才可信"的设计一致；transport 用的是 cap 后的 `self._max_tokens`，与实发请求一致。`early_termination` 不吃 fallback_base_url（模型行为而非端点故障，自洽）；identity 哈希记录 endpoint/fallback/prompt_version，可审计。两层测试均在（`test_generation_completion.py`、`test_page_review_harness.py:484`、`test_protocol_benchmark_defaults.py`）；缺 float/0-count 用例（minor）。
- `qwen_request_diagnostic.py`：`completed_object.json` 仅在 `finish_reason==stop` 且 merge 成功时落盘（有测试）；`clinical_acceptance/ranking_eligible=false` 全程标注。**缺口**：status.json 的 `original_schema_valid=true` 无法区分“模型原生完整”与“补答修复后有效”；服务端解码配置只存于自由文本 runtime_note，导致 E3 的混杂无法从工件机器判定。

### 异议与对 Codex 框架的挑战

- **O1**：不要把本对 repeat 记录为“相同条件下警示不稳定”——它 n=1 且 PLD 状态可能不同（E3）。安全表述：“一对在部分解码配置差异下发散的补答重复”。
- **O2**：真正的掩盖风险不在补答合并（合并是对的），而在**空警示数组在全链路恒合法**（补答、修订、全新生成都一样）。若目标是临床警示保真，最小修复位置是确定性警示交叉校验，不是继续加补答管道。
- **O3**：EX-04 亚型枚举丢失两次都未报（E4a），进一步削弱"靠模型自报警示"的路线。

### 建议的最小下一步验证（不集成、不实现）

- **V1 受控重复**：同一记录在案的服务端解码配置（PLD 固定并作为结构化字段写入 intervention）下 ≥5 次同请求补答重放，输出警示集合翻转率与逐项 diff。判停建议：任一翻转即判定警示内容为不稳定信号，须确定性交叉校验兜底。
- **V2 确定性锚点**：本地校验器断言"`occurrence_window` 只能绑定 source_clause 含频率短语（N年内发生N次类）的原子"——可确定性地抓住 EX-04 这类作用域扩大，零模型调用。
- **V3 工件可审计性**：diagnostic status.json 增加 `completion_merged`/`fields_added` 与结构化服务端配置，使“修复出的有效性”在工件层可见。
- **V4**（远期，若考虑产品集成补答）：警示跨重复和解（并集+逐条确认），禁止单次补答定案；修复过的对象永不裸标 `original_schema_valid`。

### 给 Codex 的有界问题

- **Q1**：V1 的 PLD 固定档位取 off（与 run-02 一致）为唯一臂，还是 on/off 双臂？（影响主线程串行资源预算。）
- **Q2**：V2 校验器应作为本任务 diagnostic-only 代码提出，还是挂到 phase-5 candidate gates 待办？（本pass按冻结边界只给标准不动代码。）

### 不确定性登记

schema-prompt 运行的干预归因为推断（E4c）；两次运行 reasoning 内容差异未观测（边界禁读）；PLD 具体语义及其开关归属主线程/共享 gate，本报告只引用 runtime_note 字面；`receipts.json`/`stream-0.jsonl` 未读（清单外且无必要）。以上不影响 E1/E2 的结论。
