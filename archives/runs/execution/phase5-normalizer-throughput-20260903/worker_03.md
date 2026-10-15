# 执行输出：phase5-normalizer-throughput-20260903 - worker_03

## 边界与上下文检查

- 运行器当前工作目录（cwd）：worktree `.../enrollment-review-app/.worktrees/phase5-clinical-facts-profile`（分支 `codex/phase5-clinical-facts-profile`），全部读写均在此目录内。未读取 home AGENTS.md/SOUL.md；未做 git 写操作；未安装任何包。
- 初始读取集合：`context/phase5-normalizer-throughput-20260903_execution_context.md`、`plans/codex_execution_phase5-normalizer-throughput-20260903.md`。
- 执行 Work Item 3（模型输入瘦身 + 体积测量 + 回归证据）。附加证据读取（均为本任务必需）：`runs/execution/.../worker_01.md`（审计结论直接定义了本项的压缩边界）、`worker_02.md`（zhipu 接入现状，保证兼容）、`app/agents/evidence_normalizer.py`、`app/agents/deepseek_evidence_normalizer_transport.py`、`app/domain/contracts/evidence_normalizer.py`、`app/services/fact_normalization_source_adapter.py`、`app/services/fact_normalization_executor.py`、`app/services/evidence_locator_service.py`、`app/evidence/locator.py`、相关测试文件。
- 硬边界遵守情况：`EvidenceNormalizerInput`、`input_scope_sha256`、`evidence_normalizer_input_scope_hash`、确定性门禁（页闭包、需求绑定、来源语义白名单）与临床判断语义零改动——只改了冻结输入的"模型可见投影"（worker_01 已证实 payload 投影不在任何哈希内）。未提前实现 Phase 5.5，未硬编码项目临床内容。未执行真实网络调用（凭据归 Codex/用户管理）。

## 已完成工作

实现三层瘦身（均为确定性、可重建、来源闭包不丢的投影层改动）：

1. **Schema 去噪**：`evidence_normalizer_json_schema()` 新增 `_strip_schema_titles()`，递归剥离 pydantic 生成的装饰性 `title`（61 处），保留全部 `description`（其中未解决项字段说明如 code 示例是模型唯一语义来源）。该函数同时服务于提示内嵌与 omlx `response_format`，受限解码语法不受影响（title 非语法键）。`_PROMPT_LAYOUT_VERSION` v3→v4。
2. **消除重复 Schema**：新增 `build_evidence_normalizer_prompt(..., include_output_schema)` 与 `_schema_repair_prompt(..., include_output_schema)`；传输新增只读属性 `enforces_output_json_schema`（仅 `response_format.type == "json_schema"` 时为真，当前即 omlx 路由）。`EvidenceNormalizerRunner.run` 以 `getattr(transport, ...)` 自动探测：受限解码传输的初始提示与同会话修复提示均不再内嵌同一份 Schema（每次请求 `response_format` 仍强制同一结构）；DeepSeek/MTPLX/GLM（json_object）路由行为不变。修复提示对 enforcing 传输同样省略，因 `response_format` 每次请求都会带上。
3. **消除重复定位（主项）**：`_model_input_payload` 重构为 v4——locators 按页嵌套（去掉逐条 `page_number` 重复）；对 `localized_text` 在该页有效文本中**恰好出现一次**的定位，正文内联渲染短代号锚点 `⟦L01⟧原文⟦/L01⟧` 并删除其 echo，locators 条目改为 `{"alias","locator_id","precision"}`；任何歧义场景确定性回退逐字 echo（重复文本、RAW_OCR 层文本不在有效文本、page_only、跨度部分重叠、正文含 `⟦⟧`、整页组合不可嵌套/离散）。代号按 locator_id 升序分配（`_locator_alias_map`）。解码容错：`parse_evidence_normalizer_output` 新增 `locator_alias_map` 参数，`_remap_locator_aliases` 在校验前把输出中的代号精确还原为完整 locator_id（`locator_ids`/`assertion_basis.locator_id`/`affected_locator_ids`；未知编号原样保留继续被拒绝）。**关键设计动机（实测驱动）**：locator_id 为 40 字符不透明哈希，全 id 锚点每个约 85 字符开销，只在跨度 >63 字符时才省字符（真实中文临床句常更短，fixture 实证如 `excerpt="ALT 5"`）；短代号锚点约 11 字符+条目内 16 字符，配合解码还原，对任意跨度长度都是净赢，且模型定位绑定反而更容易（代号就在原句上）。

体积测量（同一次合成冻结输入、生产代码路径、改动前后 apples-to-apples；2 密集页 ×16 句 + 33 定位器 + 10 资料要求）：

| 指标 | v3 基线 | v4（Schema 内嵌，MTPLX/GLM 路由） | v4（Schema 强制传输，omlx 路由） |
|---|---|---|---|
| 单次提示总字符 | 22102 | **19637（−2465，−11.2%）** | **11356（−48.6%）** |
| 紧凑 Schema | 9816 | 8274（−1542） | 不进提示（API 字段承载，同样 8274） |
| 系统合同 | 3519 | 3790（+271，锚点措辞为正确性必需） | 同左 |
| 定位 echo | 774 字符（≈96% 与页文本重复） | 仅剩 page_only 的 null | 同左 |

