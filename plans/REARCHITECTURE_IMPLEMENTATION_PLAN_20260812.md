# 入排审核系统 V2 分阶段实施计划

**2026-09-05 当前恢复入口：** 配套完整工程设计 `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` 与细化计划 `plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md` 已形成；本文件保留阶段编号、临床退出条件与历史。新 goal prompt 已写入当前 Trellis 任务，尚未设置新 goal。

**状态：** 已批准并实施中；2026-09-05 接管工程审查修订（R3，不变更临床裁决）
**设计基线：** `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`（2026-09-02 修订版）
**原则：** 每阶段有独立产物、验收证据和停止点；未通过前一门槛，不进入下一阶段。

## 阶段状态（2026-09-05 核对）

| 阶段 | 状态 |
|---|---|
| Phase 0 / 0.5 / 1 | 已完成并归档 |
| Phase 1.5 | 已完成（验收方式经用户批准改为多模型角色扮演 UAT，替代真人医学经理脚本 UAT） |
| Phase 2 / 3 / 4 | 已完成并归档（Phase 4 扫描页为 text-only，无坐标不画红框） |
| Phase 5 | 进行中，`claims_complete=false`；收口条件见“Phase 5 收口”一节 |
| Phase 5.5 | 正式逐页任务/API、取消恢复、覆盖绑定及整理入口已实现；GLM low + Gemini high 隔离24页双读已完成，runtime05整理15/15步骤但run仍partial（37事实/5事件/0暴露/54待处理），非临床验收。09-10判断检索模块与批次小样已完成，正式持久任务/缺口/UI未接线。用户要求本产品线程无损暂停交接；原件QC及全链浏览器验收未完成，详细横评后置。接任主入口HANDOFF_20260910_PRODUCT_PAUSED_AGENT_TAKEOVER.md |
| Phase 6–9 | 未开始 |

阶段完成状态此后随材料里程碑回写本文件，不再只存在于 `docs/PROJECT_CONTEXT.md`。

### 2026-09-05 接管纠偏与当前实施顺序

本节保留接管顺序；2026-09-09 已按最新用户要求恢复全局执行/会商机制，产品推理仍仅使用产品自身 harness 直连模型。详细初始审查依据、问题与组件边界见 `.trellis/tasks/09-05-phase55-dual-vlm-page-review/ENGINEERING_REVIEW_20260905_TAKEOVER.md`。

上表“已完成”保留历史归档含义，不表示全部正式产品页面已验收。当前正式 HTTP 命令、持久页任务与覆盖已接线并完成隔离真实双读；仍需完成事实/事件/用药/Profile 及临床核查，不能仅凭页覆盖通过提前进入 Phase 6。

1. 先修复确定性误采信：同读道重复信号不得算双源、数字归一化不得丢精度或零值；修复可选手写预检阻断与生产上传依赖。新增反例须先复现再通过。
2. 完整核对任务、来源、真实 API/前端边界；明确字段/时间/位置关联的对账合同与旧键兼容策略。不以新增临床硬编码解决对账差异。
3. 复用现有持久作业实现 R3 逐页提交、取消恢复及统一并发；权威页清单闭合后由服务端绑定 coverage，正式规范化入口不得静默使用旧链。补正式 API 集成测试。
4. 双主读显式凭据/模型身份预检与最小合成图像调用；手写不可用应留明确信息而非阻塞无手写任务。不得读取本机其他 harness 配置补齐产品凭据。
5. 产品金标复跑，报告事实召回、静默漏判、手写、失败覆盖与时延；阈值与临床边界按既定批准要求处理。此前不承诺真实运行质量。
6. 受控 31001 新作业、事实/事件/暴露/Profile 原件 QC、1080P/2K/4K 正式浏览器验收；满足后回写 Phase 5 与 Phase 5.5 并制定 Phase 6 具体实施包。

本轮已验证前端 526 项、后端扩大聚焦 480 项通过（真实模型探针 1 项未启用跳过），正式前端构建通过。不是全量后端复跑，也不是临床或浏览器验收。

## Phase 0：冻结基线与隔离

### 工作

