Now I have enough. Let me write the report. The conference prompt explicitly says "do not write this or any sibling output file yourself" — the runner will record it. I'll return the complete report in the final response.

# 独立规划审评：Pi / minimax-m3

## 阻断开工问题

**B1. 重新解构允许"不上传新方案"却仍可改变与流程表绑定的证据要求——会让"基线及以前必做项"在历史审核里无声消失。**
- 观察：`prd.md` §首次解构 / 重新解构 步骤 2 写明"用户可上传新方案/修订案，或不上传新方案时基于反馈修订当前草稿"；`design.md` §3.3 `ProtocolDraftRevision` 把"反馈修订"作为等同的 revision 触因；`design.md` §7 要求 `EvidenceRequirement` 来源 = 规则组件 + 研究流程表。
- 推断：当用户仅基于反馈、不提供新 `ProtocolDocumentVersion` 时，gate 没有显式禁止修改 `WorkflowStage` 与下游 `EvidenceRequirement.review_stage` / `due_stage`。后果：基线及以前的必做项（PRD §结构化要求 #7）可在不替换方案文件的情况下被改写，且 Article 31 风格的"基线前必须执行"会在历史 ReviewRun 的"应备证据"投影中消失。
- 后果：违反 `AGENTS.md` "Later-stage evidence must not silently rewrite an earlier-stage result" 与"基线及以前必做项随方案版本绑定"的边界。CRA 验真历史报告时无法发现差异。
- 最小修订：`design.md` §3.4 发布事务步骤 1 之前新增显式规则——"凡是导致 `WorkflowStage` 列表、阶段顺序、`EvidenceRequirement.due_stage` 或必做项增减的草稿变更，必须随附新的 `ProtocolDocumentVersion`（即哈希 + 方案版本号 + 正式日期全部更新）；纯反馈修订只能改 component 内的 `expression` / `exception_expression` / `display_code` / title / `source_text` 的微措辞，不能动 due_stage 与 stage 列表"。同步在 `implement.md` 切片 4 "草稿 revision" 段加一句"反馈修订触发的 revision 在发布前必须校验变更 scope ∈ {component 内表达式/例外/标题/来源}，否则拒绝保存"。

**B2. 发布事务步骤 4 "把现有项目追加到新规则 revision"未约束"上传的协议身份必须与该项目当前协议身份匹配"，可被作为跨项目覆写入口。**
- 观察：`design.md` §3.4 步骤 4 写"创建新项目，或把现有项目追加到新规则 revision"；`prd.md` §重新解构 步骤 2 也未规定"上传的新方案项目代号、版本号、哈希与当前项目不匹配时的拒绝策略"。
- 推断：用户选"项目 A（MG-K10-SAR III）"做重新解构时，若错传 D001 文档，`ProtocolAuthorityRecord`、规则集、流程节点将被替换为 D001 内容，但发布按钮仍可点击——这是跨项目无提示覆盖。中间没有任何"项目代号不一致需二次确认"的硬门。
- 后果：违反 `AGENTS.md` "Preserve source file, document version, page, exact excerpt" 与"正式规则版本必须绑定方案文件哈希、方案编号、正式版本号、正式日期和研究期别"五字段绑定。
- 最小修订：`design.md` §3.4 步骤 4 之前的新增硬约束："发布前必须 `protocol_identity_match(existing_project, uploaded_document_version)` 校验文件哈希、方案编号、版本号、版本日期、研究期别五字段全部一致；五字段中任意字段不一致即拒绝发布，并把不一致字段翻译为自然中文警示（如'上传方案编号 D001-002 与本项目当前方案 MG-K10-SAR-001 不一致，已拒绝发布'）。"

