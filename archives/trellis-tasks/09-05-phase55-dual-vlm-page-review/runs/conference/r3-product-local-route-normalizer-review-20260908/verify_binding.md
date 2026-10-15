I'll re-verify the claimed coverage-identity, contract v8, and local-key changes in source and tests rather than taking the owner's description as proof.# Conference Output: r3-product-local-route-normalizer-review-20260908 - evidence_single_object

## Output

本轮只对照源码与测试复核业主描述，不接受口头证明。未改文件、未跑测试、未调模型、未读病例或 `.env`。

### 先前 coverage 选择问题：已修复（产品 HTTP 路径）

换主读后「两份同版本成功 coverage 并列 → 规范化 409」在正式命令路径上已闭合。不是口头修复：选择器在谱系之后按 `main_reader_identity_sha256` 过滤，且合同升到 v8 会先丢掉 v7 行。

### 1. Evidence

**合同 v8 与可选身份字段**
- `PAGE_REVIEW_JOB_CONTRACT = "r3-page-review-job/v8"`（`page_review_job_service.py:29-37`）。
- `SubjectPageCoverage.main_reader_identity_sha256` 默认 `None`，`exclude_if=lambda value: value is None`（`page_review.py:407-408`）。
- 单测弹出该字段后 `model_validate`/`model_dump` 往返相等（`test_page_review_job_executor.py:228-230`）。身份只在 JSON payload，不在 ORM 列（`page_review_models.py:65-79`）。

**执行器如何派生身份**
- `main_reader_identity` 只哈希 main-A/B 的 `provider`/`base_url`/`model`/`reasoning_effort`（`page_review_job_service.py:67-71`）。不含密钥、C 道、`max_tokens`、`max_concurrency`、`fallback_base_url`。
- coverage 步骤：先 `R3_ROUTE_CHANGED` 核对完整 `route_identity`，再 `main_reader_identity(self.routes)` 写入 coverage，并进入 `coverage_id` 哈希（`page_review_job_executor.py:54-86`）。

**正式规范化：运行时取身份、不初始化模型**
- `create_app`：`require_page_review=True`，`page_reader_identity=lambda: app.state.page_review_runtime.main_reader_identity()`（`app.py:248-253,267`）。lambda 在 runtime 赋值之后才被请求调用。
- `PageReviewRuntime.main_reader_identity`：`self._routes or require_page_reader_routes(require_credentials=False)`（`page_review_runtime.py:32-34`）。`require_credentials=False` 缺密钥不抛（`page_review_harness.py:139-175`）。
- 单测：无 MAIN_A/Independent 密钥时仍得到 64 位身份，且 `_executor is None`；带密钥的 `require_page_reader_routes()` 仍报凭据错误（`test_page_review_local_route.py:16-24`）。
- 产品 HTTP 是唯一 `FactNormalizationCommandService` 生产构造点；`create_or_reuse` 把回调结果传入 `select_normalizer_coverage`（`command_service.py:540-545`）。`app/` 内无其他选择器调用点。

**选择顺序与重复失败**
- 版本过滤 → 谱系/predecessor 去重 → **然后**身份过滤 → 再丢 `lane_failures`（`page_review_coverage_selection.py:38-63`）。
- 不同身份：注入 `a*64` 后，当前身份仍选中原 coverage；`b*64` 409（`test_page_review_job_executor.py:231-238`）。
- 同一身份两份成功 coverage：有无身份参数都 409「唯一」（`:248-255`）。与业主「匹配重复仍失败」一致。

**重读必须同一身份**
- `plan_page_reread` 要求除 `recovery` 外 payload 全等，含 `routes`（`page_review_recovery.py:28-33`）。
- 仓储 predecessor 闭包字段含 `main_reader_identity_sha256`（`page_review_repository.py:291-295`）。不同身份不能写成重读后继。
- HTTP：改 MAIN_A `reasoning_effort` 后带 `predecessor_job_id` → `PAGE_REREAD_NOT_READY`（`test_page_review.py:221-229`）。改 job contract 同样 409（`:216-220`）。

**本地密钥 `PAGE_REVIEW_LOCAL_API_KEY`**
- mlx-serve 只读该变量；空则 `"local-product"`。不读 `PAGE_REVIEW_MAIN_B_API_KEY` / `CMS_SMK_API_KEY`（`page_review_harness.py:163-168`）。
- 单测在 environ 里同时放遗留 `PAGE_REVIEW_MAIN_B_API_KEY` 与 `CMS_SMK_API_KEY`，断言仍是 `local-product`；显式 `PAGE_REVIEW_LOCAL_API_KEY` 才用专用值（`test_page_review_local_route.py:45-71`）。
- `config.py:205-208` 仍为 cms-smk 定义 `PAGE_REVIEW_MAIN_B_API_KEY`（可回退 CMS）。本地路径不使用该常量。`app/config.py` 未声明 `PAGE_REVIEW_LOCAL_API_KEY` 模块常量；harness 从 environ 读取。env 文件仍会 `setdefault` 进 `os.environ`。