1. 将三轮决定、会商裁决、现有测试和关键错误案例形成冻结清单。
2. 标记旧项目目录和旧报告为legacy/read-only，增加V2写入保护测试。
3. 备份当前启动入口、配置、项目索引和测试基线。
4. 建立V2目录边界：`frontend/`、`app/domain/`、`app/workflow/`、`app/storage/`、`app/agents/`、`app/projections/`、`tests/v2/`。
5. 建立依赖和许可清单，固定React/Vite/TanStack/SQLAlchemy/Alembic版本。

### 退出门槛

- 旧项目不可写；
- 当前131项测试仍通过；
- V2目录和旧实现无写路径交叉；
- 任务日志和回滚点完整。

## Phase 0.5：领域与交互合同

### 工作

1. 定义 `fixture/v1`：Project、Subject、ReviewEpisode、Patient Profile、RuleExpression、EvidenceRequirement/Expectation、EvidenceSpan定位阶梯、Assessment、Action、ReviewRunDiff和Job事件。
2. 生成JSON Schema、OpenAPI草案和至少3名覆盖正常、明确障碍、缺口/冲突的示例受试者。
3. 把组件状态到节点主状态/计数/排序写成纯函数表和单元测试。
4. 定义每个Agent的输入/输出、PromptVersion、Gate、写权限、重试、幂等键、停止条件和审计字段。
5. 定义CSS设计token、信息密度、键盘操作、证据查看器、1080P至4K宽屏适配和页面级滚动合同。
6. 编写Phase 1脚本化UAT：不少于10项任务、测量方法、临时阈值、错误分类和迭代停止条件。

### 退出门槛

- 所有fixture通过Schema验证；
- 规则表达式可表示历史AND/OR、复合研究者判断、时间窗和例外错误案例；
- 节点汇总真值表覆盖全部状态/gap组合；
- Agent不能绕过Gate或直接写最终组件状态；
- UAT脚本和阈值经用户批准进入原型。

## Phase 1：真实前端壳可交互原型

### 工作

1. 使用Phase 0.5的目标Schema和stub API，不读取旧Markdown报告作为UI数据源；前端壳后续直接接真实API，不做一次性原型。
2. 建立无登录React/TypeScript前端壳和全局导航。
3. 同时实现“今日工作”和“项目看板”首屏变体，供UAT决定默认入口。
4. 实现项目看板：受试者×审核节点、主状态、分类计数、逐列筛选/排序和节点直达。
5. 实现Patient Profile：主题泳道、应备证据覆盖、默认风险过滤、完整明细、事件/规则/证据联动。
6. 实现入排工作台：规则树、组件判断/行动/差异、识别文本和原文件三栏同步；显示证据定位精度。
7. 实现行动中心、Job详情、快照历史、ReviewRun diff和回顾重审入口。
8. 制作至少10个关键场景：沉默/否认、阳性病史溯源、引用文件缺失、检查未完成、冲突、OCR极性、部分日期、后续节点升级、自动关闭、人工override、部分任务失败/stale。
9. 在1920×1080、2560×1440和3840×2160桌面、100%/150%/200%缩放完成Playwright截图、交互、键盘和axe-core检查。

### 退出门槛

- 最大化窗口无无效空白或主页面横向拖动；
- 1080P至4K最大化窗口均充分利用宽度，不因固定尺寸形成无效留白或裁切；
- 所有风险可点击到模拟原始证据；
- 定位降级、加载、空状态、冲突、stale、失败和恢复状态均有明确界面；
- 原型不声称后台、OCR或审核已完成。

## Phase 1.5：量化原型UAT硬门槛

### 工作

1. 由用户按脚本完成项目创建、识别节点状态、定位证据、查看Profile、关闭行动、处理冲突和恢复任务等代表任务。
2. 记录无辅助完成率、用时、误操作、错误结论、证据可达交互数、首屏偏好和主观负担。
3. 对失败项迭代信息架构、术语、密度和交互；每轮保留变更与结果。
4. 冻结获批的fixture/API和视觉交互修订号。

### 退出门槛

- 暂定无辅助完成率≥90%、错误结论=0、关键证据≤3次交互可达；
- 用户明确批准默认首屏、页面架构、术语、信息密度和主要路径；
- 所有失败均已修正或作为明确、可接受的剩余风险记录；
- 未通过本阶段不得启动Phase 2数据库/后台核心实施。

## Phase 2：SQLite领域层与持久任务

### 工作

