证据链完整。以下为跟进审阅完整报告。

# Conference Output: r3-page-resume-acceptance-20260908 - followup

## Output

**角色**：重要证据审阅（同会话跟进）。**结论**：新取消包裹、双读道（mtplx main-B）配置、冻结身份与跨模型防线的源码与测试证据均成立；先前 D1/D4 已验证修复、D2 以“新鲜预检比对”方式修复；未发现高危缺陷。剩余 1 个需 Codex 裁夺的语义问题（定向复核跨代际允许）、1 项未修复低危（D3）与若干记录性观察。不构成临床验收。

### 一、严重度排序的新发现

**N1（中，语义决策点，非缺陷）— 定向复核允许跨模型代际**：`enqueue_targeted_review` 对原任务只校验 job_type/完成态/authority/页面与核对记录绑定（`app/services/targeted_page_review_jobs.py:40-65`），**不校验原任务的执行版本或读道身份**。切换到 mtplx 后，仍可对切换前（三读道、旧 prompt）的 completed 原任务发起定向复核：targets 取自旧主读记录（:59-60 过滤 MAIN_LANES），新读用当前 A/B-high。安全性成立——原 reconciliation/coverage 不可变（`targeted_page_review_executor.py:1`），结果为独立 `TargetedReviewOutcome` 且 pending 时 `requires_user_review`（executor:79-81）；已冻结的旧定向任务在执行期会被 `TARGETED_REVIEW_CONTRACT_CHANGED` 终止（executor:30-34），无跨模型执行。**最小补救（若 Codex 认为应禁止）**：在 enqueue 处比对 `old` 的 routes/执行版本与当前一致，不一致抛 `TARGETED_REVIEW_NOT_READY`。见 Q1。

**N2（低，已验证的行为变化）— 续跑现在要求服务当时可达**：D2 修复使缓存路由下 resume 也做一次真实 `/models` 预检（`app/services/page_review_runtime.py:74-78`）。本地 mtplx 端点（或云端 A）不可达时，resume 返回 503 `PAGE_REVIEW_UNAVAILABLE`，任务不变——fail-closed 正确，但意味着“因本地服务卡死而取消→重启 GUI→立即点续跑”必须等服务就绪。漂移路径有测试（`test_page_review_resume.py:188-208`），**服务不可达+缓存存在**的组合无测试。记录为文档/用例缺口，非缺陷。

**N3（低，残留假设）**：runtime.resume 通过新鲜预检后，执行仍用缓存 `_routes`（:82-83）。检查通过后数秒内服务换模型 → 每步 `payload["routes"] != self.routes` 比对（executor:55，冻结 vs 缓存，二者一致）通过 → 请求打到旧 model id → 受控 endpoint 失败（可重试或 lane_failure）。固有 TOCTOU，后果受控，不建议改。

**N4（低，前项未修复）**：D3 仍在——resume 的 plan 重建只捕获 `AppNotFoundError` 与 `(EvidenceAppError, InvalidJobDefinitionError)`（`page_review_job_service.py:179-182` 未变），畸形 episode 载荷的 pydantic `ValidationError` 仍以 500 呈现。无突变，仅错误分类退化。最小补救：把 `ValidationError` 并入 409 映射。

**N5（低，无法在本代码库内验证）**：客户端取消后服务端计算继续（已知限制）。客户端槽位卫生有直接测试（见下）；mtplx 服务端是否及时察觉断连并释放其自身槽位不可从此代码库验证——留给 Codex 的运行验收。

### 二、前次发现处置（本次自行验证）

| 前项 | 处置 | 证据 |
|---|---|---|
| D1 前端解码拒绝合法 exhausted 组合 | **已修复+有测试** | `frontend/src/api/page-review/pageReviewHttp.ts:49` 改为蕴含式 `(canReread && status !== "needs_reread")` 才抛错；`pageReviewHttp.test.ts:8-12` 直接覆盖 needs_reread+canReread=false |
| D2 续跑用陈旧缓存身份比对 | **已修复+有测试** | `page_review_runtime.py:70-83` 缓存存在时重新预检并比对 `route_identity`，漂移→409 且不替换缓存；`test_page_review_resume.py:188-208`（`runtime._routes is original` 断言缓存未被替换）。副作用见 N2 |
| D3 resume 计划重建异常映射 | **未修复** | N4 |
| D4 前端丢弃 recovery 指引 | **已修复+有测试** | `pageReviewHttp.ts:62-66` 拼接 title+`recovery_action`；后端信封字段确为 `recovery_action`（`app/api/v2/errors.py:233`，与 EvidenceAppError.recovery 对应）；`pageReviewHttp.test.ts:13-18` 断言拼接文案 |

### 三、新范围逐项验证（证据）

