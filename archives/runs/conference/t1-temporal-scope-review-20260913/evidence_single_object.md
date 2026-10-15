All verifications are complete. I have the full evidence base — now writing the final conference report.

**Review verdict summary:** The patch direction (temporal filter before value/polarity aggregation) is mandated by design doc §17.1 and correctly eliminates order-dependent results; 183 tests across the four frozen suites pass. But I found one HIGH semantic issue (all-outside→FALSE creates definitive barrier decisions with no action item, and the expectation layer simultaneously marks the requirement OBSERVED), one MEDIUM gap-category shift (time ambiguity now masks source conflicts), one MEDIUM display regression (observed_value dropped), one pinned-but-inconsistent UNKNOWN-domination rule, and concrete test gaps including an untested FALSE branch.

# Conference Output: t1-temporal-scope-review-20260913 - evidence_single_object

## Output

### 0. 审阅范围与证据基线

- 审阅对象：工作区唯一相关代码改动 `app/domain/expression.py`（`git diff HEAD`：+24/−7，全部位于 `_evaluate_atomic`），以及新增测试 `tests/v2/test_expression_temporal_candidate_scope.py`（未跟踪，7 个用例）。工作区内其余大量修改文件（agents/transports/config/tests）不在本冻结范围内，未审阅。
- 已读：`app/domain/expression.py` 全文（612 行）、`app/domain/contracts/rules.py`（TimeConstraint/AtomicPredicate/AtomicExpression）、`app/domain/contracts/evidence.py`（ClinicalFact）、四个指定测试文件、`plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md` T1、`docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` §17（重点 17.1/17.2）；因严重度判定需要，加读了直接决策/缺口消费者 `app/domain/gates/assessment.py`、`app/domain/policies.py`、`app/projections/evidence_expectations.py`（均在冻结范围允许的"必要时检视相邻决策/缺口消费者"内）。
- 已运行（只读、`PYTHONDONTWRITEBYTECODE=1`、cache 禁用）：四个指定测试文件全部通过，共 **183** 个用例（新套件 7 + test_contract_logic 110 + calendar_units 33 + lookback 33）。Owner 报告的 "201 tests" 应含冻结清单之外的文件，本审阅只对上述 183 个负责。另用孤立 Python 复现脚本（R1–R9）和 HEAD 版本对照（importlib 加载 `git show HEAD:app/domain/expression.py`）验证了全部机制性断言。
- 本报告不改代码、不改临床资料、不声称最终验收。

**总体结论**：修复方向正确且被 §17.1 明文要求（"先按本谓词的对象、节点截止、时间角色/窗口/量词筛选，再判断同一观察是否冲突"）。修复消除了列表顺序依赖（旧代码 `matching[0]` 取决于 context.facts 顺序——这正是 owner 观察到的初始 5 fail/2 pass 中 test2 反序通过的原因，我已用 HEAD 复现核对），并把窗外事实从值/极性冲突检查中正确隔离。但存在一个必须由 Codex 明确裁决的高影响语义分叉（F1）、两个中等问题（F2/F3）和若干必补测试（F5）。**183 个测试通过不构成临床语义正确的证明**；其中最关键的新分支（全部窗外→FALSE，多事实情形）恰恰没有任何测试覆盖。

---

### 1. 严重度排序的发现

#### F1（HIGH）：全部窗外 ⇒ FALSE 依赖未声明的"窗口证据完备"假设，与系统自身的开放世界立场矛盾，并在下游产生"无行动项的确定性障碍结论"；且真值随"是否恰好存在一条窗外记录"而翻转

**证据（观察，均已复现）：**

