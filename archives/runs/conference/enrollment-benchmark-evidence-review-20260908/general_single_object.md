证据已充分。成稿前汇总：我已覆盖五份点名笔记、四组已完成 run 的合同/回执、两份 attempts CSV、41 条合同失败回放、27 组双读对账回放、两份金标与三份数值切片，以及代码范围内四个脚本与两个产品模块。以下为完整报告。

# Conference Participant Output: enrollment-benchmark-evidence-review-20260908 - general_single_object

## Boundary Check

- 本会话为 Codex 主持会商的 `general_single_object` 参与者，只读审阅，未写任何文件、未运行模型/测试/网络命令、未读取数据库/blobs/.env/凭据/home 配置。
- 阅读范围限于 context 允许的只读源根 `artifacts/phase55-model-comparison/20260907`（五份点名笔记 + 根目录其余直接相关笔记、四组已完成 run 的合同/回执/结果、两份 attempts CSV、41 条 contract-failure-replay、27 组 pair 回放、金标与数值切片、preflight 抽样）与代码范围（`scripts/score_reader_lab_values.py`、`scripts/summarize_frozen_reader_runs.py`、`scripts/run_frozen_product_reader.py`、`scripts/run_frozen_normalizer_comparison.py`、`app/llm/page_review_batch_experiment.py`、`app/domain/page_reconciliation.py`、`app/config.py` 中 PAGE_REVIEW 两项常量）。
- `product-runs-resume-20260908` 按 context 排除出结论；下文仅在其**污染了已完成汇总产物**时提及该事实本身。
- 不给模型排名、不做临床结论、不建议默认模型替换。Codex 保留最终综合与验收。

## Independent Work Product

### 最高影响发现（主动挑战结论）

**当前证据指向的最大变量不是模型质量，而是产品自身的两个环节：双读对账吞吐近乎为零、多页合并读片质量崩塌。** 任何以“哪个模型更强”为主线的横评总结都会掩盖这一点。

**观察 1（对账）：** 27 组已保存双读回放（`pair-replays/` 9 组 + `pair-complete24/` 18 组）合计仅采信 **36 条事实**（平均 1.3 条/组），其中 **16 组零采信**；同时产生 **455 条事实冲突、117 条手写冲突、28 条信号冲突**。`reconcile_page_reviews` 的采信条件是两读 `normalization_key` 字符串完全相等，而该 key 由模型自行给出的 field_name、normalized_value、context 拼接哈希构成。实例（`pair-replays/d001-glm-high-cms-high-page-44.json`）：GLM 记录字段名带原文星号 `*受累体表面积相当于手掌数`、值格式为 `2`，CMS 记录为 `受累体表面积相当于手掌数`、值格式 `2(手掌)`——数值都对，键永不相等。**推断：** 这是合同设计导致的“表达不一致=无共识”，属**代码诱导失败类**，不是模型读错；它同时把真分歧（GLM high 把 E 评分读成 2）和表达差异压进同一个“未采信”桶，冲突队列却膨胀到数百条。若产品按现设计上线异构双读，两轮定向复核将被 455 条机械冲突撑爆，时间和费用结论都会被该环节改写。

**观察 2（批次读片）：** `product-runs-batch-v2` 三页合并请求在稠密化验页上严重欠提取：生化页（34 项金标）Gemini 批次 4/34、GLM 8/34，而同模型逐页跑同页均 34/34；血常规页（29 项）批次 6/29、5/29 对逐页 29/29、17/29。批次预算起点为单页 `route.max_tokens` 不乘页数、仅翻倍一次（`page_review_batch_experiment.py` 模块声明），对三张稠密页结构性不足。**推断：** 至少对本样本，输入组织方式造成的差异远大于模型间差异；但 n=1 批次/模型，只能称“初步观察到严重退步”，不能定论——需按计划在“未用于调优的页面”复验并区分“真漏提取”与“字段命名漂移导致 unmapped”。

### 分维度审阅

**A. 模型质量——现有证据能支持什么、不能支持什么**

