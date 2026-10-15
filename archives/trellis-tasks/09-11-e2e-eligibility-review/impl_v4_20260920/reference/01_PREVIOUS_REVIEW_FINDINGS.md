# 第一轮审阅发现

基线：`60f5bb8fe67ac14d44af9ceab0801a9b2a42120b`。以下以函数/契约定位，不依赖后续可能变化的行号。

## 分级与证据口径

P1：阻断当前主链、导致已决定需求未落地，或影响重要来源/覆盖可信度。P2：可追溯性、恢复成本、维护性和交互问题。这里的优先级是工程建议，不等同于已经发生临床错误。

“代码确认”是静态行为证据；“摘录复现”是无依赖局部实验；“作者运行记录”未由本次环境复跑；“待核实”不得写成实际事故。

## R01 / P1：旧全量双读仍是执行主干，与现行 PRD 明确冲突

**证据：代码确认 + 需求原文。**

PRD 明确取消所有事实固定双 VLM、每页完整 ClausePack、所有角色统一 65K 下限。当前 `review_page` 无条件启动两个完整 `read_page`；`preflight_page_reader_routes` 要求两个主读道；常规消息仍包含完整条款包和输出 schema；最低预算仍为 65536。

`source_aligned_fact_pairs` 并不是单模型读取的替代路线。它仍要求两个主读、同一原件、同一来源区间、相同值/单位等，仅放宽部分位置表达差异。不能将这个补丁称为已经实现单主读。

**影响：** 不论页面复杂度、资料可靠性和当前任务，仍承担双完整阅读、核对和重读成本。将 OCR 改得更快也无法消除后半程重复劳动。

**修改方向：** 在既有任务/工件/权威元组中接入明确的新读取策略；旧双读作为历史可读或明确选择的高风险策略，而不是全局必经路径。不能仅设置 `require_page_review=False` 绕过来源门禁。

**定位：** S01、S02、S03、S04、S05。

## R02 / P1：逐条件 × 逐事实的长解释造成输出笛卡尔积

**证据：代码确认 + 作者运行记录。**

`build_predicate_binding_messages` 对每个谓词要求对全部事实逐条写 `considered_facts`，非对应事实也必须返回定位与解释。主要成本来自输出数量及重复解释，而不是病例真实复杂度。事实分批也不自动改变总配对数量，若每批仍遍历所有条件，总体输出仍可能维持 O(P×F)。

最新 checkpoint 自报约 20 个原子条件 × 55 个事实导致约 28 万字符输出，双道 `finish=length`。这不是本次实测，但与源码相互印证。

**修改方向：** 分离“系统确实提供了哪些事实”“哪些候选关联被发现”“哪些关联经来源核实”“哪些条件仍未决”。系统生成输入覆盖清单；模型只返回候选边、关键反证和具体不确定性。若某一步确有逐项核对需要，用紧凑状态和分组原因，避免逐格长散文。不能把系统生成的清单说成模型已正确理解了每一事实。

**不可减掉：** 全部官方/例外/跨章条件的结果覆盖；明确否认与未发现的区分；低召回检索的补查机制；来源和时间资格。

**定位：** S06、S07、S08。

## R03 / P1：262K 预算修复不一致，默认重试仍达不到新上限

**证据：代码确认 + 摘录复现。**

- `MAX_SEMANTIC_OUTPUT_TOKENS = 262144`。
- `enqueue_predicate_candidates`、`read_predicate_candidates`、`read_candidate_payload` 初始输入仍限制为 65536–131072。
- 默认 `PAGE_REVIEW_MAX_TOKENS = 65536`。
- `read_candidate_payload` 只在第一次 `length` 后翻倍一次。

本次局部实验实际结果：

| 初始预算 | 两次都截断时的请求预算 | 结果 |
|---|---|---|
| 65536 | 65536 → 131072 | 失败，不到 262144 |
| 131072 | 131072 → 262144 | 第二次仍截断则失败 |
| 262144 | 没有发出请求 | 初始校验拒绝 |

**影响：** “只修改全局上限再重跑”不足以证明当前阻塞已解除。不同任务可接受的配置范围也不一致。

