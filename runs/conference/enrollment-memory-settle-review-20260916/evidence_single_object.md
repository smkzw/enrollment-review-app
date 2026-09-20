Trellis SessionStart ✓

我先读初始读集，然后做只读证据审计。

Bash 被拒（非交互模式无权限提示）——这本身是需要披露的工具限制。改用 Glob/Read/Grep。

# Conference Output: enrollment-memory-settle-review-20260916 - evidence_single_object

## Output

### 0. 边界与工具状态（先披露失败）

- 只读完成，未加载任何模型，未修改产品/源码，未写入任何路径（含 runner 管理的报告路径）。
- **工具失败：本会话 Bash 被拒**（`Permission to use Bash has been denied ... non-interactive mode`）。后果：无法执行 `uv run pytest`、`git log/diff/blame`、`sqlite3` 查询、`ps/vm_stat` 现场采样。所有结论来自静态源码阅读 + 包内 artifact，已运行/未运行状态在 §7 逐条标出。
- 读集外补充：`reviews/`、`runs/`、`plans/`、`docs/PROJECT_CONTEXT.md`、`app/services/`、`app/agents/`、`tests/`（均为工作区文件，非生产路径，未新增生产路径）。`plans/codex_main_venue_*.md` 与 `reviews/codex_conference_*_review.md` 仍是 TODO 骨架，**不能作为本次审阅的事实源**。

---

### 1. 证据链（源链接）

| 事实 | 位置 |
|---|---|
| 结算门 `wired <= baseline + 1GiB`，需连续 2 个样本，超时抛 `MtplxMemoryReleaseIncomplete` | `app/llm/mtplx_owned_server.py:280-294` |
| 基线 = 该模型 `start()` 前的全机 `wired_bytes` 快照 | `app/llm/mtplx_owned_server.py:210-213, 223-224` |
| 快照口径 `scope: whole_system`，仅 `vm_stat`，无归属 | `app/llm/mtplx_owned_server.py:95-115` |
| 释放失败保锁：`port_released` 保持 False ⇒ 不关 admission fd（保留 flock） | `app/llm/mtplx_owned_server.py:295, 300-303` |
| 释放失败保留句柄：`stop()` 抛出前不置 `current = None` | `app/llm/mtplx_model_lifecycle.py:45-49` |
| 终态记录只有两个事件名，丢失"进程组+端口已释放"的事实 | `app/llm/mtplx_owned_server.py:296, 298` |
| `MtplxMemoryReleaseIncomplete` 继承"PID 尚未退出"语义的 `MtplxShutdownIncomplete` | `app/llm/mtplx_owned_server.py:35-46` |
| 取消：清理被 shield，取消后仍完成 kill 再抛 CancelledError | `app/llm/mtplx_owned_server.py:155-165` |
| `shutdown_seconds` 默认 30s，且被四次复用（SIGTERM 等待 + SIGKILL 等待 + 端口等待 + 内存等待） | `app/llm/mtplx_owned_server.py:59, 133-152, 275-279, 283-294` |
| 清单不覆盖 `shutdown_seconds`（只读 `max_tokens`） | `app/llm/mtplx_model_lifecycle.py:133-138` |
| lifecycle 串进入部署身份 | `app/llm/mtplx_model_lifecycle.py:184-193` |
| 部署身份 ⇒ 路线身份 ⇒ 任务载荷 / 主读身份 | `app/services/page_review_job_service.py:75-96, 141` |
| 执行器硬门：载荷 routes 不等 ⇒ 不可重试 `R3_ROUTE_CHANGED` | `app/services/page_review_job_executor.py:55-56` |
| 续跑硬门：冻结载荷 ≠ 重算计划 ⇒ 409 `PAGE_REVIEW_RESUME_NOT_READY` | `app/services/page_review_job_service.py:205-210`（+ `tests/v2/api/test_page_review_resume.py:225-238`） |
| 覆盖度绑定：按 `main_reader_identity_sha256` 过滤，不匹配 ⇒ `PageCoverageNotReady` | `app/services/page_review_job_service.py:78`；`app/services/page_review_coverage_selection.py:58-65` |
| 规范化硬门：`parameters["mtplx_deployment_sha256"] != deployment` ⇒ 报错要求新建任务 | `app/services/fact_normalization_command_service.py:218-227`；`app/agents/deepseek_evidence_normalizer_transport.py:542-543` |
| 协议语义缓存身份包含部署身份 | `app/agents/protocol_semantic_transport.py:371-393` |
| 历史 v1 身份在实际作业回执中 | `artifacts/mtplx-dual-basic-20260916/direct-read-v16-receipt.json:12-16, 26-30`（另见 `direct-read-receipt.json`、`direct-read-retry-receipt.json`、`direct-read-high-resolution-receipt.json` 同形） |
| 启动路径会真装卸模型（`sync_mtplx_model_session`），随后 `close_owned_mtplx_models()`，异常上抛 | `app/agents/protocol_semantic_route_preflight.py:243-249, 398-410`；`app/api/v2/app.py:162-167` |
| 关闭路径 await `close_owned_mtplx_models()`，异常逃逸 lifespan | `app/api/v2/app.py:415-425` |
| 采样器（0.25s）与事件写入源 | `artifacts/mtplx-dual-basic-20260916/observe_switch.py:23-43` |

