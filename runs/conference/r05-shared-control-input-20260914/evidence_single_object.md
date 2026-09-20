# Conference Output: r05-shared-control-input-20260914 - evidence_single_object

## Output

只读证据审阅已完成（未运行测试、未调用模型/数据库、未写入任何文件；全部结论来自源码阅读）。总体判定：**该纵向切片的接线在来源绑定、历史哈希、身份闭包和防伪官方编号四个主面上与设计合同 §17.3 一致，未发现 P0 级缺陷**；发现 2 项 P1（提示体积与提示演化身份 hazards）与 5 项 P2（详见下文），以及 3 个需要 Codex 裁决的边界问题。以下按「证据 / 推断 / 建议 / 不确定性」分离陈述。

### 一、已核实正确的接线（证据，file:line）

**1. 来源节点桥接（候选 → 正式目录 → 正式规则修订）闭合**
- 执行器 gate 步骤只产出候选包（`formal_catalog_status=not_materialized`），空目录 scaffold 明确不持久化：`app/services/protocol_control_execution.py:1657-1683`。
- `materialize_control_catalog` 复制全部水合候选，重复候选、缺语义、越界结构单元一律整体失败（无静默丢弃）：`app/protocols/control_catalog_materialization.py:44-57`；CONTROL_CANDIDATE 关系端改写为内容寻址 PROTOCOL_CONTROL 身份且必须存在于本次目录（:72-82）；随后用填充后的目录重跑完整发布门禁（:102-106），门禁对正式控制要求显式义务 DNF、拒绝 5.8a 平坦义务（`app/protocols/protocol_control_gate.py:4108-4114`）。
- `prepare_control_catalog_publication` 证明：任务 completed 且未取消、step/checkpoint 身份一致、checkpoint 是该步骤最后一个、payload 哈希通过、`source_input`/`source_spans` 与本次发布的方案逐字相同（防跨方案污染）、gate 版本/结果种类/候选闭包/plan_id 全部核对：`app/services/protocol_control_catalog_publication.py:44-69`。
- `bind_control_workflow_stages` 逐节点验证 `{rule_set_id}:{revision}:` 命名空间变换（内容相等）、必做项目映射桥接（span 集合相等、requirement_ids ⊆ due_requirement_ids、访视/阶段相等）、映射双射且覆盖目录引用的全部节点：`app/protocols/control_catalog_materialization.py:126-179`。来源节点本身派生自必做项目录（每 (stage, visit) 一个），故双射要求结构上可满足：`app/services/protocol_control_execution.py:794-824`。发布侧 `published_stages` 确为草稿节点加同一前缀：`app/services/protocol_publication_service.py:616-632`。
- 保存时序正确：prepare 在写入前、save 在方案/RuleSet/Project 插入之后、同一事务内：`app/services/protocol_publication_service.py:382-398, 464-472`。

**2. 历史哈希与不可变性**
- `canonical_hash` 对 JSON 键排序，决定论：`app/domain/publication.py:10-18`。
- `ControlCatalogPublication.publication_id` 由正文内容寻址派生，手工指定被拒：`app/domain/contracts/control_catalog_publication.py:154-169`；同一 RuleSet 修订至多一份目录、同 ID 不同内容被拒、读取时镜像+门禁输出哈希复验：`app/storage/control_catalog_repository.py:98-126, 203-216`。`created_at` 变化无法分叉身份（gate_result_id 碰撞时因 output_hash 不等而显式失败，`protocol_control_catalog_publication.py:118-120`）。
- 目录只能随新规则修订创建（无事后附加路径），与 §17.3「目录变化必须发布新的正式规则修订」一致（仓储 :116-124 的拒绝语义）。
- **v1 序列化兼容成立**：`ClausePack.control_publication` 为可选字段，wrap serializer 在 None 时弹出该键，历史 v1 包 canonical 字节不变；digest 排除 `schema_version`/身份字段：`app/domain/contracts/clause_pack.py:47-55`、`app/projections/clause_pack.py:164-173`。旧任务载荷无该键 → 校验默认 None → 序列化字节一致（兼容回读）。
- 下游身份闭包：页读记录身份含 `clause_pack_sha256`（`app/llm/page_review_harness.py:701-723`）、coverage 按包哈希选取（`app/services/page_review_coverage_selection.py:32-38`）、续跑要求载荷全等（`app/services/page_review_job_service.py:184-189`）、视觉来源重建要求包哈希一致（`app/services/page_review_visual_sources.py:71-73`）、审核上下文 v2 校验器核对包哈希与发布绑定（`app/domain/contracts/review_context_v2.py:124-137, 167-173`）。发布目录变化 → 新身份 → 显式 not-ready，而非静默复用。

