路由已切换：本会话现由 `codebuddy-cli/deepseek-v4-flash` 继续同一受限 worker 任务（同平台声明回退）。保留全部上下文、文件与边界。已确认的能力限制：无——工具集与边界不变，未完成工作继续。

**当前未完成点**：端到端冒烟测试中 deep_0001 以 `PROTOCOL_CONTROL_DEEP_NEEDS_REVIEW` 失败——fake 深析传输的原子摘录未通过逐字原文校验（FABRICATED_EXCERPT）。正在定位 `source_texts` 的构建来源以修正 fake。

关键发现：校验的 `source_texts` 就是 `unit.excerpt` 本身（`_candidate_source_texts`），所以 fake 用 `unit["excerpt"]` 应当通过逐字校验。真实失败原因需要深析 wire 校验的具体 issue 文本。写探针直接复跑 deep runner 捕获 issues。

写探针：从失败运行 DB 的 closure 检查点重建深析批次，直接用 fake 跑 AgentRunner，打印 attempt issues。

确认根因：深析 wire 合同要求 `review_node_bindings` ≥1，而生产 `ProtocolControlJobService` 未传 workflow_stages。检查执行服务内部是否自行派生审核节点（生产 API 也这么调用）。

根因确认：`_validate_workflow_stage_bindings` 要求候选的 `review_node_bindings` 必须引用冻结的 `known_workflow_stage_targets`，且空目录时任何绑定都非法（`WORKFLOW_TARGET_CATALOG_MISSING`），而 wire schema 又强制 ≥1 绑定。**生产 API 布线（`app/api/v2/app.py:252`）未传 workflow_stages**——这是给 Codex 的真实发现。已验收的确定性链测试则从冻结来源的必做项目录派生 stages。运行器镜像该已验收行为：从真实冻结快照的 `required_procedure_catalog` 派生 stages，并更新 fake 深析传输绑定 prompt 中的真实 stage 目标。

更新测试中的 fake 深析传输：从 prompt 的 `known_workflow_stage_targets` 绑定真实节点。

流程节点的 (审核阶段, 访视实例) 身份必须唯一。查看冻结必做项目录的实际条目，再调整流程表。

流程表每列需恰好一个标记，否则同 (阶段, 访视) 身份重复。调整为每列一个 X。

深析已通过（2 批次、4 候选）。门禁阶段报 `PHASE_APPLICABILITY_UNRESOLVED`。查看门禁校验。

门禁需要"期别语义结果视图"（resolved_view）。查找该视图的生产构造位置。

门禁在 `_execute_gate` 中调用 `validate_protocol_control_publication` 且未传 resolved_view。查找该校验内部的期别适用性路径。

门禁的确定性期别检查要求每个结构单元恰好单一期别范围（UNKNOWN/MIXED 即失败）。检查覆盖清单中各单元的期别范围，确定哪些章节缺期别线索。

22 个单元是 UNKNOWN 期别范围。给每个章节加显式"II期"线索，使期别图对全部单元产生单一范围。

章节范围只随标题线索变化。查看期别检测的章节映射逻辑。

标题带期别线索才建立章节上下文。为其余四个章节标题加 "II期" 前缀。

替换断言失败（格式不匹配）。查看实际标题行格式。

剩余 7 个未知单元：文档标题与 IN/EX 两节（含规则）。检查 section_index 的 IN/EX 标题匹配规则，确认带期别前缀的标题仍能配对。

"可选期别前缀"允许 `II期入选标准` 这类标题配对。改标题文本与 IN/EX 标题，并验证。

端到端冒烟运行成功：控制任务 completed、水合候选包、正式目录未物化、4 候选、claims_complete=false。运行完整聚焦测试文件。

运行器指标缺口：深析节缺少聚合 totals。修正。

5 个聚焦测试全部通过。现在做收尾验证：diff 检查、编译，然后尝试一次真实模型冒烟运行（预期身份失效关闭：配置 Quality vs 服务加载 Speed）。

仅我新增的两个文件为未跟踪状态，其余为工作树既有修改。现在探测模型服务并尝试真实冒烟。

服务在运行，加载的是 Speed 变体。检查 `/v1/models` 报告的身份，然后执行真实冒烟。

服务身份与配置模型不一致（Speed vs Quality）——预期失效关闭。运行真实冒烟验证门禁。

CLI 退出码 2 验证通过。小改进：来源链指标中的 `protocol_code`/`selected_phase` 应从确认检查点读取（当前为 null）。

全部验证通过。清理探针临时文件，然后输出最终报告。

# Execution Output: phase5-protocol-control-live-model-smoke-20260831 - worker_02

## Boundary And Context Check

