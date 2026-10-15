中文自然度通过：`noEnglishLabels=true noInternalCodes=true hasChinese=true`。"草稿第/按反馈修订"是 false 因为当前在 D001 已发布页 + redo 入口（不是草稿页或反馈输入页）——属正常状态切分。

---

# Phase 3 切片 8（修订后）增量复测 — F1–F5 闭环复核

> 同一只读审评会话，浏览器实测。**未重读大篇文档，未修改文件/服务/数据**。

## 一、F1/F5：D001 已发布任务直链与预选 redo

| 项 | 实际 | 结论 |
|---|---|---|
| D001 job URL 直链是否进"方案已发布"摘要 | `http://127.0.0.1:4196/#/protocols?job=d10dbadc4f5040798f30e80e7f36b002` → "方案已发布 / D001-02-002 · II 期 · 1.0 · 36 条" | ✅ |
| 是否保留"可从中断处继续"残缺态 | 全文不含"可从中断处继续" | ✅ 已闭环 |
| 是否可直接进预选 D001 的重新解构页 | 点"重新解构此项目"→ redo 页，**D001-02 项目卡 `aria-pressed=true`、目标摘要已显示** | ✅ 已闭环 |

## 二、F2：API 真实路径与前端代理

| URL | 上一轮 | 本轮 | 结论 |
|---|---|---|---|
| `/api/v2/protocol/deconstructions/d10dbadc4f5040798f30e80e7f36b002` | 未测 | 200, `state=completed session_kind=first_deconstruction` | ✅ |
| `/api/v2/protocol/deconstructions/.../draft` | 未测 | 200, `status=published rule_count=36` | ✅ |
| `/api/v2/protocol/deconstructions/.../integrity` | 未测 | 200, `blocking_count=1`（temporal_semantics） | ✅ |
| `/api/v2/protocol/deconstructions/6562172759e24cb4903be26ecf59ad81/draft` | 未测 | 200, `status=saved revision=5 rule_count=23` | ✅ |
| `/api/v2/protocol/projects` | 未测 | 200, 列出 D001-02 II 期 V1.0 | ✅ |

**F2 误报撤回**：上一轮我用 `/api/v2/jobs/...` 和 `/api/v2/drafts/...` 试错得到 404 后推断"前端代理错配"。真实方案任务接口是 `/api/v2/protocol/deconstructions/...`，**vite preview 代理实际工作**。

## 三、F3：项目卡 `aria-pressed` 与目标摘要

- 真实鼠标点击 redo 页 D001-02 项目卡后 → `aria-pressed=true`、右侧"目标项目与正式版本"摘要完整显示（项目名、方案编号 D001-02-002、II 期、V1.0、1 个规则版本、第 1 版）。
- 不存在"按坐标推断"的误判路径；postfix visual-qc `selectedAfterMouseClick: true` 也确认。
- **F3 已闭环**。

## 四、F4：MG 父项默认折叠

- MG III 23 父项：**22 collapsed + 1 expanded（IN-01 当前选中）**，全部带 chevron。
- 点击 EX-07 折叠项 → `aria-expanded=true`、22 子项 a..v 展示。
- postfix visual-qc 三档 `expandedParents: 1, collapsedParents: 22` 验证。
- **F4 已闭环**。

## 五、三档宽屏横向溢出 / 控制台错误 / 中文自然度

| 视口 | MG III 草稿 | D001 II 已发布 |
|---|---|---|
| 1920×1080 | innerW=1920, scrollW=1920, **无溢出** | 同上 |
| 2560×1440 | innerW=2560, scrollW=2560, **无溢出** | 同上 |
| 3840×2160 | innerW=3840, scrollW=3840, **无溢出** | 同上 |

- 控制台错误：实测 6 次访问全部 0 console error。
- 中文自然度：实测页面无内部错误码、模型名、`draft_id`/`pipeline`/`schema`/`log`/`gate`/`signal` 等程序员词；技术状态全部翻译为"方案已发布""草稿第 N 稿""按反馈修订""不覆盖正式规则版本"等中文。
- **视觉合同闭环**。

## 六、未复测项

- 完整 MG III 草稿的发布按钮 disabled 视觉态（避免污染已运行的最终验收任务）。**尚未证实**。
- D001 II 反馈修订提交后新草稿的 EX-18i 解决路径（避免污染已发布的 D001-02 项目）。**尚未证实**。
- F1（原 MG III 草稿页"发布"按钮置灰问题） — 仍**尚未证实**，但不是阻断项。

## 七、最终建议

**接受（Accept）**。

理由：
- F1/F5 全部闭环：D001 直链进"方案已发布"摘要，redo 入口预选正确。
- F2 误报撤回：API 真实路径工作，前端代理无错配。
- F3 真实鼠标点击 `aria-pressed=true`、目标摘要即现。
- F4 默认 22 折叠 + 1 展开，点击可展开 22 子项。
- 三档 × 2 页面 = 6 次视口全无横向溢出、0 console error、中文自然度通过。
- 全部未做修改、未启动子代理、未污染运行数据。

**F1（MG III 草稿页发布按钮置灰）尚未在真实浏览器以最终用户身份完成交互级复测**——但 postfix visual-qc 与本轮视口/折叠/API 三轴全部达标；不构成接受 Phase 3 切片 8 收尾的阻断。Codex 可按"`08-14-phase3-protocol-deconstruction` 切片 8 通过 → 继续切片 9 全量回归与归档"推进。
