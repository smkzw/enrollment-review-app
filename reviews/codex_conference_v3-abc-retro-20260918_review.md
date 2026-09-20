# Codex 综合评审：v3-abc-retro-20260918

日期：2026-09-18｜主席：Codex（ZCode 主会话）｜参与者：codex-subagent/gpt-5.6-sol（声明后备链；zcode 主路由会话未能建立，已按 packet 规则记录）

## 参与者意见采纳情况
1. **EX-04 两项时间问题同根（门禁识别缺陷）——采纳并已验证**：`_predicate_temporal_text` 用语义身份（无"1周≥4天"）做频次识别 → FREQUENCY 误报 + 同 duration 被当无锚回溯 → TIME_ANCHOR 误报。修复：occurrence_window 存在时以完整逐字来源重识别频次，仍经 `_predicate_preserves_frequency` 严格核对（绑定词前导周期短语/尾部"的"剥离扩展）；门禁版本升至 2026-09-18.1。反例测试×2 落地（test_deconstruction_gate_slice3.py：频次分母不再双报；EX-07x"6个月内"仍阻塞）。真实 SAR 草稿 integrity：5→3。
2. **反对"unresolved 即降级非阻塞"——采纳**：不实施通用降级；EX-07x 走 register_interpretation_sources 等待用户权威澄清材料。
3. **OBSERVATION_POLICY 覆盖 EX-04+EX-15（计数≠问题数）——采纳**：按谓词分账；两者均为"多记录聚合/选择方式"操作语义未决，需医学责任方确认，保持阻塞。
4. **IN-06 确定性来源装配缺口（P1+P2 共同前缀未入组件摘录）——采纳**：下次会话对 IN-06b 做目标化修订（宿主预装公共前缀摘录、限定仅返回目标对象），不等 GLM。
5. **mtplx-api 别名漏洞——采纳**：`_GRAMMAR_INCOMPATIBLE_BACKENDS` 需含 mtplx-api（下一 MTPLX 调用前修复，转工程清单）。
6. **B 链十步路径（含 preview→commit 边界）与"隔离 fixture 工程接线可先行、正式 P1 等发布"——采纳**。
7. **文档滞后——已修正**：本文件+RETURN_A/implement 同步至 revision 15、门禁 5→3。

## 会商后实际完成（下一步构建第一批）
- 门禁 EX-04 缺陷修复 + 2 个反例测试；回归甄别：4 个失败全部预存（纯 dirty 基线复现），零新增回归。
- 真实 SAR 重算：blocking 5→3（EX-07x 锚点、观察选择×1、IN-06 绑定×1）。

## 剩余 3 项与责任
| 项 | 性质 | 出路 |
|---|---|---|
| EX-07x 回溯锚点 | 真方案解释未决 | 用户提供权威澄清材料（Q&A/函件）→ register_interpretation_sources |
| 观察选择（EX-04+EX-15） | 操作语义未决 | 医学责任方确认聚合/选择方式；无来源保持阻塞 |
| IN-06 来源绑定 | 确定性装配缺口 | 下次会话目标化修订（工程，不需要用户） |

## 残余风险
- MTPLX qsa_prefill kernel JIT 缺陷未根治（瘦合同绕行有效但未做稳定性重复试验）。
- 会商参与者为后备模型（gpt-5.6-sol），非原定 GLM-5.3-Flash——独立性记录在案。
- 3 项清零前不能发布；B 正式 P1 继续等 A 发布。
