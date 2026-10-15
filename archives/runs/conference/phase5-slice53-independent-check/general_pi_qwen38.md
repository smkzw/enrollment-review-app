# Conference Participant Output: phase5-slice53-independent-check - general_pi_qwen38

## Boundary Check

- 只读审查：未修改任何文件；未运行测试套件作为验收（仅读取测试清单核对覆盖意图）；未触碰生产路径；未读取其他参与者输出。
- 审查对象为当前 worktree 未提交实现：`app/agents/evidence_normalizer.py`、`app/agents/deepseek_evidence_normalizer_transport.py`、`app/domain/contracts/evidence_normalizer.py`、`app/domain/planning/fact_normalization_planning.py`、`app/services/fact_normalization_{source_adapter,job_service,executor}.py`、`app/workflow/{runner,jobstore}.py` 差异、`app/storage/fact_repositories.py` 差异，以及相关门禁/权威模块。
- 注意：审查期间 `fact_normalization_executor.py` 与 `evidence_normalizer.py` 合同文件仍在被实现方改动（行数增长、新增 `PersistedEvidenceNormalizerUnresolvedItem` 持久化）。本报告以 2026-08-23 05:20 本地时间的快照为准；若实现继续推进，第 1、2 节中涉及执行器的行号需按最新文件复核。

## Independent Work Product

### 结论摘要

冻结输入与幂等哈希的**内容闭包总体成立**：审核节点（含 `episode_revision`）、资料类型、来源方、记录时间占位、EvidenceRequirement 均进入逐调用 `input_scope_sha256`，并经调用哈希传递进运行级幂等键；活动权威、页闭合、locator 真实性、空输出、租约丢失（迟到回包）未发现可被利用的绕过。但我找到 **3 个高严重度问题**（切片参数未冻结导致重建必然失败、运行终态无 FAILED/CANCELLED 投影、PromptVersion/ModelConfig 为未绑定内容的裸标签）与若干中低风险问题。测试通过不等于验收：下述问题多数不在现有测试视野内。

### 按严重度列出的问题

#### HIGH-1 `max_pages_per_call` 未冻结进 Job 载荷，执行期重建硬编码默认 20 —— 非默认切片创建的任务必然全步骤致命失败

- 证据：
  - `app/services/fact_normalization_job_service.py` `create_or_reuse_from_source(..., max_pages_per_call=20)` 用该参数切片生成 `calls`，但 `job_payload` 只存 `{run_id, idempotency_key, authority, prompt_version_id, model_config_id, input_scope_sha256, calls}`，**不含切片参数**。
  - 执行期 `_build_input` → `app/services/fact_normalization_source_adapter.py` `build_evidence_normalizer_input` → `build_fact_normalization_plan(...)` **未传 `max_pages_per_call`，恒用默认 20** 重新规划，再按 `(logical_document_id, page_numbers)` 精确匹配 payload 中的调用；不匹配即 `FactPlanningSourceError` → `StepFailure(retryable=False, PARTIAL_OUTPUT)`。
- 后果：任何以 `max_pages_per_call != 20` 创建的运行（>20 页文档被不同边界切分），每个模型步骤都会重建出不同的页组 → 全部致命失败，任务无法完成，且错误码伪装成“部分输出”而非定义漂移。当前仅因无人传非默认值而未爆。
- 修复建议（择一）：
  1. 把 `max_pages_per_call` 写入 `job_payload`，`_build_input` 透传给 `build_evidence_normalizer_input`（并在 `FactNormalizationCallSpec`/幂等材料中冻结）；或
  2. 重建时不按默认重新切片，而是以 payload 的 `(logical_document_id, page_numbers)` 为权威从修订中直接取页（规划器只负责供料，不再决定分组）；或
  3. 过渡护栏：在 `create_or_reuse_from_source` 拒绝非默认值，直到参数被冻结。
- 安全临时路径：在 Codex 决定前，实现方应先落护栏 3，因为它零风险且立即消除隐患。

#### HIGH-2 `FactNormalizationRun` 无 FAILED/CANCELLED 投影：任务终败/取消后运行状态永久停留 RUNNING

- 证据：
  - `app/storage/fact_repositories.py` 新增 `set_status` 只被 `app/services/fact_normalization_executor.py` `execute_finalize` 调用，取值仅 `SUCCEEDED`/`PARTIAL`。
  - 全库检索 `FactNormalizationRunStatus.FAILED`/`CANCELLED`：无任何写入点。
  - `app/api/v2/app.py` 的 `on_cancelled=project_cancelled_evidence_job` 只投影证据 OCR 运行（`recover_evidence_ocr_runs`），无事实规范化对应物；`JobStore.finish_failure`/`_cancel_steps` 亦无领域钩子。
