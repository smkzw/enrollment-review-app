All source files are current in this session (reader v4 = v3 semantics + relevance-gated ambiguity prompt; contracts unchanged with the three `Literal[False]` invariants; `written_judgment_evidence.py` unchanged since first read; `fact_expectation_gaps.py` and `evidence_expectations_v2.py` as reviewed this session). I have what I need for the design verdict.

# Conference Output: written-judgment-scope-20260910 - evidence_single_object

## Output

文本级设计复审（无视觉主张、未改代码、未实现）。核心裁决：**要求“外部世界级全量证明”才允许 professional_judgment 缺口确实过度约束了用户工作流——但现有 `source_scope_verified=False` 并没有犯这个错，它守卫的是另一个命题。修复不是放宽该布尔，而是把“报告命题”收窄为可证明的源绑定命题。** 恢复计划 ：82 已有用户授权原文："对应资料有效覆盖下两主读均未见必需的研究者书面判断，记录 professional_judgment 缺口并在后续条款结果说明‘无法判定’，不要求用户确认缺失，不阻断其他条款或报告”——授权的作用域本来就是“有效覆盖的对应资料”，不是外部宇宙。

### 一、两个命题的区分（设计地基）

- **P1（不可证，永不报告）**：“研究者从未在任何地方写过该判断”——需要外部全量证明，`source_scope_verified=False` 正确地永远守卫它，**保留不动**。
- **P2（可证，即用户所需）**：“本次提交的资料中，经完整双读检索未见与该项要求对应的研究者书面判断，因此暂无法判定符合与否”——只需要当前节点供给域的完备检索覆盖。措辞中“本次提交的资料中”是**强制限定语**：不声称判断从未发生、不声称操作未执行、不声称入排满足/不满足。

用户引文（“由于缺少研究者的判断，所以无法判定是符合还是不符合”）在报告语境下读作 P2；把 P1 的证明负担压上来才会得出“缺口永不可报告”的过度结论。

### 二、最小源绑定规则：条件与次序（全部复用现有机制，不新增认证框架）

- **C1 要求确需书面评估**：经 `prepare_judgment_search_target` 的选中路径一致性核对，已发布 requirement 的 `required_source_types` 显式含 `investigator_assessment`（模板语义全量相等检查已存在）；**不得**由 fact_type 或“数值检验默认需要判断”推断。
- **C2 当前到期且适用**：模板 due_stage ≤ 当前节点 stage、同流程节点成员、requirement 在 `due_requirement_ids`（prepare 已验证）；未到期 → not_due，不进入缺失评估。
- **C3 检索域=当前活动完整修订全部清单页**（现有构建器：无状态/日期/类别过滤），逐页字节绑定（reader v4 三重哈希核验已实现）。
- **C4 双读道完备**：每页两条已完成（finish=stop、整段合法 JSON）读道结果，对**同一**已发布 target/version（上轮指出的两项绑定检查：消费时 target 重算相等 + 跨读道 scope_sha256 与 target_sha256 全等——必须随本集成落地）；provider+model 不同（现有 coverage 规则）。任一缺页/缺道/失败/unreadable/相关 ambiguous 通道 → **不满足 P2**，该项维持 `observation_unverified`（未核实≠缺失，现有边界不动）。
- **C4' 无已知缺失的必需来源文件**：存在 `referenced_file_missing`（即 missing_source_file 语义）结构化信号时，该要求**不**评 P2——缺口保持“缺文件”，行动是补文件；文件里可能就含判断，不得重标为 professional_judgment 单独出现。
- **C5 零候选**：coverage 状态为 `ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE`——**该状态保持纯描述性**（描述“供给域内”），不需要也不添加任何调用方可设的“全局完备”布尔；三个 `Literal[False]` 不变量原样保留。
- **C6 found/混合候选阻断缺失**：任何 found/ambiguous 候选 → 进入候选/适用性复核路径（存在性待归属），绝不自动采信也绝不自动忽略。

**发射**（C1–C6 全过后）：向**现有**期望投影注入一条 `CoverageGapSignal(kind=PROFESSIONAL_JUDGMENT, fallback_only=False, applies_to_template_id=…)`，detail 为证据包引用（scope_sha256、target_sha256、双读道身份与 response_id、页数、逐页 not_found）+ 强制限定语措辞模板：“在[条款]的入排审核标准中，本次提交的资料中未见与研究者的书面判断相对应的记录，因此暂无法判定符合与否”。投影器现有判断分支（`evidence_expectations.py:261-285`）与 provenance 冻结机制（D1 修复）原样消费；D1 的五元组保留逻辑保证该信号在后续修订中精确重放或保守保留。

