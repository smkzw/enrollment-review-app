# 定向修订结果的独立复核

沿用既有只读 evidence_single_object 角色。只读本 worktree；不改文件、不启动模型服务、不读取工作区外临床资料、不递归派发。请先基于下述冻结输出和代码独立核对，不沿用上一轮结论。工程会商并不代替产品内模型。

来源：artifacts/qwen-three-platform-20260909-v3/diagnostic-formal-bounded-omlx-medium-protocol-d001/measurements/response-3.json；对应离线库中 job bc103cde5e7546f6b3e593fee9b707b4 的 source_input，原文 body.p644。可读 scripts/qwen_semantic_repair_diagnostic.py 的 frozen_input 以只读模式核验来源。禁止写数据库或恢复旧作业。

本轮结果：artifacts/qwen-three-platform-20260909-v3/formal-targeted-repair-live-01/{prepared-request.json,request-0.json,response-0.json,receipts.json,status.json}。实际 omlx/Jundot__Qwen3.8-Flash-Next-oQ4e-mtp:medium，max_tokens=131072，自然 stop，238.516 秒，6517 输出 token。之前 request-3 实际8192，不可作为128K标准横评。新代码复用产品正式 repair prompt + transport，单条 EX-04，恢复冻结原文；不含金标答案。

请核验：
1. 当前结果的原文范围、严重病史与括号示例的关系、频次结构、来源绑定，以及相对原输出的真实改进/退化。不要仅凭含数字或 JSON 合法判通过。
2. frequency gate 在 app/protocols/deconstruction_gate.py:_predicate_preserves_frequency 中要求 exact_source_clauses 和 source_term/attribute 绑定。本轮模型已填 occurrence_window，但未填 source_clause/source_term。诊断返回笼统 FREQUENCY_WINDOW_NOT_STRUCTURED 是否丢失真正修订方向？提出最小通用修改，不能写疾病或具体阈值硬编码。
3. 核验 scripts/qwen_semantic_repair_diagnostic.py 新 formal 分支是否忠实于产品，不把单条重新构造等同于完整批次续修验收。指出任何证据局限。
4. 建议下一项离线/单条测试；不要建议立即整份重跑。仅给来源明确的发现及优先级。不自行改代码。
