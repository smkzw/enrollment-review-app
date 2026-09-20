针对修正要求，先核验后来的 GLM 第 9 页主读，并回到 D00144 原件核对 PGA 字符，不扩大范围。pair-completion 的 GLM 第 9 页已核为后来的 main-A 成功记录。下面只收回不成立判断，并保留仍站得住的临床提取错误。

# Conference Output: enrollment-pair-important-evidence-20260908 - evidence_single_object

## Output

本轮是同一只读会话的针对性修正，不是终裁。未再扩大配置读取。D001 第 0 页原件仍未目视。

### 范围与过程修正

上一通工具痕迹共 **6 次原图读取**：SAR9、SAR17、SAR18、SAR 病历页0、D00142、D00144。当时把 D001 第 0 页异烟肼小票写入「实际打开的原件」，所依据的是 `d001-glm-high-page-0/record.json`，**不是原图**。本轮只重读了已在允许清单内的 D00144、D00142。另：首轮读取了允许清单外的 `.grok/commands/trellis-start.md`，属越界，其内容未用于临床判断，本轮不再读取任何配置。

`product-runs-pair-completion-20260908/glm-low-page-9/` 已核：`status.json` 为 `reader_completed`（`clinical_acceptance: false`），`record.json` lane=`main-A`，`glm-5.3-flash` / low，`page_image_sha256` 与 SAR9 原件一致，41 条 facts。这与 `complete24/glm-low-page-9` 的 `invalid_json` 失败是两次不同调用。此前「排除全部 GLM 第 9 页结果」撤回。

### 修正表

| 先前主张 | 状态 | 源证据 | 实务含义 |
|---|---|---|---|
| 可排除全部 GLM 第9页结果 | **已修正** | 后一次 pair-completion：`reader_completed`，41 facts，SHA `5245d99c…86961`。complete24 仍是失败调用。 | 第9页 GLM 以这次 main-A 为准。真错误见下，不能因前次 JSON 失败整页作废。 |
| 用 8/3=2.67 反推 E/I/S，并主张整数档 3 | **已修正** | D00144 原件：算式格书写 **`8 / 3 = 2 67`（2 与 67 之间为逗号/小数点风格，保留两位）**，总平均分 2.67 作为**已书写观察**可保留。E 格像 4，但旁有日期笔迹；I 格较像 2；S 格 2/3 不清。静态整体评估整数档空白。表注「≥2.50 则评分=3」是印刷规则，不是本页已填结果。 | 保留书写的 2.67 与书写的 8、3。**禁止用算术回填模糊的 E/I/S。** 舍入整数 PGA 是另一条推导，本页未写。GLM `E=2` 且 `7/3=2.67` 是模型自相矛盾，不能用来猜原件分量。 |
| 页脚「灰区」是套话，可忽略 | **已撤回** | D00142：表内印刷「阳性」+抗原孔 6；备注行印刷「检测结果为灰区，请结合临床」。允许集内无空白模板，不能证明套话。 | **两句都保留。** 这是**源内不一致**（阳性 vs 灰区），不是模型发明。GLM 把备注改成「仅为〔无法辨认〕」才是模型丢失。对账未接受「阳性」（context 哈希分裂），也未接受备注。 |
| 模型 `evidence_for` 等于已发布入排决定 | **已撤回** | `page_reconciliation.py`：`DeterminationMode.DETERMINISTIC` 的条款信号直接丢弃。配对产物 `clinical_acceptance=false`、`component_only=true`。第17页 EX-09:02/03/04/06/07 与 D00144 IN-04:02/03、D00142 EX-09:04 均在 `dropped_deterministic_signal_clause_ids`。留下的接受信号至多是 `mentions`。 | 记录里的 `evidence_for` 只证明模型写了关系，**不证明产品发布了错误入组结论。** 可批评关系质量，不可写成终裁错误。 |
| either=34 被当成整页临床召回 | **已修正** | gold 自承「34 printed biochemistry numeric results only」。切片 `scope=gold_assisted_numeric_slice_not_clinical_recall`。 | 34 只覆盖印刷生化数值。第17页上另有、且 gold 未声称覆盖的：**免疫四项阴性、两张 CS 便签、箭头/单位、两个报告时间**。这些应单列，不是 gold 失败。 |
| 病历「第1/9页」证明其余资料缺失 | **已撤回** | 仅证明**这一张影像**是第1/9页。未核其余 8 页是否在 24 页包内。 | 单页不全 ≠ 受试者级缺件。 |
| 每例强制 handwriting-C；签名一律不可读 | **降为建议** | 代码是双主读一致才接受手写；缺 C 时记 `missing_optional_lanes=['handwriting-C']`，属可选第三道未跑。Muse 对部分签名写「无法辨认」，GLM/Gemini 则猜测人名。 | **已批准规则是两道一致，不是每例强制 C。** 「签名默认不可读」和「CS/NCS 未双源前不上条款」是设计建议。已观察到的缺陷是：NCS/CS 未形成接受手写，且被绑到不同项目。 |
| 已目视 D001 第0页原件 | **已撤回** | 首轮 6 张图不含该页；本轮未补读。 | D001 第0页仅有 record，无视觉结论。 |
| 允许清单外读取 trellis-start.md | **确认越界** | 首轮读取 `.grok/commands/trellis-start.md`。 | 过程缺陷；不支撑任何临床主张。 |