1. 建立SQLAlchemy模型和Alembic初始迁移。
2. 实现Project、Protocol、RuleExpression、EvidenceRequirement/Expectation、Subject、Episode、Snapshot、Document、EvidenceSpan、Fact、Assessment、Action、ReviewRunDiff、AgentCall/PromptVersion和Job等核心表。
3. 启用SQLite WAL、事务、外键、版本计数和迁移前备份。
4. 实现Job/Checkpoint、数据库租约、启动恢复、取消和错误重试。
5. SSE改为订阅Job事件，浏览器不再拥有任务生命期。
6. 实现幂等键和重复请求保护。
7. 为所有人工可编辑记录实现revision乐观并发；为受影响但尚未重算的实体实现stale状态。

### 退出门槛

- 服务处理中强制终止后可从Checkpoint恢复；
- 浏览器关闭不取消任务；
- 重复请求不产生重复Job、文档或行动；
- 无永久`processing`状态；
- 数据库备份和迁移回滚通过。
- 两标签页提交旧revision时必须冲突并展示差异，不能静默覆盖。

## Phase 3：方案解构V2

### 工作

1. 上传方案并自动提取名称、编号、版本、日期，优先页眉页脚/第一页。
2. 识别独立II/III或真正无缝II/III并执行确认逻辑。
3. 对选定期别全文段落、列表项、表格行/表头和注释建立 ProtocolSectionCoverageManifest，每个结构单元必须有处置结果。
4. Protocol Deconstructor按章节切片输出结构化 Rule/RuleComponent/WorkflowStage，并解构合并用药/治疗、洗脱、时效、复测、评分/检查细则等全方案 ProtocolReviewControl。
5. Gate核对官方父级数量、编号、父子关系、全文单元处置、AND/OR/NOT、阈值、单位、时间锚点/窗口、例外、跨来源关系和必做检查。
6. 从官方规则、研究流程表和其他方案控制发布 EvidenceRequirement，并按“提前关注/本节点判定/后续节点复核”投影各 ReviewEpisode 的 EvidenceExpectation。
7. 建立首次解构和重新解构两个工作台流程。
8. 实现当前/新结果并列、逐条diff、编辑、继续对话、取消和发布。
9. 建立InterpretationSource，遇到解释材料与方案冲突时警示且不改RuleSet。

### 退出门槛

- MG-K10-SAR III和D001从原方案新建项目；
- 父级IN/EX数量、官方编号100%一致；
- 复杂条款组件逻辑可视化且通过确定性测试；
- 项目期别和审核节点不会混淆；
- 每个规则集明确绑定方案Vx.x。
- 选定期别全文结构单元 100% 有处置结果，不以关键词零命中宣称完整；
- 合并用药/治疗、洗脱、评分/检查细则等基线及以前控制均有正式来源、节点作用和可审计的重复/补充/冲突关系；
- 未命名时间锚点、未处置单元或未解决冲突阻断整份规则模型发布。

## Phase 4：证据快照、上传与OCR V2

### 工作

1. 实现增量/全量上传的显式入口和预览。
2. 文件内容哈希去重；全量上传新建EvidenceSnapshot。
3. 封装现有OCR适配器，保持全局最大8路并发。
4. OCR缓存改为内容哈希 + 页码 + 模型/参数版本。
5. 建立文档分类、页面完整性、ReferencedDocument和证据类型。
6. 保存原OCR、页图和EvidenceSpan定位；先完成oMLX布局输出、原生PDF word box和文本锚定能力spike。
7. 实现否定词/数值/单位/日期风险校对，极性变化需明确确认。
8. OCR与独立受试者LLM任务按依赖流水并行。

### 退出门槛

- 同文件重复上传不重复OCR；文件或模型变化必定重跑；
- 增量只影响保守关联范围；全量保留旧快照；
- OCR“否认/确认”、小数点、单位和日期测试通过；
- 校对不改原OCR，且重算范围可追踪。
- 每个EvidenceSpan实际精度和降级原因可见；若无法达到text_range则明确显示page_excerpt/page_only，不伪造bbox。

## Phase 5：临床事实与Patient Profile

### 工作

