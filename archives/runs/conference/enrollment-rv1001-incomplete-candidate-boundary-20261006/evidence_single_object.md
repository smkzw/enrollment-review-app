Trellis SessionStart ✓（只读会商评审，期间不做任何写入）

# Conference Output: enrollment-rv1001-incomplete-candidate-boundary-20261006 - evidence_single_object

## Output

### 0. 阅读范围、方法与被纠正的定义名

只读代码审阅（未运行 shell / 测试 / 数据库 / 私有临床工件；所有结论为代码阅读证据，未执行验证）。实际读取：
- `app/agents/evidence_candidate_partition.py`（全文 269 行）
- `app/agents/evidence_normalizer.py`：`_hydrate_draft_output`、`EvidenceNormalizerRunner.run`、`parse_evidence_normalizer_output`、`_validate_normalizer_semantics`，以及被调用的 `EvidenceNormalizerDraftOutput` 合同校验段
- `app/domain/contracts/facts.py`：`ClinicalFactCandidateV2`（同时读到 `FactNormalizationRun/Call/GateResult`，因为是候选的存储消费合同）
- `app/services/fact_normalization_executor.py`：`_load_authority`、`_load_frozen_agent_config`、`_validate_call_checkpoint_replay`、`_validate_saved_output_matches`、`_validate_partition_replay`、`_rebuild_call_checkpoint_from_persisted`、`execute_call`
- `app/services/fact_normalization_job_service.py`：`create_or_reuse_from_source`、`create_or_reuse_job`（幂等键/载荷段）、`retry`
- 相邻调用方（每题限一个）：`evidence_normalizer_repair.py`（异常类）、`fact_normalization_replay_sources.py`、`page_review_sources.py:39-72`、`identifier_value.py`、`jobstore.py:retry_failed`、`fact_repositories.py:reopen_for_retry`、`deepseek_evidence_normalizer_transport.py`（小票/工件）

**定义名纠正（按要求记录）**：
| 上下文中的名字 | 实际定义 |
|---|---|
| `_hydrate_draft` | `_hydrate_draft_output`（evidence_normalizer.py:1464） |
| `_load_run_authority` | `_load_authority`（executor:384；另有 `_validate_authority`:391、`_load_frozen_agent_config`:398） |
| `_validated_checkpoint_output` | 无同名者；最接近的是 `_validate_call_checkpoint_replay`（executor:737）与 `_validate_saved_output_matches`（executor:861） |
| `_validate_partition_receipt` | `_validate_partition_replay`（executor:885） |
| `create_from_source` | `create_or_reuse_from_source`（job_service:292） |

---

### 1. 排名结论（按决策影响）

**F1（Q1 的直接阻点，高）**：规范值缺失当前**双重**地导致整答失败，`partition_source_local_candidates` 无法隔离它。
- `ClinicalFactCandidateV2.validate_candidate` 对 affirmed/negated 候选缺 `canonical_value` 抛普通 `ValueError("肯定或否定候选必须携带规范值")`（facts.py:298-299）；`_hydrate_draft_output` 的 `except ValidationError` 只把 `type == "numeric_unit_missing"` 转成 `EvidenceNumericUnitError`，其余统一降级为普通 `ValueError("…未通过合同校验…")`（evidence_normalizer.py:1557-1568）。
- 隔离循环只捕获 `EvidenceNumericUnitError`、`EvidenceDerivedSourceError`、`EvidenceSourceObjectError/{Context,Prospective}`（partition:234-254）。普通 `ValueError` 直接穿出 `partition_source_local_candidates`，被 `recover_source_local_candidates` 调用方的 `except (ValueError,…)` 记为 `candidate_partition_failure`（evidence_normalizer.py:2405-2409）。
- 第二个更早的阻点：`value_kind == "identifier"` 的候选在隔离循环**之前**就调用 `validate_identifier_value`，该函数对 `canonical != raw`（含 canonical 缺失）抛普通 `ValueError`（partition:132-135；identifier_value.py:8-20）。因此“只在 hydration 处打补丁”的方案对标识类候选仍会整答失败（见 §5 C1）。