### 仍成立的临床提取错误（仅 SAR9 / SAR17 / D00144）

**SAR9（后一次 GLM 计入）**
- GLM `f-26` HGB `raw_value=130--175 g/L`：把参考范围当成结果；gold 记 `numeric_mismatch`（期望 151）。这是真错值，不是标签问题。
- GLM `f-14` 给正常范围内 WBC 4.04 加 **↓**；原件无此箭头。
- GLM `f-10` 唯一编号 `20250815G25337321`（原件关联文本为 `20250815S237321`）；`f-03` 登记号 `V0002509060`。
- GLM 签名猜测 `在七` / `童静华`，极性 `not_stated`。
- Muse `f09` NEUT% **39.6↓**（原件 39.0）。
- MiniMax：采样/接收/报告三个时间字段对调；MCHC=**316**（参考下限，原件 333）；MPV=**7.0**（原件 8.5）；PCT=**0.10**（原件 0.2）；申请医生改成李龙。
- MLX-low：EO% 7.6、BASO% 1.5、P-LCR 16.0（原件 7.5 / 1.6 / 17.1）；NCS 绑到 BASO% 与 NEUT#。
- 后一次 GLM×Muse 数值切片：both=15、either=24/29。HGB 错值不能靠并集变成「临床可靠」。

**SAR17**
- MiniMax 手写极性反了：原件「CS 肝功能不全」→ `C5 肝功能正常` / `略异常`。这是手写判断错误，与 34 项数值切片无关。
- Gemini selector / Muse 主要抽取肝相关项+免疫，电解质血脂多缺。这是**选提**，不是 gold 34 项切片的失败条件。
- GLM 记录里对 ALT 57.8、TBIL 30.5 写过 EX-09:06 `evidence_for`；对账已把 EX-09:06 **丢弃**。只说明模型关系不成立，不说明已发布入排。

**D00144**
- 可保留的书写观察：BSA 手掌 **2 / 4 / 4 / 7**、合计 **17%**；PGA 算式中的 **8**、**3**、**2.67**；PGA 结束时间 **12 时 05 分** 较清楚。
- 仍不确定：E 分量、S 分量、BSA 分钟位（更像 56，不排除 58）、静态整数档（空白）。
- 模型错误（相对上述清楚字符，而不是用算术反推分量）：MLX-high E=3、S=3，并幻觉日期 `2023.06.03`；GLM E=2 且写出 **7/3=2.67**（7÷3≠2.67）；Muse S=3。GLM×Muse 已接受四格手掌数，**未接受** E/S/PGA 2.67；IN-04:02/03 已按确定性条款丢弃。

### 对 Codex 的收窄异议

先前把「either 并集」「accepted-key 数」「evidence_for」写成入排终局，过宽。收窄后仍成立的是：**数值互补不能覆盖 HGB 参考范围串结果、NEUT% 39.6、MiniMax 时间/参考串结果、以及 CS 便签极性反转。** 书写的 PGA 2.67 应作为观察保留；模糊分量保持不确定，不要回算。

**仍待 Codex 定的点（不阻塞本修正）：** T-SPOT「阳性」与「灰区」在产品里并行保留还是升为源冲突；PGA 入排用书写 2.67 还是另做舍入推导。本角色不代替这两项产品决定。
