# Phase 5.8d p804 来源闭包权限验收，语义重放暂缓

## 状态

- p804 同源来源闭包的有界修订权限工程合同已验收。
- D001 病毒学 v8 仍是不可变、已拒绝、未发布的反例。
- 本切片没有运行新的 LLM/VLM 重放，没有接受 p804 临床结果。
- Phase 5.8d 仍为 `in_progress`，`claims_complete=false`。

## 已完成

- 来源闭包重写要求候选来源单元的传递闭包全集完全包含于确定性问题授权的结构单元集；否则在下一次模型调用前失效关闭。
- 修订轮次由一种结构修订类型独占：来源闭包、普通候选重分区、原子/临床内容修订不再混合扩张权限。
- 控制级问题可通过 `originating_candidate_id` 恢复候选闭包起点。
- 已覆盖实际 Runner、跨单元候选、混合问题和错误消息保留。

## 验证证据

- 聚焦回归：`47 passed in 0.09s`。
- 最终产品代码完整回归：`1007 passed, 58 warnings in 131.53s`。
- 最后测试断言补强后聚焦回归：`47 passed in 0.09s`。
- Python 编译与 `git diff --check` 通过。
- 四轮同会话独立审查最终接受：822.145 秒，101 次工具调用，无 fallback。

## 文件指纹

- `app/agents/protocol_control_deconstructor.py`: `55735333bbce470c38068c18b7dab213a9bd4d9988d4b429c21543a15e0b78ff`
- `app/protocols/protocol_control_repair_errors.py`: `69f0d6c2dddb156681d21119820d075518a61c6dfd3ee0ffd84831bc3cfcbb47`
- `tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py`: `c113547fca9db2325d41df6f6e41e74a0e1002ea8b1560ed66ecf89bec8d398e`

## 下一安全动作

1. 把 p803-p805 重放路径固化为可重现、可提交的产品级 harness，不依赖临时脚本或人工矩阵。
2. 决定串行修订类的预算政策；v8 用了5次尝试，当前默认2次不足以支持多类问题串行修订。
3. 另行做一次新的不可变 p803-p805 重放 go/no-go；未批准前不调用模型。
4. 如重放，必须确认 p805 与基线字节一致，并由父级完成 p804 医学接受；技术通过不等于临床通过。
