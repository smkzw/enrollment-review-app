# Conference Output: r05-batch-review-design-20260915 - evidence_single_object

## Output

同会话第二轮：对已落地的批量审核后端实现做只读正确性复审。未运行任何代码、未修改文件、未调用模型/数据库/浏览器。结论先行：**整体架构与已定决策一致，八个指定检查点中七个经源码验证成立；但存在 1 个高优先级必修缺陷（取消路径不容错，单条坏记录会令取消整体失败并持续饿死单成员续算）和 2 个中优先级必修缺陷（轮询步骤的错误归因、重复工作流的 TOCTOU 竞态），另有 1 项建议的提交预检。** 以下均为静态阅读证据，实现从未运行，任何“验证成立”均指标源码级推演，非运行时验证。

### 1. 已验证成立的检查点（证据）

**租约取消竞态** — 成立。`_advance` 末事务在持租约状态下检查 `row.cancel_requested` 并做边界取消 + `cancel_owned`（`batch_review_workflow.py:226-228`）；异常路径同样先判取消（245-250）。`request_cancel` 对 running 任务转 `cancel_requested` 且保留租约（`jobstore.py:1189-1201`），而 `ACTIVE_LEASE_STATES` 含 `cancel_requested`（`states.py:79`），边界操作不失权。queued 态直取消由 `project_cancelled_evidence_job` 的 batch 分支同步处理（`app.py:198-203`，先于 OCR/revision 投影 early-return）。`release_deferred` 与 `request_cancel` 的交错在 SQLite 单写者下串行化，两条顺序均收敛（释放后取消→直取消+回调；取消请求先落→下刻边界取消+清扫）。

**子创建后崩溃** — 成立，双重防护。① 反向链接发现：`owned_workflows` 经 `$.batch_job_id` 找到已建成员并跳过重建（`batch_review_workflow.py:211-214, 222-225`）；② 幂等重放：成员 payload 含 `batch_job_id` 后才计算内容哈希键（`prepared_review_workflow.py:76, 86-88`），即使重入 enqueue 也复得同一 job。且批量步骤从不遗留 running 态——`start_step` 与 `complete_step`/`fail_step` 同事务（232-236, 252-253），恢复器的 `_reset_interrupted_steps` 找不到 running 步骤，不会触发尝试预算终败（`jobstore.py:1450-1516`）。恢复链完整：续算体自调 `recover_expired_jobs`（163-166）补上 runner 每刻恢复对非 executor 类型的盲区。

**重复工作流（已实现部分）** — 基本成立。同批重放同键复用；跨所有权活跃拒绝双向生效（`prepared_review_workflow.py:77-85`：单发遇批成员、B2 批遇 B1 批成员均抛“同一份资料已有其他审核正在进行”）；批内 `context_id` 与 `review_episode_id` 双去重（`batch_review_workflow.py:48, 56-57`）。残留竞态见 R3。

**检查点** — 成立。每成员检查点 `{workflow_job_id, context_sha256, member_state, clinical_adoption: False}` 每刻经 `validate_completed_members` 全量复核（98-111），视图再次交叉核对（`batch_review_view.py:24-28`）。

**无意外临床完成** — 成立。批量 `finish_success` 仅表示编排完成（237-238）；成员任何终态（含 failed_final/cancelled）都记入检查点后继续（229-236 的 `TERMINAL` 集合）；批量代码无任何 publish 调用，发布仍走每工作流独立端点（`qualified_review.py:71-88`）；视图显式 `clinical_adoption: False`。

**不阻塞单成员续算** — 成立（除 R1 场景）。成员工作流仅由既有 PreparedReviewContinuation 与 run_once 推进；批量 `_advance` 只做 DB 操作且每轮 `release_deferred` 归还租约；`continue_reviews` 中批量先于单成员执行（`app.py:358-360`）但两者互不持有对方租约。

**配置不可用时取消** — 成立。取消路径不取 routes（`batch_reviews.py:52` 传 None；`change_batch_review` 取消分支不触碰 routes，`batch_review_workflow.py:132-135`）；清扫与恢复不依赖配置；配置坏时重试在 `routes_provider()` 抛 503 处干净失败、无状态变更。但轮询中的配置检查归因有缺陷，见 R2。

