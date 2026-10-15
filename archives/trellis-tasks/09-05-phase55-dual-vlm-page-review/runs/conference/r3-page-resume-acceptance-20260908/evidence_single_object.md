证据收集完毕。所有初始读集文件均已审阅，并补充核对了 harness 预检、状态投影、app 装配与状态机常量。以下为完整顾问报告。

# Conference Output: r3-page-resume-acceptance-20260908 - evidence_single_object

## Output

**角色**：重要证据审阅（`evidence_single_object`）。**结论**：取消后续跑工作流的核心恢复正确性成立——节点内显式续跑、全量身份冻结比对、历史检查点保全、失败无突变均有源码与测试双重证据；但发现 1 项前后端状态契约层面的已验证不一致（当前可达性受限）和 3 项低危观察，另有 2 个需 Codex 裁夺的语义问题。以下不构成临床验收。

### 一、逐项要求核对（证据：观察 + 源码定位）

| 要求 | 判定 | 关键证据 |
|---|---|---|
| 仅显式节点内续跑 | ✓ | `app/api/v2/page_review.py:121-129` 节点三重绑定；`app/services/page_review_job_service.py:166-172` job_type/subject/episode 校验（不符→404）；`app/workflow/states.py:57-70` cancelled 为终态且不可认领，无任何自动恢复路径 |
| 精确 source/rules/pages/公共路由/版本绑定 | ✓ | `page_review_job_service.py:177-188` 从活动节点全量重算 plan 并整包字典相等比较：authority（含 rule_set revision、complete_processing_revision）、clause_pack、pages（含 page_image_sha256）、association_sources、review_context（含 episode_revision）、routes 公共身份、4 个版本号；`route_identity`（:67-72）不含 api_key |
| 成功检查点不变 | ✓ | `app/workflow/jobstore.py:1263-1273` 仅翻转 cancelled→queued；`tests/v2/api/test_page_review_resume.py:98-136` 断言保留的 read 检查点逐字节不变且对应 lane 不重复调用 |
| 不新建任务、不自动 resume、不进历史队列 | ✓ | resume 无 enqueue 调用；`frontend/e2e/page-review-flow.spec.ts:63-66` 断言点击后提交恰好为 `[{resume:"root"}]`；`usePageReviewJob.ts:125-126` 取消态只走 resume |
| 不重置定向两轮预算 | ✓ | 定向任务被 job_type 检查排除（404）；`test_page_review_resume.py:284-292` 断言 `max_attempts==2` 原样；步骤 `attempt` 计数在 resume 中不重置（jobstore.py:1268-1273 未触碰） |
| Status GET 不初始化模型 | ✓ | `app/services/page_review_status.py` 纯持久层读取，不经 runtime；测试 `test_page_review_resume.py:65-66` 断言 GET 后预检计数为空 |
| 续跑预检仅 `/models`、不推断临床页、不加载服务 | ✓ | `app/llm/page_review_harness.py:249-300` 仅 GET `/models`；:269-274 mlx 未就绪即报错“不自动加载或替换模型”；不读任何临床页内容。注意（见 D2）：进程已有缓存路由时**不重复预检**，该行为被测试 `:108-110`（`forbidden_prepare`）固定为设计意图 |
| 解析后精确比较身份（含可写道在场与实际 model） | ✓ | `route_identity` 含 `model`/`model_match`；可写道缺席使 routes 键集不同→409。测试覆盖：missing-C 重启同形解析通过（:46-71）、手写 model 与 model_match 漂移均 409（:169-183）、main-A reasoning 漂移 409（:156-166） |
| 失败/漂移不突变旧结果 | ✓ | 全部校验与 `store.resume_cancelled` 在同一事务内、突变最后发生（`page_review_job_service.py:160-189`）；5 个 409/503/404 测试均断言任务仍 cancelled、步骤集合不变 |
| 前端续跑原任务、防重复、防错对象迟到、失败保留取消身份 | ✓ | `usePageReviewJob.ts:60-62,84` owner 身份双重检查；:129,134 abort/归属检查丢弃迟到响应；:136 `current.current = previous` 保留取消身份；:53,121 `starting` 防抖 + 服务端幂等（重复 resume→`changed=false`，:116-119）；切换受试者丢弃迟到结果有单测（`pageReviewFlow.test.tsx:80-94`） |

### 二、缺陷与风险（按影响排序）

