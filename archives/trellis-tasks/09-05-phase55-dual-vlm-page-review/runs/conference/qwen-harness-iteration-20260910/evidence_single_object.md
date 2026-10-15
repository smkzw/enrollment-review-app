证据链已闭合。撰写完整审阅报告。

# 会议输出：qwen-harness-iteration-20260910 - evidence_single_object

## 输出

只读审阅已完成：全部授权冻结证据（5 个产品/脚本文件、medium-protocol-d001 request-4/5 与 response-4/5、low-protocol-sar receipts.json、pause-server-11234.log 定向检索、交接文档）均已核验。以下按 证据 → 推理 → 修复建议 → 单因素验证协议 → 质疑与决策点 → 未验证项 → 有界问题 组织。

### 结论摘要（最高影响发现）

**mlx-serve 26.9.1 上 `strict: true` 的 json_schema 约束解码对本轮全部严格 JSON 请求实质失效（14/14），"两档重复 JSON 语法失效"不是两个独立的档位/模型失败，而是同一个平台级语法掩码失效缺陷的两次表现。** 在此平台上继续用 strict json_schema 跑横评即属用户明令禁止的"已知失败重复运行"。产品侧最小通用修复不是再加修复提示或扩预算，而是：(1) 把结构保证的信任边界移到已存在的本地严格校验，并将"stop+不可解析 JSON"细分为平台结构化输出失败类别；(2) `length` 先判 `completion_tokens` 是否真耗尽预算，非耗尽（平台 repetition_loop 截断）不翻倍、不同上下文重付全额重试。根因（字节级掩码错位 vs 投机解码超前语法状态）日志无法单独裁决，需冻结同源单因素实验的"关闭投机解码"臂裁决——这与已采纳的 MTPLX AR 修复同构。

### 一、证据（Evidence，全部来自冻结工件）

**A. 语法掩码静默失效（grammar disabling mask）——已证实且为全量命中**

- 服务日志单文件 27,522 行 `[grammar] sampled token … produced byte … that was rejected — disabling further mask enforcement`。逐请求统计：日志中 req#73–#112 共 14 个携带 json_schema strict 的方案解构请求（medium、low 两档），**每一个**发生 280–2,674 次掩码失效；无一个严格请求幸免。
- `[qsa-arms]` 计数器显示掩码实际参与度：req#78 `mask=12 decode=46716`、req#112 `mask=12 decode=216120`、req#108 `mask=24 decode=249996`、req#81 `mask=0 decode=111876`——约束解码在这些生成中参与率为 0–13%，其余全部无约束运行。
- 首次触发 token 兼有多字节中文（0xe4/0xe6/0xe7/0xe9 UTF-8 前导字节）**和 ASCII 结构字符**（0x22 `"`、0x61 `a`、0x5f `_`，req#73 首段日志）；一旦失步，后续空格、逗号、换行也被"拒绝"，属语法状态机与实际输出整体失步后的级联，而非单纯中文触发。
- 服务端环境：`mlx-serve 26.9.1 (MLX 0.32.2)`，`pld=on`（prompt-lookup 投机解码）、每请求 `spec-gate: ngram-score` 行、采样 `temp=1.00, top_p=0.95, top_k=20`（平台默认）。语法在推理边界才开始执行（`[grammar] deferring JSON schema until the reasoning boundary`）。

**B. 两档 stop + JSON 语法失效——已证实，且修复轮在相同位置复现**

- medium D001 第 4/12 批：response-4（首轮，`finish=stop`，11279 completion）`json.loads` 失败于第 1 行第 1554 列 `Expecting ',' delimiter`；修复轮 response-5（3892 completion）失败于第 1551 列，**同一上下文、同类错误**。括号栈追踪定位根因：`proposed_rules` 数组第一个元素对象闭合后，模型在语法只允许 `,` 或 `]` 的位置输出了 `}`（多关一层）。在正常工作的严格掩码下该 token 不可能出现——与 A 项掩码失效证据互相印证。产品现有的 `repair_json_quotes` 与 `extract_json_object` 均无法修复此错（已实测：修复后仍失败于同一位置）。
- 修复轮 req#78 `mask=12 decode=46716`：重试几乎全程无约束，87 字符的语法修复提示无法纠正解码层缺陷——同列复现是必然，不是偶发。
- low D001 第 6/12 批两轮 stop 但 JSON 语法错误（3083/5414 列）：交接文档记录；服务日志对应窗口 req#107/108（后者 disable=2585、mask=24/249996）与该失效类别一致（列号本身未在授权清单内复核，见未验证项）。
- low SAR request-0 同为 stop 后进入 json 修复分支：由 receipts（request-1 较 request-0 输入 +1107 token ≈ 回填正文+修复消息）与服务日志 prompt 序列（7413→8520）推断（推理级，见下）。
- medium SAR 第 2/9 批：req#80 stop（17190，disable=1679）→ 修复轮 req#81 length（loop-stop 截断于 9323），完整流程 failed_final——与交接一致。