**B3. 完整性检查缺少"每条基线及以前 EvidenceRequirement 必须在方案原文有锚点"的语句级证据，PRD 验收标准的"非空"门槛不足以防止"流程表解析为一条占位 requirement"。**
- 观察：`design.md` §6 12 类 Gate 中 `workflow_coverage` 描述为"流程表存在时节点非空，基线及以前必做项均已映射"——只是"已映射"，没有要求映射本身有 source span；`source_coverage` 检查"规则、组件、流程和要求均有合法来源定位"——但与流程/必做项的耦合校验没有强调逐项锚点；`research.md` 当前真实输入观察坦承"旧提取器在 III 期得到 IN 7、EX 16，但研究流程表返回空节点"——这是 Phase 3 的核心失败模式。
- 推断：gate 可能放过"流程表解析为 1 条 '基线检查' requirement、对应一段通用正文占位锚点"的退化结果，符合"非空"但完全失去必做项分解能力。
- 后果：违反 `prd.md` §结构化要求 #7 与 §验收标准 #4（"流程表存在但结果为空会被确定性检查拒绝"应理解为"分解不足也应被拒绝"），且后续 Phase 5 `EvidenceExpectation` 投影将基于错误基线生成"应有而没有"的虚假完成度。
- 最小修订：`design.md` §6 `workflow_coverage` 与 `source_coverage` 子项加一条"流程 stage 与每条必做项 requirement 必须各自带 1 个或多个 source span；span 数量等于 0 或 span 仅引用通用标题/章首/页眉/页脚（任一位置不可作为基线必做项锚点）的必须按'需要核对'拒绝发布"；`implement.md` 切片 4 验证段补"用 MG-K10-SAR 流程表逐行统计 source span 数量，断言每个基线及以前行 ≥ 1 且均为 block-level 锚点，反例用 1 行占位 requirement 注入必须被 Gate 拒绝"。

**B4. 验收标准首条"项目代号不得识别成'临床研究方案'"与 `research.md` 与 `design.md` §3.2 字段优先级规则直接冲突。**
- 观察：`prd.md` §验收标准 第一条写"项目代号不得识别成'临床研究方案'"；`research.md` 候选决策写"通用标题、SOP 模板编号和模板版本被标记为不同字段类别，不靠项目名称黑名单过滤"；`design.md` §3.2 同样规定"通用标题…被标记为不同字段类别，不靠项目名称黑名单过滤"。
- 推断：测试要么依赖"硬编码黑名单"（被设计明确禁止），要么根本不报失败（验收永远 PASS）。两种都不可接受——前者违反设计原则，后者让验收失效。
- 后果：验收门槛不可信，临床方无法判断测试是否真正落到边界。
- 最小修订：把验收首条改为"项目代号字段必须来自页眉/第一页/签署页的明确字段或正文摘要；任何出现在 SOP 模板封面、模板版本号、文件名兜底位置的'临床研究方案'类通用标题不得作为项目代号投影；该类命中必须以自然中文提示项目代号待用户确认"。等同地在 `design.md` §3.2 加"项目代号字段候选若仅在文件名/通用标题命中，必须进入用户确认页"。

**B5. 重新解构的删/减/覆盖边界未明示"草稿被取消后已编辑的 manual edit 是否随取消被丢弃"，会出现"取消的草稿内容事后被恢复"或"持续占用 revision 编号"两个极端。**
- 观察：`prd.md` §重新解构 步骤 4 写"用户可继续编辑、继续说明、再次解构、保存草稿、取消或发布"；`design.md` §3.3 `ProtocolDraftRevision` 写"每次 Agent 输出、手工编辑或反馈修订形成新 revision"；`design.md` §3.4 步骤 5 写"取消和保存草稿都不能覆盖当前正式版本"。但"取消"对 revision 表的影响没有明示。
- 推断：要么取消产生新 revision（数据膨胀且草稿进入 `cancelled` 状态的孤立历史），要么取消清空所有 manual edit（用户做了一小时手工微调后点错取消就丢失）。没有规范就是这种隐性 bug 的源头。
- 后果：违反 `AGENTS.md` "正式发布对象追加写入；草稿可修订，但不能原地覆盖已发布规则"中"草稿可修订"的人性化底线。
- 最小修订：`design.md` §3.3 `ProtocolDraftRevision` 增字段 `state: DraftState`（取值 `pending_user_input | ready_for_review | needs_review | cancelled_retained | cancelled_discarded | published`）；§3.4 步骤 5 增"取消保留的口径：默认保留全部 revision 并标记 `cancelled_retained`，发布按钮被禁用；用户在取消页可勾选'同时丢弃所有 manual edit'才会走 `cancelled_discarded` 并物理删除"；`implement.md` 切片 6 验证段增"用户已在草稿内做 5 处 manual edit，点取消后再次进入重新解构，草稿默认可见且可恢复，勾选'丢弃'后才消失"。

## 非阻断改进

