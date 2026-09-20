# Execution Output: written-judgment-search-contract-20260910 - worker_01

## Boundary And Context Check

- 本轮写仅限两个授权文件：`app/services/judgment_search_source.py`、`tests/v2/services/test_judgment_search_source.py`；`git status` 确认无其他文件改动。owner 对源构建器的重构（`FactAuthorityValidator.validate_and_get_revision` 接管活动权威校验、`scope_page_identity` 参数顺序、tamper 测试 cause 链断言）**全部原样保留**，我的新函数建立在其上而非替换。
- 无网络/模型/凭据/真实临床库/安装/本地服务/子委派；无设计/计划/checkpoint 编辑；无新框架、无 API/导出/持久化接线；候选读器仍处未接线状态。
- 工具披露：`apply_patch` 本运行时不可用，修改经 ZCode Edit/Write（含少量受控 `python` 文本替换脚本）完成，不声明与 apply_patch 等价。
- 勘察依据（只读）：`app/storage/fact_authority.py`（owner 引入的校验器）、`repositories.py` 的 `get_rule_set/get_rule/get_rule_component/get_evidence_requirement/list_expectation_templates`（全部镜像列+payload 哈希校验后解码）、`rules.py` 合同（`Rule.source_text` 为父规则已发布逐字原文所在行；`RuleComponent.title/expression/exception_expression`；`EvidenceRequirement` 必须且只能绑定子规则或流程必做项目之一）、`ProtocolSourceRecord` 合同（**仅含 source_ref 定位与哈希，无逐字文本**）、夹具规则树结构（`req-professional` → `component-ex-02` → `rule-ex-02`，EX-02）。

## Work Performed

**新增 `prepare_judgment_search_target(session, authority, requirement_id) -> (scope, target_text)`**（返回二元组，与模块既有纯函数风格一致；无平行证书 DTO）：

1. **scope**：每次准备调用 `build_judgment_search_scope` 完整重校验（owner 的 FactAuthorityValidator 路径 + 模板恰好一条 + 修订闭包 + 逐页身份），无缓存可信标记，未增加整修订重读。
2. **已发布来源装载（只含精确上下文，无整 RuleSet/ClausePack）**：`get_rule_set` → 方案版本与权威元组一致性核对；`get_evidence_requirement` → 已发布 requirement；`get_rule_component`（按 requirement 的显式 `rule_component_id`）→ `get_rule`（按组件显式 `parent_rule_id`）→ **组件属于父规则的显式成员核对** + 父规则期别与规则集一致。全程显式 ID，无标题匹配。
3. **模板一致性**：模板 `fact_type`/`due_stage` 必须等于已发布 requirement、`study_phase` 等于规则集、`workflow_stage_id` 属于该规则集 revision 命名空间；不符即“以模板顶替发布内容”拒绝（无 description-only 降级）。
4. **canonical target JSON**（`json.dumps(sort_keys=True, ensure_ascii=False, separators)`）：`identity`、`rule_set`（id/revision/protocol/study_phase）、`template`（template_id/projection_sha256/requirement_id/due_stage/study_phase/workflow_stage_id/fact_type）、`rule`（rule_id/official_code/kind/study_phase/**source_text 逐字原文**）、`component`（id/parent/display_code/title/expression/exception_expression）、`requirement`（已发布全文 `model_dump(mode="json")`，含 description）。确定性随内容变化；description 按指针处理——模块 docstring 明确记录 owner 给出的真实发布措辞只是指针而非硬编码权限，原样保留、不概括、不改写、不推断省略阈值/日期、模型输出非权威。
5. **支持边界（显式记录）**：流程必做项目目录来源（`rule_component_id=None`）→ 有界错误“流程必做项目目录来源……当前尚不支持；拒绝虚构父组件或以 description 顶替原文”。依据：`ProtocolSourceRecord` 无逐字文本，流程 requirement 的原生原文解析属方案文档读取链路，未接入即明确报错，不冒充支持。

## Artifacts And Evidence

新增 7 项测试（真实临时 SQLite + 既有链种子；未假设标题文本隐含研究者判断、未推断日期角色；无可为真的临床接受字段）：
- `test_prepare_target_includes_published_parent_source_and_child_context`：payload 与仓储逐字段断言——父规则 `source_text` 与 `get_rule` **逐字相等**、组件 title/expression 相等、requirement 全文相等（含 description）、模板 template_id/投影哈希/workflow_stage_id 相等、方案版本一致；scope 与 scope 构建器重取一致；同库重取 target 逐字相同。
- `test_prepare_target_differs_for_different_published_requirement`：不同 requirement → 不同 target，且他条 source_text 不混入。
- `test_prepare_target_excludes_whole_rule_set`：payload 无 `rules`/`clause_pack`；其他规则原文不出现在 target；rule 字段恰好 5 个。
- `test_prepare_rejects_template_requirement_mismatch`：自洽但语义分歧的模板（按投影公式重算哈希 + 镜像列同步的行级合成）→ “不一致”拒绝。
- `test_prepare_rejects_unknown_requirement_and_stale_authority`：未知 requirement 命中 0；陈旧修订指针被 owner 校验器拒绝（消息“作用域、活动指针或修订号”）。
- `test_prepare_procedure_requirement_boundary_is_explicit`：行级合成流程必做 requirement+模板（发布链同款结构）→ 有界不支持错误，消息含目录项 ID 与“尚不支持”，无降级 target。
- `test_prepare_target_is_read_only`：全库逐表指纹前后相等，`session.new/dirty` 为空。

## Commands And Observations

- `pytest tests/v2/services/test_judgment_search_source.py -q` → 首跑 2 failed，均为测试侧问题并修正：(1) 模板合同自校验投影哈希，直接改 `fact_type` 在解码期被拒——改为按投影公式重算哈希 + 同步 `projection_sha256` 镜像列，构成现实的自洽分歧反例；(2) 种子助手漏赋值 `rule_set_id`。修正后 **18 passed**（含 owner 既有全部测试）。
- 相邻套件合并：source(18) + reader(17) + coverage(31) + `test_fact_rule_link_repository.py`（rule/requirement 仓储）+ `test_storage_slice4.py`（模板边界）→ **115 passed**。
- `git status --porcelain`（限定两文件）→ 仅两个授权文件。

## Blockers Or Missing Environment

- 无阻断。工具披露：`apply_patch` 不可用（如实声明，不做等价性主张）。

## Rerun Requests Or Next Step

- 无需重跑。**已知限制（如实申报）**：流程必做项目目录来源暂不支持（有界报错，待方案文档原文解析链路）；target 是候选检索对象，**不是**跨引用已全部语义消解的证明、不是 D2 缺失生产者、不是临床批准；页域仍只是供给范围（`source_scope_verified` 恒 False）；target 尚无消费方接线（候选读器仍取自由文本，owner 集成时将 `prepare` 的 `target_text` 接入 reader 即可，二者合同已对齐——reader 端仅做非空校验与哈希，无需改动）。