**3. 无伪官方编号**
- 合同层禁止 IN/EX/REQ/CTRL 形态的控制身份与展示标签：`app/domain/contracts/protocol_controls.py:113-116, 1573-1578`；`ClausePack` 校验官方条款与控制身份无碰撞：`clause_pack.py:68-70`。
- 提示层：系统提示明确「protocol_controls……不是新的官方入排编号」「clause_id 使用其 protocol_control_id」：`page_review_harness.py:443-450`。
- 读取合同层：`ClauseEvidenceSignal.clause_id` 无 pattern 限制（`app/domain/contracts/page_review.py:171`），格式校验的 `known_clauses` 经 `clause_determination_modes` 包含控制 ID（`app/llm/page_review_format_repair.py:136, 151-158`）——控制 ID 可被合法引用且未知引用被拒。

**4. 双读重建/缓存一致**
- 生产执行器从冻结载荷传递 association sources 进行对账：`app/services/page_review_job_executor.py:204-208`；coverage 选取与视觉来源用同一当前包+同一定位来源重算对账并要求 identity 相等（`page_review_coverage_selection.py:73-88`、`page_review_visual_sources.py:77-87`）；对账身份包含 `determination_modes` 与 `association_text_sha256`（`app/domain/page_reconciliation.py:184-189`）。

**5. 忽略要求审计**：候选全集进入目录（`control_catalog_materialization.py:45` + 门禁候选闭包）；非控制单元的处置保留在冻结 manifest 中、经 job/checkpoint 哈希可回溯；`frozen_review_calculation.py:37-38` 对含控方案**显式拒绝**而非静默省略（符合任务说明的声明边界）。

### 二、缺陷与风险（按等级）

**P1-1（语义保真/成本）——提示包把目录内部簿记整份发给两主读，逐页逐道放大。**
`page_review_prompt_pack`（`app/projections/page_review_prompt_pack.py:18-24`）直接注入 `publication["catalog"]` 全量 JSON：`allowed_source_span_ids`（全部 manifest span ID，对模型无语义）、每原子 `source_span_ids`、`relation_id`/`shared_assessment_identity`、`catalog_id` 及全部四层 DNF 元数据。跨章要求多的方案会显著增加每页每道输入并稀释注意力，与 §4/§13 的紧凑条款包目标相悖，同时扩大 ID 型幻觉面。
**建议**：为读侧投影一个面向模型的控制渲染（id、display_ordinal、title、applicable_population、条件/义务/例外原子携带的 `source_excerpts` 原文、义务 kind+modality+temporal scope、节点绑定的访视名、minimum_evidence 描述），剔除 span ID 清单与关系簿记；权威全量仍冻结在 ClausePack 内。**约束**：任何此类压缩必须同步提升提示身份版本（见 P1-2），否则破坏身份假设。

**P1-2（身份 hazard）——记录身份不哈希实际提示字节。**
`PageReviewRecord` 身份只含 `prompt_version` 字符串 + `clause_pack_sha256` + `response_sha256`，不含 `messages` 哈希（`page_review_harness.py:693-723`）。本次控制注入之所以安全，仅因注入以 `control_publication is not None` 为条件且改变包哈希；未来任何**不改变包哈希**的提示渲染调整（如 P1-1 的压缩、措辞修改）将产生 prompt_version 相同而实际提示不同的记录，静默破坏双读「同一提示」前提与续跑校验。
**建议**：将 `canonical_hash(page_review_prompt_pack(clause_pack))`（或 messages 哈希）纳入记录身份，并纳入 coverage 选取所比的 `execution_versions`。

**P2-1——`review_page`/`review_pages` 便捷路径不带 association source 对账。**
`app/services/page_review_execution.py:93, 131-136`：该路径产出的 reconciliation_id 与重算核验（恒带冻结定位来源）不一致，未来任何调用方持久化其结果都会在 coverage 选取时报「现有核对结果与当前处理方式不一致」。**建议**：在持久化路径上把 `association_source` 变为必填，或断言与冻结载荷一致。

**P2-2——控制统一 DETERMINISTIC 模式抹平了研究者判断区分（读阶段惰性，评估阶段危险）。**
`clause_determination_modes`（`app/projections/clause_pack.py:155-161`）把所有控制标为 DETERMINISTIC，包括含 `MUST_PROFESSIONAL_ASSESSMENT` 义务的控制。读阶段无影响（控制信号本就全部丢弃且有审计记录），但该映射是对账身份携带的唯一词汇表；控制评估落地时若复用它，会把专业判断义务误路由进确定性聚合。**建议**：在读阶段映射保持现状的前提下，为含 MUST_PROFESSIONAL_ASSESSMENT 义务的控制引入区分模式或侧信道谓词，并显式注明该映射仅限读阶段。

