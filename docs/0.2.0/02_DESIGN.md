# 0.2.0 DESIGN：细闭环的技术设计

本文件回答"怎么实现 `01_PRD.md`"。所有 `文件:行号` 均以分支起点 `5c63ba1f` 为准，实施前先打开核对；行号漂移时以函数名为准。

---

## 1. 总体架构

```
┌──────────────────────────── 方案图 Protocol Graph（每个方案版本一次）────────────────────────────┐
│ P1 结构快照 ─► P2 范围解析 ─► P3 规则起草 ─► P4 变量绑定 ─► P5 静态检查 ─► H1 MM逐条审定 ─► P6 发布 │
│ (DOCX解析)    (确定性+MM)     (LLM,复用)     (LLM建议+MM)   (确定性,只提示)  (人工节点)     (事务)   │
└──────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                               │ RuleSet vN（含 variable_id、REQ、禁用药条目）
┌──────────────────────────── 受试者图 Subject Graph（每例×每节点，资料或更正触发）───────────────┐
│ S1 资料快照+OCR ─► S2 需求清单 ─► S3 定向抽取 ─► S4 逐字核对+风险标记 ─► S5 确定性判定 ─┐        │
│ (复用)             (确定性)       (LLM)          (确定性)                  (expression.py) │        │
│                                   S6 语义/研究者判断检索 (LLM+确定性核对) ───────────────┤        │
│                                                                    S7 结论组装 ─► S8 写工作稿    │
│                                                                    (确定性)       ReviewRun     │
│ H2 MM处理问题卡片（更正/补证/已核）──► 触发 S1/S4 起受影响部分重算 ──► 新 ReviewRun(supersedes) │
│ 查看当前结果／历史与导出（不收集最终入组决定或签发意见）                                           │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## 2. Graph Engineering：运行时任务图

### 2.1 做法

- **不引入新框架。** 继续用现有持久 Job 引擎（`app/workflow/jobstore.py`、`runner.py`、`states.py`：步骤 `depends_on`、租约、重试、检查点、启动恢复）。
- **把受试者图显式化**：新增 `app/graph/subject_graph.py`（单个模块），用一张声明表描述受试者图 S1–S8 的节点、类型、输入工件、输出工件和对应 Job／步骤，`work_draft_review` Job 的步骤依赖从这张表生成；一个测试断言代码中的节点集合与 §2.2 中 S 开头的行一致。**方案图（P1–P6）只在本文档中描述，不重构现有方案 Job**（它已有固定步骤，重构不推进闭环）。
- **边就是工件**：每个节点的输出是带哈希的版本化工件（沿用 ArtifactStore／仓储记录）。下游节点按输入哈希判断是否需要重算——这就是"受影响范围重算"。
- **三类节点**：`agent`（LLM 调用，输出必须经下游确定性节点核对）、`deterministic`（纯函数＋仓储）、`human`（等待 MM 操作，Job 状态 `waiting_user`）。

### 2.2 节点表

| 节点 | 类型 | 输入 | 输出 | 复用／新增 | 失败时 |
|---|---|---|---|---|---|
| P1 结构快照 | det | 方案 DOCX | `StructureBlock`／结构单元 | 复用 `app/protocols/docx_structure.py`、`full_protocol_coverage.build_full_protocol_coverage_manifest`（只用其确定性单元与 `heading_path`，不跑控制发现） | 停止（方案不可读） |
| P2 范围解析 | det＋human | 结构单元、IN/EX 原文 | 范围清单（章节单元 ID＋理由＋引用它的条款） | **新增** `app/protocols/review_scope.py` | 无法匹配的引用列为提示，MM 手工指定 |
| P3 规则起草 | agent | IN/EX 原文＋范围清单＋SoA 目录 | 规则草稿修订；禁用药条目草稿 | 复用官方解构（`protocol_workbench_service` 生成步骤、`app/agents/protocol_deconstructor.py`）；禁用药为**新增**小提示 | 重试 1 次；仍失败则该条款在审定页显示"起草失败，请手工填写" |
| P4 变量绑定 | agent＋human | 草稿谓词、变量字典 | 每个需要数据的条件的 `variable_id` 建议 | **新增**，结果写入 `EvidenceRequirement.variable_id` | 无建议则留空，审定页提示 MM 选择 |
| P5 静态检查 | det | 草稿 | 每条规则的提示列表 | 复用 `ProtocolDeconstructionGate` 的检查，按 §5.3 重新分级 | 不会失败；只产出提示 |
| H1 逐条审定 | human | 草稿＋提示 | `RuleReviewRecord` | **新增** | — |
| P6 发布 | det | 全部审定的草稿 | `RuleSet` vN | 复用 `ProtocolPublicationService.publish` | 结构性错误时拒绝并列出 |
| S1 资料与 OCR | det＋agent | 上传文件 | 资料快照、页、OCR 文本、有效文字 | 复用现有证据管线 | 页读失败→系统问题，其余页继续 |
| S2 需求清单 | det | RuleSet、节点 | `variable_id` 列表、REQ 列表、禁用药条目 | **新增** | — |
| S3 定向抽取 | agent | 需求清单、有效文字 | 事实候选（带 `variable_id`） | 改造 `app/agents/evidence_normalizer.py` | 批次失败重试 1 次；仍失败→该批文件进系统问题 |
| S4 核对与标记 | det | 候选、有效文字、页 OCR 风险 | 已采用事实＋风险标记；被拒候选 | 改造 `fact_candidate_gates`、`fact_evidence_closure`、`fact_publication_service` | 被拒候选→系统问题 |
| S5 确定性判定 | det | 规则包、事实、用药暴露 | 每组件 decision＋gaps | 复用 `component_review.calculate_component_review`、`expression.py` | 计算不支持→系统问题 |
| S6 语义与判断检索 | agent＋det | 语义/判断条款、页 | 引用＋建议 | 复用 judgment_search；语义命题为**新增**小步骤 | 无引用→证据不足或需研究者判断 |
| S7 结论组装 | det | S5、S6、风险标记 | 六结论＋置信＋原因＋问题卡片＋系统问题 | **新增** `app/services/review_conclusions.py` | — |
| S8 写工作稿 | det | S7 | `ReviewRun(run_kind=work_draft)`＋`work_draft_items`＋`system_issues` | **新增** `app/services/work_draft_review.py` | 身份不一致→停止 |
| H2 处理问题 | human | 卡片 | 更正／补证／已核记录 | 复用 `fact_correction_service`、增量上传 | — |
| 历史与导出 | det＋human | 已保存工作稿 | 当前／历史展示、导出 | 复用历史读取与导出；旧正式签发代码保留，不在0.2.0新增签发流程 | 读取失败显式提示，不重算旧稿 |

### 2.3 图的运行规则

1. **降级优先**：除身份类错误（错受试者、错项目、方案版本不一致、文件哈希不符）外，任何节点失败都要产出"系统问题"工件，下游节点把对应输入视为缺失继续运行。
2. **LLM 输出一律经确定性节点核对后才能被下游使用**（P3→P5/H1，P4→H1，S3→S4，S6→S4 同款核对）。
3. **重试上限 1 次**。同一输入、同一提示连续两次失败，不再自动重试，进入系统问题。不得为某一类失败新增专门的修复函数（0.1.x 方案链里已有 86 个 `*repair*`、24 个 `continue_*` 函数）。
4. **重算按哈希**：资料快照、事实修订、规则包版本任一变化，从受影响节点起重算；其余节点复用。前提是事实不随规则包版本失效，见 §4.5。
5. **"无新信息"的定义**：同一节点、相同输入哈希、相同提示／代码版本，得到相同错误码。满足即停止自动重试。

## 3. Graph Engineering：开发编排

```
             ┌──────────── 用户（真实 MM，临床最终权威）────────────┐
             │ 里程碑验收 0.2.0-M1/M2/M3；回答 PRD §13 待定事项        │
             └──────────────▲───────────────────────────▲─────────────┘
                            │ 里程碑报告                 │ 阻塞问题（一次集中）
