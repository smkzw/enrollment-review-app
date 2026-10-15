# 执行输出：r05-batch-ocr-20260915 - worker_01

## 边界与上下文检查

- **回退声明：** 声明的首要执行者 (`codebuddy/codebuddy-cli/deepseek-v4.1-flash`) 在可恢复会话存在前不可用；此会话以声明的 `zcode`/`GLM-5.3-Flash` 回退身份，在当前北京的 `off_peak` 时段内运行。相同的边界角色、源列表、输出路径、质量门和仅执行（非会议）协议均已保留。能力限制：遵照任务禁止要求，我**没有**运行测试、应用程序、数据库或模型；未声称运行时验收。代码为手动编写；仅运行了明确允许的检查（`py_compile`，`git diff --check`）。
- 上下文/计划文件与分配的源内容一并优先读取。仅写入三个授权路径；未修改 app.py/API/UI、批量审查模块、文档或测试。未安装依赖项，未进行 Git 清理。

## 已执行工作

完全按照实现契约实现了批量原件重处理后台和读取投影。

**1. `app/services/evidence_reprocessing.py` (最小化添加/重构，保留了单任务语义):**
- `ReprocessingInput` 增加了可选的 `batch_job_id: str | None`，并使用 `@model_serializer(mode="wrap")` 在其为 None 时移除该键 —— 单任务负载字节、哈希和幂等性保持不变；额外字段保持 `"forbid"`，以便现有执行器验证能够通过。
- 提取了 `create_reprocessing_child_in_session(session_factory, adapter, session, *, project_id, subject_id, review_episode_id, snapshot_id, complete_id, attempt_namespace, batch_job_id=None, expected_profile_sha256=None)` —— 共享的会话内创建者（调用者持有 `BEGIN IMMEDIATE`）：源标识通过 `_source`，命名空间幂等性查找（现有 → 验证负载相等性 → 返回），当前指针 + ACTIVE 状态检查，所有权感知挂起冲突检查，然后 `create_job_in_session`。批量路径根据冻结的配置文件构建预期负载（现有子任务不会因轮询期间的实时配置文件漂移而不匹配），并且仅在创建新子任务之前将实时适配器与 `expected_profile_sha256` 进行比较。
- 新的 `pending_reprocessing_conflict(session, *, snapshot_id, batch_job_id)`：单任务（`None`）与任何挂起任务冲突（确切保留先前消息）；批量成员仅与不在本批次的任务冲突（损坏的挂起负载计为冲突）—— 从不取消或采用独立创建的任务。
- `enqueue_reprocessing` 现在是对辅助程序的轻量封装；检查顺序和所有面向用户的消息与以前完全一致。

**2. `app/services/batch_evidence_reprocessing.py` (新建):** 父作业类型 `batch_evidence_reprocess`，契约 `batch-evidence-reprocess/v1`，所有者 `batch-evidence-reprocess/v1`；`BatchReprocessingError(ReprocessingError)` 代码为 `EVIDENCE_REPROCESS_BATCH_REJECTED`。
- `enqueue_reprocessing_batch(session_factory, adapter, *, project_id, members, request_key)`：精确键成员的 1–50 个唯一节点（剧集/快照/完成唯一性），在创建前对所有成员进行源 + 当前指针 + 挂起冲突验证；冻结 `{subject_id, review_episode_id, snapshot_id, complete_id}` + `profile_sha256`；幂等键 `f"{CONTRACT}:{project_id}:{request_key}"`；链式 `member_{index}` 步骤。
- `material`、`owned_children`（取消路径跳过 + 记录无法验证的成员，以便损坏的所有权不会阻止可证明拥有的兄弟节点；否则引发异常）、`validate_completed_members`（检查点 ↔ 拥有的子任务 ↔ 冻结标识，`activated` 必须为 False）、`cancel_owned`。
- `_create_member_child`：子任务创建在同一个 `BEGIN IMMEDIATE` 下原子性地重新检查父级取消/状态、成员索引边界、冻结配置文件和新鲜源。子任务保留 `job_type="evidence_reprocess"`（由现有执行器运行），负载携带 `batch_job_id`；命名空间 = 派生自 batch_job_id + 成员标识的 `canonical_hash`，因此批量尝试永远不会与单个请求键冲突。
- `BatchReprocessingContinuation(session_factory, adapter, *, worker_id).__call__(runner)`：所有者范围内的过期租约恢复，针对取消的父级处理 `cancel_owned`（每个批次的窄范围捕获，因此一个损坏的批次不会导致其他任务无法进行），声明最旧的排队父级，然后在 `runner.lease_heartbeat` 下推进一个边界：创建一个子任务（冻结配置文件仅在新子任务之前检查），通过 `release_deferred` 等待终端，诚实地记录终端失败/取消的子任务状态（`member_state`，`activated: False`）并继续下一个成员；创建/完整性失败 → `fail_step(retryable=False, BATCH_REPROCESS_CONTINUATION_FAILED)`，级联显式停止未启动的其余部分，同时已完成的部分保持冻结；当所有步骤完成时 `finish_success`（仅处理完成）。
- `cancel_batch_children(session_factory, batch_id)`（如果父级不是此类型则返回 False），`change_reprocessing_batch(..., operation)`（取消；如果 `cancel_requested` 则禁止重试，验证相同的冻结配置文件），`BatchReprocessingRetryService(session_factory, adapter).retry(batch_id)`。

