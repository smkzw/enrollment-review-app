所有证据已收集完毕。我已验证了版本常量、四个精确标识网关、对账接受前提条件、源对齐要求、存储库的追加写入保证以及针对性审查网关。我现在可以提交完整的会议报告了。

# 会议参与者输出：r3-source-reprojection-review-20260906 - general_single_object

## 边界检查

- 仅在 runner 绑定的 cwd（phase5-clinical-facts-profile worktree）内工作。未读取数据库、凭据、临床 blob、其他 worktree 工作目录，未读其他与会者输出；未编辑任何文件、未调用产品模型、未创建子进程。
- 初始读集 8 个文件全部读完；为核实边界又窄范围读取了相邻代码/测试（均属"narrowly necessary"）：`app/domain/page_reconciliation.py`、`app/domain/page_source_association.py`、`app/services/page_association_sources.py`、`app/services/targeted_page_review_executor.py`（仅版本守卫段）、`app/services/fact_normalization_command_service.py`（仅 coverage 消费段，约 85 行）、`tests/v2/domain/test_page_review_legacy_read.py`、`tests/v2/domain/test_page_source_association.py`（用例清单）。
- 事实核查结果：**"current main v11 / page v6 / reconciliation r3-v10" 已在代码中逐字证实**（见证据节）。**"stored receipts = main v10 / contract v4 / reconciliation r3-v9" 在我的边界内不可证实**：读 set 文件在本 worktree 全部是未跟踪文件（`git status --porcelain` 显示 `??`，无 git 历史），版本留痕只能来自产品 DB 或任务记录，两者均在禁区。阻断面：需要 Codex 从任务记录或 DB 元数据（仅 distinct 版本值计数，不取临床载荷）确认。恢复点：Codex 同会话答复即可闭合。
- 不声明任何临床/正式验收；仅返回审阅结论。

## 独立工作成果

### 1. 正式链的"四道精确身份闸门"地图（重投影必须全部穿越才可能成为正式输入）

1. **记录级合同闸门**：`reconcile_page_reviews` 第一行即拒绝任何 `contract_version != page-review/v6` 的记录（`app/domain/page_reconciliation.py:49-50`，错误文案"历史页记录版本仅供回看，请按当前版本重新判读后对账"）。旧 v4 记录连参与重算的资格都没有。
2. **覆盖执行版本闸门**：`select_normalizer_coverage` 要求 `coverage.execution_versions == page_review_execution_versions()`，即 job v7 + main v11 + handwriting v7 + reconciliation r3-v10 + contract v6 五元组精确相等（`app/services/page_review_coverage_selection.py:40`、`app/services/page_review_job_service.py:31-36`）。
3. **逐记录身份闸门**：每条入选对账引用的每条读记录，`contract_version` 必须是 v6 且 `prompt_version` 精确等于 v11（main）或 v7（handwriting），否则 409"现有判读采用旧处理方式，请重新判读当前资料；历史记录仍保留"（`page_review_coverage_selection.py:74-77`）。
4. **对账重算闸门**：服务端用当前记录+当前算法+关联来源现场重算对账，`reconciliation_id` 必须与存量一致（`page_review_coverage_selection.py:78-84`）。对账身份纳入全部结果字段+算法版本+`association_text_sha256`（`page_reconciliation.py:184-209`）。

另有两道外围闸门：局部重读规划器要求前任务载荷（去 recovery、含 execution_control 兼容）与当前载荷逐字段相等——旧时代载荷没有 `association_sources`，必然失配 → 只能整任务重读（`page_review_recovery.py:26-31`）；针对性复核执行器要求 `base_prompt_version == 当前 v11`（`targeted_page_review_executor.py:31`），辅助读也绑定新身份且按设计永不进入正式事实/覆盖。