- 可支持：两个机器金标页的数值切片。血常规 29 项：Gemini high 29/29（三个输入布局下重复）；GLM low 在 stable-prefix/source-reading 布局 23-24/29、基线 17/29；CMS low 20/4 错、Luna max 20 对但 9 错（错值多于漏值，误差性质更差）；MiniMax low（resume 代，仅参考）22 对 0 错。生化 34 项：Gemini/GLM-low/MiniMax-high 原生记录 34/34。`score_reader_lab_values.py` 计分保守（仅取前导标量、不翻参考范围找答案、重复观察计 ambiguous），方向可信。
- 关键反例（模型质量 ≠ 产品通过）：`product-runs-resume-20260908/glm-high-page-17` 产品记录被合同以“页级摘录引用了当前条款包不存在的条款”拒收，但 `raw-candidate-biochemistry-slice.json` 显示其**原始文本 34/34 全对**。schema 失败被 `failed_records_not_scored` 排除后，仅看 record 层成绩会系统性低估模型读片质量、高估合同损失——双轴分离（raw 诊断 vs 产品验收）是本套证据的正确设计，总结时必须两层并列。
- 不能支持：总体模型排名。覆盖率严重不均衡：24 页全覆盖仅 Gemini high 与 GLM low（`product-runs-complete24`）；多数模型只有 0/9/17/18/19/42/44 抽样页；同页重复调用稳定性仅 D001 42 页一处观察（“一次调用不代表稳定性”，d001-source-review.md）；手写归属、日期/单位、否定与跨页关联仅有定性笔记（sar-complete24、page-9、pages-18-19 四份 source-review），无机器金标。
- 外部 OCR 榜（external-ocr-reference）：仅作背景。逐字转录任务与本产品任务不同构，且已有单页反转实例（Gemini 数值优于 Luna，榜上相反）；不得移用其名次、token、秒数。

**B. 产品输出合同**

- `contract-failure-replay.json` 41 条全部带 `response_file_sha256`、`replay_code_verified`、`scope=response_contract_validation_not_request_reexecution`，基于真实响应离线复验，把失败细分为四类：JSON 无法修复（10）、pydantic 校验错误 1–43 项（14）、“资料对象或时间关联不符合合同”（15）、“摘录引用不存在条款”（4）。这组证据是“代码诱导 vs 模型诱导”归类的正确基础。**缺口：** 回放未声明覆盖全部 schema 失败 run（如 transport-v3 的 luna-low-page-3/6 是否在内未逐条核对），总结前应核对覆盖率。
- 失败种类 `failure_kind`（schema/invalid_json/length/endpoint）粒度过粗：schema 桶混装了模型格式错误、条款引用错误、对象/时间关联错误等医学语义完全不同的失败。41 条回放做了事后细分，但 CSV/状态层看不到。
- MiniMax（CMS）双返回“无审核价值”+非空事实被产品正确拒收（pages-18-19 笔记 + 回放确认）；同时其 usage 恒 `output_tokens=0` 而 `completion_tokens` 非零（回执保留双值 + `output_usage_disagreement=True`，未按零计费处理）——合同与计量诚实性处理正确。
- 坐标契约缺陷已记录（harness-findings #4）：bbox 无坐标空间/尺寸/旋转定义，Gemini 在 D001 44 页输出千分比坐标，跨模型 bbox 不可直接比较或画框。**这是产品合同缺口，不应记为模型不可靠。**
- `run_frozen_product_reader.py` 的冻结纪律扎实：manifest 逐文件 SHA-256、product-code 与当前 `app/` 逐字节比对（版本漂移即拒跑）、本地模型提交前 idle 检查、Luna 通道 `output_budget_enforced=False` 如实记录。这使跨代际比较的输入/代码一致性有保障。

**C. 对账失败**（见最高影响发现观察 1，补充两点）

- harness-findings #8 的“0 组采信、explicit_conflict_fields 为空”在本审阅的更大样本（27 组）下需修正表述：`fact_conflicts` 并不空（合计 455 条），空的是**采信集**。风险表述应改为“采信吞吐趋零 + 机械冲突泛滥”，比“无冲突输出”更准确也更严重。
- 全部 27 组均为**跨模型**配对（GLM×CMS、GLM×Gemini）；无同模型 main-A×main-B 对账回放（D001 Gemini 的 main-A/main-B 双份 run 已存在但未见配对回放文件）。同模型对账能分离“模型多样性”与“键匹配机制”两个变量，是当前证据矩阵的空洞。

