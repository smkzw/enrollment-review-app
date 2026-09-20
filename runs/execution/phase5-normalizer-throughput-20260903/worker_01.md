审计所需的全部证据已收集完毕。现在汇总最终报告。

# Execution Output: phase5-normalizer-throughput-20260903 - worker_01

## Boundary And Context Check

- 工作目录：runner 绑定的 worktree `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`，分支 `codex/phase5-clinical-facts-profile`。全程只读，未创建、未修改、未删除任何文件（含报告文件；本报告按指示仅在最终响应中返回）。
- 已读初始上下文：`context/phase5-normalizer-throughput-20260903_execution_context.md`、`plans/codex_execution_phase5-normalizer-throughput-20260903.md`。本次执行 Work Item 1（只读审计），未触碰 worker_02/03 的实现项。
- 未读取任何原始临床资料；所有测量基于合成输入与生产代码路径。未运行 pytest（避免产生缓存写入，与"不修改文件"边界保持一致）。

## Work Performed

对 Evidence Normalizer 的提示、定位、资料要求、传输调用链做了端到端只读审计，并用项目 venv 对真实代码路径做了只读的体积测量。结论先行：

**（观察）小时级单页时延的主导因素不是单次调用本身，而是“串行 × 高固定开销 × 输出预算”三层叠加：**

1. **调用严格串行（最大墙上时钟杠杆）**。事实规范化任务的所有 `normalize_*` 步骤默认逐个执行：`JobRunner` 默认 `max_parallel_steps <= 1`（`app/workflow/runner.py:226-243`），且并行波次的默认作用域硬编码为 `discovery_*`（`runner.py:201-204`），而规范化步骤 ID 是 `normalize_{idx:03d}_{doc}`（`app/services/fact_normalization_job_service.py:217-221`），永不匹配；任务 payload 也未冻结任何 `execution_control`（grep 全文无命中）。每个步骤 = 一次完整 LLM 调用。
2. **每次调用的模型可见输入约 90% 是固定前缀**。`build_evidence_normalizer_prompt`（`app/agents/evidence_normalizer.py:539-573`）每次渲染：模板 31 字符 + `_SYSTEM_CONTRACT` 3519 字符 + `_compact_schema()` 9816 字符 ≈ **13.4k 字符静态前缀**，再叠加动态 payload。`EVIDENCE_NORMALIZER_MAX_PAGES_PER_CALL` 默认 2（`app/config.py:298-300`），一份 100 页的证据包拆成 ~50 次串行调用，静态前缀重复 ~50 次（约 67 万字符纯重复），另外每次调用还要重复整份 `related_requirements`（按规则集全部已到期要求加载，`fact_normalization_source_adapter.py:155-167`）。
3. **输出预算大且强制逐字段展开**。Schema 把每个定义对象的所有字段设为 required（共 62 个 required；`evidence_normalizer.py:388-450` 的 `require_declared_properties`），每条候选必须显式携带全部 15/11/16 个字段（含显式 null）；`max_tokens=16384`、effort 默认 `medium`（继承 MTPLX）。解码时长与输出 token 数成正比。
4. **修复循环放大成本**。`continue_session` 追加全量历史（`deepseek_evidence_normalizer_transport.py:171-184`）：一次 schema 修复 = 原 prompt（13.4k 静态+payload）+ 上一次完整输出 + 修复 prompt（再次内嵌 9816 字符 schema，`evidence_normalizer.py:949-959`），最多 2 次；传输重试 2 次且无退避（`evidence_normalizer.py:1029-1065`）。
5. **供应商现状**：Normalizer 白名单仅 `{deepseek, deepseek-api, mtplx, mtplx-api, omlx, local-omlx}`（`evidence_normalizer.py:88-97`），默认路由 MTPLX（`config.py:285-306`）；GLM `zhipu-coding-plan` 端点已在本仓其他任务配置（`INDEPENDENT_VLM_*`、`DECONSTRUCT_GLM_*`，`config.py:166-257`，复用同一 BigModel 凭据），但 Normalizer 尚未接入——这是 worker_02 的工作面。MTPLX 注释已确认受限解码会显著拖慢长结构输出，Normalizer 的 mtplx 路径已规避为 `json_object`（`deepseek_evidence_normalizer_transport.py:231-243`）；omlx 路径仍用完整 `json_schema` 严格受限解码。

**（推断）按此结构估算**：2 页 × 2000 字符真实页 + 13.4k 静态前缀 → 单次输入约 17-18k 字符（≈7-9k token，合成实测见下节），medium 推理 + 16k 输出预算下本地供应商单次调用可达分钟级；50 次串行即小时级。与任务描述的症状一致。

