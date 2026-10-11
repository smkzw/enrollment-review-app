# Phase 5.8d 表5结构合同通过、真实 Agent 回放拒收

## 当前结论

- 共享 `TimeConstraint` 已显式表达“固定时间窗+半衰期取较长者”，不再靠文字推断。
- 条件性缩短已改为“例外条件分支 -> 替代义务组”的显式激活：默认24个月与清除剂条件成立后6个月均作用于同一触发分支，6个月时间窗在替代义务上，不在条件原子上。
- 父线程聚焦回归 `145 passed`，`git diff --check` 通过。
- 执行者建立的表5四行确定性回放只能证明合同可承载且门禁可拒绝错误结构，不能证明 Agent 能从原文生成这些结构。`structured_control_deconstruction_accepted=true` 未被 Codex 接受。

## 根因

`ProtocolControlAgentRunner` 只定义了 provider-neutral transport 协议，但当前没有使用 `protocol_control_agent_response_format()` 严格 Schema 的 OpenAI 兼容实现。既有 `DeepSeekProtocolAgentTransport` 服务于官方 IN/EX 解构，其响应 Schema 不同，不能静默复用。

## 已验证环境

- MTPLX 真实端点 `http://127.0.0.1:8002/v1/models` 可用。
- 精确模型 ID：`mtplx-qwen38-27b-optimized-quality`。
- 端点公布上下文长度 262144；本系统内置本地 LLM/VLM 不受执行/会商子 Agent 32K 限制。

## 下一安全动作

1. 在新的受控小切片中实现独立的 OpenAI 兼容 `ProtocolControlAgentTransport`，使用协议控制 wire 严格 Schema，不影响官方 IN/EX 运输。
2. 用冻结 D001 II 期表5同一代表范围真实调用 MTPLX medium，保留请求模型身份、原始 wire 哈希、同会话修复记录和门禁结果。
3. Codex 逐条对照表5原文验收较长者、24→6条件替代、中草药局部例外和首次给药锚点。
4. 不运行受试者、OCR、浏览器、独立视觉测试者或其余128个包；`claims_complete=false`。