**D. 时间与费用可比性**

时间（观察，来自两份 attempts CSV 与回执）：
1. `elapsed_seconds` 语义不同质：本地 run 含模型加载（首调 +21.3s，local-effort-check）、响应返回后后台 postcommit 未停（harness-findings #9）；远程含通道排队。**900.2s 与 459.96s 的 endpoint 行是客户端超时（`PAGE_REVIEW_TIMEOUT_SECONDS` 默认 900）与协议错误造成的右删失，不是模型延迟**，任何均值/排名必须先剔除或单独标注。
2. 重试未聚合：omlx-qwen38-high-page-9 首试 1473.8s（length）+二试 692.7s = 2166.5s 才完成；normalizer 的 GLM high 三试各 ~600s 共 1800s 零产出。按“每次成功”或“单试”统计都会失真，须按“完成一次有效产出总耗时”另列。
3. **GLM high normalizer 的 600 秒是产品运输内部超时**（`normalizer-native-runs/glm-high/receipts.json` 三条 APITimeoutError，600.06–600.22s；页面审阅超时却是 900s）。同一产品内两个环节超时阈值不一致，使 GLM high 在 normalizer 环节的“失败”部分是**配置诱导**。600s 常量出处未在本审阅代码范围内读到（推断，见验证需求 6）。
4. normalizer 重试输入递增（33875→40731→50124 input tokens）：产品运输把前轮 assistant 输出追加进多轮上下文，单试比较无效，费用/时延须累计。
5. effort 不是受控变量：Qwen3.6 模板无 effort 分支（三档渲染同串同 SHA）；Qwen3.8 原生拒绝 high（经 oMLX 映射到 xhigh），请求标签≠后端行为；Gemini effort 嵌在模型名（`gemini-3.7-flash-high`）；Luna max/high 不同参试者。各模型 effort 语义不可互比，只能按“声明的参试组合”逐个报告。
6. **MiniMax-M3 的 effort 是否生效未证实**：low/high 同一 response_model，reasoning_tokens 恒 0，但 page-44 high 回执 `reasoning_content_characters=87500`——思考内容不计 token。CMS low/high 的差异结论（如 44 页 low schema 失败、high 通过）不能归因于 effort。

费用（结论：**当前不可比，只能报告 token 趋势**）：
- `api_cost` 全列空（`summarize_frozen_reader_runs.py` 明确输出 None）；`pricing-reference-20260908.md`：MiniMax 与 GLM-5.3-Flash 官方价“待核实”，Luna 走 Codex 订阅、Gemini 走 Antigravity 通道，均非按清单实付。四个通道里两个无价、两个不按价付——**费用维度本轮没有可辩护的数字**，硬造排名会违反测试计划“费用按已核实价格或账户实际费用”的约定。
- 计量口径不可跨提供者直接比较：input_tokens 是各提供方自报 token 数（同页 GLM 36829 / Gemini 40564 / MiniMax 36896），tokenizer 不同；图像 token 有的计（Gemini）有的报 0（MiniMax `image_tokens=0`）；MiniMax completion/output 双值矛盾；思考 token Gemini 单列（thoughtsTokenCount）、OpenAI 已含于输出（不可重复相加）。pricing-reference 已正确记录这些口径坑，总结时必须逐条执行。
- 缓存命中波动大（CMS 128/768 → 36895/39040），估算须缓存/非缓存分列（pricing-reference 已要求，尚未执行）。

### 仍缺的正式产品环节测试（对照 test-plan.md 五环节矩阵）

