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
│ H3 签发（0.2.0 仅记录）                                                                          │
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
| H3 签发 | human | 工作稿 | 签发记录 | 复用 `publish_frozen_review` 路径（0.2.0 只接记录） | — |

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
| 结论级"已核"：新表 `work_draft_acknowledgements` | 新契约 | `official_code`、`input_hash`、`acknowledged_by`、`at`、`note`。新工作稿中同一条款 `input_hash` 相同则沿用 |
| `SystemIssue` | 作为 `ReviewRun` 下的 JSON 列 `system_issues` 保存 | `kind`（`method_unsupported`｜`page_unreadable`｜`model_output_invalid`｜`excerpt_unverified`｜`extraction_failed`｜`component_unstructured`｜`fact_closure_failed`）、受影响条款、说明、替代路径 |
| 命名 | — | 现有 `_completed_work_draft` 指 prepared-review 结果；新代码统一用 `work_draft_review`／`WorkDraftItem`，不复用旧名 |

### 4.5 事实与规则包版本解耦（重要）

现状：`FactAuthority`（`app/domain/contracts/facts.py:94-111`）把每个已发布事实绑定到 `rule_set_id`／`rule_set_revision`／`episode_revision`／`evidence_snapshot_v2_id`；`fact_rule_index`（`app/domain/contracts/fact_rule_index.py` 文件头注释与 `:66-112`）和 `evidence_expectations`（`app/projections/evidence_expectations.py:221-225`）会丢弃权威元组不一致的事实。照此，规则包每重新发布一次、每补传一份资料，31001 的全部事实都会失效，必须整例重抽。

0.2.0 的做法：
1. **工作稿路径不使用 `fact_rule_index`／`evidence_expectations` 的修订一致性过滤**。`select_by_variable` 只要求事实属于同一项目、受试者、审核节点，且其 `evidence_snapshot_v2_id` 是当前快照或其祖先快照（快照是不可变全量＋去重增量，祖先关系可查）。规则包修订号与事实无关，匹配靠跨修订稳定的 `variable_id`。
2. **规则包重新发布后**：已有事实直接被新规则包使用；只有新增的 `variable_id`（新条款需要的变量）才触发一次补充抽取，抽取范围是全部页但需求清单只含新增变量。
3. **补传资料后**：只对新增或变更的文件做抽取（抽取缓存键＝文件版本哈希＋需求清单哈希＋提示版本），未变文件的事实沿用。
4. 现有 Profile 投影与 `evidence_expectations` 保持原逻辑（它们服务 Profile 页），不在 0.2.0 改造；REQ 判定在工作稿路径中按 `variable_id = procedure:<id>` 直接计算（§5.5），不依赖 `evidence_expectations` 的修订检查。

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
- **SAR（已有 rev21）不重新起草**：范围清单只作为条款的"定义依据"挂在对应规则上（存 `protocol_review_scopes`，审定页与工作台中可展开原文），并作为禁用药抽取（R-A4）的输入。
- **新方案（如 D001）起草时**才把范围单元加入官方解构的 `source_materials`／`allowed_source_span_ids`（`app/protocols/deconstruction_service.py:574-610`），同时让 `catalog_material_coverage` 检查接受这些单元（否则会因"材料多于目录"报错）。

### 5.3 静态检查重新分级（P5）

`ProtocolDeconstructionGate.evaluate`（`app/protocols/deconstruction_gate.py:1972-2024`）的 12 项检查按下表处理。`publishable` 的计算（`:2018-2022`）改为：**按检查名**判断，只有下表"结构性"检查中的问题（无论原级别是"阻止发布"还是"需要核对"）阻止发布；其余检查的问题一律作为提示返回。`blocking_count` 等按级别计数的字段相应改为只计结构性问题。WP1 第一步同时统计 rev21 在新分级下的结构性问题；能通过 MM 界面编辑解决的，用界面解决，不改代码。

| 检查 | 0.2.0 级别 |
|---|---|
| identity、parent_catalog、tree_integrity、boolean_logic、diff_integrity | **结构性**：阻止发布 |
| phase_scope、numeric、temporal、workflow_coverage、evidence_coverage、source_coverage、interpretation_authority | **提示**：显示在对应规则旁；MM 审定该条即视为已处理 |

### 5.4 逐条审定（H1）

- 后端：`POST /api/v2/protocol/deconstructions/{job}/draft/rules/{official_code}/review`（审定，请求体含 `reviewer_kind`）与 `DELETE`（撤销）；发布前检查全部 IN/EX／REQ／禁用药条目均有与当前内容哈希一致的 `RuleReviewRecord`。
- **构建者不得以医学经理身份审定。** 构建者在验证副本上走流程时，`reviewer_kind=builder_verification`，`reviewed_by` 写"构建者（验证）"。0.2.0-M1 要求至少一次由用户本人完成的 `medical_manager` 审定与发布。
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
5. `review_conclusions.compose(...)` 按 PRD R-C8 组合父规则，生成六结论、置信、原因、问题卡片、系统问题；`restricted_components` 记 `SystemIssue(component_unstructured)`；
6. 写 `ReviewRun(run_kind="work_draft", supersedes_review_run_id=上一版)`、`work_draft_items`、`system_issues`（§4.4），不写 `FinalAssessment`。

Job 幂等键：`(review_episode_id, 资料快照哈希, rule_set_id, rule_set_revision, 已核记录集合哈希, 代码中的计算版本号)`。

不经过 `prepared_review_workflow.py` 的子任务（LLM 双道绑定、资格、判断内容、命题、观察、频次、计算、历史检索），也不经过 `calculate_frozen_review`（它对受限条款会抛异常，`frozen_review_calculation.py:400`）。这些代码保留、移出主路径。

