我将按只读源码审阅约束，先独立核对目标、初始读集和生命周期接线，再给出确证问题与最小修复。上下文和计划只是骨架，接下来按初始读集核对实际接线，而不是按计划里的 TODO 做推断。核心接线已经看到了；接下来核对共用入口是否被绕过，以及同步调用是否会落进事件循环。# Conference Output: enrollment-owned-mtplx-wiring-20260916 - evidence_single_object

## Output

只读源码审阅。未运行应用、测试、模型或浏览器；未读 `.env`、数据库或临床原件。`ENROLLMENT_MTPLX_MODELS_FILE` 未设定时，下列生命周期全部是空操作，当前进程不会拉起或卸载 MTPLX。以下缺陷针对**一旦该文件被设定后的实际接线**，不是对临床读片设计的重做建议。

### Evidence（源码事实）

**所有权与杀进程边界**

- `OwnedMtplxServer.start` 只对 `self.process` 这个 `Popen` 发 `terminate`/`kill`。端口占用走 `connect_ex`，占用则抛错，不按 PID/端口杀别人：`app/llm/mtplx_owned_server.py` 第 75–78、134–141、81–100 行。
- 切换前必须 `stop()` 确认退出；失败抛 `MtplxShutdownIncomplete` 且 `_release` 在 `stop()` 成功前不把 `current` 置空：`mtplx_owned_server.py` 第 27–32、99–100 行；`mtplx_model_lifecycle.py` 第 38–42 行。
- `OwnedMtplxServer` 是普通 dataclass + `Popen`，不是 async generator。`sync_session` 用短寿命 `asyncio.run(_prepare)` 做启动/健康检查，HTTP 在 loop 外同步进行：`mtplx_owned_server.py` 第 117–123 行；`mtplx_model_lifecycle.py` 第 69–84 行。

**串行锁**

- 进程内唯一 `MtplxModelOwner`，`threading.Lock` 同时服务 async `session` 与 sync `sync_session`。锁覆盖「准备 + 整段调用」，不是只覆盖启动。
- 页读：`resolve_route_model` / `direct_openai_completion` 走 `mtplx_model_session`（`page_review_harness.py` 第 272–276、479–487 行）。
- 方案解构：`_send_completion` 走 `sync_mtplx_model_session`（`protocol_semantic_transport.py` 第 495–501 行）。
- 证据整理：`_request` 走 `sync_mtplx_model_session`（`deepseek_evidence_normalizer_transport.py` 第 338–344 行）。
- 关闭：V2 lifespan 在 runner `join` 之后 `await close_owned_mtplx_models()`（`app/api/v2/app.py` 第 403–425 行）。

**作业图**

- 两路都是 `LOCAL_PAGE_PROVIDERS`（`omlx`/`mlx-serve`/`mtplx`）时 `serial_lanes=True`：先全部 main-A，再全部 main-B（`page_review_job_service.py` 第 50–72、119–121 行）。
- `shared_reader_parallelism` 有任一本地读道则本地只占 1 个槽（`page_reader_capabilities.py` 第 15–21 行）。Runner 仅在 `max_parallel_steps>1` 且多步可运行时开 `ThreadPoolExecutor`（`jobstore.py` `list_runnable_steps`；`runner.py` 第 261–286、481–512 行）。
- 页读 API 是同步 `def`（`page_review.py`），FastAPI 会丢进线程池；`PageReviewRuntime._prepare`/`resume` 在该线程里 `asyncio.run(preflight_page_reader_routes)`（`page_review_runtime.py` 第 59–64、160–166 行）。预检用 `asyncio.gather` 同时解析两条读道（`page_review_harness.py` 第 327–329 行）。
- 页读步骤本身在 JobRunner 线程里 `asyncio.run(run_cancellable(read_page, ...))`（`page_review_job_executor.py` 第 155–158 行）。取消时父任务抛 `StepFailure`，`finally` 里 `task.cancel()` 再 `await task`（`page_review_cancellation.py` 第 10–34 行）。

**异常即卸载**

```55:67:app/llm/mtplx_model_lifecycle.py
    async def session(...):
        ...
        try:
            health = await self._prepare(spec)
            yield health
        except BaseException:
            await self._release()
            raise
```

`sync_session` 同样在 `except BaseException` 里 `asyncio.run(self._release())`。`ready()` 对任意 `BaseException`（含取消、健康检查失败）都会 `stop()`（`mtplx_owned_server.py` 第 157–178 行），而 `_prepare` 在**复用已驻留进程**时每次仍调用 `ready()`（`mtplx_model_lifecycle.py` 第 44–53 行）。