**D1（中，已验证的契约不一致，当前可达性受限）**：前端解码器把 `can_reread !== (reviewStatus === "needs_reread")` 视为非法响应（`frontend/src/api/page-review/pageReviewHttp.ts:49`），但后端对“补读耗尽”任务会合法返回 `needs_reread + can_reread=false`（`app/services/page_review_status.py:44-51`：`exhausted = bool(recovery.length_override)`，标签“补读后仍有资料未读完，请核对原件”）。该组合一旦出现，前端抛 `PageReviewApiError`，用户看到的是“暂时无法查看资料进度/重新查询进度”的循环报错，而非设计好的终态提示。可达性核查：`single_length_recovery=true` 仅由 API 层接收（`page_review.py:21`），`frontend/src` 无任何调用点（`usePageReviewJob.ts:127-128` 只传 `predecessor_job_id`），故今日仅直连 API 创建的单长度补读任务会触发——但后端契约与前端校验已经分叉，且 `pageReviewFlow.test.tsx:110` 恰好 mock 了这一组合却因整体 mock 工厂而绕过了解码器，掩盖了断点。**建议**：将等价式放宽为蕴含式（`canReread ⇒ status === "needs_reread"`），或在 `PageReviewStatus` 显式建模 `exhausted` 并展示后端终态文案；同时在 `pageReviewHttp.test.ts` 补 exhausted 组合解码用例。

**D2（低-中，陈旧运行配置窗口）**：`PageReviewRuntime._routes` 进程内一次性缓存（`app/services/page_review_runtime.py:27-55`），`resume` 仅在缓存为空时预检（:70-75）。若服务进程存活期间 MTPLX GUI 重启并改供另一个 Flash-Next 模型 id，续跑比对用“冻结(旧) vs 缓存(旧）”通过，执行期才以请求失败收场。后果受控（lane_failure 检查点→needs_reread，无数据损坏；`page_review_job_executor.py:141-168` 有每步 routes 复核），且单用户本地应用重启即重新解析——但与需求“compare exact identity including … actual model”的字面读法存在解释空间：缓存身份在缓存时刻是 actual，之后只是 assumed。安全临时路径：维持现状（与测试固定的 no-re-prepare 设计一致），文档化“更换手写模型需重启服务”。见 Q1。

**D3（低，错误分类不佳）**：`PageReviewJobService.resume` 的 plan 重建只捕获 `AppNotFoundError` 与 `(EvidenceAppError, InvalidJobDefinitionError)`（:179-182）；若活动 episode 载荷畸形触发 pydantic `ValidationError`，会以 500 而非 409 `PAGE_REVIEW_RESUME_NOT_READY` 呈现。事务回滚保证无突变，仅错误语义退化。

**D4（低，恢复指引丢失）**：409 拒绝时前端仅提取 `error.title`（`pageReviewHttp.ts:62-64`），后端精心撰写的 `recovery` 文案（“……已保存的历史结果仍保留”，`page_review_job_service.py:37`）不会展示给用户。

**并发评估**：双击/重复续跑在客户端（`starting` 防抖）与服务端（状态机幂等，第二次返回 `changed=false`）双重防护，均有测试。理论残余竞态：两个并发 POST 在 SQLite 写串行化下最坏产生一条重复 `RETRY_SCHEDULED` 事件（第二个事务以陈旧内存态重放 cancelled→queued），无状态损坏；单用户本地场景可接受。`_prepare` 的双检锁正确：预检失败不发布半初始化 executor，保持可重试。

### 三、测试缺口

1. 前端无 resume 被 409 拒绝后的 UI 行为测试（推断行为合理：保留取消身份、显示 title、可重试，但未验证）。
2. `decodePageReviewStatus` 无 exhausted（needs_reread + can_reread=false）合法组合用例——正是 D1 的断点。
3. 并发双 resume 的 API 级测试缺失（低风险）。
4. “failed_retryable 中途取消→续跑”后步骤 attempt 计数保留无直接断言（代码路径正确：`_cancel_steps` 将 failed_retryable 一并转 cancelled，resume 只回 queued 不清 attempt）。

### 四、对 Codex 的质疑、决策点与有界问题

- **Q1（语义裁决）**：需求“after resolving, compare exact identity … actual model”——进程缓存身份（当前实现+测试固定）与“续跑时重新解析”两种读法，Codex 意图是哪种？这决定 D2 是记录性观察还是需改为“缓存路由存在时间超过阈值/手写道在场时续跑前重新预检”。在裁决前，安全路径是保持现状并依赖执行期每步 routes 复核兜底。
- **Q2（D1 修复方向）**：是否存在我未见的、会产生 `single_length_recovery` 任务的已发布界面或外部调用方？若无，建议随本迭代一并放宽解码不变式（一行改动+一条用例），避免未来接线时踩中。
- **质疑一处默认假设**：`main_reader_identity` 刻意排除 max_tokens/max_concurrency/fallback/可写道（`page_review_job_service.py:75-79`），使并发数变化后旧 coverage 仍可被下游整理选中。我评估这是合理的（并发不改逐页读语义，coverage 是既成事实），但它意味着“身份”在续跑校验（全量）与下游选择（仅双主读四字段）两个口径不同——若评审其他角色按单一口径核对，请以本差异为准，不是缺陷。
- 最重要异议即 D1：即便今日不可达，契约分叉应在验收记录中显式处置，而不是留给未来接线者。

**未验证项**：未运行任何测试/浏览器/模型调用（读集边界）；前端 e2e 为受控 HTTP mock，不构成临床或视觉验收。本报告为顾问输出，最终验收权在 Codex。
