# Codex Main-Venue Plan: rv1006-native-table-consumer-review-20261008

Date: 2026-10-08 UTC / 2026-10-09 CST
Objective: 独立审阅表格原生位置进入来源核对及候选整行出处装配：是否越过原子出处、语义、作用域与历史复用边界，仅工程审阅，不作临床采用

## Task Decomposition

所有者直接集成两个相连首错：review原生位置传递、候选整行出处规范化。一个C03只读挑战作用域/采用/历史，排序修后同会话复核，不新增框架或临床读道。

## Source Packet

源码基e628d4f0＋prompt列明的局部源码/测试补丁；只读允许范围见prompts/conference/rv1006-native-table-consumer-review-20261008。不提供临床原答/DB/环境。实际e628运行与补丁后结果分开，不把前者归到后者。

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `codebuddy-cli` | `deepseek-v4.1-flash` | `runs/conference/rv1006-native-table-consumer-review-20261008/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

首审194.256秒、续86.082秒、同会话01a11c53…，均returncode0/no fallback。每次7200秒完成等待主线程静默。第二轮只挑战排序/validator-only取舍/当前门重验，不重复生产或更换模型意见。

## Codex Verification Checklist

排序危险反例、原子/输入冻结、幂等及domain消费；当前门重验；18普通历史wire重新编译相等、1受限重推相等；预检无模型/无写、19/2/69；原件和历史不变。剩余完整采用及真实病例仍未达，claims_complete=false。
