Now the newly authorized evidence and the changed modules.

# Conference Output: enrollment-memory-settle-review-20260916 - evidence_single_object

## Output

### 0. 状态与证据缺口（先说要紧的）

- 只读完成，未加载模型、未改任何文件、未写入任何路径（含 runner 报告路径）。Bash 仍被拒（无 pytest/git/sqlite/ps）。
- **授权读集中的"lifecycle JSONL"在本工作区不存在。** `xhigh/models.json` 指向 `log_directory .../upright-comparison-v17/xhigh/logs`；`xhigh/logs/*` 与 `upright-comparison-v17/**` 全量列名均无任何 lifecycle 文件。该 run 目录只有 `models.json / view.png / view-identity.json / input.json / memory.jsonl` 与 `0/`、`1/` 两个答案目录。
  → 你给出的 PID 19635 release 事件、PID 22706 started 事件**无法在本工作区独立复核**；我只能用 `memory.jsonl`（唯一授权且存在的文件）交叉验证。`upright-comparison-v17/REVIEW.md` 命中过这些时间戳串，但它不在授权路径内，我**没有读**。
  → 若需要把这批数字变成可入账证据，请把 `xhigh/logs/*.lifecycle.jsonl`（或该 run 的 `REVIEW.md`）显式列入读集。

### 1. `memory.jsonl`（窗口 1789565038–1789565060，采样 1.04 s，16 KiB/页）

| 行 | time | wired pages | GiB |
|---|---|---|---|
| 315 | 5039.283 | 2,187,321 | 33.38 |
| 317 | 5041.379 | 2,313,521 | 35.30 |
| 320 | 5044.522 | 2,405,663 | **36.71** |
| **321** | **5045.565** | **474,908** | **7.25** |
| 322 | 5046.608 | 464,265 | 7.08 |
| 324 | 5048.713 | 2,265,515 | 34.57 |
| 328 | 5052.958 | 5,511,232 | 84.09 |
| 330 | 5055.067 | 5,674,353 | 86.58 |
| 332 | 5059.226 | 2,907,808 | 44.36（compressor 91,484→1,689,101 页） |

校准：你给的 release wired 34,364,194,816 B = 2,097,424 页 = **32.00 GiB**；next started 33,137,328,128 B = 2,022,542 页 = **30.86 GiB**；本机该时段干净地板 = **7.08–7.25 GiB**。

### 2. 这段证据**证明**什么

1. **前提成立（确立）**：release 记录点 32.00 GiB 距地板 7.25 GiB 尚差约 25 GiB，即"进程组+端口已退出"被记录时，前一模型的内存**确实仍在**。v1 语义记录的只是进程/端口，不是内存回收。v2 的注释（`mtplx_owned_server.py:287-288`）由此获得了一次实测支撑。
2. **间隔为零（确立）**：next 进程在 6.4 ms 后 spawn，其 started 快照 30.86 GiB 仍在地板之上约 23.6 GiB → **下一个模型是在前一模型内存几乎全量驻留时被拉起的**。这正是"串行装卸"在 v1 下没有留出任何回收窗口。
3. **回收是亚秒的（确立上界）**：5045.2345（32.00 GiB）→ 5045.565（7.25 GiB），窗口 ≤0.33 s，且此时新进程尚未实质分配。所以新门引入的等待在此场景下是亚秒级，不需要（也不应要求）多秒延迟才承认该问题。
4. **全机 wired 在亚秒尺度可自然摆动约 29.5 GiB**（5044.52→5045.565，此处恰为本产品前一模型的回收）——这条同时也界定了任何"全机计数"判据的分辨力上限。

### 3. 这段证据**不证明**什么

1. 不证明该零间隔/亚秒重叠造成了任何读取失败、重试或质量影响：`memory.jsonl` 只有计数器，run 照常推进到 86.58 GiB 平台。
2. 不证明归因：采样器无 per-process 内存；"32.00/30.86 GiB = 前一模型驻留"是尺寸+时间戳推论，不是对 PID 19635 的测量。
3. 不界定最坏情况：1.04 s 采样下这次窗口只被"擦到"（release 恰好落在 5044.52 与 5045.565 两tick之间）；**≤0.33 s 这个数字来自我看不到的 lifecycle 事件**，本文件单独只能给出"≤1.04 s"。
4. **不证明本次修复在该场景真的生效**——见下 R1/R2。

