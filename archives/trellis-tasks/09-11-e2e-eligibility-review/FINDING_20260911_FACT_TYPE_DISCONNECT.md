# 发现：确定性条款求值全链断链（2026-09-11 深夜，基线验收触发）

## 现象

基线节点 eligibility-review 返回 81 条**全部** professional_judgment（筛选节点同病：55 无法判定+26 尚未到期，无一条确定性判定）。IN-01「年龄 18~75」在 1505 条链头事实含 10 条年龄事实（值如 52 岁）的情况下仍判「无法判定：病历记录不完整」。

## 根因（逐层复现证据）

1. `app/domain/expression.py:489`：谓词匹配键 = `f"{predicate.subject}.{predicate.attribute}"`，SAR 真实规则 → `"受试者.年龄"`。
2. 真实已发布事实的 `fact_type` 是 normalizer 产出的中文临床类型名（如 `"年龄"`、`"ALT"`），**无点号组合名**。
3. 全库统计：谓词类型 116 个 vs 事实类型 910 个，**直接交集 = 0**。`_evaluate_atomic` 的 `matching` 恒为空 → `TruthValue.UNKNOWN`（reason=fact_not_observed）→ gaps 补 RECORD_INCOMPLETE → 全部落 professional_judgment。
4. 为什么测试全绿：`tests/v2/services/test_eligibility_review_projection.py` 的种子 fixture 用 `subject="demographics", attribute="age_years"` 谓词 + `fact_type="demographics.age_years"` 事实——合成英文类型名自圆其说，两侧词汇表在同一次测试里被人为对齐，掩盖了真实链路断链。这正是 EngReview 曾标记的 R1 风险（适配器）的现实爆发，但爆发点不在适配器而在**词汇表从未对齐**。
5. 该断链不影响筛选期验收结论的正确性（无法判定+缺口诚实保留符合医学边界），但意味着「确定性条款由代码判定」的产品承诺至今零兑现：81 条里 39 条 deterministic 模式的条款全部被降级为人工判断。

## 影响面

- eligibility_review 投影（筛选+基线）：全部 81 条判定不可信（过保守，不是错误判定）。
- 报告打印页/工作台「无法判定 N 条」数字被系统性放大。
- 判断检索不受影响（它按 requirement 检索，不做谓词匹配）。

## 修复方向（需用户决策，二选一或组合）

A. **事实侧对齐**：发布链路（normalizer 输出契约）要求 fact_type 使用规则的 subject.attribute 词汇表（受控词表注入提示/门禁校验）。改动大、涉及模型提示，但一次对齐永久生效。
B. **求值侧对齐**：适配器/求值器把中文事实类型映射到谓词键（如「年龄」→「受试者.年龄」）。需要映射表（又是词表维护），但不动模型链路。
C. **结构化桥接**：规则解构时给每个谓词挂 expectation 模板（已有 fact_type="年龄证明"等中文类型），求值按模板 fact_type 匹配而非 subject.attribute 拼接。最符合既有 expectation 架构，改动集中在 expression.py 匹配键。

## 暂停点

- 基线节点验收**不通过**（判定质量不可信），收口推进在此暂停。
- 06c 数据/判断检索/429 修复不受影响；`c061aa6` 及之前全部有效。
- 本发现不改变 claims_complete=false 的正确性。