---

### 2. 关键负面结论：目标项①"进程退出后内存滞后"在本包证据中**不成立**

这是我对本任务最高优先级的反对意见，先给可复核的观测序列（16 KiB/页）：

**v2 中途换模（pid 29237）**
- `continuous-switch-memory-settle-v2/samples.jsonl:39` t=39264.284 → `Pages wired down: 1727408` = **28.30 GB**
- `samples.jsonl:40` t=39264.577 → `415189` = **6.80 GB**
- 生命周期回执 `direct-cli-logs/enrollment-27b2a817….lifecycle.jsonl:2,3`：`stop_requested` t=39264.274 wired 28,302,065,664 → `process_group_and_port_released` t=39264.860 wired 6,817,349,632

即：**SIGTERM 发出后 0.30 s 内内存已回到基线**，而"进程组+端口已释放"是在其后 0.28 s 才被确认的记录点。

**v2 末次关闭（pid 29350，91.16 GB wired）**
- `samples.jsonl:85` t=39277.885 → `5547728` = 90.9 GB（`stop_requested` 在 t=39277.968）
- `direct-cli-logs/enrollment-05169281….lifecycle.jsonl:3` → `process_group_and_port_released` t=39278.894 wired 6,791,675,904
- 最后一个"高位"读点距释放记录点 **0.11 s**，中间间隔 0.28–0.31 s 的采样粒度没有出现任何"退出后仍高位"的平台段。

**v1 对照（`continuous-switch-observation`）**
- `samples.jsonl:83` t=34385.289 → `5546118`；`samples.jsonl:84` t=34385.586 → `399853`（6.55 GB）
- `events.json`：`close` t=34385.128，`closed` t=34385.814

**直连 CLI 探针** `direct-cli-release-probe-v2.json`：`release_seconds` 0.32 / 0.78，两次 `port_in_use: false`。

代码里被当作前提的注释是"Process exit can precede Metal memory reclamation"（`app/llm/mtplx_owned_server.py:281-282`）。**本包两条独立运行（v1/v2）+ 直连探针都没有出现该现象；相反，回收发生在进程确认死亡之前或同一采样间隔内。**

代价侧也不是主要问题：v2 关闭 0.93 s vs v1 0.69 s，差值 ≈ 一个 0.25 s 采样间隔——因为首次采样通常已达标。

**推论（明确标为推论）**：这不是性能问题，而是**证据问题**——一个硬失败、阻塞、会一路走到"应用启动失败"的门，其触发前提取自一个未被该包任何观测支持的失败模式。要么补一条"进程组确认消失后 wired 仍 > 基线+1GiB 持续若干秒"的样本序列（v1、v2 都是近 OOM 场景：`Pages free: 33458`、`38139554` 次 swapout，压力条件已覆盖，仍未见滞后），要么把该门降级为记录型观测。

