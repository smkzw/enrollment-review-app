All evidence gathered. The picture is complete — I've verified the transaction/lease/idempotency machinery, the maintenance-loop registration, the recovery scopes, the generic cancel/retry surfaces, and the scope-validation guards that close the duplicate-child window. Now I'll compose the full conference report.

---

# Conference Output: r05-batch-review-design-20260915 - evidence_single_object

## Output

角色：`evidence_single_object`（重要证据审阅）。只读审阅，未修改任何文件，未运行应用/测试/模型。以下先给结论，再给证据链、最小设计、主动质疑、决策点与有界问题。

### 1. 结论摘要

- 提案方向正确：现有 `JobStore`/`JobService`/维护回路已提供批量所需的全部持久化原语（幂等创建、租约、步骤检查点、取消、恢复），最小方案应是**新增一个独立 batch 父任务类型 + 复用现有维护回路**，不需要新队列、新线程、schema 迁移或改动状态机。
- 我找到的最高影响缺陷是**成员工作流身份共享**：`enqueue_review_workflow` 的幂等键是纯内容哈希（不含发起者/批次），批量成员会与用户单独发起的同一 context 工作流**复用同一个 job**，批量取消会连带取消用户单独发起的审核。必须让成员 payload 携带 `batch_job_id`（改变哈希、天然隔离），并配“同 context 已有非终态工作流则拒绝该成员”的提交校验。
- 第二个必须点：runner 每刻恢复（`runner.py:157`）的 scope 由 `executors` 类型表 AND 出来，**不含**非 executor 的父任务类型；现有 `PreparedReviewContinuation` 靠自己在 `__call__` 里再调一次 `recover_expired_jobs` 补上（`prepared_review_workflow.py:157-160`）。批量续算体必须镜像这一调用，否则崩溃后 batch 父任务在两次启动恢复之间卡在 running。
- 第三个必须点：通用取消端点 `/api/v2/jobs/{job_id}/cancel`（`jobs.py:148-150`）直达 `JobService.cancel`→`on_cancelled`→`cancel_workflow_children`，而后者对非 `WORKFLOW_JOB_TYPE` 直接 return（`prepared_review_workflow.py:343`），批量父任务经此路径取消会**孤儿化成员**；镜像的每刻取消清扫（sweep）可以在一个 poll 周期内自愈，但建议同时在 `project_cancelled_evidence_job`（`app.py:198-212`）加一个 batch 分支做到即时取消。
- 对“父持有 batch id 还是 batch 只存 id”的回答：**两者都要、各司其职**——成员 payload 携带 `batch_job_id`（所有权/取消清扫/崩溃窗口发现，镜像 `workflow_job_id` 模式）；batch 步骤检查点按序记录成员 job id（进度与失败可见性）。只存 id 不够：成员已创建但检查点未写入的崩溃窗口里，取消清扫只能靠 payload 反向链接找到孤儿成员。

### 2. 证据基础

初始读集全部读毕，另按需取证：`app/workflow/runner.py`、`app/workflow/states.py`、`app/workflow/recovery.py`、`app/storage/idempotency.py`、`app/services/page_review_runtime.py`、`app/services/predicate_binding_job.py`、`app/services/control_binding_job.py`、`app/services/binding_qualification.py`、`app/services/judgment_content_job.py`、`app/services/review_candidate_scope.py`、`app/services/prepared_review_workflow_view.py`、`app/api/v2/app.py`、`app/api/v2/jobs.py`。确认 `app/` 与 `frontend/src` 中**不存在**任何既有批量审核实现（rg `batch_review|BatchReview|批量审核` 无命中），与提案“批量尚缺”一致。

### 3. 现有可复用边界（证据 → 结论）

**事务边界**

| # | 边界 | 证据 |
|---|---|---|
| T1 | 任务幂等创建：幂等 resolve + job + steps + 依赖 + CREATED 事件单事务；支持调用方事务（`create_job_in_session`） | `job_service.py:103-178` |
| T2 | 子任务入队：各 `enqueue_*` 自开短事务；幂等键=内容哈希，且 `mark_prepared_review_job` 先把 `workflow_job_id` 写进 payload 再哈希 | `control_binding_job.py:56-61`、`predicate_binding_job.py:70-72` |
| T3 | 步骤结果提交：checkpoint+步骤状态+进度+事件同事务，先过租约栅栏 | `jobstore.py:655-705` |
| T4 | 父+子取消单事务：`request_cancel(父)` 与 `_cancel_owned(子)` 同一 `session.begin()` | `prepared_review_workflow.py:351-361` |
| T5 | 父重试先验证父转换再动子，同事务 | `prepared_review_workflow.py:371-375`、`jobstore.py:1228-1259` |