### 7.2 投影

`EligibilityReviewProjectionService.project`（`app/services/eligibility_review_projection.py:874`）改为：存在最新工作稿时直接读取其结论；否则返回"尚未生成工作稿"并提供"开始审核"动作。删除"无已完成 prepared-review 时把全部谓词强制标为未核实"的分支（`:956-1001`）对主路径的影响。

### 7.3 置信计算（S7）

纯函数，输入为组件 decision、所用事实及其风险标记、判定方式（确定性／语义／研究者判断）、"未见记录"政策是否生效、资料范围内文件类型（上传时选择的资料类型）、窗内其他结果、禁用药前提，按 PRD §7.2 的七条规则依次判断，输出 `confidence` 与第一条命中原因；非四种结论时 `confidence=null`。父规则：子项按逻辑组合后，如任一被组合进结论的子项为低置信，父规则为低置信。之后应用 `work_draft_acknowledgements`：`input_hash` 相同的条款置为高置信并注明"MM 已核"。

### 7.4 语义条款（S6）

- 语义命题（`AtomicPredicate.semantic_proposition`）：一次 LLM 调用，输入命题＋相关页有效文字，输出 `supports`｜`refutes`｜`not_found`＋逐字引用；程序核对引用，未通过视为 `not_found`。结论恒为低置信，直到 MM 已核。相关页＝资料类型为病历／门诊记录／出院小结的全部页＋命题关键词确定性命中的页；每次调用不超过 20 页，超出分批，任一批 `supports`／`refutes` 即采用并保留全部批次结果。
- 研究者判断：沿用 judgment_search 检索。注意它只选取 `required_source_types` 含 `investigator_assessment` 的资料要求（`select_judgment_search_requirements`，`app/services/judgment_search_job_service.py:81-103`），而不是按 `requires_professional_judgment` 选组件。因此 P4／发布校验须保证：凡含 `requires_professional_judgment` 谓词的组件，都有一条 `required_source_types` 含 `investigator_assessment` 的 `EvidenceRequirement`。新增对找到的摘录做逐字核对（复用 `fact_evidence_closure.py:296-310` 的包含判断）。核对通过→按记录内容给结论并引用；否则"需研究者判断"。

## 8. 更正、补证与重算

- 更正：沿用 `apply_prepared_fact_correction`（`app/services/fact_correction_service.py:1121-1275`）；可更正字段增加 `variable_id`。
- **自动重算钩子**：在 `app/services/fact_correction_executor.py` 应用成功后（约 `:150`）排队 `work_draft_review` Job（幂等键见 §7.1）。增量上传处理完成、"标记已核"（事实级或结论级）完成后同样排队；"已核"不改资料哈希，因此幂等键中包含已核记录集合哈希。
- 新工作稿写 `supersedes_review_run_id`；前端在工作稿顶部显示"第 N 版（较上一版：结论变化 x 条）"，可打开旧版。

## 9. 前端

| 页面／组件 | 改动 |
|---|---|
| `EligibilityWorkbenchPage.tsx` | 默认显示"问题卡片"视图（新组件 `IssueCardList`），点卡片进入现有三栏；保留"全部条款"切换 |
| 文案 | `frontend/src/domain/labels.ts:64-76` 与后端 `_DECISION_LABELS`（`eligibility_review_projection.py:114-126`）统一为 PRD §7；修正后端把 `professional_judgment` 标为"无法判定"的不一致（`:121`） |
| 置信 | `eligibilityReviewTypes.ts`、`eligibilityReviewViewModels.ts` 增加 `confidence`、`confidenceReasons`；高置信不显示标记，低置信显示"⚠ 低置信"与原因 |
| 系统问题栏 | 工作台右上角"系统问题（n）"抽屉，列出受影响条款与替代路径 |
| 方案页 | 每条规则"审定通过"；范围清单确认步骤；去掉跨章步骤；发布按钮条件改为 R-A8 |
| 更正对话框 | `ProfileFactCorrectionDialog.tsx` 增加"所属变量"选择；操作完成后提示"已开始重算" |
| 截图 | Playwright 在 1920×1080、2560×1440、3840×2160 三个视口截图，文件名含视口，测试断言三张截图哈希不同 |

## 10. 评测工具

- `scripts/import_manual_ie.py`：读 CSV／Excel（列：`subject_id, stage, official_code, manual_conclusion, note`；`manual_conclusion` 取值：满足／不满足／未触发／已触发／不确定），写入 `data_v2` 下的评测表，不进入任何提示词。
- `scripts/compare_with_manual_ie.py`：按受试者×节点×条款对齐最新工作稿，输出 PRD §9 指标与差异清单（CSV＋Markdown），每行带系统依据与页码，便于 MM 判定差异归类。

## 11. 移出主路径的 0.1.x 组件（保留代码，不删除）

| 组件 | 处理 |
|---|---|
| 跨章控制链（`protocol_control_execution`、`protocol_control_*` agents／gates／contracts） | 不在主流程排队；相关测试保留 |
| prepared-review 子任务链（`prepared_review_workflow.py` 及绑定资格等子任务） | 不再由前端调用 |
| 逐页双 VLM、页判读 main-A/main-B | 不默认运行；局部视觉复核保留为手动入口 |
| 方法采用 gate（`ENROLLMENT_REVIEW_METHOD_APPROVAL_GATE_ID`） | 只用于 H3 签发 |
| v1 应用（`app/main.py`、`app/router`、`app/pipeline`、`static/`） | 保持只读；`run.sh` 改为启动 v2（0.2.0-WP0） |

0.2.0-M3 之后再评估是否删除上述代码。
