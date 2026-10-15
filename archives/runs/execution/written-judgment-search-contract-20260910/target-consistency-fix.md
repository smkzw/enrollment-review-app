# Execution Output: written-judgment-search-contract-20260910 - worker_01

## Boundary And Context Check

- 本轮修改仅两个授权文件：`app/services/judgment_search_source.py`（函数内检查逻辑 + 模块 docstring）与 `tests/v2/services/test_judgment_search_source.py`（新增对抗测试）。`git status` 确认无其他文件；owner 全部既有修改（`FactAuthorityValidator` 路径、既有测试）原样保留且全部继续通过。无仓储文件修改（语义合同逐字复用、未写入）。
- 无临床文件/库、模型调用、网络、凭据、本地操作、安装、子委派。工具披露：`apply_patch` 不可用，修改经 ZCode Edit/受控文本替换完成，不声明等价。
- 复用核对：逐字读取 `save_expectation_templates`（语义合同 dict + stage 存在/方案版本/期别/前缀/due 核对）与 `get_workflow_stages_by_ids`（原生合同解码）后实现。

## Work Performed（三项修复，均在 `prepare_judgment_search_target`）

**修复 1 — 模板↔已发布 requirement 语义全量一致**：按写边界同一语义合同逐项比较 `due_stage`、`fact_type`、`required_source_types`（`sorted(set(...))` 集合语义）、`requires_contemporaneous_objective_source`、`allows_screening_record_transcription`、`description`（外加模板 `study_phase` 与规则集一致）；任一不等即“语义不一致，拒绝以模板顶替发布内容”。分歧字段绝不从 target 中省略——target 的 requirement 部分始终来自 `get_evidence_requirement` 行而非模板。

**修复 2 — 审核节点实存与到期核对**（替换原先仅 startswith 的命名空间检查）：前缀核对保留 → `session.get(WorkflowStageRecord, ...)` 行存在性（缺失 → 有界错误，不发明节点、不静默忽略）→ 行列 `protocol_version_id`/`study_phase` 与规则集一致 → `get_workflow_stages_by_ids` 解码合同 → `requirement_id in stage_contract.due_requirement_ids` 且 `stage_contract.stage == template.due_stage`。与写边界同语义的只读重核。

**修复 3 — 选中路径三重精确结构相等**：已加载 `rule_set.rules` 中该父规则 `== get_rule` 结果；`rule.components` 中所选组件 `== get_rule_component` 结果；`component.evidence_requirements` 中该条 `== get_evidence_requirement` 结果（pydantic 模型全字段相等，非模糊文本）。规范化行与包围载荷的自洽漂移一律“载荷漂移”拒绝。仅验证选中路径，docstring 明确不声称整树闭包。

**顺序说明**：流程必做来源的不支持分支保留在语义一致核对之后、工作流核对之前——其边界消息保持显式不变（现有 procedure 测试原样通过）。

## Artifacts And Evidence

新增 6 项对抗测试，全部为**自洽突变**（投影哈希按公式重算 + 镜像列同步，绝不仅破坏校验和）：
- `test_prepare_rejects_template_description_drift`（同 fact_type 的 description 漂移 → “语义不一致”）
- `test_prepare_rejects_template_source_types_drift`（required_source_types 漂移 + JSON 镜像列同步 → 拒绝）
- `test_prepare_rejects_template_flag_drift`（requires_contemporaneous_objective_source 翻转 → 拒绝）
- `test_prepare_rejects_template_wrong_due_stage_node`（模板改指真实存在的 baseline 节点：命名空间/方案版本/期别全对、FK 满足，但非到期阶段且不在 due 清单 → “按期到期”拒绝）
- `test_prepare_rejects_ruleset_rule_payload_drift`（RuleSet 载荷内 rule-ex-02 的 source_text 漂移，行级 Rule 记录不变 → 结构相等拒绝）
- `test_prepare_rejects_requirement_payload_drift_inside_component`（组件载荷内 requirement description 漂移，行级 requirement 记录不变 → 拒绝）

保留并继续通过：夹具正常行为、稳定哈希/逐字上下文、无整 RuleSet、未知 requirement/陈旧权威拒绝、流程必做显式不支持边界（消息含目录项 ID 与“尚不支持”）、只读全库指纹不变。

一个如实说明：**“审核节点行缺失”反例不可通过真实行状态构造**（模板行 FK 强制引用存在的 stage 行，删除 stage 行同样被 FK 阻止）；该路径以代码实现 + 错误消息覆盖，可行的对抗面（错节点、缺 due）已用真实行状态证明。

## Commands And Observations

- `pytest tests/v2/services/test_judgment_search_source.py -q` → **24 passed**（18 既有 + 6 新增；一次性通过，无失败需要归因）。
- 要求套件合并：source(24) + reader(17) + coverage(31) + `test_fact_rule_link_repository.py` + `test_storage_slice4.py`（模板边界仓储测试）→ **121 passed**。
- `git status --porcelain`（限定两文件）→ 仅两个授权文件。

## Blockers Or Missing Environment

- 无阻断。工具披露同前：`apply_patch` 不可用，经 ZCode Edit 完成，不声明等价。

## Rerun Requests Or Next Step

- 无需重跑。仍待 owner 集成（未变）：目标文本接入候选读器调用方、流程必做来源的方案文档原文解析链路、检索结果持久化/重试编排/独立双读回执汇总/语义核实与适用性/缺失生产者。目标准备仍非 D2 缺失生产者或临床批准；`source_scope_verified` 恒 False。
