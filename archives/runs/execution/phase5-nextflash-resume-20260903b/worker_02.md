核对完毕，证据链闭合。整理最终对账报告。

# 执行输出： phase5-nextflash-resume-20260903b - worker_02

## 边界与上下文检查

- 本 pass 只执行任务 2：**只读**核对 SAR 31001 作业、快照、租约、配置状态，给出旧 `cancel_requested` 作业合法终态对账与新受控筛选/基线作业入口；未启动任何任务、未写任何数据库、未做临床验收判断。
- 运行库不在工作树默认位置：工作树 `data_v2/enrollment-review-v2.sqlite3` 只有 schema（哈希 `35c8709b…`，与暂停检查点记录不符）。通过暂停检查点记录的主库哈希 `2d197745…` 定位到真实运行库：
  `artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/enrollment-review-v2.sqlite3`（主文件 SHA-256 至今仍等于暂停时记录值，暂停后的事务在 41KB WAL 中未落回主文件——与今晨 08:26 服务重启一致）。
- 只读手段：① 文件哈希比对；② Python sqlite3 backup API（只读 URI 源）取一致性快照到 `/tmp/worker02_ro/fresh_snapshot.sqlite3` 后查询，`PRAGMA quick_check=ok`；③ 对活动服务仅发 HTTP GET。未调用任何写工具 touching 运行数据。

## 已执行工作

**1. 运行环境现状（发现：恢复服务已在运行，非我启动）**

- PID 61776 监听 **8910**（专用隔离 V2 服务，今晨 08:26 启动，持有运行库）；PID 8502 监听 8900（主应用，未触碰）。
- MTPLX 8002 健康：`mtplx-flash-next-optimized-speed`（Qwen3.8-Flash-Next，vision 开启）；OCR 8001 健康（oMLX Qwen3.8-27B）。
- 今晨 08:26 生成 `runtime/protocol-semantic-route-preflight.json`：三条语义路由（mtplx / zhipu glm-5.3-flash / deepseek deepseek-v4-flash）均 configured + reachable，无 blocking error。

**2. 旧 `cancel_requested` 作业合法终态对账（结论：已完成合法对账）**

作业 `67478824bad845c6bd91494fa91f09bf`（fact_normalization，运行 `72787b3ec2dd4c1bb274c3cee1260316`，筛选期）**已于今晨 08:26:52 CST（DB 00:26:52 UTC）由启动恢复转为终态 `cancelled`**。事件轨迹（UTC）：

| 时间 | 事件 |
|---|---|
| Sep 2 21:37:47 | created，15 步（14 页组 + finalize），权威 = `complete-529c…`/节点修订 4 |
| 21:58:37 | normalize_000 第 1 次尝试失败 → 任务失败 |
| 22:00:45 | retry_scheduled；第 2 次尝试 |
| 22:17:25 | **normalize_000 completed**，检查点 `8082e16d7bc748b0b6ab3523d7a80680`，进度 1/15 |
| 22:23:55 | cancel_requested（= 检查点文件记录的 06:24 CST 用户暂停） |
| Sep 3 00:26:52 | **cancelled**（= 08:26:52 CST 启动恢复） |

对账依据（`app/workflow/recovery.py` + `jobstore.py:1314 cancel_expired_cancel_requests`）：worker 死亡后租约过期，启动恢复将 `cancel_requested` 直接收束为 `cancelled` 终态，非终态步骤转 cancelled、已完成步骤保留历史，并追加 CANCELLED 事件（reason=`cancel_request_expired_lease`）。当前状态：`state=cancelled`、`cancel_requested=1`（历史标记，按设计保留）、generation 3、无租约；`page_work_leases` 48 行全部无 owner/无过期时间（**活动租约为 0**）。持久化成果完整保留：检查点 `8082e16d…` + 调用 `call_44d0f8f3…`（succeeded，页 [1]）+ 30 条候选 + 5 条未解决项。**该作业已是合法终态，禁止 retry（契约上 cancelled 也不可 retry）——暂停检查点的"下一步动作 2"实际已由今晨服务启动完成。** 活动服务 GET 确认与库一致（“已停止”，recovery_action 文案正确）。

**3. 发现一处簿记不一致（只读记录，供 Codex 裁决）**

运行 `72787b3e…` 的 `status='failed'` 与作业终态 `cancelled` 不一致。成因链：21:58 首次尝试失败时 `on_failed` 回调把 run 投影为 `failed`；之后的 retry 走的路径未把 run 重开为 `running`（`reopen_for_retry` 仅在 `FactNormalizationJobService.retry` 中调用）；取消时 `cancel()` 只在立即转 `cancelled` 时投影 run；晨间恢复 `recover_fact_normalization_runs` 只收敛 `running` 状态的 run。影响仅为状态展示/簿记，不影响检查点、调用、候选与未解决项的完整性，也不影响幂等键。可选修复：让 `recover_fact_normalization_runs` 按作业终态一并收敛非 `running` 的 run 状态。

**4. 快照/节点/配置状态**

- 受试者 `0675cabcc979452dbdd5f5c1570c36d8`，项目 `draft-project-09b593a721e7`（phase_iii）。
- 筛选期节点 `59b98368e962465ca5d62ff55b4da07d`（revision 4）：活动快照 `2685d8e0…`（active，5 份资料）+ 活动完整修订 `complete-529c2876…`（complete/ready/activatable，"Phase 5 原文定位修复” 于 Sep 3 03:23 CST 启用）。
- 基线期节点 `746385aba80c421ab83aaf439e084b7f`（revision 4）：活动快照 `350c8279…`（active）+ `complete-5f514e57…`（同时刻启用）。
- 第三节点 `f9548673…`（stage=run_in）无活动指针——按合同会拒绝创建规范化作业（预期行为）。
- 登记配置：normalizer 现行有效身份 = prompt `14c70479…`（template_sha256 `8ed51e42…`，**与当前工作树代码计算的模板哈希一致**，我已只读导入计算验证）+ model `eb7c34c6…`（mtplx/medium）。`cc472990…`（19:04 UTC 登记）是中间代码态残留，与当前代码不匹配，不会被 exact-match 选择。今晨 08:26 启动未新增登记行（幂等重登记，与上述结论自洽）。

