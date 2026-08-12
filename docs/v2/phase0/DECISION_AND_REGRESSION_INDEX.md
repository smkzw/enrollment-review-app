# V2 冻结决定与回归索引

**核验日期：** 2026-08-12

**范围：** 产品决定、架构决定、历史高价值错误族及其未来验证层
**状态：** 冻结索引，不是实现说明，也不代表整个 Phase 0 已完成

## 1. 证据和权威顺序

### 1.1 事实标记

| 标记 | 用法 |
|---|---|
| OBSERVED | 当前源码、测试、日志或命令直接观察到的事实。 |
| FROZEN | 用户确认、最终设计或会商已经冻结，后续实现不得自行改写的决定。 |
| REGRESSION | 历史错误或反面案例，只能转成通用 fixture/gate/test。 |
| PENDING | 需要未来实现、独立 checker、UAT 或临床验证；当前不得宣称通过。 |

### 1.2 权威链

1. 研究方案和当前正式修订案决定 IN/EX 标准、版本、编号、逻辑、阈值、时间窗和例外；
2. Q&A、澄清函、邮件和医学解释只能解释歧义；若与方案或当前修订案冲突，必须告警并阻断争议组件，不能伪装成新方案版本；
3. 旧项目、旧报告、模型输出和历史人工结论是只读反面锚点与回归输入，不迁移为 V2 业务真相；
4. Agent 只能提交结构化候选，确定性 gate 才能接受规则、事实、判断、Action 和汇总状态；
5. 本索引不包含病历原文、密钥、原始审计事件或可识别受试者内容。

## 2. 冻结产品决定

| ID | 决定 | 后续必须保持的可观察行为 | 证据定位 |
|---|---|---|---|
| P-01 | 本地单 Mac、单用户、直接进入；不做登录、多账户、owner/admin 或审批流。 | 首屏不依赖账户所有权；系统输出是 AI 辅助底稿，不是最终入组决定。 | docs/REARCHITECTURE_FINAL_DESIGN_20260812.md §1、§2；context/enrollment_review_rearchitecture_20260812_context.md 决策记录。 |
| P-02 | 研究期别与审核节点是两个维度。独立 II 期、独立 III 期和非无缝 II/III 分开；只有方案明确 seamless/adaptive 且队列连续过渡才合并。 | Project、RuleSet、ReviewEpisode 各自保存期别和节点；不能靠文件名或模型总结推断混合范围。 | 最终设计 §2、§4；tests/test_phase_workflow.py:134-240,337-386。 |
| P-03 | 增量上传和全量上传语义不同。 | 增量按内容去重、合并并只重算受影响范围；全量创建新完整 EvidenceSnapshot；旧快照不删除。 | 最终设计 §2、§9；实施计划 Phase 4。 |
| P-04 | 后续阶段资料不静默改写早期结果；回顾重审必须创建新的 ReviewRun。 | 早期 ReviewRun、证据快照和报告保持可重现；跨阶段变化以 diff 和新运行记录呈现。 | 最终设计 §2、§9；tests/test_phase_workflow.py:572-845。 |
| P-05 | 原文件和原 OCR 不变；校对值、理由、确认和影响范围另存。 | 极性、数值、单位或日期变化须显式确认，并只重跑受影响范围。 | 最终设计 §2、§4.2；实施计划 Phase 4。 |
| P-06 | 来源冲突并列展示并阻断争议组件；不得按“既往优先”或“当前优先”自动择一。 | ConflictGroup 可追踪；无解决记录不得形成明确组件状态；解决后仍生成新 ReviewRun。 | 最终设计 §2、§5、§7；reviews/codex_conference_enrollment_review_design_conference_20260812_review.md:27-38,55-59。 |
| P-07 | Patient Profile 是从最早可证明事件到当前节点的来源链接纵向视图。 | 首屏突出入排相关、异常、临界和趋势；“未记录”显示为 EvidenceExpectation 缺口，不生成虚假正常/阴性事实。 | 最终设计 §4.2-§4.3、§8.4；会商上下文决策记录。 |
| P-08 | 每个未明确组件都必须有责任方、行动、可接受证据、到期节点、阻断等级和来源定位。 | ActionRequest 可计数、可追踪、按具体组件关闭；关闭不等于规则通过。 | 最终设计 §5.3、§6；实施计划 Phase 7。 |
| P-09 | 先用版本化 fixture/API 合同和真实前端壳做原型，经脚本化、量化 UAT 后才进入数据库/后台核心实现。 | 原型不读取旧 Markdown 作为 UI 真相；Phase 1.5 是 Phase 2 的硬门槛。 | 最终设计 §2、§11-§12；实施计划 Phase 0.5、Phase 1、Phase 1.5。 |

