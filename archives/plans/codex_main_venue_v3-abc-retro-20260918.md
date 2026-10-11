# Codex Main-Venue Plan: v3-abc-retro-20260918

Date: 2026-09-18
Objective: 复盘入排审核系统V3分工A/B/C切片：本地MTPLX属主启动与语法约束回退（合同入提示词）修复、IN-02本地修订成功、门禁28→5、剩余5项性质判定（真临床未决vs模型能力）与下一步构建方向（发布路径/B资料链/解释材料通道）

## Task Decomposition

1. **本地 MTPLX 接入改造复盘**（已完成，请挑战）：
   - 直接启动能力：`scripts/start_local_model_services.sh` + 运行清单修复（旧清单 27B 路径失效）。
   - 属主串行装卸打通：`ENROLLMENT_MTPLX_MODELS_FILE` + uvicorn 独占；生命周期日志证明每次重启干净释放。
   - 语法约束回退：xgrammar 编译 wire 合同失败（number→前瞻正则；嵌套 items→unsatisfiable，二分定位）→ mtplx 后端停用 response_format、合同入提示词；为绕开 Flash-Next qsa_prefill Metal kernel JIT 500（长提示形态触发），嵌入合同瘦身（去 $defs/深层）。
   - 结果：IN-02 由本地 Flash-Next 修订成功（revision 15）——本地语义修订链端到端可用。
2. **剩余 5 项定性**（请裁决处置路径）：EX-04×3（频次形式/回溯锚点/观察选择）、EX-07x（回溯锚点，原文确未写）、IN-06-C2-P1（来源子句绑定）。EX-07x/锚点类疑为真临床未决；IN-06/频次形式疑为模型能力+提示精度问题。
3. **发布策略**：blocking=5 时不发布（不伪造）；但"保留未决仍计阻塞"是门禁设计缺口。候选路径：a) 用户澄清材料走 register_interpretation_sources；b) GLM 配额恢复（2026-09-19 21:36）后再试 IN-06/EX-04；c) 门禁最小扩展（unresolved_items 显式存在时该类问题降级非阻塞并在报告中披露）——c 涉及发布合同，需谨慎评估。
4. **B 链下一步**（发布后）：subject 31001 → 上传 31001-基线血常规.pdf → original-page-images/v1 原图准备 → GLM-OCR-bf16 主读取（经 omlx_gate）→ 来源分派→事实发布 → 原件回看/事实修正入口。
5. **C 包前置**：等 A 发布 + B 至少一份真实事实。

## Source Packet

见 `context/v3-abc-retro-20260918_conference_context.md` 的 Source Of Truth 节（RETURN_A/B、implement、design、运行证据路径、实时 integrity 端点）。

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `general_single_object` | `zcode` | `GLM-5.3-Flash` | `runs/conference/v3-abc-retro-20260918/general_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

- 2026-09-18 10:2x CST：participant 首轮派发（zcode/GLM-5.3-Flash/max，runner 超 3600s）。
- 状态：见 Loop Log 与 runs/ 下报告文件。

## Codex Verification Checklist

- [ ] 参与者输出含完整 schema 且有独立反对意见（非复述）。
- [ ] 对 5 项阻塞给出可执行处置（含责任方与等待条件）。
- [ ] 门禁缺口（未决≠阻塞）的最小改法被评估且不违反"不以格式合法代替原件核实"。
- [ ] B 链顺序经参与者挑战后仍成立，或修正。
- [ ] Codex 综合结论写入 reviews/codex_conference_v3-abc-retro-20260918_review.md 并同步 implement.md。