### 4. 剩余具体正确性缺陷（只列这次窄改动内可修的）

**R1（主要）· 门可能"通过"而自家模型并未回收：判据是全机增量，非产品增量。**
`wired_before_start` 在 `start()` 时捕获（`mtplx_owned_server.py:213-214`），门是 `wired_now <= wired_before_start + 1GiB`（`:294-295`）。基线里若含**非本产品**的驻留（本机常态：每个样本都有 `/Applications/MTPLX.app/...` PID 2850；`docs/PROJECT_CONTEXT.md:87` 记录 8002 曾属 GUI 启动的共享 FlashNext），则该分量在自家驻留期**减少** ≥ 模型体量时会与自家未回收量相互抵消——门在这段时间尺度上无法区分"回收了"和"别人少了"。这与已被接受的误阻断（外部增加 → 永久封锁）是同一结构属性的反面；"保守"只覆盖了封锁方向，未覆盖假通过方向。
最小改动（不动已接受策略、不引入归因）：在门里同时要求"相对停机前读数的下降"，即 `wired_now <= min(wired_before_start, stop_requested 时的 wired) + 1GiB`，并在终态事件里记录用作判据的 `wired_before_start / wired_at_stop / wired_now / threshold`。这两个读数现在**都已经在回执里**（`:189-190` 每次事件都带 `wired_before_start`；`stop_requested` 事件自带 `system_memory.wired_bytes`），所以这是纯读取侧改动。

**R2（主要，且是定界问题）· 这次修复在"动机场景"里是否生效，取决于 PID 19635 自己的 `wired_before_start`。**
若 19635 的基线是在同一"外来/前序驻留未清"状态下捕获的（本 run 正是这种状态：spawn 时 30.86 GiB），则它自己的阈值也被抬高，门在 5045.23 那一刻**不会拦**，动机场景并未被覆盖。该字段现在会写进 19635 的 `started` 事件，但那个文件不在工作区。**请给出该值**；它同时是 R1 的现场判定依据。

**R3 · 终态事件语义仍由继承关系承载。** `MtplxMemoryReleaseIncomplete` 仍 `isinstance` 于 `MtplxShutdownIncomplete`（`:43-46`），而后者文档契约是"keep the hardware unavailable until this PID has exited"（`:35-40`）——内存门触发时 PID 已退出。新代码把 `except MtplxMemoryReleaseIncomplete`（`:303-305`）排在 `except MtplxShutdownIncomplete`（`:306-308`）之前是正确且必需的，但任何按基类判断的消费方（今天全仓无）会得到相反语义。廉价硬化：保留事件分离，同时修正基类契约表述或让两者并列继承 `MtplxOwnershipError`。

**R4 · `process_and_port_exited` 对同一 handle 非唯一。** `released` 只在成功路径置位（`:310-314`），内存门失败后每次重试都会重跑全流程并再记一组 `stop_requested` + `process_and_port_exited`（`:276, 285`），`memory_settle_incomplete` 亦可出现多次。审计可读（时间戳不同），但"该 handle 的端口退出时刻"不再是单值。廉价改动：对该事件加一次性标记（布尔或序号）。

**R5 · `admission_fd` 双关闭窗口（潜在）。** `finally` 里先判 `self.admission_fd is not None` 再 `os.close`（`:311-313`），`os.close` 非幂等；若同一 handle 被并发 `stop()`（`ready()` 的失败路径与 `_release()` 同时进入）且恰好交错，第二次 `os.close` 抛 `EBADF`，会从 `finally` 逃逸并顶替原异常。当前仅靠类文档"single caller must serialize access"（`:170-175`）与 owner 锁串行化兜住。硬化 2 行：`fd, self.admission_fd = self.admission_fd, None` 后再关，或 `try/except OSError`。

