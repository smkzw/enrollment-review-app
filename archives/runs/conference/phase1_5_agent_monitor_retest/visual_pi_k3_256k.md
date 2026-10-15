# Conference Participant Output: phase1_5_agent_monitor_retest - visual_pi_k3_256k

## Boundary Check

- Read `AGENTS.md`, conference context, and main-venue plan before acting. No source file was read for editing and none was modified; only read-only docs (`AGENTS.md`, task `prd.md`, `findings.md`) and the live app at `http://127.0.0.1:4173/` were used.
- Worked entirely in the real headless Chromium tab via the browser tool: desktop 1280×800, narrow 390×844, and 853px (≈150% zoom at 1280). Manipulated only synthetic UAT state (filters, selections, sessionStorage inspection, one `localStorage.clear()` probe). No other participant output was read.
- No production path touched; no final acceptance claimed. Version verified: header badge "界面试用项目 · Ⅲ期 · 方案 V1.0" and `帮助` page "页面版本：界面试用版 1.5.2", matching `frontend/public/uat-status.json` (`pageVersion: 界面试用版 1.5.2`).

## Independent Work Product

Completed route (risk → rule → judgment → evidence → profile, plus second subject/stage):

1. **今日工作 → 入排工作台（UAT-03 筛选期，EX-01a 冲突）**：今日工作卡片携带 `episode`+`component` 直达正确受试者，无静默切换。统计口径说明（I5）在页面上明确写出。
2. **规则树/父子逻辑**：EX-01 父级展开显示合成规则句；EX-01a 子项判断视图呈现「全部满足 → 任一满足 → 不满足以下条件」嵌套与例外条件块，例外附效果语「例外条件成立时，本条不因主条件成立直接判定，按方案例外处理」（**B5 复验通过**）。谓词自然：「检查值相对正常上限的倍数 大于等于 1.5 倍正常上限」，无「为 等于 是」（**I2 复验通过**）。
3. **冲突来源并列（B1 复验通过）**：证据区「冲突来源并列」将同一事实的「明确记载」与「明确否认」两侧并列，各自带文件/页码/来源方/快照版本，不自动选边。
4. **证据弹窗（I3 复验通过）**：显示资料快照「第 1 版（2026-08-12 整理）」、页码、定位精度与降级原因，诚实声明「界面试用阶段未附带原始页图，不提供整页预览」。
5. **应备证据覆盖（I4 复验通过）**：节点 7 项应备证据均带规则编号、具体要求、到期节点；EX-03a 标「后续节点尚未到期」并注明「当前不作为缺口处理」。
6. **受试者与资料/个例全景（回环闭合）**：UAT-03 风险视图 7 卡（主题标签+关联规则+打开证据）；UAT-02 个例 2 卡均带日期。完整明细按主题分泳道（研究节点/人口学/目标疾病/症状体征/既往史/用药/非药物处理/检查与评分…），空泳道文案为「该主题下当前没有已整理的结构化事件…空记录不等于"正常"或"否认"」（**B3 复验通过**）。UAT-01 时序含 1990 出生日期、2024 手术、2025 用药疗程、2026 知情同意/确诊/血常规，非节点锚点堆砌（**I6 复验通过**）。
7. **项目看板（B2 复验通过）**：「存在冲突 5」「需专业判断 5」计数非零并注明可叠加口径；点选「存在冲突」正确收敛到 UAT-03/04/08。390px 下页面无横向溢出（`scrollWidth == innerWidth == 390`），表格在容器内滚动；勾选后批量工具条为 `position: sticky`，带「只处理明确勾选对象」范围说明（**I8 复验通过**）。
8. **行动中心（I1、I5 复验通过）**：独立「溯源提醒」类别筛选返回 4 条（UAT-01/05，阻断程度「无」）；行动详情含谁负责/补什么/可关闭证据/资料版本，并诚实写明「关闭行动…不等于规则自动通过」。两页数量口径说明互相呼应。
9. **导航保护（B4 复验通过，有保留）**：无效 episode URL 显示「未找到这个审核节点…为避免误读，本次没有打开其他受试者的资料。请从项目看板重新选择」——符合修复合同。裸 `#/workbench` 经 sessionStorage `last-workbench-episode` 恢复**上次查看的** UAT-02（localStorage 为空时仍生效），这是刻意的"回到上次"而非任意首项，可接受，但见下文 R3。
10. **I7 复验通过**：UAT-02 EX-01a 显示「已触发 + 阻断」，无「触发但阻断程度：无」矛盾。
11. **中文扫描**：9 个页面 DOM 全文正则扫描 `Agent|schema|pipeline|provider|fixture|Gate|mock|OCR|LLM|AI|prompt|token|episode|component|span-` —— **零命中**。
12. **视觉**：浅色站点、全局导航稳定、风险红仅用于风险/冲突标记；390px 与 853px 三页均无页面级裁切；853px 受试者页列表降级为下拉，合理。

### 独立发现（本轮新发现，不在既有 B/I 清单）

