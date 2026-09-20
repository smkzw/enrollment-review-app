审阅完成，所有证据已收集。以下为完整报告。

---

# Conference Output: r01-binding-input-check-20260913 - evidence_single_object

## Output

### 0. 审阅基线（证据）

- 三个目标文件均为未跟踪新文件，只读审阅；未写任何文件、未调产品模型、未读私人配置、未派发子任务。
- 独立复跑 `tests/v2/services/test_predicate_binding_input.py`（禁用 cache）：**20 passed, 5 warnings, 5.88s**。
- 两个内存合同实验（仅构造模型，不落库）用于验证疑似缺陷，结果见 D1/D2。
- `grep` 确认无任何消费链引用 `predicate_binding*` 模块（仅定义文件自身命中），符合“不接消费链”边界。
- 对照读取：设计 `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md:300-312`（§17.1.1）、`app/domain/contracts/rules.py`、`app/domain/publication.py`、`app/storage/active_facts.py`、`app/storage/fact_authority.py`、`app/storage/evidence_locator_repositories.py`、`app/storage/repositories.py`、`app/projections/clause_pack.py`、`app/domain/contracts/facts.py`、`app/domain/contracts/evidence_locator.py`、`app/services/fact_normalization_command_service.py`、执行报告 `runs/execution/r01-binding-freeze-20260913/worker_01.md`。已浏览此前会议结论（语义层词表/对象身份/统一消费），本报告不重复那些论证。

### 1. 总体裁定（推断）

冻结输入实现实质满足 §17.1.1 第 1 步：权威、规则集修订、组件/谓词身份与逐字原文、已校正事实头、定位哈希全部经既有真实读取与校验链取得；服务路径未发现未发布内容混入、身份哈希缺失或校验绕过。但合同层存在一个已实证的时间约束一致性缺口（D1）和若干完整性/一致性观察，报告与文件存在滞后（D5）。

### 2. 缺陷与发现（按严重性）

**D1（中，合同层缺陷，已实证可复现）：组件校验不比较表达式与谓词条目之间的 `time_constraint`。**
`FrozenRuleComponent.validate_component` 只用 `{predicate_id: predicate}` 字典比对表达式与清单（`app/domain/contracts/predicate_binding.py:224-230`），时间约束不参与比较。实验：构造 `expression` 原子节点 `time_constraint=None`、而 `FrozenPredicateIdentity` 条目携带 28 天窗口（两级哈希按篡改内容一致重算），组件校验**通过**——冻结件内 `expression` 与 `trigger_predicates[0].time_constraint` 互相矛盾。服务路径两边取自同一 `AtomicExpression`（`app/services/predicate_binding_input.py:108-127`）故今天不会发散，但该合同是第 4/5 步版本化输出与统一消费将要持久化读取的边界，模块自述冻结“表达式时间约束”（`predicate_binding.py:6-8`）——节点时间保持目前只靠构建器纪律，不靠合同。修复建议：期望映射改为按 `predicate_id` 映射 `(predicate, time_constraint)`（沿原子表达式迭代），不一致即抛错；并补一条不一致反例测试。

**D2（低-中，已实证）：`source_status` 被校验器静默改写而非拒绝。**
`predicate_binding.py:135-141` 用 `object.__setattr__` 把撒谎值改写为派生值：传入 `source_status="verbatim"` 但无 `exact_source_clauses` 时构造成功、结果为 `unverified`。改写方向安全（无法凭空升级为 verbatim，实验确认），且该字段被排除在全部哈希材料外（`predicate_binding.py:147-148`），无哈希影响；但与全模块“拒绝冻结”的 fail-closed 风格矛盾，掩盖调用方错误。建议改为直接抛错，或将该字段改为只读派生属性、不接受输入。

**D3（低，来源完整性子集）：`FrozenLocatorIdentity` 只冻结定位工件的 15/约24 个字段。**
未进入冻结件：`bbox`、`coordinate_frame`、`sidecar_sha256`、`anchor_hash`、`disambiguation`、`locator_algorithm_version`、`coordinate_transform_version`、`effective_text_sha256`、`match_confidence`、`page_review_visual`（对照 `app/domain/contracts/evidence_locator.py:255-282` 与 `predicate_binding.py:360-377`）。缓解：定位行不可变追加写，`locator_id` 已冻结，下游可回库重读全量溯源；文本锚定三元组（`source_text_sha256`+范围+摘录）已保留，满足第 1 步候选需要。但冻结件中 `precision=BBOX` 的定位不携带坐标——冻结输入自身无法支撑 §17.4 式坐标级声明，下游不得把 precision 当作可在冻结件内验证的属性。建议在合同 docstring 明示，或若第 2/3 步需脱离仓储复核则补齐算法版本/锚点字段。

**D4（低，合同层信任假设）：`FrozenFactRecord` 不重推 `stable_identity`、不复查 UNKNOWN 极性禁带值，且无逐事实 authority 字段。**
源合同 `ClinicalFactV2.validate_fact` 会按内容重算 stable_identity 并强制极性-值规则（`app/domain/contracts/facts.py:404,423-434,216-217`），服务路径事实必经其校验，故安全；但手工构造的 `PredicateBindingFrozenInput` 可混入稳定身份与内容不符的事实、或跨 authority 事实（事实层无 authority，仅输入层有，`predicate_binding.py:427`）而不被合同拒绝。建议文档声明“仅经构建器构造”或在合同层加重推检查。

