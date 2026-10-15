# Codex Main-Venue Plan: phase5-slice61an-p804-source-closure-final-independent-review-20260828

Date: 2026-08-28
Objective: 独立审查 p804 同源来源闭包修订合同的最终共享实现与证据边界：重点挑战来源闭包和原子 span 的互斥归一化、控制级候选闭包起点恢复、闭包外冻结、来源全集守恒、测试是否覆盖真实 runner，以及执行包审计是否正确锚定创建时路线；确认不能将工程合同可用误写为真实 v8 p804 临床通过，并判断是否具备由 Codex 决定一次新不可变语义重跑的前置条件。只读，不修改代码或临床工件，不运行模型回放，不发布控制点。

## Task Decomposition

1. Inspect the final repair-scope implementation and runner path.
2. Challenge source-closure authority, control-level seed recovery, and mixed-issue isolation.
3. Add shared deterministic regressions for every confirmed escape path.
4. Re-run focused and full product-code suites.
5. Obtain independent final-code acceptance without running a clinical replay.

## Source Packet

- Shared deconstructor and repair-error modules.
- Real-runner contract tests for candidate repartition and source closure.
- Immutable v8 failure evidence as a regression anchor, not as an accepted result.
- Guard-generated conference packet and all four same-session outputs.

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `general_single_object` | `codebuddy-cli` | `deepseek-v4-flash` | `runs/conference/phase5-slice61an-p804-source-closure-final-independent-review-20260828/general_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

- Completed in one resumable CodeBuddy session in 822.145 seconds.
- Four rounds: 437.904s / 126.028s / 169.668s / 88.545s.
- No timeout, fallback, replacement session, or late output.

## Codex Verification Checklist

- [x] Exact spanning candidate fails closed before a second model call.
- [x] Control-level issue can seed the intended candidate closure.
- [x] Mixed repair classes cannot widen candidate, source-unit, span, or disposition authority.
- [x] Ordinary repartition remains transitive and conservation checks remain active.
- [x] Focused suite passed: 47 tests.
- [x] Full product-code suite passed: 1007 tests, 58 warnings.
- [x] Compilation and diff checks passed.
- [x] Independent reviewer accepted the final code.
- [ ] New immutable clinical replay intentionally deferred.