1. `app/domain/expression.py:514-521`：`relevant` 为空（所有匹配事实的时间求值均为 FALSE）时谓词直接返回 FALSE。复现 R7/R8：同一 EXISTS 谓词 + 同一时间窗——事实集合为空 → `UNKNOWN ['fact_not_observed']`；存在一条明确窗外事实 → `FALSE ['above_time_window']`。两者在"窗口内无任何观察"这一点上证据状态完全相同（开放世界：窗口内未记录 ≠ 窗口内未发生），真值却不同。
2. 下游（复现"场景 A"）：trigger FALSE → `derive_component_decision`（`app/domain/gates/assessment.py:310-315`）→ `INCLUSION_NOT_MET`；该判定属 `BARRIER_DECISIONS`（`app/domain/policies.py:42-46`）→ `BlockingLevel.BLOCKING`。同时 `derive_gate_gap_types` 只在 trigger 为 UNKNOWN 时把 reason codes 映射为缺口（`assessment.py:259-263`），`above_time_window/below_time_window` 不在 `REASON_GAPS`（`assessment.py:195-205`）中，因此缺口集合为空 → **无任何 ActionDirective**（行动指令由缺口驱动）。产品状态：受试者被确定性筛除、阻断、且没有"补窗口内检查"的行动项。
3. 跨层矛盾（证据，代码检视）：期望投影 `_matching_observations`（`app/projections/evidence_expectations.py:170-181`）仅按 `supported_requirement_ids` 匹配、**完全不检查事实日期与要求窗口**——同一条窗外事实会把资料要求标为 OBSERVED（无缺口）。于是同一事实在谓词层导致"确定性不满足"、在期望层却"满足要求"，两层互相矛盾且用户可见。
4. 反向路径（复现"场景 B"）：若期望层对某条到期要求给出 ABSENT+`RECORD_INCOMPLETE`，则 trigger FALSE 的确定性判定携带阻断缺口，`validate_decision_gap_matrix`（`app/domain/policies.py:205-206`）抛出"明确判断不能携带阻断缺口"，候选 Gate 硬失败。方向安全（fail-closed），但意味着"全部窗外 + 兄弟要求未满足"的组合会让整条候选链被拒，运营上阻断。

**对 FALSE 的钢人论证（必须记录，避免误判为纯缺陷）：** 单条明确窗外事件 ⇒ FALSE 是**已文档化的既有合同**（`tests/v2/protocols/test_node_relative_lookback_contract.py:216-218`：baseline 锚点下事件明确窗外 → FALSE + `above_time_window`；`tests/v2/test_contract_logic.py:1750-1789`：单事实边界 27→FALSE/28→TRUE）。对病史型排除回看（"随机化前 28 天内无禁用暴露"、"5 年内无恶性肿瘤"），FALSE 语义在临床上既是正确也是必要的——否则每个有陈旧病史的受试者都会涌入人工复核，直接违反 T1 退出条件"合法例外和已核实判断没有被全部拒绝"。本补丁把多事实情形统一到该既有语义，本身是对旧代码不一致行为（同值全窗外→FALSE、异值全窗外→source_conflict UNKNOWN）的收敛。

**真正未被支撑的部分（推断，需 Codex 裁决）：** 对"窗口内评估型"谓词（筛选期 HbA1c≤8.5%、窗口内体重>50kg），"仅存在窗外观察 ⇒ FALSE"隐含"窗口证据完备"假设；而评估器没有任何输入支撑该假设，且系统在 `fact_not_observed→UNKNOWN` 和 §17.2"本次资料未见所需记录"（前置条件：所有可能相关供给资料有效双读；产出：professional_judgment + 研究者补充，而非确定性阴性）中已明确采用开放世界立场。临床上正确的输出应是"待补窗口内评估"（UNKNOWN/带行动项），而非确定性 INCLUSION_NOT_MET。

**最小原则性修复（建议，不实施）：**
- 方案 a（改动小，触动决策矩阵）：谓词真值维持 FALSE（保持 183 个测试与既有合同），但在决策层为"trigger FALSE 且 reason 仅含时间窗排除码"增加非终态处置——映射为非阻断 attention 缺口或专用决策（如"待窗口内复核"），并附行动指令"提供窗口内评估/复查"。需同步放宽 `validate_decision_gap_matrix` 对该组合的禁止。
- 方案 b（临床语义最干净，合同面扩大）：为 AtomicPredicate 增加显式 `absence_semantics: event|assessment`（由 deconstructor 从条款语义填充），event 维持 FALSE，assessment 返回 UNKNOWN + 新 reason `fact_not_observed_in_window`（加入 REASON_GAPS）。改动面大，需构造器配合，超出本补丁范围。
- 无论选哪条：期望投影层与谓词层必须共享同一时间窗判定（`_matching_observations` 至少应感知 `source_validity_window`/锚点窗），否则场景 A 的跨层矛盾继续存在。

#### F2（MEDIUM）：时间未决分支掩盖值冲突与极性问题，缺口类别发生静默迁移（SOURCE_CONFLICT → DATE_OR_ANCHOR_MISSING）

**证据（已复现）：** 输入"窗口内事实值 9 + 无日期异值事实 3"——HEAD（补丁前）返回 `UNKNOWN ['source_conflict']`（复现输出）；补丁后返回 `UNKNOWN ['date_or_anchor_missing']`（R3）。真值不变，但 `app/domain/expression.py:523-530` 的未决时间分支先于冲突检查（`:540-552`）与极性检查（`:531-539`）执行，且只返回时间类 reason。