- 后果：任一步骤耗尽重试（如持续 `TRANSPORT_FAILED`、`EMPTY_OUTPUT` 致命失败）或任务被取消后，Job 层终态正确，但 `FactNormalizationRun.status='running'` 永久滞留。P5-AC11“无永久处理中”在运行镜像层被违反；下游（5.4/5.5 的 Profile 与待核对投影）读取运行状态会把已死任务显示为进行中。幂等复用路径返回 `status=job.state`（job 层），与运行记录不一致。
- 修复建议：在 finalize 之外补终态投影——`finish_failure`/取消边界（或仿 `recover_evidence_ocr_runs` 的 `recover_fact_normalization_runs`）将 RUNNING 运行标记为 `FAILED`/`CANCELLED`；`set_status` 当前“仅 RUNNING 可转”的约束正好防止重复投影。此项应在 5.3 内完成，因为 `FactNormalizationRunStatus` 枚举与 `set_status` 就是为此切片引入的。

#### HIGH-3 幂等键中的 `prompt_version_id` / `model_config_id` 是未绑定实际内容的裸标签；实际 prompt/模型/采样参数变化不改变幂等键

- 证据：
  - `app/domain/contracts/facts.py` `fact_run_idempotency_key` 将 `prompt_version_id`、`model_config_id` 作为字符串纳入键；`create_or_reuse_job` 仅校验非空，从不把它们解析到真实模型/提示词配置。
  - 实际提示词 = `FactNormalizationExecutorConfig.prompt_template` 硬编码默认串 + `app/agents/evidence_normalizer.py` 内嵌 `_SYSTEM_CONTRACT`；实际模型 = `app/agents/deepseek_evidence_normalizer_transport.py` 复用 `DECONSTRUCT_MODEL`/`DECONSTRUCT_REASONING_EFFORT`/`DECONSTRUCT_MAX_TOKENS`，`temperature=0.2` 硬编码。
  - `evidence_normalizer_prompt_template_sha256()`（对模板+系统合同的内容哈希）已存在，但除测试外**无任何调用点**——没有把内容哈希绑定到 `prompt_version_id` 的任何代码。
- 后果：改 `_SYSTEM_CONTRACT` 一个词、改 `DECONSTRUCT_MODEL` 或 temperature，只要调用方沿用同一对 `prompt_version_id/model_config_id` 字符串，幂等键不变 → 系统会**复用旧运行/旧候选**，仿佛模型行为没变。这直接违背 P5-R09“同一活动处理修订、PromptVersion、ModelConfig 和输入范围重复运行不得创建重复事实”的逆命题：不同实际模型行为被当成同一身份。真实模型闭环（implement.md 5.3 门槛）启动前这是审计黑洞。
- 修复建议：建立最小注册表或冻结字段：`prompt_version_id` 必须等于/携带 `evidence_normalizer_prompt_template_sha256(实际模板)`，`model_config_id` 必须绑定实际 `{model, temperature, reasoning_effort, max_tokens}` 的规范哈希；`create_or_reuse_job` 在创建与复用两个分支都核对。5.3 不加 API 也可先在服务层强制该绑定。

#### MED-1 零候选但逐页未解决闭合的调用会在运行级被判为失败原因，合同语义互相矛盾

- `app/domain/contracts/evidence_normalizer.py` `EvidenceNormalizerOutput` 明示允许“空候选+逐页闭合”的合法场景；`EvidenceNormalizerRunner` 与执行器也接受“仅未解决项”的调用（测试 `test_unresolved_only_run_is_durable_and_marked_partial`）。
- 但 `app/domain/gates/fact_batch_orchestration.py` `orchestrate_run_gates` 的 `empty_calls` 逻辑：**只要某个 call 无候选**（即便有未解决项闭合），就追加失败原因“调用无候选输出：…”→ `overall=REJECTED` → finalize 把运行标记 `PARTIAL`（测试 `test_run_orchestration_rejects_one_empty_document_call` 固化了该行为）。
- 后果：真正空白的文档（整页 `page_unreadable` 未解决闭合）必然产出 PARTIAL 运行与 REJECTED 失败原因。方向保守（不会静默成功），不构成安全绕过，但语义冲突会在 5.4/5.5 的“待核对/资料缺口”投影中制造假性质量告警，且与 normalizer 合同文档直接矛盾。
- 建议：若“空候选+未解决闭合”应视为合法闭合，则 `empty_calls` 应豁免已有持久化未解决项覆盖全部页的调用；若坚持保守拒绝，则修改 `EvidenceNormalizerOutput` 文档与系统提示词，消除“合法场景”的承诺。请 Codex 裁决语义。

