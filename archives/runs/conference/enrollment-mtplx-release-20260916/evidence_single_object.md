I'll start from the conference context and plan, then independently audit the MTPLX process-lifecycle and page-review harness sources.The conference packet is a stub, so I'll treat the three named source files as the source of truth and audit process-exit, flock, and payload validation next.I have the three sources; next I’ll check payload/schema contracts, lifecycle tests, and flock/process-group behavior so defects are tied to line numbers.I'll read the payload contract, MTPLX tests, and the prior conference note so I can separate confirmed defects from reused claims.# Conference Output: enrollment-mtplx-release-20260916 - evidence_single_object

## Output

只读审阅。未改源码、未启动 MTPLX/未跑模型、未读临床资料。会议 context/plan 仍是 TODO 骨架，不以它们为源。进程组/flock 结论来自当前源码 + 本机 Python 3.12 上对 **POSIX 语义** 的替代进程探测（不是 MTPLX 二进制）。**进程组消失 ≠ GPU 显存释放**；后者本轮无法验证。

最高影响问题：`stop()` 的完成条件只认「原 session 的 PGID」，不认子孙树、监听端口或 GPU。`setsid` 逃逸的子孙会让 `_group_alive` 为假，从而关掉 flock 并报告退出成功。

---

### 1. Evidence

**读过的材料**

- `context/enrollment-mtplx-release-20260916_conference_context.md`、`plans/codex_main_venue_enrollment-mtplx-release-20260916.md`：Source of Truth / Scope 均为 TODO。
- 当前源码：`app/llm/mtplx_owned_server.py`、`app/llm/mtplx_model_lifecycle.py`、`app/llm/page_review_harness.py`、`app/domain/contracts/page_review.py`（`ClauseEvidenceSignal` / `PageReviewPayload`）、`app/llm/mtplx_schema_compat.py`、`app/llm/page_review_format_repair.py`（`evaluate_page_review_response` → `PageReviewPayload.model_validate`）。
- `tests/` 无 `OwnedMtplxServer` / `_group_alive` / `pass_fds` / `admission_fd` 测试。
- 运行时：`requires-python = ">=3.12,<3.13"`；本机 `uv run python` = CPython 3.12.13。Darwin `flock(2)`：锁在文件上，fork/dup 是同一把锁的多个引用；子进程 `LOCK_UN` 会解除父进程的锁。

**独立进程组**

```85:113:app/llm/mtplx_owned_server.py
def _group_alive(process: subprocess.Popen) -> bool:
    process.poll()
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        return False
    return True
# SIGTERM → 等待 → SIGKILL → 再等待；仍活则 MtplxShutdownIncomplete(process.pid)
```

- 启动：`start_new_session=True`（`160:162:app/llm/mtplx_owned_server.py`）。所有权句柄是这次 `Popen`，不按端口杀别人（`155:156` 占用即失败）。
- 本机替代进程：session leader 的 pid==pgid；leader 先退后，仍留在原 PGID 的孙进程可被 `killpg` 打到。
- 本机替代进程：孙进程 `os.setsid()` 后原 PGID 的 `killpg(0)` 得 `ProcessLookupError`，逃逸进程仍活。此时 `_group_alive` 为假。

**取消**

```116:126:app/llm/mtplx_owned_server.py
# shield + 循环吞掉 CancelledError，等 _stop_owned 结束再重新抛出
```

- 本机 3.12 C `Task`：取消后 **不是** 忙等死锁；`_stop_owned` 能跑完（探测：`n=2`，`slow-done` 后主任务再收到 `CancelledError`）。
- `ready()` 对任意 `BaseException`（含取消）先 `await self.stop()`（`205:207`）。`_prepare` 在复用已驻留句柄时仍每次 `ready()`（`51:60:app/llm/mtplx_model_lifecycle.py`）。
- `session` / `sync_session`：非 4xx/429 的 `BaseException`（含 `CancelledError`）走 `_release()` → `stop()`（`21:24, 70:73, 90:93`）。4xx 显式拒绝可保活。

**跨进程 flock 与继承**

```148:166:app/llm/mtplx_owned_server.py
lock_path = .../enrollment-mtplx-{uid}.lock
fcntl.flock(fd, LOCK_EX|LOCK_NB)
Popen(..., start_new_session=True, pass_fds=(fd,))
# 注释：The child retains admission if the application exits unexpectedly.
```

- `stop()` 仅当 `not _group_alive` 才 `os.close(admission_fd)`（`209:215`）。组仍活则保持锁；`ShutdownIncomplete` 时 `_release` 不把 `current` 置空（`45:49`）。
- 本机 Darwin + `Popen(pass_fds)`：
  - 父进程 `close(fd)`、子进程保持该 fd：第三方 `LOCK_EX|LOCK_NB` → **BLOCKED**。
  - 父进程 `_exit`、子进程保持该 fd：→ **BLOCKED**。
  - 父进程 `close(fd)`、子进程关掉 3–255 号 fd：→ **GOT_LOCK**。