| 计划环节 | 已有冻结证据 | 缺口 |
| --- | --- | --- |
| 方案解构 | **无**（本源根内零证据） | 整环节未测：条款完整性、原编号/父子逻辑、跨章节随机节点投影（d001 笔记已警示 EX-09d 不能只按文字验收） |
| 逐页判读 | 最充分（9 代 run、数百 attempts） | 24 页全覆盖仅 2 组合；多数模型仅抽样页；重复调用稳定性未测；D001 三页之外的手写/量表页无定量金标 |
| 双读核对与复核 | 仅离线回放 | **活体两轮定向复核循环零次执行**（`targeted_page_review_executor` 未在真实冲突负载下跑过）；带 OCR 关联文本的回放未做（harness-findings #8 自认）；同模型 A/B 对账回放缺失 |
| 正式事实与 Profile | 单 job 单 call 的组件级 normalizer（`component_only=true`） | 14 个 call 仅测 1 个；远程四通道中仅 GLM 走 product_native_transport，Gemini/Luna/CMS 用 `candidate_adapter_diagnostic`（非产品运输，`formal_transport_comparison=false`）；source-audit `source_check_passed=false`；**Profile 纵向环节零证据** |
| 入排评估 | **无** | 整环节未测；不得以临时提示伪装（test-plan 明令） |
| 完整链路 | 无 | 计划上排在单环节之后，尚未到执行条件 |
| 时间/费用全流程 | 仅单环节单试 elapsed | 计划要求的“准备+初读+重试+核对+规范化+评估、单环节 vs 用户等待全流程、失败计费、缓存单列”均未产出 |

## Evidence And Assumptions

**证据（均为本审阅直接读取）：**
- 笔记：`d001-source-review.md`、`sar-complete24-source-review.md`、`normalizer-native-source-review.md`、`pricing-reference-20260908.md`、`external-ocr-reference-20260908.md`、`harness-findings.md`、`local-effort-check-20260908.md`、`page-9-source-review.md`、`pages-18-19-source-review.md`（均为 context 声明的临时性所有者观察，未当金标准）。
- 运行层：`reader-attempts.csv`（225 行）、`normalizer-attempts.csv`（41 行）、`normalizer-native-runs/glm-high/{receipts,result,transport-contract,source-audit}.json`、`product-runs-64k-transport-v3/d001-cms-high-page-44/{record,receipts}.json`、`product-runs-resume-20260908/*/status.json`（20 个目录，仍在产出新目录）。
- 校验层：`contract-failure-replay.json`（41 条）、`pair-replays/`（9 组）+ `pair-complete24/`（18 组）聚合、`gold-sar-lab-page9.json`、`gold-sar-biochemistry-page17.json`、三份数值切片的 counts。
- 代码：上述六个脚本/模块 + `app/config.py:220,224`（PAGE_REVIEW_MAX_TOKENS=12000 默认、PAGE_REVIEW_TIMEOUT_SECONDS=900 默认）。

**假设（已声明，未独立验证）：**
- glm-high normalizer 三次 600s 为产品运输（DeepSeek 通道）内部超时常量——由回执形态推断，未读到该常量代码。
- 批次提取崩塌主因是“真欠提取”还是“字段命名漂移导致 unmapped”未逐行核验切片 rows；崩塌本身是观察，归因是推断。
- CMS 通道（new-api.mediportal.com.cn）转发是否透传 reasoning_effort 未验证。
- pair-complete24 的 18 组配对模型组成为 Gemini high × GLM low（由 product-runs-complete24 目录组成推断，未逐文件核对 source_records 身份字段）。

**本审阅自我修正记录：** 初次聚合 pair 回放时读了顶层键得到“0 采信 0 冲突”的错误结论，复核文件结构后发现结果嵌套于 `reconciliation` 键下，修正为 36 采信/455 冲突。此过程说明**对账汇总产物尚不存在**——27 组回放没有任何一份机器可读的汇总文件，全靠临时脚本聚合，正是需要补的产物。

## Risks, Gaps, And Verification Needs