**N1. 子组件显示编号与官方编号格式未在 `RuleComponent.display_code` 落入 schema 校验。**
- 观察：`rules.py` 第 144-147 行 `RuleComponent.display_code: str = Field(min_length=1)` 没有任何模式约束；`Rule.official_code` 是 `^(IN|EX|REQ)-\d{2}$`。
- 推断：`prd.md` §结构化要求 #2 的"IN-04a、IN-04b"约定没有落到 schema，靠 Gate 字符串校验兜底易漂移。
- 建议：把 `display_code` 收紧为 `^((IN|EX|REQ)-\d{2})(?:[a-z]{1,2})?$`，并在 `RuleSet.validate_rule_tree` 中追加"同 `official_code` 下的 `display_code` 必须以父编号 + 唯一小写后缀形式构成完整集合"。

**N2. ALL/ANY/例外复合判断的"AND 不能弱化为 OR"在 schema 层缺断言。**
- 观察：`rules.py` 第 111-117 行 `validate_arity` 仅校验 NOT/ALL/ANY 节点数量；`design.md` §6 `boolean_logic` 描述为"ALL/ANY/NOT 元数、例外表达式、研究者复合判断"——但"研究者复合判断"是逻辑要求还是 schema 字段要求未明。
- 推断：当前模型无法结构性表达"异常存在 AND 研究者判断构成不可接受风险"——只能表达了常量条件；研究者判断在 `AtomicPredicate.requires_professional_judgment: bool` 是单谓词标志，无法标注"必须与某原子并列 AND"。
- 建议：在 `AtomicPredicate` 新增 `paired_with_professional_judgment: bool | None`，并由 Gate 校验"标记为真时所在 LogicalExpression 节点必须是 ALL 且至少包含 1 个非判断原子谓词"。

**N3. 渲染页定位的"对齐状态"没有量化阈值。**
- 观察：`design.md` §3.1 `ProtocolSourceSpan` 字段含 `alignment_status` 但没有可发布阈值；`research.md` 已承认"对齐失败时降级到文档部件/段落定位并明确标识，不伪造页码或坐标"。
- 建议：§6 Gate 增加 `span_alignment_quality` 子项，要求"用于发布的 `display_text` 必须有 ≥ 1 个 `aligned` 状态的 span；未被对齐的 span 只能作为"补充证据"出现在审阅面板，不能作为发布卡的唯一锚点"。

**N4. `RuleSet` 仅保存 `protocol_version_id` + `study_phase`，缺少 PRD §权威来源与边界 #3 要求的 5 字段绑定指纹。**
- 观察：`rules.py` 第 163-167 行 `RuleSet` 字段为 `rule_set_id` / `protocol_version_id` / `study_phase` / `rules`。
- 建议：在 `RuleSet` 增加 `protocol_document_sha256` / `protocol_version_label` / `protocol_version_date`；`ProtocolAuthorityRecord` 写入时把 5 字段拼入 `authority_record_sha256` 计算域；Gate 校验发布时这 5 字段必须与 `ProtocolDocumentVersion` 一致。

**N5. LibreOffice 版本未进入派生物身份，跨版本升级会让页面定位证据漂移。**
- 观察：`research.md` 写"记录渲染器版本、输出哈希和'渲染页'语义"，但 `design.md` §3.1 `ProtocolRenderArtifact` 字段"原始文件哈希、LibreOffice 版本、渲染参数、PDF 哈希、页数和状态"已部分包含，唯独没有约束"LibreOffice 主版本升级必须强制重渲染并把旧渲染 PDF 标记为 retired"。
- 建议：在 `ProtocolRenderArtifact` 增 `retired_at: datetime | None` 与 `retired_reason`；Gate 在发布时校验"持有 PDF 派生 span ≥ 1 的资产必须 still-active，未 retired"。

**N6. 切片 1-3 的"通过的最小 demo"若不在切片级别同时覆盖 baseline-anchor 完整性，会重蹈旧提取器"流程表返回空节点"的覆辙。**
- 观察：`implement.md` 切片 3 验证段写"Agent 契约、Gate 单元/属性/变异测试；模拟失败和恢复；不接 UI 先完成服务级真实方案草稿"——但没有"对 MG-K10-SAR 流程表逐行断言每条基线及以前行都有 source span anchor"的硬门槛。
- 建议：切片 3 验证段补"用 MG-K10-SAR 流程表对照原方案逐行统计，断言基线及以前行 ≥ 1 span 且其中至少含 1 个 `bbox` 或 `text_range` 精度（不允许全部 `page_only`）"。

