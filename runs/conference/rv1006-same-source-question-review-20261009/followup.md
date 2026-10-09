我按上次两个发现复查当前补丁：单 span 绑定、上下文身份，以及来源见证回放。# Conference Output: rv1006-same-source-question-review-20261009 - evidence_single_object

## Output

上次两处发现已在当前未提交补丁里收住。本轮没有看到新的必须先修缺陷。下面不是测试验收，也不是发布或临床批准。

### 已修复

单 span 绑定已经收紧。`source_question_official_context`（`protocol_control_source_interpretation.py` 484–519）在单元不是恰好一个 `source_span_ids` 时返回 `None`，多 span 单元进不了这条上下文路径。配对改为该 span 自身的摘录与整个 `unit.excerpt` 在 `normalize_source_excerpt` 后相等；另一位置的相同文字不会命中。平行数组长度不等或 span ID 重复会抛出「冻结官方来源位置与摘录身份损坏」，不再当成未命中。普通原句可改字段仍只有 `unresolved`（625–628）。

上下文包带有 `source_orders_by_span` 和恒为 `False` 的 `listed_order_is_reading_order`。找不到唯一 `source_order` 时该 span 为 `null`。提示词写明摘录数组按来源 ID 排列、不是阅读顺序，空顺序不能用来推定时间、范围或上位关系（579–584）。代码没有按 ID 排序去生成阅读顺序。

Runner 用 `source_question_context_identity` 比较收据 hash 与当前身份，两边都可以是 `None`（deconstructor 7240–7246）。当前陈述已无 `unresolved` 且身份不一致时，在发送请求前抛出「已变更上下文」。疑问还在时不放入 `seen_questions`，后续仍可在 `source_repairs = len(question_history)` 的原预算内重问。`_revalidated_source_seed_proof` 在回放前做同一比较（execution.py 2550）。缺 hash、错 hash、当前摘录已变、答复改了引文时，见证返回空且不改 `saved`。

### 未解决的必须先修

没有。损坏目标改为显式抛错，是本轮约定，不再要求把它吞成 cache miss。

### 建议

单元级 `source_order` 会被抄到该单元里的每一个 span。两个 span 同属一个多 span 单元时会得到同一个非空顺序，而提示词说非空值就证明原文位置顺序。更紧的做法是：只有当包含该 span 的单元本身恰好只有这一个 span 时才记录顺序，否则记 `null`。

提示词前半仍要求判断后续列表、上位条件和相邻分支，后半才禁止用数组顺序推断。模型可能只跟上前半句。

`prompt_sha256` 仍只记录、不参与恢复或见证比较。只改提示词、不改上下文包时，旧答复仍会因上下文 hash 相同而被跳过。

长度或重复 ID 的检查放在全部 `known_official_targets` 上，而且在疑问 `try` 之外。任一损坏目标都会让单 span 身份查询整批抛出，调用方得到异常，而不是「需要核对」收据。多 span 单元在扫描目标前就返回 `None`，这条路径不会主动发现损坏。

### 证据限制

本轮读了上述三个函数、合成测试 `test_same_source_official_question_context_is_read_only_not_adoption`、`test_same_source_question_runner_requires_fresh_target_review_and_preserves_history` 和 `test_revalidated_source_question_proof_requires_current_original_context`。没有运行测试。分配中的 65 passed / 1198 deselected / 7.35s 不是我的验证。

测试没有覆盖重复 span ID，也没有覆盖「绑定摘录仍在、只改其他摘录、且疑问已被清空」这一组合。代码对任何身份不等都会拒绝，但合成用例没有单独打到该组合。

没有重读目标复核复用循环，也没有读见证的调用方。因此不能判断损坏目标抛出的 `ValueError` 会不会被上层收成一次新的模型请求。没有读官方摘录的生产者，也没有读临床原件。
