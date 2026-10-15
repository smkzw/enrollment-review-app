# 工作包：从现有主链迁移，不平行造第二套系统

基线：60f5bb8fe67ac14d44af9ceab0801a9b2a42120b。以下文件是复核入口，修改前须追当前真实调用链；不要求每个文件都修改。新增文件名/字段须在当前包规范中确定。角色指产品职责，实施写入者须服从项目现行开发调度规范。

## WP00｜当前基线、回归与运行账本

**负责人：集成 owner。依赖：无。**

读取现行任务文档与本包；保全 dirty 文件；R01–R14 分类；核实配置、schema、运行入口、可用凭据与服务能力，不能读取其他 harness 的私有配置充当产品能力。复用现有 request receipts，建立阶段耗时、调用数、输出长度、未处理页/未决项账本。

入口：`AGENTS.md`、`DOCUMENTS_MAP.md`、当前 `prd.md/design.md/implement.md`、`app/config.py`、`app/services/page_review_runtime.py`、`app/services/page_review_job_executor.py`、`app/services/prepared_review_workflow.py`。

先审测试 fixture 的隔离性，再运行已有最相关测试和 `probes/`。记录测试环境和失败；不为修所有旧失败阻塞首个闭环。产物：CURRENT_BASELINE、FINDING_DISPOSITION、一个有明确定义的基线账本。原件和原始模型 payload 不进公开仓库。

**退出：**确认当前主链、测试风险和已修复项；至少有可复现失败或明确静态证据，不以“看起来”定案。无产品语义改动，回退仅移除新增技术观测。

## WP01｜先解除条件-事实绑定的输出膨胀

**负责人：C 链 owner。依赖：WP00。**

入口：`app/llm/predicate_binding_candidates.py`、`candidate_fact_accounting.py`、`predicate_binding_batches.py`、`control_binding_candidates.py`；`app/services/predicate_binding_job.py`、`control_binding_job.py`、`binding_qualification.py`、`binding_qualification_support.py`、`qualified_binding_selection.py`、`prepared_review_workflow.py`；已有候选测试。

冻结新的候选输出合同：每个原子条件有 disposition；候选/反证边引用事实与来源；未决原因明确；输入范围由程序 manifest 保存。事实分批不等于解决 O(P×F)，要去掉全矩阵的逐格长解释。使用可复现检索/分面候选与否定/无命中的补查，不能删 normal facts 或只取 top-k 后宣称全查。

统一预算来源和 provider/context 校验，移除初始 65K–131K 与全局262K互相矛盾的限制。未完成响应不得发布；容量不足采用语义单元拆分，不能截掉末尾来源/条件。旧 payload 继续可读，新候选契约与测试工厂同步升级。

**退出：**已有规则/事实可走完一次 C 链，得到非全未知的有源结果；完整覆盖条件；保留高风险非候选补查；合成规模输出不再为每个无关配对写散文。保存请求、usage、结果与未决的前后对照。回退为旧候选合同的显式读取路径，不覆盖旧工件；不得回退到丢弃验证。

## WP02｜建立新来源政策与观察/核实/事实合同

**负责人：共享合同 owner。依赖：WP00。**

入口：`app/domain/contracts/page_review.py`、`evidence_normalizer.py`、`facts.py`、`evidence_locator.py`；`app/domain/page_reconciliation.py`、`page_review_evidence_sources.py`；`app/services/fact_normalization_source_adapter.py`、`page_review_visual_sources.py`；现有 source validity 和发布校验。

把“已核实”从“必须两个主读一致”中解耦，显式表达 native/OCR/single-visual/targeted-verification/manual source policy、原件出处、核实范围、可读性和未决。保留权威元组与所有来源一致性校验；旧双读 record 不改语义、不制造第二票。新合同必须供既有 normalizer 和 qualification 消费。

修复定位压缩：同页同源的相同文本可来自不同位置；仅同一个 occurrence/源区间重叠可做无损压缩。优先在保有几何/text offsets的层处理，不能丢掉这些信息后再用字符串包含判断。每个被压缩项有可还原 mapping；不会增加错误可用定位。