┌───────────────────────────┴───────────────────────────┴──────────────┐
│ 构建者（Codex，唯一所有者）                                          │
│ 按 03_PLAN 顺序实现 → 本地验证 → 更新 05_PROGRESS → 提交            │
└───────────────┬───────────────────────────────────────┬──────────────┘
                │ 每个里程碑合并前各一次（只读）         │
     ┌──────────▼──────────┐                 ┌──────────▼──────────────────┐
     │ 评审 A：代码正确性    │                 │ 评审 B：医学结果验收         │
     │ 一个独立模型，一轮    │                 │ 以 MM 视角对照 04_ACCEPTANCE │
     │ 输出：阻断问题清单    │                 │ 与人工 IE 表；输出差异分类   │
     └─────────────────────┘                 └──────────────────────────────┘
```

- 构建者对用户结果负责；评审只读、每个里程碑各一轮，不在每次修补后触发。
- 评审发现的问题由构建者分级：阻断里程碑的修，其余记入 `05_PROGRESS.md` 的"已知问题"。
- 评审 B 不能代替用户验收。模型扮演的 MM 只用于在交给用户前过滤明显问题。
- Prompt 见 `06_AGENT_PROMPTS.md`。
- 构建期由构建者以 `builder_verification` 在验证副本自行走 H1/P6，产生 `verification_only=true` 的验证包；不借此改变正式身份或覆盖原批准。里程碑检查与实际用户批准分列，只有方向／风险／真实医学歧义需要中途询问。界面默认列待审项，按内容哈希保持其余有效审定。

## 4. 数据模型改动

所有新字段均为可选，`None` 时不参与序列化，保持既有内容哈希与历史记录不变（沿用仓库已有做法）。新增表用 Alembic 迁移（`app/storage/migrations/versions/`）。

### 4.1 变量字典

- 新增 `app/domain/variables/`：`dictionary.py`（加载与校验）＋`core_variables.yaml`（跨项目通用核心变量）。
- 条目字段：`variable_id`（小写下划线英文，稳定）、`label_zh`、`value_type`（`number`｜`category`｜`boolean`｜`date`｜`exposure`｜`procedure`）、`canonical_unit`、`unit_conversions`（如 `10^9/L → /μL ×1000`）、`aliases_zh`（OCR 中常见写法，供抽取提示与人工查找，不用于自动匹配）、`plausible_range`（按 `canonical_unit` 的合理上下限，用于 `IMPLAUSIBLE_VALUE`；数值型变量必填）、`domain`（`demographic`｜`lab`｜`vital`｜`score`｜`history`｜`medication`｜`procedure`）。
- 项目特有变量（MM 在审定时新增）随规则包版本保存：新增表 `rule_set_variables`（`rule_set_id`、`revision`、条目 JSON），不写回核心字典。
- 药物类别成员表：`app/domain/variables/drug_classes.yaml`（类别 → 中英文药名列表，如"全身糖皮质激素"→泼尼松、甲泼尼龙…）。项目补充随规则包保存。

### 4.2 规则侧

| 改动 | 位置 | 说明 |
|---|---|---|
| `EvidenceRequirement.variable_id: str \| None` | `app/domain/contracts/rules.py:507-523` | 放在需求上而不是谓词上：谓词内容哈希决定规则身份（`rules.py:327-340`），`requirement_id` 只在一个修订内有效，`variable_id` 跨修订稳定 |
| 每个需要数据的谓词必须有一条 `EvidenceRequirement`，其 `predicate_ids` 包含该谓词、`variable_id` 非空 | P4 产出，P6 发布前校验 | 0.1.x 旧规则的 89 个需求 `predicate_ids` 为空，是工作稿失败的直接原因之一 |
| 新增 `ProhibitedMedicationItem` | `app/domain/contracts/` 新文件 | 字段：`item_id`、`drug_text`、`drug_class_id`（可空）、`window: TimeConstraint`（复用，可含 `half_life_multiplier`）、`direction`、`source_span_ids`、`source_excerpt`、`applies_to_rule`（关联的 EX 编号，可空）。随 `RuleSet` 保存 |
| 新增 `RuleReviewRecord` | 新表 `rule_review_records` | `protocol_version_id`、`official_code`（或 REQ／禁用药条目 ID）、`rule_content_hash`、`reviewer_kind`（`medical_manager`｜`builder_verification`）、`reviewed_by`、`reviewed_at`、`note`（含 `excluded`、`result_variables` 设置）。有效性按 `rule_content_hash` 判断：草稿新修订中该条内容哈希不变则审定继续有效；变了则失效。发布时任一条为 `builder_verification`→`RuleSet` 标 `verification_only=true` |
| 范围清单 | 新表 `protocol_review_scopes` | `protocol_version_id`、单元 ID 列表、每项理由、来源（自动／MM 手工）、MM 增删记录 |

### 4.3 事实侧

| 改动 | 位置 | 说明 |
|---|---|---|
| `variable_id: str \| None` | `ClinicalFactCandidateV2`（`app/domain/contracts/facts.py:249-275`）、`ClinicalFactV2`（`:391-421`） | 抽取时从需求清单中选；不在清单中则为空，事实仍进入 Profile，但不参与判定 |
| `risk_flags: list[RiskFlag]` | 同上 | 枚举见 PRD §8；由 S4 程序判定 |
| `date_role: Literal["sampling","report","visit","unknown"] \| None` | 同上 | 用于 `DATE_ROLE_UNCLEAR` |
| `reviewed_by_mm: bool` 及时间 | 事实修订 | "标记已核"写新修订，不改值 |

### 4.4 审核侧

| 改动 | 位置 | 说明 |
|---|---|---|
| `ReviewRun.run_kind: Literal["work_draft","formal"]` | `app/domain/contracts/review.py:156-165`；`app/storage/models.py` 加列，默认 `formal` 兼容历史 | 工作稿与签发分开 |
| 工作稿写 `supersedes_review_run_id` | `review.py:163` 已有字段，至今无人写入（只在 `app/api/v2/review_history.py` 读取） | 同一 episode 的上一版工作稿 |
| **工作稿条目不写 `FinalAssessment`**，新表 `work_draft_items` | 新契约 `WorkDraftItem` | `FinalAssessment`（`review.py:291-308`）强制要求 `gate_result_id`、`publication_fingerprint`，属于正式签发，工作稿不伪造这些字段。`WorkDraftItem`：`review_run_id`、`official_code`、`rule_component_id`（父规则行为空）、`decision`（`ComponentDecision`）、`display_state`（六结论之一或 `system_issue`）、`confidence`（`high`｜`low`｜null）、`confidence_reason`、`reason_text`、`evidence_refs`（事实 ID→locator→页码→摘录）、`input_hash`（所用事实修订＋规则内容哈希）、`policy_group`（如 `not_recorded_in_scope`） |
| 结论级"已核"：既有 `work_draft_acknowledgements` | `WorkDraftAcknowledgement`、`WorkDraftRepository` | 冻结节点、原工作稿／条目、依据内容指纹、执行Job、核实身份和时间；不收集理由。新稿只有本条依据与计算方式完全相同才沿用，构建者试用与医学经理核实分开 |
| `SystemIssue` | 作为 `ReviewRun` 下的 JSON 列 `system_issues` 保存 | `kind`（`method_unsupported`｜`page_unreadable`｜`model_output_invalid`｜`excerpt_unverified`｜`extraction_failed`｜`component_unstructured`｜`fact_closure_failed`）、受影响条款、说明、替代路径 |
| 命名 | — | 现有 `_completed_work_draft` 指 prepared-review 结果；新代码统一用 `work_draft_review`／`WorkDraftItem`，不复用旧名 |

### 4.5 事实与规则包版本解耦（重要）

现状：`FactAuthority`（`app/domain/contracts/facts.py:94-111`）把每个已发布事实绑定到 `rule_set_id`／`rule_set_revision`／`episode_revision`／`evidence_snapshot_v2_id`；`fact_rule_index`（`app/domain/contracts/fact_rule_index.py` 文件头注释与 `:66-112`）和 `evidence_expectations`（`app/projections/evidence_expectations.py:221-225`）会丢弃权威元组不一致的事实。照此，规则包每重新发布一次、每补传一份资料，31001 的全部事实都会失效，必须整例重抽。

0.2.0 的做法：
1. **工作稿路径不使用 `fact_rule_index`／`evidence_expectations` 的修订一致性过滤**。`select_by_variable` 只要求事实属于同一项目、受试者、审核节点，且其 `evidence_snapshot_v2_id` 是当前快照或其祖先快照（快照是不可变全量＋去重增量，祖先关系可查）。规则包修订号与事实无关，匹配靠跨修订稳定的 `variable_id`。
2. **规则包重新发布后**：已有事实直接被新规则包使用；只有新增的 `variable_id`（新条款需要的变量）才触发一次补充抽取，抽取范围是全部页但需求清单只含新增变量。
   - 当前工作稿入口先将节点对应到项目现行已发布规则：核同项目／规则谱系／期别、原方案文件哈希及唯一一致的访视结构，再用既有乐观锁更新节点的当前规则与访视指向；旧冻结上下文、事实和报告不改写。在本节点有活动整理／计算作业时不切换；原件或访视不相容时明确停止该更新，不回退旧规则冒充当前。
   - 原文字覆盖证明只在同项目／受试者／节点／快照／处理修订、同方案文件及相同变量字典时复用；仍按成功call及原逐页账本核对，不按页数相等放行。覆盖复用不代表新条款满足，新增变量或改变字典仍需补充核实；旧失败和未决保留。
3. **补传资料后**：沿既有启用→事实整理→工作稿Job链，只读新增或失效文件。`retained_source_documents`核实际祖先快照、同项目／个例／节点、同方案、完整旧变量定义，以及每份文件的有效文字、定位、分类和风险处置；祖先关系或文件哈希本身不是充分证明。
   - `retained_normalization_reads`再核旧Job已终结、真实成功call、最终逐页账本、实际请求／原答工件及哈希、原模型身份、短引用、Schema和当前逐字提示。旧模型回执仍属于原模型，不制造当前调用、模型独立性或批准；缺历史证明时不跳页，工件损坏则报错。视觉补充材料与旧纯文字证明不混用。入队、完成和工作稿消费均复验冻结证明，新旧页集合逐页对账，新增页失败仍明确未完成。
   - 资料类别：文件名只生成待核建议，不由通用record或词内ct等片段推断病历／检查，不据文件名推断出具方。0.2.0定向读取保留未知类别而不阻断其他资料；身份失配仍拒绝。新`ModelConfig.parameters.include_source_categories=true`把已有结构类别传入模型，旧配置缺省false以原布局重建历史实际请求；预检、运行及回执复验使用同一冻结配置，不改旧工件或授予事实资格。来源强度仍由真实元数据及来源核对决定。
4. Profile／资料期望默认严格路径不变；0.2.0定向整理显式选择累计来源，工作稿、更正、事件／用药关联及期望覆盖均独立核上项来源资格，使用原事实ID和原authority，不复制旧事实。REQ结论仍由工作稿确定性计算。旧事实更正仅追加当前新事实；既有cascade在对应更正、候选／gate、引用映射及未改临床属性均相同时替代当前档案中的旧派生事件／用药，不能按同页或相同文字合并独立记录。原快照、原事件和历史报告不变。

## 5. 方案侧实现要点

### 5.1 解除跨章发布前置

- **先做只读诊断（WP1 第一步）**：rev21 所在草稿会话的 `session_kind`；SAR 方案与研究期别是否已有已发布项目（2026-09-20 曾发布 `rule_set rev=1`）。已有项目时，`publish_first_project` 会抛 `DuplicateFirstProjectError`（`app/services/protocol_publication_service.py:126`），必须走 `publish_re_deconstruction`，它要求 `session_kind == re_deconstruction` 且声明差异（缺失时报 `draft_diff_missing`，`:356`）。差异用现有 `/draft/comparison` 生成。诊断结论写入进度表，再决定改动点。后续再发布（WP5 新增范围与禁用药）同样走再解构路径。
- 删除或按配置跳过 `ProtocolWorkbenchService._require_control_publication_references` 的调用（`app/services/protocol_workbench_service.py:3276-3291`，调用点 `:3304`、`:3398`）。
- 门禁结果有缓存：`get_integrity` 在 `gate_version == DECONSTRUCTION_GATE_VERSION` 时复用旧结果（`protocol_workbench_service.py:1695`）。改动门禁分级后**必须提升 `DECONSTRUCTION_GATE_VERSION`**，否则 rev21 仍读到旧的不可发布结果。
- `ProtocolPublicationService.publish` 已支持无控制目录发布（`app/services/protocol_publication_service.py:394-415`）；下游 `review_protocol_source.py:93-107`、`published_clause_pack.py:10-14` 已兼容 `control_publication is None`。
- 前端 `frontend/src/components/protocols/ProtocolJobFlow.tsx:92` 去掉 `controlPublication === undefined` 条件。
- 跨章控制链（`protocol_control_execution`、`protocol_control_*` agents）保留代码与测试，从主路径断开：前端不再展示"方案其他审核要求"步骤，后端不再在主流程中排队该 Job。

### 5.2 范围解析（P2）

- 新增 `app/protocols/review_scope.py`：
  1. 用正则从 IN/EX 原文识别引用：`第\s*\d+(\.\d+)*\s*节`、`附录\s*[A-Z0-9一二三四五六七八九十]+`、`表\s*\d+(\.\d+)*`、`(参见|详见|见)…`；
  2. 在结构单元的 `heading_path`／编号／表题中匹配，取该标题下的全部单元；
  3. 按标题关键词定位 S3（研究流程表／访视流程／Schedule of Activities）与 S4（禁用药物／合并用药／伴随治疗／Prohibited／Concomitant）；
  4. 输出范围清单，每项带理由（"被 EX-07 引用"／"标题匹配：合并用药"）。
- 未能匹配的引用作为提示显示在审定页，由 MM 手工指定。
- **SAR（已有 rev21）不重新起草**：范围定位与选择复用外层不可变 `ProtocolDraftRevision.review_scope_selection` 保存，不另建 `protocol_review_scopes` 表。它不是模型作者Schema、另一份规则或临床采用。后续将已选范围作为对应条款的定义依据及禁用药抽取（R-A4）的输入。
- **新方案（如 D001）起草时**才把范围单元加入官方解构的 `source_materials`／`allowed_source_span_ids`（`app/protocols/deconstruction_service.py:574-610`），同时让 `catalog_material_coverage` 检查接受这些单元（否则会因"材料多于目录"报错）。

定位链为 `ProtocolWorkbenchService.get_review_scope` → `GET .../{job}/draft/review-scope` → 草稿及历史发布摘要的“查看审核范围”。从原任务保存的同一提取快照读结构工件并核哈希；重新解构任务没有重复结构时，按精确snapshot身份读取原任务保存记录，不重新解析方案／调用模型。S1/S3复用冻结目录，S2定位明确引用，S4取真实标题的有界子树；表格根文字复用`native_source_text`，不因根块无正文报损坏，不跨表借单元格。摘录仅要求逐字片段，不强求等于整段；项目／版本／期别／内容不符拒绝，未知引用显式保留。

选择链为同页勾选／移除理由／原文查找 → `PUT .../{job}/draft/review-scope` → 正常追加草稿修订及现有checkpoint → 同接口读回。S1/S3固定；S2/S4每项必须保留或说明移除。手工指定只允许同一冻结来源，关联官方条款与具体待定位引用；原文查找真正分页，不要求用户填写内部ID。Word多级自动编号模板未完整还原时不猜编号，例如“参照6.5”可手工指定实际章节，但这仅解决位置，不批准含义。正常手工编辑、变量修改、恢复历史均保留相应选择，旧无选择payload及hash不变。保存不是采用：对应要求未整理与审定前，API与两种发布入口明确阻止把选择冒充完整规则包；后续R-A4实际接线后以真实采用结果替代这项临时阻止，不关闭保护。当前`clinical_adoption_applied=false`，定义依据挂接及R-A4提取／审定／发布仍待完成。

### 5.3 静态检查重新分级（P5）

`ProtocolDeconstructionGate.evaluate`（`app/protocols/deconstruction_gate.py:1972-2024`）的 12 项检查按下表处理。`publishable` 的计算（`:2018-2022`）改为：**按检查名**判断，只有下表"结构性"检查中的问题（无论原级别是"阻止发布"还是"需要核对"）阻止发布；其余检查的问题一律作为提示返回。`blocking_count` 等按级别计数的字段相应改为只计结构性问题。WP1 第一步同时统计 rev21 在新分级下的结构性问题；能通过 MM 界面编辑解决的，用界面解决，不改代码。

| 检查 | 0.2.0 级别 |
|---|---|
| identity、parent_catalog、tree_integrity、boolean_logic、diff_integrity | **结构性**：阻止发布 |
| phase_scope、numeric、temporal、workflow_coverage、evidence_coverage、source_coverage、interpretation_authority | **提示**：显示在对应规则旁；MM 审定该条即视为已处理 |

### 5.4 逐条审定（H1）

- 审定入口 `ProtocolRuleReviewPanel` 消费同一草稿的真实条件树、变量绑定、来源及检查提示；分类仅作显示，不更改条款身份、含义或作用范围。复用 `ExpressionView` 展示全部／任一／否定、比较条件、时间窗、例外；绑定字典提供中文项目名，原文另列。解析把握度是可解释的核对优先级，不是医学正确概率；适用人群、例外、计算、书面判断和来源／绑定缺口为重点。
- `POST .../{job}/draft/reviews` 接受所选条目的内容哈希与设置，由 `review_rules` 与单条接口共享同一事务核验及追加事件路径。任一版本／内容／设置不符均全批拒绝；相同已审定内容、身份和设置的重试不重复记事件。筛选切换清除临时选择，确认框明确检查是否只核操作、所需结果和排除设置；不自动发布、不改变既有审定。
- R-A12复用`protocolRuleReview.ruleReviewAdvice`与既有`ProtocolManualEditDialog`：原因／备选／影响同屏；有明确原文线索才推荐核对方向，无法比较时明确不推荐，不报虚构概率。针对选中子项预填关系但不保存；用户可改选。首次与重新解构均接既有editDraft入口，原文／定位只读；保存追加修订、按内容失效审定，不自动采用。局部观察任选和外层要求组合分开；弹层初始化必须同时切换子项与条件，不混入上条。

- 后端：`POST /api/v2/protocol/deconstructions/{job}/draft/rules/{official_code}/review`（审定，请求体含 `reviewer_kind`）与 `DELETE`（撤销）；发布前检查全部 IN/EX／REQ／禁用药条目均有与当前内容哈希一致的 `RuleReviewRecord`。
- **构建者不得以医学经理身份审定。** 构建者在验证副本上走流程时，`reviewer_kind=builder_verification`，`reviewed_by` 写"构建者（验证）"。0.2.0-M1 要求至少一次由用户本人完成的 `medical_manager` 审定与发布。
- 正式规则的同源反馈草稿复用审定，必须由实际Job的冻结来源、生成草稿身份及已发布基线修订证明；有新增解释来源时不继承。保留旧审定事件原ID／哈希／人员，不复制批准记录。REQ只比较自身要求对应的阶段到期项，阶段名称、时间窗、映射、来源、变量及自身要求仍严格核对；无关条款删除不能让全部检查项目失效。当前撤销优先，改动条款须重审。服务与发布共用`current_reviews`，API新增`reviewed_content_hash`作为当前内容已核绑定；前端保留历史记录的原哈希，缺少绑定或绑定失配仍拒绝。
- 前端：在现有 `ProtocolDraftWorkbench` 每条规则上加"审定通过"按钮与状态；`ProtocolManualEditDialog`（`frontend/src/components/protocols/ProtocolRedoDialogs.tsx:389-628`）中 subject/attribute 自由输入改为"变量"下拉（来自字典＋项目变量，可新增）。
- 审定人：前端目前多处写死 `actor: "用户"`（`frontend/src/api/protocolWorkbenchHttp.ts:114, 147, 362`），改为本机配置的用户名（`.env` 新增 `ENROLLMENT_OPERATOR_NAME`，后端在响应中下发）。

### 5.5 研究流程表（REQ）

沿用 `app/protocols/procedure_catalog.py`（`build_required_procedure_catalog`，`:1563`）及其进入官方解构的路径（`deconstruction_service.py:554-563`、`protocol_deconstructor.py:3700-3740`）。每个 REQ 的 `EvidenceRequirement` 设 `variable_id = procedure:<catalog_item_id>`（`value_type=procedure`）。MM 在审定页把某 REQ 标为"不作为入组前必需"时，写一条 `RuleReviewRecord(note="excluded")`，该 REQ 保留在规则包中但不进入需求清单与判定，报告中列为"已由 MM 排除"；门禁中 `PROCEDURE_CATALOG_NOT_EXACTLY_COVERED`（`deconstruction_gate.py:3875-3893`）对已排除项不再报。判定在工作稿路径中计算（不读 `evidence_expectations` 投影结果，见 §4.5），但状态语义与 `app/projections/evidence_expectations.py:202-430` 保持一致。抽取时，检查报告／记录本身产出一条 `variable_id = procedure:<catalog_item_id>` 的事实（检查名称、日期、来源页）。映射：

| 情况 | 对应现有状态 | 结论 | 置信／原因 |
|---|---|---|---|
| 有该检查的报告或记录，且 MM 指定的必需结果变量都有值 | `OBSERVED` | 满足 | 高 |
| 同上，但来源较弱（筛选转录、邮件、翻拍） | `OBSERVED_WEAK` | 满足 | 低：来源较弱 |
| 有该检查记录，但缺必需结果变量 | — | 证据不足 | "结果不完整：缺 X" |
| 资料中提到做过但未见报告 | `REFERENCED_MISSING` | 证据不足 | "资料提到该检查，但未见报告" |
| 未见任何记录 | `ABSENT` | 证据不足 | "本次资料未见该检查" |
| 检查属于后续节点 | `NOT_DUE` | 未到期 | — |
| 检查日期不在方案规定的时间窗内 | — | 不满足 | "检查日期超出时间窗" |
| MM 已排除 | — | 不判定 | 报告列为"已由 MM 排除" |

`PENDING_CONTROL_APPLICABILITY` 来自已移出主路径的跨章链，工作稿路径中不应出现；出现则记 `SystemIssue`。

定向抽取中，`procedure` 类型输出有源布尔完成事实，与各项读数分开。原文明示完成或实际报告已填写结果且归属明确时，可以形成完成记录；医嘱、预约、次数及空白印刷项不证明完成。完成不证明正常或必需结果齐全；日期不从打印日、上传日或节点锚点补造。

## 6. 资料侧实现要点

### 6.1 定向抽取（S3）

- `app/agents/evidence_normalizer.py`：输入增加"需求清单"（`variable_id`、中文名、类型、单位、常见写法）；输出 `EvidenceFactDraft` 增加 `variable_id`（JSON Schema 中为需求清单 ID 的枚举＋null）、`date_role`。
- 删除"fact_type 只是展示类别、不必与需求一致"这一提示语义（`:521-522`），`fact_type` 保留为展示名。
- 不在需求清单内的内容照常抽取供 Profile 使用，`variable_id=null`。

### 6.2 核对与风险标记（S4）

| 改动 | 位置 |
|---|---|
| 肯定事实也要求 `assertion_text` 逐字出现在有效文字中，且数值字符串出现在 `assertion_text` 中（目前肯定事实只核 `asserted_object`） | `app/domain/gates/fact_evidence_closure.py:278-358` `_validate_assertion_text_closure` |
| 归属核对（PRD R-B4 ③④）：检验项名称（`label_zh`／`aliases_zh`）与数值在同一行或同一表格行；数值不落在参考范围模式（如 `\d+(\.\d+)?\s*[-–~]\s*\d+(\.\d+)?`）内。不通过→采用但加标记 `ATTRIBUTION_UNCERTAIN`（显示"数值归属需核对"） | 新增于 `app/domain/risk_flags.py`；PRD §8 增补该标记 |
| `IMPLAUSIBLE_VALUE`：换算后数值超出字典 `plausible_range` | `app/domain/risk_flags.py` |
| 整页阻断改为打 `LOW_OCR_CONFIDENCE` | `fact_evidence_closure.py:581-608`、`_has_unlocated_value_dependencies` `:643-662` |
| **页覆盖改为逐页**：`validate_page_coverage`（`fact_evidence_closure.py:71`）在任一页缺失时拒绝整个修订的全部候选。改为：缺失／重复的页记 `SystemIssue(page_unreadable 或 extraction_failed)`，只拒绝这些页上的候选；可参照已有的 `validate_page_coverage_per_candidate`（`:150`） | `fact_evidence_closure.py:71-148` |
| 同句上下文限定不满足的阻断（`fact_candidate_gates.py:530-539`）保留为拒绝，但记为 `SystemIssue(excerpt_unverified)` 而非静默丢弃 | `app/domain/gates/fact_candidate_gates.py` |
| 新增 `app/domain/risk_flags.py`：按 PRD §8 规则计算标记（阈值来自规则包中对应谓词的 value） | 新文件 |
| 去掉 `requirement.fact_type == fact.fact_type` 的硬性相等（Profile 侧链接因此能建立） | `app/domain/contracts/fact_rule_index.py:177`，改为 `requirement_id ∈ supported_requirement_ids` 或 `variable_id` 相等 |

**匹配的权威来源**：工作稿判定只用 `select_by_variable`（`variable_id`）。抽取器继续输出 `supported_requirement_ids`，仅供 Profile 与旧投影使用，工作稿不读它。

### 6.3 用药暴露

- 新增适配：`MedicationExposureV2`（`facts.py:525-551`）→ 判定用事实，`variable_id = drug_class:<class_id>` 或具体药物变量；有效日期取 `end_range`，`duration_status` 为持续则取锚点日；只有 `start_range` 时置 `PARTIAL_DATE`／低置信。
- 来源只有处方／医嘱／购药记录时打 `PRESCRIPTION_ONLY`。
- 药名在类别表中找不到→不参与类别匹配，生成卡片"未能归类的用药：××"；此时该受试者所有禁用药类别条款的"未触发"降为低置信（PRD R-C3）。
- `duration_status` 为间断或未知、只有 `start_range`→相关结论最多低置信，不得为高置信"未触发"。
- 禁用药判定用现有 `evaluate_time_constraint`（`app/domain/expression.py:336-416`），半衰期规则沿用 `HalfLifeEvidence`。

## 7. 判定与工作稿

### 7.1 新的工作稿路径（替代 prepared-review 子任务链）

新增 `app/services/work_draft_review.py`，作为一个持久 Job 类型 `work_draft_review`：

1. 冻结上下文：复用 `prepare_review`（`app/services/review_preparation_command.py:16-57`）的冻结逻辑与 `review_run_id` 预分配。它目前在任一事实引用闭包或定位校验失败时让整次审核失败（`_validate_referential_closure`、`validate_locators`）；工作稿路径中改为**剔除该事实并记 `SystemIssue(fact_closure_failed)`**，只有身份类错误整体停止；
2. `select_by_variable(clause_pack, facts, anchor_dates) -> {predicate_id: [fact_ids]}`：纯函数，按 `EvidenceRequirement.predicate_ids` × `fact.variable_id` 连接，再按 PRD R-B7 的时间窗与选取规则确定判定值；
3. 对每个组件调用 `calculate_component_review`（`app/services/component_review.py:27-66`），传入上一步的 `predicate_fact_ids`，`unverified_predicate_ids` 只包含**确无可用事实**的谓词；锚点日期取 `ReviewEpisode.anchor_dates`；
4. 语义条款与研究者判断条款并入 S6 结果；
5. `compose_parent(...)` 按 PRD R-C8 只汇总已到期子项，生成六结论、置信、原因、问题卡片、系统问题；后续子项完整保留为未到期，并在父项原因中说明届时重新审核。全部未到期才汇总为未到期；当前未知及 `restricted_components` 的系统问题仍参与组合，不能被未来子项掩盖；
6. 写 `ReviewRun(run_kind="work_draft", supersedes_review_run_id=上一版)`、`work_draft_items`、`system_issues`（§4.4），不写 `FinalAssessment`。

Job 幂等键：`(review_episode_id, 资料快照哈希, rule_set_id, rule_set_revision, 已核记录集合哈希, 代码中的计算版本号)`。

不经过 `prepared_review_workflow.py` 的子任务（LLM 双道绑定、资格、判断内容、命题、观察、频次、计算、历史检索），也不经过 `calculate_frozen_review`（它对受限条款会抛异常，`frozen_review_calculation.py:400`）。这些代码保留、移出主路径。

节点回溯复用 `AnchorResolutionStatement`／`InterpretationSource` 与现有时间求值器，不新增病种分支。工作稿 `review_anchor_dates` 仅把本次明确筛选／基线日期映射到已审定条件声明的 `review_node_date`，不写回节点、不借用旧日期；变量选择及原文关系的时间核验共用该映射。解释材料按实际适用条目纳入审定内容哈希，复制时仅身份重绑定不使内容改变；无范围、未知范围或正式修订材料影响全部条目。正式复制仍核来源冻结回执、原方案输入与既有本人审定；未变条目才能继承，新增说明不是新的批准记录。

规则局部修订新增数据项目时，已有变量定义须逐项原样保留，才可复用已读文字范围；删除或改变旧定义仍拒绝复用。每条原文关系另核实际目标及请求哈希：新项目／新条件不能继承旧判断，不因共享一页而自动成为已核内容。

### 7.2 投影

`EligibilityReviewProjectionService.project`（`app/services/eligibility_review_projection.py:874`）改为：存在最新工作稿时直接读取其结论；否则返回"尚未生成工作稿"并提供"开始审核"动作。删除"无已完成 prepared-review 时把全部谓词强制标为未核实"的分支（`:956-1001`）对主路径的影响。

### 7.3 置信计算（S7）

纯函数，输入为组件 decision、所用事实及其风险标记、判定方式（确定性／语义／研究者判断）、"未见记录"政策是否生效、资料范围内文件类型（上传时选择的资料类型）、窗内其他结果、禁用药前提，按 PRD §7.2 的七条规则依次判断，输出 `confidence` 与第一条命中原因；非四种结论时 `confidence=null`。父规则：子项按逻辑组合后，如任一被组合进结论的子项为低置信，父规则为低置信。之后应用 `work_draft_acknowledgements`：依据内容与计算方式均未改变的条款才沿用核实；实际`confirmation_kind`区分医学经理核实和构建者试用核实，后者不得显示成正式医学批准。计算版本改变时不得自动继承旧核实。

### 7.4 语义条款（S6）

- 关系型条件不可拆成互不关联的存在性命中：有源条件应保留对象、治疗／操作与对应结果、适用期间及当前节点限定。沿原资料要求和判断字段表达，仅改相关草稿并重新审定；不改普通用药史，也不通过独立找到药物和症状来证明治疗失败。D19的IN-03修订是本次规则数据变化，不是新增特定药物／季节的程序分支。
- 含书面判断的复合条件中，所有需原文核对的原子共享既有`source_context`与`correspondence_check`，不只给末尾判断原子：先核事件／治疗／采集、适用期间及对应结果，不能仅因同一受试者或早于节点就判关系成立。旧未收到该限定的目标失效，不连带重读相容兄弟。仍使用原`SourceRelation`、确定性组合和工作稿Job，不新建审阅入口或人工覆写库；模型返回正常或引文合法不证明对应关系正确。
- 语义命题（`AtomicPredicate.semantic_proposition`）：输入条件与当前节点有效原文，输出supports/refutes/not_found/unclear/conflict及逐字引用；引用失败是技术失败，不能改成not_found。已完成的批次保存；相反记录并列，不能任一批支持就忽略其他批反证。每批16个条件，当前短资料共享完整文字而不按页数机械截断；输入超过短批范围时明确技术问题，不假称已检索。结论低置信，数值计算独立；病例原答与运行回执受控本地保存。
- `work_draft_semantics`按已发布原子条件短批检索冻结的当前节点有效文字，复用现有产品传输与JSON解析；每批是既有work_draft_review Job的持久步骤，不新建队列。原始请求、完整回答和回执只保存在ArtifactStore，成功批次不因兄弟失败重读。对应病历诊断、疗效、意愿、明确否认可用于关系核对，不要求另写判断或签字。逐字引用单独保存source_read_refs，不伪造ClinicalFact、A/B读道或作者元数据。数值、单位、均值及日期计算仍由原求值器完成；模型仅提出来源关系，不输出入排结论。
- 数值型病史／用药条件可检索原件对完整条件的明确否认，不将否认补成零数量；普通检验／评分继续用已发布数值。已有合格数量的确定性结果及事实引用不被未知原文覆盖；相反关系保留为矛盾。含书面判断的组合条件向读者一并提供完整组合、例外和当前已审定资料要求，不能只传脱离限定的单个条件。未见这些限定的旧答案不复用于受影响目标，但同一旧请求中其他未变目标仍经原始请求／原答／冻结规则核对后复用；不重构旧提示、不改旧结果。
- 用户D15：入选缺正向支持仍证据不足；排除按完成核对的本次资料未见相应不合格依据可范围性未触发，明确标低置信与资料范围，不冒充否认或NCS。不可读、实际冲突或真实异常不得套用该政策。组合复用现有表达式；只有在未知子项取true/false均不改变已证结果时，才不让无关资料要求阻断；相关未知仍保留。普通通用值不证明研究者判断、实际用药或未来意愿，须原文关系。高后果分歧在验收前核原件；不以颜色、测试或关系数量作为临床正确度。
- 上述未见事件政策仅用于主表达式中逻辑正极性的`exists`或`eq True`事件原子；`NOT`内、`eq False`及例外原子不得因缺记录得到肯定或否定。按现有表达式的嵌套极性逐叶限定，保留独立数值／例外的原政策；原始来源关系记录不改写。无法关联的独立资料要求继续阻断并明确列出，不能用既有症状否认替代尚未建立关联的检查结果。

- `WORK_DRAFT_SEMANTIC_PROVIDER/MODEL/REASONING_EFFORT/MAX_TOKENS`只覆盖本角色，未配置时沿用抽取角色身份；不改变旧抽取／OCR／方案任务。病历角色的模型身份含实际提示版本与传输选择。cms-router使用既有流式累积，必须收到实际模型与正常结束；不将私有思考内容作为业务证据。
- 实际直接`propose_question_classifications`不消费规范化专用`include_source_categories`；仅本角色身份和复验中排除这一非操作参数，不连带排除实际提示／Schema／来源／预算／模型参数核对。旧请求工件与新校验证明分开保存，来源或语义改变仍按受影响范围失效。
- 每批格式修正与length恢复共用最多两次实际请求；已用完不再叠加。401/403/429访问受限中断后续重复请求；超时是技术失败，不表示原件缺失，也不自动扩大读取范围。
- 格式层给模型显式短目标／页编号及枚举，宿主保存可逆表，严格解码后再逐字核对；不猜截短的旧编号。只去除空字段及目标自身的机器编号，保留所有原文、否定、数量、时间、例外和其他依赖标识。对象／时间未核清或“未见”附相关摘录仅保留未知读数，不进入确定结论、不套未见记录政策；来源失配仍拒绝。
- 引用仅差原文换行时，复用原定位函数找到同页唯一范围，并还原为该范围的逐字原文；改字／改标点／空格合数／数字跨行／多重匹配仍拒绝。原答不改；旧实际请求和原答可经当前校验重新取得证明，不刷新模型额度。两个答案复验后方向不同，保存双方工件并将读取分歧列技术待核，不能自动宣称患者原件互相矛盾。只有两答均UNKNOWN、适用且policy=false、对象及时间已核、页集合相同并有共同逐字摘录、无已有真实方向分歧时，conflict／unclear分类差异可保留为忠实未知；原理由和两工件引用保留在复验证明，不合成临床阴性。显示只净化说明中的临时编号和关系标签，原始摘录／临床读数不净化；未见记录的逐页检索范围默认折叠，仍可逐页打开原件。
- 已知合法页的摘录误标页码时，只在同一冻结文件版本、当前有效来源范围中查逐字原文；全文件恰好出现一次才保存原声明页→实际页的定位复验证明。未知别名、跨文件、重复文字、改字及跨页换行拼接不恢复，不丢掉坏摘录换取成功。原答／旧终态不改，证明记录实际校验版本；引用恢复不等于医学关系已核实。
- 回答原样附带输入version／stage／anchor_dates时，先严格核三者与实际请求完全相同，再抽取results；新增判定字段／错节点／错日期仍拒绝。此类一致附带信息不是目标越界，不触发无必要全批重答。旧匹配回执按实际存储请求及相同逐项门槛复验，不能用当前提示替换旧版本反算历史。
- 适用范围与来源身份分开：`object_matches/time_matches`证明摘录属于本受试者、判断对象及有效期间，不等同于适用人群。人群限制来自原条件`applicable_population`或本项已发布方案原文（含条件主体与流程脚注）；后者必须独立返回逐字`population_scope_excerpt`，校验仍核患者原件，不能只据检查名称、缺报告或无关兄弟范围跳过。只有方案限定和病例归属均有据，才能`applicable=no`；真歧义保留。计算与REQ消费者再核范围摘录属于自身来源，只剪去已证不适用项，不改已发布规则。新增`scope_only`读取只核范围，数值／分类结果仍用确定性事实计算。旧请求按实际旧Schema复验，已完成操作及未改语义继续复用；旧读道被禁止核脚注范围的未决项不能假称已核过新维度。
- 正向原文关系不跳过日期计算：带时间约束的条件，还须同一准确摘录的已采用观察、合法采样／发生记录日期及已核锚点，经既有日历求值和选择函数核实在窗内；报告日期不替代发生日期。缺日期／锚点或摘录对应不明确时只保留相关记录及具体未决，不用模型的支持信号代算时间，不将一条窗外记录当成整个窗内明确否认。
- 分组不改变复用资格：入队前先按完整当前目标集核实际旧请求、原答及来源，再将未完成目标优先装入短批。执行时同样核完整当前目标集，之后取本批交集；不可用新子集要求旧整组恰好相等，造成已成功内容重读。幂等键以固定目标集而非缓存命中或分组顺序形成；计算版本进入结论核实身份，防旧人工核实状态沿用到改变后的求值器。
- 组合后的资料要求仍按确证依赖消费：对共同原始要求，派生绑定的内容身份完全一致，且每项已观察或经真假反事实证明不影响当前结论时，才闭合原始要求；没有绑定证明或内容已变的独立要求仍保留。已有明确否认的ALL不额外索取无关兄弟判断，相关未知仍阻断。原文关系说明不得覆盖仍缺少的定量操作数，结果原因须列明未核项目；原文摘录不改，说明中的传输词即使没有摘录也统一转为中文。
- 同一组件的依据按条件保存为可选`WorkDraftItem.reason_parts`：条件身份、名称、原说明及是否影响当前未决。标记沿经过日期／数值核验的最终表达式中未决分支追溯，不直接采用模型方向，也不将逐叶反事实无变化当作多个未知兄弟共同无影响；缺少定量操作数不得隐藏。父项只汇集当前节点子项。原汇总及引用保持，旧空字段不参与序列化以保留历史哈希；API和前端拒绝重复条件或非布尔核对标记。未决详情先展示相关待核条件，其余条件和完整原汇总折叠可达；保存、读取和展示不触发额外模型调用。
- 来源故障从calculate经严格`SystemIssue`装配进入compose及保存稿，不能丢掉而升格置信。REQ故障按冻结流程目录的真实`item_id`关联，目录失配明确拒绝；不靠伪造IN/EX编号或模糊字符串传递影响。忠实restricted组件沿现有投影显示具体限制及未核维度，不填共享时间窗或改成可求值。
- 规则包新发布后，工作台读取可能仍因节点旧版本拒绝；只有目录确认同规则谱系存在新修订时，展示原工作稿入口，由用户主动更新，仍由后端核患者、原件、节点及版本合法性，不自动写入或绕过来源错误。完成后重新读取节点和结果，清除旧结果专属链接。
- 新规则修订的关系复用沿用现有临床来源相容条件：同项目／受试者／节点／快照／处理修订、原方案文件哈希／期别／变量定义及实际访视范围。旧请求先对旧冻结规则的完整目标验证，再逐项取与当前目标语义及来源完全相等的读数；删除／改变一个条件不让未改兄弟整组重读。改变对象、来源、时间、变量、提示语义或模型仍拒绝；成功抽取状态只属于抽取运行，不给工作稿捏造同名状态。重新计算结论不复用旧批准或旧结果。
- 流式保活仅作传输信号，不计模型身份／用量；带正文、思考或终止内容的保活标识拒绝。网关请求别名可与首个实际模型名不同，但同一有效内容流不能切换模型。此身份保护与请求回执绑定；未加载补丁的旧真实调用必须另列，不能用后来的单测冒称旧调用已按新保护运行。
- 复用现有Job检查点及原始请求／回答：同受试者、节点、来源文字及元数据、原子目标、模型／参数和实际语义指导完全相容时，重新核验旧读数并保存新证明；只改格式版本不重读合格内容。旧合格方向不得变化，旧未知不得提升；原先只因完全一致身份回显或唯一换行差异被拒的原答可在当前完整核对后取得来源资格，不代表医学批准。其他未通过内容只保留未知；新增可恢复原答若方向冲突仍列矛盾。模型、来源、条件、语义指导或输出合同变化拒绝复用；坏工件哈希硬拒，不伪装缓存未命中。研究者判断已检索而仍缺支持时按用户D14列证据不足，未完成检索仍系统问题。

## 8. 更正、补证与重算

- 更正：沿用 `apply_prepared_fact_correction`（`app/services/fact_correction_service.py:1121-1275`）；可更正字段增加 `variable_id`。
- 所属审核项目：`fact-corrections/facts/{fact_id}/options`只读当前节点已发布字典及精确事实修订；不提供派生倍数作原值选项。选择不自动换值／单位／类型；服务核类型、单位及作用域，变更关联时重建对应资料要求，清除关联则只保留档案记录。显式变更的两侧快照同时含`variable_id`，旧格式与旧hash不改；更正历史按冻结规则显示中文名称，不露内部ID。节点级影响无法逐项列清时不显示全零计数，不把未知范围冒充无影响。
- 规则单独更新后的来源复用：复用既有来源相容判断，逐项核同项目／受试者／节点／快照／处理修订、方案文件哈希、期别及完整旧变量定义。工作稿更新可确定性追加当前Profile，沿用真实事实ID及来源身份，不复制或改写旧事实、不重跑OCR／抽取；默认正式事实选择仍要求原权威完全一致。补证的逐文件来源及累计派生引用按§4.5复验；更正保存新事实于当前权威，原快照／更正谱系与旧报告不改。复用证明不是医学批准，也不修改来源强度或已核标记。
- **更正后的自动重算**：0.2.0更正Job冻结`work_draft_recompute`，沿用plan→apply，再追加独立work_draft步骤。apply先原子保存更正及提交证明；第三步重新核当前节点／已发布规则，调用既有`WorkDraftReviewService.start`，保存子Job关联。不在apply事务内调用后续核对：后续故障只重试失败步骤或子Job，不回滚已提交更正、不重复发布。路径绑定的`fact-corrections/jobs/{job_id}/work-draft`读取实际关联与终态；界面只有新稿真正保存才显示完成。旧两步任务及其幂等身份不改，未配置数据字典的旧链不自动接入。增量上传的自动衔接仍待完成；现有整理finalize已会排队工作稿，不能再造第二套队列。
- **结论核实**：`work-draft-confirmations`显式操作仅接受当前、完整且来源闭合的已保存低置信确定父项；未决／矛盾／系统问题、未完成子项和未核来源不允许点击变通过。冻结材料与计算版本须仍匹配，原值、结论与旧版均不改。以既有3步Job复制已验证的完整结果，仅提升目标置信，保存新run及supersedes；无语义读取步骤，不重新OCR或调用模型。重复提交读原Job，不重复追加。普通重新计算及整理后自动工作稿的身份均冻结核实集合；临床内容、来源或计算方式变化时不继承旧核实。报告／导出同样保留`confirmation_kind`；构建者只写`builder_verification`，旧未知规则身份保守显示验证用。界面不收集评估理由，失败不显示成功；保存后回到同条新版，不携旧item_id。其真实试用不替代M2数值更正／补证。
- 新工作稿写 `supersedes_review_run_id`；前端在工作稿顶部显示"第 N 版（较上一版：结论变化 x 条）"，可打开旧版。

## 9. 前端

| 页面／组件 | 改动 |
|---|---|
| `EligibilityWorkbenchPage.tsx` | 默认问题列表＋宽判定详情；点来源打开宽幅原件侧栏，关闭恢复当前选择。保留全部条款与历史；不为入组决定收集评估理由 |
| 文案 | `frontend/src/domain/labels.ts:64-76` 与后端 `_DECISION_LABELS`（`eligibility_review_projection.py:114-126`）统一为 PRD §7；修正后端把 `professional_judgment` 标为"无法判定"的不一致（`:121`） |
| 置信 | `eligibilityReviewTypes.ts`、`eligibilityReviewViewModels.ts` 保留 `confidence`、`confidenceReasons`；结果页低置信只留简短标记，具体原因不占正文（可悬停查看）；不是删除原回执或改置信等级 |
| 系统问题栏 | 工作台右上角"系统问题（n）"抽屉，列出受影响条款与替代路径 |
| 方案页 | 每条规则"审定通过"；范围清单确认步骤；去掉跨章步骤；发布按钮条件改为 R-A8 |
| 更正对话框 | `ProfileFactCorrectionDialog.tsx` 增加"所属变量"选择；操作完成后提示"已开始重算" |
| 截图 | Playwright 在 1920×1080、2560×1440、3840×2160 三个视口截图，文件名含视口，测试断言三张截图哈希不同 |

### 9.1 阅读层级（D18）

`ProtocolRuleReviewPanel`以条款／重点标识→实际逻辑→可展开备选比较／资料要求→原文位置／历史组织。A/B/C使用当前解释、仅有源推荐和调整影响，不为每个常规OR宣称歧义；多子项默认列可展开的组合摘要，备选也按子项独立展开、仅默认打开首组，避免同类分析一次铺满页面。`displayProtocolSourceLocators`只折叠完整来源身份相同的重复显示；原始mapper、ID、来源资格和审定哈希不变，位置未知或不同不能按文字合并。手工弹层的精确重复摘录只展示一次。

逻辑树优先显示条件已有的中文含义，不能被通用数据项目名称覆盖并丢失关系、范围或否定；内部英文属性才使用已绑定的中文项目名。连续同源修订的审定继承逐层核实际生成／来源冻结回执、已发布基线与逐条内容身份；不得把当前来源改版本号后当作历史来源，也不新增签名。当前撤销及中间撤销优先，缺来源证明不继承，循环链拒绝。历史记录自身哈希及审定人类型不改。

`EligibilityWorkbenchPage`去完整研究名称，以项目代号、节点和版本识别；中栏权重增大，提供列表收起／恢复。判定理由按中文句界与已有项目标签排版、显式使用分点标记，不生成新医学摘要；原件区保留当前摘录，其他依据及核对范围按需展开，冲突仍显式保留。工作稿操作和次要方法说明下钻，已有更正及取证入口不改。工具栏“定位当前查看页”只滚动到正在浏览的页；“返回本条依据页”恢复该条真实来源及摘录，两者不混淆。实际Ego三宽屏与点击已检查，实际浏览器缩放尚未验证；构建／视口模拟均不能冒充全部视觉验收。

2026-10-14 展示纠偏：全局导航为可叠加展开的图标轨；原件侧栏用原生dialog承载既有查看器，负责焦点、Esc、滚动隔离，不新建来源数据层。个例默认时间线，由现有Profile条目的原始时间与值派生，只分组显示、不合并独立观察、不推断缺失日期；无日期的内容单列。来源强度、生成信息及修订谱系下钻，风险与真实未决仍可达。规则备选通过既有手工编辑／审定入口执行，不让说明文字冒充可选动作。

时间图按既有语义分区生成病史／用药两组对象行；相同对象只归同行，不合并源记录或计为独立采集。点代表确切日，虚线范围代表日期精度，只有事件／暴露明确起止才能画持续条；不以月份推断疗程，无日期另列，近一年筛选保留更早记录入口。点选后才展开`ProfileItemCard`详情／原件。检验主层仅报告已标异常或严格同一断言行数值与参考范围比较的高／低（`reference_abnormality`）；未知不能当正常，不计算CS或入排。完整记录仍按类型可达，已有冲突区不删。

`PatientProfileService.fact_display_metadata`按已存事实精确ID批量只读补充`date_role/reference_abnormality`，核同项目／个例／节点／资料处理身份、源修订、值／单位／极性／对象／日期范围及定位一致；不重新采用或改变Profile hash，不要求新规则下重读旧资料。报告日、采样日、就诊日分别展示，未知用途为原文日期。`SourceExcerpt`对当前对象及条款共有的原文字面加粗／着色，不改文字、数值或否定，不作语义判定。现文字OCR读道无已核坐标；原件查看器已有真实坐标转换及红框，只对authenticated bbox使用，无坐标仍定位原页。普通来源只铺当前摘录，其他来源可选；真实冲突并列。规则所选修改未保存前，单条及跨条目批量批准不得将旧解释当已完成修改。

## 10. 评测工具

- `scripts/import_manual_ie.py`：读 CSV／Excel（列：`subject_id, stage, official_code, manual_conclusion, note`；`manual_conclusion` 取值：满足／不满足／未触发／已触发／不确定），写入 `data_v2` 下的评测表，不进入任何提示词。
- `scripts/compare_with_manual_ie.py`：按受试者×节点×条款对齐最新工作稿，输出 PRD §9 指标与差异清单（CSV＋Markdown），每行带系统依据与页码，便于 MM 判定差异归类。

## 11. 移出主路径的 0.1.x 组件（保留代码，不删除）

| 组件 | 处理 |
|---|---|
| 跨章控制链（`protocol_control_execution`、`protocol_control_*` agents／gates／contracts） | 不在主流程排队；相关测试保留 |
| prepared-review 子任务链（`prepared_review_workflow.py` 及绑定资格等子任务） | 不再由前端调用 |
| 逐页双 VLM、页判读 main-A/main-B | 不默认运行；局部视觉复核保留为手动入口 |
| 方法采用 gate（`ENROLLMENT_REVIEW_METHOD_APPROVAL_GATE_ID`） | 保留旧正式签发消费者，不进入0.2.0工作稿／展示主路径 |
| v1 应用（`app/main.py`、`app/router`、`app/pipeline`、`static/`） | 保持只读；`run.sh` 改为启动 v2（0.2.0-WP0） |

0.2.0-M3 之后再评估是否删除上述代码。