---

### 3. 确证缺陷与最小修正

#### D1（高）历史身份兼容：把"等待策略"编进部署身份，一次性废掉三类历史对象

`mtplx_model_lifecycle.py:193` 的 `"lifecycle": "owned-serial/v2-memory-settle"` 进入 `mtplx_deployment_identity`，随后进入四个消费者的**相等性比较**：

1. **在途/排队页读作业**：冻结载荷 routes（`page_review_job_service.py:141`）与现算 routes 比较，不等即不可重试 `R3_ROUTE_CHANGED`（`page_review_job_executor.py:55-56`）。
2. **已取消作业续跑**：`comparable != plan` ⇒ 409 `PAGE_REVIEW_RESUME_NOT_READY`（`page_review_job_service.py:205-210`，测试固化了该行为）。
3. **规范化阶段绑定**：覆盖度行按 `main_reader_identity_sha256` 过滤（`page_review_coverage_selection.py:58-60`），v1 时期写入的覆盖度必然不匹配 ⇒ `PageCoverageNotReady`；另有 `mtplx_deployment_sha256` 硬比较直接报"请新建整理任务"（`deepseek_evidence_normalizer_transport.py:542-543`）。
4. **协议语义缓存身份**（`protocol_semantic_transport.py:371-393`）：全部 v1 缓存条目失效，需重跑语义批次。

**代价是真实的、且被证据固定**：`direct-read-v16-receipt.json:12-16` 等四份真实回执记录的是 `"lifecycle": "owned-serial/v1"`，对应 2026-09-16 07:16Z / 08:04Z 的真实作业。也就是说升级后这些作业**在模型、路径、manifest sha256、档位、提示词、合同版本全未变化**的前提下会被判为"配置已变"，把一次"卸载等待策略变更"翻译成"必须重读资料"。

**最小修正（行为安全）**：从 `mtplx_deployment_identity` 返回字典中**移除 `lifecycle`**，只把它写进生命周期日志 / 非身份回执字段。核查：全仓 `"lifecycle"` 作为该身份的取值只出现在 `mtplx_model_lifecycle.py:193`，**无任何消费方按值分支**，因此移除不改变行为。
若必须保留模式标记，则改走**已有**的显式版本通道 `page_review_execution_versions()`（`page_review_job_service.py:42-47`，其语义本就是"处理方式已更新，请保留现有结果并新建处理任务"），并补齐兼容映射（旧值 `owned-serial/v1` ≡ 当前模式），与 `page_review_job_service.py:206-208` 已有的"新增调度不改变阅读语义"先例保持一致。

#### D2（高）全机计数误阻断：无归属、无重基线、无出口

- 门只读 `wired_bytes`（全机口径，`app/llm/mtplx_owned_server.py:95-115`），与**本产品无关的应用**增长无法区分；阈值固定为"该次 `start()` 前的快照 + 1GiB"，**永不刷新**（`:210-213, 285-291`）。
- 失败即 `MtplxMemoryReleaseIncomplete`（`:293`），`current` 不清空、flock 不释放（`mtplx_model_lifecycle.py:47-49`；`mtplx_owned_server.py:300-303`）。

**误阻断的两个真实落点**：
1. **启动失败**：启动预检会真加载模型并在 `finally` 里 `asyncio.run(close_owned_mtplx_models())`（`protocol_semantic_route_preflight.py:243-249, 398-410`），该异常逃逸后 `initialize` 中断（`app/api/v2/app.py:162-167`）——即"另一个应用多占了 1GiB wired"可以导致**入排审核应用起不来**。
2. **误导性状态**：模型进程已死、端口已空，但 flock 仍被本进程持有，第二个产品实例被拒时的文案是"另一个入排审核进程正在使用本地模型，请等待其释放"（`mtplx_owned_server.py:207`）——与事实不符。

