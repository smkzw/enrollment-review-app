# Execution Output: phase5-normalizer-throughput-20260903 - worker_02

## Boundary And Context Check

- Runner cwd: `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`（git 分支 `codex/phase5-clinical-facts-profile`）。所有读写均在该目录内。
- 初始读取集合：`context/phase5-normalizer-throughput-20260903_execution_context.md`、`plans/codex_execution_phase5-normalizer-throughput-20260903.md`。未读取 home AGENTS.md / SOUL.md；workspace `AGENTS.md` 出现在初始上下文中。
- 分配项：Work Item 2 —— Evidence Normalizer 对 `zhipu-coding-plan`/GLM-5.3-Flash 的供应方中性接入与凭据预检复用，保持 MTPLX/DeepSeek/oMLX 兼容，增加聚焦测试。未实施 Work Item 1（只读审计）与 Work Item 3（输入瘦身），未提前实现 Phase 5.5，未硬编码任何项目临床内容。
- 附加证据读取（记录如下）：`app/agents/evidence_normalizer.py`、`app/agents/deepseek_evidence_normalizer_transport.py`、`app/agents/protocol_semantic_transport.py`（已批准 GLM 路由的参照实现）、`app/agents/protocol_semantic_route_preflight.py`、`app/agents/protocol_semantic_model_router.py`、`app/config.py`、`app/services/fact_normalization_executor.py`、`app/services/fact_normalization_command_service.py`、`app/services/fact_normalization_job_service.py`、`app/domain/contracts/agents.py`、`tests/v2/agents/test_evidence_normalizer_transport_config.py`、`tests/v2/agents/test_mtplx_semantic_route_regressions.py`、`.env.example`。
- 重要发现（证据）：`tests/v2/agents/test_mtplx_semantic_route_regressions.py::test_default_semantic_route_is_mtplx_and_ocr_stays_omlx` 断言默认 `EVIDENCE_NORMALIZER_PROVIDER == "mtplx"`。因此本实现**未改动默认路由**，只新增可选 GLM 路由（见 Next Step 的决策点）。
- git 状态说明（观察）：`app/agents/evidence_normalizer.py`、`app/agents/deepseek_evidence_normalizer_transport.py`、`tests/v2/agents/test_evidence_normalizer_transport_config.py` 在本 worktree 为未跟踪文件（上一 slice 的未提交状态），我的编辑落在其上；未执行任何 git 写操作。

## Work Performed

1. **`app/config.py`** —— 新增 Evidence Normalizer 专属 GLM 连接配置（位于现有 `EVIDENCE_NORMALIZER_*` 块之后）：
   - `EVIDENCE_NORMALIZER_GLM_BASE_URL`（默认 `https://open.bigmodel.cn/api/coding/paas/v4`）
   - `EVIDENCE_NORMALIZER_GLM_API_KEY = env 或 DECONSTRUCT_GLM_API_KEY`（后者自身回退 `INDEPENDENT_VLM_API_KEY`）—— 即凭据预检复用链：单机单用户无需重复粘贴同一 BigModel 密钥
   - `EVIDENCE_NORMALIZER_GLM_MODEL`（默认 `glm-5.3-flash`）、`EVIDENCE_NORMALIZER_GLM_REASONING_EFFORT`（默认 `high`）
   - 默认 `EVIDENCE_NORMALIZER_PROVIDER` 保持 `mtplx` 不变（受上述钉死的回归约束，且避免在无 GLM 凭据的现网启动后作业期失败）。

2. **`app/agents/evidence_normalizer.py`** —— `SUPPORTED_EVIDENCE_NORMALIZER_PROVIDERS` 增加 `zhipu-coding-plan`、`glm`（启动注册 `_runtime_model` 与任务入口校验共用该集合，接入链自动打通）；新增 `ZHIPU_EVIDENCE_NORMALIZER_BACKENDS` 与 `SUPPORTED_GLM_NORMALIZER_REASONING_EFFORTS`（low/high/max）；`validate_evidence_normalizer_model_config` 对 zhipu 系 provider 增加词表校验（medium/xhigh/default 对 GLM 直接 fail-closed），使冻结合同在每个执行边界（注册、任务创建、执行器加载）保持一致。

3. **`app/agents/deepseek_evidence_normalizer_transport.py`** —— 供应方中性接入，完全镜像已批准的 `protocol_semantic_transport.py` GLM 路由约定：
   - 构造器接受 zhipu 系 backend；凭据缺失时在构建任何客户端之前抛出含复用链说明的中文错误（不静默替换供应商）；
   - `_normalize_zhipu_coding_plan_base_url`：保留 `.../paas/v4` 路径、剥离误加的 `/v1`；
   - `_map_glm_normalizer_reasoning_effort`：`""/default/auto` 解析为配置默认（high），仅支持 low/high/max；
   - zhipu 客户端 `httpx.Client(trust_env=False)`（不继承环境 HTTP_PROXY）+ `timeout=600.0` + `max_retries=0`（重试预算归 Runner，避免客户端重试叠加昂贵长请求）；
   - `_completion_kwargs` zhipu 分支：映射后的 `reasoning_effort`、`extra_body.thinking(enabled, clear_thinking=False)`、温度显式优先否则钉 0.1（与方案语义路由一致）；
   - 工厂 `evidence_normalizer_transport_from_model_config` 新增 zhipu 分支：凭据预检 fail-closed、`response_format={"type": "json_object"}`（BigModel Coding Plan 与已批准路由一致；结构仍由本地 Pydantic/来源闭包门禁强校验）。
   - DeepSeek/MTPLX/oMLX 分支的既有行为逐行未动。

