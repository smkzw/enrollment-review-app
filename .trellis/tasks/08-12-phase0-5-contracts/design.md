# Phase 0.5 合同设计

## Contract Layers

1. `app/domain/contracts/`：Pydantic 领域 DTO、稳定 enum、RuleExpression 递归结构。
2. `app/domain/gates/`：纯函数校验状态/gap、Agent 写权限和规则结构。
3. `app/domain/rollup.py`：组件到节点主状态、计数和排序的确定性汇总。
4. `contracts/v1/schema/`：由代码生成的 JSON Schema 与 OpenAPI 草案。
5. `contracts/v1/fixtures/`：正常、明确障碍、缺口/冲突三个自包含受试者。
6. `contracts/v1/agents/`：节点 I/O、PromptVersion、权限、重试、幂等和停止条件。
7. `contracts/v1/interaction/`：设计 token、交互和 UAT 合同。

## Invariants

- 所有可持久实体含 `schema_version` 和稳定 ID；可编辑实体含 revision。
- 日期使用 ISO 8601 字符串和显式精度，不依赖 JavaScript/Python 隐式日期解析。
- RuleExpression 使用可辨别联合；原子谓词只能引用自己的 subject/attribute/unit/anchor，不接受理由文本推导。
- EvidenceSpan locator 只允许一个精度层并保存降级原因；没有 bbox 时前端不能显示坐标高亮。
- AssessmentCandidate 与 FinalAssessment 类型分离；只有 Gate 输入能产生 FinalAssessment。
- 节点汇总不读取 narrative/reasoning，只读取结构状态、gap、blocking 和 expectation。
- Action 自动关闭只接受同一 rule_component_id 的 closure predicate；关闭不等于规则通过。

## Schema Policy

- Pydantic 是规范源；生成脚本必须确定顺序并可重复执行。
- JSON Schema 使用 `fixture/v1` 标识和 `$defs`；fixture 既经过模型校验，也经过生成 schema 校验。
- OpenAPI 草案只定义 Phase 1 stub 所需的只读查询和界面动作，不提前实现数据库。
