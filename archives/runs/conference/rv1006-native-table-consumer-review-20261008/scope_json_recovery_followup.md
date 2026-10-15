第五轮差异复核：先定位 `json_invalid` 重试与 v4 标记的落点。

核对服务层失败映射与专用失败码解析。

最后一处：确认失败码解析函数是否会遮蔽专用 JSON 失败码。

# 单条来源范围回答语法恢复：受限差异审阅（基线 5bac5819）

**结论**：未发现必须修。五项挑战逐一有证据支持；本审阅未运行测试、未调用产品、未核临床。

## 必须修
无。

## 逐项裁定（落点）
1) **次数有限且真实扣减**：`deconstructor.py:8178-8180` `for format_attempt in range(2)` 每次调用前 `source_repairs += 1`；入口先验 `source_repairs >= max` 即抛（`:8163-8164`）；首次 JSON 失败后仅当 `format_attempt==0 且 source_repairs < max` 才允许重交（`:8211`）。`json_budget` 用例（`max_schema_repairs=1`）只得到 1 次调用、1 条 schema_invalid 记录（测试 `:6733-6734,6766`）。预算不足时不会再调。
2) **不会变成可采用未决**：二次仍 json_invalid 时抛出技术失败 `SourceTargetReviewValidationError(code=SOURCE_SCOPE_CORRECTION_JSON_INVALID, retry_class="schema")`（`:8212-8219`），非 unresolved；失败码在白名单贯通外层 attempt（`:9501`）与服务映射（`execution.py:4109`），服务以 `retryable=False` 抛 `PROTOCOL_CONTROL_SOURCE_SCOPE_CORRECTION_JSON_INVALID`（`:4119-4136`）；`protocol_control_call_failure_code`（`protocol_control_agent_transport.py:331-348`）对本异常返回 None，不遮蔽专用码。
3) **失败前不变更来源/兄弟**：`source_interpretation` 仅在成功解析并过 apply/原生门后重赋值（`:8230-8244`）；JSON 失败路径只记录 attempt、无字段写入；兄弟不经此块。重试提示不回声坏答（测试断言二次提示无"Wait structure_unit_id"，`:6729-6730`）。
4) **合法 JSON 错 ID 仍硬拒**：结构化但身份错由 `apply_source_scope_correction` 拒绝（`source_interpretation.py:509`），不进入格式重试（`wrong_id` 仅 1 次 scope 调用；`json_then_wrong_id` 重试后仍拒、来源不变，`:6742,6749,6762`）。混合错误类型 `all(type=="json_invalid")` 为假即直接 raise（`:8189-8191`）；传输失败非 ValidationError、不重试。
5) **成功不额外改语义/不开整包**：成功后仍走同一非原生等式检查、apply 门、原生共同标题再核、`_unreported_time_fragments`（`:8225-8243`），随后仍是 `repaired_review_indexes` 保护下的一次目标重核；重交仅追加格式约束且声明"原来源、编号与修订范围不变"（`:8220-8224`）。

## 残余与证据边界
- validator 仅升 `native-table-scope-recovery/v4`（`execution.py:2060`），compiler 列表未动（`:2053`）；旧 validator-差容忍与旧成功复用语义沿用前几轮结论，新路径只在修复环执行。
- 未读：服务 `detail` 文案字典在新码处是否已有专用中文说明（`:4143` 起截断）；错误码贯通已验证，文案呈现属建议核对项。
- 账本说明：`source_repairs` 是本批修复共享计数，不是全历史每条 scope 调用账本；本补丁不声称全局额度模型（与任务声明一致）。
- 静态读取 8 次有界区域；测试未运行，结论以代码与既有断言为准。
