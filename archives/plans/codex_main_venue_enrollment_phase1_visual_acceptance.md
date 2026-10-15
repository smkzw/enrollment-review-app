# Codex Main-Venue Plan: enrollment_phase1_visual_acceptance

Date: 2026-08-13
Objective: 独立审查 Phase 1 入排审核前端壳的中文医学监查用户体验、信息架构、响应式、证据可达与视觉完成度，给出接受或阻断结论

## Task Decomposition

1. 校验会商合同、路由和只读边界，并对 Kimi K3 主路由做一次连通性检查。
2. 独立评审者读取设计合同、真实前端源码和现有截图，必要时操作本地前端，形成带复现证据的接受/阻断意见。
3. Codex 对评审意见逐项复核；阻断项先修订并重新执行自动化和真实浏览器检查，非阻断项进入 Phase 1.5 观察清单。
4. 通过后冻结 Phase 1 验收证据、清理可再生缓存并停在 Phase 1.5 用户硬门槛。

## Source Packet

- 架构与阶段事实源：`docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`、`plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`。
- Phase 1 产品合同：`.trellis/tasks/08-13-phase1-frontend-shell/prd.md`、`.trellis/tasks/08-13-phase1-frontend-shell/design.md`。
- 实际产品壳：`frontend/src/`，自动化入口：`frontend/e2e/` 下的分层规格文件。
- 渲染证据：`frontend/e2e/screenshots/`；可操作地址：`http://127.0.0.1:4173/`。
- 不向评审者提供构建者私有推理或其他评审输出。

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `visual_pi_k3_256k` | `kimi-code` | `k3-256k` | `runs/conference/enrollment_phase1_visual_acceptance/visual_pi_k3_256k.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

- 首次派发前运行主路由连通性检查；连通性诊断不替代真实会商。
- 真实会商使用 120 分钟硬等待，不因运行缓慢主动轮询或 fallback。
- 同一会话仅在输出不完整或有可执行缺口时继续；终态失败前不切换路由。
- 开始/结束时间、会话号、路由、终态和是否采纳记录到 metrics/review。

## Codex Verification Checklist

- [ ] 独立评审者未改写产品文件，未读取工作区外临床资料。
- [ ] 独立结论包含可复现证据和接受/阻断判断。
- [ ] Codex 对每个阻断项在真实页面或源码中复核。
- [ ] `npm test -- --run`、`npm run build`、`npm run e2e` 通过。
- [ ] Codex 重看桌面、窄屏、150%/200% 的最终截图，无页面横向溢出或遮挡。
- [ ] Phase 1 Trellis 状态、验收记录、阶段清理和 Phase 1.5 停止点已更新。