**修改方向：** 统一任务预算合同、请求前能力检查、累计消耗和重试策略；优先解决 R02，不建议将所有下限/上限一起改成更大数值。模型 context 上限、最大输出和本次输入占用必须区分。

**定位：** S06、S07、S09、S10。实验：`probe_results.json`。

## R04 / P1：响应模型身份记录了，但没有在核心读取中按策略核实

**证据：代码确认 + 局部探针；不是临床误判实证。**

`PageCompletion` 包含 `response_model`；页任务回执也保存实际响应名。但 `read_page` 构造 `PageReviewRecord` 时写入请求的 `route.model`，未对实际响应模型做身份策略核对。流式累积函数不断覆盖模型字段，未保留整条流模型声明序列。绑定通用读取函数同样未做身份检查；所读候选比较代码核对请求模型和完成状态，未核对实际响应模型。

局部探针中，请求名与合成响应名不同，`read_candidate_payload` 仍返回解析成功。这里仅证明 helper 接受，不能据此声称完整资格门禁已经发布了错误临床结论。

**影响：** 网关替换模型、两道实际落到同一模型、或运行中更换上游，可能无法从主要记录正确识别；“两次读取”不能因此自动称为“两个独立模型”。

**修改方向：** 保留 requested / resolved / response / deployment identity；允许显式登记的别名，不做宽泛字符串相似匹配。流中身份变化留完整回执；未批准的变化失败或变成明确不可用于该核实策略的记录，不偷偷降级。在新单主读政策中也不要伪造双读身份。

**定位：** S03、S06、S07、S11。

## R05 / P1：跨章控制资料期望被日志化跳过，返回集合不再覆盖全部模板

**证据：代码确认。**

`project_expectations` 和 `EvidenceExpectationProjectionService.project` 遇 `template.control_origin is not None` 时 warning 后 `continue`。前者文档仍称一个模板恰好一条期望。单模板投影拒绝未接入条件的控制模板，这种拒绝本身比无条件套用更安全；问题是批量层将其从结果中直接省略。

**准确边界：** 这不等于“整个系统完全不处理跨章要求”。冻结审核计算另有控制链，并要求完整控制输入。本条专指资料期望投影完整性和用户可见性，不能扩大为已证明所有临床终点均漏算。

**修改方向：** 已核实事实可独立保存；未投影控制要求仍以结构化 `not_evaluated` / `unsupported` / 明确待核实状态呈现，带 control_id、阶段、原因和后续动作。正式接入适用条件与来源有效期。不要为数量齐全而写 `observed`，也不要恢复成所有控制无条件阻塞全部事实。

**验收：** 含一个普通模板和一个控制模板的合成病例，返回结果或同级可见未决清单必须可对账覆盖二者；不能只记日志。

**定位：** S12、S13、S14。

## R06 / P2：前端将审核节点/规则版本误标成资料/档案版本

**证据：代码确认。**

`EligibilityWorkbenchPage` 页脚：

```
资料版本：formatSnapshotVersion(selectedEpisode.revision, null)
档案版本：formatSnapshotVersion(reviewData.ruleSetRevision, null)
```

审核节点 revision 不是证据快照版本；ruleSetRevision 也不是患者档案版本。页面标题另外使用项目目录的方案版本，应核实它与当前报告冻结版本是否始终一致。

**修改方向：** API/ViewModel 提供明确的 protocol/rule set、episode、evidence snapshot、processing revision、profile revision、review run identity。界面只显示真实具有对应语义的值；缺失就明确缺失，不拿别的 revision 凑展示。

**验收：** 所有版本故意取不同值；旧报告与当前项目版本不同；切换受试者/节点时不可显示前一对象资料。这里只确认页脚错配，尚未执行浏览器切换测试。

**定位：** S15。

## R07 / P1（待本地 pytest 确认）：新增输出合同未同步合法测试样例

**证据：代码与测试静态冲突，未运行仓库测试。**