#### MED-2 两套互相分叉的 `call_id` 派生方案，其中一套是死代码

- `app/domain/planning/fact_normalization_planning.py` `build_fact_calls_from_plan` 生成 `{run_id}:call-{idx:04d}-{sha8}` 格式的 `FactNormalizationCall`；
- 持久化实际走 `app/services/fact_normalization_job_service.py` `_build_persisted_calls` 的 `call_{canonical_hash[:24]}`，执行器只认 payload 里的后者。
- 前者除导出与测试外无消费者。两套身份格式并存是未来漂移源（例如误用前者落库后与幂等重放冲突）。建议删除 `build_fact_calls_from_plan` 或让持久化路径唯一复用它。

#### MED-3 两个不同定义的“输入范围哈希”同名共存

- 规划层 `compute_input_scope_hash`（含 contract_version、authority、revision、manifest 哈希、逐调用哈希）与作业层 `_compute_input_scope_sha256`（仅 `{calls:[{logical_document_id,page_numbers,input_sha256}]}`）。
- 运行记录持久化的是作业层哈希；规划层哈希只存在于 `FactNormalizationPlan` 返回对象，被 `create_or_reuse_from_source` 丢弃。二者都确定性且被逐调用哈希支配，当前无实际分叉，但同名双域是后续“改了哈希算法以为改了幂等”的陷阱。建议二选一并删除另一个。

#### MED-4 `raw_output_sha256` 在两条传输路径下语义不同

- `transport_fn`（结构化）路径：`_sha256(json.dumps(raw_output.model_dump(...), sort_keys=True))`——**且未用紧凑分隔符**，哈希的是解析后合同的规范化转储；
- 文本传输路径：`EvidenceNormalizerAttempt` 记录的是模型原文哈希。
- 同一列 `FactNormalizationCall.raw_output_sha256` 承载两种语义，且前者与代码库其余 `canonical_hash`（紧凑分隔）风格不一致。审计“模型到底回了什么”时，结构化路径无法还原原文。建议：结构化路径同时保存传输原文哈希，或至少统一为紧凑规范分隔并注明语义。

#### LOW-1 `_build_step_specs` 的 `len(step_id) > 120` 哈希回退是死代码（`safe_doc` 已截断 48 字符，总长 ≤60）。

#### LOW-2 `FactNormalizationRunRepository._by_idempotency_key`、`list_by_run`、`_load_run_candidates` 均为全表扫描+逐行解码；单用户可接受，但 5.5 的 500 事实/多次重算场景会放大。

#### LOW-3 检查点重放分支（`execute_call`/`execute_finalize` 开头对 `last_checkpoint` 的直接返回）跳过权威再校验。当前状态机下不可达（有检查点⇒该步骤已被视为完成，不会重跑；且检查点只能在已通过 `apply` 内权威复核的事务中存在），但若未来引入“重跑已完成步骤”能力即成绕过。建议在分支内补一次 `_validate_authority` 或加注释声明其依赖的不变量。

#### LOW-4 执行器尚未在 `app/api/v2` 注册（`fact_normalization` job 类型无 executor 映射、无创建端点）。这与 5.3“不加 API/UI”的范围一致，不是缺陷；但意味着 HIGH-2 的取消投影必须随 5.4 接线一并落地，届时需复核 `on_cancelled` 是否覆盖事实运行。

### 目标项逐条核对（无绕过证据）

