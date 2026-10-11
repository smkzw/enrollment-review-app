# Conference Participant Output: phase5-slice58-runtime-bootstrap-review-20260824 - general_pi_qwen38

## Boundary Check

- **工作目录约束**: 仅在 runner 提供的当前工作目录内只读审查，未读取/修改授权 workspace 外生产路径。`context/phase5-slice58-runtime-bootstrap-review-20260824_conference_context.md` 与 `plans/codex_main_venue_phase5-slice58-runtime-bootstrap-review-20260824.md` 初始可读集之外的主动取证均限制在任务列出的 source-of-truth (`app/config.py`, `app/api/v2/*`, `app/services/fact_normalization_*`, `frontend/src/api/fact-normalization/*`, `frontend/e2e/phase5-real-acceptance*`, `app/agents/evidence_normalizer*`, `app/domain/contracts/evidence_normalizer*`)。
- **只读边界**: 未修改任何源文件、测试、报告或原始临床文件；未执行写入类工具；所有结论来自静态读取与 grep/glob 交叉验证。
- **验收权边界**: 未执行最终视觉/PPT/浏览器/临床/法规验收，未声称通过/不通过最终裁决；浏览器/e2e 结论仅引用 `frontend/e2e/phase5-real-acceptance-support.ts` 的编排逻辑与断言，未启动真实浏览器。
- **模型路由边界**: 使用本 Pi 会话独立全量推演，未读取其他参会者输出；输出写入由 runner 托管 (`runs/conference/.../general_pi_qwen38.md`)，本轮未自行持久化。
- **证据时效**: 以 worktree 当前未提交快照为准（`git status` 显示 277 未提交变更），未运行测试套件作为验收证据，仅核对测试清单意图。

## Independent Work Product

### 0. 假设与挑战立场

初始计划（`plans/codex_main_venue_*.md` 全为 TODO）与 conference_context 的 `Scope:TODO` 表明 5.8 的“闭环充分性”尚未被 Codex 分解为可验证的验收清单。默认信任“注册+精确选择+前后端合同+恢复+真实模型+方案保留+定位”均已闭合是危险假设。本审查以证伪视角逐项寻找**可重现的伪通过路径**——即某个缺陷能让失败/空/陈旧/虚构结果看起来像成功。

### 1. 按严重度排序的可验证问题（均可复现）

#### S0-Critical — 允许伪通过，直接违背 P5-AC10/AC11

**S0-01 真实模型可用性在启动时未验证，配置错误延迟到运行时重试循环**
- **现象**: `EVIDENCE_NORMALIZER_PROVIDER=deepseek` 且 `DEEPSEEK_API_KEY=""` 时，`register_evidence_normalizer_runtime_config` 与 `select_registered_evidence_normalizer_config` 均通过（`app/services/fact_normalization_command_service.py:107-121` 的 `_is_usable_model_config` 仅调 `validate_evidence_normalizer_model_config` 检查 provider/effort/max_tokens/temperature，不检查密钥），但 `app/agents/deepseek_evidence_normalizer_transport.py:150-152` 在 `evidence_normalizer_transport_from_model_config` 时才 `raise ValueError("DeepSeek 语义服务尚未配置")`，执行器将其包装为 `StepFailure(retryable=True, TRANSPORT_FAILED)`，任务进入带退避的重试直至 `failed_final`。用户看到 `queued/running` 长时间无终态，`frontend/src/features/fact-normalization/useFactNormalizationJob.ts:242-254` 的轮询不报警，e2e 在 `allowLiveModel` 未显式检测密钥缺失时会超时而非明确报告“配置缺失”。
- **伪通过风险**: 一个完全不可用的模型配置会让“发起整理”看似成功（201 + job_id），但永远达不到 P5-AC10 要求的“结构化候选经 Gate 后发布”。离线开发者或 CI 若未设置 `PHASE5_REAL_ACCEPTANCE_ALLOW_LIVE_MODEL=1` 会误以为“不需要真实模型”。
- **复现**: `EVIDENCE_NORMALIZER_PROVIDER=deepseek` + 空 key → `POST /api/v2/subjects/{s}/review-episodes/{e}/fact-normalization-jobs` → 201；查询 `GET /api/v2/jobs/{id}` 长期 `running`，最终 `failed_final`，但启动阶段无任何错误信封。
- **修复**: 在 `_is_usable_model_config` 与 `validate_evidence_normalizer_model_config` 中增加 provider 级密钥可达性探测的**同步快检**（仅检查空/缺，不做网络探测）并在 `app/api/v2/app.py:130-132` 的 lifespan 中对当前登记配置执行一次 `evidence_normalizer_transport_from_model_config` 试建（不发请求），失败即 `AppFactNormalizationConfigError` 阻断启动；或至少将 transport 创建失败映射为 `422` 而非 `retryable` 以便前端立即显示“本机模型服务未配置”。

