证据链已闭合。所有只读检查完成：未运行任何模型请求、未读取密钥、未修改文件、冻结推理仅做聚合计数未外泄原文。现在出具本角色的完整会议报告。

---

# Conference Output: qwen-harness-diagnostic-review-20260909 - evidence_single_object

## Output

### 一、总裁决：三类归因的证据等级

| 归因类别 | 裁决 | 关键证据 |
|---|---|---|
| 已证实配置缺陷 | **成立**（已在工作区修复，遗留一处文档矛盾） | git diff（index→worktree）+ request-2.json 请求体 + `qwen_protocol_measurement.py:59` |
| 重复生成 | **成立**（成本重复，但全部显式失败，无静默污染） | request-3 与 request-2 sha256 完全相同；oMLX 131072 token 重复循环 |
| 平台故障 | **未证实**（两次失败均无受控 A/B 对照） | mtplx 32 分钟流中断 + Errno 61；oMLX 重复循环——原因均不能排除采样默认值/配置因素 |

### 二、三个指定审查问题的结论

**Q1：sampling-default 开关是否会禁用兼容性保障？——会（修复前已实际发生，工作区已修复，但测试 docstring 仍有矛盾）**

证据链（全部为观察，非推断）：
- 暂存版（index）`app/agents/protocol_semantic_transport.py` MTPLX 分支中，`kwargs["extra_body"] = {"generation_mode": "ar"}` 位于 `if not self._provider_defaults:` 块内——即 `provider_defaults=True` 会同时去掉 `temperature=0.0` 和 AR 保障。
- 横评入口 `scripts/qwen_protocol_measurement.py:59,63` 固定传 `provider_defaults=True`，因此**横评的每一次 mtplx 请求都在严格 json_schema 下运行平台默认投机解码**。
- 冻结请求体证实缺陷实际生效：`artifacts/qwen-three-platform-20260908/mtplx/medium-protocol-d001/measurements/request-2.json` 顶层仅有 `model/messages/max_tokens/reasoning_effort/stream/stream_options/response_format`（json_schema strict=true），**无 `generation_mode`、无 `temperature`**。
- 工作区修复（未暂存 diff）将 AR 提出到开关外并更新了类内注释；`tests/v2/agents/test_protocol_benchmark_defaults.py:163` 的断言 `mtplx["extra_body"] == {"generation_mode": "ar"}`（provider_defaults=True 下）与修复后代码一致。

**最高优先级缺陷（我主动发现的遗留问题）**：同一测试文件 docstring 第 9–12 行仍写着"`provider_defaults` 可选开关：仅去掉产品侧 temperature **与 MTPLX generation_mode=ar 覆盖**”——与它自己的第 163 行断言及修复后代码直接矛盾。这份 docstring 描述的是修复前的错误语义；任何按文档“复原”的人都会重新引入缺陷。**最小修复：改一行 docstring 为“仅去掉产品侧 temperature；generation_mode=ar 为严格 Schema 兼容保障，不受该开关影响”**，并加一条断言 AR 在两种开关下都存在的参数化用例（现有两条用例其实已覆盖，docstring 是唯一残留）。

**Q2：最小 AR 修复是否保持缓存身份？——产品路径逐字节保持，横评路径正确轮换，无跨身份复用风险**

`semantic_cache_identity()`（`protocol_semantic_transport.py:324-346`）哈希 `_completion_kwargs` 的返回（仅弹掉 messages）。对比修复前后：
- 产品默认路径（`provider_defaults=False`）：修复前后 kwargs 均为 `temperature=0.0 + extra_body={"generation_mode":"ar"}`，**完全相同 → 缓存身份逐字节保持**，既有 semantic-batch 缓存条目（键构造见 `app/agents/protocol_deconstructor.py:3686-3718`，包含 transport 身份 + prompt + batch_id + rule_codes + protocol sha）继续有效。
- 横评路径（`provider_defaults=True`）：请求契约真实变化（新增 extra_body），身份应当且确实改变——这正是防止把修复前 mtp 生成的缓存段错误复用为修复后结果的必要行为；`test_provider_defaults_changes_semantic_cache_identity`（测试第 180–188 行）与该语义一致。
- 交叉路径：legacy 与 platform 身份在修复前后均不相交（temperature 差异 + extra_body 差异），无碰撞面。