**影响：** `_decision_for_unknown`（`assessment.py:285-292`）把 SOURCE_CONFLICT 缺口映射为 `ComponentDecision.CONFLICT`，无冲突缺口则映射为 `INDETERMINATE`；行动指令也随之不同（冲突解决 vs 日期补充）。同一数据问题现在把审阅者引向"补日期"而非"解决冲突"——而一旦日期补齐，它本来就会变成冲突。这违反项目边界"Separate rule judgment from gap reason. Do not collapse … conflict … into one status"的字面要求之一角：不是状态坍缩，但**缺口归因**被单一化了。

**建议（不实施）：** 未决时间分支的 reason 集合在"相关事实间同时存在值/极性差异"时并集加入 `source_conflict`（或在 `derive_gate_gap_types` 之外由事实层 conflict_group 兜底——注意 `assessment.py:253-255` 已按 ConflictGroup 记录补冲突缺口，前提是事实入库时建了 conflict group；未建组的散在异值无此兜底）。

#### F3（MEDIUM）：全部窗外 FALSE 分支丢弃 observed_value/observed_unit（相对 HEAD 的显示/溯源回退）

**证据（已复现）：** HEAD 对单条窗外事实返回 `FALSE ['above_time_window'], observed=3 mmol/L, spans=['s1']`；补丁后同一输入 `observed_value=None, observed_unit=None`（`expression.py:516-521` 未填充这两个字段；evidence_span_ids 保留）。多事实全窗外同样为 None（R1）。

**影响：** 候选/前端无法再展示"窗外被排除的观察值是多少"，只能给 fact/span id。对"为何不满足"的人工核验是信息损失。修复简单（从被排除事实集中按排序取代表填充），但"FALSE 结果上展示 observed_value"的语义需 Codex 拍板（避免被误读为"窗口内失败的值"）。

#### F4（MEDIUM，属已被 owner 测试钉住的设计决策，提请复议而非缺陷）：原子层"时间未决支配一切"与评估器自身逻辑层"决定性兄弟压倒 UNKNOWN"的原则不一致

**证据（均已复现）：** 逻辑层 `_evaluate_logical`（`expression.py:116-129`）：`ALL[FALSE,UNKNOWN]→FALSE`、`ANY[TRUE,UNKNOWN]→TRUE`——决定性分支不被 UNKNOWN 兄弟污染。而原子层新分支：窗口内事实值 3（比较 TRUE、时间 TRUE）+ **同值**无日期重复记录 → 谓词 UNKNOWN（R4；即新套件 `:47-52` 钉住的行为）。同值（value、canonical unit、polarity 全同）的未决时间事实**在数学上不可能改变比较结果**（比较只依赖值三元组，与 R4 中两条事实的比较结果相同），却被允许冻结结论——直到事实更正流程移除无日期重复。

**钢人论证：** "唯一可判定事实"学说（别名注释 `expression.py:497`："别名集合仍要求唯一可判定事实"）可以辩护该冻结：两条记录本应是一条，评估器拒绝在记录集合不干净时下结论。但评估器自己的唯一性判据是值相等（同值即"同一观察"、不报冲突，`:540-544`）——按此判据 R4 就是一条带日期的观察，冻结缺乏一致根据。真正的约束在 `validate_decision_gap_matrix`：明确判断不能携带阻断缺口（DATE_OR_ANCHOR_MISSING 属阻断），因此"真值定论 + 日期缺口信号"在现矩阵下不可能共存，冻结是被矩阵合同强制的。**若要松绑，需先改决策矩阵/引入非阻断日期提醒缺口，属决策合同变更，提请 Codex 决策点而非本补丁缺陷。**保守方向安全（不产生错误放行），代价是人工复核量与事实更正负担。

#### F5（LOW-MEDIUM）：必补测试缺口（当前全部窗外→FALSE 分支零覆盖）

以下情形无任何测试（按优先序）：
1. 多事实全部窗外（同值与异值两版）→ FALSE + 时间 reason + used_fact_ids/evidence_span_ids 保留（R1/R2 已手工复现，无断言钉住）——这是本补丁**新引入语义且无旧测试等价覆盖**的唯一分支（单事实边界测试不覆盖多事实路径）。
2. F3 的 observed_value 回退（若裁决为需保留，则补断言）。
3. NEGATED 窗外事实先于冲突/极性检查被过滤（R5 已复现：NEGATED 窗外 + AFFIRMED 窗内 → TRUE，used 仅窗内）——极性翻转×时间过滤的交叉仅被 polarity=UNKNOWN 版本间接覆盖。
4. 例外表达式（exception_expression）走同一时间过滤路径的语义（T1 退出条件"合法例外没有被全部拒绝"目前无时间维度的例外用例）。
5. Gate 级：trigger FALSE + 纯时间 reason → 缺口空 → `INCLUSION_NOT_MET` 阻断且无行动项（场景 A）；trigger FALSE + 兄弟期望 ABSENT 缺口 → 矩阵抛错（场景 B）。两者都是本次语义的直接下游，无断言。
6. 全窗外分支的乱序不变性（used_fact_ids 排序）。