## Artifacts And Evidence

（本任务无产出文件；以下为审计事实与可泛化最小压缩边界，供 Codex 与 worker_02/03 使用。）

**调用链全图（观察）**：
`FactNormalizationCommandService`（注册 PromptVersion/ModelConfig，`fact_normalization_command_service.py:137-193`）→ `FactNormalizationJobService.create_or_reuse_*`（规划 calls、冻结 `input_sha256`/`max_pages_per_call` 进 payload）→ `JobRunner`（默认串行认领步骤）→ `create_fact_normalization_executor().execute_call`（`fact_normalization_executor.py:793-995`：重建冻结输入 → 传输工厂 `evidence_normalizer_transport_from_model_config` → `EvidenceNormalizerRunner.run` → 确定性校验/页闭包 → 租约事务提交）→ finalize 步骤聚合门禁/发布。
提示构造：`build_evidence_normalizer_prompt` = 模板 + `_SYSTEM_CONTRACT` + `_compact_schema()` + payload（context / related_requirements / pages.effective_text / locators.localized_text，`evidence_normalizer.py:492-536`）+ 可选视觉观察段（+299 字符边界声明）+ 收尾指令。

**输入合同冻结面（worker_03 的硬边界，观察）**：
- `input_scope_sha256` 覆盖 pages（含 `effective_text_sha256`）、`available_locators` **全量含 `localized_text` 与 `source_text_sha256`**、requirements、context、manifest（`app/domain/contracts/evidence_normalizer.py:228-271`）。任务按 `input_sha256` 冻结与重放校验（`fact_normalization_executor.py:572-637`）。**因此合同本身（字段与哈希输入）不可瘦身；可瘦身的只有 `_model_input_payload` 的模型可见投影，以及渲染层。**
- 提示模板哈希 `evidence_normalizer_prompt_template_sha256` = 布局版本 + 模板 + `_SYSTEM_CONTRACT` + `_SCHEMA_REPAIR_CONTRACT` + `_compact_schema()`（`evidence_normalizer.py:373-385`）。**注意：payload 投影不在哈希内**——只改 `_model_input_payload` 不破坏已冻结运行；但改 system contract/schema/布局版本会改变哈希，`_load_frozen_agent_config` 对比持久哈希与当前模块常量（`fact_normalization_executor.py:325-332`），**所有未完成的旧冻结运行会立即硬失败**（PARTIAL_OUTPUT，retryable=False）。新运行会经 `fact_normalization_command_service.py:137-151` 自动注册新 PromptVersion，无需手工迁移；旧未完成运行需重建。

**可泛化的最小压缩边界（建议，按风险从低到高排序）**：

| 层 | 动作 | 预期收益 | 风险 |
|---|---|---|---|
| D 编排（无提示哈希影响） | 并行化：在 job payload 冻结 `execution_control.parallelizable_step_ids`（或扩展 runner scope），runner 允许 `max_parallel_steps>1`；各 call 的 apply 写不同行，finalize 有 `depends_on` 兜底 | 墙上时钟近似 ÷ 并行度，是最大杠杆 | 需验证并行波次下 store 认领/租约行为；本地单机供应商并发上限需尊重 |
| D 编排 | 调大 `EVIDENCE_NORMALIZER_MAX_PAGES_PER_CALL`（env，默认 2） | 摊薄 13.4k 静态前缀、减少调用次数 | 单调用输出更长，修复爆炸半径更大；受 `_MAX_PROMPT_CHARS=100k` 约束 |
| B 投影（哈希不受影响） | schema 去噪：剥离 pydantic 生成的 `title`（61 处/1481 字符）与 `description`（8 处/742 字符） | schema 9816→7524 字符（-23%），零校验语义变化 | 无校验风险；但会改变提示哈希 → 触发布局版本 bump |
| B 投影 | 定位去重：`EFFECTIVE_TEXT` 层且 `localized_text` 是该页 `effective_text` 精确子串的 locator，改为在页文本内联 `[locator_id]` 锚点或 `[start,end)` 偏移渲染，仅对非子串（`RAW_OCR` 层、校正后文本）与 `page_only` 保留独立 echo | 消除任务书所指“重复定位”；页文本越长收益越大 | locator_id 是不透明哈希（`app/evidence/locator.py:97-100`），**必须保留可见锚定**，否则模型盲选 locator → 断言校验失败 → 修复循环反而更慢；内联标记需在合同措辞中声明非正文，防模型把标记抄进候选（确定性门禁可兜底） |
| B 投影 | `related_requirements` 谨慎瘦身（如去 `rule_component_id` 等模型用不到的投影字段——当前投影已最小，见 `evidence_normalizer.py:505-519`） | 随规则集规模线性 | `description` 是绑定 `supported_requirement_ids` 的语义提示，删它会降低绑定质量；不建议本轮动 |
| C 输出形状 | 不建议：放开“全字段 required”或 `model_uncertainty` 可省 | 输出 token 显著下降 → 解码提速 | 该收紧是为防“省略字段逃避逐页闭合”（`evidence_normalizer.py:388-394` 注释），重新打开即回归规避洞；除非实测证明输出是瓶颈，否则不要动 |