## 3. 冻结架构决定

| ID | 决定 | 强制不变量和未来验收 | 证据定位 |
|---|---|---|---|
| A-01 | 临床真相使用结构化、版本化领域记录，不以 Markdown 或单一 overall_verdict 为业务真相。 | Project、ProtocolDocumentVersion、RuleSet、RuleComponent、Fact、EvidenceSpan、Assessment、Action、ReviewRun 可独立追踪；报告只是投影。 | 最终设计 §3-§5、§10；app/models.py:17-65 为 legacy 反面模型。 |
| A-02 | 首版采用 SQLite/WAL、持久 Job/Checkpoint、显式状态机和可测试状态转移；LangGraph 仅保留为后续候选。 | 浏览器关闭不拥有任务生命期；重启可恢复；不会永久 processing；迁移可备份/回滚。 | 最终设计 §3.1、§9；实施计划 Phase 2、统一验证矩阵。 |
| A-03 | Agent 是有界、类型化、候选输出节点；Agent 不能直接写最终组件状态。 | Schema、输入范围哈希、PromptVersion、模型、尝试次数、GateResult 和原始输出哈希可审计；Gate 失败停在候选/人工处理。 | 最终设计 §7；reviews/codex_conference_enrollment_review_design_conference_20260812_review.md:31-32,43-47。 |
| A-04 | 逻辑、编号、父子关系、阈值、单位、日期/时间窗、例外、阻断等级、状态汇总和 Action 转移必须由确定性代码实现。 | 禁止用正则把无效 Agent 输出修成通过；任何不符合状态/缺口矩阵的候选被拒绝。 | 最终设计 §5-§7；实施计划统一验证矩阵 L1。 |
| A-05 | Safety/Provenance Critic 条件触发、独立、只可 veto/downrank/open_action，不能静默改写 assessment。 | 仅在高风险规则、冲突、OCR 极性/数值风险或 Gate 异常触发；Critic 失败保留原判断并标记待重试。 | 最终设计 §7.0、§7.2、§12。 |
| A-06 | EvidenceSpan 使用可见的定位精度阶梯：bbox、text_range、page_excerpt、page_only。 | 前端显示实际精度和降级原因；没有可靠坐标时不得伪造高亮。 | 最终设计 §4.2、§8.4；实施计划 Phase 4。 |
| A-07 | EvidenceRequirement 投影为 EvidenceExpectation；判断状态与 gap_type 分离。 | observed/observed_weak/referenced_missing/absent/not_due 与 record_incomplete、referenced_file_missing、required_procedure_not_done、professional_judgment、source_conflict、ocr_or_parse_risk、future_stage_not_due 等不混用。 | 最终设计 §4.2、§5.2-§5.3；实施计划 Phase 5-6。 |
| A-08 | V2 有独立命名空间和 storage root；legacy 只提供显式只读适配。 | V2 写目标不得落入 legacy 项目、旧报告或审计树；快照测试在 V2 操作前后比较受保护树内容。 | Phase 0 design.md；最终设计 §9-§10；BASELINE_MANIFEST.md §7。 |
| A-09 | 前端是新的 React/TypeScript/Vite 产品壳，fixture/API 合同先于数据层；不把旧单文件 SPA 或自由文本审核器直接升级为 V2 核心。 | UI 读取结构化合同；桌面/窄屏、证据定位、空/错/stale/恢复和键盘路径进入真实浏览器验收。 | 最终设计 §3.3、§8、§10；实施计划 Phase 1、Phase 1.5。 |
| A-10 | 所有业务变更都保留 revision、stale 影响范围、AgentCall/GateResult、ActionTransition 和 ReviewRun diff。 | 旧事实不被覆盖；受影响投影可重建；报告可回到方案版本、RuleModelRevision、EvidenceSnapshot 和 EvidenceSpan。 | 最终设计 §6、§7、§9；实施计划 Phase 2、Phase 7。 |

## 4. 历史高价值错误族

以下错误均以通用不变量登记。未来 fixture 可以使用最小、去标识化或合成事实；不得把当前项目的规则编号、受试者结论或硬编码后处理搬入 V2。

