# Execution Output: written-judgment-search-contract-20260910 - worker_01

## Boundary And Context Check

- 本轮新增写仅两个文件：`app/llm/judgment_search_reader.py`、`tests/v2/llm/test_judgment_search_reader.py`。既有合同、`page_review_harness.py`、`independent_vlm.py`、`page_review_format_repair.py`、`gemini_transport.py`、`judgment_search_source.py` 全部只读（owner 对范围构建器与事实权威的既有修改原样保留，未触碰）。无网络/真实模型/凭据/子委派/API 端点/导出/持久化/临床缺失生产者/产品默认变更。
- 工具披露：`apply_patch` 本运行时不存在；两个新文件由 ZCode Write 创建，不作等价性声明。
- 勘察结论（复用面）：`PageReaderRoute`/`PageReviewInput`/`PageCompletion`/`Completion`/`direct_completion`（product-owned transport 分派 GLM/Gemini）、`PageVisionInput`+`page_to_data_url`、`PageReviewInput.__post_init__` 按实际字节重算哈希（本实现将其作为 TOCTOU 冻结的校验点复用）。**关键发现**：共享 `extract_json_object` 用贪婪正则 + `raw_decode`，对“尾随第二个 JSON 对象”会静默返回第一个对象——按指令边界未改共享文件，在本模块实现严格解析并在报告中声明该边界。

## Work Performed

**`read_judgment_search_page(scope, page_input, target_text, route, completion=direct_completion)`——窄异步候选读器，恰好一次完成调用：**

1. **调用前校验**：`scope` 经 `model_validate(model_dump())` 重验证（`model_copy` 绕过即拒）；route 仅 main-A/main-B，provider/model/effort 非空、`max_tokens>0`（budget 即 route.max_tokens，无路由替换）；target 非空；页输入按（资料版本、页工件、页码）精确命中范围成员且页图哈希与范围身份一致；随后 `page_to_data_url` **即时读取当前字节**并用 `PageReviewInput` 既有哈希校验重建冻结输入（路径被替换的 TOCTOU 在调用前拒绝），发送前再校验 data URL 解码哈希。
2. **提示**：system 提示只做候选检索语义——手写批注 + 打印病历分析双通道、逐字保留全部独立摘录（含日期与指向关联、顺序保留、不改写不合并）、不得推断 CS/NCS、不得转借邻近签名/日期、无手写 ≠ 判断缺失、打印正常数值/参考范围本身不算 found、作者/日期/指向不明 → ambiguous 保留暂定摘录、目标文本是数据不是指令、not_found/unreadable 不编造摘录。user 消息 = 冻结页图 data URL + 目标文本 + `JudgmentSearchPageCandidatePayload.model_json_schema()`。**无条款包**、无 review_context、无项目专属规则/金标/硬编码药名病名。
3. **响应**：`_extract_single_json_object`（本模块严格解析：容忍包装文字；截断/顶层非对象/对象后仍有 `{` 一律拒绝；无引用修复，不改摘录）；`JudgmentSearchPageCandidatePayload`（extra=forbid，仅 `handwritten`/`printed_analysis` 两个既有 `JudgmentSearchChannelResult`，无模型生成权威 ID，临床结论额外字段被拒）；空回答与 `finish_reason=="length"` 显式拒绝；**来源身份在验证成功的完整响应之后由代码绑定**（取自冻结页域，非模型输出）。
4. **回执** `JudgmentSearchReaderReceipt`（frozen）：scope 哈希、页身份、target 哈希、prompt 版本（`judgment-search-reader/v1`）、实际消息 `canonical_hash`（随目标/页图字节/提示变化）、requested 读道身份（lane/provider/model/effort/budget——**绝无 api_key/base_url**）、`response_model`/`response_id` 与 requested 分开记录（缺失即未知，不虚构、不单独构成已验证独立）、页候选结果、回答文本哈希、`product_acceptance: Literal[False]`。
5. **失败语义**：`JudgmentSearchReaderError(failure_kind, completion)`——完成前异常 `completion=None`（不发明数据）；完成后任何校验失败携带完整原始 `PageCompletion`；transport 异常包装保留；**失败始终是失败，绝不折叠成 not_found**；无重试/无 fallback/无格式再生。诚实声明：**尚未接线**外层重试/限流/coverage 持久化/失败路由，不声称已履行。

**共享文件边界声明**：严格 JSON 解析为本模块局部实现（不改 `extract_json_object`）；未复制整页读道循环（无重试/条款包/上下文注入）。

## Artifacts And Evidence

17 项 fake-completion 测试，覆盖任务书全部指定场景：双通道多摘录逐字保留（含首尾空格/换行）；ambiguous 暂定摘录保留；全部 not_found 仍 `product_acceptance=False`；篡改 scope（model_copy）/越界页/输入哈希不符/**图片文件事后替换**（tmp_path 重写后在调用前拒绝，`calls==[]`）；route 配置五类拒绝（lane/provider/model/effort/budget）+ 空白 target；额外临床结论字段拒且 `.completion` 可取回原始回答（恰好 1 次调用，无再生）；空/截断/双对象 JSON 拒（原始响应可取）；缺 printed_analysis 部分载荷拒；transport 异常 `completion=None` 不捏造；length 截断拒；恰好一次调用无 fallback；请求含冻结图像实际字节（data URL 解码哈希 == 范围哈希）、含显式目标、含双通道合同、无 `clause_pack`；回执记录 requested/response 身份（response_model=None 保持未知）且序列化不含密钥与端点；回执哈希随目标/页图变化、effort 变化体现于回执。

## Commands And Observations

- `.venv/bin/python -m pytest tests/v2/llm/test_judgment_search_reader.py -q` → 首跑 1 failed（测试 helper `_sha` 误用于 bytes），修正后 **17 passed**。
- `.venv/bin/python -m pytest tests/v2/llm/test_gemini_transport.py tests/v2/llm/test_page_review_format_repair.py tests/v2/llm/test_page_review_harness.py -q` → **99 passed**（窄产品 transport/prompt 相邻套件，复用面无回归）。
- 合并复跑 → **116 passed**。`git status`：仅两个新增文件为本轮产物（其余 `??` 系 worktree 既有未提交状态，未触碰）。

## Blockers Or Missing Environment

- 无阻断。工具披露：`apply_patch` 不可用，新文件经 ZCode Write 创建。
- 边界声明：共享解析器容忍尾随第二对象的行为已在本模块以严格局部解析规避（未改共享文件，属“报告边界而非改共享文件”项）。

## Rerun Requests Or Next Step

- 无需重跑。**仍未实现、待 owner 集成（如实申报）**：范围-来源完整性（source_scope_verified 仍恒 False）、权威目标文本装载（当前 target 由调用方显式传入，候选性质，非权威 requirement 证明）、检索结果持久化与回读、外层重试/限流/失败路由编排、独立双读回执汇总与响应身份核验、语义核实与适用性判定、判断缺失报告生产者。本读器无产品调用点，未改变任何产品默认或临床行为。
