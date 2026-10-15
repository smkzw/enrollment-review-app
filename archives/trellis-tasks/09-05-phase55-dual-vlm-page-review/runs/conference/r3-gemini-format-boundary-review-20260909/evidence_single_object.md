全部证据已收集，164 项相关测试通过。现在整理并输出审阅报告。

# Conference Output: r3-gemini-format-boundary-review-20260909 - evidence_single_object

## Output

只读独立工程复查已完成。基于当前工作区代码与测试（未依赖执行者论述、未调用模型/网络、未读 `.env`/个人配置/临床原件），我的总体结论：**四条目标链路（格式纠正、Gemini 原生传输、OAuth、执行/回执/恢复）的核心安全属性成立且测试覆盖扎实；发现 2 个实质缺陷（中等严重度、均可最小修复）与 4 个低严重度缺口**，无破坏事实保真或凭据安全的直接路径。164 项相关测试本地全部通过（全部 mock，无网络）。

### 0. 证据与方法

- 初始读取集不在 CWD 根的 `context/`、`plans/` 下，实际位于任务包 `.trellis/tasks/09-05-phase55-dual-vlm-page-review/` 下（同名文件存在），已据此审阅。此为路径解析记录，非阻塞。
- 逐行审阅：`app/llm/gemini_transport.py`、`gemini_oauth.py`、`page_review_format_repair.py`、`page_review_harness.py`、`page_review_admission.py`；消费者 `app/services/page_review_execution.py`、`page_review_job_executor.py`、`page_request_receipt.py`、`page_review_recovery.py`、`page_review_job_service.py`、`page_review_runtime.py`、`page_review_cancellation.py`、`app/workflow/runner.py`（并行波次）；合同 `app/domain/contracts/page_review.py`；配置模板 `.env.example`（模板文件，非个人配置）。
- 测试运行：`tests/v2/llm/test_gemini_transport.py`、`test_gemini_oauth.py`、`test_page_review_format_repair.py`、`test_page_review_harness.py`、`tests/v2/services/test_page_review_job_executor.py`、`test_page_review_execution.py`、`test_targeted_page_review_jobs.py`、`tests/v2/llm/test_targeted_page_review.py`、`tests/v2/api/test_page_review_resume.py`、`test_page_length_recovery.py` — **128 + 36 = 164 passed**。
- 未验证项：真实端点行为（`-high` 后缀与 `modelVersion` 回执的实际服务端字符串）无法离线证明，只能由代码+断言形状及上下文所述真实运行佐证；"24页18通过→重读22通过”等数量未核验，且按边界不作为验收。

### 1. 逐项核验结论（证据）

**1.1 一次格式纠正：同模型、同图、不删事实不改数值、严格失败边界**
- 同模型同图：修复循环留在 `read_page` 内，`active_route` 不变，`build_format_repair_messages` 只追加一条纠正消息（`page_review_format_repair.py:155-170`）；测试断言 `routes[0] is routes[1]`、system/页输入逐字节相同、图像 data URL 逐字节相同（`test_page_review_format_repair.py:92-119`）。
- 恰好一次：`format_repair_used` 标志，第二次仍错显式失败并带“格式纠正一次后仍失败”前缀（`page_review_harness.py:611-616`）。
- “不删事实、不改数值”：这是**提示层约束 + 同一严格合同复验**，不是机械事实集比对（`_FORMAT_REPAIR_REQUIREMENTS`；日期/数值歧义 `repairable=False` 直接失败，`page_review_format_repair.py:106-113`）。设计上合理——首次回答本就违约不可信，最终发布的只有通过复验的第二次回答，两次原始回答均留档。属设计判断而非缺陷，见 §3 残余风险。
- 边界交互均正确且有测试：429 重试不消耗唯一修复名额；length 边界对修复轮仍生效（预算 12000→24000）；`CancelledError` 是 `BaseException`，不被 `except Exception` 吞掉。
- 针对性复核的修复留在 focus 范围内（追加为第 4 条消息，`clause_signals` 强制空）。

**1.2 响应记录与版本闭包**
- 每次尝试（含修复重读、加预算、备用端点切换）都经 `recorded_completion`：请求回执（图像替换为 sha 引用并对照 artifact store 复验字节，`page_request_receipt.py:22-25`）+ 原始响应 artifact + checkpoint 内 `response_attempts` 绑定。schema 拒绝时原始响应仍保留（executor 测试断言两次尝试的请求/响应凭据齐全，修复请求第 3 条消息含 `format_repair`）。
- 版本闭包：executor 入口校验执行版本（`R3_EXECUTION_VERSION_CHANGED`）与路由身份（`R3_ROUTE_CHANGED`）；恢复复用前经仓储复验绑定（含 `prompt_version`、条款包、页身份）；resume 复核在线身份拒绝漂移；记录 identity 哈希含 `prompt_version + response_sha256`。**缺口见 F3/F4。**

