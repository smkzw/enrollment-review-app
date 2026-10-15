# 会议输出：qwen-bounded-completion-review-20260910 - evidence_single_object

## 输出

续审第七遍（oMLX 页读原生约束 + sar17 完成证据 + AR 更正）。边界遵守：只读；未读 `response-*.json`/`stream-*`/`request-*.json`（含私有推理）；无模型调用、无写入。

### 更正确认（本人前审）

撤回 pass-6“OOM 归因留待 AR 路线”的表述：MTPLX 原生 API 在 AR 模式下对图像请求显式返回 400（"image content requires MTP generation mode"），且 AR 服务已关闭——**AR 图像重放是已证死路，不再建议**；exit 137 的 OOM 成因维持非排他（单样本）。pass-6 的重放建议仅在“核实空闲内存的运行时/MTP 模式或其它读道”意义上存续。

### 新完成证据的状态（按限定）

`diagnostic-omlx-medium-sar17-complete-page-contract`：完成、finish=stop、v13、46 facts/9 signals/6 handwriting。**两次调用**：receipt[0] 642.8s/18004 输出、stop、JSON 不完整 → 触发产品格式修复轮；receipt[1] 374.0s/10490 → 终稿。两份回执 `response_format_warning` **键在场且为 null**（捕获代码在运行，服务端两次均编译文法、无降级）。所有权声明：34/34 固定数值金标命中（owner 评分）、四项免疫学数值/单位经 owner 对源图核对、 handwriting 作者/范围未裁定、终模型未给 bbox——**均不构成临床验收**，本审阅不接受。

### 传输选项模块评审（`page_review_transport_options.py`）

**设计合格，四项硬边界均核实**：(1) 仅 `provider=="omlx"` 生效，其他 provider 返回 `{}`（测试参数化覆盖四家）；(2) 从消息中**现取** `output_schema`（含 targeted-review 修改后的 schema——选项随当前消息派生，不陈旧）；(3) `decoding_response_format` 投影保留（pass-5 已证的 nonblank 防御未丢）；(4) `thinking_budget=budget` 与 `max_tokens` 同值共享 131072，且**随 length 重试的预算翻倍同步**（harness 与测量脚本都传当前 budget），无 temperature 等采样改动；提示消息本体不被改动（测试断言 deepcopy 等价）。协议侧不受扰：`protocol_semantic_transport` 用自己的投影（pass-5 已审），测量脚本 `request_options is None` 守卫使协议诊断的显式 body 不被覆盖。

**SDK 与裸流一致性：成立。** harness 走 SDK `extra_body={"thinking_budget":…}`（序列化后并入 body 顶层）；测量脚本把 `extra_body` pop 后并入裸 body 顶层——两条路径线上等价（response_format + thinking_budget 顶层，reasoning_effort 均保留）。差异仅流式与否（既有状态）。

**修复轮处理：行为正确但无测试钉住。** `page_completion_options` 扫描到原始 user 消息中的 output_schema 即返回选项，`build_format_repair_messages` 追加修复指令不移除原消息 → 修复轮同样带约束与预算（sar17 两轮回执均无降级与之相符）。但这一关键路径只被证据覆盖、没被测试覆盖（见下）。

### 可行动问题（按优先级）

1. **“编译成功 ≠ 保证良构”已被本证据反证，且 harness 的 SDK 路径看不见降级信号。** call-0 两难并存：warning null（文法已编译）却 stop+不完整 JSON——机制未解（授权文件不足以裁定；owner 可用留存的 response/stream 追查，如宽容 EOS 假说）。行动项：`PageCompletion`/record 在 SDK 路径增加 Warning 头可见性（`with_raw_response` 或等价），否则产品路径的 oMLX 约束一旦回归 pass-3 的 parser 失效场景将完全静默。
2. **请求身份/版本记录缺口。** `PageReviewRecord` 身份哈希与 `prompt_version`(v13) 均不编码解码模式（response_format/thinking_budget 在否）。同一身份字段下，带/不带原生约束的两条 record 只能靠 response_sha256 间接区分。行动项：把选项摘要（或 constrained_decoding 布尔+thinking_budget）并入 identity 输入或 prompt_version 后缀——诊断侧已有 request 文件，产品 record 缺此维度。
3. **缺三个聚焦测试**：(a) 修复轮派生——构造页面消息→模拟 format-repair 消息→断言选项仍在且 schema 未变（本证据的核心路径）；(b) 预算共享不变式——length 翻倍后 thinking_budget 同步（单行断言即可）；(c) 裸流合并 parity——扩展既有 mock 测试断言 body 顶层同时含 thinking_budget 与 response_format。
4. 次要：`page_completion_options` 对每条 user 文本做整段 `json.loads`（约 35K token 文本）——CPU 代价可忽略，仅记录。

### 限度

原生 oMLX 页读运行仍 pending 正式化，本审阅不作接受；34/34 金标是 owner 评分的数值维度，handwriting 归属、bbox 缺失、免疫学四项之外的字段均未裁定；call-0 的 malformed-stop 机制未解意味着“降低畸形重试成本”的收益是经验性的（本例一轮修复内消化），不是保证。以上不动摇本遍结论：模块边界正确、一致性成立、两个可行动缺口（SDK 侧降级可见性、record 身份编码）与三个聚焦测试值得在下一轮落地。