**C. `length` 非真实预算耗尽——已证实**

- receipts[1]（low SAR request-1）：`requested_output_tokens=131072`、`finish_reason=length`、`completion_tokens=18010`（仅预算 13.7%）。服务日志同 token 数精确对应：`[loop-stop] degenerate tail loop cut after 18010 generated tokens (finish_reason=length details=repetition_loop tier=near_repeat trim_start=16986)`。req#81 的 9323 同类。**平台把重复环截断以 `length` 收尾，`length` 在该平台不等于预算耗尽。**
- 该请求 `first_content_seconds=1723.4 / elapsed=1786.1`：96% 生成发生在思考段，重复环位于思考尾部；服务端先于客户端保护（`repetitive_reasoning_tail` 需 ≥8192 字符尾窗 60% 重复）截断。
- 产品当前行为：传输层 `_complete` 对 length 追加"重新输出完整 JSON"重试一次（同预算、同上下文、历史继续累积）；页读道 `read_page` 更是 `max_tokens *= 2` 盲目翻倍一次（`protocol_semantic_transport.py:466-486`、`page_review_harness.py:589-596`）。暂停信号到达时，request-2（5 条消息、以 length 修复消息收尾）正是在为一次已被平台判为退化的失败重付全额生成（服务端 12026 token 流出后被断开）。
- 成本量化（仅本日志内的结构性失败生成）：req#77 11279 + #78 3892 + #80 17190 + #81 9323 + #112 18010 + #113 12026 ≈ **71,720 completion token** 的本地 GPU 时间花在结构失败的生成与被证明无效的重试上（按日志 4.6–17 tok/s 折算约 70–260 分钟）。

**D. 客户端断开附近服务崩溃（退出 139）——现象证实，根因未闭合**

- 日志终止于 `<- 8590+12026 tokens streamed … [client_disconnect]`，**末尾无 "Shutting down gracefully…" 横幅**；同日志内此前 8 次正常停机均有该横幅。结合交接（session 18531 退出 139、TERM 时 PID 已不存在），服务进程在处理该断开时/后崩解（139=SIGSEGV），无栈迹。
- 同日志内另有 3 次 client_disconnect 终止（req#21、#69 及更早）未导致崩溃——崩溃是断开/取消处理路径中的竞态事件，不是"任何断开必崩"；`[hot-cache] committed … from a cancelled prefill` 等取消路径代码在崩溃窗口运行。

### 二、推理与根因分析（Inference，标注为推理）

1. **掩码失效机理存在两个竞争假设，冻结日志不能单独裁决**：(H1) 字节级语法掩码对多字节 UTF-8 token 的对齐缺陷；(H2) 投机解码（pld/ngram drafter）超前推进语法状态，主模型采样 token 与掩码预期失步。支持 H2 的旁证：首触发含纯 ASCII token（H1 难以单独解释），且 MTPLX 上"AR 模式修复严格 JSON"的已验证先例（投机解码超前语法状态）与本现象同构。A/B 实验的 A1 臂（见第四节）可直接裁决。
2. **同列复现（1554/1551）表明失效是解码层、上下文相关的系统性问题**：两轮独立采样在同一边界（长中文临床串后的数组元素衔接处）踩中同一非法 token。提示层修复（87 字符纠错消息）对解码层缺陷无效——冻结证据里 2/2 次修复重试失败（response-5 同错；req#81 进环）。
3. **low SAR request-0 属 stop+不可解析 JSON 的推断链**：prompt 7413→8520 增量 (+1107) 与"回填正文（receipts[0] 的 3704 completion 含思考，正文约千 token）+修复消息"吻合，且 request-2 以 length 修复消息收尾需要该前置链。未直接读取该 request 文件（不在授权清单），故标注为推理。
4. **在 `length`=重复截断时，产品两条重试路径都在放大成本**：传输层同上下文重试（历史含退化输出，`json-repair` 还会整份回填破损正文），页道翻倍预算。冻结证据中没有任何一次"length 后重试成功"的样本。
5. 修复流为三层堆叠（传输层 2 次 → 批级结构修复 1 次 → 页道格式重读 1 次，`protocol_deconstructor.py:3899-3930/4195-4230`、`page_review_format_repair.py`），每层重发完整提示+累积历史；在掩码失效平台上这三层都是对同一解码层缺陷的无效重复支付。