**1.3 Gemini 原生 SSE / 截断 / OAuth / 凭据**
- SSE 错误事件（3 种形态）、非 JSON 事件、流中断（`httpx.HTTPError`）一律拒绝部分结果（`gemini_transport.py:118-191`），错误消息只含异常类型名不含 URL/头。
- 截断：`MAX_TOKENS→length`，预算加倍一次后显式失败；另有独立的一次性 48k 补读任务（`plan_page_reread` `single_length_recovery`：仅一道、仅 length、`max_attempts=1`、`retry_length=False`、禁 fallback、禁止链式再补读）。
- `promptFeedback.blockReason` 无候选 → content_filter。
- 后缀映射：请求模型 = `{route.model}-{effort}` = `gemini-3.7-flash-high`，`thinkingLevel: "HIGH"`；回执 `modelVersion` 必须等于裸名或后缀名否则拒绝（`gemini_transport.py:193-196`），测试断言请求形状与身份不匹配拒绝。服务端实际接受后缀无法离线证明（推断：真实运行佐证）。
- 凭据：`route_identity` 不含 `api_key/project_id`；请求回执不含头/密钥；错误回执只记 `error_type/status_code/failure_kind`（测试断言异常文案不进回执）；OAuth 模块只读显式 env，全部 HTTP `trust_env=False`，无个人 harness/home 配置读取路径。产品运行时（`page_review_runtime`）经 `PageReviewAdmission` 以 `(provider, model)` 为键的 `threading.BoundedSemaphore` 强制分道并发（跨线程/跨事件循环正确，非阻塞获取使取消不遗留租约），GLM low + Gemini high 双道与“九月六日决策”测试一致。

**1.4 可取消**
- `run_cancellable` 0.25s 轮询持久取消标志，取消即 `task.cancel()` 并等待；传输层流中取消有专项测试；取消边界后 resume 不重复已提交读；429 的 60s 退避发生在准入槽之外（不占道）。

### 2. 实质缺陷与最小修复

**F1（中）未知/缺失 finishReason 被归为 `schema`，绕过自动重试与备用端点机制。**
`_FINISH_MAP` 之外的 finish（如 `OTHER`、`ERROR`、`IMAGE_SAFETY`、`LANGUAGE`，以及流正常结束但无 finishReason 的 `None`）落入 `read_page` 的 `finish_reason != "stop"` 分支，`failure_kind="schema"`（`page_review_harness.py:601-605`）。后果：executor 仅对 `endpoint` 做步级自动重试（`page_review_job_executor.py:160`），也不触发 `fallback_base_url` 切换；传输侧异常（服务端 ERROR、无 finish 的静默截断）被迫走整页 FAILED_PENDING_REREAD + 新重读任务，恢复成本偏高。失败本身是闭合的（无错误数据），故定级中等。
最小修复：在传输层把未映射的非空 finishReason 与 `None` 归为可重试的传输类失败（如映射到 `endpoint` 或新增 `finish_anomaly` 并纳入 executor 可重试集合），保留 `stop`+合同失败才归 `schema`。注意与现有测试 `test_nonterminal_or_unknown_finish_cannot_accept_valid_json` 的语义协调（仍不得采信结果，只改失败分类）。

**F2（中低）OAuth 缓存无 401 失效路径。**
`gemini_oauth._cache` 仅按本地时钟过期（`expires_in-300`，`gemini_oauth.py:38-39`）；端点返回 401（令牌被吊销/时钟偏移/静态 `GEMINI_ACCESS_TOKEN` 过期）时，同任务内的步级重试与重读任务会持续复用同一坏令牌直至本地到期。失败闭合但把可刷新凭据变成持续性道失败。
最小修复：传输层捕获 HTTP 401 时调用新增的 `gemini_oauth.invalidate()` 清除对应缓存项（仅当配置了 `GEMINI_REFRESH_TOKEN`），使下一次尝试强制刷新。