1. **冻结输入与幂等哈希的字段闭包**：`EvidenceNormalizerInput.context` 含 `document_type`、`source_party`、`current_review_stage`、`workflow_stage_id`、`metadata_revision_id`、`document_record_time`；`related_requirements` 按 `requirement_id` 排序进入输入；`evidence_normalizer_input_scope_hash` 将 authority（含 `review_episode_id`+`episode_revision`）、context、requirements、manifest/completion 哈希、页、locator 全部纳入；逐调用哈希经 `calls[].input_sha256` 进入作业层 `input_scope_sha256`，再进入 `fact_run_idempotency_key`。`document_record_time` 恒为 `None` 是因为 `SourceDocumentMetadataRevisionRecord` 无记录时间列，合同文档明确承认该占位语义（不得用上传/筛选/操作日填充），记录时间仅可从有定位正文抽取——与 PRD P5-R04 一致。**注意**：`related_requirements` 过滤为 `STAGE_RANK[due_stage] <= STAGE_RANK[episode.stage]`（已到期集合），这是策略选择且已文档化，不是缺陷。
2. **活动权威**：`execute_call` 在读取会话先 `FactAuthorityValidator.validate`；模型调用在事务外；`apply` 在租约写栅栏事务内**再次**校验；`execute_finalize.apply` 三次校验（权威、修订一致性、页覆盖）。`episode.stage` 变更走 `EpisodeRepository.update`（revisioned update，`revision` 递增）→ 冻结的 `episode_revision` 失配 → `STALE_AUTHORITY` 致命失败并保留上一活动状态。未发现绕过。
3. **页闭合**：规划期 `validate_full_page_closure`+`validate_calls_contiguous`（缺页/多余/重复/间隙全拒）；输出期 `validate_output_page_closure`（每页必须被候选定位或逐页未解决项覆盖，泛化空闭合被拒）；持久化后 `_validate_persisted_page_closure` 在 finalize 复核；最后 `validate_page_coverage` 门禁对完整修订页集合精确相等。四层闭合方向一致且全部安全失败（宁拒勿放）。未发现绕过。
4. **locator 真实性**：候选合同 `locator_ids` 最少 1 个；解码期强制属于本调用 `available_locator_ids`（含 unresolved 与断言定位）；门禁期 `validate_locator_and_text_hash` 复核修订成员资格、页产物/页码闭包、`authenticity`、effective_text 修订绑定、断言哈希一致，并对断言文本做“必须落在定位原文内+否定必须直接支配对象”的字符级闭合（`_validate_assertion_text_closure`）。PAGE_ONLY 定位不足以支撑断言。未发现虚构定位可通过的路径。
5. **空输出**：合同允许空形状，但 `EvidenceNormalizerRunner` 对全空输出抛 `EMPTY_OUTPUT`，`transport_fn` 路径同样；逐页闭合阻止“空候选冒充闭合”；批次门禁对空批次 REJECTED；本切片不写任何发布实体，空输出不可能生成空 Profile。未发现绕过。
6. **租约丢失/迟到回包**：心跳丢失 → `LeaseLostError` 丢弃执行器结果；新增 `acquire_step_commit` 以单条条件 UPDATE（state∈ACTIVE、owner、generation、`lease_expires_at>=now`、步骤 running）作为原子写栅栏，`apply` 只在栅栏后执行且被 `before_commit` 监听器禁止自行提交；栅栏失败回退到 `_lease_guard` → `LeaseLostError`/`StepMismatchError`，整个事务回滚，域副作用与检查点同生共死（`tests/v2/workflow/test_prepared_step_result.py` 覆盖四个场景）。恢复器对过期租约 `recovering`→检查点视为完成/按预算重排。未发现迟到回包可提交双份结果的路径。
7. **重启幂等**：检查点与候选/调用/未解决项在同一事务提交；身份冲突防护（`CALL_IDENTITY_CONFLICT`/`CANDIDATE_IDENTITY_CONFLICT`/`UNRESOLVED_IDENTITY_CONFLICT`）；幂等仓储用 `on_conflict_do_nothing` 原子争抢，同键异哈希抛 `IdempotencyConflict`。候选主键由 `{kind, call_id, position, 内容}` 派生、排除模型自造 ID 与时间戳，重放可重建。未发现重复事实路径（前提：HIGH-3 的模型身份绑定修复后）。

## Evidence And Assumptions

**证据（均为本次只读审查直接观察）**
- 文件快照：`app/services/fact_normalization_executor.py`（490 行，05:19 快照）、`fact_normalization_job_service.py`（429 行）、`fact_normalization_source_adapter.py`（443 行）、`app/domain/planning/fact_normalization_planning.py`（466 行）、`app/domain/contracts/evidence_normalizer.py`（332 行）、`app/agents/evidence_normalizer.py`（541 行）、`deepseek_evidence_normalizer_transport.py`（118 行）、`app/workflow/runner.py:353-425`、`app/workflow/jobstore.py:535-660,1208-1400`、`app/storage/fact_repositories.py:214-236,435-520`、`app/storage/fact_authority.py` 全文、`app/domain/gates/fact_evidence_closure.py:60-520`、`app/domain/gates/fact_batch_orchestration.py:561-961`、`prd.md`、`implement.md §5.3`。
- 差异：`git diff app/workflow/runner.py app/workflow/jobstore.py app/storage/fact_repositories.py`（PreparedStepResult/写栅栏/set_status 为本切片新增）。
- 检索事实：`fact_normalization` 在 `app/api` 零匹配；`FactNormalizationRunStatus.FAILED/CANCELLED` 零写入点；`evidence_normalizer_prompt_template_sha256` 仅测试调用；`build_fact_calls_from_plan` 仅导出/测试。