**结论 A（对核心问题的直接回答）**：拟议的"显式重投影实体"路线**作为正式 normalizer 输入当前是不充分的，且不可能在不同时改四道闸门的前提下充分**。每道闸门的错误文案本身已宣布官方路径是"重新判读、历史保留"。这与设计文档 §7（"旧记录按旧版本解码，新结果使用新版本；禁止原地重算历史键"）、§8.1.5（"缺少定位依据时沿用未解决状态，禁止将新算法套到旧结果冒称已验收"）、§10（"新路径必须显式 R3 身份"）的既定裁决一致。**我的裁定建议：重投影保持诊断/回放定位；正式准入不在本轮立项**——产品政策（AGENTS.md：旧项目是只读反例/回归锚点，新架构一律新建项目）意味着"正式准入"没有真实用例，属 YAGNI。

### 2. 但重投影有真实的诊断价值（当前实现已部分为之铺路）

r3-v10 相对存量 r3-v9 的实质差异是 §8.1 来源关联采信。关键机制：context 为 None 的事实经键路径**永不采信**（`page_reconciliation.py:83-87` 的 `unassociated_fact_keys`），且被 `source_aligned_fact_keys` 显式跳过；后者要求 context 非空、`polarity != "not_stated"`、摘录在冻结侧车文本中**唯一命中**、对齐范围+字段名+context 键+值/单位+箭头标记全部一致（`page_source_association.py:52-68`）。v4 时代记录**可能**携带 context（v3+ 的解码器都接受 context 参与键计算，`page_review.py:100-108`）——若存量真实记录确有非空 context，那么"重投影键 + r3-v10 重对账 + 同一冻结文本的关联来源"可以让旧观察**首次**通过 §8.1 范围对齐产生采信候选。这是重投影路线唯一有分量的正当动机，也是"比较显式重投影 vs 重跑当前读链"对照实验值得做的理由。关联来源本身对旧处理修订同样可派生（`page_association_sources.py` 从不可变修订的 OCR 页+更正投影有效文本），但 `ocr_page_id is None` 的页没有 rescue 路径。

### 3. 最小诚实实现（诊断定位）

- 新只读投影实体 `page-review-normalization-projection/v1`，字段：`parent_page_review_id` + **`parent_payload_sha256`**（比单引 response_sha256 更强，锚定整条解码记录）、`source_contract_version`、`source_prompt_version`、`projection_algorithm_id`、重算后的 facts/handwriting 规范三元组、`association_text_sha256`（若做了重对账）。父记录零改动。
- **必须新造一个显式规范化算法版本常量**：当前"现行算法"是隐式的（`fact_normalization_key` 无 flag 即现行），算法身份寄生在合同版本上（v6 解码路径=现行算法）。投影实体不得借用合同版本充当算法标签。
- 投影是纯函数：只重算 `normalization_key/normalized_value/normalized_unit(/normalized_text)`；不新增/删除/改写观察；`context is None` 保持 None，**绝不合成 context**；raw_text/raw_value/region 逐位不动。
- 消费出口仅限：覆盖率/影响面分析（多少键变化、多少页在对账分类上翻转）、与重读结果的回归对照、金标工作。不进 `select_normalizer_coverage`，不进发布事实，不计入 §13 双源采信召回。

### 4. 兼容"纯算法升级"与"真提示/读内容变更"的判据

**判据：变更能否表达为"已存字段的全体确定性全函数"** —— `f(field_name, raw_value, context) → (key, value, unit)`，不引入任何页面上未存的新信息。
- **兼容（可重投影）**：v4→v5（箭头在单位前剥离）、v5→v6（/μl）正是此形态，现有 v4/v5 字节稳定测试已固化其逆解码器（`tests/v2/domain/test_page_review_legacy_read.py:71-131`）。
- **不兼容（必须重读）**：v10→v11 提示改变的是"读什么、抄多细"（context 完整性、location_text 规则、单位抄录义务、handwriting=[] 规则、has_eligibility_value 语义）。确定性函数造不出模型没抄的字段。投影后旧读相对新读**系统性欠采信**——这个不对称必须作为报告输出，不得隐藏。