长句页组（每句追加 ~48 字符复核说明）实测 21205（内嵌）/12924（强制）——echo 消除量随定位覆盖文本线性放大，锚点开销固定。每次调用 Schema 净省 1542 字符；按 worker_01 审计的 ~50 次串行调用、100 页证据包估算，仅 Schema 去噪即省 ~7.5 万字符/运行，omlx 强制路由叠加省 ~50 万字符/运行（编排串行杠杆不在本项范围，已在 worker_01 报告中留 Codex 裁定）。

## 工件与证据

修改文件（均在授权范围内；normalizer 相关文件在本 worktree 为上一 slice 遗留的未跟踪状态，与 worker_02 报告一致）：
- `app/agents/evidence_normalizer.py`：布局 v4、`_strip_schema_titles`、`_anchor_spans_for_page`/`_render_anchored_page_text`/`_locator_alias_map`/`_remap_locator_aliases`、`_model_input_payload` v4、`include_output_schema` 贯穿构建/修复/Runner、合同新增锚点措辞（锚点非正文、引用一律完整 locator_id）。
- `app/agents/deepseek_evidence_normalizer_transport.py`：新增 `enforces_output_json_schema` 属性（只读，不改任何供应商行为）。
- `tests/v2/agents/test_evidence_normalizer_adapter.py`：更新 1 个 v3 结构断言，新增 9 个聚焦测试（锚定/echo 回退/部分重叠回退/Schema 去 title 留 description/省略内嵌 Schema/布局 v4/代号解码还原+未知代号拒绝/Runner 双向探测/修复提示省略）。
- `tests/v2/agents/test_evidence_normalizer_transport_config.py`：新增 2 个能力位测试（omlx=True；mtplx/deepseek/zhipu=False；显式 json_object/json_schema 构造）。
- `tests/v2/services/test_fact_normalization_visual_observation_wiring.py`：`assert RAW_TEXT in prompt` → 剔除渲染标记后逐字匹配（`re.sub(r"⟦/?[^⟧]*⟧", "", prompt)`），保持"有效文本未被观察改写"的原测试意图（v3 断言隐含了正文连续渲染这一实现细节）。

回归测试全部通过：
- `tests/v2/agents/` 全目录：**124 passed**（含 MTPLX 身份/默认路由钉死回归、既有解码器与 Runner 测试零改动通过）。
- 注册/任务/执行器冻结合同链（command_service + registration + executor_profile）：**27 passed**。
- 视觉观察接线、api/test_fact_normalization、contract_logic、planning、source_adapter、persistence、publication、expectations、fact_repositories 合并跑：**409 passed**。
- `python -m compileall` 五个改动文件：OK。提示模板哈希稳定性复查：稳定，且因布局版本/合同/Schema 变更必然不同于 v3。

## 命令与观察

- 测量脚本以 heredoc 方式运行（`.venv/bin/python - <<EOF`，未在工作区写任何临时文件），基线与终测使用同一构造器。
- 观察 1（开发中自我纠错）：先实现了全 id 锚点，测量后确认短中文句（23-35 字符）场景下每个定位净亏 ~33 字符，遂改为短代号+解码还原方案；该决策有量化依据。
- 观察 2：调试中发现并修复 `_remap_locator_aliases` 的映射方向错误（渲染用 id→alias，还原需反向），由测试 `test_decoder_remaps_anchor_aliases_to_full_locator_ids` 钉死。
- 观察 3：`fact_evidence_closure.py:570` 等确定性门禁会把断言文本与定位原文逐字比对——若模型把锚点符号抄进输出，会在门禁处确定性失败并进入修复循环，构成锚点污染的兜底；合同措辞已显式禁止。
- 观察 4：`evidence_normalizer_prompt_template_sha256` 的组成（布局版本+模板+合同+修复合同+Schema）随本次变更自动变化；执行器 `_load_frozen_agent_config`（fact_normalization_executor.py:325-332）对持久哈希强校验。

## 阻碍或缺失的环境

- 无阻塞。两点说明：
  1. **（证据，非阻塞）旧冻结运行的哈希不兼容**：所有在 v3 提示下创建且尚未完成的规范化运行，在下次认领时会因持久 `template_sha256` 与新模块常量不一致而硬失败（PARTIAL_OUTPUT，retryable=False）；新运行经 `fact_normalization_command_service.py:137-151` 自动注册新 PromptVersion，无需手工迁移。这与 worker_01 审计的预期行为一致，属布局版本升级的既定代价。
  2. **（剩余验证，非阻塞）真实路由冒烟未做**：代号锚点的模型实际引用行为（是否偶发把代号写进 `locator_ids`——解码器可容忍还原，但未实测频率）与单页时延改善需在配置 GLM 凭据的环境跑一次真实单页调用，属本包"只读单页速度质量闸门"工作项，超出本项边界。

## 重跑请求或下一步

- 无重跑请求。本项实现与回归已完成，可进入 Codex 验收。
- 建议给速度质量闸门执行者的输入：对比指标用上表口径（同冻结输入、`build_evidence_normalizer_prompt` 前后字符数）；GLM 路由（json_object）提示仍内嵌 Schema，oMLX 路由提示省略内嵌 Schema；若真实调用发现模型频繁输出代号，解码器已可无损还原，无需修复循环。
- 给 Codex 的后续决策项（本项未动，属增量机会）：`related_requirements` 投影中的 3 个来源标志字段（`required_source_types`/`allows_screening_record_transcription`/`requires_contemporaneous_objective_source`）按 worker_01 建议本轮保留，因其属模型可见的语义提示面，动它需单独评估对绑定行为的影响；并行化与 `MAX_PAGES_PER_CALL` 仍是更大的墙上时钟杠杆（worker_01 表格 D 层）。