**假设（标注不确定性）**
- [推断] `EpisodeRepository.update` 修改 `stage` 时按 `apply_revisioned_update` 惯例递增 `revision`（未逐行读该函数实现）；若 stage 变更不 bump revision，则“审核节点锚点漂移→权威失配”的防线退化为仅靠活动指针比对，需补测。建议 Codex 让实现方补一条“stage 前进后运行中任务必须判陈旧”的聚焦测试。
- [推断] 部署锁定 SQLite（幂等仓储使用 `sqlite_insert` 方言）；条件 UPDATE 栅栏在 SQLite 单写者语义下无交错问题，同样的模式在 Postgres READ COMMITTED 也成立，但代码并未声明多库支持。
- 审查期间实现仍在演进（执行器文件在两次读取之间变长）。本报告结论对“结构/边界”稳定，但行号与 LOW 级细节需按提交时文件复核。

## Risks, Gaps, And Verification Needs

1. **HIGH-1 修复前禁止用非默认 `max_pages_per_call` 创建任务**；验证需求：补一条“以非默认切片创建的任务可被执行器重建并完成”的集成测试，或“非默认值在创建期被明确拒绝”的护栏测试。
2. **HIGH-2 验证需求**：注入步骤耗尽重试/任务取消后，断言 `FactNormalizationRun.status` 离开 RUNNING；该测试目前不存在（现有持久化测试只覆盖 SUCCEEDED/PARTIAL 两条路径）。
3. **HIGH-3 验证需求**：真实模型最小闭环（implement.md 5.3 门槛）启动前，必须有 prompt/模型内容哈希绑定的合同测试：同一 `prompt_version_id` 下改动 `_SYSTEM_CONTRACT` 或模板必须产生不同幂等键或明确冲突。
4. **MED-1 语义裁决需求**：零候选+未解决闭合的调用在运行级应合法还是保守拒绝，需要 Codex 拍板并同步两份合同文档与测试。
5. 残余风险（无发现但需持续盯防）：
   - 模型非确定性：重试产生不同候选集时“首个成功提交者赢”，身份按位置派生——可接受，但若未来允许“部分步骤重跑”，LOW-3 的检查点直返分支必须先补权威复核。
   - 仓储全表扫描在 5.5 规模下的性能（LOW-2）。
   - `raw_output_sha256` 双语义在审计真实模型输出时的取证缺口（MED-4）。

## Recommended Next Step

建议 Codex 按以下顺序处理（均可由实现方在同一工作树完成）：
1. 裁决 HIGH-1 方案（推荐：`max_pages_per_call` 冻结进 `job_payload` 并在 `_build_input` 透传；过渡期先在创建端拒绝非默认值）。
2. 裁决 HIGH-2 是否属 5.3 范围（我判断属：`FactNormalizationRunStatus` 与 `set_status` 即为此引入），若是则要求补取消/终败投影 + 聚焦测试。
3. 裁决 HIGH-3 的绑定形式（最小可行：`create_or_reuse_job` 强制 `prompt_version_id == evidence_normalizer_prompt_template_sha256(实际模板)`，模型配置以规范哈希冻结）。
4. MED-1 语义二选一并消除合同矛盾；MED-2/3 删除死代码与重复哈希域。

给 Codex 的有界问题（阻塞级别由高到低）：
- Q1：`max_pages_per_call` 冻结进 payload（方案 A）还是重建不再重新切片（方案 B）？未决前我推荐先落“创建端拒绝非默认值”护栏。
- Q2：运行状态 FAILED/CANCELLED 投影是否必须在 5.3 交付（而非推迟到 5.4 接线）？若推迟，P5-AC11 的“无永久处理中”在本切片只能以 Job 层终态为满足，需要用户认可该口径。
- Q3：零候选但逐页未解决闭合的调用，运行级应判合法闭合（豁免 `empty_calls`）还是维持保守 REJECTED→PARTIAL？这决定 5.4 资料缺口投影是否出现系统性假性告警。
