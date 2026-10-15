# Execution Output: phase5-slice58-structured-output-runtime-20260824 - worker_03

## Boundary And Context Check

已读取指定 context/plan，并只读检查当前实现 diff、领域契约、解构门禁、执行器及协议测试。未修改文件，未调用真实 oMLX/DeepSeek，不宣称真实运行时验收。

## Work Performed

- 审查 flat wire schema、表达式/例外/时间窗/证据要求/来源片段/nullable 字段闭包。
- 检查批次来源过滤、candidate/catalog closure、会话压缩及 repair 路由。
- 检查 DeepSeek 的 `json_object`、完整领域契约、reasoning 和历史行为。
- 运行聚焦测试、协议测试套件、编译和 diff 检查。
- 使用冻结 D001-II checkpoint 做静态批次大小和 prompt 体积探针。

## Artifacts And Evidence

按严重性排序：

1. 高：compact semantic repair 未强制校验 `batch_id`。

   `app/agents/protocol_deconstructor.py:1933-1945` 已支持 `expected_batch_id`，但 runner 在 `:2477-2480`、反馈修订在 `:1783-1787` 均未传入。当前 prompt 虽生成 `repair:<codes>`，解析器却接受任意值。

   独立 fake-gate 探针使用目标 `EX-01`，发送错误 `batch_id="repair:IN-01"`，仍得到 `status=可以进入审阅`、2 次 attempt，说明错误批次身份可被应用。

2. 高：传输超时不是端到端有界。

   `app/agents/deepseek_protocol_transport.py:101-105` 使用 `OpenAI(timeout=600.0)`，但未设置 `max_retries=0`；实际 client 观察到 `max_retries=2`。单次失败请求最多可能自动重试 3 次，且 `_complete` 还包含额外调用路径（`:150-180`）。

   D001 冻结目录有 36 个父规则，即至少 12 个 3-rule 批次；runner 的 semantic repair limit 为 `max(16, catalog_size)`（`protocol_deconstructor.py:2466-2469`）。没有整个任务的 deadline/cancellation，慢失败仍可能持续数小时。

3. 高：批次来源闭包仍允许不属于目标父规则的来源 ID。

   `app/agents/protocol_deconstructor.py:647-684` 只过滤 `source_materials`，但仍把全部 `allowed_source_span_ids` 发送给模型（`:675`）。`_validate_semantic_batch`（`:1867-1880`）在 `source_owners` 为空时放行来源。

   独立探针将 IN-01 的来源改为只属于流程目录的 `span-proc-screen`，校验结果为 accepted。最终门禁可能拦截，但批次 prompt、repair 和诊断边界已被污染。

4. 高：compact 反馈修订仍发送完整 frozen input。

   `app/agents/protocol_deconstructor.py:1761-1774` 直接使用 `source_input.model_dump_json()`，没有复用按目标父规则过滤的批次 payload。D001 checkpoint 的 source input 序列化后为约 56,183 字符，包含 36 个父规则和 91 个来源材料，可能抵消 compact 方案并逼近上下文上限。

5. 中高：wire schema 对合法领域表达式施加未在领域模型中定义的 128 上限。

   `app/agents/protocol_deconstructor.py:387-390` 和 `:443-447` 限制 children/nodes 为 128；但 `app/domain/contracts/rules.py:223-234` 的 `LogicalExpression.children` 没有该上限。超过 128 节点的合法领域表达式无法无损编码，应明确加入领域门禁或移除该隐式限制。

6. 中：批次合并静默丢失后续 `created_by_agent_call_id`。

   `_merge_semantic_batches`（`protocol_deconstructor.py:1918-1930`）只取第一批的 call ID，不校验后续批次一致性。独立探针用 `call-1`/`call-2` 合并成功并保留 `call-1`，造成后续内容 provenance 被错误归属。

7. 中：聚焦测试没有真正覆盖目标 compact 多批路径。

   - 大目录批次测试（`tests/v2/protocols/test_protocol_deconstructor_adapter_slice3.py:694-750`）使用非 compact `FakeTransport`。
   - compact 测试（`:825-868`）只有单批，且 fake compactor 不实际替换 history。
   - 没有错误 repair `batch_id`、流程来源泄漏、128 节点、`finish_reason="length"`、OpenAI retry 上限测试。
   - wire schema 测试部分只是把结果与同一函数重新生成的 schema 比较，独立性有限。

正向结论：

- wire round-trip 探针覆盖了逻辑表达式、例外、时间上下界、半衰期、occurrence/prospective window、prospective period、source clauses、数值列表和 source validity window，`roundtrip_equal=True`。
- `_merge_semantic_batches` 和 hydration 均执行完整父规则顺序/数量闭包。
- DeepSeek 显式 backend 仍使用 `response_format={"type":"json_object"}`、`deepseek-v4` reasoning 设置和完整 history；聚焦测试通过。
- D001 静态 prompt 探针显示每个 3-rule 批次只发送选中材料文本；但当前来源 ID 校验仍不闭合。

## Commands And Observations

- `.venv/bin/pytest -q tests/v2/protocols/test_deepseek_protocol_transport_slice3.py tests/v2/protocols/test_protocol_deconstructor_adapter_slice3.py tests/v2/protocols/test_deconstruction_transport_config.py`

  结果：`55 passed`。

- `.venv/bin/pytest -q tests/v2/protocols`

  结果：`392 passed, 8 failed`。8 项均为 LibreOffice `/opt/homebrew/bin/soffice` `Abort trap: 6` 渲染失败，未指向本切片四个实现文件。

- `.venv/bin/python -m compileall ...`

  结果：通过。

- `git diff --check -- ...`

  结果：通过。

- 初次使用系统 pytest 时因缺少 `sqlalchemy` 失败；切换项目已有 `.venv` 后测试正常。未安装或修改环境。

## Blockers Or Missing Environment

- LibreOffice 当前无法稳定执行，因此协议全套中的真实文档渲染回归未完成。
- 未执行真实 oMLX/DeepSeek 请求；无法证明 16,000 token、600 秒 timeout 或 provider strict decoding 的真实表现。
- 当前没有独立的 job-level deadline 测试。

## Rerun Requests Or Next Step

建议 Codex 先修复：

1. 在 runner 和反馈修订中传递并校验精确 `expected_batch_id`。
2. 将 batch source IDs 限制为目标父规则来源，并校验 unresolved `source_refs`。
3. 为 OpenAI client 明确设置有限 retry，并增加整个解构任务 deadline。
4. 决定 128 节点限制是否属于正式领域契约。
5. 增加真实 compact 多批 fake transport、错误 batch ID、来源泄漏和 truncated-output 回归。

之后再在全新隔离目录执行真实 D001-II 与 MG-K10-SAR-III；本 worker 不做最终运行时接受。
