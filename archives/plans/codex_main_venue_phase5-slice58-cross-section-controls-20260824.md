# Codex Main-Venue Plan: phase5-slice58-cross-section-controls-20260824

Date: 2026-08-24
Objective: 独立审查方案全文跨章节入排控制点的领域模型、冻结目录、Agent边界、来源闭包、发布门槛及Phase 5.8实施顺序；不得把会商角色当测试者，不得修改代码或读取工作区外临床资料。

## Task Decomposition

1. Codex 先核对现有合同与构建路径，确认 `required_procedures` 只来自研究流程表。
2. 两名参与者在新鲜、隔离上下文中分别完成整体审查，不读取对方输出，不改代码。
3. 核心裁决点：三类目录模型、候选发现与冻结分层、稳定身份、审核阶段、时间锚点、来源引用、跨目录重复/冲突、发布完整性。
4. Codex 对会商建议做证据对照，形成本 Phase 5.8 的增量实施分片；未经确定性测试与真实方案验收不算完成。
5. D001 II 与 MG-K10-SAR III 各从原始方案创建新隔离项目，逐项人工比对 IN/EX、流程必做项与跨章节控制点；此门槛通过后才可进入独立测试者试用。

## Source Packet

- 授权读取范围仅限当前工作树中 `context` 文件列明的设计、任务、合同、构建器和测试。
- 关键已知事实：`build_required_procedure_catalog()` 的正式输入为结构块、期别投影和来源片段；只遍历表格根，并要求访视型表头、操作行及 `X/(X)` 标记。
- 关键已知缺口：当前 `CatalogKind` 只有官方父规则与必做项目；无独立全文入排控制点对象。
- 会商不接触工作区外的 D001/MG 真实临床文件。

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `general_pi_qwen38` | `alibaba` | `qwen3.8-max` | `runs/conference/phase5-slice58-cross-section-controls-20260824/general_pi_qwen38.md` |
| `general_grok46` | `cursor-cli` | `auto` | `runs/conference/phase5-slice58-cross-section-controls-20260824/general_grok46.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

- 启动时间：待预检通过后记录。
- 每个角色等待至终态或 120 分钟硬等待返回；不因慢响应重复派发。
- 任何 fallback 必须由 runner 依终态失败规则触发，记录真实 provider/model/session；不由 Codex 静默替换。

## Codex Verification Checklist

- [ ] 两路提示词预检通过，角色与最新路由一致。
- [ ] 两名参与者终态输出均可审计，未修改工作树。
- [ ] 每项采纳建议都能映射到当前代码合同、用户新需求或明确反例；不以模型自信作为证据。
- [ ] 新模型不修改官方 IN/EX 编号和数量，不将额外控制点伪装为 EX/IN 子项。
- [ ] 全文候选发现不直接成为正式规则；必须有来源闭包、期别/节点归属和完整性校验。
- [ ] 冲突、重复、未命名时间锚点和与修订案/方案权威边界均有明确结构化处置。
- [ ] 实施后用 D001 II 与 MG-K10-SAR III 逐项人工核对，先证明内部 Agent 与门禁，再启动独立测试者。