**5. 新受控筛选/基线作业入口（含关键前置条件）**

法定入口：`POST /api/v2/subjects/{subject_id}/review-episodes/{review_episode_id}/fact-normalization-jobs`（`app/api/v2/fact_normalization.py:41`，8910 专用服务）。权威/配置服务端派生，`idempotency_intent` 被显式丢弃；创建事务内跑 `FactAuthorityValidator` 强校验（活动指针对、修订一致、complete/ready）。

**关键前置条件（阻塞项）**：作业创建幂等表已有记录 id=103：键 `677c455e…` → 作业 `67478824…`。由于旧作业的权威（`complete-529c…`/rev 4）、prompt（`14c70479…`）、model（`eb7c34c6…`）与输入范围都与当前派生身份相同，**在输入不变的条件下重 POST 该入口会命中 `IdempotencyRepository.resolve`（同键同哈希无条件复用，不检查引用作业是否终态），返回旧的 `cancelled` 作业（created=false），不会新建**。基线期同理（其最新幂等键 `54f50414…` 绑定已取消作业 `3dc50723…`）。

合法新建路径（三选一，需 Codex 决策）：
1. **合同修复自然换键（推荐路径）**：worker_01 落地 Evidence Normalizer 合同修复若改变模板/Schema 常量 → 新 `template_sha256` → 新 prompt_version → 新幂等键 → 新作业；
2. 激活新的完整处理修订（材料实质变化 → 权威/范围变化 → 换键）；
3. 产品级改动：`resolve` 命中终态（cancelled/failed_final）作业时允许废弃旧记录新建（这是幂等契约变更，需 Codex 批准）。

新建后的“首页组幂等复用验证”（暂停检查点动作 3）依赖执行器层 `_rebuild_call_checkpoint_from_persisted`/`_validate_call_checkpoint_replay`；注意持久化调用 `call_44d0f8f3…` 属于旧 run `72787b3e…`，**跨 run 的调用级复用是否生效正是 worker_01 的审计点**——两层幂等（作业创建层 + 步骤/调用层）需要协同，否则要么新作业建不出来（本报告第 5 点），要么建出来后首页组重复调用模型（worker_01 的问题）。

## 产物与证据

- 一致性快照：`/tmp/worker02_ro/fresh_snapshot.sqlite3`（55,013,376 B，quick_check=ok，可复查）；另 `/tmp/worker02_ro/db.sqlite3`（工作树空库对照）。
- 关键证据（均为只读查询）：作业 `67478824…` 行 + 15 步 + 11 条事件；检查点 `8082e16d…`（payload 含 call_id `call_44d0f8f3…` 与 candidate_ids）；`fact_normalization_runs` 13 行全 `failed/cancelled` 终态；幂等记录 44–103；`evidence_snapshot_status_events`（筛选 06:18 UTC / 基线 14:16 UTC activate）；8910 GET 返回 cancelled 状态。
- 引用代码：`app/workflow/states.py:57`（终态定义）、`app/workflow/recovery.py:41`、`app/workflow/jobstore.py:1314`、`app/api/v2/app.py:165-201`（启动恢复接线）、`app/api/v2/fact_normalization.py:41`、`app/services/fact_normalization_job_service.py:551-616`（run 投影/恢复）、`app/storage/idempotency.py:88`（resolve 无终态逃生）、`app/storage/fact_authority.py:63`（权威校验）。

## 命令与观察

- `lsof`：PID 61776 持有运行库并监听 8910；PID 8502 监听 8900。
- `shasum -a 256`：运行库主文件 = `2d197745…`（与暂停检查点一致）；工作树 `data_v2` 库 = `35c8709b…`（排除）。
- sqlite3 backup API（mode=ro 源）+ 查询：jobs/job_steps/job_events/job_checkpoints/page_work_leases/fact_normalization_runs/calls/candidates/unresolved/idempotency_records/review_episodes/evidence_processing_revisions/evidence_snapshot_status_events/model_configs/prompt_versions。
- `curl GET` 8910 作业状态、8002/8001 `/health`。
- 只读 Python 导入计算当前模板哈希 `8ed51e42…` 并与登记 prompt 比对。

## 阻碍或缺失环境

- 无工具/环境缺失。两点不确定性如实记录：① 无法从库内记录确证 8910 进程（08:26 启动）加载的就是当前工作树代码，但“启动未新增登记行 + 当前模板哈希匹配 `14c70479…`”与之自洽；② 旧 run 停在 `failed` 而非 `cancelled` 的确切历史路径（retry 走了哪条入口）无法从持久数据唯一确定，不影响对账结论。

## 重试请求或下一步

给 Codex 的精确决策请求：**新建受控筛选作业走哪条合法路径**——(a) 依赖 worker_01 合同修复自然更换 prompt 身份后从 API 新建（我的推荐，不引入契约变更），还是 (c) 批准修改作业创建幂等层为终态引用提供重建逃生？同时请裁决 run `72787b3e…` 的 `failed` 状态残留是否随本次修复一并收敛。确认后即可按暂停检查点动作 3 推进：新建筛选作业 → 验证首页组幂等复用与耗时 → 完成后审计候选质量再串行基线期。本 pass 未启动任何长任务，运行数据库零写入。
