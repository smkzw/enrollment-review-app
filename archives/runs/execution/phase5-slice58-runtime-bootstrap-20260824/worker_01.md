# Execution Output: phase5-slice58-runtime-bootstrap-20260824 - worker_01

## Boundary And Context Check

- Working directory: `.`
- Read initial context and plan files.
- Read-only audit boundary followed; no source, test, production, or runner-report files were modified.
- No conference, internet access, package installation, or production database access performed.

## Work Performed

- Traced `PromptVersion`, `ModelConfig`, repository persistence, application lifespan, command service, job service, and executor configuration reload.
- Inspected fixture-only registration paths and existing protocol-deconstructor behavior.
- Ran focused tests with the project `.venv`.
- Ran isolated fresh-database and wrong-agent-selection runtime probes.

核心结论：

1. 全新数据库迁移后不会自动登记 Evidence Normalizer 配置。
2. 应用 lifespan 能启动，但首次创建规范化任务时因配置缺失失败。
3. 当前模型选择存在误选其他 Agent 配置的路径：无显式 normalizer 标记时，会回退选择任意结构上可用的模型。
4. `ModelConfig` 当前没有正式的 Agent 归属字段，`parameters["agent_node"]` 只是非强制约定。

## Artifacts And Evidence

- `app/api/v2/app.py:118-228`
  - lifespan 只执行 `upgrade_or_fail`、恢复任务、构造服务和执行器。
  - 没有 PromptVersion/ModelConfig 注册或启动校验步骤。

- `app/storage/migrate.py:513-531`
  - `upgrade_or_fail` 只负责 SQLite 运行时检查、迁移、schema/PRAGMA 验证和返回 session factory。
  - 不写入任何 Agent 配置。

- `app/storage/models.py:1091-1106`
  - `PromptVersionRecord` 规范化列：ID、node、template hash、schema version。
  - `ModelConfigRecord` 规范化列：ID、provider、model、reasoning_effort。
  - 模型参数全部留在 canonical payload 中，没有 Agent 归属列。

- `app/domain/contracts/agents.py:20-33`
  - `PromptVersion` 有正式 `node` 字段。
  - `ModelConfigContract` 没有 `agent_node` 或用途字段，仅有自由结构 `parameters`。

- `app/storage/repositories.py:251-352, 1132-1162`
  - 追加仓储通过 payload/hash 保存不可变记录。
  - ModelConfig 的 `parameters` 不在镜像列中，只随 payload 保存和哈希校验。
  - 现有共享模式可支持追加新身份，但不能通过结构化列直接按 Agent 过滤模型。

- `app/storage/repositories.py:3239-3268`
  - PromptVersion/ModelConfig 的现有批量登记只发生在 `persist_fixture()`。
  - 这是 fixture 播种路径，不是生产应用启动路径。

- `tests/v2/services/test_fact_normalization_persistence.py:425-443`
  - 规范化测试通过 `_seed_chain()` 手工插入 PromptVersion/ModelConfig。
  - 现有测试数据库因此掩盖了全新数据库缺配置问题。

- `app/services/fact_normalization_command_service.py:103-161`
  - PromptVersion 按 `EVIDENCE_NORMALIZER`、合同版本和模板 hash 筛选。
  - ModelConfig 先筛选结构可用项；只有存在 `parameters["agent_node"] == "evidence_normalizer"` 时才优先使用显式标记项。
  - 若没有显式标记项，则回退到所有结构可用模型：

    `usable_models = marked if marked else structural`

  - 因此其他 Agent 的唯一可用模型可能被选中。

- `app/services/fact_normalization_job_service.py:166-208`
  - 创建任务时同样只校验 PromptVersion 类型、模板 hash，以及模型的 `max_tokens`/`temperature`。
  - 未校验模型 Agent 归属、provider 是否支持或模型合同身份。

- `app/services/fact_normalization_executor.py:255-323, 634-729`
  - 执行时按运行中冻结的 ID 重新读取配置。
  - PromptVersion 会再次校验 node、合同版本和模板 hash。
  - ModelConfig 仅被读取并传给 transport factory，没有再次校验 Agent 归属。

- `app/services/protocol_deconstruction_executor.py:561-572`
  - Protocol Deconstructor 在执行时内存构造 PromptVersion。
  - 未发现其向共享 PromptVersion/ModelConfig 表登记生产配置的机制。

- `app/agents/deepseek_evidence_normalizer_transport.py:142-181`
  - 真正传输层只支持 `deepseek/deepseek-api` 和 `omlx/local-omlx`。
  - 当前命令选择器允许任意 provider 只要结构参数合格，错误 provider 会延迟到执行阶段失败。

## Commands And Observations

- `uv run pytest -q ...`
  - 失败：`/Users/smkzw/.cache/uv` 无权限。
  - 未安装或修改任何依赖。

- 系统 `pytest`
  - 使用 `/usr/bin/python3` 3.9.6，失败：缺少 `sqlalchemy`。
  - 不符合项目 `requires-python >=3.12,<3.13`。

- `.venv/bin/pytest -q tests/v2/api/test_fact_normalization_registration.py tests/v2/services/test_fact_normalization_command_service.py`
  - 结果：`11 passed`。

- `.venv/bin/pytest -q tests/v2/api/test_fact_normalization.py tests/v2/agents/test_evidence_normalizer_transport_config.py`
  - 结果：`11 passed`。

- 隔离 fresh-db runtime probe，使用临时 `ENROLLMENT_V2_DATA_DIR` 和 `TestClient`：
  - `fresh_db_prompt_rows=0`
  - `fresh_db_model_rows=0`
  - `fresh_db_select=AppFactNormalizationConfigError`
  - 应用 lifespan 本身成功启动，但配置选择失败。

- 隔离 wrong-agent-selection runtime probe：
  - 插入一个合法 Evidence Normalizer PromptVersion。
  - 插入一个无 `agent_node` 标记的 `protocol-model-v1` ModelConfig。
  - 选择结果：

    `unmarked_other_agent_selection_prompt=normalizer-prompt-v1`

    `unmarked_other_agent_selection_model=protocol-model-v1`

  - 证明当前 fallback 会实际选择其他 Agent 模型配置。

## Blockers Or Missing Environment

- 本审计无剩余环境阻塞；项目 `.venv` 可正常执行测试和运行时探针。
- 未执行真实 DeepSeek/oMLX 网络模型调用；本任务只审计注册、选择和启动路径。
- 未进行最终临床、浏览器、视觉或生产验收。

## Rerun Requests Or Next Step

建议 worker_02 按以下边界实现：

1. 在应用启动路径登记或核验 Evidence Normalizer 专属 PromptVersion/ModelConfig。
2. 配置必须追加写、身份不可变；合同或模型参数变化生成新身份，禁止覆盖旧记录。
3. 选择器必须要求明确的 Evidence Normalizer 归属，删除 `marked else structural` fallback。
4. 启动或命令创建阶段应 fail-closed 校验 provider、model、推理参数及 normalizer 合同。
5. 保留其他 Agent 的共享配置，不修改临床规则和既有历史运行。

worker_03 应补充 fresh-db、配置变更追加、不可变身份、错误 Agent 配置拒绝、错误 provider 拒绝及命令路径回归。

需要 Codex 决策的一点：是否沿用现有 `ModelConfigContract.parameters["agent_node"]` 作为最小兼容归属标记，还是升级为正式的一等字段；当前代码和数据库 schema 尚无正式 Agent 归属字段。