**明确不可压缩（冻结审计输入与临床判断，合同约束）**：`EvidenceNormalizerInput` 字段集与 `input_scope_sha256` 的输入、`_hydrate_draft_output` 的系统侧哈希/身份注入、`validate_output_page_closure` 逐页闭包、`_filter_supported_requirement_bindings` 的失败关闭语义。

## Commands And Observations

- `grep -rn normalizer app` → 定位核心：`app/agents/evidence_normalizer.py`（agent+prompt+解码器）、`app/agents/deepseek_evidence_normalizer_transport.py`（OpenAI 兼容传输）、`app/services/fact_normalization_executor.py`（持久执行器）、`app/services/fact_normalization_source_adapter.py`（输入构建）、`app/domain/contracts/evidence_normalizer.py`（合同）、`app/config.py:285-306`（运行配置）。
- `python -c`（项目 `.venv/bin/python`，只读导入测量）：`_SYSTEM_CONTRACT`=3519 字符；`_compact_schema()`=9816 字符；其中 title 1481 + description 742 字符可无风险剥离；`$defs` 11 个、required 合计 62；ProfileLane 13 枚举 252 字符、GapType 13 枚举 330 字符。
- 合成 2 页输入走真实 `build_evidence_normalizer_prompt`：总 14815 字符，静态前缀 13366（90%）；`effective_text` 594 字符；locator 全页 echo 场景下重复量 = 页文本长度（EFFECTIVE_TEXT 层 100% 重复）。粗估输入 ≈6k token（合成小页；真实页按 2×2000 字符估算 7-9k token）。
- 构造过程中两次 pydantic 校验报错（`LocatorPrecision.SENTENCE` 不存在 → 实际枚举 `bbox/text_range/page_excerpt/page_only`；`FactAuthority` 修订为 int；`EvidenceRequirement` 必须绑定 rule_component 或 procedure_catalog 之一）——均属我合成输入的问题，与生产代码无关，已修正后通过；这同时反向验证了输入合同校验在真实生效。

## Blockers Or Missing Environment

- 无阻塞。补充说明两点非阻塞事实：(1) 系统 `python3` 缺 pytest，本项目 `.venv` 完整可用；(2) 未测量真实证据包的页文本分布与单次调用实测耗时——需要真实数据/真实路由，属后续“只读单页速度质量闸门”工作项，本审计只给出结构性证据。

## Rerun Requests Or Next Step

- 给 worker_02：接入 `zhipu-coding-plan` 只需扩展 `SUPPORTED_EVIDENCE_NORMALIZER_PROVIDERS`（`evidence_normalizer.py:88-97`）、`validate_evidence_normalizer_model_config` 无需改动哈希面；传输工厂增加 bigmodel 分支可复用 `INDEPENDENT_VLM_BASE_URL/API_KEY` 模式（`config.py:166-180`）。注意 `_with_v1_suffix` 对 bigmodel `/v4` 端点不适用（其后缀逻辑是 `/v1`）。
- 给 worker_03：优先做“投影层瘦身”（payload 投影 + schema title/description 剥离），配合 `_PROMPT_LAYOUT_VERSION` bump v3→v4；合同字段与 `input_scope_hash` 不动。定位去重必须保留模型可见锚定（内联标记或偏移），不可裸删 `localized_text`。体积测量建议直接复用本报告的合成构造法 + 对比 `_compact_schema()` 前后字符数，另加一条“旧冻结运行会因哈希不匹配硬失败”的回归说明。
- 给 Codex（决策项）：并行化（编排层，无提示哈希影响）是小时级→分钟级的最大单一杠杆，但属编排行为变更，未列入本次三个工作项，是否纳入本轮请 Codex 裁定。