- 启动失败路径在 `Popen` 之前 `os.close(fd)`（`163:165`），会释放本进程的锁引用。

**v16 region 与 PageReviewPayload**

- 提示版本：`PAGE_REVIEW_PROMPT_VERSION = "page-review-r3/v16"`（`66:app/llm/page_review_harness.py`）。
- 合同：`region: PageRegion | None = None`；`json_schema_extra` 的 if/then/else；`require_signal_excerpt`：非 `none` 必须有 `PageRegion`，`none` 不得带摘录（`165:181:app/domain/contracts/page_review.py`）。
- `model_json_schema()` 实测：`required == ["clause_id","signal"]`；`region` 为 `anyOf[PageRegion,null]` + `default: null`；if/then/else 存在。
- v16：`required.append("region")`（`404:408:app/llm/page_review_harness.py`）。Pydantic 每次返回新 dict，**不污染**后续 `model_json_schema()`。
- 校验入口仍是 `PageReviewPayload.model_validate`（`127:128:app/llm/page_review_format_repair.py`）。实测：`signal=none` 省略 `region` 合法；`signal=mentions` 省略 `region` 失败（「必须携带原文摘录」）。
- MTPLX 约束解码会删掉 if/then/else（`11:12:app/llm/mtplx_schema_compat.py`）；产品校验仍保留。`tests/v2/llm/test_page_review_transport_options.py` 明确覆盖这一点。

**未做的检查**

- 未 exec 已安装 `mtplx`，未知它是否 `setsid`/关额外 fd。
- 未测 GPU / Metal 显存。
- 未把 `owned_mtplx_server()` 当作产品路径（全库无其它引用；产品走 `MtplxModelOwner`）。

---

### 2. Inference

1. **`stop()` 成功只证明「原 PGID 里已经没有可信号的成员」。** 若 MTPLX 工作进程 `setsid`/`setpgid` 离开该组：`_group_alive` 为假 → 关掉 flock → `_release` 丢掉句柄 → 下一轮 `start()` 只剩端口探测。监听口仍被孤儿占着时，会误报「其他服务」且不能加载下一模型；孤儿已死、口已空、GPU 仍占时，会再拉起第二个权重。这是当前完成谓词的结构洞，不是「killpg 写错 pgid」（在 `start_new_session` 且子孙留组时，pid==pgid 是对的）。

2. **异常父退出时的 flock 继承，成立条件是子进程不关继承来的 fd。** 源码注释把它写成无条件事实。父进程还活着时父 fd 自己持锁，不受 MTPLX 关 fd 影响；父进程崩溃后，若 MTPLX 关掉额外 fd，锁会掉。之后若尚未 bind，第二个体可以再 `Popen`；已 bind 则 `_port_in_use` 仍 fail-closed。`pass_fds` 没有第二持有者。

3. **取消路径在 3.12 上能把 SIGTERM/SIGKILL 跑完**，不要按「shield 死锁」报缺陷。真正的取消问题是：复用中的 `ready()` 把探活失败/取消当成「启动失败回收」，会拆掉已经驻留的组。一次页读取消会经 `session` 的 `CancelledError` 再 `stop()` 整组——若产品意图是「生成可能仍占 GPU，必须卸车」则自洽；它仍然只卸进程组，不证明显存归还。

4. **v16「region 必填」与合同校验没有 fail-open 漏洞。** 非 `none` 缺 region 仍被 `require_signal_excerpt` 拒绝。差异是单向加严：v16/提示要求 **键必须出现**（`none` 则为 `null`）；Pydantic 因 `= None` 允许 `none` 省略键。MTPLX 去掉 if/then 后，约束解码仍允许 `evidence_for + region:null`，会被合同打回并走格式纠正——这是既有测试承认的分工，不是 v16 新开的洞。

5. **任何「组已死 / flock 已释放 / `poll()` 非空」都不能写成 GPU 空闲。** 驱动、运行时缓存、逃逸子孙都不在这两个文件的 API 里。

---

### 3. Recommendation

只列最小修订，按优先级。

1. **`OwnedMtplxServer.stop`：组空之后、关 `admission_fd` 之前，再看本 spec 的 `(host,port)`。** 仍占用则 `MtplxShutdownIncomplete`，保持 flock。这补上「`setsid` 孤儿仍占端口」的假完成，仍然 **不等于** GPU 释放。改动面：`stop()` 约 209–215 行，或把 host/port 传入 `_stop_owned`。