**S0-02 运行时配置“精确选择”在 lifespan 精确路径下掩盖多登记漂移，另一条扫描路径仍会随机失败**
- **现象**: `app/api/v2/app.py:198-202` 将启动时 `register_evidence_normalizer_runtime_config` 的返回值以 `registered_config` 注入 `FactNormalizationCommandService`，后续 `select_registered_evidence_normalizer_config(session, registered_config=...)` 走精确加载分支（`371-383`），即使 DB 中残留旧 `ModelConfigRecord` / `PromptVersionRecord`（例如修改过 `EVIDENCE_NORMALIZER_TEMPERATURE` 导致旧 id 仍在），也**不会**触发“多份可用配置”的失败。相反，任何以 `registered_config=None` 实例化的服务（测试、脚本、未来重构）会走扫描分支 `384-442` 并因 `len(marked)>1` 立即 `AppFactNormalizationConfigError`。同一套 DB 在两条路径下行为不一致，说明“唯一性”不变量未被存储层约束，仅被调用方是否记得传参保证。
- **伪通过风险**: 运营人员改环境变量后重启，旧配置成为孤儿但系统看似正常；数周后某个未传参的后台任务或单测突然全量失败，难以定位为“配置漂移”。更严重的是 `EVIDENCE_NORMALIZER_TEMPERATURE` 等参数的变更会产生新 `model_config_id` 但旧行仍被视作“可用”，精确路径却永远选中新行，旧数据仍参与 `tests/v2` 的全表扫描断言，但生产不受控。
- **复现**: 正常启动一次 → 改 `EVIDENCE_NORMALIZER_TEMPERATURE=0.5` → 重启 → `select * from model_config_records` 得到两行均满足 `_model_marked_for_normalizer`；`select_registered_evidence_normalizer_config(session)`（无参）抛多配置错误，但 `app.state.fact_normalization_command_service.create_or_reuse` 仍成功。
- **修复**: 在 DB 层增加 `agent_node=EVIDENCE_NORMALIZER` 的**唯一活跃**约束或在 `register_evidence_normalizer_runtime_config` 中对旧活跃配置做显式归档/失效标记；同时让无参扫描分支在发现 >1 可用时不直接抛通用中文错误，而是返回“检测到孤儿配置 {ids}，请执行 `DELETE` 或重启前清理”的可操作信息，并在 lifespan 启动日志中打印当前登记的 `prompt_version_id/model_config_id` 供审计。