**Q3：全页格式修复是否会改动有效事实？——存在结构性残留风险（有界的真实风险，需要最小补救）**

`app/llm/page_review_format_repair.py` 的修复是**整页重生成**：原始完整提示 + 一条含校验错误与不可信上一回答的纠正消息（`build_format_repair_messages`），第二次回答整体替换第一次（`page_review_harness.py:607-621`）。已存在的确定性防护：仅一次重读（`format_repair_used`）、日期/数值歧义不可修直接失败（`page_review_format_repair.py:107-113`）、非 `stop` 硬失败、同一模型/原图/ClausePack、同一严格合同复检。残留风险有两个，且都只有提示词级约束：
1. **静默漂移**：第一次回答中本已合法的事实（仅格式字段出错）在第二次整体重生成后可能被改写或丢失，第二次通过校验即被整体采纳，无任何结构化比对。
2. **锚定**：不可信的完整上一回答被嵌入纠正消息，模型可能复制其内容错误（要求"不得原样复制"仅是提示约束）。

**最小可测补救（非重写）**：修复成功后，以 `normalization_key` 为键，对第一次回答中 Schema 合法的 facts/handwriting 项与第二次做确定性一致性比对；若 previously-valid 项的 `raw_value`/normalized 值/原文摘录发生变化或消失，在页记录上附加 `format_repair_drift` 标记供人工复核（符合“应用不是最终入组决定权威”的边界）。该检查纯离线、可用固定的一对尝试载荷做单元测试，不触碰线上契约与修复提示。

### 三、重复生成与平台故障的区分证据

**mtplx medium-protocol-d001（运行 `failed_final`，`claims_complete=false`，route_audit `cache_hits=0`）**：
- 批次 1/12：call 0（4544 prompt，stop）→ 语义修复 call 1（8601 prompt，cached 4544，stop，37s）——常规修复，非异常。
- 批次 2/12：会话压缩后（history-000 三条消息 `[user 143字, assistant 14字, user 10712字]`，assistant 14 字恰为压缩锚定回执），call 2 流式 **1934 秒（约32分钟）后 `RemoteProtocolError`**，http 200，finish=null，usage 空；内容本身无重复（162 个 40 字符 shingle 中 159 个去重），10144 个流事件中约 8164 个为无载荷 keep-alive，正文速率约 3.4 字符/秒——**流近停滞后断开**。
- call 3（request-3.json）与 request-2.json **sha256 完全相同**（`01d66538…`）——`RemoteProtocolError ⊂ httpx.TransportError` 落入 `_send_completion` 的瞬态重试，同载荷重发；**无 response-3.json**（测量器在 `try` 前保存请求、receipt 只在流式 try 的 finally 写出，故 try 前失败或进程被杀都留下无收据请求）。route_audit 记录随后 `<urlopen error [Errno 61] Connection refused>`——本地平台在流中断后已不可达。
- **归因边界**：流中断的直接原因是平台侧连接断开（已观察），但**根因未证实**——无法排除 32 分钟停滞与 mtp/严格 Schema 组合、平台重启等因素的关联；ar/mtp 配对诊断输出存在于 `diagnostic-ar-d001-medium-20260909`、`diagnostic-ar-sar-low-20260909`，按边界我未读取，是 Codex 的指定后续证据。