**读 API 源身份** — 成立。GET 逐成员复核 context 的 sha/项目/受试者/节点绑定（`batch_review_view.py:16-21`）；`_raise_translated` 对未知异常原样上抛、不吞（`review_action_worklist.py:149-154`）；`context.subject.subject_code` 字段真实存在（`review_context_v2.py:79` + `review.py:78-80`）。批 payload 的 `project_id` 与成员 project 一致性在提交、创建（`require_batch_member`）、视图三处校验。

### 2. 必修缺陷（按严重度）

**R1（高）取消路径不容错 → 取消整体失败 + 持续饿死全部续算。**
`owned_workflows` 对任何无法核验或不一致的关联成员直接抛异常（`batch_review_workflow.py:78-85`），而 `cancel_owned`（90-95）、`change_batch_review` 取消分支（133-134）、`cancel_batch_children`（121-122）都无逐条容错。后果链：① 单条成员 payload 损坏（`verify_payload_sha256` 抛 `PersistedContractInvalid`）→ 整个取消事务回滚，**连同 `request_cancel(batch_id)` 一起回滚**——用户连把批量标记为取消都做不到；② `__call__` 清扫循环内 `material(session, batch_id)` 无 try/except（172-174），同缺陷使清扫+认领事务整体失败，且因 `continue_reviews` 先批量后单成员的顺序（`app.py:358-360`），异常上抛后**该刻 PreparedReviewContinuation 也被跳过**——一条坏批量记录会每个维护刻重复触发，永久停摆所有单成员工作流推进。既有实现明确具备此容错：`_children(for_cancellation=True)` 逐条捕获并“保留该记录并停止其他已确认任务”（`prepared_review_workflow.py:109-122`），`_cancel_children` 对父记录逐条捕获（149-153）。
**修正**：给 `owned_workflows` 增加 `for_cancellation=True` 模式（校验失败→log+跳过该成员，取消其余已核验成员）；`__call__` 清扫对每个 batch_id 包 try/except（捕获 `PersistedContractInvalid` 与 `ScopeViolationError`，log 后继续）；`change_batch_review` 取消路径确保 `request_cancel(batch_id)` 与尽力而为的成员取消分离（先落取消标记，成员取消失败不回滚标记）。禁止为批量任务触发 OCR/revision/normalization 投影的现状保持不变。

**R2（中）轮询步骤的错误归因：配置/版本漂移在错误时机致命失败当前成员。**
`_advance` 在判断“本刻只是轮询已有成员”之前就校验 live `current_review_task_versions()` 与 `routes_provider()`（203-207）。成员 k 已在跑、只是等待终态时，一次瞬时配置中断或中途代码升级即令 member_k 步骤 fatal+级联（251-255）→ 批量 failed_final，而成员 k 继续运行且未被取消（失败路径不调 `cancel_owned`）——形成“批量已失败+成员活跃”的不一致观感，且配置恢复后也必须人工批量重试。对照单成员路径：routes 只在 `_schedule` 创建子任务时校验（`prepared_review_workflow.py:289-291`），轮询路径（`_dependencies_complete`→release）不校验。且创建时的钉版校验已由 `require_batch_member` 承担（`batch_review_workflow.py:41-43` 比较 payload 钉值）——203-207 对创建是冗余、对轮询是误伤。
**修正**：把 203-207 的版本/路由校验移入 `if child_id is None:` 分支（仅创建前执行）；轮询刻只做 context/链接/检查点完整性检查。批量重试入口的钉版校验（138-140）保留不变。

**R3（中）活跃拒绝的 TOCTOU：并发下仍可产生同 context 双活跃工作流。**
`enqueue_review_workflow` 的活跃扫描是同事务内 select-then-insert（`prepared_review_workflow.py:77-86`），无数据库约束（决策禁止迁移）。批量续算线程与 API 线程同时为同一 context 创建时，两个事务可在彼此提交前完成扫描，产生一个批成员 + 一个单发工作流同时活跃；两者各自可发布到同一 `review_run`。单机单用户下概率低，但“differently-owned 不得同时活跃”是被明确决策为不变式的，应当强制而非依赖时序。
**修正（无迁移约束下）**：进程级互斥——单进程 FastAPI 应用，在 runtime 或模块层用一把 `threading.Lock` 串行化 `enqueue_review_workflow` 的“扫描+创建”段即可闭合；或创建提交后同事务复核一次活跃集（排除自身 job_id，命中即抛）。若 Codex 决定接受为已记录的残留风险，须在文档显式声明。