**S0-03 代表病例原件定位验收的 e2e 断言仅覆盖“存在一个可解码 bbox”，不覆盖 P5-AC02/AC12 要求的全类别逐项回源**
- **现象**: `frontend/e2e/phase5-real-acceptance-support.ts:943-995` 对定位的验证为：`evidenceButtons.count()>0` → 点击直到出现 `pageImage.naturalWidth>0` 且 `selectedBox` 与图片有交集之一即 `verifiedLocator=true`。PRD P5-AC02（任一关键事实 3 次内可达原文）与 P5-AC12（人口学/疾病/MH/CM/检验/日期/冲突/溯源逐事件核对）要求的是**分泳道抽样**，而编排未断言：人口学、目标疾病、症状、MH、CM、检验等每个泳道至少一条可定位；冲突组并列、溯源提醒的弱来源标记是否存在。
- **伪通过风险**: 一个仅抽到“收缩压”但丢失“糖尿病否认”“用药暴露”的模型输出仍能让 `flow.source_locator` 通过，因为只要有一个 bbox 几何正确即算 `pass`。这是 slice5.3 探针已暴露的“Schema 合法 ≠ 语义闭合”的同类问题在 5.8 被 e2e 再度掩盖。
- **复现**: 构造合成输入让模型仅返回一个事实候选 → 发布后 `PatientProfile` 仍 `succeeded` → e2e 仍 `verifiedLocator=true` → `flow.patient_profile` 记录 `observed_only` 而非 `fail`。
- **修复**: 在 `stepPatientProfileAndLocator` 中对 `config.casesFile` 声明的关键事实类型清单（或至少对 13 泳道中 P0 类别）逐类定位：`demographics`, `targetDisease`, `medicationExposure`, `labOrScore` 各取首条，要求每条均满足 `naturalWidth>0` 且 bbox 相交；对弱来源事实额外断言界面出现“溯源提醒”文案。缺失类别即 `disposition: fail`，而非 `observed_only`。

#### S1-High — 闭环脆弱，需人工干预或延迟失败

**S1-01 前后端合同丢精度：`run_id` 在命令响应中被前端静默忽略**
- **证据**: 后端 `app/api/v2/fact_normalization_schemas.py:21-27` 的 `FactNormalizationSubmitDTO` 必含 `run_id`；`app/services/fact_normalization_job_service.py:416-427` 将 `run_id` 写入 `job_payload`；前端 `frontend/src/api/fact-normalization/factNormalizationViewModels.ts:137-152` 的 `decodeFactNormalizationCommand` 仅校验 `job_id/created/state/state_label/recovery_action`，不读取 `run_id`，且 `FactNormalizationCommandView:47-53` 接口根本没有 `runId` 字段。Decoder 对多余字段不抛错（`record()` 仅检查必需字段），属于 lossy contract。
- **风险**: 后端若因幂等复用返回旧 `job_id` 但新 `run_id`（或相反），前端无法察觉；审计链“job ↔ run ↔ authority”在浏览器层断裂。测试 `tests/v2/api/test_fact_normalization*.py` 不会捕获该漂移，因为前端单测使用 fake repo 而非真实 HTTP。
- **修复**: 二选一保持合同对称：要么 `FactNormalizationSubmitDTO` 去掉 `run_id`（若确定前端永不需要），要么前端 `CommandView` 增加 `runId` 并在 `decode` 中强制校验 `requiredString(row.run_id)`。推荐后者，因 `run_id` 是后续 `GET /patient-profiles?run_id=` 回放的关键审计键。

**S1-02 客户端幂等键与服务端权威幂等键语义脱节**
- **证据**: 前端 `frontend/src/api/fact-normalization/factNormalizationHttp.ts:82` 以 `idempotency_intent` 发送 `input.idempotencyKey`；后端 `app/services/fact_normalization_command_service.py:515` 显式 `del idempotency_intent` 并注释“禁止影响权威/配置选择或服务端幂等键”，`app/services/fact_normalization_job_service.py:341-349` 的真实幂等键由 `fact_run_idempotency_key(authority, prompt_version_id, model_config_id, input_scope_sha256)` 派生。前端 `useFactNormalizationJob.ts:278-282` 仍为每次 `start` 生成 `profile-organize:${episodeId}:${uuid}` 并存 `idempotencyRef`。
- **风险**: 开发者误以为修改客户端 key 可强制创建新运行，实则只有证据快照/配置/范围变化才生效，导致“刷新后仍看到旧整理结果”被误判为 bug。更重要的是，e2e 的 `BrowserObservationSink` 无法通过客户端 key 关联到服务端 `run_id`。
- **修复**: 前端注释与 `FactNormalizationRequest` 的 `description` 已说明“不参与权威派生”，建议在 `startFactNormalization` 的错误提示中当检测到服务端返回 `created=false` 时显式文案“已复用既有整理任务（证据未变化）”，而非“创建成功”。文档层面在 `implement.md:5.3` 门槛中补充该语义。

