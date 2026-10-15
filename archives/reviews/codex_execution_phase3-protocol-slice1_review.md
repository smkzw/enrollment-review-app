# Codex Execution Review: phase3-protocol-slice1

## Verdict

`accept after revision`。执行者完成了结构基座，Codex 与独立审查随后发现并修复了
虚假精确页定位、源哈希分叉、可变工件、样式继承和 OOXML 静默漏提问题。

## Worker Outputs

- `worker_01`：契约、ORM 与 Alembic `0004`。
- `worker_02`：DOCX 结构提取、LibreOffice 渲染、来源对齐；同会话补修嵌套表格、页眉角色、编号、修订与来源摘录。
- `worker_03`：测试、真实方案探查、pdfplumber spike 与迁移 head；报告格式不完整，因此不以自述作为验收证据。
- 自动主路由两次遇到供应商周额度 `429`，按声明链回退到 CodeBuddy CLI / DeepSeek V4 Pro xhigh；未随意换路。

## Manager Assessment

实现范围与 Phase 2 基座一致，没有写回 legacy。执行产物可用，但最初把重复文本首个
命中当作精确定位、把源路径当作存储引用，不能直接验收。Codex 已从共享机制修复，
没有写入项目特异规则。

## Boundary Check

- 写入范围限定于 V2 方案登记、结构提取、来源对齐、迁移、测试和当前任务记录。
- 两份真实方案只读使用；未修改源方案、受试者资料、旧项目或既有临床报告。
- 执行者不能自行裁决完成；所有修复由 Codex 检查实际差异，并以真实方案回归和全仓测试验收。

## Hermes Workflow Record

任务通过 `hermes_workflow_guard.py` 初始化和记录。实际执行路由是声明链中的 Pi/OpenCode
Go 尝试及 CodeBuddy CLI 回退；Hermes 不是本轮执行模型，也没有模型输出被当作验收依据。
真实 `429`、回退原因、会话和精简交接保存在执行运行记录中。

## Codex Independent Verification

- `uv sync --frozen` 成功；运行依赖可导入。
- 两份真实方案只读结构提取、渲染、逐页文本、来源对齐通过；源哈希、大小、mtime 与目录项前后不变。
- 最终全仓：`514 passed, 1 skipped, 18 subtests passed`；唯一跳过为遗留 06003 OCR 缓存夹具缺失。
- Alembic 升降级、ORM/schema 一致、畸形 DOCX、内容寻址工件、来源哈希复验、编号继承、内容控件、重复范围降级均有回归。

## Cleanup Decision

保留精简执行报告、路由失败证据与验收记录；清理测试缓存和重复临时派生物。切片 1
提交后再由 guard 归档执行过程文件。