**本机触发条件有据**：`docs/PROJECT_CONTEXT.md:87` 记录 8002 当前属于 GUI 启动的共享 FlashNext；而单个模型的 wired 变化量级为 6.62 GB → 28.30 GB（`enrollment-27b2a817….lifecycle.jsonl:1,2`）。任何"GUI/其他应用再起一个模型"或大量 IOKit/Metal 活动都会远超 1GiB 余量。采样文件每行都含一个命令行匹配 `mtplx` 的进程（如 `samples.jsonl:104` 的 `2850 … /Applications…`，因载荷截断无法确认完整身份，标为未验证），与"共存"场景一致。

**最小修正（保留 fail-closed 精神，去掉不可归属性）**：
1. `status != "observed"`（`vm_stat` 失败/解析失败）**不得**当作"内存未释放"（见 D5）。
2. 释放确认拆成两段语义：**进程组+端口已释放**是硬结论（保留 flock 只在"进程未死/端口被占"时）；**全机 wired 未回落**只允许降级为"记录告警 + 继续"或要求一个显式、可审计的受控覆盖（例如环境变量 + 生命周期事件），而不是进程级永久封锁。
3. 若要维持硬门，必须给出**归因依据**：例如只对"本 launch_id 的进程组已消失"后仍持续超阈值 N 秒、且 `vm_stat` 连续可测的样本生效，并在事件里写入 `baseline / observed / samples / status`。

#### D3（高）失败态分类与可恢复性：进程已释放的事实被吞掉，用户拿不到责任方与动作

`stop()` 的唯一终态事件只有 `process_group_and_port_released`（`:296`）与 `shutdown_incomplete`（`:298`）。而内存门失败时，**进程组与端口其实已经确认释放**（`:273-279` 已通过），这一事实在任何事件里都不存在——审计者无法区分"进程没死"与"进程死了但全机 wired 高"。

同时 `MtplxMemoryReleaseIncomplete` 继承 `MtplxShutdownIncomplete`（`:43-46`），而基类契约是"caller must keep the hardware unavailable until this PID has exited"（`:35-40`）——此处 PID 已经退出，继承关系向消费者传达了相反语义。全仓 `MtplxOwnershipError` 的捕获点只有两处（`protocol_control_execution.py:854`、`protocol_deconstruction_executor.py:215`），页读路径没有任何一处把它翻译成带责任方/动作的用户态。

**最小修正**：
1. 抛错前补写独立终态事件（建议 `process_group_and_port_released` **与** `memory_settle_incomplete` 同时落盘，含 pid/launch_id/returncode/baseline/observed/样本数/`vm_stat` 状态）。
2. 让内存未回落**不继承**"PID 未退出"语义（改为与 `MtplxShutdownIncomplete` 并列，或在消费者侧显式区分）。
3. 文案按项目规则补齐"责任方 + 动作 + 可接受证据 + 到期阶段"：现文案（`:46`）只说明"不会被关闭"，未给出用户该做什么；同时给它一个独立错误码而非落入通用失败。

#### D4（中高）取消/失败保锁的时延上界被低估：单次 `stop()` 最坏约 120 s

`shutdown_seconds` 默认 30（`:59`，清单不覆盖，`mtplx_model_lifecycle.py:133-138`），但被四个独立预算复用：SIGTERM 等待 30 + SIGKILL 等待 30（`:140-151`）+ 端口等待 30（`:275-279`）+ 内存等待 30（`:283-294`）。`stop()` 又会在每次 `_release()`/重试（`mtplx_model_lifecycle.py:45-49, 51-60`）和关闭路径（`app/api/v2/app.py:420-421`）重入。
**最小修正**：`stop()` 内使用**单一** monotonic 总预算，子步骤共享；`close()`/lifespan 使用有界等待并记录超时。

#### D5（中）"测不到"与"未回收"被合并为同一状态