**S1-03 任务恢复仅收敛 `cancelled/failed_final`，孤儿 `running` 运行可能永久悬挂**
- **证据**: `app/services/fact_normalization_job_service.py:536-555` 的 `recover_fact_normalization_runs` 通过 `join(JobRecord, job_id)` 仅处理 `running` run 且 `job.state in (cancelled, failed_final)` 的情况；既不处理 `failed_retryable`（等待重试）也不处理 `JobRecord` 已被物理删除或 `run.job_id is NULL` 的孤儿（虽正常事务中不应出现，但 crash 在 `repo.create_or_reuse(run)` 与 `store.create_job` 之间仍可能留下）。`app/workflow/recovery.py:33-54` 的通用 `run_startup_recovery` 会把过期租约标记为 `recovering` 并重排，但不负责将 `FactNormalizationRunStatus.RUNNING` 同步为 `FAILED`。
- **风险**: 若 JobRunner 在 finalize 期间进程被杀且租约未过期，重启后 `FactNormalizationRun` 保持 `running`，而对应 `JobRecord` 仍 `running`，既不会被 `recover_fact_normalization_runs` 改写，也不会被前端轮询识别为失败，导致 P5-AC11 “无永久处理中”被违背。前端 `useFactNormalizationJob.ts:232-254` 仅在 `completed/failed_*` 时停止轮询，`running` 会无限 `setInterval`。
- **修复**: 扩展 `recover_fact_normalization_runs` 对所有非 `cancelled/failed_final` 的过期 `running` run，在 `run_startup_recovery` 之后的 `recovered_jobs` 列表中若发现对应 run 仍 `running` 则置为 `FAILED` 并记录 `payload_sha256` 校验失败原因；或将 run 的 `status` 投影改为直接由 `JobRecord.state` 派生（`project_fact_normalization_run_status` 已在 `on_cancelled/on_failed` 回调中处理，但缺少对 `recovering` 的处理）。

**S1-04 自动方案信息（Protocol/RuleSet）在输入冻结中的保留依赖重建而非持久，可被新发布掩盖**
- **证据**: `app/domain/contracts/facts.py` 的 `FactAuthority` 含 `protocol_version_id/rule_set_id/rule_set_revision`；`app/services/fact_normalization_source_adapter.py:76-130` 的 `_load_normalizer_context` 每次从 `SourceDocumentMetadataRevision` 与 `EvidenceRequirement`（按 `authority.rule_set_id/revision`）重建 `related_requirements`；`app/services/fact_normalization_executor.py:342-360` 的 `_build_input` 每次执行前重建而非读取 job payload。Job payload 的 `authority` 已冻结，但 `related_requirements` 未持久，仅以 `input_sha256` 间接约束。
- **风险**: 若在 job 排队期间发布新 `RuleSetRevision` 但 `ReviewEpisode` 仍指向旧 revision，executor 重建时会使用旧 revision 的 requirements（正确），但 e2e 的 `stepRealNormalizer:850-879` 在 `build_activate` 后立即检查 `profile`，未断言 profile 的 `authority.rule_set_revision` 等于激活时的 `CompleteEvidenceProcessingRevision` 对应的 rule_set_revision，无法证明“档案显示的方案期别与整理时的方案一致”。
- **修复**: 在 `PatientProfileService` 生成的 `profile.revision` 中已冻结 authority（`app/services/patient_profile_service.py:88-...`），e2e 应在 `flow.patient_profile` 后对 `GET /api/v2/patient-profiles/{subject}?episode={id}` 返回的 `authority.protocol_version_id` 做精确等值断言，而非仅 `not.toContainText`。