| ID / 错误族 | OBSERVED/REGRESSION 证据与失败模式 | 冻结不变量 | 未来 fixture / gate / test 层 |
|---|---|---|---|
| R-01 AND/OR 弱化 | app/deconstructor.py:38-55,112-124 和 tests/test_phase_workflow.py:291-335 覆盖“异常 + 有临床意义 + 研究者判断”被压成单一异常触发。 | ALL/ANY/NOT、括号、父级/子项和研究者复合判断必须保真；缺任一 AND 组件不得判明确障碍。 | Fixture：RuleExpression 的嵌套 ALL/ANY/NOT 与缺组件矩阵；Gate：表达式求值、Schema、Assessment 一致性；Test：L1 单元/变异测试，L2 Agent 候选评测，L3 错误族回归。 |
| R-02 指标串项/交叉规则污染 | SYSTEM_REVIEW_REPORT.md:68-70；tests/test_phase_workflow.py:1100-1146,1590-1605 覆盖以不相干指标替代目标指标或把一个规则的实验室事实带入另一规则。 | 原子谓词必须绑定对象、属性、单位、阈值和 RuleComponent；相似名称不能替代；事实引用必须在组件范围内。 | Fixture：目标指标、相似但不等价指标、单位和缺失值组合；Gate：对象/属性/单位/阈值精确匹配与组件依赖；Test：L1 property/mutation、L2 Normalizer/Assessor、L3 临床回归。 |
| R-03 否定词、沉默和极性误读 | tests/test_phase_workflow.py:1771-1777,1509-1526 与最终设计 §5.4 约束“明确否认有证据，沉默不是否认”；OCR 低质量极性不得直接形成结论。 | negated/affirmed/unknown、时态和确定性单独存储；未提及只能生成记录完整性缺口，不得生成阴性事实。 | Fixture：同一概念的明确否认、明确阳性、沉默、否定范围跨句和 OCR 不确定文本；Gate：极性/范围/确定性与 EvidenceSpan；Test：L1 语义状态、L2 抽取评测、L4 OCR gold page，极性错误为 0。 |
| R-04 例外条件错配 | app/deconstructor.py:49-55、tests/test_phase_workflow.py:321-335,1249-1282 覆盖例外缺一个组件仍被当作例外通过，以及研究者判断被泛化替代。 | 例外是独立表达式树，触发项、例外项和研究者明确判断必须全部可追溯；笼统“可入组/无不适”不等价于指定判断。 | Fixture：触发项、完整例外、部分例外、相似但不等价判断；Gate：例外树完整性、证据要求、状态/缺口矩阵；Test：L1 表达式/状态，L2 Assessor，L3 例外回归。 |
| R-05 阶段、期别、锚点和时间窗错配 | tests/test_phase_workflow.py:134-240,525-845 覆盖筛选与基线、II/III、未来节点、洗脱期和缺失基线锚点不能混用；app/phases.py:14-40,65-86,181-200 定义现有阶段范围。 | Project stage、ReviewEpisode、anchor date、document phase 和 due status 必须是独立字段；缺锚点不能借用筛选日期或文件名；未到期不等于当前缺证据。 | Fixture：跨阶段同一事实、缺失/部分日期、未来要求、洗脱窗口边界；Gate：阶段过滤、日期上下界、due/not_due、ReviewRun 隔离；Test：L1 日期属性/边界、L6 API、L7 E2E。 |
| R-06 证据状态与判断状态混淆 | app/models.py:17-23 的 legacy 五态、tests/test_phase_workflow.py:679-711,865-899,1509-1526 与最终设计 §5.2-§5.3 共同显示：证据不足、需研究者、溯源提醒、未来复核和明确不符合不能合并。 | state 与 gap_type 分离；record_incomplete、referenced_file_missing、required_procedure_not_done、professional_judgment、source_conflict、future_stage_not_due 各有责任方和关闭谓词；provenance_followup 非阻断但可计数。 | Fixture：同一 RuleComponent 的各 gap 组合及阻断等级；Gate：一致性矩阵、Action 生成/关闭、节点汇总纯函数；Test：L1 truth table、L6 API、L7 UI 计数与排序、L12 人工验收。 |
| R-07 父子层级、官方编号和汇总错位 | app/deconstructor.py:35-36,112-116、tests/test_phase_workflow.py:933-959,1414-1468 覆盖重复父级、漏父级和一个子项的状态污染兄弟子项。 | 官方 IN/EX 父级数量、顺序、编号和 parent_id 不变；子项是 RuleComponent，不升级为新父级；父级汇总只消费其真实子树。 | Fixture：父项、多层子项、重复/缺失父项、同前缀非同父项；Gate：编号/树形/schema/rollup；Test：L1 tree/property/mutation、L2 Deconstructor、L3 方案回归。 |
| R-08 OCR 幻觉、数值/单位/日期和定位污染 | SYSTEM_REVIEW_REPORT.md:161-220 记录重复幻觉、数字污染和无意义 OCR；tests/test_phase_workflow.py:1700-1777,2903-2925 已有并发、极性、幻觉和来源一致性回归。 | 原 OCR、页图和校对值分层保存；重复、极性、数值、单位、日期和定位风险必须可见；低质量页不能直接产生明确结论。 | Fixture：原生 PDF、扫描、照片、手写、重复文本、关键小数/单位/否定词；Gate：内容哈希、质量/风险、EvidenceSpan 定位阶梯；Test：L4 OCR gold pages、L2 事实评测、L6 上传/重跑幂等。 |
| R-09 ICF/日期来源串用 | SYSTEM_REVIEW_REPORT.md:225-285 记录 ICF 日期从沟通类/其他受试者材料误取；app/subject_dates.py:91-145 和 tests/test_phase_workflow.py:2763-2823,2878-2902 约束来源类别、受试者一致性和合理日期。 | 日期必须绑定 SourceDocumentVersion、证据类别、受试者、事件语义和精度；版本日期、沟通日期和 ICF 事件日期不可互换；手工确认不能被缓存回填覆盖。 | Fixture：同页多日期、版本日期/签署日期、其他主体 ID、沟通类与筛选记录冲突、部分日期；Gate：来源/主体/事件/合理性/人工 override；Test：L1 日期属性、L4 OCR/date、L6 API 回填与审计。 |
| R-10 来源冲突和自动择优 | 会商审查确认 legacy prompt 的来源偏好与“不自动择一”边界冲突；reviews/codex_conference_enrollment_review_design_conference_20260812_review.md:27-38,55-59。 | 冲突事实进入 ConflictGroup 并列展示，争议组件不得明确；只有来源链接的解决记录和新 ReviewRun 才能改变状态。 | Fixture：当期/既往/解释材料互相冲突及无冲突对照；Gate：冲突检测、hard block、resolution predicate；Test：L1 conflict predicates、L2 Critic、L6 API、L12 盲后比较。 |
| R-11 模型漏审、缺规则和自由文本修补 | tests/test_phase_workflow.py:780-822,1635-1657 覆盖模型漏掉官方 Rule ID 时补为证据不足；SYSTEM_REVIEW_REPORT.md:369-383 记录规则编号硬编码和约 50 个后处理 guard 的维护风险。 | Agent 输出必须声明覆盖范围并经 Schema/Gate；漏项停在失败/人工处理，不用正则改变临床语义；V2 规则编号由输入 RuleSet 驱动。 | Fixture：漏规则、重复规则、排序变化、措辞变化和无效 JSON；Gate：覆盖、Schema、幂等、拒绝而非修补；Test：L0 contract、L1 parser/gate、L2 Agent eval、L3 known-error regression。 |
| R-12 V2 写边界越界 | legacy 路径曾承担业务写入；V2 若复用旧 root 会破坏只读回归锚点。 | V2 只能写 V2 root，legacy `projects/`、`output/` 和未声明 root 均拒绝；该边界属于数据隔离，不扩展为本阶段安全测试。 | Gate：canonical V2 storage root 与 legacy snapshot；Test：L1 写边界、L6 集成写保护。 |
| R-13 并发、重复提交和任务生命周期错位 | tests/test_phase_workflow.py:2931-2945 覆盖重复处理锁；最终设计 §9 要求 Job/Checkpoint、租约、幂等和浏览器关闭不取消任务。 | 同一输入/文件/模型/节点有幂等键；Job 状态不由 SSE 连接拥有；取消、重试、恢复和 stale 影响范围可审计。 | Fixture：重复上传/重复 Job、kill/restart、SSE 断开、部分 OCR 失败；Gate：lease/idempotency/checkpoint/stale；Test：L1 transition、L5 fault injection、L6 API/E2E。 |