- **Provider/route**: 本会话为同平台声明回退，执行角色 `worker_02` 现由 `codebuddy-cli` / `deepseek-v4-flash` 继续；原 `glm-5.3-flash` 身份被回退覆盖。工具集与边界不变，未丢失任何上下文、文件或工具结果。未做任何无法执行的声明：全部验证均为本会话实际运行获得。
- **读取范围**：初始读取集（`context/phase5-protocol-control-live-model-smoke-20260831_execution_context.md`、`plans/codex_execution_phase5-protocol-control-live-model-smoke-20260831.md`）+ 生产链只读模块（`protocol_control_agent_transport.py`、`protocol_control_discovery_transport.py`、`protocol_control_execution.py`、`protocol_deconstruction_executor.py`、`protocol_workbench_service.py`、`deconstruction_service.py`、`procedure_catalog.py`、`section_index.py`、`phase_detection.py`、`metadata.py`、`protocol_control_gate.py`、`full_protocol_coverage.py`、`protocol_control_planning.py`、`workflow/runner.py`、`jobstore.py`、`config.py`、`.env.example`、`tests/v2/services/test_protocol_control_execution.py`、`tests/v2/conftest.py`）。未读取 `.env` 密钥，未读取 D001/SAR 等真实临床材料。
- **写入范围**：仅授权产物——`scripts/run_protocol_control_smoke.py`（新增）、`tests/v2/services/test_protocol_control_smoke_runner.py`（新增）。未修改任何生产模块。`git status` 中其余修改均为工作树既有状态。
- **报告文件**：按边界未写 `runs/execution/.../worker_02.md`，由 runner 持久化本回复。

## Work Performed

实现并验证了 `worker_02` 的工作项（最小、可复现、词汇中立的真实生产 harness 冒烟运行器与持久化指标）。

### 产物 1：`scripts/run_protocol_control_smoke.py`（新增，约 700 行）

冒烟运行器，流程与边界：

1. **先验模型身份**：构建生产环境发现/深析传输，`verify_model_identity(force=True)` 正向核验 `/v1/models` 实际加载模型；缺失/歧义/不一致即失效关闭（中文诊断），不建立任何任务。默认已核对"配置 Quality vs 服务加载 Speed 变体"即拒绝运行。
2. **词汇中立合成协议**：内置固定常量语句生成 DOCX（标题、方案信息、II期设计、官方 Word 编号列表的入选/排除标准、单标记流程表、管理要求、背景说明），任何外部输入无法进入文档；`--fixture` 外部文件被 `projects/` 与真实数据目录守卫拒绝。
3. **真实生产来源链**：`ProtocolWorkbenchService.start_first_deconstruction` → 生产 `JobRunner` + `create_protocol_deconstruction_executor` 驱动 登记→提取→渲染对齐（LibreOffice）→识别→用户确认边界（`confirm_identity` 从识别结果推导输入）→冻结结构快照。冻结后经显式非重试边界 `SMOKE_SOURCE_STOP_AFTER_FREEZE` 停止，不驱动官方 IN/EX 语义解构（generate_draft）。
4. **生产控制链**：从冻结快照的必做项目录派生通用 workflow stages（镜像已验收确定性链做法，见下方发现 A），经 `ProtocolControlJobService.create_from_deconstruction` + `create_protocol_control_executor` + 真实 `JobRunner` 驱动发现/深析/水合/门禁。
5. **持久化指标**：`run_record.json` 含模型身份（配置/已核验/服务清单）、发现分布（candidate/context_only/non_control/uncertain）、深析范围（批次/owned 单元/候选数）、schema 修复数与传输重试数、延迟（阶段/总计）、结果类型、正式目录状态、失败类别、边界声明；`claims_complete=false` 显式恒为 false。

### 产物 2：`tests/v2/services/test_protocol_control_smoke_runner.py`（新增，5 个测试全通过）

- `test_identity_mismatch_fails_closed_before_any_run`：Speed/Quality 身份不一致 → 退出码 2、`data_v2` 目录未创建（无任何任务建立）、运行记录可独立重载、`claims_complete=false`。
- `test_guard_rejects_real_project_and_data_dir_fixtures`：`projects/` 与真实数据目录内文件被拒，受控临时目录合成文件放行。
- `test_synthetic_fixture_is_self_contained`：文档每段文本逐字来自声明常量集合（结构性词汇中立）。
- `test_full_smoke_run_with_verified_fake_transports`：真实生产链 + 确定性假传输全链路完成：来源冻结快照、控制任务 completed、`result_kind=hydrated_candidate_control_package`、`formal_catalog_status=not_materialized`、发现分布/深析批次/修复计数与延迟齐备。
- `test_smoke_source_job_never_reaches_official_deconstruction`：来源任务冻结后停止，`stop_error_code=SMOKE_SOURCE_STOP_AFTER_FREEZE`，控制任务消费同一冻结快照。