1. Evidence Normalizer生成ClinicalFact/Event/MedicationExposure候选。
2. Gate校验Schema、EvidenceSpan、否定状态、日期精度、重复和冲突。
3. 建立事实到规则组件的双向索引。
4. 实现Patient Profile主题泳道、疾病历程、MH/CM、非药物治疗、检查评分和特殊经历。
5. 计算EvidenceExpectation覆盖状态，把缺失/弱证据/引用未提供与规则双向链接，并保留供后续阶段生成行动的结构化缺口；本阶段不创建ActionRequest。
6. 计算部分日期上下界和病程/洗脱可判定范围。
7. 首屏按入排相关、异常、临界和趋势变化过滤；全量值在明细。

### 退出门槛

- 所有关键事件可回源；
- 阳性长期病史筛选转述生成加强溯源待办；
- 沉默不生成否认事实；
- 冲突来源并列且不自动择优；
- 代表受试者Patient Profile逐事件人工核对通过。
- “未记录”只显示为Expectation缺口，不生成虚假的正常/阴性事实。

### Phase 5 收口（2026-09-01 增补）

当前现场（2026-09-03 临床质检复核）：SAR 方案作业已完成并发布规则修订 16；worktree 显式 env 契约、`DECONSTRUCT_GLM_API_KEY` 和启动预检已完成。31001 的合法 GLM 事实规范化作业已完成，当前已发布 223 条事实、19 个事件、10 条用药暴露、130 条资料期望和 1 个 Patient Profile；但临床质检发现事实类型与条款绑定合同错位造成已有证据误报缺失，另有药名推测和邮件讨论误投影为用药暴露，故 `claims_complete=false`。修复必须采用项目无关的合同与 harness，不得给 31001 或 D001 写特例。收口工作项：

1. **修复配置加载边界（阻塞项）：** 建立 worktree 显式 env 契约（`ENROLLMENT_ENV_FILE` 必填或启动脚本显式注入所需密钥变量），补齐 `DECONSTRUCT_GLM_API_KEY`；实现服务启动凭据与端点预检门禁——对声明路由逐候选报告“已配置/未配置”与端点连通性（不打印密钥），任一声明候选不可执行即拒绝启动或显式降级并写入路由审计。
2. **按检查点收口 SAR 作业：** 遵循 `CHECKPOINT_20260901_SAR_FRESH_PROTOCOL_LIVE_PAUSED.md` 恢复入口——只读核对现场 → 修复凭据链并验证 → 重新运行全新运行门禁 → 决定恢复第 2 次尝试或新建受控尝试；不得伪造环境、改写审计或拼接失败候选。
3. **语义批次提示合同增补：** 每批提示附允许来源 ID 白名单并要求模型逐条自检来源归属，针对 DeepSeek 来源闭包失败的根因做提示侧修复，不放松门禁。
4. **完成 Phase 5 剩余验收：** 31001 事实规范化、Patient Profile、浏览器临床 QC（P5-AC10/12/13），回写 PRD 验收框，`claims_complete=true`。

### Phase 5 收口退出门槛

- 凭据预检有故障注入测试：缺 key/端点不通时启动被拒或显式降级，路由审计如实记录；
- SAR 方案规则目录通过完整性检查与人工可读抽查并发布；
- 31001 逐事件核对通过，Phase 5 PRD 验收状态回写。

## Phase 5.5：真实资料 OCR/VLM 评测与双 VLM 逐页判读（2026-09-01 新增，2026-09-02 按横评修订）

设计依据：设计书 §2（冻结决定 10/11）、§3.3、§4.2、§5.4 无阈值规则、§7.2、§7.4 与 §12 两次修订裁决。

### 工作

