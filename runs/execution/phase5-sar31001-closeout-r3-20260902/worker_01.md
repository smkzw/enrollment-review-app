# 执行输出: phase5-sar31001-closeout-r3-20260902 - worker_01

## 边界与上下文检查

- 本次为只读审计，未修改任何共享服务、代码或数据库。所有 SQLite 查询使用 `sqlite3 -readonly`；主库文件 SHA-256 在审计前后保持 `79d93f382d93acf06ba0d45cfa1d8384b13146e70e96f574b5bd0666d28350ef`（与暂停检查点锚点一致）。仅创建/写入了本报告（由 runner 持久化）。
- 初始读取集已读：`context/phase5-sar31001-closeout-r3-20260902_execution_context.md`、`plans/codex_execution_phase5-sar31001-closeout-r3-20260902.md`。补充读取（说明理由）：暂停检查点 `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260902_SAR31001_NORMALIZATION_MTPLX_PAUSED.md`（唯一权威的暂停现场记录）、`app/config.py`、`app/pipeline/ocr.py`、`app/workflow/{states,jobstore,recovery,runner}.py`、`app/agents/deepseek_evidence_normalizer_transport.py`、`app/services/fact_normalization_{executor,job_service}.py`、`app/storage/idempotency.py`、`app/api/v2/{app,jobs}.py`、MTPLX/oMLX 应用配置与诊断日志（`~/Library/Application Support/{MTPLX,oMLX}/`）、运行库 `artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/enrollment-review-v2.sqlite3`。未读 peer 报告、未做临床判断、未实施 Phase 5.5。

## 已执行的工作

按工单 1 完成 6 项只读审计：(1) 8001/8002/8900（含 8910/8911 观察）；(2) MTPLX 实际模型与响应格式；(3) 三次 502 日志定位与归因；(4) OCR 8 路准入代码与后端就绪度；(5) cancel_requested 规范化作业的租约与终态（代码路径 + 数据库实证）；(6) 安全恢复建议。

**最重要的两条发现（先讲结论）：**

1. **三次 502 的根因是 MTPLX 桌面应用在 14:21–14:47 CST 窗口内被用户两次退出，而非应用契约、模型绑定或 OCR 门禁问题。** MTPLX 应用自记诊断 `app_stop_all_invoked (reason=app_termination, daemon_state=stopped)` 两次恰好夹住三次失败：06:23:09Z（ attempt 2 失败前 1.4 秒）、06:47:51Z（attempt 3 失败后 1.5 秒）。当前 8002 已由用户于 20:52 CST 重启，实际模型标识与应用冻结配置完全一致。
2. **卡在 `cancel_requested` 的规范化作业已在我审计期间（21:01:39 CST）被合法路径终态化为 `cancelled`**——由 8910 专用 V2 服务（worker_02 边界内）启动时的 `run_startup_recovery → cancel_expired_cancel_requests()` 完成，事件原因 `cancel_request_expired_lease`，这正是代码设计的安全终态化路径。作业不可恢复、不可复用（0/6 步完成，无任何部分事实落库，已验证 `clinical_facts_v2/events_v2/medication_exposures_v2/patient_profile_revisions_v2` 均为 0）。**但由此产生一个 Codex 必须先决策的问题：现有幂等机制没有 supersede 路径，字节级相同的重新提交只会返回旧的 cancelled 作业而不会创建新作业**（详见下文）。

## 工件与证据

### A. 端口审计（观察时间 2026-09-02 20:57–21:15 CST）

| 端口 | 角色（按检查点） | 审计时刻状态 | 证据 |
|---|---|---|---|
| 8001 | OCR / oMLX | 首次探测未监听；20:56 用户重启 oMLX 后 **UP**，`GET /v1/models` → 200 | `~/Library/Application Support/oMLX/config.json` port=8001；进程 python3.1 PID 97854（oMLX.app PID 97843，20:56 启动） |
| 8002 | MTPLX 语义模型 | **UP**，`/health` 200 ok | 服务器 python3.1 PID 95014，`started_at=1788353522`（20:52:02 CST），MTPLX.app PID 94586（20:51:27 启动） |
| 8900 | “主应用” | **监听中但不是入排应用** | PID 8502，2026-08-31 06:46 启动，cwd=`/Users/smkzw/Vibe-Research/backend`，`uvicorn app:app --port 8900`；`/health` → 404 |
| 8910 | 本任务专用 V2 | 暂停时已停止；审计期间 **重新上线** | Python PID 1875 监听 8910 且持有运行库 WAL（worker_02 的边界，非我启动） |
| 8911 | — | 有 Python 监听器出现/消失（PID 91140 → PID 1527） | peer 活动，按边界不评审 |

