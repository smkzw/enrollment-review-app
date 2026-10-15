# Codex Main-Venue Plan: phase3-slice1-acceptance

Date: 2026-08-14
Objective: 独立审查 Phase 3 第一切片的方案原文登记、DOCX结构提取、受控渲染、来源对齐、不可变存储和真实方案回归，寻找会导致临床规则错漏或虚假来源定位的系统性缺陷；仅审查，不修改文件。

## Task Decomposition

1. 独立复核领域契约、SQLite 迁移和不可变工件边界，确认源文件、提取块集与渲染件均由内容哈希绑定。
2. 复核 DOCX 结构提取对表格、嵌套表格、页眉页脚、编号继承、修订和内容控件的覆盖，寻找会静默漏掉方案正文的路径。
3. 使用仓内测试证据审查来源对齐，重点挑战重复文本、CJK 字距、跨结构块共享范围和伪精确页码。
4. 由 Codex 对两份真实方案执行只读回归，核对源文件前后哈希、目录状态、渲染页数和每个精确摘录的页内可回验性。
5. 仅在确定性测试和独立复核均通过后放行切片 1；覆盖不足必须作为已知限制进入后续切片，不得降低来源精度门槛。

## Source Packet

- 架构与实施基线：`docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`、`plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`。
- Trellis 任务合同：`.trellis/tasks/08-14-phase3-protocol-deconstruction/` 下的 `prd.md`、`design.md`、`implement.md`、`research.md`。
- 待审实现：`app/domain/contracts/protocol_ingestion.py`、`app/protocols/`、`app/storage/migrations/versions/0004_protocol_ingestion.py`、`tests/v2/protocols/`。
- 执行证据：`runs/execution/phase3-protocol-slice1/`、`reviews/codex_execution_phase3-protocol-slice1_review.md`、`metrics/phase3-protocol-slice1_execution_metrics.md`。
- 真实方案仅由 Codex 在本机只读验证；外部参与者不得读取工作区外临床源文件。

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `general_pi_qwen38` | `cms-smk` | `deepseek-v4-flash:max` | `runs/conference/phase3-slice1-acceptance/general_pi_qwen38.md` |
| `general_grok46` | `grok-build` | `grok-4.6` | `runs/conference/phase3-slice1-acceptance/general_grok46.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

- Pi 健康探针超时后按合同执行一次真实调用，建立可恢复会话；未因探针状态随意换路。
- Grok 首轮取消后复用同一会话得到一份完整审查；后续输出不完整，经同会话恢复仍不足，因此不作为最终放行证据。
- Pi 的初审、返修复核和最终碰撞复核均在可追踪会话中完成；最终放行只采用完整且可由确定性测试复现的意见。
- 路由、会话状态与耗时保存在 `runs/conference/phase3-slice1-acceptance/` 和会议指标文件中。

## Codex Verification Checklist

- [x] 契约、ORM 与迁移可往返，且不存在双 schema 漂移。
- [x] 源 DOCX、规范化块集和 PDF 渲染件均为内容寻址，不依赖可变外部路径。
- [x] 提取与渲染前复验源哈希；源文件和目录在真实方案回归前后未改变。
- [x] 两份真实方案的官方编号、结构下限、渲染页数和正文抽取通过。
- [x] 所有保留的精确文本范围均能在声明页回验，且不存在跨结构块共享同一物理范围。
- [x] 重复文本、页眉页脚和降级匹配不会冒充规则级精确来源。
- [x] 最终全仓测试 `514 passed, 1 skipped, 18 subtests passed`；唯一跳过是遗留 OCR 缓存夹具缺失。
- [x] 剩余页级召回不足被记录为后续受限插值研究，不降低当前来源可信度。