## 5. 回归层定义与执行边界

| 层 | 目标 | 本索引中的主要覆盖 |
|---|---|---|
| L0 合同 | JSON Schema、API/OpenAPI、Job 事件、枚举和版本兼容。 | R-01、R-06、R-07、R-11。 |
| L1 确定性逻辑 | 表达式、阈值、单位、日期、树、状态矩阵、汇总、Action、幂等和写入边界；必要时增加 property/mutation test。 | R-01 至 R-07、R-09、R-12、R-13。 |
| L2 Agent 评测 | 在隔离的 gold fixture 上评估抽取/候选/批评；Agent 不写最终业务真相。 | R-01 至 R-04、R-08、R-10、R-11。 |
| L3 临床回归 | 只读 legacy 错误族转成盲后比较样本；偏差定位到规则、事实、Span、Agent 或 Gate 层。 | R-01 至 R-11；不导入旧结论，不运行项目特异补丁。 |
| L4 OCR/解析 | 分原生 PDF、扫描、照片、手写和表格的 gold page；检查极性、数值、单位、日期、幻觉和定位降级。 | R-03、R-08、R-09。 |
| L5 Job/恢复 | 故障注入 kill/restart、浏览器关闭、SSE 重连、重复提交、部分失败和恢复/取消。 | R-05、R-06、R-13。 |
| L6 API/集成 | FastAPI 合同、上传/快照、阶段隔离、Action 闭环、审计和只读写保护。 | R-05、R-06、R-09、R-10、R-12、R-13。 |
| L7 浏览器/视觉/可访问性 | 真实桌面和窄屏、证据定位、状态计数、stale/失败/恢复、键盘和无障碍。 | R-05、R-06、R-08、R-10、R-13。 |
| L11 原型 UAT | 在用户批准前测量任务完成率、错误结论、证据可达性和首屏/信息密度。 | P-07 至 P-09；不以截图或模型自评代替 UAT。 |
| L12 全流程 UAT | 新 V2 项目从方案创建开始，盲后与人工结果比较，逐条核对障碍、缺口、专业判断和来源。 | 所有临床错误族；必须在 Phase 8，不能在 Phase 0 宣称。 |