1. **金标评测集（已完成 2026-09-02）：** 71 页真实原始资料（SAR III 4 例 44 页 + D001 II 3 例筛败 27 页，筛败原因对模型隐藏），隔离目录 `~/tmp/ie-vlm-benchmark-20260902/`；SAR 页面+事实级金标 832 条、7 例 158 条条款金标，Cursor subAgent 对图首审 + Gemini-3.7-Flash 条款复审 + 机械/用户规则裁定，争议 0。金标 xlsx、ClausePack、页清单与 harness 在该目录，迁入仓库时只迁 harness/ClausePack/评分脚本，不迁原始页图。
2. **多模型横评：** 详细横评延后至系统构建完成。当前先以 GLM-5.3-Flash low × Gemini-3.7-Flash high 完成正式产品链路及真实资料核对；不能把其他模型或其他配置的指标转移给当前组合，也不能以延后横评替代产品临床验收。
3. **ClausePack 投影：** 从已发布 RuleModelRevision 生成紧凑判读条款包，内容寻址、版本化；超出体积预算时按条款分组分包并记录分包依据。
4. **双 VLM 逐页判读 harness（单阶段）：** 两个主读独立读取全部页内事实及手写批注，严格校验 JSON Schema；强制 `handwriting[]`，证据关系仅允许 `evidence_for/against/mentions/none`。归一化后对账并生成逐页覆盖。截断按预算规则重试，429 等待不计内容重试，失败显式呈现；云端并发 2–3，本地平台间串行。复用已有 JSON 修复、归一化及服务生命周期实现。
4b. **ClausePack `determination_mode`：** 投影时按 RuleComponent 类型标注 deterministic / semantic / investigator_judgment；`deterministic` 条款的 VLM 方向信号在 Reconciler 丢弃；`investigator_judgment` 条款按 §5.4 无阈值规则映射状态与缺口。
4c. **手写内容核对：** GLM 与 Gemini 均输出结构化手写内容，按目标、类别、文字、位置及日期核对。两个不同模型一致才采信；同一模型重复请求不增加独立意见数，分歧不能传播成全报告判断。
5. **模型接入：** main-A GLM-5.3-Flash low，`zhipu-coding-plan`；main-B Gemini-3.7-Flash high，`google-antigravity` OAuth。产品从显式 env 读取端点和凭据，自行完成 OAuth 更新与原生 HTTP 调用，不运行个人 harness。核验实际模型及视觉能力，并区分请求档位与实际有效档位；采样沿用厂商默认，不自动切换其他模型。
6. **OCR 侧车化改造：** oMLX 转录保留存档/文本锚定位/预筛职责；Evidence Normalizer 输入切换为“采信页级记录 + 侧车转录”；不回改 Phase 4 已冻结的证据快照与 OCR 产物，只新增处理修订。
7. **端到端试运行：** 用 31001 等代表受试者跑通逐页判读→对账→规范化，与 Phase 5 已发布事实对照并形成差异清单。

### 退出门槛

- 评测报告已落盘（2026-09-02）；产品 harness 在同一金标集复跑：双模型并集事实召回 ≥0.95、金标负判定静默漏判 = 0、手写判断类条目采信召回与冲突呈现率有数字，采信阈值由用户在实测数字上批准；
- 页级 Schema 无判定词；`deterministic` 条款方向 100% 由确定性代码给出（路由审计证明）；
- SA03008 尿隐血 3+ 类无阈值异常在产品中落为 `professional_judgment` 缺口 + 研究者 ActionRequest，不落为满足/未触发；
- seeded 极性/关键数值错误 = 0（沿用统一验证矩阵 OCR 行）；
- 代表受试者每一页在 SubjectPageCoverage 有处置，舍弃有可审计理由；分歧页 100% 呈现为冲突，无静默单源采信；
- 路由审计证明双模型互盲、无跨模型拼接；
- 路由审计证明 Gemini 是完整第二主读，普通事实及手写内容均独立提取；本地模型、DeepSeek 与 OCR 侧车不进入受试者主读；
- 双 VLM 判读结果与 Phase 5 既有事实的差异清单经人工复核。

## Phase 6：结构化入排审核与行动建议

### 工作

1. Eligibility Assessor逐RuleComponent输出语义候选、使用事实和gap建议，不写最终状态。
2. 确定性Evaluator/Gate计算IN/EX、父子逻辑、阈值、单位、例外、时间窗、一致性矩阵和最终组件状态。
3. 根据缺口分类生成ActionRequest，责任方限定为四类。
4. 实现项目/节点主状态和分类计数，不再覆盖为单一overall verdict。
5. 后续节点打开时自动升级并重跑尚未到期组件。
6. 高风险规则、冲突、低质量OCR和Gate异常触发独立Critic；Critic仅可否决/降级/开行动。
7. 按节点级 ModelConfig 记录各语义节点的准确性、耗时和费用；Assessor 输入为交叉采信的事实与页级信号（结构化记录，不直读页图像）。
8. 实现ReviewRun前后组件、事实、Action和证据差异投影。

### 退出门槛