#### S2-Medium — 可运维性与一致性

**S2-01 Evidence Normalizer 未使用共享 `OmlxGateClient`，并发无背压**
- **证据**: `app/api/v2/app.py:225-233` 的 `EVIDENCE_PROCESSING_JOB_TYPE` 传入 `OmlxGateClient(owner="phase4-evidence-ocr-v2")`，而 `FACT_NORMALIZATION_JOB_TYPE:231-233` 仅 `FactNormalizationExecutorConfig(session_factory)`，无 gate。`app/services/omlx_gate.py:131-...` 的租约机制因此不适用于事实整理，若批量触发多个受试者整理（如 5.8 的两例 D001+MG-K10 并行），本地 `oMLX` 的固定 `port` 端点会被并发击穿。
- **修复**: 为 normalizer 增加独立 gate owner（如 `phase5-fact-normalizer`）或复用同一 gate 但区分 `kind`，并在 `app/config.py:78-93` 增加 `EVIDENCE_NORMALIZER_GATE_TTL` 配置。

**S2-02 前端本机恢复键未绑定权威，证据版本变化后仍复用旧 job_id**
- **证据**: `frontend/src/api/fact-normalization/endpoints.ts:25-27` 的 `factNormalizationJobStorageKey(reviewEpisodeId)` 仅以 `reviewEpisodeId` 为键；`frontend/src/features/fact-normalization/useFactNormalizationJob.ts:204-230` 在切换 episode 时读取旧 `job_id` 并 `getFactNormalizationJobStatus`，即使该 job 对应的 `input_scope_sha256` 已与当前 `CompleteEvidenceProcessingRevision` 不一致，也仅靠 `profileStale`（来自另一个 profile API 的布尔）决定是否显示 `stale`。若 profile API 尚未返回，UI 会短暂显示旧 `completed` 的成功态。
- **修复**: 存储时一并持久 `input_scope_sha256` 或 `evidence_snapshot_v2_id`，恢复时比对当前 episode 的 active revision，不一致立即显示“资料已更新，需重新整理”而非旧成功态；或在 `GET /jobs/{id}` 的响应中增加 `authority` 摘要供前端比对。

**S2-03 oMLX provider 的 `/v1` 后缀拼接未做幂等 `//` 归一化，DeepSeek 的 `response_format: json_schema` 在 oMLX 路径下硬编码**
- **证据**: `app/agents/deepseek_evidence_normalizer_transport.py:162-181` 对 oMLX 强制 `base_url += "/v1"` 而不检查已有后缀是否含 `//v1/`；且 `response_format` 固定为 `json_schema` 的 `evidence_normalizer_output`，但 `app/config.py:38` 的 `OMLX_BASE_URL` 来自 `~/Library/Application Support/oMLX/config.json` 的 `port`，不同版本 oMLX 可能不支持 `json_schema` 严格模式。
- **风险**: 低，但属于运行时配置精确选择的一部分；若 oMLX 升级后不支持该 schema 严格模式，整理任务会以 `PARTIAL_OUTPUT` 失败却被前端显示为“资料不完整”而非“模型不支持”。
- **修复**: 将 `response_format` 作为 `ModelConfigContract.parameters.get("response_format")` 的可配置项，并在 `_is_usable_model_config` 中校验其枚举。

### 2. 对 5.8 闭环充分性的总体判断