**入口覆盖缺口**

- `protocol_control_agent_transport.py` 与 `phase_applicability_transport.py` 都声明 `mtplx`/`mtplx-api`，但 `_complete` 直接 `chat.completions.create`，不进 `sync_mtplx_model_session`。
- `owned_mtplx_server()` 这个 async contextmanager 无产品引用；产品路径是 `MtplxModelOwner` 持有 `OwnedMtplxServer`。

**配置身份**

- 进程身份：`ENROLLMENT_MTPLX_MODELS_FILE` 的绝对路径 + 文件 sha256。运行中文件变更或环境变量被清空会拒绝新 session，但不会自动 `close`（`mtplx_model_lifecycle.py` 第 101–117、159–168 行）。
- 作业身份：`route_identity` 只有 `provider/base_url/model/reasoning_effort/max_tokens/...`，不含 `executable`/`model_path`/文件哈希（`page_review_job_service.py` 第 75–87、196–202 行）。

### Inference（由源码推出的行为，非运行观测）

1. **双驻留（两个本产品拉起的 serve）在持锁路径上被故意堵住。** 切换先 `_release`；`ShutdownIncomplete` 时不 `start`；`poll()` 已死后才放弃句柄；新 `start` 发现端口占用只拒绝、不杀。这与「本锁只协调本产品进程、端口占用拒绝」一致。
2. **真正的高风险不是双进程，而是「任何失败都拆掉唯一驻留」。** `direct_openai_completion` 把 HTTP 放在 `session` 里面；`read_page` 对 429/endpoint 会重试；方案解构对 5xx/429/连接错误最多 3 次。每一次抛错都会 `_release` → 下次重试走最长 600s 冷启动。取消路径（`run_cancellable` → `CancelledError` → `_release`）是符合「取消释放」的；把普通传输错误算进 `BaseException` 则过宽。
3. **复用中的 `ready()` 会把已健康进程杀掉。** 反例：模型 A 已驻留并完成第 N 页；第 N+1 页 `_prepare` 再探 `/health`；探测被取消或对身份字段一次误判，`ready()` 的 `except BaseException` 直接 `stop()`。这不是「启动失败回收」，是误卸载。
4. **关闭与排队：进程替换是安全失败，请求层会互相踩。** `close()` 先置 `closing=True` 再抢锁；抢到后的 session 会在 `_prepare` 失败。但 `except BaseException` 仍会再 `_release`，与 `close()` 的 `_release` 串行，不构成双启。`close_owned_mtplx_models` 在 `close()` 返回前不把 `_owner` 置空，因此关停完成前不会新建第二个 owner。
5. **同步入口源码上不允许跑在运行中的事件循环里**（`get_running_loop()` 成功则抛错）。方案/整理走 JobRunner 线程；页读 enqueue/resume 是同步路由 + `asyncio.run`。`async def start_deconstruction` 只入队，不在事件循环里调 `_send_completion`。
6. **方案工作流并未全部进入同一把锁。** 同一解构作业里的 phase-applicability、以及独立的 protocol-control，都可以在 worker 里对同一 `base_url` 发请求，却不持有 `owner.lock`。此时 API 线程的页读预检可以抢走锁并切模型，把无锁请求打到正在退出的进程上。单 JobRunner「一次一个 job」减轻了双作业并行，但挡不住 API 预检与 worker 重叠。
7. **预检 `gather` 两条 mtplx 读道（不同 `model`）会在入队时强制 A→停→B，作业随后又从 main-A 开始再切回 A。** 锁保证不会双启，但每次 enqueue/resume 都可能多一次完整卸载/加载。
8. **旧作业身份与加载配置身份是断开的。** 进程内改文件：后续页读/方案调用在 `configured_mtplx_owner()` 处失败，已冻结 payload 的作业不能继续。重启后若 `PAGE_REVIEW_*` 字符串没变，resume 认为身份一致，但新 owner 可能加载另一份权重。

### Recommendation（最小修复，按优先级）

