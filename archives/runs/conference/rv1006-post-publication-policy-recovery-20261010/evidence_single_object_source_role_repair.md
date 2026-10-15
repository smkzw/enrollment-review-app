Trellis SessionStart 上下文已加载。开始冻结代码只读审阅（基线 5749dd12；上限 14 次读取；不派工、不运行、不改文件；报告不复述临床原文）。先定位本轮新增/相关符号。

定位完成（SourceScopeCorrection 452-568、apply 759-800、decon 7066-7210/8283-8320/10387-10424、alignment 428-461/920-924、execution 2367-2445、测试 5106-5210/273-410）。并行读取前五区。

并行读取后四区（decon repeat_scheme_only 合并/提示与分流、heading recheck 派发、repeat count 测试族）。

Trellis SessionStart 上下文已加载。冻结代码只读审阅完成（14/14 次读取用尽；未运行测试/模型/服务、未改文件、未派工；报告不复述任何原文，仅述结构）。先结论，后清单。

## 一、结论概览

- 问题 1（标题主题重分类）：**现有合同可做到"有据、局部、有界、可失效重核"**——选择、证据、保留、无新绑定、不可照抄旧分类、单次调用与预算、历史恢复、旧证明失效均有代码与测试支撑；但"标题到底是主题还是真实访视阶段"仍由模型/复核者主张，宿主只能证明"来自完整标题、非正文、非显式时间片段、非已知节点名、scope 未变"，**不能证明其不是真实阶段**。
- 问题 2（仅补 repeat_scheme）：**范围没有扩大**——只允许补 `evaluation.repeat_scheme`（原缺 → 新有），其余求值字段/时间约束/原句/来源/强度/兄弟逐字段冻结；次数证明只证明"有源表示"，未知范围/结果采用保持 unresolved；消费者对未知保持 UNKNOWN，不默认。存在两条**未闭合的模型主张面**（许可强度、无比较词的纯事件次数），见建议。
- 未发现"已证必须修复"的硬缺陷；以下按 已证 / 建议（含危险反例）/ 未验 分列。

## 二、已证（代码+测试直接支持）

**A. 标题主题重分类（问题 1）**
1. 选择判据 `heading_scope_requires_recheck`（source_interpretation 466-477）：`affected_stage` 非空、`scope_quote is None`、该词**整词等于 heading_path 中某一项**、不出现于本条正文、不匹配显式时间片段、不是已知节点目标（display_name/来源摘录）——只"选出待核"，不决定含义（docstring 467）。
2. 合同字段与证据：`SourceScopeCorrection.heading_topic_quotes`（452-460）；`apply_source_scope_correction`（759-833）对主题声明的校核：逐字且去重、必须 ⊆ 所属标题（774-775）；**scope_quote/scope_context_unit_id 必须与旧值完全一致**（776-777，不制造访视来源绑定）；主题词不得是显式时间片段、不得来自正文、不得是已知节点（778-783）；提议的 stage/time 不得复用主题词（784-785）。
3. 保留保护：正文时间与真实阶段仍受"删除即拒"（794-795、796-801），仅"被声明为标题主题的词"从该保护中豁免（792-793、796）；期别剥离逻辑保持（803-823）；随后做**单陈述隔离重验**（824-832）。
4. 不回退旧分类：派发侧在 apply 后**重跑选择判据**，仍命中即拒（deconstructor 8309-8310，"不能照抄旧分类充当核对"）；提示只授权范围/阶段/时间字段（8301-8302）。
5. 有界与历史：单次调用由 `(index, precondition_sha256)` 去重 + `source_repairs < source_repair_limit` + 服务可调用性三重门（8297-8299）；成功/失败都写 attempts（含 precondition_sha256、guidance_version、called）（8304-8326）；恢复侧把 `source_heading_scope_recheck` 纳入历史校验（7703-7720）。测试：负例族 lost_title/invented_title/lost_body_time/real_period/known_visit/changed_scope/unresolved 全部拒，正例保留正文字段时间、scope 不变、标题仍在冻结来源、旧清单不被改（tests 5106-5161）；runner 测：1 次调用、历史保存、unchanged/exhausted 在恢复后 0 次再调用（5164-5201）。
6. 旧证明失效：对齐证明输入身份含 statement 全文（candidate_alignment 563-605），`reusable_proven_alignment_items` 逐项重验身份+响应摘要+重解析（694-735）；种子证明在无法从原答复现时返回 None、并要求组件身份除 compiler/validator 外全等（execution 2367-2442）。