`tests/v2/llm/test_predicate_binding_candidates.py::_case` 构造的合法样例不含 `fact_accounting`，多项测试却要求 `validate_predicate_candidates` 成功，或要求通过新增 schema。当前验证器明确对缺少该字段抛错，schema 也将其设为必填。所读 v2 公共 conftest 没有补齐这个字段的机制；本轮没有完整核查所有 pytest 插件/子目录 conftest，因此保留实际复现步骤。

**修改方向：** 按批准的新合同统一测试工厂；保留缺字段应拒绝的负例。不得删除测试或放宽校验来追求“全绿”。旧存储记录的可读兼容与新请求合法性分开。

**定位：** S06、S16、S17。

## R08 / P2：事实读取与条款包/节点/整组读道身份耦合，增量恢复成本高

**证据：代码身份绑定 + 作者已知问题记录；影响范围需继续追消费链。**

页判读记录身份包含 clause_pack、review_context、请求和模型配置；执行器会因 routes 改变拒绝旧任务。checkpoint 自报路由变化后不能局部重读，元数据确认晚于 build 会要求重建和重判。

这些拒绝用于防止旧结果冒充新上下文，有安全价值；不能简单删除。问题是“原件观察”“医学语义对应”“当前审核结论”的缓存和有效性边界没有充分分离。

**修改方向：** 原件及读取合同未变时复用已核实原件观察；只重新做受规则、节点、元数据语义影响的步骤。旧全条款提示生成的观察不能未经验证就迁移成协议无关缓存。每次更正/补证生成新的审核，旧报告不改。

**定位：** S03、S08、S11。

## R09 / P2：单调用内部等待/重试有界，但缺少清晰的端到端预算观测

**证据：所读 helper 的代码行为。全系统是否另有统一限制尚需核查。**

页读取和绑定可各进行 12 次 60 秒的限流等待，另有长度重试、格式修复、fallback 和作业重试。单函数有界，不等于一例所有节点的总成本可控。

**修改方向：** 记录父 run 的累计模型调用、排队/推理/修复耗时和无进展轮数；同输入连续失败应停在明确未决/技术失败，不无限重复。30 分钟不是硬终止临床核查线，不据此删除事实。

**定位：** S03、S06、S11。

## R10 / P2（策略切换风险）：有 PDF 文字层不等于临床内容已完整提取

**证据：路由代码；没有证明当前最终审核发生了漏读。**

`decide_route_detailed` 以 `native.text.strip()` 非空选择原生路线。混合扫描 PDF 可能只有页码/页眉可复制，主体仍是图像。当前后续全视觉链可能捕捉到它；因此这是改成 OCR/原生主路线时必须补齐的验收条件，不应直接宣传“当前系统已漏掉这些患者资料”。

**修改方向：** 来源完整性/可见内容覆盖检查，支持混合页面和局部图像区域；至少覆盖“仅页码文字层 + 主体扫描图”“隐藏错误 OCR 层”“多张报告同页”“跨页表头”等回归。

**定位：** S18。

## R11 / P2（次要性能）：原生读取探测结果未直接交给构建步骤

**证据：调用结构；耗时影响未测量。**

路由判断调用 `extract_native_page`，构建原生页又经 `_extract_native` 调用同一提取函数。应测量是否为重复解析热区；可将已经获得的不可变 NativePage 作为准备工件传递，但需保持哈希与来源绑定。不要在没有 profile 结果前将它排在大模型输出结构问题之前。

**定位：** S18。

## R12 / 产品决定，不直接定为 bug：本地优先与当前云端运行路线的边界

最新 checkpoint 记录 main-A 为 GLM、main-B 通过本地网关使用 MiniMax。localhost 仅证明网关监听本机，不证明模型推理在本机。此前 V3 要求产品显式配置，禁止悄悄远端代跑。

需要确认最近是否有新授权，以及原件图像、脱敏文本、结构化事实的发送边界。没有证据就不宣称发生了未经授权的数据外传，也不能默认为它已获批准。

## 不应当误报或删除的现有能力