**幂等边界**：`IdempotencyRepository.resolve` 同键同哈希复用、同键异哈希抛冲突（`idempotency.py:111-125`）；`create_job` 对已存在键返回 `created=False` 与原 job_id（`job_service.py:142-147`）。**“子先创建、后记录”的崩溃窗口已被三层机制闭合**（证据）：① 键由 `(workflow_job_id, context, routes, frozen_input)` 确定性导出，重放 `_schedule` 复得同一子 id；② `require_prepared_candidate_scope` 把 facts/规则集 sha/components/控制发布全量钉死在 context 快照上，底层数据漂移时在创建前抛 `ScopeViolationError`（`review_candidate_scope.py:26-50`），不会生成同键异哈希的重复子；③ `_dependencies_complete` 交叉核对检查点子清单与反向链接发现的真实子任务（`prepared_review_workflow.py:265-283`）。批量成员必须复制这三层（成员键含 `batch_job_id`；提交时冻结成员清单；gate 交叉核对）。

**租约边界**：条件更新认领+generation 递增（`jobstore.py:413-473`）；所有写入过 `_lease_guard`（owner+generation+未过期，`jobstore.py:475-494`）；`ACTIVE_LEASE_STATES` 含 `cancel_requested`（`states.py:79`），取消请求不会使进行中的边界提交失权；`finish_success` 用条件 UPDATE 保证完成/取消只有一个库级赢家（`jobstore.py:1100-1131`）。**“等待时不占模型 worker 租约”的既有实现**：父在每次 `_advance` 末尾 `release_deferred` 退回 queued（`prepared_review_workflow.py:216-221`、`jobstore.py:523-548`），等待=重复 claim/poll，不持租约睡眠。批量父照抄即可。

**注册/回路**：单线程 `JobRunner.serve` 每刻先 `_maintenance()`（含 `on_maintenance` 回调）再认领一个 executor 任务（`runner.py:140-166`）；`on_maintenance=PreparedReviewContinuation(...)` 只挂这一个回调（`app.py:350-353`）。认领 scope=`executors 类型表 AND prepared_review_job_scope()`（`runner.py:112-113`）：`WORKFLOW_JOB_TYPE` 与任何新 batch 类型都**不在 executors 中**，模型 worker 永远不会认领父任务——这对批量是正确且免费的安全属性。启动恢复 scope=`prepared_review_job_scope()`，其第一分支“类型不在六个审核类型中”即覆盖新 batch 类型（`review_runtime_ownership.py:17-25`、`app.py:182`），故启动路径无需改动；**每刻恢复**对父任务无效（被 executors AND 掉），只能靠续算体自己补调（`prepared_review_workflow.py:157-160` 正是为此存在）。

**取消面**：专用端点 cancel/retry（`qualified_review.py:163-185`）走 `change_review_workflow`；通用 `/jobs/{id}/cancel`（`jobs.py:148-150`）触发 `on_cancelled` 钩子；通用 `/jobs/{id}/retry` 有按类型注册表 `job_retry_services`（`jobs.py:159-165`、`app.py:260-262`）——这是批量重试的现成注册点。每刻取消清扫 `_cancel_children` 以 `cancel_requested` 父 + 反向链接找未终态子（`prepared_review_workflow.py:136-154`，limit 50），它是通用取消路径的安全网。

### 4. 最小批量设计（建议，不实现）

**新类型与载荷**（新模块 `app/services/batch_review_workflow.py`）：
- `BATCH_JOB_TYPE="batch_review_workflow"`，`BATCH_CONTRACT="batch-review-workflow/v1"`；不加入 executors、不改 `OWNED_TYPES`、不改 `JobStore`。
- 提交事务（镜像 T1+T2）：对每个成员 `{subject_id, review_episode_id, context_id}` 调 `require_prepared_review_intent` 验证 + 查重（同批内 context_id 唯一；同 context 已有非终态工作流则拒收该成员并给出可见理由）；冻结 `members` 列表（含 context_sha256、includes_controls）、`routes`、`task_versions` 于 payload；幂等键 `f"{BATCH_CONTRACT}:{canonical_hash(payload)}"`。
- 步骤：`member_001..member_N` 顺序 `depends_on` 链 + 终步 `collect`（collect 的 gate 检查全部成员终态）。步骤集硬校验镜像 `prepared_review_workflow.py:191-192`。