- 关键错误fixture全部通过：AND/OR、GGT/ALT/AST/TBil、尿检/感染、梅毒例外、研究者复合判断、FEV1、洗脱期、日期锚点；
- 无来源引用不能形成明确判断；
- 每个未明确项都有具体责任、动作、证据形式和到期节点；
- Critic不能静默修改判断。
- 主状态/计数完全来自纯函数，模型总结变化不得改变列表状态。

## Phase 7：Action闭环、批量与报告

### 工作

1. 实现ActionTransition、系统自动关闭、人工override、重开和supersede。
2. 为每种gap_type建立机器可检查的关闭谓词。
3. 无关上传、重复Job和重复回调进行幂等测试。
4. 实现后台批量审核、批量OCR重置、批量重新审核和批量个人报告导出。
5. 实现个人、中心、项目Markdown与HTML报告。
6. 更新详细帮助页、故障说明、桌面入口和任务恢复提示。
7. Job页面展示逐项进度、影响范围、stale标志、粒度重试、安全取消和估算时间/费用。

### 退出门槛

- 无关文件不关闭待办；
- 自动/人工状态历史完整可逆；
- 行动关闭不静默改变规则结论；
- 报告无内部日志或指令性措辞；
- 浏览器关闭后批量任务继续运行并可重新连接。

## Phase 8：新项目全流程临床验证

### 工作

1. 旧D001与MG-K10-SAR III保持只读。
2. 用原方案在V2从头创建全新项目。
3. 先跑少量已知高风险病例，逐页、逐事实、逐规则QC。
4. 再扩展D001代表性筛败/成功病例和MG-K10-SAR III中心31。
5. 人工结果只用于事后比较，不注入审核提示。
6. 对每个偏差定位到规则、事实、EvidenceSpan、Agent或Gate层并修复通用根因。
7. 全量重跑关键回归，不用个人特异补丁掩盖问题。

### 退出门槛

- 已知历史错误类别零复发；
- 方案父级规则覆盖完整；
- 每个明确障碍、关键缺口和专业判断逐条人工复核；
- Patient Profile与原始资料代表性全量核对通过；
- 运行时间、API成本、OCR并发和恢复性记录完整。

## Phase 9：切换与清理

### 工作

1. 新项目默认进入V2写路径；旧项目只读入口保留。
2. 桌面入口直接打开V2项目看板。
3. 删除登录、多账户、owner/admin和旧写API。
4. 移除不再使用的旧缓存、临时原型、重复样式和废弃脚本；删除前生成精确清单。
5. 归档旧架构说明，更新最终运维、备份和恢复文档。

### 退出门槛

- 新建、方案解构、上传、OCR、审核、Patient Profile、待办和导出全流程通过；
- 旧项目无写入口；
- 桌面双击启动和重启恢复通过；
- 完整测试、浏览器视觉QC和最终用户验收通过。

## 工程纠偏清单（2026-09-01 工程 review）

按“最小必要改动”执行，随相邻阶段顺带完成，不单开大重构：

1. **配置边界（Phase 5 收口第 1 项，阻塞）：** env 契约 + 凭据/端点预检门禁。
2. **生产依赖归位：** `openai`、`pymupdf` 等生产路径实际依赖从 dev group 移入主依赖；`uv sync --no-dev` 后服务必须可运行。
3. **命名纠偏：** `app/agents/deepseek_protocol_transport.py` 更名为中性 semantic transport（实际承载 GLM/MTPLX/DeepSeek 多后端）。
4. **方案侧 PDF 路径删除：** 方案导入 MIME 白名单仅 docx；`app/protocols/pdf_structure.py` 的方案入口下线（受试者证据 PDF 路径不受影响）。
5. **Legacy 双轨收敛：** `app/deconstructor.py`、`app/pipeline/reviewer.py` 冻结只读，V2 不得 import；Phase 6 开始前下线 legacy 解构/审核入口，不拖到 Phase 9。
6. **主仓漂移清理：** 删除主仓未跟踪的过期 `frontend/src/api/evidence/evidenceProcessingTypes.ts` 与 `evidenceProcessingViewModels.ts` 副本（比 worktree 已跟踪版本旧）；声明 phase5 worktree 的设计书与本计划为唯一权威版本，主仓副本在合并时同步。
7. **巨型模块拆分（随迭代顺带）：** `protocol_deconstructor.py`（约 4.5k 行）、`deconstruction_gate.py`、`protocol_workbench_service.py`、`evidence_processing_executor.py` 按步骤边界拆分；Phase 5.5 新增双 VLM 代码不得并入既有巨型文件。
8. **质量护栏：** ruff + eslint 绑进日常脚本与 trellis-check；端口权威表（8001 oMLX、8002 MTPLX、8900 legacy、8910–8919 专用 V2、20128 cms-router）写入运维文档，修正 `run.sh` 注释漂移。

