# Conference Participant Output: phase5-slice57-remediation-final-visual-latest - visual_pi_k3_256k

## Boundary Check

- 仅在工作目录内读取：`frontend/e2e/screenshots/` 六张截图、`frontend/e2e/profile-correction.spec.ts`、`profile-evidence-screenshots.spec.ts`、`profile-evidence-fixtures.ts`、`frontend/src/components/profile/` 四个组件、`frontend/src/pages/SubjectsPage.tsx`、`frontend/src/styles/profile.css`、`patientProfileFixtures.ts`。未读生产路径，未改任何文件。
- 六张截图全部以原始尺寸检查（1920×1080 / 2560×1440 / 3840×2160），两种状态（概览、证据面板）均覆盖——满足通过裁决的前提。
- 一处自纠：首轮并行读图时 4K 两图的内容归属看似颠倒，我用像素级核验（裁剪红框预期区域计数深红像素：`4k evidence-panel` 区域命中 2056 px、`4k two-column` 为 0；2K 同理 660/0）确认**文件名与内容一致**，不作为缺陷上报。建议 Codex 按自己的 checklist 用本地查看器独立复核一次。

## Independent Work Product

以懒惰但专业的医学监查员视角：我要的是"一眼可信、错了能追、改完能回"。逐项结论如下。

### 确认通过（观测证据，非推断）

1. **草稿保留**：e2e 断言查看原文后理由、修改前/拟修改预览、影响范围仍在（spec:251-261）；代码上 `evidenceOpen` 时 dialog 仅 `visibility:hidden` 保持挂载、Escape 被禁用（`ProfileFactCorrectionDialog.tsx:655-668, 838-846`）。合格。
2. **历史不可变语义（无版本混用）**：历史按 `profileRevisionId` 精确加载修订生成的档案，**明确拒绝回退最新版**（`ProfileCorrectionHistory.tsx:59-63` 注释 + "已拒绝使用当前档案回退显示"）；文案"本次修订形成档案第 3 版"、修改前/后快照并列；历史里"查看原文"传入的是历史 model——证据面板锚定的是修订生成的档案版本，不是当前版。这正是防混用的正确做法。
3. **红框唯一性与诚实性**：`isRealBboxLocator` 要求 precision=bbox + authenticated + bbox + coordinateFrame 四者齐备才画框，页内摘录/仅页码只导航不合成坐标；截图中每页仅一个框；定位与处理修订页面不一致时停止精确定位并 alert（`ProfileEvidencePanel.tsx:202-208`）。
4. **中文原生性**：文案通顺、临床语气得体（"分区暂无记录不代表正常或否认…请以本审核节点的资料核对结果为准"、"肯定"极性、"原文区域/仅页码"分级）。无生硬机翻。
5. **三档宽度无页面级横向溢出**：`expectNoPageOverflow` + 目视确认；1080p 下证据面板打开后档案列压至约 470px 仍可读。

### 缺陷（按严重度）

**F1（中）提交后关闭窗口＝丢失进行中任务跟踪，且档案不会自动刷新。**
证据：`SubjectsPage.tsx:469-480`——`onClose` 直接置空 `correctionItem`，dialog 卸载，900ms 轮询 effect 随之停止；`handleCorrectionCompleted` 只在 dialog 内触发。排队/运行中点"先关闭"或 Escape（locked 状态下 Escape 仍可用）后：任务在服务端继续跑，但首屏档案与修订记录都不会刷新，页面上也**没有任何"有修订正在处理"的指示**。失败恢复文案"修改内容仍保留在当前窗口"只在窗口开着时成立。监查员关掉窗口去喝口茶，回来看到旧值 120/80，会以为修订没生效——这是误导性状态。
修复方向（决策点，见 Q1）：完成前拦截关闭并二次确认；或把 job 状态提升到页面级轮询 + 头部"修订处理中"徽标。
另注：轮询在 `failed_final`（非终态）下仍以 900ms 无限续跑直到卸载——资源小问题，顺带处理。

**F2（中低）定位摘录与红框内文字不逐字一致（fixture 层）。**
证据：`patientProfileFixtures.ts:54` excerpt="血压 120/80 mmHg"；合成原件被框行（`profile-evidence-fixtures.ts:256`）="**基线**血压 120/80 mmHg"。截图里"原始识别文字"引用缺少"基线"二字，与红框内容不符。UI 标着"原始识别文字"却不是框内文字的逐字引用——定位诚实性的视觉论证被自己削弱。注意：修订 spec 里 `GENERATED_EXCERPT="基线血压 130/85 mmHg"` 是含全句的，两处 fixture 标准不一。
修复：截图 fixture 摘录改为"基线血压 120/80 mmHg"（或收窄 bbox）；并由 Q2 确认后端契约。