检查点“主应用 8900 保持运行”的表述与现实不符：8900 现属另一项目进程。恢复主应用前需用户处置（停掉 Vibe-Research 后端或换端口）——用户决策，非我权限。

### B. MTPLX 实际模型与响应格式

- **实际模型**：服务器命令行 `--model ~/.mtplx/models/Youssofal--Qwen3.8-27B-MTPLX-Optimized-Quality --model-id mtplx-qwen38-27b-optimized-quality --backend-id qwen3_next --reasoning-parser qwen3 --reasoning-effort medium --preserve-thinking auto`。`/v1/models` 恰好一个条目：`mtplx-qwen38-27b-optimized-quality`，context 262144。`/health`：`api_key_required=false`、调度器 `max_active_requests=4`、warmup 完成、模型载入内存正常（M5 Max）。**当前实例标识与运行库冻结 model_config 完全一致**：DB `model_configs` 行 = provider `mtplx` / model `mtplx-qwen38-27b-optimized-quality` / effort `medium` / max_tokens 60000 / temperature 0.2。检查点担忧的 `mtplx-flash-next-optimized-speed` 属于暂停前的旧实例，该实例已不存在。
- **推理强度契约**：服务器支持 effort_levels `[xhigh, medium, low]`（默认 medium）；应用发送 `reasoning_effort=medium`——受支持，无漂移。
- **响应格式契约**（`app/agents/deepseek_evidence_normalizer_transport.py:104-157`）：同步 OpenAI SDK → `MTPLX_BASE_URL + /v1`，api_key 兜底 `"local-mtplx"`；`chat.completions.create` 带 `response_format={"type":"json_object"}`（mtplx 路径）+ `reasoning_effort`；**只读 `choices[0].message.content`**（thinking 由服务器 qwen3 parser 剥离到 reasoning_content，不干扰解析）。客户端未显式设置 timeout/max_retries（SDK 默认 600s / 2 次）。`extra_body generation_mode=ar` 仅在 json_schema 时添加——当前 json_object 路径用服务器默认 mtp 生成。
- **未做最小真实调用**（有意保守）：检查点要求恢复前先经用户确认 MTPLX 测试结束；且当前实例 `requests_completed=0`，尚未有任何消费方验证过它。建议恢复流程第一步做一次极小 chat 调用验证 content 返回 JSON。

### C. 三次 502 日志（最小根因证据）

**应用侧**（DB `job_events`，作业 `2e28e8673eee412abba3fc3f61cd476d`，run `4ecda29906164a35ad7cbe0b021d9275`，筛选期 episode `59b98368e962465ca5d62ff55b4da07d` rev 3）：

| UTC 时刻 | 事件 | 详情 |
|---|---|---|
| 06:21:51.630 | attempt 1 step_started `normalize_000_3de286...` | |
| 06:22:32.342 | step_failed | `detail="Error code: 502"`, `TRANSPORT_FAILED`, retryable（41s） |
| 06:22:32.863 → 06:23:10.715 | attempt 2 step_failed | 同上 502（38s） |
| 06:23:11.756 → 06:47:49.852 | attempt 3 step_failed | 同上 502，`attempt_exhausted=true`（24m38s） |
| 06:47:49.856 / .857 | finalize `DEPENDENCY_FAILED` → job failed | |
| 07:04:56.631 | retry_scheduled（scope=normalize_000+finalize），attempt 4 step_started | |
| 07:38:26.991 | cancel_requested | lease v2-worker gen 4，07:55:55Z 过期 |

`fact_normalization_calls` 中该 run 为 **0 行**——没有成功调用记录持久化（失败路径不写该表，见 §E 观测性缺口）。

**服务侧**（`~/Library/Application Support/MTPLX/Diagnostics/*.jsonl`，事件 `app_stop_all_invoked`）：

- `2026-09-02T06:23:09Z`，reason=`app_termination`，daemon_state=`stopped` —— **attempt 2 的 502 前 1.4 秒**
- `2026-09-02T06:47:51Z`，reason=`app_termination`，daemon_state=`stopped` —— **attempt 3 的 502 后 1.5 秒**
- 其余退出记录：09-01T13:48:17Z、09-02T09:00:12Z、09:12:25Z（17:00/17:12 CST，即检查点暂停前后用户在测试 MTPLX）；另有 09-01 两次 `launch_button_stop`。