**N7. 切片 8 医学监查员试用前置的"连通性测试"列了 CodeBuddy，而 conference context 已规定非视觉角色的参与者集合。**
- 观察：`implement.md` 切片 8 步骤 1 写"首次调用前分别做 CodeBuddy、Pi/Minimax、Grok Build 连通性测试"；`context/phase3-protocol-plan-review_conference_context.md` 规定非视觉任务参与者为 Pi/cms-router/deepseek-v4-flash / Pi/OpenCode Go/deepseek-v4-flash / Grok Build grok-4.6 / Pi/cms-router/minimax-m3，根本没有 CodeBuddy。
- 建议：把切片 8 步骤 1 改为"按 conference context 列出本次会议实际参与者清单，对每个参与者分别做一次冒烟连通性测试，记录返回模型、reasoning_effort、入参摘要；CodeBuddy 仅在视觉/HTML/PPT 子任务中考虑"。

**N8. 切片 7 真实方案验收没有"反向不匹配"硬测试。**
- 观察：`prd.md` §验收标准 第二段"MG-K10-SAR III 父规则为 IN 7 条、EX 16 条…"给了正向断言，但"用 D001 创建 III 期项目"这类反向用例没有写明。
- 建议：切片 7 验证段补"上传 D001 但选择 III 期项目——必须被 Gate 拒绝且提示'方案编号/版本不匹配本项目'；上传 MG-K10-SAR 但选择 II 期项目——必须被 Gate 拒绝且提示'方案不含 II 期结构'，并必须截图佐证"。

**N9. 重新解构"八类结构化差异"与首次解构"六类信息"的产品话术不一致。**
- 观察：`prd.md` §首次解构 步骤 5 用"父规则、子条件、逻辑关系、时间窗、例外、所需证据、审核节点和方案原文定位"（8 项）；`prd.md` §重新解构 步骤 3 用"新增、删除、原文变化、逻辑变化、时间窗变化、例外变化、证据要求变化和审核节点变化"（8 项）。
- 推断：差异维度与解构维度命名不同，第一次进入重新解构的用户要重新映射术语。
- 建议：把两类术语对齐为同一个分类法，至少在用户态文案里保持一致；术语表作为内部词汇表的对外别名。

**N10. 视觉路由的"派发独立视觉测试者"前置条件应在切片 5 完成后做一次窄屏冒烟而非切片 8 才出现。**
- 观察：`implement.md` 切片 8 步骤 2 才让测试者"启用视觉从清洁系统…完整走两份方案"。但 §Phase 1 验收门槛已要求"在 1280/1440/1920 和代表性窄屏、100%/150%/200% 缩放完成 Playwright 截图、交互、键盘和 axe-core 检查"。
- 建议：把"窄屏 + 缩放 + axe-core"冒烟提到切片 5 验收段，避免切片 8 才发现"页面级横向滚动"早就出现。

**N11. 视图术语"Compensation"未在 PRD/User-Facing 中禁用。**
- 观察：`prd.md` §界面与中文要求 6 写明禁用 `Agent / schema / pipeline / provider / gate / draft_id` 等内部词，但 `design.md` §6 Gate 仍以 `阻止发布 / 需要核对 / 提醒` 出现——OK；问题是 `design.md` §3.4 步骤 5 仍出现 `translation`、`transaction`、`revision` 等内部词；前端展示规则树时不只要屏蔽实现字段名，还要屏蔽"中期别显示的跨期提示残留"（PRD §结构化要求 #9）。
- 建议：补一条"用户态文案审计脚本"作为切片 5 验证项，断言可见 DOM 中不出现 PRD §界面与中文要求 6 所列词表 + 不出现"与 II 期相同"/"仅 III 期"等跨期比较残留。

**N12. 切片 5 缺少"右栏原位回跳"与"原文与编辑同步"的强校验。**
- 观察：`prd.md` §界面与中文要求 4 写"原文、结构化规则和修改说明之间可在不超过三次操作内往返"；`design.md` §9.2 写"右侧为方案原文与来源定位；窄窗口变为三个标签页，但共享同一选中规则和来源状态"。
- 建议：切片 5 验证段补"Playwright 步骤：选中父规则 IN-04 → 右侧原文跳到对应锚点 → 切到窄屏三个标签页 → 切换 tab 选中状态仍为 IN-04，每步操作 ≤ 3 次"。