**退出：**真实单读取+针对核实工件可以保存、重建、消费，不依赖伪 A/B；同词不同项目/日期/位置保留；伪来源、跨受试者、错误 hash 仍拒绝。迁移增加式且旧报告可读。测试见 A03/A07/A12/A15。

## WP03｜低清扫描、手写与混合文字层读取

**负责人：B 链读取 owner。依赖：WP02 的合同冻结，可与其实现并行。**

入口：`app/evidence/page_processor.py`、`ocr_adapter.py`、`render.py`、`reading_view.py`；`app/services/evidence_processing_executor.py`、`page_review_execution.py`、`page_review_job_service.py`、`page_review_job_executor.py`、`targeted_page_review_executor.py`。

以所有页 manifest 为分母。原生文本/OCR 和可见内容覆盖合并考虑；扫描默认主 OCR，可靠原生不强制OCR，疑难区域可 VLM主读。全页覆盖检查不只依靠 OCR 报“有手写”；复用已有版面/风险工件，避免固定再加一个整页长输出 Agent。

多报告页建立区域归属，低清/屏幕翻拍保留原图、派生阅读视图与坐标映射；针对核实保留足够表头/日期/单位上下文。正常结果不能按规则相关性丢弃。原件不可读时保留未决，不生成补字图。

**退出：**A01–A09 场景通过；单主读政策不是旁路；未读区域和假空白不会被算作完整；表格错行与 NCS 对象覆盖受控。先少量代表页集成，再进行30–150页资料验证，不先横评所有模型。

## WP04｜角色路由、并发、预算及可恢复循环

**负责人：harness/runtime owner。依赖：WP00，接口与 WP02 协调。**

入口：`app/llm/page_review_harness.py`、`page_reader_capabilities.py`、`page_review_admission.py`、`page_review_transport_options.py`；`app/services/page_review_runtime.py`、`page_review_cancellation.py`；`app/workflow/` 既有持久调度。

正式任务按角色配置，不再让文字绑定/专业判断核实统一继承“两个page reader”的前置。默认云端产品路线；本地模型管理不再是新默认的启动前提，但不删除历史兼容。不凭名称猜 vision/schema/上下文上限。

冻结 requested/resolved/observed identity；维护显式别名/网关 envelope 合同、流完成检查、敏感回执分层。修改 `_streamed_chat_completion` 不仅记最后模型；合法别名通过，未经声明的实质变化隔离或失败。

预算按任务与输入规模；transport retry、schema repair、semantic reread 分开。有界队列、provider级共享限流、公平调度、429释放worker、取消与晚到响应 fencing。设置测量用起始并发而不是宣称最优；每轮无进展停在明确未决。

**退出：**A17–A21/A27通过，待重试不独占全部槽；失败不修改已完成兄弟结果；不完整响应不可发布。回退按角色配置选择旧运行策略，新旧工件分别标记。

## WP05｜规范化、元数据采用、完整条件与跨章要求

**负责人：事实/资格 owner。依赖：WP01/WP02；与WP03/WP04联调。**

入口：`app/services/fact_normalization_source_adapter.py`、`fact_normalization_executor.py`、`fact_publication_service.py`、`evidence_expectation_projection_service.py`、`frozen_review_calculation.py`；`app/projections/evidence_expectations.py`；`app/domain/expression.py`、`control_layer_evaluation.py`。

将新来源合同接入下游所有门禁。拆掉固定双读的实现约束，不删来源核实要求。文件元数据区分自动有据采用与人工确认；无法确定的 source party 不猜，但也不因无关元数据未知而阻断整份资料的所有事实处理。

跨章控制仍有模板级处置：适用、未适用、尚未到期、待判断/不支持均可回到规则与节点。不能只有日志；不能全部当无条件缺失。字段/条款判断、gap reason、技术失败分层。保留精确比较、单位、日期精度、复查选择、例外和研究者判断边界。

**退出：**A10–A16/A23/A28/A30，三链使用同一发布修订；部分事实可先保存但当前判定不隐瞒相关未决。禁止用人工确认假标记跨过 gate。