**F3（低中）失败页恢复引导是死路。**
证据：三档证据面板截图第 2 页均显示"资料名称暂不可读取"、"这一页暂时无法显示原图／原始页面读取失败，请在后续恢复处理中重试。"——无按钮、无责任方、无预期时间；同时面板标题仍标"2 页连续查看"。监查员无处可点，"后续恢复处理"是别人的事还是我的事？
修复：失败页不计入"连续查看"计数或明确徽标化，并给出可操作动作（如跳任务中心/重新处理资料）。该失败页为 fixture 有意构造，但文案是产品文案。

**F4（低）4K/2K 概览视觉效率：全宽卡片 + 窄列内容。**
证据：3840×2160 概览中，事实详情行（事件时间/记录性质/记录项目/记录结果/原文定位）单列堆叠在卡片左侧约 640px 内，卡片右侧约 55–60% 为空白；"阿司匹林"的记录结果行已溢出首屏。`layout-contract.test.ts` 禁止页面级 max-width 是对的，但当前实现等于把宽度浪费在空白而非信息密度上。1080p 同样右侧约 40% 空置。
修复：宽屏下详情字段改两列网格（`profile.css` 已有 `repeat(auto-fit, minmax(12rem,1fr))` 模式可复用）。

**F5（低）头部元信息易混**："筛选期"出现两次（受试者徽章 + 元信息行）；"档案第 1 版／资料版本 1／生成时间／待核对 0 项"并列，两个版本号相邻无语义区分辅助。建议合并徽章或加注 tooltip。

**F6（琐碎）测试卫生**：`profile-correction.spec.ts` 末尾 `toHaveCount(0)` 断言原样重复两行。

### 对既定计划的挑战

- "Playwright 283 passed"不能替代视觉验收：截图采集 spec（`profile-evidence-screenshots.spec.ts`）只做 waitFor+截屏，**零视觉断言**；F4 这类信息密度问题测试永远抓不到。本次六图人眼检查是必要的，Codex 的独立复核也是必要的。
- "草稿保留"只验证了"看原文再回来"这一条路径；**关闭-重开路径**（F1）是同一可恢复性命题的另一半，现有测试未覆盖。

## Evidence And Assumptions

- 观测：六张截图逐张目视 + 红框区域像素核验（上述计数）；组件与 spec 按行号引用。
- 推断 [INFERENCE]：F1 中"服务端任务完成后档案不刷新"——代码上刷新只挂在 dialog 的 `onCompleted`，未实测排队态关窗的浏览器行为；需 Codex 按其 checklist 复跑确认。
- 假设：第 2 页读取失败为 fixture 有意构造（未逐行追 fixture 的页面装配）；截图 fixture 的 excerpt/bbox 关系不代表真实后端数据质量。
- 假设：1080p 下"− 100% +"缩放控件无前导标签属可接受密度，不单列缺陷。

## Risks, Gaps, And Verification Needs

给 Codex 的边界问题：

- **Q1（决策点，阻塞 F1 修复方向）**：修订任务排队/运行中，用户关闭窗口是"允许且后果自负"还是产品缺陷？若允许，页面是否需要"修订处理中"指示与完成后的自动刷新？
- **Q2（阻塞 F2 定级）**：后端契约是否保证 locator excerpt 逐字等于框内识别文字？若不保证（摘录可为节选），UI 是否需要"摘录为节选"标注以防监查员误信逐字引用？
- **Q3（F3 背景）**：证据页读取失败的真实恢复路径归谁（任务中心？重新处理资料？）？"请在后续恢复处理中重试"指向的具体入口是哪个？
- 验证需求：F1 需要一次真实浏览器复跑（提交→排队态→关窗→观察档案/历史/通知）；其余均已在本次 pass 内完成静态+视觉核验。

## Recommended Next Step

1. Codex 裁决 Q1：若认定 F1 为缺陷，优先做页面级 job 状态保留（改动集中在 `SubjectsPage.tsx` 挂载逻辑，不动 dialog 内部）。
2. 一行修复 F2 fixture 摘录（`patientProfileFixtures.ts:54`），并借机与后端确认 Q2 契约。
3. F3 文案补充可操作恢复入口；F4/F5 可降级为后续打磨项，不阻塞本切片验收。
4. Codex 按 checklist 用本地查看器独立复核六图（尤其 4K 两图），然后做最终验收。

除 F1（待 Q1 裁决）外，其余各项均有确切证据与低风险修复路径；本切片核心契约——草稿保留、历史不可变、红框诚实、中文原生——经独立核验成立。