### 5. 响应原文哈希可复验性（重投影资格的第一道机器可查前提，含具体反例）

`response_sha256 = canonical_hash(raw)`（排序键紧凑 JSON，`app/domain/publication.py:10-18`），且 `ContractModel extra="forbid"` 保证持久化载荷=模型原始四键载荷+注入的派生字段（`page_review_harness.py:574-620`）。因此**可从存量记录确定性重建 raw 并复验 SHA**，但重建规则有陷阱，必须按精确逆变换：
- 每条 fact 剥离 `normalization_key/normalized_value/normalized_unit`；handwriting 剥离 `normalization_key/normalized_text`；
- **context 必须剥离等于默认值/None 的键**：harness 在算哈希**之前**用 `ObservationContext.model_validate(...).model_dump()` 规范化了 context（`page_review_harness.py:586-590`）——模型原始 JSON 若省略 `time_text`/`location_text`/`polarity`，存记录里却是"键存在、值为 None/默认"。逆变换不剥这些键，SHA 必然失配。
- 该性质必须先用**真实存量记录**做 property test 验证后才许任何投影信任它；个别记录复验失败 → 该记录投影不合格（登记诊断，禁止猜测修补）。

### 6. 必测反例清单（在既有测试之外新增）

1. response_sha256 逆重建 property test：覆盖"模型省略可选 context 键""polarity 缺省""箭头+μl 单位""重复摘录"形状；失败记录必须可判不合格而非误报。
2. 投影全函数性/幂等性：投影(投影结果)==投影结果；注入伪造观察/合成 context/改 raw_value 的变体被构造性拒绝。
3. 历史不可变性：投影批处理前后，父行 `payload_sha256` 与 `get_review` 解码逐字节不变（仓库 `_same_or_conflict`+column mirrors 已提供机制，`page_review_repository.py:46-51,113-135`）。
4. 投影记录重对账：身份确定性（同输入同 id）、与历史对账 id 必然不同、**handwriting 触发翻转**反例——handwriting 键参与 `handwriting_reader_triggered`（`page_reconciliation.py:168-176`），键重算可把"两主读一致无手写"翻成触发 C 缺席，覆盖处置随之变化；此分类翻转须进对照报告。
5. 资格守卫：父记录旧合同解码失败（键被篡改）→ 投影拒绝；`ocr_page_id is None` 页无关联来源 → 关联采信缺席、状态保持未解决；context=None 或 polarity=not_stated 的事实经两条路径都不得采信（机制已存在，测试钉死投影不得绕过）。

### 6bis. 对照实验设计（回答"比较重投影 vs 重跑当前读链"）

冻结小样（同一批页图像+条款包+冻结修订），双臂：(a) 重投影+r3-v10 重对账；(b) v11 全量重读新任务。输出对照维度：accepted_fact_keys 差集、冲突→采信与采信→冲突翻转清单、C 缺席触发翻转、context 缺失导致的结构性欠采信率、耗时/成本/失败率（429/内容过滤）。它是报告，不是断言——v10/v11 提示差异只能行为学度量（见风险节）。

## 证据与假设

**已证实（代码，file:line）**
- 现行身份：`PAGE_REVIEW_PROMPT_VERSION="page-review-r3/v11"`、`HANDWRITING_PROMPT_VERSION="handwriting-review-r3/v7"`、`TARGETED_REVIEW_PROMPT_VERSION="page-targeted-review/v2"`（`app/llm/page_review_harness.py:52-54`）；`PAGE_REVIEW_CONTRACT_VERSION="page-review/v6"`（`app/domain/contracts/page_review.py:15`）；`RECONCILIATION_VERSION="page-reconciliation/r3-v10"`（`app/domain/page_reconciliation.py:23`）；job 合同 v7（`page_review_job_service.py:28`）。
- 历史字节稳定机制与既有钉死测试：见上节 5、6 引用。
- 接受前提、对齐前提、四道闸门、外围闸门：见工作成果节引用。
- §8.1 自述"v9/v10 真实病历页双读有效但零采信"（设计文档 :119）与"存量=r3-v9"的说法互洽；现行代码已含关联接线（job service 冻结 `association_sources`，`page_review_job_service.py:89-90,108`），与"已实施未采信投影"段互洽。