**业主已否决项（源码仍如此）**
- 辅助幂等键仍是 `r3_targeted_page_review:{reconciliation_id}`（`targeted_page_review_jobs.py:84-87`）。路由变化：同键异哈希 `IdempotencyConflict`；执行期 `TARGETED_REVIEW_CONTRACT_CHANGED`（`targeted_page_review_executor.py:30-34`）。未把路由写入键，未重置两轮预算。
- `read_page` 仍在 `fallback_base_url` 非空时换端点（`page_review_harness.py:561-567,582-587`）。身份哈希不含 fallback URL。
- `pending_only_output` 仍是整个 call 全有或全无（`page_review_pending_normalization.py:14-23`）。未见拆页缩短。

**孤立脚本**
- 仍 `create_app` + 产品 POST + `run_job(新 id)`（`run_isolated_page_revision.py:84-110`）。因此走带身份回调的 command 服务。未断言 GLM low / ddalcu。

**非产品 job 的 coverage 辅助函数**
- `build_subject_page_coverage` 不写 `execution_versions` 也不写 `main_reader_identity_sha256`（`page_review_execution.py:210-238`）。`app/` 内无 API/executor 调用；仅测试内存断言（`test_page_review_execution.py:300-327`）。

### 2. Inference

1. **先前 P0（换 MiniMax→mlx-serve 后两份可用 coverage）已修复。** 机制有两层：v8 `execution_versions` 先丢掉 v7；v8 且不同主读身份时，谱系后过滤只留当前运行时身份。产品 POST `fact-normalization-jobs` 会传入该身份。孤立 `--normalize` 只要先在同进程跑完新页级任务，就走同一路径。
2. **无生产 HTTP 旁路。** 选择器的身份参数可选，但 `create_app` 总是注入回调。`create_or_reuse_from_source(page_review_coverage_id=...)` 仍信任调用方 coverage id，产品命令层先选择再传入。客户端不能自带 coverage id。
3. **无模型初始化。** 身份路径不跑 `preflight_page_reader_routes` / `/models`。与「取身份不必启动本地模型」一致。
4. **重读同一身份是硬约束，不是选择器附带效果。** payload `routes` 全等 + 仓储身份字段。与「失败则不可用变化后的路由续跑、不重置辅助轮次」一致。
5. **本地密钥声明成立。** 遗留 MAIN_B/CMS 密钥不能再进入 mlx-serve。cms-smk 仍用旧变量，属另一 provider。
6. **同一身份的第二份成功 coverage 仍 409，这是刻意的。** 身份比 job payload 窄：只改 `PAGE_REVIEW_CLOUD_CONCURRENCY` / `PAGE_REVIEW_MAX_TOKENS`、或手写 C 预检时有时无，会得到新 job（payload 不同）但同一身份，随后规范化唯一性失败，且不能当重读挂上 predecessor。这是剩余操作碰撞，不是换主读 P0 的回归。
7. **未实现的混合页缩短不是本轮回归。** pending 短路仍按 call。按业主要求不当作本轮必须改的缺陷，也不据此要求第三轮业务拍板。

### 3. Recommendation

**不要再把换主读 coverage 选择当作未修缺陷。** 产品路径已按当前身份过滤。

**不要**把路由加进辅助幂等键、不要拆掉同模型 fallback URL、不要在本轮缩短混合页输入。

**仅在要消灭「同身份误伤」时做最小补丁（非本轮 P0）：** 新建成功 coverage 若与已有当前身份成功行碰撞，应拒绝第二份独立成功行，或要求 predecessor；不要静默挑选。手写 C 波动若被当成新主读任务，会踩这个碰撞。

**测试缺口（不是产品旁路）：** HTTP 测试没有「v8 MiniMax coverage + 当前 mlx-serve 身份 → 选中后者」。该行为目前只在 executor 单测里注入哈希。`FactNormalizationCommandService` 单测仍 `require_page_review=False`，不能证明身份接线。`build_subject_page_coverage` 若以后用于持久化，必须补盖章，否则正式选择器会忽略这些行。

孤立脚本仍应在 201 后断言 payload.routes 为 GLM `low` + mlx-serve ddalcu；这不改变产品选择器结论。

### 4. Uncertainty

- 未跑测试、未读运行库。v7 历史行被版本过滤是代码结论；源孤立库若已是 v8 且身份与当前本地路由相同，脚本会因 200 复用而拒绝「新任务」，这是脚本策略，不是选择器回归。
- `PageReviewConfigError` 在身份回调上不是 `EvidenceAppError`。进程重启后仅 POST 规范化、且 env 的 provider/model 非法时，可能 500 而不是 409。未在运行时观察。
- `config.py` 未导出 `PAGE_REVIEW_LOCAL_API_KEY` 不影响 harness 读 environ；未读 `.env` 确认该键是否已写入。

### 5. Objections / 决策点

**异议：** 业主对 P0 的描述与源码一致，应视为已修，而不是仍开着的 coverage 选择缺陷。把「同身份重复 409」说成未修 P0 是错的。辅助轮次与 fallback 按业主处置保留，本角色不再重提为必须修订。

**不要求第三轮业务评审。** 混合页缩短仍缺来源保全证据，维持未实现。不自动采信事实（`candidate_auto_accept` 仍为 false）。

**无临床接受声明。** Codex 仍是终裁。