#### F6（LOW，记录不阻塞）

- `expression.py:512` 按 fact_id 字典序排序决定 observed_unit 在规范化等价拼写间的取值（R9：`z-first` 的 "mmol/l" 胜出仅因 id 序）——确定性但任意，可接受。
- 排序后 `_compare` 只跑一次（对 matching[0]），因值三元组唯一而安全；单位不匹配检查同理不受影响。
- 提示词声明的"broad fact-type alias 缺陷"确认不在本 diff 内（`predicate_fact_type_aliases` 逻辑未改动），未与本题混同。

---

### 2. 挑战清单逐项裁决（提示词指定项）

| 挑战项 | 裁决 | 依据 |
|---|---|---|
| 标量比较 FALSE × 歧义日期 | 保守正确：歧义兄弟存在时永不产生比较性 FALSE（R3）；窗口内失败值被歧义遮蔽为 UNKNOWN，方向安全 | `expression.py:523-530`；R3 |
| 否定观察（NEGATED） | 正确且为改进：窗外 NEGATED 被过滤（R5→TRUE 仅凭窗内）；窗内 NEGATED 翻转比较（R6）；混合极性同窗仍报冲突（元组含 polarity） | R5/R6；`:540-544` |
| EXISTS | FALSE/UNKNOWN 不对称成立（R7 vs R8）→ F1 的核心；EXISTS × 窗内值存在 → TRUE 正常 | R7/R8 |
| 空可用证据 vs 已知窗外事件 | 同上不对称；另加期望层"OBSERVED 无视日期"的跨层矛盾（场景 A/B） | §1 F1 |
| 全窗外且值不同 | FALSE，值分歧不可见——与"时间范围先于聚合"自洽，可接受；未决冲突经 conflict_group 兜底（若入库建组） | R1；`assessment.py:253-255` |
| 跨日期等值（窗内） | 定论成立、双 fact/span 保留、排序确定——修复目标本身，正确 | 新套件 `:36-44` |
| 部分日期/部分窗口 | 既有区间算法保留：整个可能区间一致才定论，跨界 UNKNOWN——未被本补丁破坏（33 用例通过） | `test_time_constraint_calendar_units.py` |
| 三值逻辑 | 原子层与逻辑层在"UNKNOWN 是否可被决定性结果压倒"上不一致 → F4 | R4 + 逻辑层复现 |

### 3. 验收限制（本审阅不能证明的）

- 未运行冻结四文件之外的测试（owner 的 201 之差 18 个用例属未审文件）；未起应用/数据库实例；未做 UI/原件链路验证。
- 场景 A/B 用 `model_construct` 夹具直调 gates/policies 函数复现，路径忠实于现行代码，但未穿过完整 live 投影服务（`eligibility_review_projection.py` 的实际装配未逐行核对）。
- HEAD 对照经 importlib 加载 shim 完成，输出与 diff 推演一致，可信；但未运行 HEAD 全套测试回放。
- F1 的临床影响定级（HIGH）基于评估型谓词在真实方案中的普遍性推断，未对具体项目条款抽样统计——标注为推断。

### 4. 给 Codex 的决策点与有界问题

- **Q1（阻塞 F1 处置）：** 全窗外⇒FALSE 对"窗口内评估型"谓词是否被接受为既定语义？若否，选方案 a（决策层时间排除码→非终态处置+行动项）还是方案 b（谓词级 `absence_semantics`）？安全临时路径：维持现行为，先落 F5.1/F5.5 测试把当前语义与下游后果钉住，并在恢复计划记录该未决分叉。
- **Q2（F2）：** 未决时间分支是否应并列输出 `source_conflict`（当相关事实同时存在值/极性分歧）？还是接受单一时间归因、依赖 conflict_group 兜底？
- **Q3（F4）：** 同值无日期重复冻结结论——维持保守（接受复核负担）还是排期"决策矩阵支持非阻断日期提醒"后的松绑？
- **Q4（F3）：** FALSE 结果是否恢复 observed_value/unit 填充（需同时定义其展示语义）？

**安全临时路径（若 Codex 暂不答复）**：补丁可按"方向正确、带未决语义分叉"留在当前状态——它没有引入任何错误放行（wrong-TRUE）路径，全部新增风险集中在"过度确定的阴性"；F5.1 的回归测试应在任何后续改动前先行落地，以防该无覆盖分支被后续重构静默改变。
