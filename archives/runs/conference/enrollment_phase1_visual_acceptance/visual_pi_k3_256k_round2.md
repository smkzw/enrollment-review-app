# Conference Participant Output: enrollment_phase1_visual_acceptance - visual_pi_k3_256k (Round 2 复核）

**结论：`接受进入 Phase 1.5`** — 首轮阻断项 B1 已按真实数据契约关闭并经代码+真实浏览器双重验证；8 项复核中 6 项完全关闭、2 项大部分关闭但各有一个残余，均为"重要但不阻断"。**特别警告：Codex 提供的"153 项 Playwright 通过"中，全页面缩放断言为假阳性通过（测试在页面加载完成前测量），请勿将该数字作为缩放覆盖的证据。**

## Boundary Check

- 仅只读复核：未修改源码、测试、截图、任务记录；未读工作区外临床资料；未做安全测试；未读其他参与者输出。
- 读取范围：首轮报告、`wire.ts`/`mappers.ts`/`viewModels.ts`/`TodayPage.tsx`/`WorkbenchPage.tsx`/`RuleTree.tsx`/`ExpressionView.tsx`（含 `ExpectationCoverage.tsx`、`profile.css` 定位溢出根因）、`frontend/e2e/` 规格与重生成截图。
- 独立验证：`http://127.0.0.1:4173/`（实为 Vite dev server，服务当前源码）在 1440/390 视口真实点击；Playwright 全新上下文临时脚本（写 /tmp，未触碰仓库）复核缩放；隔离运行单条缩放 e2e（`--output=/tmp`，未改写仓库测试产物）。

## Independent Work Product

### 首轮阻断项

**B1 `时间窗：undefined undefined undefined 天` — 已关闭（代码+实测双证）**

- 代码：`mappers.ts` 新增 `formatTimeConstraint`，按 wire 真实结构（`anchor_type/direction/lower_bound_days/upper_bound_days/half_life_multiplier/allow_partial_date`）建模；`anchorLabel` 全枚举中文锚点（签署知情同意/筛选/基线/随机/事件发生），边界组合（仅下界/上下界相等/仅半衰期/on）均有中文输出，无插值裸字段。
- 实测：1440 视口 EX-01a 判断区显示"用药·禁用用药暴露为 等于 是，时间窗：随机前 28 天内"；390 窄屏判断标签页同样显示；全 9 页渲染文本扫描无 `undefined`/`null`。被吞掉的"28 天"临床信息已回到界面。

### 本轮 8 项复核逐项结论

| # | 项 | 结论 | 我实际核查的证据 |
|---|---|---|---|
| 1 | 时间约束中文建模 | **已关闭** | 上；另测 `例外条件` 与 `不满足以下条件` 层级渲染正常 |
| 2 | 单位中文化 | **已关闭** | 实测 IN-01 显示"人口学·年龄（岁） 大于等于 18"（单位去重，无 year）；EX-01a 显示"大于等于 1.5 倍正常上限"；全 9 页扫描无 `year`/`xULN`。遗留微瑕（不阻断）：属性名"…的倍数"与值"倍正常上限"语义略重复，可读 |
| 3 | 今日事项带规则编号+直达 | **已关闭** | 今日 6 张卡均显示"关联规则：IN-01 / EX-01a / EX-02a / 必做-01a · 缺口 · 责任方"，卡片可区分；实测点击"来源存在冲突"卡 → **1 次操作**落地 EX-01a 自动选中且证据卡（合成筛选资料.pdf·第 4 页·仅页码·降级原因·来源方）同屏可见，≤3 合同稳固成立 |
| 4 | 文件名去实现标签 | **已关闭** | `mappers.ts:266 displayFixtureFileName` 剥离 `-clear/-barrier/-gap_conflict`，单测 `mappers.test.ts:132` 断言"合成筛选资料.pdf"；实测证据卡/弹窗显示净名，全 9 页扫描无 clear/gap_conflict。fixture wire 原名保留（冻结合同，边界正确） |
| 5 | 父规则状态汇总 | **已关闭** | 规则树实测：IN-01"子项需处理"、EX-01"子项有冲突"、EX-02~04"子项需处理"；aria-label 含"共 N 个子项，子项有冲突，已折叠"；父子缩进层级保持（截图与 DOM 双证） |
| 6 | 默认落点风险优先 | **已关闭** | 裸 `#/workbench` 实测落在 UAT-02·筛选期·**明确障碍**（首轮为 UAT-01 无风险）；`mapEpisodeSummary.focusComponentId` 按 冲突→阻断→需处理 优先级选组件 |
| 7 | 全页面 150%/200% 缩放 | **仍存在（重要但不阻断）+ 测试假阳性** | 详见下方 R1 |
| 8 | REQ- 不得出现在界面 | **仍存在残余（重要但不阻断）** | 详见下方 R2 |