**F2（恢复方案的最易漏点，高）**：隔离策略版本已折入运行冻结身份，改动隔离语义会**同时**威胁“复用六个成功”的通道。
- `CANDIDATE_PARTITION_POLICY` 常量被 `create_or_reuse_job` 折入 `effective_scope` 与幂等键（job_service:581-586），执行期 `_load_frozen_agent_config` 要求 payload 的策略字符串等于该常量、且 precondition 哈希与 `run.input_scope_sha256` 相互匹配（executor:418-426），否则 `PARTIAL_OUTPUT` 硬失败（"不能将旧作业改作新读取"）。
  - 推论：若把策略版本从 v3 升到 v4，**旧任务在当前代码下无法重试**（同一检查立即失败），六个成功也就无法经同 run 通道复用。若保留 v3，必须保证旧收据重建逐字节一致。
- `_validate_partition_replay` 会遍历**重建收据的全部键**与旧收据比较（executor:911-915）：`rebuilt.receipt` 若新增任何键，`receipt.get(新键)=None != value` → 旧收据判不可复用。所以最小补丁**不得新增收据键**（或必须做版本感知重放）。

**F3（能力缺口，中高）**："新受控请求身份引用旧成功输出"在代码中**完全不存在**，不是配置项。
- 跨 run 全代码无 `source_run_id`/`prior_run`/`historical_reading` 类字段（全仓 grep 无匹配）。
- `_rebuild_call_checkpoint_from_persisted` / `_validate_call_checkpoint_replay` 的期望身份元组含 `run_id`（executor:980-992、757-774），新 run 复用旧 call 行会 `CALL_IDENTITY_CONFLICT`。
- `FactNormalizationCall.reading_method` 枚举只有 `model_response / adapter_response / retained_pending`（facts.py:832），且 `candidate_partition_sha256` 的合同校验要求 `reading_method == "model_response"`（facts.py:857-858）。因此“历史重放 + 局部保留”在当前合同下**无法合法表达**，只能伪装成 `model_response` 或 `adapter_response`——正是提案要禁止的。

**F4（已实现的诚实通道，中）**：同 run 重放入口存在且完整，但会改动运行/步骤状态。
- `execute_call` 有两条复用路径：`context.last_checkpoint`（executor:1151-1179）与步骤检查点缺失时 `_rebuild_call_checkpoint_from_persisted`（executor:1180-1203）；后者文档明确“不得为同一调用再次消耗模型”（executor:964-970）。两路都经 `_validate_call_checkpoint_replay`：权威仍有效、run 权威一致、call 身份四元组一致、读取方式/原答哈希/候选清单/未解决项清单一致、`validate_replayed_sources` 来源复验、文字核对复现（executor:748-820）。
- 人工入口：`FactNormalizationJobService.retry` → `JobStore.retry_failed`（只把失败步骤置回 queued，保留已完成步骤；jobstore.py:1248-1279）→ `reopen_for_retry`（FAILED/CANCELLED→RUNNING；fact_repositories.py:348-365）。
- 代价：`retry_failed` 会清空失败步骤与作业级 `error_code/error_classification`（jobstore.py:1259-1267），运行状态由 FAILED 转 RUNNING。这是“是否改动旧终态”的边界问题，需 Codex 裁定（见 §8 D1）。
- 减配提示：`validate_replayed_sources` 在 `payload.page_review_coverage_id` 为空时**直接 return**（replay_sources.py:12-14），此时复用成功的“来源复验”主要靠 call 四元组与 authority 一致性，不含逐候选原件绑定复验。

**F5（闭包与消费者，中）**：隔离闭包是**按显式 id 引用**传播的，不追语义依赖；且“无合法事实可留”时整答仍失败。
- 用药孤儿闭包（fact 无剩余 exposure 覆盖→连带隔离）见 partition:204-216；事件/暴露依赖隔离见 217-219；分类清单只过滤 `rejected`（223-224）。该方向与草稿合同 `exposure_refs == actual_refs`（evidence_normalizer.py:426-432）自洽。
- 危险面：任一**全局关系不变量**（重复事件、分类不完整、暴露未闭合）在重放 `validate()` 时以普通 `ValueError` 抛出 → 整答失败；这是设计使然（不可替模型选一份），但必须在补丁说明中列为“仍须整拒”。
- 残余语义风险：与缺值候选**语义相关但无 id 引用**的兄弟项不会被连带隔离（例如某事实的解读实际依赖被隔离候选的上下文），会以“合法兄弟”继续存在。这是建议里必须写明的已知缺口，不是当前代码缺陷。