**推断（标注）**
- 存量 v4 记录**可能**携带非空 context（v3+ 解码路径接受 context）；携带比例与 polarity 分布未知——直接决定关联 rescue 的现实收益。
- 归一化键在事实间碰撞风险随投影不变（键是纯函数输出），但 `accepted_fact_keys`/冲突分组/C 触发会变。

**假设（不可验证于边界，已声明）**
- 存量身份=v10/v4/r3-v9：待 Codex 元数据确认。
- v10→v11 提示文本差异：本 worktree 无 v10 文本副本（harness 文件未跟踪、无版本日志、任务目录无留痕），**不可文本审计**。

## 风险、差距与验证需求

1. **最高影响发现——提示文本未被冻结**：§7 要求"提示文本哈希与版本、响应原文哈希、Schema 版本一起冻结"，实现只冻结了版本**字符串**；system prompt 是代码内联字符串，未按版本持久化文本或哈希入记录/任务载荷。后果：今后每一轮"这算算法升级还是提示变更"的裁决都永久缺失文本证据，本轮 v10 vs v11 已无法文本 diff。最小修复：下一合同版本把构建后的 system_prompt 的 SHA-256 写入 `PageReviewRecord`（或内容寻址存 prompt 快照）。
2. **规范化算法版本无常量**：算法身份寄生在页合同版本上，"纯算法修复不改合同"在该架构下不存在（v6 解码验证器用现行算法复验，算法一变旧 v6 记录解码即失败→被迫升合同）。可接受，但投影实体必须显式记录 source contract + target algorithm 双版本，不得沿用合同版本冒充算法版本。
3. **原始响应字节未持久化**（仅 SHA+解析后载荷）："保留原始模型响应"只能以"解析载荷+可复验 SHA"的形式满足；复验性质未在真实记录上证明（陷阱见工作成果节 5）。
4. **存量身份未核实**：若 Codex 确认结果与假设不符（例如存量含 contract v3 或无 context），资格守卫与关联 rescue 的适用面要重估。
5. **操作面风险（非本项目新引入，但投影会放大感知）**：对账重算闸门意味着任何未来算法变更都会使全部既有 coverage 立即失配并要求整链重读；重投影对照报告应提前量化该影响面。
6. 验证需求：上述 property test 与反例 1-5；存量元数据核实；对照实验需真实页图像与双模型凭据——均超出我边界，留待 Codex 立项。

## 建议下一步

**给 Codex 的裁决点**
1. 采纳"重投影=诊断实体，正式准入不立项"（我的建议），还是存在我未见的正式准入用例（如页图像已丢失/永久内容过滤、无法重读的旧受试者）？后者需按工作成果节 3 的守卫单独立项并过四道闸门的显式放行分支。
2. 是否批准"prompt_sha256 入记录"作为下一合同版本（v7）必选项，以关闭风险 1。
3. 对照实验（重投影 vs v11 重读）是否列入当前阶段收尾证据矩阵——它同时是 §8.1 关联采信在真实记录上的首个实效度量。

**有界问题（同会话可答）**
- Q1：存量真实页读的精确身份（main/contract/reconciliation/handwriting 各版本 distinct 值）及**非空 context 占比**？只需元数据，我可据此把资格守卫从"假设"升级为"事实"。
- Q2：v10→v11 提示变更清单在任务记录中是否留痕？若无，是否接受"提示变更只可行为学比较"为既定限制？
- Q3：是否存在"原件不可重读"的旧受试者场景？（决定裁决点 1。）

**安全临时路径（不等答复即可做）**：按工作成果节 3 落地诊断投影实体+property test 骨架+对照报告模板；全部出口停在诊断层，不触碰四道闸门，不违反 §8.1.5。
