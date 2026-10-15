我按会议角色做只读审阅：先读指定源码与任务上下文，再核对启动链、仅查看模式与同源服务边界。关键启动链已读完。接下来核对只读打开、schema 校验语义、GET 消费者是否会写库或调模型。`verify_schema` 返回差异列表，空列表为一致。接下来核对 GET 路由副作用、服务构造与桌面生命周期。# Conference Output: t7-desktop-readonly-20260914 - evidence_single_object

## Output

独立只读审阅结论：**仅查看链路在存储与 HTTP 写面上是收口的；最高影响缺口在产品合同与前端工作台仍未按 `can_modify=false` 收口，而不是生命周期泄漏。** 未运行测试、应用、模型、数据库或浏览器，不宣称临床或运行验收。

---

### 证据（源码已核对）

**启动链**

- `scripts/start_v2_desktop.command:13-18` 用 osascript 在「开始工作 / 仅查看已有资料」中选择，仅后者追加 `--browse-only`，然后 `exec` `.venv/bin/python -m scripts.run_v2_desktop`。
- `scripts/run_v2_desktop.py:23-59` 先写 `ENROLLMENT_ENV_FILE`，再 `import app.config`，再 `create_desktop_app(..., browse_only=...)`；`127.0.0.1:0` 独占绑定；`server.started` 后才打印 URL 并 `webbrowser.open`；仅查看打开 `#/reports`，正常模式打开 `#/protocols`。
- `app/api/v2/desktop.py:12-22` 先 `require_product_frontend`，再 `create_app(..., browse_only=...)`，然后注册 `/api/{path:path}` 兜底 404，最后 `StaticFiles(..., html=True)` 同源挂前端。
- `app/api/v2/app.py:152-154`：`browse_only=True` 时直接返回 `create_browse_app`，不进入 `upgrade_or_fail` / 启动恢复 / `JobRunner` / `OmlxGateClient` 实例化。

**仅查看打开与释放**

- `app/storage/read_only.py:20-49`：库文件不存在则拒绝；`sqlite3.connect(as_uri() + "?mode=ro", uri=True)` + `PRAGMA query_only = ON`；核对 alembic head 与 schema 差异列表；失败路径 `engine.dispose()`。
- `verify_schema_matches_metadata`（`app/storage/migrate.py:539-555`）返回**差异清单**，空列表为一致。`read_only.py:44-45` 对非空列表拒绝打开，语义正确，不是反转。
- `app/api/v2/browse.py:27-40`：`open_read_only` 成功后，服务构造与 `yield` 包在 `try/finally`，`engine.dispose()` 总会跑。这与 `app.py:357-367` 标准模式「`app.state.engine` 赋值后，初始化失败也要释放」是同一类防护。
- `resolve_data_paths`（`app/storage/config.py:101-115`）只拼路径，不 `mkdir`。`WriteBoundary.create`（`app/storage/boundaries.py:29-35`）只做路径重叠检查，不写盘。

**仅查看是否触发写入或模型**

- HTTP：`browse.py:44-53` 非 GET/HEAD/OPTIONS 一律拒绝；`browse.py:59-65` 只从现有 router 复制 `methods <= {GET,HEAD,OPTIONS}` 的 `APIRoute`。FastAPI 在 `add_api_route` 时已把 router prefix 写进 `route.path`（安装源码 `fastapi/routing.py:1387`、`1762-1764`），复制后路径仍是 `/api/v2/...`，不是丢前缀。
- 已纳入 GET 的模块（`evidence.py` / `evidence_processing.py` / `patient_profiles.py` / `review_history.py` / `subjects.py` / `protocols.py` 的 `projects_router`）中，**没有** `session.begin()` / `create_job` / `enqueue`。`PatientProfileService.latest/history` 只派生 `stale`，注释与实现均声明不改历史行（`patient_profile_service.py:220-248`）。
- 未纳入：jobs、page-review、eligibility、review-actions、fact-normalization、protocol deconstruction 命令路由。`create_browse_app` 不建 `JobRunner`、不做 `run_startup_recovery`、不 `OmlxGateClient()`。
- 仍会构造写向服务：`EvidenceUploadService`（内含 `JobService`）、`ProtocolWorkbenchService`（默认 `feedback_reviser=_revise_feedback_with_model`）、`SelectiveVisionPostprocessJobService`（`browse.py:34-37`）。构造函数本身不写库；对应 GET（预览、正式项目列表、视觉任务投影）是读。
- 导入耦合：`desktop.py:7` 无条件 `from app.api.v2.app import create_app`，因此仅查看仍会加载 `JobRunner`、`OmlxGateClient`、`omlx_http_inference`、语义预检等模块。`OmlxGateClient.__init__` 不加载门禁脚本；脚本在 `_gate()` 才加载（`omlx_gate.py:134-153`）。
- `run_v2_desktop.py:25` 导入 `app.config` 时，模块级执行 `OMLX_BASE_URL = os.getenv(..., _discover_omlx_base_url())`（`app/config.py:111-128`），会读本机 oMLX 配置路径。这是读配置，不是推理调用。
- 标准「开始工作」：`should_run_semantic_route_preflight` 默认 True（`protocol_semantic_route_preflight.py:388-396`），随后 `atomic_write_bytes` 写 `runtime/protocol-semantic-route-preflight.json`（`app.py:169-178`），并启动 `JobRunner`。这是正常写服务，不是仅查看。