- **运行配置注册与精确选择**: 当前实现做到了“内容寻址的不可变追加 + 启动时精确加载”，能防止“模型/提示词被静默替换后复用旧候选”的伪通过，但**密钥/可达性未纳入可用性判断**且**多登记的孤儿检测仅在扫描路径生效**，导致配置类伪通过仍可能。需补密钥快检与孤儿归档。
- **前后端合同**: HTTP 层的 `FactNormalizationRequest/SubmitDTO` 与前端 `decode*` 已做到严格校验（`extra="forbid"` 在后端，`requiredField` 在前端），但** `run_id` 的 lossy 解码**与**客户端幂等键被丢弃**属于合同漂移，虽不直接导致临床错误，但削弱审计。
- **任务恢复**: 持久 Job 的 `lease + checkpoint + write-fence`（`app/workflow/jobstore.py:538-579` 的 `acquire_step_commit` + `complete_step_after_commit_fence`）已能防止“浏览器关闭后丢失进度、重复执行产生重复事实”，符合 P5-AC11 前半；但**孤儿 `running` run 的收敛缺口**仍可能产生永久悬挂。
- **真实模型可用性**: 最小探针 (`slice53`) 的“定位摘要入参 + 系统字段回填”修正已生效，且 `app/agents/evidence_normalizer.py:329-341` 的 `evidence_normalizer_prompt_template_sha256` 将提示词版本与内容哈希绑定，防止提示词漂移。但**启动时不做传输试建**，真实模型离线被延迟到执行期。
- **自动方案信息保留**: `FactAuthority` 与 `related_requirements` 的输入哈希链已保证同一 `input_scope_sha256` 变化会触发新幂等键，防止方案切换被静默复用；但 e2e 未断言该保留。
- **代表病例原件定位验收**: 后端已做到 `fact_evidence_locator_links` 仅引用 `EvidenceLocatorArtifact` 且 `PAGE_ONLY` 不得支撑断言（`app/domain/contracts/evidence_normalizer.py:120-125`），但 e2e 的单样点几何相交验收不足以证明分泳道全覆盖，存在以偏概全的伪通过。

## Evidence And Assumptions

**直接证据（文件/行号均已读取）:**
- `app/config.py:78-93` — `EVIDENCE_NORMALIZER_*` 独立于 `DECONSTRUCT_*`，默认 `provider=omlx, model=Qwen3.8-27B-oQ8e-fp16-mtp`。
- `app/services/fact_normalization_command_service.py:107-139, 262-330, 332-442, 515` — 可用性判断、不可变注册、精确/扫描两分支、客户端 intent 丢弃。
- `app/services/fact_normalization_job_service.py:253-470, 536-555` — 幂等键派生、持久调用/步骤声明、恢复仅处理 `cancelled/failed_final`。
- `app/services/fact_normalization_executor.py:643-994` — 双阶段执行、checkpoint 复用校验、page closure 四层校验、`TRANSPORT_FAILED` 可重试、`EMPTY_OUTPUT` 不可重试。
- `app/agents/evidence_normalizer.py:79-84, 86-117, 183-213, 220-341` — 支持 provider 集合、模型配置校验、draft 仅语义草稿、模板哈希。
- `app/agents/deepseek_evidence_normalizer_transport.py:142-182` — 仅 `deepseek`/`omlx` 合法，deepseek 需 `DEEPSEEK_API_KEY`，omlx 强制 `/v1` 与 `json_schema`。
- `app/api/v2/app.py:101-203, 231-233` — lifespan 中 `register_evidence_normalizer_runtime_config` 与 gate 仅用于 OCR。
- `app/api/v2/fact_normalization.py:41-73` 与 `fact_normalization_schemas.py:12-27` — 薄 DTO、`idempotency_intent` 可选。
- `frontend/src/api/fact-normalization/*` — `endpoints.ts:7-27`, `factNormalizationHttp.ts:72-111`, `factNormalizationViewModels.ts:47-181`, `useFactNormalizationJob.ts:124-341` — 前端命令/恢复/轮询/本地存储。
- `frontend/e2e/phase5-real-acceptance-spec.ts:1-60` 与 `phase5-real-acceptance-support.ts:761-995` — 真实验收编排、fixture 陷阱、`naturalWidth>0` + bbox 相交即通过。
- `app/services/patient_profile_service.py:1-60` — Profile 仅基于已发布 v2 实体，`stale` 派生。
- `app/workflow/recovery.py:33-63` 与 `app/workflow/jobstore.py:538-579` — 启动恢复与写栅栏。

