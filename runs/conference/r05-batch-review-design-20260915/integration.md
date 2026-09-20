# Conference Output: r05-batch-review-design-20260915 - evidence_single_object

## Output

同会话第三轮：复审 R1/R2/R3 修复与全新前端集成，端到端源码契约审查。只读，未运行任何代码。结论：**三项修复均已按声明的方向落地且与既有仓库模式一致；十二个指定检查点中十个源码级成立；发现 2 个必修缺陷（D1 坏记录毒化近期列表并连带丢失取消入口；D2 请求键仅存内存，刷新后重击会产生重复批次与重复准备记录）**，另有 3 项小改进。以下为证据与最小修正。

### 1. 上轮修复验证（证据）

- **R1** ✔：`owned_workflows(for_cancellation=True)` 对无法核验的成员记日志并跳过（`batch_review_workflow.py:71-94`）；清扫逐批捕获 `PersistedContractInvalid`/`ScopeViolationError` 并继续（180-185）；`continue_reviews` 用 try/finally 保证 PreparedReviewContinuation 总被调用（`app.py:358-362`）。残余小项：`_advance` 异常处理器内（258-261）`material` 再抛会回滚同事务的 `cancel_at_boundary`，但随后由续算体自身的 `recover_expired_jobs`→`cancel_expired_cancel_requests`（171-174）在租约到期后收敛，可接受。
- **R2** ✔：版本/路由校验已移入 `if child_id is None:` 创建分支（221-226）；纯轮询刻（240-241 release）不再因配置漂移失败。
- **R3** ✔（附一条首跑验证点）：`session.execute(text("BEGIN IMMEDIATE"))` 为 `session.begin()` 后首条语句（`prepared_review_workflow.py:72-73`），与仓库既有配方一致（`evidence_activation_service.py:120-126`、`evidence_api_command_service.py:226-231`；二者以 autobegin 调用，新写法显式 begin，两种形态在 pysqlite 延迟 BEGIN 行为下等价，不匹配时会是响亮报错而非静默错账）。所有 `WORKFLOW_JOB_TYPE` 创建都经此单函数，扫描+插入对并发写者原子，TOCTOU 关闭。

### 2. 检查点核验（成立项）

| 检查点 | 结论 | 关键证据 |
|---|---|---|
| UI 准备前冻结/当前指针 | ✔ | 面板逐选项重取 episode 并比对 `activeEvidenceSnapshotId`/`activeEvidenceProcessingRevisionId`，漂移即报“所选资料已变化”（`BatchReviewPanel.tsx:90-94`）；`prepare` 钉全量 authority（95-100）；指针源自 episode 活跃字段（`review_action_worklist.py:74-75`）；DTO 字段齐备（`catalogTypes.ts:40-57`） |
| 选择变化 | ✔ | 签名含指针，指针变=新意图=新键（84）；顺序由后端排序决定且确定（`project_evidence_overview.py:38-39`、`repositories.py:2116-2121`）；勾选上限 50（`ReviewProjectPage.tsx:50`） |
| 卸载/重连 | ✔ | AbortController+定时器清理、按 URL `batch` 参数重挂载、4s 轮询+失败退避（`BatchReviewPanel.tsx:24-42`）；`updateParams` 为合并语义保住 project 等参数（`router.tsx` patch 实现） |
| 逐节点显式身份 | ✔ | 成员=(subject, episode)，episodeId 全局唯一且前后端双去重（`batch_review_workflow.py:57`、`batchReviewHttp.ts:33`） |
| 记录态 vs 当前态 | ✔ | 两列分列 live state 与 checkpoint member_state（`BatchReviewPanel.tsx:63-64`、`batch_review_view.py:55-56`）；客户端仅接受终态 recorded_state（`batchReviewHttp.ts:39`） |
| 发布深链 | ✔ | `#/reports?…&workflow=` 被 `ReportsPage.tsx:237-238` 消费进 `PreparedReviewPanel`（按 workflow 重挂载）；批成员是普通 WORKFLOW_JOB_TYPE，读/发布/单独取消重试均走既有端点 |
| 批完成≠临床决定 | ✔ | 完成文案“本批处理已结束，请查看逐项结果”（:60）；`clinical_adoption:false` 前后端双重强制（`batch_review_view.py:58`、`batchReviewHttp.ts:28`）；无任何通过/符合计数 |
| Recent20 预览语义 | ✔ | 后端取 21 返 20+has_more（`batch_review_view.py:14-20`）；标签仅“第N批·节点数·状态”；客户端校验 ≤20（`batchReviewHttp.ts:53`） |
| 费用估算诚实声明 | ✔ | “本批暂未提供耗时与费用估算。”（`BatchReviewPanel.tsx:112`） |
| 不混入估算器/导出/OCR重置 | ✔ | 审阅范围内无任何此类代码或入口 |

### 3. 必修缺陷

