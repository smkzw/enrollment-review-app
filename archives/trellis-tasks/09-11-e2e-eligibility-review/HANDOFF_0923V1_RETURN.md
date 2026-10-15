# 0923V1 审阅纠偏实施记录

更新：2026-09-23（Asia/Shanghai）。本文件记录本轮代码修订与只读审计，不构成恢复临床作业或最终验收。

## 现场与授权

- 唯一工作树：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`；分支 `codex/phase5-clinical-facts-profile`；本轮起始 HEAD `bc5d1cb815bf512c964784cda92914689ef1ce11`。
- 依据：用户提供的 `enrollment_review_0923V1_bc5d1cb.zip`，现行 `.trellis/tasks/09-11-e2e-eligibility-review/delivery_20260922/`、`prd.md`、`design.md`、`implement.md`。本包是增量纠偏，不创建新 Phase。
- 本轮授权代码修订与必要的定向检查；未授权恢复已取消的 W6 临床作业、调用收费端点、修改原始资料、提交或推送。所有原始方案、病例、已发布规则及草稿修订21未改。
- 工作树现有修改为本轮代码、测试与任务记录，均未提交。恢复者先 `git status --short` 和 `git diff`，不可 reset/clean。

## RV1-01–08 处置

| 审阅项 | 本轮处置与代码落点 | 仍需证据 |
|---|---|---|
| 01 短文本误判充分 | `app/evidence/selective_vision_review.py` 提升计划版本为 v2；扫描/视觉识别页置信未知、已知非文字标记、规则表格等不再仅凭8字跳过。保留可靠原生文字的快速路径。 | 生产材料加载器尚无独立手写/表格区域覆盖图；风险标记可能遗漏未被原始提取层识别的笔迹。真实病例逐页核查。 |
| 02 失败写成完成 | `app/services/selective_vision_postprocess_executor.py` 将来源未核实、缺图、失败关闭、观察缺页转为持久失败；`app/services/selective_vision_observation_service.py` 先保存可读页，缺图页另列；重试复用相同来源、提示、风险和模型的已成功页。`app/api/v2/evidence_processing.py` 给旧版终态任务可操作的重试入口。 | 人工重试已在测试数据库完整驱动；真实病例/服务失败仍待 Q3。不可读原件最终应作为具体资料缺口呈现。 |
| 03 旧计划身份误用 | v1→v2；`app/services/selective_vision_runtime.py` 将供应商、地址、模型、思考档位和输出额度组成不含密钥的身份；`selective_vision_postprocess_job_service.py` 用其区分任务，旧终态可启动新任务；`selective_vision_observation_service.py` 的成功观察再绑定OCR原文哈希。`fact_normalization_source_adapter.py` 在正式路径只收当前任务回执中的页ID与观察ID，不再枚举全部历史成功记录。 | 真实服务上的多供应商切换、别名模型回执、旧运行历史迁移及病例事实质量仍待验证；不允许热改连接后直接续跑。 |
| 04 跨章要求不可见 | `frontend/src/pages/EligibilityWorkbenchPage.tsx` 将 `controls[].obligations` 单列为“方案补充要求”，进入列表、筛选、计数、详情及病例事实原件关联；不伪装成 IN/EX 编号。 | 控制点的方案原文跨度尚未形成可点击定位；报告/打印与 UI 的正式同源计数待真实发布后对账。 |
| 05 100条硬上限 | 同一页面增加完整分页、筛选/选择统一处理、空结果无无关详情；101和250项、末尾深链反例通过。 | 最终宽屏 Ego Lite 真机交互与缩放仍待 Q3。 |
| 06 W6 分类与分包 | 只读冻结收口核对，结果见下节；没有粗暴删候选或按 SAR 硬编码。 | 需抽样核对来源/标题/临床角色和真实 tokens；再决定通用发现合同或有界分包调整。 |
| 07 失败步骤归属 | 现场 `deep_0007=failed_final`，`hydrate` 仍依赖它；纠正旧交接“只是历史失败”的错误。不对已取消 Job 做 SQL 修复。 | 下一轮须据活动 DAG/合同选择合法新作业或合法修复，不可仅 resume_cancelled。 |
| 08 更正闭环 | 旧的失效/历史保护不回退。 | 本轮未形成真实新事实、新工作稿、补证后的新结论；不得把 W5 合同测试说成完整病例验收。 |

## W6 冻结账本与恢复判断

只读数据库：`/Users/smkzw/tmp/enrollment-review-w6-20260922/data/enrollment-review-v2.sqlite3`。SQLite `-readonly` 查询 `jobs`、`job_steps`、`job_step_dependencies` 和 `job_checkpoints`；未读取或更改凭据。跨章作业 `0da5ef099b3e4972a012d14a3d5d75fe` 为 `cancelled`、`cancel_requested=1`、92/172；`deep_0007` 仍是活动 DAG 的 `failed_final`。`hydrate` 的依赖包含 `deep_0001` 至 `deep_0084`，因此仅恢复已取消步骤不足以完成。

冻结 `deterministic_closure` 有 1,927 个结构单元：candidate 488、uncertain 50、context_only 281、non_control 1,108。538 个 candidate/uncertain 拥有单元进入 84 个深审批次，批大小最小1、平均6.4、最大12；16批只有一个拥有单元；共59种标题路径，182次只读上下文引用。这里的分母分别是结构单元、深审批次、上下文引用，不可写成“84/85个单元进入深审”。未找到可信的模型 token 账本，token 开销记为 unknown。

538 个拥有单元的种类为 list_item 202、table_row 201、paragraph 129、table_note 4、footnote_or_annotation 2；摘录合计 28,670 字符，平均 53.3 字符（只是摘录长度，不是实际提示或 token 用量）。单单元批次中可见“盲法”“不良事件定义/分类”“统计估计目标”“知情同意过程”“附录过敏性休克处理”等标题；是否包含筛选/基线放行条件必须检查对应原文和跨章引用，不能只凭标题断定删除，但足以证明目前分类与标题分包需要分别诊断。

用产品 `build_protocol_control_agent_prompt` 对冻结 84 批重建输入，不调用模型：提示文本合计 7,381,055 字符；最小 83,015、中位 87,739.5、最大 101,301 字符。16 个单单元批次占 1,359,918 字符。批次序列化中已知官方目标重复约 1,020,684 字符、已知流程目标重复约 1,435,980 字符；实际提示还包括 Schema 等开销，所以不能把这些数直接换算为可省 token 或费用。538 个深审拥有单元中，目录指路性条目 20 个（7 candidate、13 uncertain），修订史 8 个 candidate。抽样包括只有“排除标准/禁用药物”及页码的目录项、只写“优化入排标准”的修订说明，也包括导入期真实限制和混合节点义务。前两者缺独立规范内容，但后者不能因此被删。实际供应商 token/重试耗时仍为 unknown。

只读分包模拟：按冻结单元原顺序、每批最多12个，允许相邻标题共批并保留逐单元来源/标题、必要上下文和已知目标，重建提示后得到45批、4,184,393字符（中位91,976，最大106,200）；相对旧84批减少约43%提示字符。但3批超过旧批次最长101,301字符，且没有实测模型输出质量、完整性或服务上下文上限；**这不是已接入的产品计划或速度收益**。不可凭模拟直接让45批替换84批，也不能把当前单批大小写成通用安全阈值。

抽样的决策理由显示“修订记录中可能涉及要求”会进 candidate，仅“盲法标题，无法可靠判断”会进 uncertain；同时文档总标题正确归为 non_control，修订史标题归为 context_only。说明至少需要核查修订史/标题粒度是否让深审范围扩大；不能未经来源核验就降级或删除它们。此前跨批 `non_control` 被有效候选引用后提升 `context_only` 的处理保留。

恢复决策：**本轮不续跑**。已完成结构分类、典型反例与产品提示字符量测量；供应商 token 账本缺失，不补造。通用发现提示已把导航/历史文字与真实当前要求区分，版本为 `control-discovery-prompt/v2`；执行版本为 `protocol-control-execution/v15`，旧取消作业不会与新提示混算。跨标题有界合批仍需按实际输出预算与来源关联验证，每个单元必须保留自身来源、标题及只读上下文。新作业从合法入口建立，旧回执仅作审计，逐项证明可复用范围才可引用；不得把 `failed_final` 改成成功或放宽 `finish_success`。新提示尚无模型质量验证。

## 验证与未运行

- 本轮真实运行：后端受影响套件 `90 passed`，含失败任务生命周期、v1迁移、8字/版面反例、不同模型不复用观察、缺图同批可读页保留与定向重试；仅第三方 SWIG 弃用警告。命令：`.venv/bin/python -m pytest tests/v2/evidence/test_selective_vision_review.py tests/v2/services/test_selective_vision_observation_service.py tests/v2/services/test_selective_vision_postfreeze_orchestration.py tests/v2/services/test_selective_vision_user_control.py tests/v2/services/test_fact_normalization_command_service.py tests/v2/api/test_selective_vision_user_control_api.py -q --tb=short`。
- 扩大本轮相关消费者回归：`137 passed, 2 skipped`，包含当前任务观察 ID 排除同页历史观察、OCR 原文变动拒绝整理、供应商连接在同一进程改变时拒绝沿用旧客户端。命令：`.venv/bin/python -m pytest tests/v2/evidence/test_selective_vision_review.py tests/v2/api/test_selective_vision_user_control_api.py tests/v2/services/test_selective_vision_live_single_page_e2e.py tests/v2/services/test_fact_normalization_visual_observation_wiring.py tests/v2/services/test_fact_normalization_command_service.py tests/v2/services/test_selective_vision_postfreeze_orchestration.py tests/v2/services/test_selective_vision_user_control.py tests/v2/services/test_selective_vision_observation_service.py tests/v2/llm/test_independent_vlm.py -q --tb=short`。两项跳过分别是显式开关控制的真实单页视觉调用与 Coding Plan 连通性；未调用收费端点。只有第三方 SWIG 弃用警告。
- W6 发现合同与执行版本修订后集中回归 `41 passed, 1 failed`。命令：`.venv/bin/python -m pytest tests/v2/services/test_protocol_control_execution.py tests/v2/api/test_protocol_control_execution.py tests/v2/protocols/test_protocol_control_anti_overfit_chain_wide.py tests/v2/protocols/test_protocol_control_generalization.py -q --tb=short`。新增旧 v14 检查点拒绝在 v15 下重放、通用发现提示断言均通过。唯一失败是既有深审提示字符预算 `<30,000`，实际 53,906；本轮未修改深审提示，固定合同 17,259 字符、完整 Schema 34,921 字符，属真实待解决的效率问题。未删测、未改上限、未声称全绿；瘦身需保留结构接受和临床完整性，再用真实模型验证。
- 本轮真实运行：`frontend` 中 `npx vitest run src/pages/EligibilityWorkbenchPage.test.tsx --reporter=dot`，16项通过（包括官方满足而跨章要求未满足）；`npm run build` 通过，现有主包体警告仍在；`git diff --check` 通过。
- 旧作者记录 Q1/Q2 通过，没有本轮全量重跑。未运行产品真实模型、收费端点、方案深审、规则发布、5份24页病例事实/Profile/报告、一次真实更正/补证、第二结构留出、Ego Lite 1080P/2K/4K、备份恢复。`claims_complete=false`。
- 旧快照/报告与新结果 hash 对比：尚无新临床结果，不能给出对比或宣称任何结论变化。

## 下一步

1. 补齐 W6 真实冻结发现的来源抽样和耗时账本，按语义范围与标题分包分别诊断；在新版本身份下合法重建或修复活动 DAG，完成跨章深审。原则上优先消除真实无效批次，不牺牲跨章节漏检防线。
2. 用隔离产品服务验证当前任务回执到事实/Profile的逐页来源闭包，并核对模型别名、旧任务迁移和供应商切换；配置改变必须启新任务，不能让冻结中的旧规范化作业混入新观察。合格同模型同输入的已核实页可定向复用。
3. 只有官方和跨章要求同源完整后正式发布，继而以真实资料生成事实、事件、用药暴露、Profile、当前节点工作稿及报告。按“问题→原件→更正/补证→局部失效→新结果”跑完整闭环。
4. 最后做第二结构留出、报告/API/UI/打印计数对账、部署备份恢复和 Ego Lite 宽屏真实交互。临床与审阅验收仍需独立来源核查，不以本轮绿色测试代替。
