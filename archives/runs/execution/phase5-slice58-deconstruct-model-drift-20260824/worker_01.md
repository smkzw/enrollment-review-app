# Execution Output: phase5-slice58-deconstruct-model-drift-20260824 - worker_01

## Boundary And Context Check

已读取声明的 execution context 与 plan，并按 `worker_01` 只读边界审计。未修改源代码、测试、生产路径或生成文件；未读取 peer worker 报告。

## Work Performed

- `app/config.py:49-52` 定义旧审核模型：

  `REVIEW_MODEL` 默认值为 `Qwen3.6-27B-oQ8-mtp`。

- `app/config.py:70-75` 存在系统性继承：

  `DECONSTRUCT_MODEL = os.getenv("DECONSTRUCT_MODEL", REVIEW_MODEL)`

  因此未显式设置 `DECONSTRUCT_MODEL` 时，方案解构自动使用旧审核模型。`DECONSTRUCT_BACKEND` 与 `DECONSTRUCT_REASONING_EFFORT` 也分别继承 review 配置。

- 当前 runner 中 `.env` 不存在，相关环境变量均未设置；按源码默认值，当前进程会得到：

  - `REVIEW_MODEL = Qwen3.6-27B-oQ8-mtp`
  - `DECONSTRUCT_MODEL = Qwen3.6-27B-oQ8-mtp`
  - `DECONSTRUCT_BACKEND = omlx`

- 历史真实 oMLX 记录显示，2026-08-22 `http://127.0.0.1:8001/v1/models` 返回 200，目录包含 `Qwen3.8-27B-oQ8e-fp16-mtp`，模型计数为 15。该模型也是当前 `EVIDENCE_NORMALIZER_MODEL` 的默认值。此证据支持它作为专属方案解构模型候选，但不是本次“当前目录”的重新确认。

- V2 方案解构实际路径为：

  `app/api/v2/app.py` → `create_protocol_deconstruction_executor()` → `_resolve_transport()` → `DeepSeekProtocolAgentTransport()`。

  `app/services/protocol_deconstruction_executor.py:432-445` 只检查 `DEEPSEEK_API_KEY`，并未根据 `DECONSTRUCT_BACKEND` 选择 oMLX。

- `DeepSeekProtocolAgentTransport` 使用 `DECONSTRUCT_MODEL`，但 endpoint 是 `DEEPSEEK_BASE_URL`；因此存在独立的 provider 路由风险：配置默认说是 oMLX，V2 transport 实际走 DeepSeek。

- V2 启动时仅注册 Evidence Normalizer 的持久化 `PromptVersion/ModelConfig`；方案解构没有类似注册或模型配置冻结。生成步骤只在内存中构造 `PromptVersion`，没有查找或写入协议专属 `ModelConfig`。

## Artifacts And Evidence

关键证据：

- `app/config.py:49-52,70-90`
- `app/agents/deepseek_protocol_transport.py:10-48`
- `app/services/protocol_deconstruction_executor.py:432-445,541-587`
- `app/api/v2/app.py:119-132,210-216`
- `app/llm/client.py:132-143,317-347,377-396,487-509`
- `app/router/projects.py:1069-1077`
- `app/agents/deepseek_evidence_normalizer_transport.py:41-48,142-181`
- 历史 oMLX 记录：`runs/test/phase4-d001-real-uat-20260822/r8/connectivity/localqwen.stdout.txt:198-212`
- 隔离数据库：`artifacts/phase5-acceptance/20260823/data/enrollment-review-v2.sqlite3`

隔离数据库观察：

- `model_configs` 仅有 Evidence Normalizer 的 `Qwen3.8-27B-oQ8e-fp16-mtp` 配置。
- `agent_calls` 无记录。
- `protocol_deconstruction` 任务在 `generate_draft` 因 `SEMANTIC_PROVIDER_UNAVAILABLE` 失败，说明当次运行在 provider 配置门禁处终止，尚未形成协议模型调用证据。

## Commands And Observations

- 使用 `rg` 审计 `REVIEW_MODEL`、`DECONSTRUCT_MODEL`、transport 和注册路径，确认上述引用关系。
- 使用 `sqlite3` 查询 `model_configs`、`agent_calls`、`jobs`、`job_events`，未修改数据库。
- 使用：

  `curl --noproxy '*' http://127.0.0.1:8001/v1/models`

  本次返回 connection refused/status 000。
- `lsof` 曾显示 8001 有 `python3.1` listener，但 runner 内无法建立连接；`ps` 查询受 sandbox `operation not permitted` 限制。
- 未运行测试；本 worker 为只读审计，聚焦回归由其他工作项负责。

## Blockers Or Missing Environment

1. 本次无法重新确认当前 oMLX `/v1/models` 目录，因此 `Qwen3.8-27B-oQ8e-fp16-mtp` 只能作为历史实时证据支持的候选，不能作为本轮当前运行证明。
2. V2 方案解构的 DeepSeek transport 与 `DECONSTRUCT_BACKEND=omlx` 存在路由不一致。若目标确实是本机 oMLX，单独修改默认模型名不能修复该 provider 路由问题。
3. 隔离运行环境未设置 `DEEPSEEK_API_KEY`；这解释了历史隔离任务的 provider unavailable，但不等同于模型 ID 已验证失败。

## Rerun Requests Or Next Step

- 在 oMLX 可达的同一运行环境重新执行 `/v1/models`，确认确切模型 ID 与 HTTP 200。
- `worker_02` 可将 `DECONSTRUCT_MODEL` 默认值改为已确认的专属模型，同时保留 `DECONSTRUCT_MODEL` 显式环境覆盖。
- `worker_03` 应覆盖：默认值、环境覆盖、transport 实际收到的 model，以及 legacy/V2 路径。
- 请 Codex 明确：V2 是否有意继续走 DeepSeek；若目标是 oMLX，需要另行授权修复 `_resolve_transport`/transport provider 选择。