### 三、共存与不重复用户行动

期望合同一行一缺口（单 gap_type）天然防重复：`referenced_missing` 优先级高于 absent（现有次序），C4' 保证两者互斥不并存于同一要求；professional_judgment 行的行动=“研究者补充书面判断或指认已有判断位置”，缺文件行的行动=“补交文件”——各自单一行动集，无重复催办。fallback `observation_unverified` 仅对**不合资格**项保留，合资格项被具体信号取代（现有 precedence 处理），无双报。

### 四、反例挑战（逐条裁决）

1. **上传不全（未被引用的漏交报告）**：P2 照发——措辞只声明供给域内未见+无法判定，行动含“或提供含该判断的资料”；系统无法证明不完备，也不声称。✓ 不过界。
2. **作者不明（发现 CS 便签但无署名/日期）**：found/ambiguous 候选 → C6 阻断缺失 → 存在性成立、适用性未知 → observed_weak/未核实路径。绝不因作者不明改判缺失，也绝不采信。✓
3. **报告被抄入筛选病历**：抄印本含打印分析 → 候选 found → C6 阻断；仅转述数值无判断 → 供给域内 not_found 正确，且筛选转述来源强度规则不动（转述永不证明 investigator_assessment）。✓
4. **后续节点的相关记录**：C2/C3 限定当前节点快照；P2 措辞节点限定。后续新证据 → 新期望 revision 追加，旧 P2 行原样保留（追加写不变量）。✓ 符合“后期证据不改写早前结论”。
5. **泛化“初步符合入排”表述**：候选（found/ambiguous）→ C6 阻断 → 人工/语义适用性复核决定它是否针对**本条**判断；既不自动采信也不自动忽略。页7 探针即此例（一读 ambiguous 保留、另一读 not_found，分歧被保留）。✓
6. **显式缺必需报告**：C4' → 保持 referenced_file_missing，不发 P2，单一补文件行动。✓
7. **全部可读且无书面判断**：P2 按用户原文措辞发射，工作流继续，**不**停下向用户确认。✓ 正是用户要求。

### 五、最小集成（不实施）

仅三块胶水：① 两个绑定检查（target 重算、跨道相等）；② “缺失评估器”纯函数（消费持久化回执+coverage 摘要，判 C1–C6，发射单条信号）；③ 回执的追加式持久化（仍缺的外层编排）。不改 judgment_search 合同、不改三个 Literal[False]、不加全局完备布尔、不动投影器与 D1 机制。

### 六、测试矩阵（最小集，合成）

T1 干净缺失（全页双读 not_found、无缺文件信号）→ ABSENT/PROFESSIONAL_JUDGMENT + 限定语措辞 + 工作流继续；T2 单页单道 unreadable → 维持 observation_unverified；T3 单道 found → 阻断走候选；T4 相关 ambiguous → 阻断（coverage_incomplete）；T5 存在 referenced_missing → 保留缺文件、无 P2、单一行动；T6 目标漂移（道间或对重算）→ 有界报错不出缺失；T7 后续节点新证据 → 新 revision 追加、旧行不变；T8 泛化表述页 → 候选阻断；T9 无 investigator_assessment 要求 → 评估器拒绝（C1）；T10 某道缺页结果 → 阻断。恢复计划 ：82 已列的验收反例（失败/漏页不得冒称已核实；补充判断后新修订复核旧结果保留）分别由 T2/T7 覆盖。

### 七、未决选择（需所有者裁决，不阻塞设计定稿）

① 分组目标调用下“相关通道”的粒度：单目标设计页级通道皆相关；分组设计需按 target_ref 逐目标判定 unreadable 是否阻断**该要求**（无关目标的不可读不应阻断）——建议随分组集成一并定。② 缺失评估器的执行时点：finalize 前置（需检索编排先完成）或独立投影修订。③ ActionRequest 措辞模板与责任方文案的最终定稿（结构已有，属产品文案）。④ 分组调用预算参数（沿上轮：实测失败率定，不设魔数）。

### 边界

同厂商同家族复审独立性受限；本报告为证据绑定的工程设计评审，非正式项目签收、非临床验收；未实现任何代码、未声称新用户授权（恢复计划 ：82 的既有授权被引用而非扩大）、不要求用户确认已文档化的缺失判断。
