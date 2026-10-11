# Execution Output: phase5-slice58-deconstruct-model-drift-20260824 - worker_02

## Boundary And Context Check

已读取更新后的 execution context，确认真实失败机制：oMLX 已到达目标模型，但仅请求 `json_object`，最终产生 `SEMANTIC_DRAFT_MISSING`。本次仅修改授权的方案解构源文件与聚焦测试，保留其他 dirty-worktree 变更；未触碰 frontend、运行时数据、源方案或生产路径。

## Work Performed

- 增加显式 `ProtocolOutputKind` transport contract：
  - `semantic_candidate`
  - `semantic_rule_repair`
- 调用方显式传递输出类型：
  - 初始解构、分批解构、结构修复：candidate schema
  - 定向父规则修订、反馈修订：rule-repair schema
- oMLX 使用对应 Pydantic domain model 的严格 JSON Schema。
- DeepSeek 保持 `{"type": "json_object"}` 行为及既有 thinking 参数。
- runner 无 `final_draft` 时，从最近 attempts 提取去重后的最多 3 条 schema/gate 诊断：
  - 问题最多 700 字符
  - 下一步最多 300 字符
  - 总诊断最多 3000 字符
- 不持久化 raw model output，也不暴露 hidden reasoning。
- 更新了协议 fake transports 与聚焦测试。

## Artifacts And Evidence

主要修改：

- `app/config.py:70-81`
  - 默认 `DECONSTRUCT_MODEL=Qwen3.8-27B-oQ8e-fp16-mtp`
  - 默认 backend 为 `omlx`
  - 保留显式 `DECONSTRUCT_*` 覆盖
- `app/agents/protocol_deconstructor.py:60-77,203-222`
  - 输出类型 contract 与 strict schema builder
- `app/agents/deepseek_protocol_transport.py:47-120,169-203`
  - provider、端点、密钥和 schema 分流
- `app/services/protocol_deconstruction_executor.py:433-481,625-629`
  - backend 选择与有界失败诊断
- `tests/v2/protocols/test_deconstruction_transport_config.py`
  - 默认值、环境覆盖、endpoint/key、精确 candidate/repair schema、DeepSeek 兼容行为、诊断边界
- `tests/v2/protocols/test_protocol_deconstructor_adapter_slice3.py`
  - fake transport 输出类型与调用断言

实时 oMLX 目录仍可见：

`Qwen3.8-27B-oQ8e-fp16-mtp / owned_by=omlx / max_model_len=131072`

## Commands And Observations

聚焦回归：

```text
.venv/bin/pytest -q \
  tests/v2/protocols/test_deconstruction_transport_config.py \
  tests/v2/protocols/test_deepseek_protocol_transport_slice3.py \
  tests/v2/protocols/test_protocol_deconstructor_adapter_slice3.py \
  tests/v2/api/test_protocols_api.py
```

结果：

```text
76 passed, 5 warnings
```

编译与 diff 检查：

```text
.venv/bin/python -m compileall -q \
  app/agents/deepseek_protocol_transport.py \
  app/agents/protocol_deconstructor.py \
  app/services/protocol_deconstruction_executor.py \
  app/config.py

git diff --check
```

结果：

```text
compileall_and_diff_check=PASS
```

实时模型检查：

```text
curl ... http://127.0.0.1:8001/v1/models
```

结果包含目标模型：

```text
[('Qwen3.8-27B-oQ8e-fp16-mtp', 'omlx', 131072)]
```

## Blockers Or Missing Environment

代码、聚焦测试和静态检查均无阻塞。

本 worker 尚未执行修复后的完整隔离 D001-II 与 MG-K10-SAR III 真实解构运行，因此尚不能确认 durable job 已完全消除 `SEMANTIC_DRAFT_MISSING`。

## Rerun Requests Or Next Step

由父 Codex 执行最终真实隔离复跑，并确认：

1. 初始请求发送 `protocol_semantic_deconstruction_candidate` strict schema。
2. 局部修订请求发送 `protocol_semantic_rule_repair` strict schema。
3. 实际请求模型为 `Qwen3.8-27B-oQ8e-fp16-mtp`。
4. durable job 成功产出并保存 `final_draft`。
5. 若仍失败，StepFailure detail 中仅出现有界 schema/gate 诊断，不包含 raw output 或 hidden reasoning。