1. **resume 污染已完成汇总（最高优先，机械性）**：09:33–09:44 生成的 `sar-biochemistry-numeric-slice.json`、`raw-candidate-biochemistry-slice.json` 与 `reader-attempts.csv` 均含 `product-runs-resume-20260908` 行，与 context“排除出结论”直接矛盾。任何基于这三份文件的总结都会吸入未冻结数据。缓解：重新生成时按代际白名单过滤，或在每行加 generation 列与 `in_progress` 标记。
2. **对账吞吐是产品上线阻塞项**：455 条机械冲突 × 最多两轮定向复核的费用/时延会吞掉模型环节的全部优化；若先跑更多模型而不修键匹配，后续所有双读数据的解释力持续衰减。
3. **“需要核对”状态语义混装**：normalizer CSV 里 glm-high（三次超时零输出）与 omlx（有输出待核）同为“需要核对”，且 `failure_kind` 空——下游按状态过滤会把超时失败当待办而非失败。state 口径应区分 `transport_failed`。
4. **费用维度结论悬空**：若总结报告需要费用列，当前唯一诚实写法是“不可比 + 已核价两通道的区间估算 + token 趋势”。跳过核价就出费用表是可预见审阅反对点。
5. **批次实验结构性欠预算**（65536 不乘页数、仅一次翻倍）使“批次 vs 逐页”比较偏向逐页；若要公平回答计划里的上下文组织问题，批次预算应按页数缩放后重跑（这是实验设计修正，不是产品结论）。
6. **待核清单**：(a) 600s normalizer 超时常量出处（`app/agents/deepseek_evidence_normalizer_transport.py` 一带）；(b) MiniMax effort 透传（request-0.json 应有 payload 证据）；(c) 41 条回放对全部 schema 失败 run 的覆盖率；(d) 批次切片 rows 的 missing 与命名漂移分解；(e) `explicit_conflict_fields`（API 投影）与 `fact_conflicts` 的投影关系，解释 harness-findings #8 的“空”表述。

**给 Codex 的有界问题（附安全暂记路径）：**
1. MiniMax-M3 经 cms-smk 是否确认发送并生效 reasoning_effort？若否，CMS low/high 合并为单一参试配置（暂按“未证实生效”报告，不删除行）。
2. resume 行从三份汇总产物中剔除是“重新生成”还是“综合时手工过滤”？（建议重新生成 + 代际白名单，一次性消除复发风险。）
3. 对账键匹配的语义对齐（字段名字典、值/单位规范化、context 位置对齐）是否作为产品修订立项并用 27 组冻结回放离线复测？此步零模型调用、当日内可出吞吐对比（建议为下一动作首选）。
4. 方案解构与入排评估两环节是在本轮补测（D001 DOCX 与已发布规则已冻结，具备条件），还是在 20260907 报告中显式声明“未覆盖”？影响“正式横评已完成”这句话能否成立。
5. normalizer 600s 超时属产品配置还是脚本？若属产品，按产品缺口记录还是为本轮对齐到 900s？（暂按“配置诱导失败，不计入模型质量”报告。）

## Recommended Next Step

**第一步（零模型调用、决定性、当日可完成）：修汇总与对账回放。**
1. 以代际白名单（排除 resume-20260908）重新生成 reader-attempts.csv 与三份数值切片；给 normalizer 状态拆分 transport_failed。
2. 写一份 `reconciliation-replay-summary.json`：27 组回放的采信数/冲突数/冲突原因分布 + 失配键的逐字段 diff（GLM `2` vs CMS `2(手掌)`、星号字段名、location_text 差异各占多少条）。455 条冲突分类后，“代码诱导 vs 模型诱导”的比例第一次有了数字。
3. 依据该分类做键匹配对齐的最小修订设计，用同一批回放复测吞吐——这是双读架构去留的第一个硬证据。

**第二步（最小增量模型测试，按计划顺序补环节）：** D001 冻结输入上的方案解构单环节（至少 2 个候选）；d001-page-44 一对模型跑一次活体定向复核循环（用真实冲突负载）；normalizer 扩到同 job 全部 14 个 call 并为 Gemini/Luna/CMS 声明运输等价性或标记不可比。

**第三步（费用）：** 核实 MiniMax 与 GLM 官方价后按 pricing-reference 的口径规则（成败分别累计、缓存分列、思考/正文口径分提供者）产出区间估算；Luna/Gemini 永远标注“订阅通道、非实付”。

**明确不做：** 不出模型总排名；不基于 2 页金标或单页反例替换默认模型；不在 resume 冻结前出任何含其数据的总结。