## WP06｜例外驱动的医学经理工作台

**负责人：前端/API owner。依赖：WP02/WP05，界面壳可并行。**

入口：`frontend/src/pages/EligibilityWorkbenchPage.tsx`、`EvidencePage.tsx`、`ReviewActionsPage.tsx`；`frontend/src/api/eligibility-review` 对应现有模块；`OriginalEvidenceViewer`；`app/services/eligibility_review_projection.py`、`review_action_worklist.py`、`patient_profile_service.py`。

默认风险/冲突/未决队列，根因聚合 + 条款影响计数；全部条款/事实/时间线/处理状态和原件一键下钻。点击 issue 定位字段原件，同时显示规则原文、对象/时间、冲突各方及具体动作。不会用 top-N 把其他风险藏掉。

可靠元数据自动处理，必要歧义才询问；不要求每页/每字段/每条款确认。保存系统审核报告无需逐条勾选。关闭 issue 不改资格，补证/修订才产生新审核。

API 提供独立 protocol/rule/episode/snapshot/processing/profile/review identities，界面不能把 episode 当资料版本、rule 当档案版本。区分草稿/处理中/已完成系统审核及临床意见；系统审核不是最终入组决定。

**退出：**A22–A24/A26；1080P/2K/4K真实浏览器；所有真实问题可到达；无不必要逐条确认；切换对象无旧响应覆盖新状态。新 UI 可回到旧只读报告，不改变存储临床结论。

## WP07｜更正、补证及有依据的增量复用

**负责人：增量/存储 owner。依赖：WP02/WP05；接口可先定义。**

入口：`app/services/fact_correction_service.py`、`evidence_correction_service.py`、`evidence_revision_builder.py`、`evidence_revision_workflow.py`、`review_history_service.py`、`page_review_recovery.py`；既有ArtifactStore和FactAuthority。

建立实际依赖：原件→视图/观察→事实→对应/资格→判定/报告。元数据改正不默认重OCR；规则/节点变化不默认重读原图，但旧观察若实际依赖这些上下文则不能盲复用。

新增文档使“在此前所给范围未发现”的检索结果失效，不能只看直接fact依赖。精确重复字节可复用提取，保留上传事件与归属；近重复/不同批注不能自动当同一原件。新报告冻结新版本，旧不变。

**退出：**A12/A15/A25/A29；一次补证、一次字段更正、一次元数据更正分别给出实际重算闭包/未重算理由；旧报告hash和显示不变。回退仅切换活动修订，不覆盖旧内容。

## WP08｜真实闭环、百页级质量/性能和剩余全仓审阅

**负责人：独立验证 owner，集成 owner交付。依赖：WP01–WP07。**

先单例，后规模与跨方案；不要用几十轮源码会商代替真实运行。代表集有低清、小字、翻拍、手写、跨页、多来源矛盾；合成测试和真实材料分开，gold不上产品输入。

测读取召回、数值/单位/对象/时间联合正确、关键误清零计数、每条规则有真实处置、最终误报/漏报、必要与不必要人工操作、首次有用输出和全程耗时。报告原始计数/分母；样本少不能宣称统计学泛化。

补足上一轮未做的全仓领域：方案解构/控制/发布链、所有qualification与normalization路径、数据库迁移/并发/lease、上传解析与本地服务安全、前端构建/E2E。新发现先可复现再分类，不能以此拖延已经可交付的单例。

**退出：**有全流程证据、真实未决和明确剩余范围；质量不过不得用提速覆盖。发布前依策略默认与实际运行一致，不再出现 PRD称取消双读而常规路径仍双读的情况。

## 协同与每包统一回执

每包提交：基线/受影响文件；合同与迁移；失败→修复用例；实际命令/退出码；mock与真实运行区分；生产/存储/消费/UI接通状态；原件与旧版本保护；新风险/回退。共享合同一次冻结，分工按接口同步；集成 owner维护唯一现行任务索引，历史checkpoint不反复注入每个运行prompt。