`_system_memory_snapshot` 在 `vm_stat` 失败/解析失败时返回 `{"status": "unavailable"}`（`:98, 103-104, 114-115`）；循环把 `wired is None` 记为 `stable = 0`（`:287-289`），于是**30 s 后无论"测不到"还是"真没回落"都抛同一个 `MtplxMemoryReleaseIncomplete`**（`:292-293`）。非 Darwin 平台恒为 `unavailable` ⇒ `wired_before_start is None` ⇒ 门被静默跳过（`:280`），"v2-memory-settle" 身份在非 Darwin 上是名义的。
这与项目既定原则同构（"不得把记录不完整与专业判断合并为同一状态"）。
**最小修正**：区分 `unmeasurable` 与 `not_released`；前者不阻断、只记录；并在回执里写平台与测量状态。

#### D6（中）`session()`/`sync_session()` 的"任何非显式拒绝都释放"与新增阻塞门叠加

`_explicitly_rejected` 只覆盖 400/401/403/404/422/429（`mtplx_model_lifecycle.py:21-24`），其余（超时、5xx、连接错、调用方抛出的 schema/解析错）一律 `await self._release()`（`:70-73, 90-93`）。加入内存门后，一次瞬时传输错误会：(a) 最多再花约 120 s；(b) 可能抛 `MtplxMemoryReleaseIncomplete`，**覆盖原始错误**并保留 `current` 与 flock。
这正是 `runs/conference/enrollment-owned-mtplx-wiring-20260916/evidence_single_object.md:68` 的第一条建议（当时未修），本次修改**抬高了它的代价**。
**最小修正**：仅在取消 / 关停 / spec 变更时卸载；瞬时传输失败保留驻留进程。

#### D7（中）该路径**零测试覆盖**，而被它影响的身份行为有测试固化

`tests/` 全目录检索 `mtplx_model_lifecycle|mtplx_owned_server|OwnedMtplxServer|MtplxModelOwner|MtplxMemoryReleaseIncomplete` → **0 命中**；同时 `tests/v2/api/test_page_review_resume.py:225-238` 固化了身份变化的拒绝行为——即"新门无测试、被它破坏的旧行为有测试"。
**最小修正**（注入 `_system_memory_snapshot`/假进程即可，不需要真模型）：阈值边界、`unavailable`、两样本要求、取消保锁、失败后保留 `current` 并可重试、以及身份在本次变更前后保持稳定。

#### D8（低）其它

- `_record_lifecycle` 在事件循环线程同步调 `_system_memory_snapshot`（`:188, 271, 296, 298`），而结算循环用 `asyncio.to_thread`（`:286`）——口径不一致，每次最长 1 s 阻塞事件循环；`_port_in_use` 的连接探测同样在循环上（`:89-92, 276`）。
- 结算门对**已释放句柄的重复 `stop()`** 不做"已结算"记忆，重试各付 1–2 个样本；且 `wired_before_start` 永不刷新 ⇒ 若基线取到瞬时高位则门**永久偏松**（fail-open），取到瞬时低位则**永久偏紧**（误阻断），两种方向操作者均不可见。

---

### 4. 需要指出的正确之处（避免只给负面）

- 所有权靠 `Popen` 句柄而非端口发现（`:134`）；`_finish_cleanup` 用 shield 保证取消不留下活进程（`:155-165`）；取消/失败保留 flock 是刻意的 fail-closed（`:300-303`）；端口二次确认补上了"孤儿仍占端口"的假完成；`+1GiB`/两样本被明确标注为启发式、且不声称归因（`:281-282`）——这些是本次修复中确实成立的部分，我未找到反例。

---

### 5. 我认为最该先处理的顺序（建议，非裁决）

1. **D1**：先决定 `lifecycle` 是否留在身份里。它决定是否要重读/重跑历史资料，是唯一会**改变临床工作产物范围**的项。
2. **D2 + D5**：把"全机计数 / 测不到"从硬门里摘出来，或至少让启动路径不被无关应用的内存决定生死。
3. **D3 + D4**：失败可诊断、可恢复、有责任方与动作、时延有上界。
4. **D6 + D7**：把瞬时错误与真实失败分开，并补最小单元测试。

