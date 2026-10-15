# Codex Execution Plan: r3-reader-format-repair-20260909

Objective: 产品读页格式失败的有界原模型纠正

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 当前GLM low与Gemini3.7 high产品真实24页初次6页失败，一次正式只重读失败页后仍有2页格式失败。通用原因：region对象误放location/context/raw_text额外字段；has_eligibility_value=false却含facts；模型复制整个输入模板；未知clause_id；invalid JSON。不能删字段、覆盖价值标记、猜条款、改数值来凑通过。请仅修改app/llm页读模块与tests/v2/llm及必要版本消费者测试，实现每次read_page对schema/invalid_json失败最多一次格式纠正调用：同模型、同原图、同ClausePack、同完整原提示，加入明确校验错误与上一回答作不可信输出参考，要求重新返回完整合同并重新读原件，不得向另一模型泄露回答。纠正属于产品提示框架，版本化；length/429/取消既有边界不变，所有请求/响应沿用当前recorded_completion持久化，每次模型真正调用可核查，不运行真实模型。避免巨型函数继续扩张，优先新独立模块抽取格式校验/修复封装，Ponytail最小完整改动。不要吞掉校验失败或放宽schema；第二次仍错误仍显式失败。硬来源或临床矛盾不准用格式纠正解决，日期/数值歧义不自动改写。检验value标记矛盾可要求原模型重新读页后选择一致输出，代码不自行选择。无权修改.env/docs/plans/scripts/DB/artifacts或个人配置，不网络不递归派发。可读当前harness/合同/执行器的记录边界，合成测试须涵盖成功、两次失败上限、两读隔离、错误信息不含凭据、取消、429、未知条款、先失败后正确与记录调用次数。保留最新Gemini OAuth/transport主线程修改，不改OAuth文件。不宣称真实临床验收完成。 | `runs/execution/r3-reader-format-repair-20260909/worker_01.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
