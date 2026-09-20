# Phase 5.5 技术设计

## 边界

合同层分成两个小模块：`app/domain/contracts/page_review.py` 只定义不可变交换合同；`app/projections/clause_pack.py` 只负责从已发布 `RuleSet` 生成内容寻址 ClausePack。模型客户端、调度、持久化与界面在后续步骤接入，不提前混入合同实现。

## ClausePack

- `ClausePack` 绑定 `rule_set_id / revision / protocol_version_id / study_phase`，并保存稳定 `clause_pack_sha256`。
- 每个 `ClausePackClause` 对应一个 `RuleComponent`，保留官方规则编号、规则类型、父规则与组件身份、原文、结构化表达、例外和资料要求。
- 分类优先级为：任一原子谓词需要专业判断 -> `investigator_judgment`；否则存在时间约束、数值比较、数值值或多层逻辑 -> `deterministic`；其余 -> `semantic`。分类规则只使用结构字段。
- 哈希覆盖全部执行字段，不包含生成时间、文件名、模型结果或测试项目别名。

## 页级合同

- `PageReviewRecord` 一页一模型一条。main-A/main-B 可写事实、条款信号和手写；handwriting-C 必须只写手写数组。
- `PageFactObservation` 同时保存原始文字和值、规范值和 `normalization_key`，不得把规范化结果覆盖原文。
- `ClauseEvidenceSignal` 仅允许四种证据信号和摘录，不携带条款判定。
- `HandwritingObservation` 使用固定类型并保存原文、规范键和页内位置；空数组是合法的强制字段。
- `PageReconciliation` 保存已对齐事实、事实冲突、已采信手写、手写冲突及被丢弃的确定性方向信号。
- `SubjectPageCoverage` 绑定预期页清单和每页处置，校验页身份完整且不重复。

## 兼容与失败关闭

- Pydantic `extra=forbid` 负责拒绝判定词与未知字段。
- handwriting-C 如写入事实或条款信号，合同直接拒绝。
- 失败覆盖保留原读道身份、失败类别和待复读状态；后续调度不得用另一读道替换。
- 本阶段不建数据库迁移，先稳定合同和纯函数；持久化随 harness 接入时单独设计。

## 受控重叠

Phase 5 的人工临床核对发现手写 CS/NCS 未被 OCR 文本覆盖。该问题正是 Phase 5.5 的输入，不应通过手工补事实或假闭合解决。因此 Phase 5 继续保持开放，Phase 5.5 先建立合同；待真实双模型页读结果补齐覆盖后，再回到 Phase 5 完成 31001 临床 QC。