**R6 · 发布策略只落在 per-launch JSONL。** 部署身份按你的决定保持 `owned-serial/v1`（`mtplx_model_lifecycle.py:193`）——兼容性正确；代价是 `release_policy: "memory-settle/v1"`（`mtplx_owned_server.py:189`）不进任何产品持久化的作业/覆盖度身份。审计"哪些历史读取跑在带门策略下"只能靠 PID/时间 join 日志目录。记为残余限制，非缺陷。

**R7 · 复用探活失败仍会卸载并可能顶替原错。** `ready()` 的 `except BaseException` 调 `stop()`（`:268-270`），对**已驻留且健康**的进程，一次 `/health` 抖动仍会卸载 80 GiB 级模型；现在还会叠加 30 s 级内存门，并可能以 `memory_settle_incomplete` 顶替原始健康错误。沿用既有"未知传输结果不得保留可能在生成的进程"策略时请注意：健康探测失败不是传输结果，二者不同源。一行残留，非本次引入。

### 5. 已确认无缺陷 / 无泄漏（供你收口）

- 有界阶段算术与你的表述一致：单次 `stop()` 最坏 = 60 s（SIGTERM+SIGKILL 各 30，`:140-151`）+ 30 s 端口（`:280-284`）+ 30 s 内存（`:289-300`）≤ 120 s；不是 30 s 总计。重试会重付。
- 重复 `stop()` 幂等：`if self.released: return`（`:273-274`）+ `released` 仅在 `port_released and not _group_alive` 时置位（`:310-314`），故 `ready()` 失败后下一次 `_prepare` 走 `_release()` 立即返回并新建句柄，不再重付门；`current` 保留语义未变（`mtplx_model_lifecycle.py:46-49`）。
- 取消保留锁：门期间 `port_released` 仍为 False ⇒ fd 不关、`released` 不置位、`current` 不清空（`:305, 309-314`；`mtplx_model_lifecycle.py:47-49`），fail-closed 符合预期；进程退出时 OS 释放 flock，未发现泄漏路径。
- 不杀无关进程：所有权仅经 `Popen` 句柄 + `os.killpg(process.pid, …)`（`:134-147`），`ps -axo pgid=` 只读（`:126-129`）。
- `_finish_cleanup` 的 shield 语义不变，取消不会留下活进程（`:155-165`）。
- 身份兼容缺陷已消除：`owned-serial/v1` 恢复后，`page_review_job_executor.py:55-56`（`R3_ROUTE_CHANGED`）、`page_review_job_service.py:205-210`（409 续跑）、`page_review_coverage_selection.py:58-60`、`deepseek_evidence_normalizer_transport.py:542-543`、`protocol_semantic_transport.py:371-393` 五处比较对本次改动不再敏感；模型/提示词/合同身份未变，与我上一轮的判断一致。

### 6. 残余限制

- 本文件的 1.04 s 粒度不能给出回收时长的分布；"亚秒"上界的精确值依赖我看不到的 lifecycle 事件。
- 全机 wired 无法区分产品/非产品（你已接受）；R1 说明该性质同样削弱**通过**方向的可信度，而不仅是封锁方向。
- 未验证：`xhigh/logs` 在源机上是否存在（本工作区无）；该 run 的 release/start 事件时间戳；PID 2850 当时实际驻留体量。

### 7. 定界问题

1. 请给出 PID 19635 `started` 事件的 `wired_before_start`（或其 `system_memory.wired_bytes`）。这是判定 R2"动机场景是否真被覆盖"的唯一现场依据；若它 > 地板+10 GiB，则本次门在该场景不生效，需要按 R1 的 `min(...)` 判据补一次。
2. R1 的 `min(wired_before_start, wired_at_stop) + 1GiB` 是否可作为门内判据接受（只读回执已有字段，不新增归因、不改你已定的封锁/不杀进程策略）？若不接受，请明确"假通过"是否为有意接受的风险，我据此刻入残余限制。
3. R3–R5 三项（契约表述、事件唯一性、fd 双关）是否授权为有界修补？如否，我按潜在项保留在报告而不要求改动。

**边界声明**：以上为只读建议，不构成 Codex 最终裁决；未做临床/产品验收，未修改任何文件，未加载任何模型。