**3. `app/services/batch_evidence_reprocessing_view.py` (新建):** `recent_reprocessing_batches`（轻量级父级元数据，偏移量上限 ≤100000，页面 20 + `has_more`，`unavailable_count` 用于损坏的行 —— 从不伪造空成功）和 `batch_reprocessing_view`（验证项目，通过 `_source` 验证每个成员的冻结标识，子任务所有权和完成检查点；已完成的子任务修订版本通过命名空间/契约/`activated=False`/修订标识检查进行验证；暴露 `state` 与 `recorded_state`，因此子任务后来的手动重试永远不会与批量结果混淆；`activated` 恒为 False；`failure_detail` 来自最后一个延续失败事件）。

**所有者集成界面（根据契约所有者处理 app.py/API/UI）：** 注册 `BatchReprocessingContinuation(session_factory, app.state.evidence_reprocess_adapter, worker_id=...)` 到 `on_maintenance` 链（与 `BatchReviewContinuation` 并行）；在 `project_cancelled_evidence_job` 中添加 `cancel_batch_children`（返回 False 时回退到现有链）；为 API 创建暴露 `enqueue_reprocessing_batch` / `change_reprocessing_batch` / 两个视图函数；可选地在 `app.state.job_retry_services` 下注册 `BatchReprocessingRetryService`；不要在 `runner` `executors` 映射中注册 `batch_evidence_reprocess`（仅通过延续进行推进）。

## 工件与证据

- `app/services/batch_evidence_reprocessing.py` (新建，约 290 行)
- `app/services/batch_evidence_reprocessing_view.py` (新建，约 130 行)
- `app/services/evidence_reprocessing.py` (已修改：serializer + 两个新函数 + `enqueue_reprocessing` 重构；执行器、`reprocessing_view`、`ReprocessingRetryService` 未动)
- 读取的来源：`evidence_reprocessing.py`，`batch_review_workflow.py`，`batch_review_view.py`，`workflow/jobstore.py`，`workflow/runner.py`，`workflow/recovery.py`，`workflow/states.py`，`services/job_service.py`，`services/review_runtime_ownership.py`，`services/prepared_review_workflow.py` (子任务创建 + 批量成员资格模式)，`storage/idempotency.py`，`services/evidence_app_errors.py`，`api/v2/app.py` (仅集成点)，`domain/contracts/common.py`，`domain/contracts/evidence.py` (省略 none 序列化器先例)，`.trellis/spec/backend/{index,persistent-jobs}.md`，`docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` §17 + §17.6 批量契约 (2026-09-15) + 设计 §17 (批量 OCR = 剩余的“批量OCR新修订”)。

## 命令与观察

- `python3 -m py_compile` 在所有三个文件上 → `PY_COMPILE_OK`。
- `git diff --check` → 清洁 (`DIFF_CHECK_OK`)。
- AST 未使用导入扫描 → 所有三个文件均无问题。
- 观察：`git status` 报告 `app/services/evidence_reprocessing.py` 为未跟踪 (`??`) —— 这是预先存在的分支状态（该文件从未在此工作树上提交），并非由我的编辑引起；其更改无法通过 `git diff` 查看，因此 Codex 应审查完整文件。
- 仅静态验证追踪（不允许运行时）：子任务创建原子性（所有者重新检查 + 配置文件 + 指针在同一个 `BEGIN IMMEDIATE` 下），单任务负载兼容性（省略 none 序列化器从 `model_dump` 中移除该键，因此旧的和新的单任务负载相等），`claim_next` 从不声明父级（类型不在执行器映射中），子任务由主运行器范围 (`prepared_review_job_scope` 通过 `not_in`) 恢复，`release_deferred` 将父级返回为 `queued`（成员步骤从不可重试失败）。

## 阻塞或缺失环境

无。禁止运行测试/模型/数据库是根据合同执行的，而非环境故障。

## 重跑请求或下一步

无需重新运行；工作在分配的范围内完成。所有者的剩余集成：app.py 连接（延续、取消回调、重试服务注册），API 端点 + 前端，以及延迟的运行时验证（子任务创建原子性、取消/重试/恢复生命周期、跨批次成员重叠、视图分页下的孤立/损坏行） —— 根据计划，全部推迟到所有者的验收测试。Codex 的一个设计说明（非阻塞）：入队时的挂起冲突检查是建议性的（TOCTOU）；权威门是 `BEGIN IMMEDIATE` 下的子任务创建，根据契约，它会明确停止未启动的其余部分 —— 如果所有者更倾向于在提交时出现更少的批次中期停止，那么唯一的选择是排队成员，而不是停止，这需要明确的合同变更。