## 统一验证矩阵

| 层级 | 工具/对象 | 必测项 | 硬门槛或校准方式 |
|---|---|---|---|
| 合同 | Pydantic/JSON Schema/OpenAPI快照 | Agent I/O、fixture、Job事件、EvidenceSpan、状态枚举 | Schema/Gate 100%；合同变化必须显式迁移 |
| 确定性逻辑 | 单元/属性/变异测试 | 官方编号、父子树、AND/OR/NOT、阈值/单位、例外、部分日期、节点汇总 | 父级编号100%；已知错误fixture零复发；关键变异必须被测试捕获 |
| Agent评测 | 节点级gold set | 事实抽取、语义组件候选、Critic否决；沉默/否认、交叉条款污染、研究者复合判断 | 无虚构Span、无已知错误；P/R/一致率先校准后由用户批准，不凭空固定 |
| OCR | 按原生PDF/扫描/照片/手写分层gold pages | 否定词、小数/单位、日期、表格、幻觉、定位成功率 | seeded极性/关键数值错误=0；定位不足必须可见降级 |
| 双VLM交叉 | 分类金标页 + 双盲逐页判读 | 字段级一致/分歧、单源候选处理、页覆盖处置、舍弃理由、跨模型隔离 | 分歧页100%进冲突；无静默单源采信；每页有处置；路由审计证明互盲 |
| 路由/凭据预检 | 故障注入 | 缺key、端点不通、声明路由含不可执行候选 | 启动被拒或显式降级并写审计；禁止带病声明路由进入语义作业 |
| 临床回归 | D001/MG-K10-SAR III错误类 | GGT替代、尿检感染、EX-20h/EX-11 AND、梅毒例外、FEV1、洗脱/锚点 | 已知错误类别零复发；人工结果只用于盲后比较 |
| Job/恢复 | 故障注入 | 各步骤kill -9、浏览器关闭、SSE重连、重复提交、部分OCR失败、恢复/取消 | 无永久processing、重复Job/文档/Action或静默stale |
| API/E2E | FastAPI + Playwright | 全量/增量、阶段隔离、Action关闭/override/重开、报告、关键用户旅程 | 关键旅程全部通过；审计链完整 |
| UI/视觉/可访问性 | Playwright截图 + axe-core + 键盘 | 1920×1080、2560×1440、3840×2160、100/150/200%缩放、长文本、空/错/加载/stale | 页面级无横向滚动；0个critical axe错误；键盘可完成主路径 |
| 性能 | 本地代表负载 | 100名受试者看板、500事实Profile、证据首开、8路OCR、流水并行 | Phase 0.5先记预算，Phase 8用实测校准并禁止无说明回退 |
| 原型UAT | 脚本化任务 | 首屏选择、证据定位、规则/行动/恢复路径 | 暂定完成率≥90%、错误结论=0、关键证据≤3次交互；用户批准阈值 |
| 全流程UAT | 新建V2项目 | 从方案到Profile、审核、行动、报告、恢复 | 每个明确障碍/关键缺口/专业判断人工复核，最终用户签收 |

## 实施启动条件

只有在用户明确批准本设计和计划后，才开始Phase 0/0.5/1。Phase 1.5未通过前不得开始Phase 2。批准前不改写V2业务代码、不删除旧项目、不运行新的全量临床审核。

**2026-09-01 增补：** 上述批准已发生，Phase 0–4 已完成。当前顺序约束为：先完成“Phase 5 收口”，再启动 Phase 5.5；Phase 5.5 的评测与逐页判读门槛未过，不进入 Phase 6 结构化入排审核。双 VLM 判读不回改 Phase 4 已冻结的证据快照与 OCR 产物，只新增处理修订。