**B. 仅补 repeat_scheme（问题 2）**
1. 来源声明判定 `source_declares_uncompared_action_count`（428-435）：action 且非 threshold、恰一个数字、逐字"N次"、无比较方向词。
2. 表示证明 `_source_repeat_count_is_preserved`（438-464）：无方向、无 predicate；对候选义务原子中现存 scheme 重验（v4 现行提取、来源 ⊆ 求值来源）、要求 `count_status=specified` 且 `maximum_repeats` 与源数字一致、scheme 来源 ⊆ 本单元且逐字含源句；**恰好一个** scheme 才算数。自述只证表示，不证许可/触发/资格/结果采用（440-443）。
3. 缺口变成定位修复而非伪造比较：缺 scheme 且无 predicate 时抛 `repeat_scheme_only` 定位错误（920-924）；分流只在单条 `repeat_scheme_missing` 且该 statement 命中来源声明判定时启用，且禁用 numeric-predicate reader（deconstructor 10383-10394）。
4. 字段级合并：`repeat_scheme_only` 分支要求时间约束不变、原 scheme 为空、新 scheme 现行提取、其余 evaluation 字段逐一不变；通用字段（kind/statement/modality/来源/后续义务等）冻结（7063-7144）。
5. 提示：只准补 repeat_scheme、声明不是阈值、v4、未知范围/结果采用写 unresolved、来源必须来自本原子冻结来源、不得借兄弟、返回完整 atom 由宿主只合并获准字段（7191-7198）。
6. 预算/去重/错误：`reviewed_atom_repairs` 按路径去重、`repairs=max(repairs,source_repairs)+1` 单次计费、失败即 attempts+回待核（不再整包）（10403-10436）。
7. 证明身份：候选含任何 scheme 时输入身份加入 `repeat_count_alignment` 版本（583-586）；改动 count 后复用失效（tests 354-356）。
8. 消费者保持：`evaluate_repeat_count` 未声明→TRUE(原因码)、未核/范围不符→UNKNOWN、超限→FALSE、资料不全→UNKNOWN（repeat_observation_count 18-44）；测试断言 `permission=="optional"`、`no_repeat_result_use=="unresolved"` 保持、0 次→TRUE、超限→FALSE、不全→UNKNOWN（tests 345-353）；字段修复测试：unknown_scope 合并后消费者 UNKNOWN、changed_policy/statement/time/missing/historical 全拒且基线逐字不变、wrong_count 合并后重核对拒（359-408）。

## 三、建议（含危险反例；均非已证缺陷，但属可达模型主张面）

- S1（许可强度）：`repeat_scheme_only` 合并不校验 `permission` 与 `SourceStatement.force` 的一致性。危险反例：源文为"可复查"（force 非 required），模型在补的 scheme 里填 `permission="required"`，宿主接受，下游按必做处理。最小建议：合并/表示证明中要求 `permission=="required"` 仅当 `statement.force=="required"`，否则只接受 optional/unresolved（用现有字段，不加词表）；负例=把"可"填成 required 应拒或保持 unknown。影响消费者：`calculate_control_repeat_triggers`（trigger/permission 逐条求值，35-109）、`repeat_review_presentation`（permission/unknown 呈现，97-104）。
- S2（纯事件次数误当复查）：来源声明判定只排除"有比较方向"，无方向的“发生N次”型短语在标签恰为 action 时可能进入复查分支。危险反例：事件发生计数（无至少/至多）被补成复查合同，下游把它当检查复查而非事件频次。最小建议：在判定上收紧为 `decision_functions == {"action"}`（或同时排除 time_validity/threshold/发生窗口语义），并补一条无方向事件次数负例；现有 `frequency` 变体带方向、不能覆盖该缺口（tests 325-335）。影响消费者：`evaluate_repeat_count`、`calculate_control_repeat_triggers`。
- S3（主题主张的宿主边界）：`heading_scope_requires_recheck` 与主题声明都允许"像真实阶段的标题"（非期别、非显式时间片段、非已知节点）被声明为主题并从 stage/time 删除；`real_period` 测试之所以拒，是因为它同时改了 scope。最小建议：补一条"疑似真实阶段标题、scope 不变、仅声明主题"的负例/边界测试，把"主张面"固化成文档与测试断言；不要加关键词例外。影响消费者：源疑问选择 `can_recheck_source_scope_question`（611-640）及后续对齐的访视/范围证明。
- S4（整包重验位置）：`apply_source_scope_correction` 内部只做**单陈述隔离**重验（824-832），派发侧 apply 后直接赋值（8308-8311）。建议确认其后存在整包 `validate_source_interpretation`（保存/恢复路径确有：execution 2399、2402 全量重验），否则将该单陈述验证升级为整包验证。未验，非已证缺陷。

## 四、未验 / 未读

- 服务端 `_revalidated_source_seed_proof` 全文（2433-2460 仅读头）；校正重放体（2600-2695 的 `apply_source_scope_correction` 调用与 scope_correction_indexes）仅 grep 级证据。
- 本条新增的 validator 组成串具体名称未读（2122 附近未读；validator_version 参与保存/复用与门版本再核的机制已证：2148-2153、2918、2991-2994、4427-4428）。
- `_source_repeat_count_is_preserved` 在 validate 数值段的正例调用点（940 之后）未读，行为由测试 305-356 钉住。
- 未做 diff（Bash 早前权限拒绝，未重试）；测试未运行。

## 五、覆盖与缺口一句话

现有完整核对能覆盖：标题来源资格与保留、无新访视绑定、重分类必须真实改变、单次/预算/历史/证明失效；以及复查次数的有源表示、字段级不可扩张、未知保持 UNKNOWN、证明随 scheme 失效。仍缺/待产品定界：许可强度与源力的对齐、无方向事件次数的排除、疑似真实阶段标题的边界主张、heading 应用后的整包重验位置。

本轮为只读审阅、未新建任务；按工作流需征询：本回合是否需要建立 Trellis 任务（若不建，本报告即终稿，后续仅在指定新窗口继续只读核对）？
