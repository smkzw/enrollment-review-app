# Codex Execution Plan: phase5-slice59m-20260827

Objective: 打通其他方案控制Agent的MTPLX严格Schema传输，并对冻结D001 II期表5代表控制进行真实Agent回放与父级临床验收

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 实现独立的OpenAI兼容ProtocolControlAgentTransport，使用protocol_control_agent_response_format严格Schema、MTPLX medium和同会话修复历史 | `runs/execution/phase5-slice59m-20260827/worker_01.md` |
| `worker_02` | 为新传输和ProtocolControlAgentRunner补齐真实路径的配置、严格Schema、同会话、长度与错误回归，确保不复用官方IN/EX错误Schema | `runs/execution/phase5-slice59m-20260827/worker_02.md` |
| `worker_03` | 使用系统内置MTPLX独立Agent/harness对冻结D001 II期表5代表行进行真实小范围回放，保留原始wire哈希/修复/门禁证据并供Codex逐条临床QC | `runs/execution/phase5-slice59m-20260827/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

1. The control transport uses `protocol_control_agent_response_format()` with strict JSON Schema and never the official IN/EX schema.
2. Product MTPLX identity is exact, reasoning is medium, temperature is zero, HTTP proxy inheritance is disabled, output budget follows existing MTPLX configuration, and repair calls retain one immutable local message history/session ID.
3. Transport and runner regressions prove schema selection, exact route, history restoration/continuation, bounded error behavior, and no silent semantic-model fallback.
4. The live D001 replay is produced by the product `ProtocolControlAgentRunner` plus the new MTPLX transport. Artifacts retain input/protocol hashes, request identity, attempt outcomes, raw-output hashes, hydrated wire and publication-gate results.
5. Codex independently checks first-dose anchors, longer-of selection, 24-month default plus clearance-activated 6-month substitute, and the local herbal exception against the frozen source excerpts. Missing or incorrect Agent output is diagnosed and repaired at the shared prompt/contract/gate layer before acceptance.
6. No broad run or user-facing visual test occurs in this backend slice; `claims_complete=false`.