**F3（低）格式纠正的版本闭包在发布记录中不可直接观测。**
`PageReviewRecord.prompt_version` 在修复重读后仍为基线版本，记录无 `format_repair_used` 类字段；纠正 provenance 只能通过 job checkpoint 的 `response_attempts` → 第二次请求回执（含 `repair_version`）间接追溯。identity 哈希因 `response_sha256` 不同不会碰撞，下游 selection 不受影响，属审计便利性缺口。
最小修复：合同 v7 增加 `format_repair_used: bool`（或组合 `prompt_version + PAGE_REVIEW_FORMAT_REPAIR_VERSION` 后缀），同步更新 `page_review_recovery` 的 binding 相等检查。

**F4（低）每次尝试的回执不记录实际 `base_url`。**
备用端点切换后，只有最终记录的 `endpoint_base_url`/`fallback_used` 可见，单次尝试由哪个端点服务不可分辨（对 GLM 道 fallback 场景有影响；Gemini 默认无 fallback）。
最小修复：在 `recorded_completion` 的回执 payload 中加入 `route.base_url`（`route_identity` 已视其为公开路由语义）。

**F5（低）`modelVersion` 缺失时身份校验静默跳过**（`gemini_transport.py:193` 的 `is not None` 前置）。逐响应身份门退化为配置钉定；Gemini 实际总带该字段，且 `response_model=None` 会在回执可见。最小加固：流结束而无 `modelVersion` 时显式拒绝或至少在回执中标记。

**F6（低）OAuth 刷新无单飞**：到期时并发道会同时 POST token 端点，良性（last-wins），仅多余调用。可选：按键的异步互斥。

### 3. 设计判断与残余风险（非缺陷，供 Codex 知情）

- Gemini 预检是**离线性质**（凭据/HTTPS/模型钉定；原生端点无 `/models`），代码注释已声明，逐响应 `modelVersion` 核对兜底。代价：坏凭据在首页才发现，消耗一次步级重试后进入待重读。我认为是合理权衡，但应在运维预期中写明。
- 修复重读“不删事实不改数值”依赖提示约束 + 同一严格合同复验；重读是全新读，与首次回答的事实集分歧不被系统标记（首次回答违约不可信，机械比对反而不当）。残余风险：模型在修复轮系统性少报而合同无法察觉。现有缓解：双主读互盲 + 核对 + 原始回答留档可事后审计。可接受。
- 请求体不含 `temperature`（采样默认）、`includeThoughts` 分离思考与正文、`maxOutputTokens` 覆盖思考+正文（high 思考消耗预算 → MAX_TOKENS → 加倍/48k 补读阶梯成立）。
- 运行器并行波次只约束总量（双道 cap 之和），可能向单道倾斜；`PageReviewAdmission` 在执行器层纠正为按道限流——实现正确，20ms 非阻塞轮询代价可忽略。

### 4. 对 Codex 的质疑点、决策点与有界问题

1. **决策点（对应 F1）**：非 stop/length/content_filter 的 finish 是否改为可自动重试分类？权衡：自动重试（同模型同图，无事实风险）vs 现行保守的“请保留原件并重新核对”用户路径。我建议传输类异常归 `endpoint`，保留“stop 但合同失败”为 `schema`。
2. **有界问题（影响 F2 定级）**：生产 `.env` 是否配置了 `GEMINI_REFRESH_TOKEN`（我不读该文件）？若仅用静态 `GEMINI_ACCESS_TOKEN`，401 场景实际是“静态令牌过期需人工重新授权”，F2 的修复价值取决于此。安全临时路径：维持现状（fail-closed），F2 修复顺延。
3. **有界问题（不影响工程结论）**：真实运行剩余两页“格式错”的具体 `failure_kind` 是 `schema` 还是 `invalid_json`、且修复轮失败原因是哪类合同违约？这决定是否需要收紧修复提示（如针对 `has_eligibility_value` 一致性），属后续执行层事项。
4. **质疑**：会议上下文的 Source Of Truth/Scope/Success Criteria 仍是 TODO 模板——本次以 objective 文本为准完成，建议 Codex 在主会场记录中补全，避免后续对账缺失。

### 5. 结论

以当前代码与测试为据：格式纠正的“同模型、同图、恰好一次、严格失败、可取消、双留档”成立；Gemini 原生传输对错误/截断/身份的 fail-closed 边界成立；凭据不进入回执、错误与日志面；恢复/续跑的版本与身份闭包成立。建议按 F1→F2→（F3/F4 顺手）顺序做最小修复；F5/F6 可选。上述数量表现（24/18/22）未核验且不构成任何临床验收；最终验收权在 Codex。
