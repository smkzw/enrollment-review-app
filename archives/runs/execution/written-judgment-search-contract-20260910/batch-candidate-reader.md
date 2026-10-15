# Execution Output: written-judgment-search-contract-20260910 - worker_01

## Boundary And Context Check

- 修改仅限四个授权文件 + 一个新测试文件：`app/llm/judgment_search_reader.py`、`app/services/judgment_search_results.py`、`tests/v2/llm/test_judgment_search_reader.py`（本轮零改动）、`tests/v2/services/test_judgment_search_results.py`、新增 `tests/v2/llm/test_judgment_search_batch_reader.py`。`git status` 确认；无其他任何文件改动。
- owner 侧变更已保留：v4 读器在其最新形态上扩展（owner 期间已把 reader 测试从 17 扩到 33 项——全部继续通过）、results 测试的 `_fake`/`_channel` owner 版签名按现状适配。
- 无 DB/源材料/网络/API/模型/本地服务/安装/委派；未对无关代码跑格式化。工具披露：`apply_patch` 不可用，修改经 ZCode Edit 与受控文本替换完成，不声明等价。

## Work Performed

**读器模块（最小连贯扩展，v4 单版本字节级不变）：**
- 新常量 `JUDGMENT_SEARCH_BATCH_PROMPT_VERSION = "judgment-search-batch/v1"`；新合同 `JudgmentSearchBatchTargetIdentity`（requirement_id + scope_sha256 + target_sha256，仅确定性 raw 绑定所需）、`JudgmentSearchBatchResultItem`（requirement_id + 双通道，与单版本形状一致）、`JudgmentSearchBatchPagePayload`（results 列表，extra=forbid）。
- 回执新增 `batch_targets: tuple[...] = ()`（单版本默认空；完整目标原文不入回执，哈希即冻结输入身份）。
- **共享响应选择助手 `select_candidate_page_channels`**：单版本要求批次组为空（防改标）；批次版本要求非空组、批次回答 requirement 集合与请求精确一致（缺失/多余/重复拒绝——不猜 ID、不删未知项、不补 not_found），并只选中与回执 scope/target/requirement 三元组精确匹配的组；其他版本“保留原样，不重标、不接纳”。单读器解析块与装配器均改走此助手（单一实现）。
- **`read_judgment_search_page_batch`**：调用前逐目标重验证 scope（model_copy 防绕过）、同权威、同页域（版本/工件/页码/哈希全集合相等）、目标非空、requirement 不重复；页成员/页图哈希走既有冻结路径（`_freeze_page_input`，图像只读一次——避免 requirements×pages×2 重复读图）；同一 `_SYSTEM_PROMPT`、同一消息结构、同一图像校验（不手搓弱发送路径）；**恰好一次完成调用**，无重试/无筛选遗漏；每目标一条扩展回执（按请求顺序，共享同一原始 completion 对象与消息哈希，batch_targets 为全部请求组）；任一目标/回答无效 → 既有读器错误并保留原始完成，绝不部分成功。

**装配器**：移除自身版本门，改用共享助手——批次回执可被正确绑定接纳（组三元组必须匹配当前 scope），单/批互不冒认；过时/未知版本依旧“不重标、不接纳”；原始通道不一致依旧拒绝。工件 save/load 无需修改即兼容（新字段带默认，旧工件照常装载）。

## Artifacts And Evidence

- 新批次测试 8 项：两目标一次调用、按请求顺序、共享 raw completion/messages 哈希/路由/预算（2048 不变）、消息含双目标全文+双通道契约+无条款包；不同目标相同摘录各自保留（无降级合并）；缺失/多余/重复 ID → `batch_shape` 且原始响应保留（恰好一次调用）；非 stop → `length` 保留原始；围栏完整 JSON 接受；页越界/图片事后替换/跨权威/页集不一致/重复 requirement/空目标/空白目标全部**调用前**拒绝（`calls==[]`）；两个版本常量字节不变断言。
- results 扩展 6 项：批次回执仅绑定匹配 scope（错位 → 范围哈希拒绝；found 单回执 → 原生 `candidates_present` 且采信恒 False）；变造批次组 → ID 集合冲突拒绝；批次回执无组 → “缺少批次目标组”；单版本回执携组 → “不得携带批次目标组”；批次回执通道漂移 → “原始回答”拒绝。
- 回归：reader(owner 33) + results(20) + batch(8) + artifacts(12) + source(24) + coverage(31) → **127 passed**，单跑 reader 33 与 artifacts 12 确认单版本行为与存储兼容性不变。

## Blockers Or Missing Environment

- 无阻断。工具披露：`apply_patch` 不可用（如实声明，不主张合规等价）。

## Rerun Requests Or Next Step

- 无需重跑。**未实现/待集成（如实申报）**：真实模型调用与路由预检、批次调用点接线与持久编排（重试/限流/失败路由）、独立双读路由回执汇总、语义核实与适用性、professional_judgment 缺失生产者；批次回答对非选中组的内容仅由 ID 集合与选中组绑定保证，未选中组的原文完整性依赖同一 raw completion 保留（回执非外部鉴证）。本实现是候选读取与绑定装配，非作业集成或上线批准，无任何临床采信声明。
