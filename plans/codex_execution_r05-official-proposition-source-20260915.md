# Codex Execution Plan: r05-official-proposition-source-20260915

Objective: 为所有者接通官方谓词的受限原文命题消费，实施来源合同/生产端小单元；并非临床采信或独立测试。遵守本树指令、apply_patch、保留全部无关脏工作。用户禁止阶段测试，不写或运行测试、样例探针、import应用、DB/服务/模型/浏览器，不递归派发。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 仅允许修改 app/domain/contracts/rules.py、app/agents/protocol_deconstructor.py、app/protocols/deconstruction_gate.py、app/services/protocol_draft_service.py；其他文件只读。AtomicPredicate增可选semantic_proposition:str非空（旧None序列化省略，保留旧内容身份），显式表达需要来源含义核实的命题；只允许comparator=exists/value=None/unit=None、不与requires_professional_judgment混用（研究者仍走原专属链），不允许occurrence_window与该字段混用；允许prospective_period/prospective_window，未来命题不再伪造数值直接比较。不得从旧字段自动补命题。生产wire新增必填nullable字段，解析/草稿编辑白名单/持久化映射完整保存；系统提示说明语义原方向、与数字日期计算分离、按方案来源保留限定条件、不能把意愿当已履行；不硬编码项目疾病药物。研究者判断不改含义，复杂复查仍明确未核实，不借本字段跳过。更新当前wire版本与发布门版本使旧工件不能假冒新生产方法，历史读取保留；不要更改稳定系统ID种子。检查合法新产物从wire到RuleComponent来源校验及草稿编辑是否丢字段，门拒新生产缺字段/来源不闭合，但不要把机械substring当语义真实性。仅实现以上来源单元；消费者由所有者整合后统一审阅，不能宣布端到端完成。返回修改清单、明确静态未运行边界、相邻必改点。 | `runs/execution/r05-official-proposition-source-20260915/worker_01.md` |

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
