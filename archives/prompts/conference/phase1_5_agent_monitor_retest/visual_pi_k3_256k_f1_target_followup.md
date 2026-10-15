Active task: `.trellis/tasks/08-13-phase1-5-agent-monitor-uat`

继续使用上一轮同一会话、同一资深中文医学监查员角色。Codex 已修复你指出的 F1 残余：Patient Profile 的链接现在必须把事件对应的规则组件与证据片段属主配成同一审核子项。请只在真实浏览器 `http://127.0.0.1:4173/` 复验这一处，不展开全站测试，不读取或修改源码。

Hard boundaries:

- 只读浏览器试用，不修改文件、页面数据或源代码。
- Work only inside the current workspace.
- Runner-managed output path: `runs/conference/phase1_5_agent_monitor_retest/visual_pi_k3_256k_f1_target_followup.md`. Never write this path with tools; return the complete report and let the runner persist it.

Read these files only:

- `AGENTS.md`
- `.trellis/tasks/08-13-phase1-5-agent-monitor-uat/prd.md`

请验证：

1. 打开 UAT-03 筛选期受试者资料页。
2. 在风险视图点击“资料缺口与冲突待处理”的“查看判断依据”。
3. 核对地址中的 `component` 与实际选中的规则子项一致，并确认落点为 `EX-01a 实验室异常与研究者风险的复合条件`，不再出现地址请求 IN-01、页面却静默打开 EX-01a 的不一致。
4. 桌面和 390px 窄屏各验证一次；窄屏必要时切到“规则”标签确认选中项。

返回精简报告：实际操作、可复核观察、该残余是否关闭、是否仍有阻断 Phase 2 的同类问题。区分观察事实与建议，不重复前两轮报告。
