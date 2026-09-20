Trellis SessionStart ✓

我将首先了解仓库结构，并定位“活动131包计划”以及现有的可复用契约。

当前工作目录（CWD）在多次调用间会重置；我将使用绝对路径。

我现在理解了该切片模式。让我阅读最新的已接受检查点（生命体征 v14, ECG），以了解每个包的工件结构，并找到 131-package 计划。

ECG 清单为我提供了确切的工件格式。现在让我来定位活动冻结计划 (`papl-40b1237a22e538a278b4fd5e`) 及其第 74 包。

计划已验证（SHA 匹配，131 个数据包）。现在让我来提取第 74 号数据包。

包 74 = `pap-ddea6dc1bab6691aaace01bc`，拥有 body.p819-p827。现在让我从结构 blob 中提取这些单元以及只读闭包源的实际节选。

自有单元已确认（纯评分方法）。现在处理只读闭包源——IN-04 阈值、流程表行以及 p885。

Package 51 负责 IN-04；p885 属于只读上下文。现在让我研究一下最新的 config schema (ECG) 以及 flow rows 是如何进入 config 的。

现在让我查看流程表结构——标题行和第 22–25 行的单元格——以确定哪些访视包含疗效评估。

关键发现：DLQI 行没有筛选标记。我来确认一下列 c2 的含义，并检查表脚注。

找到了 `baseline-value` 规则 (p316/p347/p885)。现在让我查看 `vital-sign config` 的 `workflow_stages` (`flow-d1-pre-dose`) 以及 `p316` 的所有者。

`visit_merge_baseline_value.v2` 是最接近的现有契约（D1 给药前基线）。我来读取一下它。

该协定是可重用的。现在让我检查一下所有 PASI/PGA/BSA/DLQI 行和 IN-04 的官方流程目录。

流程目录确认了权威节点结构。我来获取确切的 `item_ids` 和 `span ids`。

已捕获 IN-04 权威行。现在让我检查现有的测试模式，以了解新切片应添加哪些“必要测试”。

我现在已经完全掌握了模式。让我检查一下基础配置 (viral_tb) 以及用于 dry-run prepare 的 replay script interface。

现在我来了解一下 `replay harness` 的 `config` 验证，以确保新配置（config）能够通过 `dry-run`。

矩阵中有 PASI/PGA/BSA 行，但没有 DLQI 行。我来提取准确的 IN-04 矩阵行和 DLQI D1 span（“评估PASI、PGA、BSA”片段来源）。

Schema 已确认。我来检查一下共享动作目录（shared action catalog）中与评分相关的动作（以决定是否声明动作类型）。

目前尚无评分操作类型——我将保持 `config` 精简，并将 `action metadata` 标记为待重播时考虑。我来检查一下 `prepare gate` 验证了什么。

所有契约细节已确认。现在我将创建三个构件：config、父检查清单和测试。

现在是父级临床检查清单。

已确认父级索引。让我先检查一下 `ResolvedUnit` 的字段以及 `_resolve_units`/`_workflow` 的返回格式，然后再编写测试。

正在编写重点回归测试。

14 个测试已通过。现在执行模型无关的空跑准备。

Preparation accepted (19 units, 38,896-char prompt). Now verify prompt hygiene: known targets present, zero QC leakage.

抽查一下 DLQI 上下文和 freeze provenance，然后修复清单中的一个计数错误（我写了“十四”但实际上是 19 个单位）。