**F6（实现陷阱，中）**：新异常类**不得**继承 `EvidenceNumericUnitError`。隔离循环的数字单位分支有精确类型判定 `type(exc) is not EvidenceNumericUnitError`（partition:234-235），子类会被 `raise` 重新抛出；runner 的 `isinstance(...)` 分派（evidence_normalizer.py:2542）又会把它送进 `terminal_schema_failure`，随后在 partition 内自爆成 `candidate_partition_failure`。必须新增独立类 + 独立 catch + 显式 runner 分派（见 §5 C2）。

---

### 2. Q1：缺值候选能否沿既有局部隔离保留为“来源待核”

**结论（推荐 + 证据）**：可以，但**不是现状**，且必须是“有界的候选级值形态失败”而不是“任何校验失败都可隔离”。
1. 缺 `canonical_value` 属于“草稿结构完整、身份完整、来源绑定已过检”的候选级值形态失败——正是数值单位缺失（已可隔离）的同类。当前只差一个类型化、带 candidate_ref 的失败信号 + 一个 catch 分支。
2. **来源绑定可在隔离前检查**：`partition_source_local_candidates` 先用原始草稿字段构造 source_proxies（candidate_id / source_observation_refs / locator_ids / assertion_basis.qualifiers），在任何隔离动作之前调用 `validate_accepted_candidate_sources`（partition:143-151），并对**将被隔离的项同样执行**（设计注释：删除不能隐藏畸形答案，partition:74）。此外 102-105（locator ⊆ 冻结输入、身份非空）、118-131（requirement ⊆ 冻结、观察引用非空且不重复）、136-142（断言依据与另处来源 locator ⊆ 候选 locator）都在隔离前完成。
3. **精确保留 locator 与依赖闭包**：`retained_questions` 为每个被隔离项（含连带隔离的事件/暴露）生成带 `affected_pages/affected_locator_ids/affected_observation_refs` 的未解决项（partition:179-198），收据还保留整份 `original_draft`（partition:262）。被隔离候选不会进入 `output.fact_candidates`，因此不会成为 `FactNormalizationCandidateRecord`，也不可能被发布为事实（executor:1387-1403、1433-1471 只持久化 `final_output` 的候选）。这一点支持提案“绝不作为 adopted fact”的前提。
4. **必须仍然整拒的全局故障**（补丁不得稀释）：
   - 身份/结构：非 `phase5/normalizer-draft/v5`、顶层或候选未知字段、重复 JSON 键、JSON 截断/Markdown 包装、结构 schema 任一错误（partition:70-79；repair.py:55-60；parse:1640-1656）；
   - 全局身份唯一性：跨三类集合的 `candidate_ref` 重复（116-117）、未解决项观察引用重复（80-83）；
   - 来源/范围：locator 越界、来源语义白名单之外、另处来源越界、requirement 越界、来源绑定失败（102-108、118-131、136-142、143-151、152-154）；
   - 关系闭包：派生引用不完整（155-160）、用药分类不完整/重叠（161-175）、重放时草稿合同要求的“同一时刻重复事件”“暴露未闭合”（evidence_normalizer.py:352-361、426-432）；
   - 运行身份：run/call/logical_document/page 一致性（parse:1754-1780）。
5. **消费方四类情形**（connected consumers）：
   - **常规**：affirmed 数值事实有值无单位 → 已是 `EvidenceNumericUnitError` → `numeric_unit_missing` 未解决项（既有先例，可作新补丁的模板）。
   - **危险**：affirmed/negated 事实**有单位、有断言依据、来源绑定合格，但缺规范值**。若误判为可“采用”会产生无来源的规范值；正确处置是隔离。若该事实在 `actual_exposure_fact_refs` 中，孤儿闭包会连带隔离其事实（partition:204-216），必要时整答拒留（255-256）；若暴露仍在而分类清单与事实不一致，重放的草稿合同会以普通错误整拒（426-432）——不会静默产生自相矛盾的档案。
   - **同义陷阱**：`value_kind="identifier"` 的同一缺失在**预检阶段**就整答失败（partition:132-135），比正文候选更早、更硬；补丁必须同源处理，否则同类失败两种命运。
   - **损坏**：原答损坏（截断/重复键/未采信观察/定位与观察页不一致）一律整拒，不进入隔离（partition:75-79、149-151；page_review_sources.py:57-72）。