**归因（标注为推断）**：502 集群与用户两次退出/重启 MTPLX 应用精确同窗。attempt 3 持续 24m38s 说明期间服务器已重新可用（用户在 06:23 退出后重启了应用），最后的在途调用被 06:47 的退出杀掉。三次失败均为 MTPLX 服务端返回 HTTP 502（OpenAI SDK `APIStatusError` 格式），映射为 retryable `TRANSPORT_FAILED`（`fact_normalization_executor.py:785`）。**不确定性**：attempt 1（06:22:32Z 失败）无同秒服务端日志对应；把它归入同一次退出序列是合理推断但无直接日志行。

### D. OCR 8 路准入

- `OCR_MAX_CONCURRENT=8`（`app/config.py:145`，`.env.example` 一致）。
- 全局准入点 `global_vlm_semaphore()`（`app/pipeline/ocr.py:74-88`）：**每事件循环仅一个** `asyncio.Semaphore(8)`，进程内全部 OCR 共享——并发多个 `/process` 请求不会放大上限；缓存键为 `(loop id, configured)`。
- 实际获取点：`app/pipeline/ocr.py:258、295、337`——每页 VLM 调用都在 `async with semaphore` 内；文件级并发（每批 `Semaphore(OCR_MAX_CONCURRENT)`，ocr.py:554-559）嵌套于同一 8 路闸门内 → 对 oMLX 的同时 VLM 调用有效上限恒为 8。
- 在线验证工具已存在：`tests/v2/evidence/probe_omlx_gate_live_concurrency.py`（`--url http://127.0.0.1:8001`）。
- 后端就绪：oMLX 8001 健康，冻结的 `OCR_MODEL_LONG/SHORT = models--PaddlePaddle--PaddleOCR-VL-1.6` **在当前目录中**（另有 GLM-OCR-bf16 等）。OCR 链路无需修改即可服务。

### E. cancel_requested 规范化作业租约终态

- **状态机**（`app/workflow/states.py`）：`running → cancel_requested → cancelled`；终态 = {completed, failed_final, cancelled}；`CLAIMABLE_JOB_STATES = {queued, recovering}`；`DIRECT_CANCELABLE_JOB_STATES = {queued, failed_retryable, recovering, waiting_user}`；`ACTIVE_LEASE_STATES = {running, cancel_requested}`。→ `cancel_requested` 只能由**当前租约持有者**在步骤安全边界提交取消（`app/workflow/runner.py:281-283, 544-546`）；无人持有租约时它不在任何可认领/可直接取消集合中。
- **设计好的出口**：V2 写服务启动时 `run_startup_recovery`（`app/api/v2/app.py:166`）→ `cancel_expired_cancel_requests()`（`app/workflow/jobstore.py:1315-1348`）：`cancel_requested` + 租约过期 → 直接置 `cancelled`（终态）、清租约、generation+1、非终态步骤置 cancelled、追加事件 `{"reason":"cancel_request_expired_lease"}`。
- **审计期间实测**：21:01:39 CST，作业翻转为 `cancelled`、租约清空、generation 4→5、事件 seq 15 载荷 `{"reason": "cancel_request_expired_lease"}`。主库文件 SHA 不变；变更落在新出现的 24,752 字节 WAL（mtime 21:01），持有者为 8910 上的 V2 进程 PID 1875。**这是设计内行为，无需也不应手工改库。**
- **当前事实计数为零已验证**：`clinical_facts_v2=0, clinical_events_v2=0, medication_exposures_v2=0, patient_profile_revisions_v2=0`——与检查点一致，无部分数据需要清理。
- **幂等监视项（Codex 决策点）**：run `4ecda299...` 状态 `failed`，幂等键 `e610e2e1aa5fd44f02477007f14e480b2540cd3daf7206b3f9ae6f0f4af9b070`，由（权威元组＝筛选期 episode rev 3 + snapshot `2685d8e0...` + complete 修订 `complete-45b1c163...`、prompt_version `evidence-normalizer/prompt/c1e69fd6...`、model_config `evidence-normalizer/model/5c9814f8...`、input_scope_sha256、`phase5/facts/v1`）派生。`IdempotencyRepository.resolve`（`app/storage/idempotency.py:102-125`）+ `fact_normalization_job_service.py:434-457`：**同键同哈希 → 复用旧记录（created=False，返回旧作业，状态 cancelled），不创建新作业；同键异哈希 → `IdempotencyConflict`；不存在任何 supersede/重试通道**。因此 worker_03 的“合法新作业入口”若字节级重放同一请求，将被幂等挡回旧作业。合法新入口必须至少改变一个哈希输入（实践中＝通过合法证据处理产生**新的 complete 处理修订/新权威元组**），或由 Codex 决定增加显式 supersede 机制。
- **基线期作业时间线**（供 worker_02 参考，深诊断不在我范围）：`49bda9d5...` failed_final/SNAPSHOT_STATE_INVALID（06:35:12→06:52:19Z，17 分钟）；`ce47ea92...` failed_final/EXECUTOR_ERROR（06:52:54→06:53:00Z，**仅 6.4 秒**——快速失败，指向执行器级异常而非模型超时）；`604bd788...` cancelled（07:27:48→07:50:02Z）。基线期 episode `746385ab...` 确认无活动快照/修订。

