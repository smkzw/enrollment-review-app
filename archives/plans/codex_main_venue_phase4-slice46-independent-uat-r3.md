# Codex Main-Venue Plan: phase4-slice46-independent-uat-r3

Date: 2026-08-21
Objective: 在正式非试用构建上由指定三模型独立完成 Phase 4 清洁库端到端视觉试用，核查资料上传、识别核对、证据原件联动、版本生成启用、恢复和宽屏体验

## Task Decomposition

1. Codex 构建普通生产前端，并启动三组互相隔离的清洁后端与页面入口。
2. 三个指定模型分别以真实医学监查人员角色独立完成全流程试用和截图，不互读结果。
3. Codex 对照真实 API/数据库、原始截图和代码路径验证每项高优先级发现，剔除环境污染与绕过控件造成的假阳性。
4. 对共同根因作系统级修复并跑聚焦、全量、构建和真实浏览器回归；再由 fresh-context Trellis 检查者裁决。

## Source Packet

TODO

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `visual_pi_k3_256k` | `kimi-code` | `k3-256k` | `runs/conference/phase4-slice46-independent-uat-r3/visual_pi_k3_256k.md` |
| `codebuddy_hy3` | `codebuddy-cli` | `hy3` max | `runs/conference/phase4-slice46-independent-uat-r3/codebuddy_hy3.md` |
| `pi_minimax` | `cms-router` | `minimax-m3` | `runs/conference/phase4-slice46-independent-uat-r3/pi_minimax.md` |
| `grok_medium` | `grok-build` | `grok-4.6` medium | `runs/conference/phase4-slice46-independent-uat-r3/grok_medium.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

TODO: Record start/end time, pending/failed/incorporated status, retry reason, and whether late outputs were used.

## Codex Verification Checklist

- [ ] 三组端口均为普通构建，真实目录与 API 对象一致。
- [ ] 三个指定模型、provider、effort 和 session 有运行记录，无静默 fallback。
- [ ] 每份报告包含真实截图、完整操作路径、量化结果和接受裁决。
- [ ] 所有阻断/高问题由 Codex 独立复现或以数据库/API/截图证伪。
- [ ] 修复后聚焦测试、全量测试、前端构建、Ruff、diff-check 和三档宽屏真实浏览器通过。