---

### 3. Q2：旧成功范围合法恢复的最小边界

**存在的能力（已实现，同 run）**
- 六个成功调用（SUCCEEDED call 行 + 251 候选）可经 `retry(job_id)` 同 run 重放：已完成步骤保留，失败步骤回到 queued；执行期对每个已成功调用走 `context.last_checkpoint` 或 `_rebuild_call_checkpoint_from_persisted`，**不再消耗模型**，并以 `_validate_call_checkpoint_replay` 做当前复验；`apply()` 不重放（executor:1202-1203 直接返回检查点），旧 call/候选/未解决项行与哈希保持不变（executor:1446-1471 的等值即幂等检查是防冲突而非改写）。
- 七个失败切片没有已持久化的成功 call 行，`_rebuild_call_checkpoint_from_persisted` 返回 None，重试会**真实调用一次模型**（executor:1204-1334）。这是“新读取”，不是历史采用，因此不需要历史来源伪装；但其**原始失败回答文本已被保留**：传输小票 `raw_text` + `request_sha256` + `request_artifact_sha256` 在 `finally` 中写入工件（transport:395-424、481-500；executor:1245-1267 的 `record_request/record_completion`），失败工单另存 `evaluation_manifest`（executor:1336-1345）。这为将来的历史重放提供了真实材料，但目前没有一等公民字段。

**不存在的能力（跨 run 历史采用，未实现）**
- 新 run（新 `run_id`）无法引用旧 run 的 call 行（身份元组含 run_id；executor:757-774、980-992）；无历史来源策略字段/载荷哈希折叠；`reading_method` 无历史值；局部保留证明被合同绑定在 `model_response` 上（facts.py:832、857-858）。因此“新受控请求身份引用旧成功输出”必须**新建生产者/存储/消费链**，不能靠既有开关或 `adapter_response` 伪装（`adapter_response` 是确定性适配器读取方式，executor:1281-1303，用它承载旧模型输出会绕过“证明是模型读取”的合同意图）。

**最小诚实设计（推荐顺序）**
- **P2（首选，零新增能力）**：修复隔离语义（P1）后，对**原任务**执行一次受控 `retry`。六次成功经既有重放通道复验复用；第七切片以新模型读取推进（此时新隔离分支生效）。不伪造历史读取、不改旧 call 行与哈希。唯一边界：重试会重开 run 并清空失败步骤错误标注（jobstore:1259-1267；fact_repositories.py:348-365），需 Codex 明确这不算“改动旧终态”（见 §8 D1）。
- **P3（仅在 P2 不可用时才建）**：新 run + 显式历史读取来源。最小改动面：
  1. 生产者：`create_or_reuse_from_source` 增历史来源入参（旧 run/call、旧 `input_sha256`、`raw_response` 工件 sha、`request_sha256`、旧策略与 precondition），按现有 `*_precondition` 模式折入 `effective_scope` 与幂等键（job_service:524-596 模式）、写入 payload 与 submitted_hash；
  2. 存储/合同：`reading_method` 增加显式历史值并规定其与 `candidate_partition_sha256` 的关系（放宽 facts.py:857-858 需有替代证明，不能简单删除）；call 合同携带历史来源哈希；
  3. 消费：`_load_frozen_agent_config` 增加历史分支校验（新，仿 executor:418-426）；`execute_call` 在读模型之前增加历史分支：按 sha 取工件、核验旧封套的 job/step/run/call/input/request/body 哈希，再以当前代码做 `recover_source_local_candidates`/`validate_evidence_normalizer_output`，并复用 `_validate_saved_output_matches` 式当前复验；未解决项继续进入待核消费，不得当作已采信。
  4. 未建成前的诚实替代：若权威修订已变更导致旧 run 不可重放，则**新 run 全量重读**是唯一诚实选项；不得以历史采用之名规避。