### 真实模型冒烟（已执行）

服务 `127.0.0.1:8002` 在线，`/health` 与 `/v1/models` 均报告 `pocketaihub-qwen3.8-27b-abliterated-mtplx-optimized-speed`；配置 `PROTOCOL_CONTROL_MODEL=mtplx-qwen38-27b-optimized-quality`。运行器按边界**先验身份、失效关闭**：退出码 2，仅落盘 `run_record.json`（无数据目录、无任务、无任何语义请求），记录 `reason=mismatch`、`served_model_ids=[...speed]` 与中文诊断。这同时是"Speed 变体加载时拒绝运行"门禁的真实证据；**未在身份不匹配下运行任何语义调用**。

### 确定性端到端证据（假传输，真实生产链）

`EXIT=0`；来源链 `block_count=46`、`content_sha256` 记录、`protocol_code=SYN-SMOKE-001`、`selected_phase=phase_ii`、`workflow_stage_count=2`、冻结后显式停止；控制任务 `completed`、`candidate_ids_count=4`、发现分布 `{candidate:2, context_only:15, non_control:14, uncertain:2}`、深析 2 批次/4 候选、修复 0、总延迟 2.02s。

## Artifacts And Evidence

| 文件 | 状态 | 说明 |
|---|---|---|
| `scripts/run_protocol_control_smoke.py` | 新增 | 冒烟运行器（CLI + 可导入函数，测试经 importlib 加载） |
| `tests/v2/services/test_protocol_control_smoke_runner.py` | 新增 | 5 个聚焦测试，`5 passed` |

验证命令：`uv run pytest tests/v2/services/test_protocol_control_smoke_runner.py`（5 passed）；`uv run python -m py_compile`（通过）；`git diff --check`（通过，无空白错误）；真实冒烟 `scripts/run_protocol_control_smoke.py --out-dir /tmp/smoke-live`（exit=2，身份失效关闭）；探测脚本与 `/tmp/smoke-*` 临时产物已清理。

## Commands And Observations

- 生产链适配过程（探针迭代，最终全部固化进运行器）：合成 DOCX 需 Word 官方编号列表（"List Number"）承载入选/排除父规则；需结构完整流程表（≥2 表头/标记列、行标签、含基线列）且**每期别列恰好一个标记**（否则 `(review_stage, visit_instance)` 身份重复）；每个章节标题需带期别线索（`II期…`），文档标题也需含 `II期`，否则覆盖清单单元为 UNKNOWN/MIXED 触发门禁 `PHASE_APPLICABILITY_UNRESOLVED`。
- 深析 wire 合同实测：`review_node_bindings` 至少 1 项，且 `_validate_workflow_stage_bindings` 要求绑定必须引用冻结的 `known_workflow_stage_targets`（空目录时任何绑定非法）。
- 真实服务探测：`curl /health`、`curl /v1/models` 均报告 Speed 变体（详细 JSON 已观察，未泄露任何密钥）。

## Blockers Or Missing Environment

无环境阻塞。LibreOffice（`/opt/homebrew/bin/soffice`）与本地模型服务均可用。唯一预期阻塞：当前服务加载 Speed 变体而配置为 Quality，真实语义冒烟按边界失效关闭——这是设计行为，非缺陷。

## Rerun Requests Or Next Step

给 Codex 的两个发现与建议：

- **发现 A（生产布线）**：`app/api/v2/app.py:252` 构造 `ProtocolControlJobService` 时未传 `workflow_stages`（默认空）。门禁实测：深析 wire 要求 `review_node_bindings ≥ 1` 且绑定必须存在于冻结 `known_workflow_stage_targets`；空目录时深析必然失败（`WORKFLOW_TARGET_CATALOG_MISSING` 或 schema 非法）。本运行器从冻结来源快照的 `required_procedure_catalog` 派生 stages（与已验收确定性链 `tests/v2/services/test_protocol_control_execution.py` 完全一致），使合成协议可跑通。建议 Codex 复核生产 API 是否应同样从冻结来源派生 workflow_stages。
- **建议下一步**：请 Codex 决定真实语义冒烟的时间窗口（需将本地模型服务切换到配置的 Quality 变体 `mtplx-qwen38-27b-optimized-quality` 后再运行 `python scripts/run_protocol_control_smoke.py --out-dir <目录>`；运行器已具备完整门禁，切换后即可复现真实发现/深析与持久化指标）。后续 worker_03 反过拟合审查可基于本运行器做只读检查。

未声明最终验收：正式目录物化、真实协议回放门禁、渲染/临床/监管验收均属 Codex 职权范围。
