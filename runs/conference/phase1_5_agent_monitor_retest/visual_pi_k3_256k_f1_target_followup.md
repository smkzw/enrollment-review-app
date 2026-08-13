# Conference Participant Output: phase1_5_agent_monitor_retest - visual_pi_k3_256k (F1 target follow-up)

## 边界核对

同会话、同资深中文医学监查员角色。仅真实浏览器只读操作 `http://127.0.0.1:4173/`（1280×800 与 390×844），未读源码、未改任何文件或数据，未展开全站测试。`AGENTS.md` 与任务 PRD 于本会话起始已读，约束不变。未写 runner 报告路径；以下为完整返回。

## 实际操作与可复核观察

**桌面 1280px [已观察]**
1. 打开 `#/subjects?subject=subject-uat-03-gap_conflict&stage=screening`。
2. 风险视图「资料缺口与冲突待处理」卡的链接 href 现为 `#/workbench?episode=episode-uat-03-screening-gap_conflict&**component=component-ex-01**&evidence=span-uat-03-screening-gap-page`——component 已改为证据片段属主，与上轮 `component-in-01` 不同。
3. 点击「查看判断依据」后地址栏 hash 与卡片 href 完全一致；落点标题为「**EX-01a 实验室异常与研究者风险的复合条件**」与「EX-01a 证据与原始资料」，截图确认冲突来源并列区正常渲染。地址请求子项 == 实际选中子项，静默打开不一致子项的现象消失。

**窄屏 390×844 [已观察]**
4. 同一入口重复操作：落点 hash 同样为 `component=component-ex-01&evidence=span-…`；页面 `scrollWidth=390=innerWidth`，无页面级横向溢出。
5. 切到「规则」标签：EX-01a 按钮带 `rule-tree__component--selected` 类与 `aria-current="true"`，IN-01 无选中态——地址、URL 参数、规则树选中三者一致。截图可见 EX-01a 高亮选中。
6. 附带观察 [建议，非缺陷]：390px 下规则树子项名「实验室异常与研究者风险的复合条件」在窄列中折成约 5 行，可读但略显拥挤；不影响选中识别，不阻断，供后续视觉优化参考。

## 结论

- **F1 残余关闭 [已观察证据支持]**：链接 component 与 span 属主已配对为同一审核子项（EX-01a），桌面与 390px 两种布局下地址请求与实际选中一致，规则树选中态经 `aria-current` 复核确认。上轮「地址请求 IN-01、页面静默打开 EX-01a」的不一致不可复现。
- **是否仍有阻断 Phase 2 的同类问题**：本轮限定范围内**未发现**。F1 主问题与残余均已关闭；遗留项仅为 F2（冲突两侧来源区分度）、F3（风险卡时间信息）与上述窄屏折行建议，均属 Phase 2 合同或后续优化性质。
- **独立意见（综合三轮）**：**可进入 Phase 2** [建议，最终裁决权属 Codex]。