**正式构建身份与同源**

- `desktop_frontend.py:7-31` 要求 `enrollment-product-build/v1`、`interface_trial is False`、`protocol_stub is False`、`api_base == ""`、`asset_base == "/"`，并按清单 SHA-256 核对每个文件（含 `index.html`）。失败中文拒绝，不回退试用页。
- `frontend/vite.config.ts:16-32` 仅 `apply: "build"` 生成该清单；`interface_trial` 在 `mode === "test"` 或 `VITE_ENROLLMENT_INTERFACE_TRIAL=true` 时为 true，正式构建应为 false。
- 前端同源：`getProtocolApiBase()` 在未设 `VITE_API_BASE` 时返回 `""`（`protocolApiConfig.ts:6-11`）。开发代理（`vite.config.ts:35-49`）只作用于 Vite server/preview，不作用于桌面 uvicorn。
- 桌面不复用固定 8902：`run_v2_desktop.py:36-54` 使用 OS 分配端口并把已绑定 socket 交给 uvicorn。

**原件与报告读取**

- 报告页：`ReportsPage.tsx:103-156` GET `/api/v2/protocol/projects`、`/api/v2/projects/{id}/subjects`、`/api/v2/subjects/{id}/review-episodes`、review-runs。这些 GET 都在 browse 复制集合内。
- 查看原件：`FrozenReviewEvidence.tsx:22-28` GET 冻结 `completeProcessingRevisionId` + `evidenceSnapshotV2Id`；`OriginalEvidenceViewer` 用 `evidencePageImageUrl` → `GET /api/v2/evidence-processing-revisions/{id}/pages/{entry}/image`（`evidenceHttp.ts:83-89`，`evidence_processing.py:450-471`）。`page_image` 只 `artifact_store.read_by_sha`（`evidence_api_read_service.py:625-653`）。
- 打印时隐藏运行状态条：`reports.css:316-323` 对 `.application-mode-notice` 等 `display: none`。

**仅查看合同被前端打穿（最高影响已证缺陷）**

1. `ApplicationModeNotice.tsx:4-22` 只把 `browse_only && can_modify===false` 画成横幅；失败/非 JSON 时保持 `browseOnly=false` 且 `catch` 吞掉。全库前端只有这一处读 `application-status`。
2. `FrozenReviewReport.tsx:104-108` 在已完成报告上仍提供「登记办结依据 / 重新办理」，打开 `ReviewActionResponseDialog`，其 `reviewActionHttp.ts:17-21` 对 `/actions/.../responses` 发 **POST**。browse 中间件会拦，但 UI 仍邀请写入。
3. 正式模式默认路径是 `/protocols`（`router.tsx:19-24`，`routes.tsx:87-93`）。仅查看启动器写 `#/reports`，但空 hash / 刷新到 `/` 会落到方案工作台。`SideNav` 仍列出方案工作台、入排工作台、任务与系统、受试者资料；这些页面会打未注册的 GET/POST。
4. 写拒绝用 **503**（`browse.py:47`）。503 是「稍后重试」语义，与「本次打开不会修改」的永久策略不一致。

**生命周期（仅查看）**

- 打开失败：`open_read_only` 内部 dispose。
- 打开成功、服务构造失败或关闭：`browse.py` `finally: engine.dispose()`。
- 未发现仅查看路径调用 `wal_checkpoint` / `ensure_directories` / `upgrade_or_fail`。
- 标准模式关闭：`JobRunner.request_stop()` 后 `thread.join(timeout=5.0)`（`app.py:351-354`），未检查线程是否仍存活再 `engine.dispose()`。这是标准写服务关闭竞态，不是仅查看。

---

### 推断