- 禁止项核对：`adapter_response` 冒充读取方式（禁止，见上）；改旧 call/候选终态与哈希（禁止；P2 不动 call 行）；把历史重新标注为当前读取（禁止；P3 必须显式 `reading_method`）；把旧策略收据在新代码下静默重放（F2 已证明会失败或被误判，需版本感知或保持 v3 语义）。

---

### 4. 全局故障与来源绑定小结（对照提案三问）

| 提案问题 | 答案 | 决定性引用 |
|---|---|---|
| 类型化失败能否交给既有隔离器 | **不能现状**；可经最小补丁变成“能” | partition:234-254；evidence_normalizer.py:1557-1568 |
| 是否保留精确定位与依赖闭包为未解决 | 是（含 pages/locator/observation 与全部依赖项） | partition:179-198、200-226、257-268 |
| 独立有效兄弟是否不动 | 结构上不动；但语义相关兄弟不追闭包（残余风险） | partition:217-226；§1 F5 |
| 隔离前能否检查来源绑定 | 能，且对将被隔离项同样执行 | partition:74、102-108、132-151 |
| 全局故障是否仍拒绝 | 是，见 §2.4 清单 | partition:70-175；evidence_normalizer.py:352-432 |

---

### 5. 反例（counterexamples）

- **C1（同义不同命）**：`value_kind="identifier"` 且 `canonical` 缺失 → 在 partition:132-135 的预检即整答失败；只改 hydration 的补丁无效。
- **C2（继承陷阱）**：新异常继承 `EvidenceNumericUnitError` → partition:234-235 的 `type(exc) is not …` 精确判定直接 `raise`；runner:2542 的 `isinstance` 会先送它进 `terminal_schema_failure`，最终仍记为 `candidate_partition_failure`。必须独立类 + 独立分派。
- **C3（镜像失败）**：unknown 极性却携带值/单位（facts.py:292-296）同样以普通 `ValueError` 整答失败，说明这是“候选级值/极性形态”族，补丁建议按族定义白名单，而非只补一个字段。
- **C4（不可择优）**：同一检验同一时刻被拆成两条事件 → 必须整拒（evidence_normalizer.py:352-361），不得隔离其一。
- **C5（损坏）**：重复 JSON 键 / 截断 / Markdown 包裹 / 定位与采信观察不一致 → 整拒（repair.py:55-60；partition:75-79、149-151）。
- **C6（闭包回归）**：收据键集合若变动，旧收据重建比较必然失败（executor:911-915）；策略字符串若升版，旧任务重试在 `_load_frozen_agent_config` 即失败（executor:418-426）。

---

### 6. 最小补丁计划（建议；未执行）

**P1 隔离补丁（核心，最小面）**
1. `app/domain/contracts/facts.py:292-316`：将“肯定/否定候选缺规范值”等**候选级值形态**违规改为 `PydanticCustomError` 具名代码（仿既有 `numeric_unit_missing`），不改有效候选语义。
2. `app/agents/evidence_normalizer.py:1557-1568`：识别新错误代码，抛独立类型化异常（带 candidate_ref），其余合同失败保持普通 `ValueError`（全局拒绝）。
3. `app/agents/evidence_normalizer_repair.py:36-42`：新增独立异常类（**不继承**数值单位类）。
4. `app/agents/evidence_candidate_partition.py`：(a) 循环内新增 catch 分支，模式同 234-239，校验 candidate ⊆ `fact_refs - rejected`；(b) 修正 132-135 标识预检，使值形态失败可被隔离（来源逐字/绑定类失败保持整拒或映射到既有 SourceObject 族——Codex 决策）；(c) `retained_questions` 增专用 code 与诚实文案（既有 `code: str` 自由字段，无合同破坏，evidence_normalizer.py:436）；(d) **不新增收据键**；`CANDIDATE_PARTITION_POLICY` 保持 v3（否则按 F2 需版本感知重放）。
5. `app/agents/evidence_normalizer.py:2542-2551`：将新异常纳入“直接转 `terminal_schema_failure`”分派（避免消耗修复预算、避免诱导模型猜值）。
6. 验证（建议命令，未运行）：`pytest` 相关用例（partition / normalizer / executor / job_service），新增四类矩阵用例与“旧收据在新代码下重建逐字节一致”的回归。