**R4（建议，非正确性）提交时不预检成员活跃冲突。**
`enqueue_batch_review`（47-67）不检查成员 context 是否已有活跃工作流，冲突要到该成员的顺序轮次才暴露——第 30 人在前 29 人完成后才失败。补一条 `job_type=WORKFLOW_JOB_TYPE AND state NOT IN (终态) AND $.review_context_id IN (本批 contexts)` 查询即可在提交时 fail-fast 并给出逐成员理由。运行时校验仍是权威（提交后仍可能新增冲突），此为体验改进。

### 3. 次要事项（不阻塞）

- `batch_reviews.py` POST 缺 `status_code=201` 与“未新建则 200”的既有惯例及 response_model（对照 `qualified_review.py:91-101`）；`created` 已在 body 中，功能无损。
- 无批列表端点（前端发现 batch id 需要；可后置，前端尚未接线）。
- `TERMINAL` 字面量（`batch_review_workflow.py:23`）与 `workflow/states.py:57-61` 的 `TERMINAL_JOB_STATES` 重复定义，宜改为导入防漂移。
- 视图 items 未含 `context_id`（前端深链可能需要）；成员经单集重试后 live `state` 与 `recorded_state` 会合法分叉，前端须同时展示两者。
- `_advance:223` 的 `owned[member["context_id"]]` 直接索引，链接缺失时抛 KeyError 而非可读的 ScopeViolation（仅可调试性）。
- 清扫无 `.limit()`（既有用 50，`prepared_review_workflow.py:146`）；当前 ≤50 批×50 成员规模无碍，量大后补。
- 两个并行批（不同 context）会交错推进，模型并发仍受单 runner 认领与单任务步上限约束——可接受，建议在文档注明。

### 4. 决策符合性核对

| 决策 | 状态 | 证据 |
|---|---|---|
| 仅同项目 | ✔ | 提交校验 `batch_review_workflow.py:53-54`；`require_batch_member`/视图复核 |
| 严格串行成员 | ✔ | depends_on 链（64-66）+ 步骤完成以成员终态为门（229-236） |
| 成员三终态记录后继续 | ✔ | `TERMINAL` 含 failed_final/cancelled → complete_step 记 `member_state` 后续成员推进 |
| 创建/资料/配置失败可见停止 | ✔（归因时机见 R2） | fatal fail_step+级联→批量 failed_final，detail 为中文原因（251-255） |
| 不自动发布 | ✔ | 批量代码零 publish 引用 |
| 批所有权隔离取消 | ✔（残留 R3） | `batch_job_id` 入 payload→独立幂等键+反向链接；单发双向拒绝异属活跃 |
| 上限 50 | ✔ | `:48` + API `max_length=50`（`batch_reviews.py:24`） |
| 成员重试独立、批量重试仅编排 | ✔ | `change_batch_review` retry 只 `retry_failed(batch)`（141）；成员重试仍走 `change_review_workflow` |
| 无新队列/迁移 | ✔ | 仅 payload json 链接，无 schema 变更；批量类型不在 executors（`app.py:283-330`），run_once 永不认领 |

### 5. 不确定性与未验证项

- 实现从未运行：上述全部为静态推演，SQLite 并发交错结论基于单写者模型的推断，未经实测；无任何针对批量模块的测试（`tests/` 中 `batch` 命中仅为无关的 legacy 脚本 `scripts/d001_phase2_batch_review`）。
- `continue_reviews` 异常顺序饿死（R1②）的持续性与 runner 捕获点（`runner.py:164-166`）为推演，建议修复后以故障注入验证。
- 前端未接线，视图字段充分性（列表发现、context_id 深链、双状态展示）待前端接入后复核。
- R3 竞态窗口大小未测量；若采纳进程锁方案，需确认 uvicorn 单进程部署假设持续成立。

**给 Codex 的净结论**：R1 必须修复后此实现才达到“可运行验证”的门槛；R2、R3 建议与 R1 同批修复（改动均局部于 `batch_review_workflow.py` 与 `enqueue_review_workflow`）；R4 可选。不构成最终验收，临床/产品接受归 Codex。