### 残余问题（均非后续阶段功能缺失，均为本壳内小修）

**R1（重要但不阻断）缩放验证为假阳性通过 + 代理缩放下受试者页仍溢出 58px**

- 事实链：① `desktop-routes.spec.ts:76` 的缩放测试用 `openRoute`（`page.goto('/#/subjects')` 为同文档 hash 跳转）+ `waitForLoadState('networkidle')`，hash 跳转时 networkidle 立即返回，随后 `setZoom` 仅等 120ms 即断言——我用 Playwright 全新上下文逐字节复现：断言时刻页面处于"正在整理资料"加载态（diff=0）；② 等页面真正加载完成后，受试者与资料页在 CSS-zoom=2 下 `scrollWidth=1498 > 1440`（3 次全新上下文均复现，溢出点为 `.expectation-cover__gap/__note` 所在网格，尽管 `overflow-wrap:anywhere` 已在源码中）；③ 原生缩放等效视口（720px）实测无溢出——真实浏览器缩放用户不受影响。
- 影响：用户风险低（仅影响 CSS-zoom 代理场景）；但**验收证据失真**——"153 项通过"不能证明 9 页缩放合规。
- 修复：a) 缩放测试断言前等待页面就绪锚点（如各页 `key` 文本可见）；b) 受试者页 `.expectation-cover__row` 网格在 CSS-zoom 下的轨道塌陷（实测 `gridTemplateColumns: 72px 0px 2px`）需防御性修复。

**R2（重要但不阻断）REQ- 在方案差异两处仍可见**

- 实测：今日工作·近期变化"方案删除条件 **REQ-02**"；方案工作台·规则差异"删除 **REQ-02**"（全 9 页仅此 2 处）。根因：protocol diff 映射（`mappers.ts` 新增/删除/变化标题）未走 `displayRuleCode`，一行修复。
- 影响：监查员在信息性差异区看到无意义内部代号；不在核心审核链路。注意今日工作是默认首屏候选之一，建议进 Phase 1.5 用户试用前顺手关闭。

### 抽查确认无回归

- 390 窄屏：今日/受试者/工作台均无页面级横滚；工作台判断标签显示完整时间窗；证据 1 次直达仍成立。
- 重生成截图：desktop-1440-today（卡片含关联规则，信息分层清晰）、desktop-1440-workbench-zoom200（标签模式、父级汇总徽标、无重叠无错误断行）。
- 诚实性无回退：界面试用标记、报告"不会生成文件"、任务演示"不会实际运行文字识别或审核"均在。

## Evidence And Assumptions

- 证据：每项结论标注了实测路径；关键实测输出——EX-01a 判断区文本、今日卡片链接 href（均带 `component=`）、全新 Playwright 上下文三连测 `sw=1498`、断言时刻 `state:"loading"`、全 9 页 REQ/year/xULN/undefined 扫描表。
- [INFERENCE]：R1 中"真实用户不受影响"基于"浏览器原生缩放=布局视口收缩"的标准行为推断，已用 720/960px 视口代理验证。
- 假设：450px 高度等极端视口未测；Codex 声称的 137 项单测与构建通过未亲自重跑（只读边界内运行了单条 e2e 缩放测试验证真假）。

## Risks, Gaps, And Verification Needs

- **最高风险不是界面缺陷，而是验收证据可信度**：R1 证明当前缩放 e2e 可以在页面未加载时通过。若同类"networkidle+短等待"模式存在于其他 e2e 断言，"153 通过"的整体证明力需 Codex 复核（我仅确证缩放用例；路由可达性用例用 `expect(...).toBeVisible()` 轮询，不受影响）。
- **给 Codex 的有界提问**：R2 的 REQ-02 残余是否构成你验收清单上的硬门槛？若否，建议作为 Phase 1.5 前最后一轮文案清扫的一部分（连同"倍数/倍正常上限"去重），无需单独阻断。
- 建议（非要求）：为"渲染文本不含 undefined/null/REQ-"加一条跨页全局 e2e 断言，把本轮两类语言缺陷永久关进测试。

## Recommended Next Step

1. Codex 复核 R1 测试假阳性（`desktop-routes.spec.ts:76` + `helpers.ts setZoom`）；接受我提供的复现脚本结论或自行用全新上下文重测受试者页 200%。
2. 一行修复 R2（diff 标题过 `displayRuleCode`），并把缩放断言前加页面就绪等待。
3. 两项均为分钟级修复，可在 Phase 1.5 启动前顺手关闭，不需要再开一轮完整会商；若 Codex 认为 R2 属硬门槛，修复后可由本会话快速复核确认。

**最终意见：`接受进入 Phase 1.5`** — 首轮阻断已真实关闭，壳已满足中文资深医学监查员的首屏风险识别、明确下一步、证据可追溯与父子规则层级需求；R1/R2 为重要但不阻断的残余，建议在用户试用前关闭但不构成门槛。