**D5（低，报告与文件滞后）：执行报告称 `15 passed`，当前文件实为 20 通过。**
`runs/execution/r01-binding-freeze-20260913/worker_01.md`（Commands 节）记录 15 passed；现文件含 supplied-facts 围栏与布尔算子等测试共 20 项。非代码缺陷，但报告描述的不是当前文件世代，Codex 需核对哪次修复后未更新报告。

**D6（观察，潜在风险）：`_expression_material` 按内容哈希排序逻辑子节点（`predicate_binding.py:69-78`）。**
当前安全：`LogicalOperator` 仅 ALL/ANY/NOT（`app/domain/contracts/enums.py:28-31`，可交换或一元）。若将来加入非交换算子（before/implies 类），乱序归一会把不同语义折叠为同一身份。建议加守护注释或断言算子集合保持可交换/一元。

**D7（观察）：`current_fact_heads` 对权威不符事实静默跳过（`app/storage/active_facts.py:29-30`）。**
传入事实由构建器前置逐条核对（`predicate_binding_input.py:265-270`）弥补；仓储读取路径下旧权威事实按当前权威作用域被排除，符合 §17.5 落实选择规则。副作用：冻结件无法区分“当前权威下尚无事实”与“事实仅存在于旧权威”——第 1 步范围内可接受，下游缺口统计不得将其读为完整性证明。

### 3. 正向核实（证据，对照 §17.1.1 第 1 步逐项）

- **权威/旧修订拒绝**：`authority_from_active_episode`（`fact_normalization_command_service.py:450-485`）成对活动指针派生并全量校验；服务再经 `validate_and_get_revision` 重验（`predicate_binding_input.py:195-212`；校验器 `fact_authority.py:80-200` 含快照作用域、指针对、陈旧修订、complete+ready 门禁），`revision.evidence_processing_revision_id` 字段真实存在（`evidence_locator.py:1033`）。
- **已发布规则集**：`get_rule_set` 按精确 `(id, revision)` 读取并验 payload 哈希与列镜像（`repositories.py:1476-1487`）；`RuleSetRecord` 仅经发布事务写入（`protocol_publication_service.py:930-958`，前置权威记录/完整性清单/门禁），“已发布”由写入路径保证。规则集身份三元组与权威核对（`predicate_binding_input.py:217-227`）。
- **谓词导出与原文**：按表达式位置确定性导出触发/例外；`predicate_id` 全 RuleSet 唯一由发布合同强制（`rules.py:360-363`），逐次出现不会产生重复清单；逐字原文非空必须属于父规则原文（`predicate_binding.py:251-257`），缺失显式 `unverified`。
- **事实与来源**：`current_fact_heads` 头选择先于校正排除、不复活旧值、同修订冲突 fail-closed（`active_facts.py:25-39`）；传入事实必须与已发布集合全等（`predicate_binding_input.py:283-288`，改值/隐藏均有测试）；`ClinicalFactV2` 自身强制 locator_ids 排序去重（`facts.py:404`），冻结层排序检查不会误拒真实事实。
- **定位核验**：`get_many` 缺失抛 NotFoundError、逐条 `_verify_source` 含摘录逐字切片校验（`evidence_locator_repositories.py:742-768,578-635`）；`validate_locators` 拒跨节点/跨快照/跨处理修订（`fact_authority.py:204-288`）。OCR 篡改在权威闭包处更早被拒（`AppStaleAuthorityError`，测试 ：612-629），同为 fail-closed。
- **哈希确定性**：`canonical_hash` sort_keys（`publication.py:10-18`），三层（谓词/组件/输入）均按唯一身份排序后再哈希，乱序同哈希测试独立复跑通过。
- **身份含组件上下文**：`predicate_identity_sha256` 含 role/rule_component_id/parent_rule_id/official_code（`predicate_binding.py:91-105`），符合第 4 步“条件身份须含组件上下文”。
- **无语义越权**：不带候选/已验证状态/结论；fact_type 仅随已发布要求原文进入；`official_code` pattern 与发布合同完全一致（`rules.py:312`）。

### 4. 对 Codex 的要点、建议与有界问题

- **建议修复（本会话可续问）**：D1 合同层补 `(predicate, time_constraint)` 一致性比较 + 反例测试；D2 改拒绝或改派生属性；D5 同步执行报告世代。
- **Q1（D1）**：确认修复落点——合同校验器（我的推荐，成本一处、覆盖手工/持久化构造）还是仅构建器纪律 + 文档声明？
- **Q2（D3）**：第 2/3 步是否需要在冻结件内携带 bbox/sidecar/算法版本，还是定位闭包按“locator_id + 回库重读”设计？
- **Q3（不确定性，我无法在边界内取证）**：真实已发布规则集中是否存在 `source_clause` 不属于父规则 `source_text` 的谓词（如跨章定义）？若存在，当前实现会整体拒绝冻该组件（fail-closed，`predicate_binding.py:251-257`）。设计第 1 步原文“跨章定义随对应要求提供”暗示应随件提供而非拒绝——需要 Codex 裁定这是待补的提供路径，还是当前发布链保证不存在该形态。临时安全路径：维持拒绝，不猜值不造摘录（现行为）。
- **未验证边界**：真实临床库与真实规则集形态未读（超出授权）；7 组件合成种子之外的真实形态（更深表达式树、REQ 组件、仅例外组件）未覆盖；本审阅非临床/监管验收，Codex 保留最终采信权。