4. **`tests/v2/agents/test_evidence_normalizer_transport_config.py`** —— 新增 9 个聚焦测试（详见 Artifacts），并保留原有 5 个兼容测试原文。

5. **`.env.example`** —— 在证据规范化块下注释形式记录 4 个新环境变量与凭据复用关系、GLM 强度词表约束。

## Artifacts And Evidence

修改文件：
- `app/config.py`（+19 行）
- `app/agents/evidence_normalizer.py`（provider 集合 + GLM 词表 + 校验分支）
- `app/agents/deepseek_evidence_normalizer_transport.py`（zhipu 接入）
- `tests/v2/agents/test_evidence_normalizer_transport_config.py`（5 旧 + 9 新测试）
- `.env.example`（文档）

新增测试覆盖点：① provider 集合含 zhipu 路由（注册链入口）；② 工厂冻结身份 + BigModel 端点（无 `/v1` 后缀）+ `max_retries=0`/`timeout=600`/`trust_env=False` + json_object + thinking extra_body + 显式温度；③ 未显式配置温度时钉 0.1；④ 凭据缺失 fail-closed 且错误先于客户端构建（`_FakeOpenAI.calls == []`），错误含复用链提示；⑤ `paas/v4/v1` 归一化；⑥ 强度越界（medium）在工厂即拒绝；⑦ 空强度映射到配置默认；⑧ 合同校验器对 zhipu 接受 low/high/max、拒绝 medium/xhigh/default，且不影响 MTPLX；⑨ 子进程配置探针验证凭据复用链（`INDEPENDENT_VLM_API_KEY` → `DECONSTRUCT_GLM_API_KEY` → `EVIDENCE_NORMALIZER_GLM_API_KEY` 优先级）与默认端点/模型/强度。

测试证据（`.venv/bin/python -m pytest`）：
- `tests/v2/agents/test_evidence_normalizer_transport_config.py`：**14 passed**（0.84s）
- `tests/v2/agents/test_mtplx_semantic_route_regressions.py` + `test_evidence_normalizer_adapter.py`：**50 passed**（2.29s）—— 含 MTPLX 身份/MTP wire/默认路由回归，兼容性证明
- `tests/v2/services/test_fact_normalization_command_service.py` + `tests/v2/api/test_fact_normalization_registration.py` + `tests/v2/services/test_fact_normalization_executor_profile.py`：**27 passed**（13.85s）—— 注册/任务创建/执行器冻结合同链
- `tests/v2/agents/` 全目录：**114 passed**（3.38s）
- `python -m compileall` 对四个改动源文件：OK

## Commands And Observations

- 读取类：`grep`/`Read` 定位 normalizer、GLM 参照路由、预检机制、注册与执行链（文件清单见 Boundary Check）。
- 写入类：对上述 5 个文件的定向编辑（Edit/Write）。
- 验证类：上述 pytest 5 条命令、`compileall`。均通过。
- 观察 1：`protocol_semantic_route_preflight.py` 是方案解构任务专属的启动预检（含 `candidate_availability_error` 与密钥脱敏）。**推断**：Evidence Normalizer 在 config 中被明确声明为独立任务配置（“不得继承方案解构配置后误选其他任务模型”），把 normalizer 接入该协议预检会破坏任务隔离，故“凭据预检复用”落为：同一 BigModel 凭据链复用 + 与 `candidate_availability_error` 同风格的中文 fail-closed 预检错误，而不复用协议路由预检本体。
- 观察 2：zhipu 客户端的 `httpx.Client` 与传输同生命周期（每次 run 经 `transport_factory` 新建），与已批准协议路由的既有模式一致，未引入新的资源管理差异。
- 观察 3：未配置 `ruff`（无此依赖），未安装（遵守禁装边界）；用 `compileall` + 全量相关测试替代语法/导入验证。

## Blockers Or Missing Environment

- 无阻塞。未做真实网络调用（凭据与速率归 Codex/用户管理；只读单页速度质量闸门属本包其他工作项，不在本项范围内）。

## Rerun Requests Or Next Step

- **留给 Codex 的决策点（推断+建议）**：默认 `EVIDENCE_NORMALIZER_PROVIDER` 仍为 `mtplx`。若要让 Phase 5 单页时延修复默认生效，需将默认改为 `zhipu-coding-plan` 并同步改写 `test_mtplx_semantic_route_regressions.py` 中的默认路由钉死断言；这是一次产品路由决策（且要求 GLM 凭据在部署环境可用），超出本项“接入+兼容”的授权，未实施。启用新路由的最小操作（无需代码变更）：环境文件中设 `EVIDENCE_NORMALIZER_PROVIDER=zhipu-coding-plan`、`EVIDENCE_NORMALIZER_REASONING_EFFORT=high`（或 low/max），密钥按复用链留空或显式填写。
- 剩余验证需求（供 Codex 验收）：① 在配置 GLM 凭据的环境做一次真实单页调用冒烟（验证 BigModel 端点接受 `reasoning_effort`/`thinking` extra_body 与 `json_object`）；② Work Item 3 的输入瘦身与本接入叠加后的端到端体积/时延测量；③ 若 Codex 决定翻转默认路由，需同步更新默认路由回归测试。