**D1（必修，后端+前端联动）：单条坏记录毒化整个近期列表，且视图失败时批量取消入口消失。**
`recent_review_batches`（`batch_review_view.py:13-20`）对每批调用严格版 `batch_review_view`，而后者在成员链接损坏（`owned_workflows` 严格抛错，:27）、检查点不一致（:45-49）、成员 context 漂移（:38-42）乃至 `_workflow_stage_label` 缺阶段名（`review_action_worklist.py:68-80` 无回退，抛 `ReviewHistoryIncompleteError`）时整体抛错——**一批坏，20 批全 409**，面板近期列表整体 ErrorState（`BatchReviewPanel.tsx:113`），用户选不了任何批次。单批 GET 同理整体失败，此时 `data===null` 而“停止本批”按钮渲染以 `data` 为前提（:54）——尽管后端取消路径已容错、仅需 batchId，用户却从 UI 失去了停止该批的入口。这正命中“损坏的已取消记录不得阻塞其他记录”的要求。
**最小修正**：(a) `recent_review_batches` 逐项 try/except，失败项降级为 `{job_id, project_id, state, items: [], clinical_adoption: false, failure_detail: "该批记录暂时无法核实"}`；(b) `batch_review_view` 改用容错版 `owned_workflows`（返回已核实集合+损坏成员 id），损坏成员以 `state:"unverifiable"`、`workflow_job_id:null` 呈现而非整体抛错（`_advance` 内的严格校验保持不变，推进仍失败关闭）；(c) 前端同步：`parse` 允许 `items.length===0` 仅当 `failure_detail` 非空，`state()` 接受 `"unverifiable"` 并加标签“记录待核实”，且只要 `batchId` 存在且批次非终态就渲染停止按钮（取消端点只需 batchId）。这是同一契约的两侧改动，须一起落地。

**D2（必修，前端）：请求键仅存内存——不确定应答后刷新页面再重击=重复批次+重复准备记录。**
`request.current`（`useRef`）按签名缓存 `crypto.randomUUID()`（`BatchReviewPanel.tsx:76,84`）。挂载丢失（F5、离开页面、应用重启）后键即失效：重击生成新键→后端幂等键 `{CONTRACT}:{project_id}:{request_key}` 不同→**同成员第二批次被创建**；活跃拒绝机制会把第二批打成可见的“未完成”批次（成员创建被拒，`prepared_review_workflow.py:78-86`），同时 `${key}:${episodeId}` 的 prepare 重放也失效，为同一节点再冻结一批重复 context。这直接违背“不确定应答回来的重击幂等”检查点（组件存活期内是幂等的，跨挂载不是）。
**最小修正**：键按选择签名持久化——`sessionStorage` 以 `projectId+signature` 为键存取 requestKey（生成时写入、start 时先查），无需后端改动、无需新 UI；可保留最近约 8 条防膨胀。中途卸载的场景（`operation.current?.abort()`，:78）同样被此修复覆盖：重挂载后重击会重放同一批 prepare 并复得原 context，批次只建一次。

### 4. 建议项（非阻塞）

- **D3** 签名改为对 choices 按 episodeId 排序后再 `JSON.stringify`（一行）：当前顺序稳定性是两个仓储排序的实现细节，显式排序让幂等契约自证。
- **D4** `BatchProgress` 连续 4 次失败后轮询永久停止（:36-37），仅剩通用错误文案；加一句“已暂停自动刷新”提示避免“卡住”观感。
- **D5** `recent_review_batches` 每次调用做 20×全量 `batch_review_view`（每批重验全部成员 context+检查点），且面板在每次 batchId 变化时重取（:73）。本地单用户可承受，但它是该流程最重的端点；近期列表可瘦身为 `{job_id, state, member_count}` 免逐成员校验，选中时再载全量视图。做 D1(a) 时可顺带。

### 5. 首跑验证点与未验证项

- `BEGIN IMMEDIATE` 与显式 `session.begin()` 的组合（R3 新写法）与两个既有调用点（autobegin 形态）静态等价，但该组合此前未在本仓库运行过——首次运行冒烟时确认无误即闭环；若 SQLAlchemy 升级改变 pysqlite BEGIN 发射行为，此处会响亮失败而非静默错账。
- 全部结论为静态源码推演；按约束未运行编译、测试或应用。D1/D2 修复后建议以故障注入（损坏一条成员 payload、刷新后重击）做针对性验证——此为后续执行任务，非本审阅范围。
- 前端仅审查了列出的六个文件；`PreparedReviewPanel` 对批次成员工作流的完整渲染行为（发布按钮、进度标签）依赖既有代码，本轮未展开。

**净结论**：D1、D2 修复前不建议进入用户可见验证；两者均为局部修正（一个视图/列表函数对 + 一个键持久化），不涉及新编排层或无关文件。R1/R2/R3 修复接受。不构成最终验收，临床/产品接受归 Codex。
