# Execution Output: phase5-slice58-structured-output-runtime-20260824 - worker_02

## Boundary And Context Check

已读取初始 context、执行计划、worker_03 独立审阅及授权范围内当前 diff。未读取 job 数据库或临床源文件，未修改 runner 报告文件及授权范围外文件。

## Work Performed

- 收紧非递归 oMLX wire schema：
  - 时间数量要求正整数和有效单位。
  - 时间约束要求非空 `anchor_type`、`direction`、布尔 `allow_partial_date`。
  - occurrence/prospective window、period 及 predicate 核心字段均要求完整语义。
  - 移除 wire 层 `unit_match_policy`，hydration 固定为 `exact_canonical_label`。
- 增加防御性 hydration：
  - 全空可选对象归一化为 `None`。
  - 部分对象精确报错，不再生成伪完整领域对象。
  - 保留现有 Pydantic、来源、阶段、编号、时间锚点和 deterministic gate。
- 保持并验证批次身份、来源闭包、反馈目标规则压缩及跨批次 provenance 校验。
- oMLX 默认单批输出上限改为 `8192`；DeepSeek 仍保持 `json_object`、60000 token 配置和既有 reasoning 行为。
- OpenAI client 明确设置 `max_retries=0`；`finish_reason="length"` 永不解析为完整 JSON，仅进入有界重试。
- 会话压缩超过 12000 字符时显式失败，不再静默截断。
- 强化 prompt，要求仅输出 1–3 个父规则的最小完整图，禁止重复节点、组件、摘录和其他批次内容。

## Artifacts And Evidence

修改文件：

- `app/agents/protocol_deconstructor.py`
- `app/agents/deepseek_protocol_transport.py`
- `app/config.py`
- `tests/v2/protocols/test_protocol_deconstructor_adapter_slice3.py`
- `tests/v2/protocols/test_deepseek_protocol_transport_slice3.py`
- `tests/v2/protocols/test_deconstruction_transport_config.py`（新增）

验证覆盖：

- nullable-placeholder 回归
- partial nested object 拒绝
- 精确领域 round trip
- wire schema 无 `unit_match_policy`
- 无 `maxItems: 128`
- compact 多批历史实际压缩
- 错误 repair batch id
- ownerless/cross-batch source refs
- feedback payload 不含全量规则/来源
- provenance mismatch
- SDK retry 配置
- `finish_reason="length"`
- 超限 history anchor 显式失败

## Commands And Observations

- 聚焦协议测试：`70 passed, 5 warnings`
- 完整协议回归：`415 passed, 58 warnings in 113.16s`
- JSON Schema `Draft202012Validator.check_schema`：candidate/repair schema 均通过；编码长度约 5801/5769 字符。
- `py_compile`：通过。
- `git diff --check`：通过。
- 授权范围状态仅包含上述文件修改/新增。

## Blockers Or Missing Environment

未发现阻塞。警告为既有 Python/SQLAlchemy deprecation warnings。

未运行真实 D001-II 端到端重试，因此不能宣称真实项目运行已最终验收。LibreOffice 相关问题未在本授权范围内处理。

## Rerun Requests Or Next Step

请 Codex 在独立环境重新执行真实 D001-II 首批运行，重点确认：

1. oMLX 实际请求 `max_tokens=8192`；
2. provider 不再生成 nullable placeholder；
3. 首批 `finish_reason` 不再因 16000 token 上限截断；
4. 若仍失败，记录完整 job-level deadline 风险。当前仍无新增 whole-job global deadline；仅有 600 秒请求 timeout、SDK 零重试及应用层两次有限响应尝试。