### 三、最小通用修复建议（Recommendation，均为建议，未改任何代码）

按杠杆排序，全部为平台无关（通用）、不触碰临床内容的改动：

- **R1 把结构保证的信任边界移到本地校验，细分失败类别**。本地已有严格校验（jsonschema/pydantic + wire 校验器），wire schema 在此平台只能当提示不能当保证。产品在 `stop`+不可解析/不合 schema 时，将 `failure_kind` 细分（如 `structured_output_unreliable`/`invalid_json_stop`），与"输出合法但语义错"分开计量。横评契约中"平台结构化输出能力失败"与"模型语义质量失败"分列，避免平台缺陷污染模型质量排名（两者都如实记录，不是掩盖）。
- **R2 `length` 先判真实耗尽再动作**。`usage.completion_tokens`（或字符数下界）接近 `max_tokens` 才算耗尽；远低于预算（如本例 18010/131072）判为 `repetition_cut`：页道不翻倍预算，传输层不同上下文重付全额重试，直接按已存在的重复保护路径显式失败。判别逻辑可用冻结 receipts 做离线单测（无需模型，不需要运行任何本地推理）。
- **R3 平台结构性失败时跳过同上下文修复重试**。冻结证据证明该类重试 2/2 无效且每次重付全额生成（B/C 项）。当失败被分类为解码层/平台结构类时，不再发"请重新输出完整 JSON"轮（它保留退化上下文并再生成一次），直接向调用方抛出带类别的显式失败。这是"最小"且通用的止损；语义层的批级修复（对合法 JSON 的语义问题）保持不变。
- **R4 组装上游缺陷报告包（mlx-serve 26.9.1）**：①语法引擎"reject 后禁用掩码"策略把 strict 静默降级为无约束——正确行为是采样前施加掩码、或显式失败请求、或至少在响应元数据暴露 `mask_disabled`；②多字节/ASCII token 被拒的首发现象与（若 A1 裁决成立）投机解码×语法交互；③客户端断开处理路径的 SIGSEGV（退出 139，无栈迹，需上游复现）。附本日志行号证据（3060 起、14214、30118、末行）。
- **R5 服务崩溃的产品侧缓解**：现有 `resolve_route_model` 预检（模型 ready+vision 声明）已是正确的重启闸门；补充"平台崩溃为已知缺陷"的记录与恢复路径（重启服务、从冻结状态续跑剩余批次），暂停路径尽量在请求间隙断开（不强求，用户暂停权优先）。

### 四、冻结同源单因素验证协议（最小实验，先于任何更大重跑）

**冻结源（不重跑 A0，证据已在）**：medium-protocol-d001 `request-4.json`/`request-5.json`（同列失效对）+ low-protocol-sar `request-0/1`（stop 失效 + 重复截断对）。以字节级 sha256 记录（诊断脚本已有该机制）。

**单因子臂（每次只改一个因子，其余全冻结：messages 字节、max_tokens、reasoning_effort、采样=平台默认、服务版本/模型/量化、本地校验代码不变）**：

| 臂 | 唯一变量 | 裁决目标 |
|---|---|---|
| A0 | 已冻结基线（strict json_schema） | 无需运行 |
| A1 | **关闭投机解码**（服务端 pld/drafter 关闭重启），仍 strict json_schema | 裁决 H2（drafter×语法交互）。与已采纳的 MTPLX AR 修复同构，**优先执行** |
| A2 | `response_format` 改 `{"type":"json_object"}`（同 messages） | 若 A1 无效：裁决"严格语法掩码"因子本身 |
| A3 | 移除 `response_format`（同 messages；**明确标注：compact 提示中此时无正式 schema**） | 仅当 A1、A2 均失败后作为版本化后续，且不得与 A2 并列当同质对照 |

**回答主席挑战题**：`_batch_prompt_payload` 中 `schema_suffix = "" if compact else …`（`protocol_deconstructor.py:1266`）——compact wire 合同下，正式 JSON schema **只存在于 wire 层，提示内只有文本结构合同**（`_COMPACT_WIRE_COMPONENT_CONTRACT`）。因此"去掉 wire schema"后提示中确实没有 schema；A3 与 A2 的差异不止解码方式，还隐含"提示缺 schema"这一第二因子，必须如实标注而非当作纯单因素。