**P2-3——发布路径不交叉核对 phase applicability 视图。**
执行器 gate 与 `prepare_control_catalog_publication` 均不传 `phase_applicability_view`（`materialize_control_catalog` 有此可选参数）。两侧输入一致故无分歧，且视图「不重写来源期别范围」，非正确性缺陷；但若 manifest 存在已决议视图，正式发布未将其作为额外验收输入。见下方问题 Q1。

**P2-4——控制最低证据与专业评估义务暂无下游消费者（属声明待办，非新发现 bug）。**
统一期望/控制评估缺失；判断检索现仅按官方条款 requirement_id 绑定（`review_context_v2.py:220-230`）。集成时控制 `minimum_evidence` 须与官方 `evidence_requirements` 进入同一要求身份命名空间，且 §17.2 四态判断表须覆盖控制级 MUST_PROFESSIONAL_ASSESSMENT。

**P2-5——「未进入正式目录的已知控制须在范围说明可见」尚无承载面。**
目录只随新规则修订创建；控制作业晚于方案发布时，本切片没有任何审阅期表面提示「已知控制未随本修订发布」。前端编排属声明缺席，记录为集成要求。

**P3（顺带）**：`_validate_control` 首行 `next(iter(unit_by_id.values()))` 在空 manifest 时抛 StopIteration 而非门禁错误（`protocol_control_gate.py:4095`）；空 manifest 实际不可构造，仅健壮性小疵。

### 三、边界问题裁定（任务指定评估项）

**「控制关系信号归类为 dropped deterministic aggregation 是否可接受的读阶段边界」——可接受，附条件且条件当前成立**：(a) facts/handwriting 的对账与条款身份无关、独立保留（`page_reconciliation.py:66-96, 143-167`）；(b) 丢弃逐页记录于 `dropped_deterministic_signal_clause_ids` 并进入对账身份哈希（:113-122, 182, 188）；(c) 无任何评估消费者把页级控制信号当条件证明。**必须强调**：该丢弃清单只证明「某读道把本页关联到该控制」，是方向不是求值，不得据此声称四层语义原子已证实——与任务声明的「NOT claiming semantic atoms proven」一致。

### 四、下一步最小集成设计（保留四层结构，不拍平、不 exists 谓词）

1. **冻结输入**：按 (authority, publication) 冻结 `ControlEvaluationInput` = 发布目录四层原文 + 该权威已对账事实/手写集合 + workflow_stage_map + 锚定日期；不接受页级信号输入。
2. **确定性评估器复用 `calculate_component_review` 分工**：适用性→按节点绑定与当前 review_context 阶段过滤；触发→逐分支对事实求值、未证实显式保留；义务→逐组带 modality 的结果（mandatory/recommended/best_effort 为不同结果，不合并）；例外→仅被证实的例外按 `waives_trigger_branch_indexes`/`activates_obligation_group_indexes` 语义解除/替代，替代时间窗只读义务组。
3. **专业判断路由**：MUST_PROFESSIONAL_ASSESSMENT 义务以 (protocol_control_id, obligation_id) 为要求身份接入 §17.2 四态机制，扩展 judgment search scope 类型而非另建平行表。
4. **输出**：每控制 `ControlAssessment`，原子级证据只引用 fact_id/locator；缺口原因分列（记录不全 / 缺判断 / 未到期节点 / 冲突）；展示用「方案控制 NN」，无 IN/EX 码。
5. **接入门槛**：替换 `frozen_review_calculation` 的显式拒绝之前，控制评估须通过与 §17.1.1 同级的隔离评测与留出反例验证；在此之前保留拒绝。

### 五、给 Codex 的最重要异议与有界问题

- **Q1（P2-3）**：`prepare_control_catalog_publication` 是否应在 manifest 存在已决议 phase applicability 视图时强制接收并核对之？影响发布验收强度；安全临时路径=维持现状（两侧输入已一致）。
- **Q2（P1-2）**：是否现在就把提示内容哈希纳入记录身份与 `execution_versions`？影响所有后续提示演化（含 P1-1 压缩）的安全性；安全临时路径=至少在 P1-1 实施时同步 bump `PAGE_REVIEW_PROMPT_VERSION` 并登记该约束。
- **Q3（消费边界确认）**：控制评估是否确认「只消费发布目录 + 已对账事实，页级信号永久保持 dropped/audit-only」？此决定直接约束第五节第 1 步的输入合同。

**不确定性声明**：未读全 4637 行门禁的每一条检查（抽查了入口编排、`_validate_control`、`_resolve_targets`、`_check_phase_applicability`）；`protocol_control_job_service` 创建细节、`page_association_sources` 内部实现未深读（判定为非本切片直接依赖）。以上均不影响已列结论的证据等级；全部发现为源码静态证据，未做任何运行验证。本报告不构成临床、监管或用户侧验收。
