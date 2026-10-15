# Execution Output: written-judgment-search-contract-20260910 - worker_01

## Boundary And Context Check

- 本轮仅新增两个文件：`app/services/judgment_search_results.py`、`tests/v2/services/test_judgment_search_results.py`；`git status` 确认无其他改动。owner v4 读器（`judgment-search-reader/v4`、回执内嵌原始 `PageCompletion`、`uncertainty_note`/`coordinate_convention="unverified"` 合同字段、严格单围栏解析器）、最新源构建器、覆盖函数全部只读保留。
- 无共享文件改动、无临床资料/库、API/模型调用、网络、安装、凭据、本地平台、子委派。工具披露：`apply_patch` 不可用，新文件经 ZCode Write 创建，不声明等价。
- 复用面：`summarize_judgment_search_coverage`（原生缺页/缺读道处理）、`JudgmentSearchPageCandidatePayload` + `_extract_single_json_object`（owner 现行解析器，按指令显式允许复用；私有名导入已在源码注释说明）、`JUDGMENT_SEARCH_PROMPT_VERSION`（v4）。

## Work Performed

**`assemble_judgment_search_coverage(scope, target_text, receipts) -> JudgmentSearchCoverageSummary`**（纯函数，无存储/新 DTO）：

1. **重验证**：scope 与每条回执均经 `model_validate(model_dump())`（`model_copy` 变造被拒）；回执内嵌 completion 随转储往返。
2. **当前目标绑定**：target 非空；`sha256(target_text.strip())` 逐条等于回执 `target_sha256`；回执 `scope_sha256` 逐条等于当前 scope。
3. **页身份三重一致**：回执 `page` 必须是当前页域成员且四字段精确相等；`page_result` 四字段与回执页一致；同读道同页重复 → 拒绝（不最后者胜、不计作第二模型）；外来页拒绝。
4. **读道身份**：仅 main-A/B；provider/model/effort 非空、budget 为正；同读道跨页 provider/model/effort 一致；**响应模型必须非空且忽略大小写/首尾空白等于请求模型**（未知/别名拒绝，无回退）；跨读道同 provider+model → 拒绝（同模型不构成独立双读，显式早拒并声明别名不支持）。
5. **原始回答核对**：`finish_reason` 双侧 stop；回执镜像的 response_model/response_id/finish_reason/completion_text_sha256 与原始 `PageCompletion` 一致；用当前解析器 + 候选合同重解原始文本，**两条通道必须与绑定页结果逐字段相等**（自然保留 `uncertainty_note` 与 `coordinate_convention=unverified`；无坐标缩放、无引文修补、无重试）。
6. **版本门槛**：仅接纳当前 `judgment-search-reader/v4`；历史版本回执保留原样、不重标、不接纳。**无跨上下文同文本污染启发式**（docstring 明示：相同文本候选按各自页/通道绑定核对）。
7. **原生装配**：每读道构建 `JudgmentSearchLaneResult`（页按合同序），交 `summarize_judgment_search_coverage`；缺页/缺读道/空列表 → 原生 incomplete（绝不补 not_found）；全 not_found → 原生状态 + 三 False 不变量。

## Artifacts And Evidence

14 项测试，回执全部经真实 v4 `read_judgment_search_page`（注入 fake completion、内存页字节、真实合同 scope）产生：
- 正常：双读道全 not_found → 原生 absence 状态 + 三 False 不变量；found+ambiguous → `candidates_present`，found 候选 `coordinate_convention="unverified"`、ambiguous 暂定摘录 `uncertainty_note="作者与日期不可辨"` 保留；**两读道相同文本候选 → 不视为污染**（2 条 found 并列）；缺页/单读道/空列表 → 原生 incomplete。
- 拒绝（全部 `JudgmentSearchResultsError`）：当前目标不匹配；scope 漂移（可重验证的不同 scope → 范围哈希）；外来页（model_copy 自洽变造）；同读道同页重复；**绑定页结果与原始回答矛盾**（合法但漂移的候选文本 → 重解比对拒绝）；回答文本哈希/响应 ID/finish_reason/响应模型镜像漂移（回执侧与 completion 侧双向）；响应模型 None/未知网关别名（真实读器产出）；同模型双读道；同读道混 effort；历史版本 v3；model_copy 变造（scope 哈希无 pattern 列经比对拒、页身份 pattern 列重验证拒、requested 空 model/零预算拒）。

## Commands And Observations

- 新测试首跑 5 failed/9 passed，失败均为测试脚手架问题并修正：payload 助手被 `_gather` 误当页选择器调用（补页选择 lambda）；scope 漂移反例改用可重验证的不同页域；伪造页结果改为“合同合法但语义分歧”的候选文本漂移（空 found 候选本会被合同重验证拦截）；`match="model"` 误中 "model_copy" 文案（改精确匹配）；v4 回执 `scope_sha256` 无 pattern 的实际行为按“比对层拒绝”断言并在测试注释说明。修正后 **14 passed**。
- 聚焦套件：results(14) + reader(17) + source(24) + coverage(31) → **102 passed**（一次性，无失败）。

## Blockers Or Missing Environment

- 无阻断。工具披露：`apply_patch` 不可用（如实声明，不主张合规等价）。

## Rerun Requests Or Next Step

- 无需重跑。**仍未实现/待集成（如实申报）**：真实模型调用与真实路由预检、检索结果持久化与回读、外层重试/限流/失败路由编排、独立双读路由回执的跨执行核验、语义核实与适用性判定、professional_judgment 缺失生产者。本装配无产品调用点；scope/target 引用本身不声明真实调用发生过；无任何临床批准或采信声明。