**执行要素**：每臂每请求顺序 2 次；每臂独立 SSD 缓存目录（`semantic_cache_identity` 哈希含 response_format，臂间缓存身份自动隔离；服务端前缀缓存命中数照记，不清他人缓存）；记录 每请求 mask-disable 行数（服务日志）、`[qsa-arms]` mask/decode 计数、本地 jsonschema 校验（对原 wire schema，代码不变）通过率、finish_reason、completion_tokens vs 预算、耗时/tok/s。`clinical_acceptance=false` 全程保持；结构有效性是唯一终点。
**判定与停止标准**：A1 使 mask-disable 归零且本地校验通过 → 根因为投机解码×语法，修复走服务端配置/上游补丁，产品保留 strict；A1 无效而 A2 通过 → 产品对该平台改 json_object+本地严格校验；A1、A2 均无效 → 该平台结构化输出按现状不可用，如实记录进横评，不推 A3 之外的动作，且**不得断言所有平台都能被修可靠**。C 类（重复环）在 A1/A2 上顺带观测：req#112 掩码参与仅 12 次≈本已无约束，故重复环大概率与语法无关、属采样/解码病态（temp=1.0 默认），若各臂均复现则单独立项。
**工具缺口（需授权的小改动，本次未做）**：`scripts/qwen_request_diagnostic.py` 硬编码 `mtplx`/8002 且仅支持 `generation_mode` 干预；需最小扩展 `--provider/--url` 与 `--response-format {strict,json_object,none}`，源请求 hash 与 fresh 输出目录机制已就绪。

### 五、对当前计划的质疑与决策点（Challenges / Decision points）

1. **最高影响缺陷**（摘要已述）：14/14 严格请求掩码失效意味着该平台任何"stop+结构合法"的表象都只是本地校验放行的偶然；继续在此平台用 strict json_schema 重跑横评=已知失败重复，直接违反用户明确的迭代-验证要求。决策点 1：横评在 A1/A2 裁决前是否全面暂停该平台 strict 路径（建议：是，仅跑单因素臂）。
2. **"最小通用修复"的表述挑战**：真正的最小修复是**停止支付已被证明无效的重试**（R2/R3）并**前移信任边界**（R1），而不是新增任何修复提示或预算策略；新增提示类修复在冻结证据中 2/2 无效。
3. 决策点 2：A1 需要重启本地服务关闭 pld（运行动作）；在"不得运行本地模型"的本次会议边界下，A1 属于下一步执行项而非本审阅项，需 Codex 明确排期与授权边界。
4. 决策点 3：横评契约是否接受"平台结构化输出失败"与"模型语义失败"分列（建议分列；两列都如实计数，不互抵、不补写）。
5. D 类崩溃与 A/B 实验解耦：崩溃复现需要受控断开实验，不与单因素臂混跑；在 A1/A2 期间避免人为中途断开（请求间隙暂停），把崩溃风险从验证窗口中剥离。

### 六、边界与未验证项（Uncertainty）

- 退出 139 无栈迹，因果强度仅"时间相邻+日志戛然而止"；不能断言具体缺陷代码位置。
- low D001 3083/5414 列号引自交接文档（原始工件不在授权清单，未复核）；low SAR request-0 的失效类别是推理（第三节推理 3），置信中高但非直接证据。
- 同列复现的精确机理（为何恰在该数组边界）未裁决——属解码层上下文相关失效，留待 A1/A2。
- H1/H2 根因竞争未裁决（A1 的存在理由）；temp=1.0 平台默认与重复环的因果关系仅是假设。
- `repetitive_reasoning_tail` 只查思考不查正文；正文重复无保护（本冻结集内正文重复未出现，属前瞻缺口，建议列为版本化后续而非本次）。
- 未运行任何模型、未修改任何代码、未补写任何临床内容；`runs/conference/…/evidence_single_object.md` 未写入（runner 专属路径）。

### 七、给 Codex 的有界问题

- **Q1**：A1（关闭投机解码+保留 strict）是否授权为下一个执行实验并优先于 A2？理由：它直接裁决根因、与已采纳的 MTPLX AR 先例同构；若先跑 A2 而 A1 未做，"放弃 strict"与"关 drafter"两因素将混淆。安全临时路径：在裁决前，该平台 strict 路径暂停、不再投入横评批次。
- **Q2**：`qwen_request_diagnostic.py` 的最小扩展（provider/url/response_format 参数化）是否作为独立小改动授权？它只影响诊断入口，不触碰产品传输与提示。
- **Q3**：横评契约是否采纳"平台结构化输出失败/模型语义失败"双列记账（决策点 3）？这影响后续所有九组合的排名解释。

（恢复点：若需同会话续问，本报告证据均可回溯——日志行号 3060/14214/30118/末行、medium response-4/5 错误列 1554/1551、receipts[1] 18010/131072、代码位置 `protocol_semantic_transport.py:466-486/392`、`page_review_harness.py:589-596/302-344`、`protocol_deconstructor.py:1266/3899-3930`。输入预算用量低，未触及任何输出限额。）