**BatchReviewContinuation**（镜像 `PreparedReviewContinuation`，小得多）：
- `__call__`：先 `recover_expired_jobs(batch 类型+owner scope)`；再取消清扫（父 `cancel_requested` → 经 `$.batch_job_id` 链接找非终态成员 → `request_cancel(成员)` + 复用 `PreparedReviewContinuation._cancel_owned(成员)` 一并取消成员的模型子任务）；再认领一个 queued batch 父（独立 worker id，如 `f"{worker_id}:batch-review"`）。
- `_advance`：当前步为 `member_k` 且上一成员未终态 → release 轮询；上一成员终态（completed/failed_final/cancelled 均算**编排终态**，结果记入检查点后继续）→ 调 `enqueue_review_workflow(..., batch_job_id=父id, pinned_task_versions=payload["task_versions"])` 创建成员，`complete_step` 落成员 id；`collect` 步 gate 全员终态后完成，`finish_success`。成员创建失败（版本漂移/context 失效/路由变化）→ `fail_step(retryable=False)` + 级联（fail-fast，见 D1）。
- 版本/路由钉死：创建前比对 `current_review_task_versions()`/`routes_provider()` 与 payload 钉值，不等即抛 `ScopeViolationError`（镜像 `prepared_review_workflow.py:54-55、289-291`）。这需要给 `enqueue_review_workflow` 增加**可选参数** `batch_job_id`、`pinned_task_versions`（默认 None，行为不变，约 10 行）。

**取消/重试**：`change_batch_workflow(operation="cancel")` 单事务 `request_cancel(batch)` + 逐成员 `request_cancel` + `_cancel_owned`（镜像 T4）；终态成员自然 no-op（`jobstore.py:1169-1170`），满足“已完成子必须存活”。重试=对 batch 自身 `retry_failed`（只重置失败的编排步骤，已完成成员步骤及其检查点不动）；**成员工作流自身的失败用既有按集重试端点**，批量视图实时读成员状态呈现。

**视图**：新 GET 端点按 `$.batch_job_id` 链接读成员 job 状态 + 父步骤进度（镜像 `prepared_review_workflow_view.py:9-36`）；既有 Job 页天然获得逐成员步骤进度。

**注册（`app/api/v2/app.py` 三处小改 + API）**：① `on_maintenance` 换成依次调用两个续算体的组合函数；② `project_cancelled_evidence_job` 增加 batch 分支（只取消成员，**不得**触发 OCR/revision/normalization 投影）；③ `job_retry_services` 注册 batch 服务。API 在 `qualified_review.py` 或新 router 加 POST 创建（成员列表设上限）、GET、`/cancel`、`/retry`；`PageReviewRuntime` 加两个薄包装（镜像 `page_review_runtime.py:102-125`）。

### 5. 主要缺陷、风险与对策（主动质疑）

