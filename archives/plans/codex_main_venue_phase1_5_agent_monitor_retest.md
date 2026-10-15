# Codex Main-Venue Plan: phase1_5_agent_monitor_retest

Date: 2026-08-14
Objective: 以资深中文临床试验医学监查员身份，在真实浏览器独立复验Phase 1.5修复后的入排审核工作台，深度检查风险分类、冲突证据、规则父子逻辑、Patient Profile、证据回源、中文交互、桌面与窄屏视觉，追查任何预期外结果并给出是否可进入Phase 2的独立意见

## Task Decomposition

1. 独立测试者先核对页面版本和无登录入口，自由浏览完整站点并形成自己的风险假设。
2. 在真实浏览器完成至少一条跨页证据往返，核查本轮修复的加和分类、冲突来源并列、父子逻辑、例外条件、期望覆盖、Profile 空状态和导航保护。
3. 检查桌面、窄屏或浏览器缩放下的首屏信息优先级、文字可读性、滚动负担与操作反馈。
4. 对预期外结果追查系统性原因，独立给出 Phase 2 放行意见；Codex 以自动化、真实缩放和源码/契约证据交叉验收。

## Source Packet

- 架构设计书与分阶段实施计划。
- Phase 1.5 Trellis 验收合同、设计补充与问题记录。
- 运行中的 `http://127.0.0.1:4173/` 界面试用版 1.5.2。
- 最终 Playwright、Vitest、pytest、启动器和真实 Chrome 缩放证据由 Codex 持有，不先灌输给参与者结论。

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `visual_pi_k3_256k` | `kimi-code` | `k3-256k` | `runs/conference/phase1_5_agent_monitor_retest/visual_pi_k3_256k.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

- 单次真实路由，最长等待 120 分钟；慢响应保持等待，不按固定间隔重派。
- 只有终态失败、空输出、截断或同会话恢复无进展时才进入声明的 fallback。
- 结束后在 metrics 中记录开始/结束时间、会话、实际路由、fallback 和是否采纳。

## Codex Verification Checklist

- 对参与者每个高优先级发现用实际页面、测试或源码重新核实，不以模型自信代替证据。
- 复核 1280/1440/1920/390 自动化结果及 100%/150%/200% 真实 Chrome 缩放。
- 复核前后端全量测试、启动器双跑和中文原生扫描。
- 若参与者发现新的真实阻断，先修复并复验，再决定 Phase 2；若仅为后续能力或偏好，写入后续阶段而不阻塞。