**取消包裹**：读页与核对均被 `run_cancellable` 包裹（`page_review_job_executor.py:154-158, 206-209`）；0.25s 轮询持久 `cancel_requested/cancelled`（`page_review_cancellation.py:10-34`）。已验证：已取消任务绝不发出首个请求（cancellation 测试：20-27）；在途请求被 CancelledError 打断、无部分检查点、无 coverage（resume 测试：144-172）；操作先完成则结果保留（cancellation 测试：46-53）；原始异常不被掩盖（:56-63）；`StepFailure(retryable)` 在 `fail_step` 的取消优先分支收敛为 cancelled（`jobstore.py:757-772`）——**无误报临床失败**。排队中步骤由 runner 边界检查取消（`runner.py:285-287`）；并行波次内已完成的兄弟读先提交（ACTIVE 状态含 cancel_requested，`runner.py:496`+`jobstore.py:577-631`），波后边界收敛（`runner.py:525-532`），取消导致的 StepFailure 不进入 lane_failure 记录。

**客户端清理/无孤儿本地槽**：`PageReviewAdmission` 本地系（mlx-serve/mtplx/mtplx-gui/omlx）共享单槽、非阻塞获取、`finally` 释放（`page_review_admission.py:9-33`）；被取消的等待者在槽释放后不再派发、槽可复用（cancellation 测试：66-97，`entered == [True, True]`）。receipts 落盘为文件写，不在 await 点，不被打断。

**双读道配置**：mtplx 时弹出 HANDWRITING_C（`page_review_harness.py:242-243`），B 钉死 `mtplx-flash-next-optimized-speed`（`app/config.py:201-210`）、reasoning high、并发 1；A 保持 GLM-5.3-flash low、云端并发 {2,3}；`supports_vision` 门禁 fail-closed（harness:280-283，`test_page_review_local_route.py:83-108` 含无视觉即拒、凭据不泄漏、集合恰为 {A,B}）。预检只打 `/models`，mlx 路径仍“不自动加载”。

**无第三票/无误报缺第三服务**：mtplx 路径不做手写补读（`page_review_execution.py:143`），`handwriting_third_read_expected=False` 使 reconcile 拒绝任何 C 记录（`page_reconciliation.py:53-56`）且 `handwriting_reader_triggered` 恒 False → `missing_optional_lanes` 恒空（:178-188）——直接验证了需求。两主读各自读整页含手写；手写观察需双道各一次、上下文非空才接受，否则列 conflict 交人工（:155-172）。事实/条款信号仍要求双主读一致（:88-101, :129-146）。

**冻结身份与源版本兼容**：payload routes 为逐道公共身份（无 api_key），executor 每步复核（executor:55）；局部重读要求前次 comparable==当前 plan（含 routes），复用收据经 repository 逐字段重验（含 prompt_version，`page_review_recovery.py:28-69`）；旧任务续跑被整包比对拒绝（409），切换前 queued/running 旧任务在认领后以 `R3_ROUTE_CHANGED`/`R3_EXECUTION_VERSION_CHANGED` 终止，检查点保留——历史不重写。

**覆盖派生整理**：`select_normalizer_coverage` 先按当前 `execution_versions`（含 prompt v11）过滤，再按 `main_reader_identity_sha256` 过滤，重读 lineage 校验、失败终态不复活，唯一才可用（`page_review_coverage_selection.py:25-66`）——旧模型覆盖被排除并报 `PAGE_COVERAGE_NOT_READY`（历史保留），新模型必须 fresh job。逐记录 prompt/contract 复核与 reconciliation 重放等值（:71-87）。

### 四、剩余决定性测试（建议）

1. 后端：缓存路由存在 + 实时服务不可达 → 期望 503 且状态不变（补 N2 组合；现仅覆盖漂移与配置缺失）。
2. 后端（若 Q1 裁决为禁止）：定向 enqueue 对旧代际原任务 → 期望 409。
3. 集成：并行波次中途持久取消，已提交兄弟读保留（当前为单元组合覆盖，无单一场景）。
4. 真实 mtplx 服务的浏览器 e2e（1080p/2K/4K）与取消-续跑实测——超出本只读边界，属 Codex 视觉/运行验收。

### 五、对 Codex 的有界问题

- **Q1（N1）**：切换模型后，是否允许对切换前的 completed 原任务发起定向复核（新读新模型、targets 源自旧记录、结果独立且需人工复核）？若意图是“切换即全新开始”，最小补救是在 `enqueue_targeted_review` 增加原任务代际校验。裁决前安全路径：维持现状（不可变性已有保证）。
- **Q2（N2）**：请确认“续跑点击时本地/云端服务必须可达，否则 503”是 D2 修复的预期语义；若是，建议在用户可见文档标注。

未运行任何测试/浏览器/模型调用（只读边界）；本报告为顾问输出，验收权在 Codex。