2. **不要把 flock 押在 MTPLX 不关 fd 上。** 在 `setsid` 之后、`exec` 之前 `fork` 一个同 PGID 的 pause 持有者（或等价 wrapper），只负责占着 lock fd；`killpg` 会一并收掉。父崩溃时即使 `mtplx` 关了额外 fd，持有者仍挡第二个体。不要让 MTPLX 去 `LOCK_UN`（Darwin 上会把父锁一起解开）。

3. **拆开「首次启动失败回收」和「复用探活」。** `_prepare` 仅对刚 `start()` 的句柄让 `ready()` 失败即 `stop()`；已驻留句柄的探活失败/取消应抛错并保留句柄，取消卸车交给 `session` 的 `CancelledError` 路径。避免第 N+1 页的 `/health` 取消拆掉第 N 页刚用完的组。

4. **v16 与合同对齐（低优先级，非 fail-open）。** `ClauseEvidenceSignal.region` 去掉 `= None`，键必填、值仍可为 `null`；保留现有 validator。则 `model_json_schema()["required"]` 自带 `region`，`append` 变成空操作。不要在解码侧恢复 if/then 来「代替」产品校验。

5. **不要** 按端口杀未持有的 PID、不要把 flock 升级成全机 GPU 锁、不要把 `poll() is None` 或 `ShutdownIncomplete` 未抛当作显存已释放。

---

### 4. Uncertainty

- **MTPLX 二进制**：是否关非 stdio fd、是否再 `setsid`/`setpgid`、SIGTERM 后工作线程是否仍占 GPU——未跑，保持 `pending`。
- **GPU / 驱动**：本角色没有硬件观测。即便 `killpg` + 端口空，仍可能残留 Metal/CUDA 上下文。
- **非 Darwin flock**：本探测在 macOS 上。Linux 上 flock 跟打开文件描述绑定，父死子持 fd 通常仍锁；未在本轮复测。
- **PID/PGID 复用**：`shutdown_seconds` 默认 30s×2，窗口内复用概率低，源码未处理 `PermissionError`。
- **`close()` 无超时地等 `owner.lock`**（`95:102:app/llm/mtplx_model_lifecycle.py`）：在途 session 不结束则关停被堵住。JobRunner 是否在 lifespan 里先取消页读，不在本任务的两个文件里证完。
- 未跑 pytest；schema 行为来自一次解释器探测。

---

### 5. 异议、决策点、给 Codex 的有界问题

**异议**

- 把「`killpg` + flock + shield」当成已经闭环的释放协议，过满。源码只闭环了 **本产品、本 uid、原 PGID、advisory flock**。
- 注释「子进程在应用异常退出后仍持有 admission」在本机只有「子进程不关 fd」时成立；写成无条件会误导验收。
- v16 `append("region")` 不是合同漏洞；真正缺口是 MTPLX 去掉 if/then 后，非 `none` 仍可能解码出 `region: null`，靠事后 `model_validate` 拦截。那是既有分工，不必再靠 v16 填一次。
- `_finish_cleanup` 在 3.12 上可工作。若后续审查再报「取消死锁」，需要新的运行证据。

**请 Codex 裁决**

1. 已安装 MTPLX 是否保证：所有 GPU 工作进程留在 `Popen.pid` 这个 PGID，且不关闭继承 fd？**这决定建议 1+2 是必须还是防御。** 本角色不能跑该二进制。
2. `stop()` 完成条件要不要包含「本机端口已空」？建议要。仍须在操作手册写明：端口空 ≠ GPU 空。
3. 页读取消是否必须拆掉驻留进程？若必须，接受每次取消后最长约 `2 * shutdown_seconds` 的组信号等待，以及随后可能的冷启动。若否，只取消 HTTP，把卸车留给 `close()` / 换模型。
4. `ClauseEvidenceSignal.region` 是否改为无默认值以匹配 v16 键必填？建议改；不改也不开 fail-open。

**Codex 回答前的暂定安全路径**

- 不要把「`stop()` 返回 / flock 可再获取 / `poll()` 非空」写成可加载下一模型的硬件空闲证明；硬件租约继续由调用方持有，直到有独立的 GPU/端口观测。
- 在 MTPLX 的 fd/`setsid` 行为未证实前，不要依赖「父进程被 kill -9 后 flock 仍挡住第二个体」作为唯一互斥；启动窗口仍可能并跑。
- v16 与 `PageReviewPayload` 可视为 **值级 fail-closed、键级提示更严**；不必为 region 阻塞本生命周期修复。

本角色不声称最终验收。GPU、真实 MTPLX 二进制、生产路径保持 `pending`。