## 必须保留的设计

- **Protocol Deconstructor 节点仅写 draft，G1-pinned 不调用、不直接写 RuleSet**（`design.md` §5.2 与 `permissions.py`）：保留作为 Agent 与 Gate 边界的硬约束，这是整套权威体系的根。
- **ProtocolSourceArtifact / ProtocolRenderArtifact / ProtocolSourceSpan 三层证据身份**（`design.md` §3.1）：保留。Phase 3 完成后所有 EvidenceSpan 都能 1:1 追溯到不可变原始文件与渲染参数，不需重建。
- **元信息五级优先级 + 模板编号/版本字段类别**（`design.md` §3.2 与 `research.md`）：保留为唯一确定性身份来源；这是对抗黑名单式伪过滤的唯一正确做法。
- **官方父规则目录由结构通道确定性识别 + Agent 仅做语义拆分**（`design.md` §4.2 + §6 Gate）：保留。父级编号 100% 一致承诺只可能由这条路给出。
- **12 类 Gate + 按 `阻止发布 / 需要核对 / 提醒` 分级映射**（`design.md` §6）：保留。即使要细化每项内涵，分级表是必须的。
- **发布事务一事务内"锁定 revision → 复跑 Gate → 写入权威记录 → 写入新项目 / 追加 revision → 写入幂等记录"，任一失败全量回滚，保留旧 revision 可读**（`design.md` §3.4）：保留。这是 PRD §权威来源与边界 #3 反向防"老 revision 被悄悄抹去"的硬保险。
- **基于 `official_code` 对齐 + 子组件语义键 + 多源独立比较的结构化 diff 管道**（`design.md` §10）：保留。这是"重新解构差异"反退化到"自由文本正则对比"的唯一可行路径。
- **变体 + 父级编号 + 流程 span 锚点 三类必须确定性单测/属性/变异测试**（`implement.md` 切片 3 验证段）：保留最小集合，但需要把范围扩大到流程表 baseline 锚点（参见 B3、N6）。
- **首批清洁 V2 数据目录 + MG-K10-SAR III / D001 II 两个真实方案作为回归锚点**（`prd.md` §验收标准 + `implement.md` 切片 7）：保留。旧项目只读反例锚定不在验收，但作为唯一可触发的"已知错误 fixture"必须跑通。
- **Codename-LibreOffice + 渲染 PDF + 提取快照 的最小固定夹具**（`design.md` §12 与 `research.md`）：保留作为可跨会话回归的最低证据。
- **解释材料只能附在说明层，冲突时 Gate 拒绝改 RuleSet**（`design.md` §3.3 与 §6 `interpretation_authority`）：保留。这是 PRD §权威来源与边界 #2 的合规保证。
- **首次解构与重新解构两个清晰入口、互不串扰**（`design.md` §9.1）：保留为产品底色，避免"CRA 误点重新解构把方案覆盖"。配套强制加上 B2 项目身份硬校验。

## 结论

**修订后可开始。**

理由：5 条阻断问题中 B1（无新方案时偷偷改基线及以前必做项）、B2（跨项目身份错传可被覆盖）、B3（流程表占位 requirement 通过 Gate）、B4（黑名单 vs 设计原则直接冲突）都违反 `AGENTS.md` 临床与证据边界；B5（取消/丢弃边界不清）虽未直接破坏不变量，但会让"草稿状态 + 用户意图"在发布前产生不可追溯的歧义。12 条非阻断改进均属可逐步落地。最关键的核心设计（分层证据身份、五级元信息优先级、12 类 Gate、发布事务回滚、官方父级目录由结构通道确定性识别、旧项目只读）全部到位——问题集中在"边界条件 + 验收口径"而非"骨架设计"。

最小开通条件：在 `design.md` §3.4 前置 B1 / B2 两条硬约束，§6 Gate 增 §B3 流程表逐行锚点子项，§结构化要求 #2 + §3.3 落 B5 草稿状态机；`prd.md` §验收标准 第一条改写为 B4 五字段绑定指纹；`implement.md` 切片 3 验证段补 N6 baseline 锚点断言、切片 7 补 N8 反向不匹配测试、切片 8 步骤 1 改 N7 与 conference context 对齐的用户路由清单。完成上述修订后即可进入 PRD §"开工门槛"四条启动检查与切片 1 spike。