1. OCR 已有内容寻址缓存、分段与请求/响应保存；不是缺少这些基础机制。
2. 正式页执行器的 coverage 来源是冻结页面清单，不是只按成功结果自定义分母。不能因低层便捷函数的构造方式就断言正式链路会漏页放行。
3. parent prepared-review job 等待 children 时不占用模型 worker；已存在持久任务和恢复机制，不需要再造一个编排平台。
4. 页 disposition=accepted 不自动代表所有事实已核实；需继续按事实、覆盖、发布等不同层检查，不能仅凭名称判定错误放行。
5. 时间窗、数值单位、来源资格、触发/例外、官方/控制完整范围已有明确边界。不能用取消验证来“解决”延迟。

## 本轮覆盖与尚未完成的全量验收

已做：仓库结构盘点；当前需求/交接/运行记录比对；OCR 与页读取关键段、页核对、正式页任务执行、绑定候选及其预算/回执、跨章期望、冻结计算和表达式关键段、前端版本展示、相关测试样例检查；局部 AST 探针。

尚未做：全仓所有文件逐行审阅；完整方案解构/控制生成及水合链的实际回归；事实归一化与所有 publication gate 的全链验证；数据库迁移/崩溃/并发故障注入；上传和本地服务安全测试；所有前端交互与 E2E；真实模型、用户 Mac、本地 dirty 状态及临床资料运行。不得用本报告取代这些验收。

## 固定提交证据索引

以下链接全部固定到同一提交，避免未来分支变化影响复核。

- S01: [.trellis/tasks/09-11-e2e-eligibility-review/prd.md](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/.trellis/tasks/09-11-e2e-eligibility-review/prd.md)
- S02: [app/services/page_review_execution.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/services/page_review_execution.py)
- S03: [app/llm/page_review_harness.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/llm/page_review_harness.py)
- S04: [app/domain/page_source_association.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/domain/page_source_association.py)
- S05: [.trellis/tasks/09-11-e2e-eligibility-review/AGENT_ASSIGNMENTS_V3_20260917.md](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/.trellis/tasks/09-11-e2e-eligibility-review/AGENT_ASSIGNMENTS_V3_20260917.md)
- S06: [app/llm/predicate_binding_candidates.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/llm/predicate_binding_candidates.py)
- S07: [app/services/predicate_binding_job.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/services/predicate_binding_job.py)
- S08: [.trellis/tasks/09-11-e2e-eligibility-review/CHECKPOINT_20260920_ABC_B_DONE_C_BINDING_LLM_BLOCKED.md](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/.trellis/tasks/09-11-e2e-eligibility-review/CHECKPOINT_20260920_ABC_B_DONE_C_BINDING_LLM_BLOCKED.md)
- S09: [app/llm/page_reader_capabilities.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/llm/page_reader_capabilities.py)
- S10: [app/config.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/config.py)
- S11: [app/services/page_review_job_executor.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/services/page_review_job_executor.py)
- S12: [app/projections/evidence_expectations.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/projections/evidence_expectations.py)
- S13: [app/services/evidence_expectation_projection_service.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/services/evidence_expectation_projection_service.py)
- S14: [app/services/frozen_review_calculation.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/services/frozen_review_calculation.py)
- S15: [frontend/src/pages/EligibilityWorkbenchPage.tsx](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/frontend/src/pages/EligibilityWorkbenchPage.tsx)
- S16: [tests/v2/llm/test_predicate_binding_candidates.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/tests/v2/llm/test_predicate_binding_candidates.py)
- S17: [tests/v2/conftest.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/tests/v2/conftest.py)
- S18: [app/evidence/page_processor.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/evidence/page_processor.py)
- S19: [app/evidence/ocr_adapter.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/evidence/ocr_adapter.py)
- S20: [app/services/prepared_review_workflow.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/services/prepared_review_workflow.py)
- S21: [app/domain/expression.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/domain/expression.py)
- S22: [app/domain/page_reconciliation.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/domain/page_reconciliation.py)
- S23: [AGENTS.md](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/AGENTS.md)
- S24: [DOCUMENTS_MAP.md](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/DOCUMENTS_MAP.md)
- S25: [pyproject.toml](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/pyproject.toml)