- 仅查看**不会**走迁移、任务恢复、后台 runner、OCR 门禁 acquire。在「进程是否主动开始新审核 / 调模型」这一点上，源码设计是成立的。
- 仅查看**会**加载写服务与模型栈的 Python 模块，并在导入 `app.config` 时发现 oMLX 地址。这不等于推理，但「仅查看进程零模型依赖」的说法过强。
- 报告/原件的**协议面**是接通的：目录 GET + 冻结 review-history + 冻结页图。磁盘上页图是否存在、WAL 只读打开在脏 WAL 下是否成功，源码无法证明。
- 前端仍是完整工作台。用户从仅查看横幅旁边走进方案/入排/办结对话框，是可预期的操作路径，不是极端边界。
- 复制 `APIRoute` 进无 prefix 的新 `APIRouter` 目前能工作，是因为 FastAPI 把 prefix 烤进 `route.path`。这是脆弱约定，不是当前路径丢失。

---

### 建议（最小、连贯的修补；不改本轮文件）

按影响排序，一组补丁即可，不要另起架构：

1. **把 `application-status` 提升为壳层状态，而不是横幅私有 state。**  
   `AppShell` 在 `browse_only` 时：空 hash 与写页面重定向到 `/reports`；`SideNav` 只保留报告（及只读的受试者/资料查阅，若产品允许）；`FrozenReviewReport` 去掉办结/重开按钮。横幅保留。
2. **写拒绝从 503 改为 403（或 409）+ 现有 `BROWSE_ONLY` 信封。** 不要用可重试状态码表达永久只读。
3. **`create_desktop_app(browse_only=True)` 直接 `import create_browse_app`，不要先导入 `app.api.v2.app`。** 仅查看进程不再因 import 拉进 JobRunner/Omlx/预检。`ProtocolWorkbenchService` 若仍只为 `GET /protocol/projects` 存在，可改为只读 list（或给 `feedback_reviser` 显式禁用实现），避免默认绑模型修订函数。
4. **生命周期：仅查看现状可保持。** 标准模式若要顺手收口，`join` 超时后若线程仍活着应记日志并避免立刻 dispose；这不是仅查看阻断项。

不要做：为仅查看再写一套报告 API、改 schema 校验函数名、用试用 `frontend/dist` 回退。

---

### 不确定性（未跑运行时，不得当缺陷关闭）

- 未启动 uvicorn，未打开 SQLite，未验证 `mode=ro` 在未 checkpoint 的 WAL 上能否读。
- 未构建 `frontend/dist`，未核对 `generateBundle order:post` 是否始终把 `index.html` 列入 `product-build.json`。
- 未验证 `python -m scripts.run_v2_desktop` 在无 `scripts/__init__.py` 的 namespace package 下于当前 `.venv` 的导入（历史 `__pycache__/run_v2_desktop.cpython-312.pyc` 只说明曾经按该模块名编译过）。
- 页图文件缺失时的 UI 文案路径有源码，真实缺文件表现未看。
- 标准模式预检默认开启是否属于本任务「桌面启动链」必须项，需 Codex 定夺。
- 为核对 FastAPI `include_router` 是否丢 prefix，曾用一条本机 `python3 -c "import fastapi"` 定位安装路径，随后改为读该安装源码。未启动本应用、未连库、未调模型。

---

### 对 Codex 的异议、决策点、有界问题

**异议**

- 任务上下文把「仅查看不跑迁移/恢复/模型」写成已完成事实。源码支持「不跑 runner / 不 acquire 门禁」，但不支持「前端不能发起写」和「仅查看进程不加载模型栈」。
- 「中间件拦 POST 就够了」不成立：报告页办结对话框和默认 `/protocols` 是用户会走到的主路径。
- 生命周期异常释放在仅查看上**不是**当前最高缺陷；把审阅重心放在 dispose 会漏掉合同缺口。

**决策点（请 Codex 拍板后再改代码）**

| 决策 | 建议默认 | 为什么要拍板 |
|---|---|---|
| 仅查看 UI 是「全工作台 + 写失败」还是「只读壳」 | 只读壳 | 影响 SideNav、报告办结按钮、空 hash 默认页 |
| 仅查看 GET 是否允许当前活动处理修订/OCR 页，还是仅冻结报告+冻结页图 | 允许已有资料 GET，但导航不指向上传/入排/任务 | 现在 browse 已挂了 live 读接口 |
| 仅查看是否必须不 import `app.api.v2.app` | 应该 | 否则「不触发模型」只能说到 runner 层 |
| 写拒绝状态码 | 403 | 503 会误导重试 |

**有界问题（缺答则按括号内暂定路径）**

1. 仅查看是否必须从 DOM 去掉「登记办结依据」等写入口，还是 403/503 即可？（暂定：必须去掉，否则与横幅文案直接冲突。）
2. 空 hash 在仅查看下应落 `/reports` 还是允许 `/protocols`？（暂定：`/reports`。）
3. 受试者目录/原件查看是否保留在仅查看导航中？（暂定：可保留只读查阅，但证据工作台上传按钮必须按 `can_modify` 隐藏。）

本角色不宣称 Codex 终审、不宣称浏览器/视觉/临床验收。源文件按任务要求未改。