**omlx xhigh-sar-18（`state: failed`）**：
- 请求体**无 `response_format`**（自由 JSON）、无 temperature/generation_mode、effort=xhigh、多模态页图——与 mtplx 的严格 Schema 路径**不同因**。
- `finish_reason=length`，completion_tokens 恰为 131072 上限，2793 秒（约46.5分钟），268168 字符中 40 字符 shingle 仅 930/6704 去重（重复率约 86%，单一片段重复 103 次）；流中 18343 个 reasoning 载荷增量 + **仅 1 个 content 增量**，且 `text == reasoning` 逐字节相同、first_content_seconds≈总时长——平台在结尾把积累的推理整体镜像为单块正文。真实 JSON 正文从未产生。
- 失败被安全拦截：harness 按 length 加倍预算 → 测量器授权上限守卫（`qwen_platform_measurement.py:64-65`）以 "Requested retry exceeds the authorized output ceiling" 显式失败。**归因边界**：重复循环与“平台默认采样（未固定 temperature=0.0）+ xhigh + 开放式生成”的组态相关，但**平台缺陷未证实**——需要 temperature 受控 A/B 才能定责。冻结推理内容我只做了聚合计数，未在报告中复现任何原文。

### 四、给 Codex 的异议、决策点与有界问题

1. **（决策点）测试 docstring 矛盾必须随本修复一并修订**（见 Q1）。安全临时路径：以代码 + 第 163 行断言为权威，不要按 docstring 重新门控 AR。
2. **（有界问题）**`diagnostic-ar-*` 两个目录是否已产出完整的 ar/mtp 配对结论？若未完成，则“投机解码越过语法状态”目前只有代码注释级主张，最终归因表述应拆为“已证实：开关旁路了兼容保障（配置缺陷）”与“待证：mtp 与严格 Schema 失败的因果（平台行为）”。这直接决定“平台故障”一类能否写入结论。安全临时路径：按未证实表述。
3. **（异议/最小补救）测量记账缺口**：`MeasuredCompletion` 在 try 外保存请求体（tokenizer/idle-wait/连接失败都不留 receipt），request-3 这种“有请求无收据”的样本在事后审计中无法区分进程被杀与 try 前失败。最小修复：把保存后全部步骤纳入 try/finally，或在保存后立即写最小 `state` 标记。不影响线上契约。
4. **（观察，供产品决策，非本修复必需）**传输层对 `RemoteProtocolError` 的同载荷重试意味着最坏 3×32 分钟的重复生成成本；若流中断发生在大量生成已耗时后，可考虑超过耗时阈值时按 TRANSPORT_TIMEOUT 类终态上浮而非盲目重试。属产品语义变更，需 Codex 决定，不纳入最小修复。
5. **（小项）**receipt 的 `sampling` 字段是硬编码字符串 "platform defaults; no sampling overrides"；当前两次运行（meter 从不加 temperature）下准确，但若未来有人经此测量器跑 `provider_defaults=False` 会失真。最小修复：由 request_options 实际内容生成该字段。

### 五、证据/推断/建议/不确定性分离声明

- **观察**：本节所有文件引用、git diff、sha256 相等关系、流事件计数、shingle 去重率、usage/finish 字段、route_audit 与 status.json 内容。
- **推断**（已在文中标注）：request-3 为传输层瞬态重试的产物（同 sha + RemoteProtocolError 属 TransportError 族）；history-000 的 14 字 assistant 为压缩锚定回执；oMLX 尾部单块 content 为平台镜像行为。
- **建议**：docstring 修订、`format_repair_drift` 一致性比对、测量器 receipt 覆盖范围修复（均为最小、可离线单测）。
- **不确定性**：mtplx 流中断与 oMLX 重复循环的平台级根因均未证实；call 3 的终态（被杀 vs try 前失败）在现有工件下不可判定；`diagnostic-ar-*` 结果未读（边界排除）。

**给 Codex 的有界问题（重述）**：请确认 (a) `diagnostic-ar-*` 配对结论是否可作为 mtp→Schema 失败的归因依据；(b) 测试 docstring 按“AR 无条件”修订是否获批。两项都不阻塞 AR 修复本身的采纳——其正确性由代码级证据独立成立。

未运行任何模型或 API 请求，未读取密钥/临床数据库/活跃诊断目录，未修改任何文件；报告由 runner 持久化。