**推断（未直接执行，仅静态分析）:**
- `FactAuthorityValidator.validate` 会校验 `episode_revision` 的递增，但未逐行追踪其对 `protocol_version_id` 的校验路径；假设其覆盖但未 100% 证实。
- `ModelConfigRecord` 的物理表结构未读取，假设 `AppendRepository.save` 为 `INSERT ON CONFLICT DO NOTHING` 语义，孤儿行不会自动清理。
- 真实 oMLX 端口下的模型 `Qwen3.8-27B-oQ8e-fp16-mtp` 在当前工作站是否已安装、是否支持 `json_schema` 严格输出为外部不确定性，未做网络探测。

**不确定性:**
- `runs/conference/phase5-slice53-independent-check/general_pi_qwen38.md` 中提及的 `EVIDENCE_NORMALIZER_PROVIDER` 历史默认值与当前 `Qwen3.8-27B` 是否一致，属跨切片漂移不确定。
- `PHASE5_ISOLATED_DATASET_ROOT` 指向的 D001/MG-K10 原始数据集结构未在本只读审查中打开，无法验证其文件类型/页数与 `max_pages_per_call=20` 切片边界的交互。

## Risks, Gaps, And Verification Needs

| 风险 | 触发条件 | 后果 | 最小复核试验 |
|---|---|---|---|
| R1 密钥缺失的 deepseek 配置通过启动 | `DEEPSEEK_API_KEY` 未设 + `provider=deepseek` | 任务永久重试，前端无明确“配置错误” | 设空 key 重启，断言 `POST` 立即 422 而非 201 |
| R2 孤儿配置导致扫描路径偶发失败 | 改过 temperature/max_tokens 后未清理 DB | 某条测试/脚本无参调用突然抛多配置错误 | `SELECT count(*) FROM model_config_records WHERE parameters->>'agent_node'='evidence_normalizer'` 后改配置重启，分别调用两分支 |
| R3 单 bbox 通过掩盖分泳道丢失 | 模型仅产 1 事实但 e2e 仍 pass | P5-AC12 在 5.8 被伪通过 | 在合成输入中只留 1 候选，跑 e2e 观察 `verifiedLocator` 是否仍 true |
| R4 失联 run 永久 running | finalize 阶段 kill -9 | 前端永不终态，P5-AC11 失败 | `kill -9` job worker 后重启，查询 `fact_normalization_runs.status` |
| R5 本地存储复用旧 job_id 误显示旧成功 | 证据快照更新后未重新整理直接刷新 | 用户看到“整理成功”但实为陈旧 | 更新证据后刷新，观察 `profileStale` 是否延迟或闪烁 |
| R6 oMLX 并发无 gate | 并行触发两受试者整理 | 本地模型 OOM/超时，部分失败被记为 `PARTIAL` | 并行 `POST` 两个整理，观察 `oMLX` 日志是否并发 |

**仍需 Codex 补足的验证（非本参会者职责，但影响裁决）:**
- 真实 `TestClient` + 临时 `ENROLLMENT_V2_DATA_DIR` 的启动探针（worker_01 曾做的隔离 fresh-db probe）是否在 5.8 分支仍通过，且日志包含 `evidence_normalizer_runtime_config: {prompt_version_id, model_config_id}`。
- `frontend` 的 `npm run build` 与 `playwright` 在 1080P/2K/4K 下 `ProfileNormalizationStatus` 的文案是否同时通过中文审计与 `axe`（参考 `.trellis/spec/frontend/quality-guidelines.md:31-35`）。
- 数据库迁移 `0013_clinical_facts_profile_v2` 及其后续追加列的 `payload_sha256` 兼容性（`quality-guidelines.md:76-77`），需对旧 payload 的解码回归。