---

### 6. 不确定性与证据边界

- 我**无法**反证"内存滞后"不存在；能断言的是**本包证据内未出现**。若原始触发来自包外运行（例如某次完整页读会话），该证据不在读集内，我的结论随之改变。
- `direct-cli-release-probe-v2.json` 的 `after` 快照**采样时机无文档**、其生成脚本不在 artifact 集合中，故"即时性"在该文件上只是推论；承重证据是 `observe_switch.py` 的 0.25 s 连续采样。
- 采样文件每行 `processes` 被截断，PID 2850 的完整命令未验证；"GUI 模型共存"是由 `docs/PROJECT_CONTEXT.md:87` 支撑、由采样佐证，而非直接观测到的 GUI 模型已加载。
- 未验证：`SubjectPageCoverage` / 作业载荷在**实际 sqlite** 中是否已存在 v1 身份行（`direct-upload-runtime/enrollment-review-v2.sqlite3` 存在但为二进制，Bash 被拒无法查询）。不过 `direct-read-*-receipt.json` 已证明 v1 身份进入过真实作业载荷与回执。
- 未验证：`R3_ROUTE_CHANGED` / `PAGE_REVIEW_RESUME_NOT_READY` 在真实历史作业上的实际触发（未运行测试与服务）。

---

### 7. 未运行的检查（未完成即未完成）

- 未运行任何测试（`uv run pytest` 等），Bash 被拒；因此"零测试覆盖"是**检索结论**，不是执行结论。
- 未运行 `git log/diff` 以核对 v1→v2 字符串变更的提交与作者（Bash 被拒）。
- 未启动应用、未调用模型、未做浏览器/端口/内存现场验证。

---

### 8. 给 Codex 的定界问题与决策点

1. **前提证据（最高优先）**：是否存在本包之外的观测，显示"进程组确认消失后 wired 仍 > 基线+1GiB 持续若干秒"？若有，请给出该 PID/时间窗/文件；若无，我建议把该门降级为记录型观测，或至少把"仅内存未回落"从硬失败改为可恢复告警。
2. **失败语义由谁裁**：当进程与端口已被确证释放、仅全机计数未回落时，期望行为是①进程级硬封锁（现状）、②记录告警并继续、③受控显式覆盖？并请指定责任方、动作、可接受证据与到期阶段（项目规则要求），我据此给文案与状态码方案。
3. **身份归属**：`lifecycle` 是否必须留在部署身份里？若必须（例如验收要求可追溯"卸载等待策略"），我建议改走 `page_review_execution_versions()` 通道并补 `owned-serial/v1 ≡ owned-serial/v2-memory-settle` 的兼容映射——请确认该兼容判定是否与"后期证据不得静默改写早期结论"一致。
4. **"取消和失败保锁"的预期**：我读到的是**有意的 fail-closed 保留**（fd 保留、`current` 保留、下次 `stop()` 可重试），并未发现保锁泄漏。若 Codex 手上有"取消路径提前关 fd / 未保留句柄"的反例，请给复现步骤（哪个 await 点、哪个异常类型），我按反例重审 §3-D3/D6。
5. **是否需要就 D1 补一份迁移与回归清单**（受影响对象：在途 r3_page_review 作业、已取消待续跑作业、已写入的覆盖度行、历史规范化作业、协议语义缓存）。这属于跨包改动，超出本角色边界，需 Codex 明确授权范围后另行处理。

**安全临时路径（在 1–3 有答复前）**：不修改源码；若必须先恢复可用性，仅建议 Codex 以运营方式处理（先确认无本产品模型进程残留与端口占用，再重启应用），不做任何产品侧热修。

**边界声明**：本输出为只读建议，不构成 Codex 最终临床/产品/生产裁决；我未修改任何文件，也未加载任何模型。