**F1（最高优先级，证据链诚实性缺陷）**：个例全景/完整明细中每张事件卡的「打开证据：<事件名>」链接全部指向**同一个证据定位**。实证：UAT-01 完整明细里「阑尾切除术」「术后抗菌药物疗程」「目标疾病确诊」「签署知情同意书」的链接均为 `evidence=span-uat-01-screening-clear-age`；点击「打开证据：阑尾切除术」落地到 IN-01 证据区，展示的是「年龄：36岁」摘录——与阑尾切除术完全无关，且页面无任何"这是共享示例定位"的提示。UAT-03 同样：7 张卡（含「合并用药时间轴待核对」「既往资料被引用但未提供」）全部指向同一 `span-uat-03-screening-gap-page`，落地为 EX-01a 冲突证据。链接文案承诺的是该事件的证据，实际交付的是无关证据——方向性误导，比"没有证据"更危险：监查员可能把年龄记录误认为手术证据。这触及产品核心承诺（每个事实可回源）。

**F2（中）**：冲突并列两侧除判定标签（明确记载/明确否认）外不可区分——同文件、同页码、同来源方、无摘录、无录入条目标识。监查员无法判断同一页上哪条记录说了什么。属"仅页码"精度下的诚实降级，但并列展示的实用价值大打折扣。

**F3（低/建议）**：UAT-03 风险视图 7 卡中 6 张无时间信息（仅首张有 2026-08-10）；纵向视角下「合并用药时间轴待核对」无法定位时间窗。完整明细泳道有日期，可缓解，但首屏风险卡缺时间削弱了"风险优先 + 时间"的首屏目标。

## Evidence And Assumptions

**已验证事实**（真实浏览器操作，附落点）：
- 版本 1.5.2：`uat-status.json` 与帮助页一致；无登录直达。
- B1–B5、I1–I8 逐项复验通过（路径见上；关键 DOM 证据：sticky 工具条 `position: sticky, top: 60`；390px `scrollWidth=390=innerWidth`；溯源提醒筛选返回 4 条；无效 URL 守卫文案原文）。
- F1 证据：UAT-01 五张事件卡 href 均为 `span-uat-01-screening-clear-age`；点击后 `location.hash=#/workbench?episode=episode-uat-01-screening-clear&evidence=span-uat-01-screening-clear-age`，证据区显示「年龄：36岁」。
- F2 证据：冲突两卡均为「合成筛选资料.pdf 第 4 页 · 筛选记录 · 来源方：研究者方」「该页仅有定位信息，未提供文字摘录」。

**推断**（未直接证实）：
- F1 根因 [INFERENCE]：fixture/投影层每个 episode 只生成了一个代表性 span，个例事件统一复用；并非逐事件映射缺失的显示 bug。
- 裸导航恢复上次上下文依赖 sessionStorage 设计 [已观察 key 存在，设计意图为推断]。

**假设**：853px 视口近似 1280 下 150% 缩放的真实布局（非真实 Chrome 缩放；Codex 持有真实缩放证据，此处仅作补充）。

## Risks, Gaps, And Verification Needs

- **R1（F1，建议阻断级）**：个例事件「打开证据」误导性定位。修复方案（供 Codex 裁决，取其一）：a) 最小诚实修复——链接文案改为「查看关联规则证据」并在落地页加「试用数据中多个事件共用同一示例定位」提示；b) 合同级修复——fixture 为每个事件主题生成独立 span 并加合同校验（与 I6 同类不变量）。验证：点击「阑尾切除术」应落到含手术摘录/页码的证据或明确声明无独立定位。
- **R2（F2）**：冲突两侧不可区分。建议至少补录入条目/时间/录入人之一以区分同页两条记录；若受合成数据限制，列入 Phase 2 并保留现状的诚实说明。验证：冲突卡两侧存在可区分字段。
- **R3（B4 残余，低）**：裸导航静默恢复上次受试者，无任何「已恢复上次查看的 UAT-02」提示。建议加一行轻提示；不阻断。
- **R4（F3）**：风险卡缺时间。建议风险卡带「相关资料时间/时间窗」字段；不阻断。
- **Phase 2-8 未实施项（不误判为回归）**：真实方案解析、OCR/页图坐标高亮、逐事件真实回源摘录、模型逐条审核、持久任务、报告文件生成——均未宣称已验证。
- **对 Codex 的界定问题**（影响 F1 定级）：fixture 合同中"每 episode 单一共享 span"是 Phase 1 有意边界还是映射疏漏？若是有意边界，采用修复方案 a 即可放行；若是疏漏，建议本轮内做 a 的文案降级再放行。安全 provisional path：按"文案降级"处理，工作量小且不碰数据合同。

## Recommended Next Step

**独立意见：暂不开门，修复 F1 文案/提示级降级后放行 Phase 2（预计小改动）；F2 记入 Phase 2 合同，R3/R4 记入后续优化。**

理由：B1–B5 与 I1–I8 全部复验通过，信息架构、父子逻辑、例外语义、分类计数、溯源提醒、空态诚实、窄屏/缩放布局与中文原生表达均达到本轮验收合同；唯一触及产品核心承诺（证据回源诚实性）的新缺陷是 F1——它不需要等 Phase 2 的真实逐事件定位能力，仅把链接承诺降到与实际能力一致即可消除误导。若 Codex 确认 F1 属有意合同边界并接受方案 a，则本轮复测即可关闭，Phase 2 可开。
