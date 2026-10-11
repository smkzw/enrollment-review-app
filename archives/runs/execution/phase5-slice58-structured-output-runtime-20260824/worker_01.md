# Execution Output: phase5-slice58-structured-output-runtime-20260824 - worker_01

## Boundary And Context Check

已读取指定 execution context 与 plan。仅在当前工作树内做只读分析；未修改代码、未读取生产路径、未启动会议、未访问互联网、未执行最终验收。

## Work Performed

分析了：

- 严格 JSON Schema、递归表达式与约束解码风险。
- D001-II 实际冻结输入的 Prompt、Schema、批次和历史累积规模。
- oMLX/DeepSeek transport 参数及重试行为。
- 真实隔离 Job 的运行时间线与持久化状态。
- 批次闭包、candidate/repair 语义及确定性 Gate 保留风险。

## Artifacts And Evidence

关键证据：

- `app/domain/contracts/rules.py:217-239`：`RuleExpression` 是递归 `oneOf`；`LogicalExpression.children` 可继续引用自身。
- `app/domain/contracts/rules.py:154-206`：`AtomicPredicate.value` 含重叠的 string/integer/number/boolean/list/null 分支。
- `app/domain/contracts/rules.py:41-109`：`TimeConstraint` 含 nullable union 与条件性 `allOf/if/then`。
- `app/agents/protocol_deconstructor.py:185-222`：候选 Schema 约 9,516 字符，包含 19 个 `$defs`、18 个 `anyOf`、3 个 `oneOf`、1 个 `allOf`、3 个 discriminator，并存在 `LogicalExpression` 自递归。
- D001-II 冻结检查点：
  - 36 条父规则：`IN-01..06`、`EX-01..30`
  - 50 条必做项目
  - 91 个来源材料
  - `source_input`：56,183 字符
  - 默认初始 Prompt：71,692 字符 / 86,036 UTF-8 bytes
  - Prompt 内 Schema：9,516 字符
- 现有批次算法 `app/agents/protocol_deconstructor.py:1259-1366`：
  - 每批 3 条父规则，共 12 批。
  - `requested_rule_codes` 只改变提示文字，不裁剪 `source_input`。
  - 每个后续批次仍重复完整 Schema。
  - 无模型输出时，仅用户 Prompt 累积至第 12 批已达 178,179 字符；尚未计入历史中的 assistant 输出。
- `app/agents/deepseek_protocol_transport.py:101-126`：
  - oMLX 每次发送完整严格 Schema。
  - `max_tokens` 固定为 60,000。
  - DeepSeek 仍使用普通 `json_object`，不应改变。
- `app/agents/deepseek_protocol_transport.py:193-203`：
  - `continue_session` 每次重发完整历史，因此批次不是独立的小请求。
- 真实隔离 Job：
  - `generate_draft` 于 `2026-08-23 17:53:43.358793` 启动。
  - 最近更新时间 `18:41:27.810051`，已持续 2,864.45 秒（47 分 44 秒）。
  - 仍为 `running`，进度停在 6/10。
  - 只有 `step_started`，没有完成事件、草稿、Agent call 或模型输出记录。

## Commands And Observations

使用了：

- `sed` / `nl` / `rg`：读取解构 transport、Schema、runner、测试。
- `sqlite3 -readonly`：读取隔离数据库 Job、Step、Event、Checkpoint。
- `./.venv/bin/python`：计算真实冻结输入、Schema、Prompt、批次和递归引用图。

核心观察：

1. 主要瓶颈最可能在 oMLX 约束语法构建/解码，而非 Gate 或 Pydantic hydration。递归 `oneOf`、重叠 scalar `anyOf`、nullable 分支及条件 `allOf` 组合，是静态上最危险的结构。该点属于基于代码与运行负载的推断，当前没有 oMLX 内部编译日志可直接证明。

2. 当前“每 3 条父规则分批”没有真正降低首个请求规模：单条、三条、36 条代码时 Prompt 分别约为 71,711、71,729、72,026 字符。

3. Schema 在消息文本和 `response_format` 中各发送一次；一次请求约重复 19K 字符结构定义。后续同一 session 还会不断累积历史。

4. 60,000 token 的统一上限没有按批次限制；D001 理论上最多 12 个初始批次、最多 36 个语义修订批次，另有结构修复和空正文重试，存在调用放大。

5. 现有 `_validate_semantic_batch()` 只校验父规则编号顺序和 `candidate_id`。小批次合同还需要确定性校验 `affected_scope` 不越过本批、警告/未决项不跨批污染，并在最终 merge 前检查完整闭包。

## Blockers Or Missing Environment

- 隔离数据库没有 `agent_calls` 或原始模型响应，无法判断 47 分钟停在首批 Schema 编译、首批生成还是后续历史累积。
- 当前工作树没有 oMLX 约束解码内部日志或编译耗时指标。
- 本 Worker 只负责分析，未创建实现或测试工件。

## Rerun Requests Or Next Step

建议 worker_02/Codex 按以下优先级修订：

1. 保留最终 `ProtocolSemanticDeconstructionCandidate`、Pydantic 校验和确定性 Gate；仅为 oMLX 增加小型 wire contract。
2. wire contract 使用每批有限父规则、明确 `maxItems`，避免递归 `oneOf`、条件 `allOf` 和重叠 scalar union；可采用扁平表达式节点/边 IR，响应后再重建领域表达式。
3. 去除 Prompt 中完整 Schema 文本，保留简短字段说明；严格 Schema 仍通过 oMLX `response_format=json_schema` 发送。
4. 按批裁剪父规则目录和来源材料；流程目录继续由系统确定性装配，不让模型重复生成。
5. 增加独立的批次/修订 token 上限，不再沿用 60,000；每批失败应在有界时间内返回中文诊断。
6. 保留 DeepSeek 的 `json_object` 路径，并增加测试证明其兼容性。
7. 聚焦回归应覆盖：12 批 D001 规模、历史长度上限、candidate/repair 闭包、跨批 warning 越界拒绝、Gate 结构保真及 oMLX/DeepSeek response format 分支。