## Recommended Next Step

**不建议直接进入最终用户试用；建议先由 Codex 牵头执行“配置-真实模型-定位”三项最小修复后重跑受影响全量（约 1 人日）:**

1. **配置层（0.5h 代码 + 0.5h 验证）**
   - 在 `validate_evidence_normalizer_model_config` 增加 `provider==deepseek → DEEPSEEK_API_KEY 非空` 的快检；在 `app/api/v2/app.py:lifespan` 对 `evidence_normalizer_runtime_config` 执行一次 `evidence_normalizer_transport_from_model_config` 试建，失败即阻断启动并返回可操作中文（“本机模型服务未配置/不支持的供应商”）。
   - 在 `register_evidence_normalizer_runtime_config` 追加对旧活跃配置的归档日志（打印被保留/被归档的 `model_config_id`），并在文档中明确“改环境变量后需重启，若仍报多配置请清理表”的操作步骤。

2. **e2e 定位验收（1h 代码 + 1h 真实数据跑）**
   - 将 `stepPatientProfileAndLocator` 的单点验证扩展为按 `CaseDescriptor` 声明的关键泳道抽样（至少 `demographics/birthDate`, `targetDisease`, `medicationExposure`, `labOrScore`），每类未命中即 `disposition: fail`。对弱来源事实额外断言界面 `溯源提醒` 文案存在。`history_replay` 在无修订时保持 `observed_only` 的当前行为不变。

3. **合同与恢复（0.5h 代码）**
   - 修复 `run_id` lossy：`FactNormalizationCommandView` 增加 `runId` 并在 `decodeFactNormalizationCommand` 中校验；或后端 `FactNormalizationSubmitDTO` 去掉 `run_id` 以保持对称，需 Codex 定夺（见下 Q1）。
   - 扩展 `recover_fact_normalization_runs` 对 `running` + 过期租约的 run 置为 `FAILED`，并在前端 `useFactNormalizationJob` 的存储中一并持久 `input_scope_sha256` 用于恢复时比对。

**向 Codex 的有界提问（任一未决均按安全侧暂停该类验收）:**

- **Q1 合同**: `run_id` 预期是否属于前端可审计字段？若否，是否应从 `FactNormalizationSubmitDTO` 移除以避免“返回但不消费”的漂移；若是，前端解码是否应强制校验并在 `useFactNormalizationJob` 中透传给后续 `profile` 关联？
- **Q2 真实模型**: 对于 `provider=omlx` 的离线开发机，启动时是否要求对 `OMLX_BASE_URL` 做一次 2s 超时的 `GET /v1/models` 健康探测并在失败时降级为 `observed_only` 而非阻断启动？当前默认是阻断（若按建议修复），需确认离线策略。
- **Q3 定位抽样**: 5.8 的 D001/MG-K10 代表病例是否已有各泳道的“关键事实清单”（按 `evidence_normalizer` 的 `fact_type` 枚举），可作为 e2e 的 `CaseDescriptor.expectedFactTypes` 输入，还是允许 e2e 仅做几何存在性检查并将分泳道核对留到 Codex 的人工逐事件核对？

**安全 provisional 路径**: 在上述 Q 未答复前，默认按最保守执行——`run_id` 先以前端追加校验、前向兼容旧后端（多余字段忽略改为必需）；`omlx` 健康探测设为**警告日志但不阻断**，仅 `deepseek` 缺 key 时阻断；e2e 保持单点几何校验但将报告标记为 `advisory` 并在最终裁决中注明“未覆盖分泳道全量”，由 Codex 人工核对补位。
