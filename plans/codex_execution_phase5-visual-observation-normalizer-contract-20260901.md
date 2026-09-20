# Codex Execution Plan: phase5-visual-observation-normalizer-contract-20260901

Objective: 建立选择性视觉观察进入事实规范化候选输入的最小通用合同：观察只能作为来源绑定的补充候选或OCR风险提示，不覆盖OCR，不直接发布临床事实或入排结论；保持D001暂停且不引入项目特异规则。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审阅事实规范化输入规划、选择性视觉观察仓储与发布门禁，提出最小数据合同、身份闭包、失败边界和无需接线的反例；不得修改文件。 | `runs/execution/phase5-visual-observation-normalizer-contract-20260901/worker_01.md` |
| `worker_02` | 作为唯一代码写者，按既有模式实现最小来源保真接线和聚焦测试；优先复用合同与仓储，不新增项目特异词表，不改变OCR原文或直接发布事实。 | `runs/execution/phase5-visual-observation-normalizer-contract-20260901/worker_02.md` |
| `worker_03` | 只读独立攻击写者产物，验证观察缺失/关闭/来源错配/OCR漂移/旧修订/重复观察/提示注入不会形成事实候选或污染原文；不得修改文件。 | `runs/execution/phase5-visual-observation-normalizer-contract-20260901/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