### F. 安全恢复建议（最小集合，不改共享服务）

1. **MTPLX**：现实例模型绑定已与冻结配置一致，无需切换。恢复前置＝用户确认测试结束；然后先做一次极小真实 chat 调用验证 `choices[0].message.content` 返回 JSON，再放行作业。不要改 `MTPLX_MODEL`。
2. **oMLX/OCR**：8001 健康、模型在目录，无需动作。
3. **8900**：端口被无关项目占用，需用户处置后才能启动入排主应用（或换端口）。
4. **已取消作业 `2e28e867...`**：保持终态，不恢复、不复用、不标记成功（与检查点一致）；其 run 无任何调用行，无残留数据。
5. **新规范化入口（worker_03）**：不得字节级重放旧请求（幂等会返回旧 cancelled 作业）。**建议 Codex 在 worker_03 启动前先决策新入口的权威元组来源**（新 complete 修订 vs. supersede 机制）。
6. **8910**：已在运行且启动恢复已按设计终态化取消作业——无需手工干预。
7. **锚点管理**：运行库现处于 WAL 活跃写入状态，检查点的主文件 SHA 不再反映有效库状态；建议 Codex 在下一个干净时点重做快照锚点（含 WAL）。

## 命令与观察记录

- `lsof -nP -iTCP:8001/8002/8900/8910/8911 -sTCP:LISTEN`；`ps`/`lsof -p <pid>`（cwd、启动时间、命令行）。
- `curl`（只读 GET）：`8002/health`、`8002/v1/models`、`8001/v1/models`、各端口 `/health`。
- `sqlite3 -readonly` 查询：`jobs`、`job_events`、`fact_normalization_runs/calls`、`review_episodes`、`model_configs`、`service_command_events`；`shasum -a 256` 前后哈希验证主库未变。
- 读取 MTPLX/oMLX 应用配置与 `Diagnostics/*.jsonl`（`app_stop_all_invoked` 事件）。
- 代码审计（只读）：`app/workflow/states.py`、`jobstore.py:401-465,1292-1348`、`recovery.py`、`runner.py`、`app/pipeline/ocr.py:74-88,410-470,540-660`、`app/agents/deepseek_evidence_normalizer_transport.py`、`app/services/fact_normalization_executor.py:740-829`、`fact_normalization_job_service.py:380-470`、`app/storage/idempotency.py:102-148`、`app/domain/contracts/facts.py:699-723`、`app/api/v2/app.py:166`。
- 工具与目标均已记录如上；未发生写操作（除本报告）。

## 阻碍或缺失的环境

- 无执行阻碍。三项注意事项：(1) 未执行“最小真实 MTPLX 调用”（按检查点需用户先确认测试结束，且属恢复动作而非只读审计）；(2) attempt 1 的 502 无同秒服务端日志（MTPLX 未提供请求级日志文件），归因依赖诊断事件夹逼 + 时序一致性；(3) 8900 与运行库 WAL 的现场在审计窗口内被 peer/用户改变，本报告以“观察时刻”口径记录，Codex 接受时请注意时点。

## 重跑请求或下一步

- **需 Codex 决策**（阻塞 worker_03 的新作业入口）：规范化幂等键无 supersede 通道——新入口采用“新 complete 处理修订产生新权威元组”，还是为 failed/cancelled run 增加显式 supersede 机制？
- **移交 worker_02 的输入**：基线 `ce47ea92...` 仅 6.4 秒即 EXECUTOR_ERROR（快速失败），`49bda9d5...` 17 分钟后 SNAPSHOT_STATE_INVALID；两者共用 episode `746385ab...`（无活动快照）。
- **移交 worker_03 的输入**：8910 已在运行；旧作业已终态 cancelled；事实计数全零；冻结 model_config 与现网 MTPLX 完全一致；恢复后首步做一次最小真实调用。
- **可选后续（非本工单）**：TRANSPORT_FAILED 详情目前丢失 502 响应体（仅 "Error code: 502"），且失败路径不写 `fact_normalization_calls`/`agent_calls`——建议未来在有界范围内捕获响应状态/体片段以缩短下次根因定位。