1. **[缺陷·证据] 成员身份共享 → 跨请求取消污染**：`enqueue_review_workflow` 幂等键=内容哈希且不含发起上下文（`prepared_review_workflow.py:64-73`）；用户先单发、批量后纳入同一 context → `created=False` 复用同一 job → 批量取消连带取消用户单发审核。**对策（D3）**：成员 payload 加 `batch_job_id`（键随之隔离，按构造消除共享）；并拒绝“同 context 已有非终态工作流”的成员入批（提交时校验，理由可见）。副作用是理论上同 context 双工作流并发被排除——这正是想要的。
2. **[缺陷·证据] 每刻恢复盲区**：`runner.py:157` 的恢复被 executors AND 限制；批量父若续算体不自调 `recover_expired_jobs` 将依赖启动恢复兜底，两次启动之间的崩溃窗口内卡 running。**对策**：续算体 `__call__` 首行镜像 `prepared_review_workflow.py:157-160`。
3. **[缺陷·证据] 通用取消端点孤儿化成员**：`cancel_workflow_children` 对非 WORKFLOW 类型早退（`prepared_review_workflow.py:343`）。**对策**：清扫自愈 + `app.py:198-212` 加 batch 分支即时取消（仅成员，不碰 OCR 投影）。
4. **[质疑提案假设] “顺序创建”的语义未定**：若 member_{k+1} 的 gate 等 member_k **终态**（严格串行，吞吐≈Σ成员时长）；若只等“已创建记录”则成员并行、模型并发失去上界。现有系统没有并发上限机制（`max_parallel_steps` 只管单任务步骤）。**建议严格串行**为最小默认（D2），需要并行时再引入上限，属扩张。
5. **[质疑] 级联失败 vs 逐成员可见**：`fail_step` 默认 `_cascade_final_failure` 下游全灭（`jobstore.py:813-822`）。若成员**工作流失败**也走 fail-fast，一批 50 人在第 3 人失败即整批停，与“失败成员逐个可见、编排完成≠临床接受”的语义冲突。**建议区分**：创建/环境类失败=fail-fast 级联；成员工作流终态失败=记入检查点、继续编排（D1）。
6. **[风险] 崩溃中断步骤的恢复语义**：批量成员步骤沿用默认 `max_attempts=1, retryable=False`，崩溃即 failed_final+级联，需人工重试——与现有 prepared-review 完全一致（保守、可见），且成员创建幂等使人工重试安全。不引入自动重试，保持一致（可选方案已注明）。
7. **[次要·推断] 轮询成本**：父任务每刻 claim/release 一次 + json_extract 无索引扫描；现有单集工作流已如此，本地 SQLite + 成员上限（建议 ≤50，对齐 `prepared_review_workflow.py:146` 的 limit 50）下可接受；仅为记录，不构成设计变更。
8. **[确认提案正确处]** “批量完成=编排完成”“不自动发布”“不新增队列”“恢复时不得动态替换 source context”均与既有机制吻合：发布保持每集独立端点（`qualified_review.py:71-88`）；context 由 sha 钉死且漂移即拒（`prepared_review_workflow.py:95-96`）；OCR 重置/重审/冻结导出确应独立类型，不并入本批。

### 6. 决策点与有界问题（请 Codex 裁决）

- **D1** 成员工作流失败语义：继续编排并记录（我的建议）还是整批 fail-fast？影响 `collect` gate 与级联使用方式。
- **D2** 严格串行 vs 有界并行（后者需新增并发上限，属扩张；我的建议=严格串行）。
- **D3** 成员键含 `batch_job_id` 并禁止同 context 双活工作流（我的建议） vs 直接采纳既有同键工作流（简单但取消耦合，我反对）。
- **D4** 成员数上限与查重策略（建议 ≤50、批内 context 去重、跨批非终态拒收）。
- **D5** 用户中途单独取消某成员：视为该成员编排终态“已取消”、批量继续（我的建议）——请确认产品预期。
- **Q1** 批量是否限定单项目内（context→episode→subject→project 链）？跨项目提交是否需要拒绝？（影响提交校验是否加项目一致性检查。）
- **Q2** 严格串行下整批墙钟≈N×单集时长，对真实 N（如 20–50 集、每集数十分钟）是否可接受？若不可接受，D2 需前移。
- **Q3** 批量层是否需要暴露“重试失败成员”（聚合触发既有成员重试），还是保持成员重试只在单集界面（Phase7 提到“粒度重试”，最小方案建议后者，Job 页天然有步骤粒度）。

### 7. 必要范围 vs 不必要扩张

**必要**：新 batch 服务模块；`enqueue_review_workflow` 两个可选参数；`app.py` 三处注册小改；4 个 API 端点 + runtime 薄包装；成员身份/恢复/取消三项修正（§5.1–5.3）。
**不必要（明确不做）**：新队列/线程/服务进程；schema 迁移；改 `JobStore`/`JobService`/状态机/`OWNED_TYPES`/executors；把批量泛化成“任意任务批量”抽象（OCR 重置、重审、冻结导出将来各自独立类型）；批量层任何发布/临床判断；移动端/窄屏变体。

### 8. 证据/推断/建议/不确定性声明

- **证据**：§2–§3 及 §5.1–5.3 全部带文件：行号，静态阅读得出，未执行验证。
- **推断**：SQLite 单写者下的并发安全、`frozen_input` 跨进程哈希稳定性（依赖稳定 DB 查询序）、轮询成本量级——基于代码结构推断，未实测。
- **建议**：§4 设计与 §5 对策、§6 倾向。
- **不确定性**：前端批量面板交互（本审阅未覆盖前端）；`docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` §6.1/§17 未在初始读集中，若其中有既定批量约束请 Codex 指出，我可同会话补审；成员失败“继续编排”下批量最终态为 completed 但含失败成员，UI 措辞需 Codex 定（避免“批量成功”误导，属产品文案而非本审阅范围）。

本报告为工程顾问意见，不构成临床/监管/用户验收结论；最终采纳与验收归 Codex。