**P2 恢复（不改代码）**：`FactNormalizationJobService.retry(job_id)` → 六次成功零模型重放 + 第七切片一次新读取。前置：权威仍为活动修订；`artifact_store` 已配置（partition 策略强制，executor:1132-1134）；策略字符串与收据键不变。

**P3 历史来源能力（本轮不建议实施）**：见 §3 P3 的生产者/存储/消费者最小改动清单；若实施，必须先写清证据合同（旧请求/主体/回答/输入 + 当前复验）与未解决消费语义。

---

### 7. 残余不确定性（未证实项）

1. 该失败 run 的权威修订是否仍活动、run 现为 RUNNING 还是 FAILED（决定 `retry` 是否走 `reopen_for_retry`，job_service:826-830）——本只读轮无法查库。
2. 六个成功是否走 `page_review_coverage_id` 路径（决定重放来源复验强度；replay_sources.py:12-14 早退）。
3. 第七切片的工件是否含 `raw_response.raw_text`（streaming GLM 路径按代码会写，但工件存储是否配置需实例态证据）。
4. 第七切片原答在**新隔离语义下**是否仍留有 ≥1 合法事实（partition:255-256 可能整拒）——未读原答，不能承诺。
5. 未读边界（不展开）：`execute_finalize` 全体与 `PatientProfileService.generate` 的未解决项消费、`_build_input`、`EvidenceNormalizerDraftOutput/EvidenceFactDraft` 全字段、`evidence_question_repair` 交互、文本核对投影、UI 待核计数、测试与既有应用数据。

---

### 8. 异议、决策点与给 Codex 的有界问题

**异议/O1（最高影响）**：提案把“旧成功复用”表述为需要新历史来源能力；代码事实是**同 run 重放已实现**，真正缺的只是**失败切片**的原答重放。若把两者混为一谈，会误建一套跨 run 采用机制，反而引入更高风险。建议路线：先 P1 + P2，把 P3 推迟到权威/策略确需变更时。
**异议/O2**：任何“升级隔离策略版本再复用旧 run”的隐含假定都与 executor:418-426 + 911-915 冲突。补丁必须显式选择：保 v3 语义（并证明旧收据逐字节可重建）或引入版本感知重放；不能两者都不做。
**异议/O3**：`validate_replayed_sources` 在无页级覆盖时早退；若本次六次成功属该路径，“当前复验”主要靠身份与输入哈希，报告与验收措辞不应过度声称来源级复验。

**决策点/有界问题（每问附理由与安全暂定路径）**
- **D1/Q1**：`retry` 会清空失败步骤错误标注并重开 run（jobstore:1259-1267；fact_repositories.py:348-365）。这是否违反“不得改旧终态”？——**为何重要**：它决定 P2 是否可用。**暂定安全路径**：若不允许，则只能走 P3 新 run + 历史来源（本轮未实现），或对第七切片做一次新 run 的重读而不采用旧原答。
- **D2/Q2**：`CANDIDATE_PARTITION_POLICY` 保持 v3 还是升 v4（+版本感知重放）？**为何重要**：升版会让旧任务在当前代码下无法重试。**暂定**：保 v3 + 不新增收据键，并在提交说明中论证“新分支只作用于过去必然整拒的输入，旧收据重建不变”。
- **D3/Q3**：标识类“原答逐字/绑定失败”应整拒还是映射到既有 SourceObject 可隔离族？**为何重要**：决定 C1 的修复边界与安全姿态。**暂定**：值形态隔离、逐字/绑定整拒。
- **D4/Q4**：是否先给一次“有界修复提问”让模型补值？**暂定**：否（猜值风险；与 `numeric_unit_missing` 先例一致，直接隔离）。
- **D5/Q5**：六次成功是否 `page_review_coverage_id` 路径、`artifact_store` 是否可用、第七切片原答是否仍处于活动权威？——这三项决定 P2/P3 的可执行性与复验强度，属于只读轮不可证实项，需 Codex 以实例证据确认。