1. **`session` / `sync_session` 不要对普通 `Exception` 做 `_release`。** 只在 `CancelledError` / `GeneratorExit` / `KeyboardInterrupt` / `SystemExit`、以及明确的关停/切换路径卸载。传输超时、429、5xx 应保留驻留，让现有重试逻辑真正复用进程。这是最高优先级，改动面限于 `mtplx_model_lifecycle.py` 两处 `except BaseException`。
2. **把「首次启动失败回收」和「复用探活」拆开。** `_prepare` 仅在刚 `start()` 的句柄上让 `ready()` 失败即 `stop()`；已驻留进程的探活失败应抛错并保留句柄，取消则交给 session 的取消释放。避免健康检查误杀。
3. **phase-applicability 与 protocol-control 的 mtplx 完成路径必须走同一 `sync_mtplx_model_session`。** 否则「页读/方案/整理共用入口」在方案工作流内部就不成立，关停/切换可以在无锁请求仍在飞行时发生。
4. **作业冻结身份补上 models 文件哈希或 `model_path`。** resume/续页应拒绝「路由字符串相同、权重文件已变」。进程内文件变化：应拒绝**新 owner**，但已构建的 owner 应能把已入队作业做到下一个安全边界，而不是让下一页直接炸在 `configured_mtplx_owner()`。
5. **预检不要 `gather` 两条需要互斥 GPU 的 mtplx 读道。** 改为同一把锁下顺序探活；能复用则不切。这是性能/关停抖动修复，不是双驻留修复。

不建议：按端口杀进程、把锁升级成跨应用互斥、为这次审阅新增测试文件、重做入排临床流程。

### Uncertainty（未做运行验收，不得当作已证实）

- 未跑：取消后 `Popen` 是否总在 `shutdown_seconds` 内退出；MTPLX 子进程/worker 是否会在父进程 `poll()` 已死后仍占端口或 GPU。
- 未跑：`asyncio.run(_prepare)` 结束时 httpx/异步生成器收尾是否在某 Python/httpx 版本上误伤进程（源码意图是不会）。
- 未跑：`str(OpenAI.base_url)` 与 models 文件 `base_url`、页读 `PAGE_REVIEW_*_BASE_URL` 三者在真实配置下是否总能 `rstrip('/')` 对齐；对不齐会失败关闭，表现为「生命周期已开但所有 mtplx 调用立刻 `MtplxOwnershipError`」。
- 未跑：API 线程 `asyncio.run(preflight)` 与 JobRunner `asyncio.run(read_page)` 的真实重叠时序。
- 当前仓库未设定 `ENROLLMENT_MTPLX_MODELS_FILE`，上述生命周期在本进程中**尚未激活**。

### 对计划/前提的异议

- 会议计划和 context 仍是 TODO 骨架，不能当源。接线真相在 `mtplx_owned_server.py` / `mtplx_model_lifecycle.py` 及三处调用点。
- 「共用入口」若只算页读 harness + 方案语义 + 整理 `_request`，源码是接上了；若「方案」包含解构作业里的 phase-applicability/protocol-control，则**没有**共用入口。按产品语义，后两者会打同一本机地址，必须进锁。
- 「取消释放」已被写成「任何异常都释放」。这会把重试变成反复冷启动，并在 `ShutdownIncomplete` 时把 owner 钉死。这不是更安全，是更脆。
- 双驻留防护在持锁路径上是认真做的；把审阅重点理解成「再设计一套临床双模型」会偏题。问题是生命周期状态机过宽卸载 + 入口漏接。

### 请 Codex 裁定的问题（阻塞结论的部分）

1. 传输错误是否必须卸载？我建议否。若产品坚持「任何失败都腾 GPU」，需要接受页读 429/一次 endpoint 失败就 600s 冷启动，并写进操作预期。
2. phase-applicability / protocol-control 是否必须进同一 mutex？我建议必须。若确认它们生产路径永远不是 mtplx，应在构造时拒绝 `mtplx`/`mtplx-api`，而不是静默直连。
3. 旧作业身份以谁为准：冻结的 `routes` 字符串，还是 models 文件哈希/`model_path`？我建议 resume 必须同时匹配，否则会在重启后用新权重续旧作业。

### 暂定安全路径（在 Codex 回答前）

不要打开 `ENROLLMENT_MTPLX_MODELS_FILE` 做生产。未激活时行为与现在一致：不拉起、不卸载、不杀端口上的别人。若要激活，先改 `except BaseException` 与 `ready()` 复用停机，再把漏掉的两个 mtplx 传输接进 session；在此之前，预检 `gather` 与文件哈希/作业身份分裂仍是已知风险。

本角色不声称最终验收。未验证运行的项保持 `pending`。