## 6. Fixture 和 gate 设计约束

1. 未来 fixture 使用版本化 fixture/v1 合同，包含最小 Project、RuleSet、RuleComponent、WorkflowStage、ReviewEpisode、EvidenceSnapshot、EvidenceSpan、ClinicalFact、Assessment、Action 和 ReviewRun；文本应去标识化或合成。
2. 每个 fixture 要同时保存预期不变量、触发证据类型、允许状态、禁止状态、阻断等级和来源定位；不能只保存一个最终 verdict。
3. 历史项目规则编号只保留在回归证据的 locator 中；V2 gate 按语义结构、树、属性、阈值、单位、时间窗和证据要求工作，不按项目编号写分支。
4. 旧项目和旧报告保持 read-only；临床回归只读入安全副本或结构化最小 fixture，比较在运行后进行，不能把旧报告注入 Prompt 或 V2 业务状态。
5. 任何失败先定位违反的不变量和所属层；不能通过扩大正则、增加项目特异例外、重写旧报告或提高模型调用次数来掩盖失败。
6. 只要 fixture 触及 OCR、日期、来源冲突或临床判断，就必须保留 source file、版本、页码/定位精度、事件语义和不确定性；不得在此索引复制病历原文。

## 7. 当前已知回归入口与待验证项

### 已有 legacy 反面入口

```bash
env PYTHONDONTWRITEBYTECODE=1 \
  /usr/bin/python3 -m pytest -q tests/test_phase_workflow.py
```

源码/测试定位：

- app/deconstructor.py:38-55,112-124,536-563：逻辑保真、例外和复合条件；
- app/phases.py:14-40,65-86,181-200：阶段范围与当前节点原则；
- app/subject_dates.py:91-168：ICF 来源、主体一致性、合理日期和人工回填；
- app/models.py:17-65：legacy verdict/报告模型，作为迁移反面锚点；
- tests/test_phase_workflow.py:291-335,525-845,933-1167,1249-1468,1509-1667,2763-2995：现有错误族和恢复/安全测试；
- SYSTEM_REVIEW_REPORT.md:68-70,161-220,225-285,369-383,531-537：历史错误与旧实现风险；
- docs/REARCHITECTURE_FINAL_DESIGN_20260812.md:2,20-80,132-220,221-505：冻结产品、领域、门控和架构决定；
- plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md:5-31,141-261：Phase 0 退出门槛与统一验证矩阵；
- reviews/codex_conference_enrollment_review_design_conference_20260812_review.md:27-59：独立会商采纳/拒绝边界。

### PENDING

- V2 fixture/v1、JSON Schema、OpenAPI、状态汇总真值表和 Agent contracts 尚未由本 Worker 创建或验收；
- legacy 错误族尚未全部转换为与项目无关的 V2 结构化 fixture；
- V2 Gate、写保护、Job 恢复、OCR gold page、真实浏览器、可访问性和 UAT 均需要后续阶段；
- 没有执行新的临床重审，也没有把历史报告判定宣称为 V2 结果；
- 当前工作树存在并行未跟踪 Phase 0/V2 文件，本索引只负责两个指定文档，不能替代独立 checker 的验收。
