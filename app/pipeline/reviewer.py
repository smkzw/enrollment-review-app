"""LLM-based enrollment review module v2.0.

Sends criteria rules + evidence bundle to the LLM and parses the
structured markdown response into a ReviewReport.

Key changes from v1:
- No auto-extracted anchor dates — LLM identifies dates from evidence.
- Evidence hierarchy rules in prompt (screening record > prior record).
- LLM must quote source document names and categories in reasoning.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from app.config import REVIEW_BACKEND, REVIEW_MODEL
from app.llm.client import review_chat
from app.models import GroupResult, ReviewReport, ReviewResult
from app.phases import phase_by_id, render_phase_scope

logger = logging.getLogger(__name__)

RULE_ID_PATTERN = re.compile(r"(?<![A-Za-z0-9])(?:IN|EX)-[A-Za-z0-9_.-]+")

# ---------------------------------------------------------------------------
# Verdict emoji ↔ internal value mapping
# ---------------------------------------------------------------------------

_EMOJI_TO_VERDICT: dict[str, str] = {
    "通过（需验证": "pass_verify",
    "通过需验证": "pass_verify",
    "需溯源验证": "pass_verify",
    "病史来源需溯源验证": "pass_verify",
    "后续阶段复核": "pass_verify",
    "后续阶段待复核": "pass_verify",
    "基线待后续阶段复核": "pass_verify",
    "✅": "pass",
    "❌": "fail",
    "⚠️ 证据不足": "insufficient",
    "⚠️证据不足": "insufficient",
    "⚠️ 需研究者": "investigator",
    "⚠️需研究者": "investigator",
    "⚠️": "insufficient",
    "— 不适用": "na",
    "—不适用": "na",
    "—": "na",
}


def _map_verdict(cell: str) -> str:
    cell = cell.strip()
    normalized = re.sub(r"\s+", "", cell)
    if normalized in {"-", "－"}:
        return "na"
    if any(
        key in normalized
        for key in (
            "通过（需验证",
            "通过需验证",
            "需溯源验证",
            "病史来源需溯源验证",
            "后续阶段复核",
            "后续阶段待复核",
            "基线待后续阶段复核",
        )
    ):
        return "pass_verify"
    for pattern, value in _EMOJI_TO_VERDICT.items():
        if pattern in cell:
            return value
    if "不通过" in cell:
        return "fail"
    lower = cell.lower()
    if "fail" in lower:
        return "fail"
    if "不适用" in cell or "—" in cell:
        return "na"
    if "证据不足" in cell:
        return "insufficient"
    if "需研究者" in cell:
        return "investigator"
    if "通过" in cell or "pass" in lower:
        return "pass"
    logger.warning("Could not map verdict from cell: %r", cell)
    return "insufficient"


# ---------------------------------------------------------------------------
# System prompt (v2.0 — evidence hierarchy, LLM-identified dates)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
你是一名资深的临床试验入排审核专家。根据入排标准规则和证据材料，逐条审核。

## 证据层级规则（重要！）

证据材料按以下类别标注，权威性从高到低：
1. **筛选-基线病历**（最权威）— ICF签署、入排评估、生命体征以此为准
2. **筛选-基线检验报告单** — 筛选期实验室/影像/心电图
3. **既往病历** — 历史诊断、既往用药
4. **既往检验检查报告单** — 历史实验室数据
5. **入组审核邮件/沟通记录/Q&A** — 辅助参考

**冲突处理**：当不同类别证据对同一信息有不同记载时，先判断该信息属于“当期事实”还是“既往事实”，再按对应层级采信。例如：
- 既往病历和筛选病历都提到"签署知情同意"→ 以筛选病历记录的签署日期为准（患者可能参加过其他试验）
- 方案要求"既往诊断/症状起病/病程时长达到X年或X月"→ 以既往病历、既往检查报告、既往处方、出院小结、诊断证明等源文件优先；筛选/基线病历中的一句病史转述不能等同于既往源文件
- 邮件中"建议核实XX" ≠ XX确实有问题 → 需看筛选病历/检验报告的原文档判断
- ICF签署日期 ≠ ICF版本日期（版本日期是知情同意书模板的制定日期，签署日期是受试者实际签字日期）

## 既往事实/病程时长溯源规则（重要！）

以下条款必须按“历史事实”处理：既往诊断、最早症状、病程时长、病史超过若干年或月、既往治疗或手术、既往用药暴露、既往检查异常、既往参加研究或使用生物制剂/疫苗等。

- **首选证据**：既往门急诊/住院病历、出院小结、诊断证明、既往检验检查报告、既往处方/用药记录、既往病程记录等可追溯源文件。
- **筛选/基线病历转述**：如果只有筛选或基线病历写有"患者自述/既往诊断/病史X年/症状X年"，且未见更早既往源文件、也没有矛盾证据，可以判为 `✅通过（需验证：病史来源需溯源验证）`，不得写成普通 `✅通过`。
- **证据冲突**：既往源文件与筛选/基线病历转述冲突时，优先采信既往源文件，并在推理依据中说明冲突。
- **完全缺失**：如果既往事实或时长在任何源文件中均未见明确支持，判为 `⚠️证据不足`。
- **不得使用**：EDC入排汇总勾选、IE/IEYN类汇总字段、邮件中的"已符合/已确认"不能单独证明既往事实。

## 关键日期识别

锚点日期仅供参考，必须从证据原文中明确提取和核实，不得推断或用报告日期/打印日期/上传日期替代：
- **ICF签署日期**：在筛选病历中找"受试者于XXXX年XX月XX日...签署了知情同意书"（注意区分ICF版本日期和签署日期）
- **筛选日期**：筛选病历的就诊/评估日期
- **年龄**：从筛选病历中提取（如"年龄：65岁"），据此验证是否符合入选标准年龄要求。如果无出生日期，直接使用病历记载的年龄。
- **基线/随机日期**：仅在证据明确写明基线、随机、给药或等价访视日期时使用；未明确写明时不得自行推断

## 审核原则
1. **推理依据必须引用原文**：写明 `【证据类别·文件名】pN 提及："原文关键句"`。例如：`【筛选-基线病历】p2 提及："受试者于2025年08月12日09时55分...签署了知情同意书"`
2. 不要写LLM的思考过程，只写最终结论和支撑原文。
3. 有子项的标准整体判断。

## 判定闭环规则（防止表格结论与依据冲突）

每一条规则必须先完成语义判断，再填写判定结果。不要先看条目标题或局部异常就写结论。

- **排除标准（EX）**：只有证据明确达到方案规定的排除触发条件，才能判 `❌不通过`。推理依据必须写清 `触发判断：已触发`，并列出触发子项、原始数值/事实、单位、阈值或方案条件。若依据中出现"未达排除阈值、未触发排除标准、故本条通过、需研究者评估、暂不直接判定不通过"，判定结果不能写 `❌不通过`。
- **可能性不是触发**：`存在违规可能`、`存在隐患`、`未明确是否使用/发生`、`时间窗交接不清`、`需确认`、`待补充` 只能判 `⚠️需研究者` 或 `⚠️证据不足`，不能直接判 `❌不通过`。只有明确证据显示在方案时间窗内发生了禁用事实或达到阈值，才可不通过。
- **纳入标准（IN）**：只有证据明确不满足纳入条件，才能判 `❌不通过`。若只是缺少资料、缺少当前阶段应到达检查、或病史需溯源，应判 `⚠️证据不足` / `⚠️需研究者` / `✅通过（需验证：病史来源需溯源验证）`。
- **复杂组合/实验室条款**：逐一比较子项。单个指标异常、参考范围外、NCS/CS待判断，不等同于触发排除；必须比较方案阈值。例如"高于正常上限"不等于"超过3倍ULN"，"HBcAb阳性"不等于"HBV-DNA阳性"。
- **检验项目必须精确匹配**：实验室阈值只能由方案列明的检验项目或明确同义词触发，不能用相邻项目、同属肝功能项目或常识相关项目替代。例：若方案写 `ALT或AST或总胆红素 ≥1.5×ULN`，只有 ALT/谷丙/丙氨酸氨基转移酶、AST/谷草/天冬氨酸氨基转移酶、总胆红素/TBil 可触发；GGT、ALP、直接胆红素、间接胆红素、胆汁酸等即使异常，也不能触发该子项。未列名但异常的指标只能进入“其它实验室异常且有临床意义/研究者评估”通道，不能直接判 definitive 不通过。
- **条款主题必须匹配证据主题**：不能把某条证据中的“异常”迁移到不相关条款。例：EX-07 活动性感染/急性疾病状态需要感染或急性疾病的诊断、症状体征、抗感染治疗或相关检查证据；尿糖、潜血、GGT等孤立检验异常不能证明活动性感染，也不能推翻病历中“否认活动性感染或急性疾病状态”的记载。
- **合取条件必须全部满足**：方案写 `且/并且/同时/经研究者评估` 的组件是 AND，不得弱化成 OR。例：`任何其它实验室检查结果异常且有临床意义，经研究者评估如果参与研究将可能对参与者构成不可接受的风险` 必须同时满足：其它实验室异常 + 该异常有临床意义 + 研究者评估参与研究可能构成不可接受风险。尿糖1+、潜血阳性、GGT升高或“未排除临床意义”均不是完整排除条件。
- **临床意义和不可接受风险必须有明确判断来源**：若方案子项要求“异常且有临床意义/研究者评估不可接受风险”，必须有研究者/医生明确判断为有临床意义，并明确评估参与研究将可能构成不可接受风险。`未排除临床意义`、`需研究者评估`、`除非后续补充排除证据` 只能判为 `⚠️需研究者`，不能直接判 `❌不通过`。
- **研究者判断类复合条件不能缺项**：若排除条件是 `存在疾病/异常/用药/病史` + `研究者判断不具备临床研究条件/可能影响研究评估/增加安全性风险/疗效不佳/影响依从性/有自杀风险`，则两部分必须同时有证据。只有疾病、异常或用药存在，或只写 `未明确判断具备条件`、`必要时专科就诊`、`疗效不详`，不能判 `❌不通过`，应判 `⚠️需研究者`。
- **梅毒筛查例外必须完整**：若方案写 `梅毒特异性抗体试验阳性（梅毒非特异性抗体阴性且研究者判断为既往感染已治愈的除外）`，则 TPPA/TP-Ab/梅毒特异性抗体阳性本身是触发项。只有同时具备 `TRUST/RPR/非特异性抗体阴性` 和 `研究者明确判断既往感染已治愈` 才能按例外通过。`目前无不适`、`未予治疗`、`非活动性感染`、`不符合所有排除标准/可以进入研究` 不能替代 `既往感染已治愈`。

## DeepSeek输出前自检（必须逐行执行）

DeepSeek在长规则和高推理token下容易出现“推理正确但表格判定未同步”“漏掉父级官方编号”“用整体入排结论替代单条研究者判断”的问题。输出前必须按下列门控逐条修正：

1. **官方父级规则不可遗漏**：用户给出的每个官方父级规则ID必须在表格中出现一行。可以在同一行写子项a/b/c的组件判断，但不得只输出EX-20a~EX-20h而漏掉EX-20父级行，也不得把子项升级成新的官方父级编号。
2. **fail门控**：任何 `❌不通过` 都必须有明确正向触发证据，且推理依据不得含有 `未达阈值/未触发/不触发/需研究者/未明确/证据不足/待补充/后续复核/不能直接判定` 等保留语。如果这些词描述的是当前条款，先把判定改成 `⚠️需研究者`、`⚠️证据不足` 或 `✅通过`，再输出。
3. **整体IE结论不能替代单条证据**：`符合所有入选标准且不符合排除标准`、`可入组`、`不符合所有排除标准`、`整体符合入排` 只能作为背景，不能替代某个复合条款要求的研究者明确判断。若条款要求“研究者评估不可接受风险/不具备临床研究条件/既往感染已治愈”，必须引用该单条判断；没有则判 `⚠️需研究者` 或 `⚠️证据不足`。
4. **阈值子项与其它异常子项分流**：若ALT/AST/TBil等阈值子项未达方案阈值，但有其它异常或临床意义标记，不要把阈值子项判失败；应将残余问题放到“其它实验室异常+研究者判断”类子项，并检查AND组件是否完整。
5. **例外缺项不能硬套**：例外条款缺少必要组件时，不能按例外通过；但若缺少的是研究者确认/治愈判断/不可接受风险判断，也不能仅凭“缺少例外证明”自动写成 definitive `❌不通过`，应按当前阶段资料性质判 `⚠️需研究者` 或 `⚠️证据不足`，除非方案原文明确规定缺少该组件本身即排除。
6. **最后一致性检查**：若表格"判定结果"与"推理依据"不一致，必须在最终输出前改正表格判定，不要把矛盾留给系统解析。

## 工作要求
1. 严格基于证据判定，不得臆测。
2. 每条父级规则ID只能输出一行；不要把IN-04a/IN-04b等子项拆成多个IN-04，也不要把子项升级成新的父级编号。子项判断合并写在同一行推理依据中。
3. 每条规则：✅通过 / ✅通过（需验证：病史来源需溯源验证）/ ❌不通过 / ⚠️证据不足 / ⚠️需研究者 / —不适用。
4. 推理依据1-2句，必须包含原文引用（含证据类别标注和原文关键句），并包含 `触发判断：...` 或 `符合判断：...`。
5. 情形组单独判定。
6. 总结论判定标准（必须严格遵循）：
   - **fail（不可入组）**：至少一条入选标准被 definitive 判定为**❌不通过**（如年龄超标、实验室值明确低于阈值），或至少一条排除标准被 definitive 触发。注意：⚠️证据不足和⚠️需研究者 ≠ ❌不通过。
   - **insufficient（证据不足）**：没有任何标准被 definitive 判定为不通过，但存在 ⚠️证据不足 的项目；若同时存在 ⚠️需研究者，整体仍优先写 insufficient，因为需要补充额外资料。
   - **investigator（需研究者判定）**：没有任何标准被 definitive 判定为不通过，也不存在 ⚠️证据不足，但存在 ⚠️需研究者 的项目；这表示已有资料需要研究者/医学判断，不等同于缺源文件补证。
   - **pass（可入组）**：没有❌不通过、⚠️证据不足、⚠️需研究者时，即使存在 `✅通过（需验证：病史来源需溯源验证）`，整体也按 pass。`通过（需验证）`仅作为溯源提醒，不单独改变整体结论；输出给用户时统一写“溯源提醒”。
7. 涉及年龄判断时，直接使用病历记载年龄，不要因缺少出生日期而判"证据不足"。

## 输出格式
### 逐条审核结果
| 规则ID | 规则名称 | 类型 | 判定结果 | 推理依据 |
|--------|----------|------|----------|----------|
| IN-01 | 知情同意 | 入选 | ✅通过 | 【筛选-基线病历】p2 提及："受试者于2025-08-12 09:55签署了知情同意书" |

### 总结论
判定结果：（pass / fail / insufficient / investigator）
一段话总结。
"""


# ---------------------------------------------------------------------------
# Response parsing (unchanged from v1)
# ---------------------------------------------------------------------------

def _strip_md_table_row(line: str) -> List[str]:
    line = line.strip().strip("|")
    return [cell.strip() for cell in line.split("|")]


def _is_separator(line: str) -> bool:
    return bool(re.match(r"^\|[\s\-:]+\|", line))


def _parse_rule_table(text: str) -> List[ReviewResult]:
    results: List[ReviewResult] = []
    lines = text.split("\n")
    in_table = False
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_table:
                break
            continue
        cells = _strip_md_table_row(stripped)
        if len(cells) < 4:
            continue
        if "规则ID" in cells[0] or "规则id" in cells[0].lower():
            in_table = True
            continue
        if _is_separator(stripped):
            continue
        if not in_table:
            continue
        rule_id = cells[0].strip()
        rule_name = cells[1].strip() if len(cells) > 1 else ""
        type_cell = cells[2].strip() if len(cells) > 2 else ""
        verdict_cell = cells[3].strip() if len(cells) > 3 else ""
        reasoning = cells[4].strip() if len(cells) > 4 else ""
        if "入选" in type_cell or "inclusion" in type_cell.lower():
            rule_type = "inclusion"
        elif "排除" in type_cell or "exclusion" in type_cell.lower():
            rule_type = "exclusion"
        else:
            rule_type = type_cell
        verdict = _map_verdict(verdict_cell)
        results.append(ReviewResult(
            rule_id=rule_id, rule_name=rule_name,
            rule_type=rule_type, verdict=verdict, reasoning=reasoning,
        ))
    return results


def _more_conservative_verdict(left: str, right: str) -> str:
    rank = {
        "na": 0,
        "pass": 1,
        "pass_verify": 2,
        "investigator": 3,
        "insufficient": 4,
        "fail": 5,
    }
    return left if rank.get(left, 3) >= rank.get(right, 3) else right


def _merge_duplicate_rule_results(results: List[ReviewResult]) -> List[ReviewResult]:
    """Keep one row per parent rule ID and preserve the strictest verdict."""
    merged: list[ReviewResult] = []
    by_id: dict[str, ReviewResult] = {}
    for item in results:
        existing = by_id.get(item.rule_id)
        if existing is None:
            by_id[item.rule_id] = item
            merged.append(item)
            continue
        existing.verdict = _more_conservative_verdict(existing.verdict, item.verdict)
        if item.rule_type and not existing.rule_type:
            existing.rule_type = item.rule_type
        if item.rule_name and not existing.rule_name:
            existing.rule_name = item.rule_name
        if item.reasoning and item.reasoning not in existing.reasoning:
            existing.reasoning = (existing.reasoning.rstrip("；;。") + "；" + item.reasoning).strip("；")
    return merged


def _insert_missing_parent_rule_results(results: List[ReviewResult]) -> bool:
    """Insert inferred parent rows when the LLM outputs children but omits the parent."""
    seen_ids = {item.rule_id for item in results}
    parents_to_insert: dict[str, tuple[int, ReviewResult]] = {}
    for idx, item in enumerate(results):
        parent_id = _child_parent_rule_id(item.rule_id)
        if not parent_id or parent_id in seen_ids or parent_id in parents_to_insert:
            continue
        parents_to_insert[parent_id] = (
            idx,
            ReviewResult(
                rule_id=parent_id,
                rule_name="父级汇总项",
                rule_type=item.rule_type,
                verdict="na",
                reasoning="父级汇总项，由同一父级子项决定。",
            ),
        )
    if not parents_to_insert:
        return False
    for insert_at, parent in sorted(parents_to_insert.values(), key=lambda item: item[0], reverse=True):
        results.insert(insert_at, parent)
    return True


def _parse_group_table(text: str) -> List[GroupResult]:
    results: List[GroupResult] = []
    lines = text.split("\n")
    in_table = False
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_table:
                break
            continue
        cells = _strip_md_table_row(stripped)
        if len(cells) < 2:
            continue
        if "组ID" in cells[0] or "组id" in cells[0].lower():
            in_table = True
            continue
        if _is_separator(stripped):
            continue
        if not in_table:
            continue
        group_id = cells[0].strip()
        verdict_cell = cells[1].strip() if len(cells) > 1 else ""
        members_cell = cells[2].strip() if len(cells) > 2 else ""
        explanation = cells[3].strip() if len(cells) > 3 else ""
        verdict = _map_verdict(verdict_cell)
        if members_cell and members_cell not in ("无", "—", "-"):
            satisfied = [m.strip() for m in members_cell.split(",") if m.strip()]
        else:
            satisfied = []
        results.append(GroupResult(
            group_id=group_id, verdict=verdict,
            satisfied_members=satisfied, explanation=explanation,
        ))
    return results


def _parse_overall_verdict(text: str) -> str:
    lower = text.lower()
    verdict_match = re.search(
        r"判定结果[：:]\s*(?:\*\*)?\s*(pass|fail|insufficient|investigator|needs_evidence|可入组|不可入组|证据不足|需研究者判定|需研究者|待补证)",
        text, re.IGNORECASE,
    )
    if verdict_match:
        val = verdict_match.group(1).strip().lower()
        if val in ("pass", "可入组"):
            return "pass"
        if val in ("fail", "不可入组"):
            return "fail"
        if val in ("insufficient", "证据不足"):
            return "insufficient"
        if val in ("investigator", "需研究者判定", "需研究者"):
            return "investigator"
        return "needs_evidence"
    if "不可入组" in text or "不满足入组" in text:
        return "fail"
    if "证据不足" in text:
        return "insufficient"
    if "需研究者判定" in text or "需研究者" in text:
        return "investigator"
    if "待补证" in text:
        return "needs_evidence"
    if "可入组" in text or "满足" in text:
        return "pass"
    logger.warning("Could not determine overall verdict from response")
    return "needs_evidence"


POSITIVE_TRIGGER_PATTERNS = [
    r"触发判断[：:]\s*已触发",
    r"(?<!未见)(?<!未)(?<!不)(?<!无)(明确|已|已经)?触发(?:了)?(?:本条|该条|排除|子项|EX-[A-Za-z0-9_.-]+)",
    r"(?<!未见)(?<!未)(?<!不)(?<!无)(达到|符合)(?:了)?(?:本条|该条|排除|方案).{0,16}(标准|条件|阈值)",
    r"(?<!未见)(?<!未)(?<!不)(?<!无)(超过|高于|大于).{0,18}(?:3\s*倍|三\s*倍|正常上限|参考上限|ULN)",
    r"(?:ALT|AST|TBil|TBiL|总胆红素|肌酐|CREA|ANC|中性粒细胞|血红蛋白|Hb)"
    r"[^，。；;|]{0,24}(?:>|≥|>=)"
    r"[^，。；;|]{0,24}(?:3\s*倍|三\s*倍|正常上限|参考上限|ULN|方案标准|排除标准)",
    r"(?<!未见)(?<!未)(?<!不)(?<!无)(低于|小于|<|≤).{0,18}(?:阈值|方案标准|排除标准|下限)",
    r"研究者.{0,8}(判断|评估|认为).{0,12}(有临床意义|CS|临床显著)",
]

NEGATIVE_TRIGGER_PATTERNS = [
    r"触发判断[：:]\s*(未触发|不触发|未见触发)",
    r"触发判断[：:]\s*(?:未达到|未达|未见达到|未见达)[^。；;|]{0,24}(?:不触发|未触发)",
    r"(未触发|不触发).{0,18}(EX-[A-Za-z0-9_.-]+|排除|标准|条件|阈值|本条|该条)",
    r"(未触发|不触发).{0,18}(排除|标准|条件|阈值|本条|该条)",
    r"(未达到|未达|未见达到|未见达|未超过|未低于|不符合).{0,20}(排除|标准|条件|阈值|方案)",
    r"(故|因此|所以|综上|重新评估|重新确认).{0,18}(本条|该条)?.{0,8}(通过|不触发|未触发)",
    r"(不支持|不能|不应|暂不).{0,12}(判定|判断).{0,8}(不通过|触发)",
    r"均未触发排除标准",
]

INVESTIGATOR_PATTERNS = [
    r"暂不直接判定不通过",
    r"(待|需|需要).{0,8}(研究者|PI|医学监查).{0,8}(确认|评估|判断)",
    r"尚未见研究者.{0,12}(确认|评估|判断)",
    r"(未明确|未见明确|不能确认|无法确认|尚未确认).{0,30}(是否|有无|使用|发生|执行)",
    r"(存在|有).{0,12}(违规可能|违规隐患|入排风险隐患|待确认|需确认)",
    r"(时间窗|洗脱期|用药记录|治疗记录).{0,30}(不清|不明确|交接不清|待确认|需确认)",
]


def _last_semantic_index(patterns: List[str], reasoning: str) -> int:
    last = -1
    for pattern in patterns:
        for match in re.finditer(pattern, reasoning, re.IGNORECASE):
            last = max(last, match.start())
    return last


def _has_positive_trigger_semantics(reasoning: str) -> bool:
    """Return true when the reasoning states a definitive trigger condition."""
    return _last_semantic_index(POSITIVE_TRIGGER_PATTERNS, reasoning) >= 0


def _has_negative_trigger_semantics(reasoning: str) -> bool:
    """Return true when the reasoning states the exclusion was not triggered."""
    return _last_semantic_index(NEGATIVE_TRIGGER_PATTERNS, reasoning) >= 0


def _has_investigator_semantics(reasoning: str) -> bool:
    return _last_semantic_index(INVESTIGATOR_PATTERNS, reasoning) >= 0


def _has_ex20g_liver_analyte_substitution(reasoning: str) -> bool:
    """Detect using a non-listed liver enzyme to trigger ALT/AST/TBil criteria."""
    if not re.search(r"(EX-20g|ALT\s*或\s*AST\s*或\s*(?:总胆红素|TBil|TBiL))", reasoning, re.IGNORECASE):
        return False
    allowed_measured_trigger = re.search(
        r"(ALT|丙氨酸氨基转移酶|谷丙|AST|天冬氨酸氨基转移酶|谷草|总胆红素|TBil|TBiL)"
        r"[^，。；;|]{0,24}\d+(?:\.\d+)?\s*(?:U/L|μmol/L|umol/L|µmol/L|mg/dL|)"
        r"[^，。；;|]{0,40}(≥|>=|>|超过|高于|升高|异常|触发)",
        reasoning,
        re.IGNORECASE,
    )
    if allowed_measured_trigger:
        return False
    return bool(re.search(r"(GGT|γ-?GT|γ谷氨酰|谷氨酰转肽酶|谷氨酰转移酶)", reasoning, re.IGNORECASE))


def _has_ex07_unrelated_lab_substitution(reasoning: str) -> bool:
    """Detect unrelated urinalysis/lab abnormalities being used as EX-07 infection proof."""
    text = reasoning or ""
    if not re.search(r"(尿常规|尿检|尿液|尿糖|葡萄糖|潜血|隐血|红细胞|实验室异常|检验异常)", text):
        return False
    if not re.search(r"(否认.{0,12}(活动性感染|急性疾病)|无.{0,12}(活动性感染|急性疾病)|未见.{0,12}(活动性感染|急性疾病))", text):
        return False
    infection_evidence = re.search(
        r"(尿路感染|泌尿系感染|膀胱炎|肾盂肾炎|肺炎|支气管炎|发热|抗感染|抗生素|CRP.{0,12}(升高|异常|阳性)|"
        r"(白细胞|亚硝酸盐|细菌).{0,12}(阳性|升高|异常)|诊断.{0,16}(感染|急性疾病))",
        text,
        re.IGNORECASE,
    )
    return infection_evidence is None


def _has_explicit_clinical_significance_source(reasoning: str) -> bool:
    """Return true only when CS/unacceptable-risk wording is tied to a clinician/investigator."""
    return bool(
        re.search(
            r"(研究者|医生|PI|医学监查).{0,16}(判断|评估|认为|确认).{0,24}(有临床意义|CS|临床显著|不可接受.{0,8}风险)",
            reasoning or "",
            re.IGNORECASE,
        )
        or re.search(
            r"(有临床意义|CS|临床显著).{0,16}(研究者|医生|PI|医学监查).{0,16}(判断|评估|认为|确认)",
            reasoning or "",
            re.IGNORECASE,
        )
    )


def _mentions_ex20h_other_lab(reasoning: str) -> bool:
    return bool(
        re.search(
            r"(EX-20h|(?:任何)?(?:其它|其他)实验室|实验室检查结果异常且有临床意义)",
            reasoning or "",
            re.IGNORECASE,
        )
    )


def _has_explicit_unacceptable_risk_source(reasoning: str) -> bool:
    """Return true when investigator/clinician explicitly ties participation to unacceptable risk."""
    text = reasoning or ""
    return bool(
        re.search(
            r"(研究者|医生|PI|医学监查).{0,18}(判断|评估|认为|确认).{0,40}"
            r"(参与研究|参加研究|入组|继续研究).{0,30}(不可接受.{0,8}风险|构成.{0,8}不可接受|安全性风险不可接受)",
            text,
            re.IGNORECASE,
        )
        or re.search(
            r"(研究者|医生|PI|医学监查).{0,18}(判断|评估|认为|确认).{0,40}"
            r"(不可接受.{0,8}风险|构成.{0,8}不可接受|安全性风险不可接受)",
            text,
            re.IGNORECASE,
        )
    )


def _has_incomplete_ex20h_all_of_logic(reasoning: str) -> bool:
    """EX-20h requires abnormal lab + CS + investigator unacceptable-risk assessment."""
    text = reasoning or ""
    if not _mentions_ex20h_other_lab(text):
        return False
    has_lab_abnormality = bool(re.search(r"(异常|阳性|升高|降低|>|<|↑|↓|\+)", text))
    has_clinical_significance = _has_explicit_clinical_significance_source(text)
    has_unacceptable_risk = _has_explicit_unacceptable_risk_source(text)
    return not (has_lab_abnormality and has_clinical_significance and has_unacceptable_risk)


def _mentions_syphilis_specific_positive(reasoning: str) -> bool:
    """Detect treponemal/specific syphilis antibody positivity."""
    text = reasoning or ""
    specific = r"(?:梅毒(?:螺旋体)?特异(?:性)?抗体|TPPA|TP-Ab|TP抗体|Anti-TP|抗TP|梅毒TP)"
    return bool(
        re.search(specific + r"[^，。；;|]{0,28}(?:阳性|阳性↑|\+|positive)", text, re.IGNORECASE)
        or re.search(r"(?:阳性|阳性↑|\+|positive)[^，。；;|]{0,28}" + specific, text, re.IGNORECASE)
    )


def _mentions_syphilis_nonspecific_negative(reasoning: str) -> bool:
    """Detect non-treponemal/non-specific syphilis test negativity."""
    text = reasoning or ""
    nonspecific = r"(?:梅毒非特异(?:性)?抗体|非特异(?:性)?抗体|TRUST|RPR|甲苯胺红|快速血浆反应素)"
    return bool(
        re.search(nonspecific + r"[^，。；;|]{0,28}(?:阴性|negative|-)", text, re.IGNORECASE)
        or re.search(r"(?:阴性|negative|-)[^，。；;|]{0,28}" + nonspecific, text, re.IGNORECASE)
    )


def _syphilis_reasoning_without_protocol_exception_quote(reasoning: str) -> str:
    """Remove criterion-language echoes so they do not count as source evidence."""
    text = reasoning or ""
    text = re.sub(
        r"符合[“\"']?非特异性抗体阴性且研究者判断为既往感染已治愈[”\"']?的?例外",
        "",
        text,
    )
    text = re.sub(
        r"符合[“\"']?梅毒非特异性抗体阴性且研究者判断为既往感染已治愈[”\"']?的?例外",
        "",
        text,
    )
    text = re.sub(
        r"方案.{0,24}非特异性抗体阴性且研究者判断为既往感染已治愈",
        "",
        text,
    )
    return text


def _has_explicit_syphilis_cured_judgment(reasoning: str) -> bool:
    """Return true only when source reasoning contains an explicit cured-prior-infection judgment."""
    text = _syphilis_reasoning_without_protocol_exception_quote(reasoning)
    cured = r"(?:既往[^，。；;|]{0,16}(?:梅毒)?感染[^，。；;|]{0,8}已?治愈|梅毒[^，。；;|]{0,18}已?治愈|已规范治疗[^，。；;|]{0,18}治愈)"
    clinician = r"(?:研究者|医生|医师|PI|医学监查)"
    negative_cured_judgment = (
        r"(?:未见|缺少|尚缺|无|没有|未明确|不能证明|无法证明)[^。；;|]{0,36}"
        + clinician
        + r"?[^。；;|]{0,24}(?:判断|评估|认为|确认|明确)?[^。；;|]{0,60}"
        + cured
    )
    if re.search(negative_cured_judgment, text):
        return False
    return bool(
        re.search(clinician + r"[^。；;|]{0,32}(?:判断|评估|认为|确认|明确)[^。；;|]{0,48}" + cured, text)
        or re.search(cured + r"[^。；;|]{0,40}" + clinician + r"[^。；;|]{0,20}(?:判断|评估|认为|确认|明确)", text)
        or re.search(r"(?:记录|提及|显示|评估为|明确判断)[^。；;|]{0,80}" + cured, text)
    )


def _has_incomplete_syphilis_exception_logic(reasoning: str) -> bool:
    """TPPA/treponemal positive can pass only with non-specific negative + explicit cured judgment."""
    text = reasoning or ""
    if not _mentions_syphilis_specific_positive(text):
        return False
    has_nonspecific_negative = _mentions_syphilis_nonspecific_negative(text)
    has_cured_judgment = _has_explicit_syphilis_cured_judgment(text)
    return not (has_nonspecific_negative and has_cured_judgment)


def _neutralize_syphilis_exception_wording(reasoning: str) -> str:
    text = reasoning or ""
    replacements = [
        (
            r"符合[“\"']?非特异性抗体阴性且研究者判断为既往感染已治愈[”\"']?的?例外",
            "仅可证明非特异性抗体阴性，尚不能证明完整例外",
        ),
        (
            r"符合[“\"']?梅毒非特异性抗体阴性且研究者判断为既往感染已治愈[”\"']?的?例外",
            "仅可证明梅毒非特异性抗体阴性，尚不能证明完整例外",
        ),
        (
            r"符合[“\"']?非特异性抗体阴性[”\"']?的?例外",
            "仅可证明非特异性抗体阴性，尚不能证明完整例外",
        ),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text


def _has_explicit_unfavorable_researcher_judgment(reasoning: str) -> bool:
    """Return true when a clinician/investigator explicitly states the adverse component."""
    text = reasoning or ""
    clinician = r"(?:研究者|医生|医师|PI|医学监查)"
    action = r"(?:判断|评估|认为|确认|明确)"
    adverse = (
        r"(?:不具备临床研究条件|不具备.{0,8}研究条件|不适合.{0,12}(?:参加|参与|入组|本研究)|"
        r"不宜.{0,12}(?:参加|参与|入组|本研究)|不能.{0,12}(?:参加|参与|入组|本研究)|"
        r"可能影响研究评估|影响研究评估|可能增加.{0,8}安全性风险|增加.{0,8}安全性风险|"
        r"影响用药依从性|有自杀风险|疗效不佳|因安全性原因停药|不可接受.{0,8}风险|构成.{0,8}不可接受)"
    )
    patterns = [
        clinician + r"[^。；;|]{0,24}" + action + r"[^。；;|]{0,56}" + adverse,
        adverse + r"[^。；;|]{0,32}" + clinician + r"[^。；;|]{0,20}" + action,
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            prefix = text[max(0, match.start() - 14): match.start()]
            matched = match.group(0)
            if re.search(r"(未见|未明确|无|否认|缺少|不足|不详|待|需|需要|不能确认|无法确认)", prefix + matched[:16]):
                continue
            if re.search(r"(未判断|未明确判断|未见判断|无判断|没有判断|缺少判断)[^。；;|]{0,24}" + adverse, matched):
                continue
            if re.search(r"(表明|说明)[^。；;|]{0,12}(未判断|未明确判断|未见判断|缺少判断)", matched):
                continue
            return True
    return False


def _is_systemic_disease_researcher_rule(result: ReviewResult) -> bool:
    text = f"{result.rule_id} {result.rule_name}"
    return bool(
        re.search(
            r"(重大.{0,4}不稳定.{0,8}系统性疾病|系统性疾病|不具备临床研究条件)",
            text,
            re.IGNORECASE,
        )
    )


def _has_ex11_specific_unfavorable_judgment(reasoning: str) -> bool:
    """EX-11's required adverse component is study unsuitability, not generic risk wording."""
    text = reasoning or ""
    clinician = r"(?:研究者|医生|医师|PI|医学监查)"
    action = r"(?:判断|评估|认为|确认|明确)"
    adverse = (
        r"(?:不具备临床研究条件|不具备.{0,8}研究条件|不适合.{0,12}(?:参加|参与|入组|本研究)|"
        r"不宜.{0,12}(?:参加|参与|入组|本研究)|不能.{0,12}(?:参加|参与|入组|本研究))"
    )
    patterns = [
        clinician + r"[^。；;|]{0,24}" + action + r"[^。；;|]{0,56}" + adverse,
        adverse + r"[^。；;|]{0,32}" + clinician + r"[^。；;|]{0,20}" + action,
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            prefix = text[max(0, match.start() - 14): match.start()]
            matched = match.group(0)
            if re.search(r"(未见|未明确|无|否认|缺少|不足|不详|待|需|需要|不能确认|无法确认)", prefix + matched[:16]):
                continue
            if re.search(r"(未判断|未明确判断|未见判断|无判断|没有判断|缺少判断)[^。；;|]{0,24}" + adverse, matched):
                continue
            if re.search(r"(表明|说明)[^。；;|]{0,12}(未判断|未明确判断|未见判断|缺少判断)", matched):
                continue
            return True
    return False


def _normalize_ex11_component_wording(reasoning: str) -> str:
    """Keep EX-11 reasoning anchored to its own protocol component."""
    text = reasoning or ""
    text = re.sub(
        r"是否对受试者参与研究构成不可接受的?风险",
        "是否导致受试者不具备临床研究条件",
        text,
    )
    text = re.sub(
        r"对受试者参与研究构成不可接受的?风险",
        "需进一步明确其是否导致受试者不具备临床研究条件",
        text,
    )
    text = re.sub(
        r"对参与研究构成不可接受的?风险",
        "需进一步明确其是否导致受试者不具备临床研究条件",
        text,
    )
    text = re.sub(
        r"参与研究将?可能?构成不可接受的?风险",
        "需进一步明确其是否导致受试者不具备临床研究条件",
        text,
    )
    if "研究者明确判断不具备临床研究条件" not in text:
        text = (
            text.rstrip("。；; ")
            + "。EX-11完整触发条件应为相关重大或不稳定系统性疾病事实 + 研究者明确判断不具备临床研究条件；当前依据未完整证明该研究者判断。"
        )
    return text


def _has_missing_required_researcher_judgment(reasoning: str) -> bool:
    """Detect missing/unknown judgment for compound criteria that require investigator assessment."""
    text = reasoning or ""
    missing_prefix = r"(?:未明确|未见明确|未见|无|缺少|不足|不详|不能确认|无法确认|尚未确认|待|需|需要)"
    judgment_terms = (
        r"(?:研究者|医生|医师|PI|医学监查|判断|评估|认为|确认|具备临床研究条件|不具备临床研究条件|"
        r"适合参加|不适合参加|影响研究评估|增加安全性风险|安全性风险|有临床意义|不可接受风险|"
        r"疗效不佳|疗效佳|安全性原因停药|影响用药依从性|自杀风险)"
    )
    if re.search(missing_prefix + r"[^。；;|]{0,36}" + judgment_terms, text):
        return True
    if re.search(judgment_terms + r"[^。；;|]{0,24}(?:不详|不明确|缺失|缺少|待确认|需确认|未见|未明确)", text):
        return True
    if re.search(r"研究者虽嘱[^。；;|]{0,30}但未明确[^。；;|]{0,40}(?:判断|评估|确认|具备|不具备|适合|不适合)", text):
        return True
    if re.search(r"(?:疗效|安全性原因|依从性|自杀风险)[^。；;|]{0,18}(?:不详|不明确|未见|未明确|缺少|待确认|需确认)", text):
        return True
    if re.search(r"(?:未见|未明确|缺少)[^。；;|]{0,18}(?:疗效不佳|安全性原因停药|影响用药依从性|自杀风险)", text):
        return True
    return False


def _has_global_ie_substitution_for_researcher_component(result: ReviewResult) -> bool:
    """Detect a pass that uses aggregate IE wording instead of rule-specific judgment."""
    if result.rule_type != "exclusion":
        return False
    text = f"{result.rule_name} {result.reasoning or ''}"
    if _has_explicit_unfavorable_researcher_judgment(result.reasoning or ""):
        return False
    global_ie = (
        r"(?:符合(?:所有)?入排标准|初步符合入排|整体符合入排|符合入组标准|可入组|可以入组|"
        r"可以进入研究|进入研究|不符合(?:任一|所有)?排除标准|未触发(?:任一|所有)?排除标准|"
        r"发放导入期药物|发放研究药物|整体可接受)"
    )
    if not re.search(global_ie, text):
        return False
    abnormal_or_cs = (
        r"(?:异常|升高|降低|阳性|CS|有临床意义|临床显著|肝功能不全|血脂异常|高胆固醇|"
        r"AST|ALT|GGT|LDL|胆固醇|甘油三酯|尿糖|潜血|蛋白尿)"
    )
    if not re.search(abnormal_or_cs, text, re.IGNORECASE):
        return False
    needs_specific_judgment = (
        _rule_requires_explicit_unfavorable_researcher_component(result)
        or re.search(
            r"(?:有临床意义|CS|临床显著|异常)[^。；;|]{0,42}"
            r"(?:不适合|不具备|不可接受风险|影响研究评估|安全性风险|研究者(?:判断|评估|认为|确认))",
            text,
        )
        or re.search(
            r"(?:不适合|不具备|不可接受风险|影响研究评估|安全性风险|研究者(?:判断|评估|认为|确认))"
            r"[^。；;|]{0,42}(?:有临床意义|CS|临床显著|异常)",
            text,
        )
    )
    return bool(needs_specific_judgment)


def _is_fev1_threshold_rule(result: ReviewResult) -> bool:
    text = f"{result.rule_id} {result.rule_name} {result.reasoning or ''}"
    return bool(re.search(r"(FEV1|一秒用力呼气量|肺功能|预计值百分比|%pred|支气管舒张剂)", text, re.IGNORECASE))


def _has_fev1_interpretable_numeric_support(reasoning: str) -> bool:
    text = reasoning or ""
    if re.search(
        r"(FEV1|一秒用力呼气量)[^。；;\n|]{0,60}(占预计值|预计值百分比|%pred|预测值百分比)[^。；;\n|]{0,32}"
        r"(?:为|=|:|：|>|≥|大于|高于)?\s*\d{2,3}(?:\.\d+)?\s*%?",
        text,
        re.IGNORECASE,
    ):
        return True
    if re.search(
        r"(占预计值|预计值百分比|%pred|预测值百分比)[^。；;\n|]{0,20}"
        r"(?:为|=|:|：|>|≥|大于|高于)?\s*\d{2,3}(?:\.\d+)?\s*%?[^。；;\n|]{0,30}(FEV1|一秒用力呼气量)",
        text,
        re.IGNORECASE,
    ):
        return True
    if re.search(r"(FEV1|一秒用力呼气量)[^。；;\n|]{0,40}(>|≥|大于|高于)\s*50\s*%", text, re.IGNORECASE):
        return True
    return False


def _is_historical_diagnosis_duration_rule(result: ReviewResult) -> bool:
    text = f"{result.rule_id} {result.rule_name}"
    return bool(
        result.rule_id == "IN-02"
        or re.search(r"(诊断|病史|病程|季节性过敏性鼻炎|SAR|银屑病病程|既往明确病史)", text)
    )


def _has_screening_only_history_duration_support(reasoning: str) -> bool:
    text = reasoning or ""
    historical_claim = re.search(
        r"(自\s*20\d{2}\s*年.{0,24}(开始|出现)|于\s*20\d{2}\s*年.{0,18}(确诊|诊断)|"
        r"(病史|病程|症状|诊断)[^。；;\n|]{0,18}自\s*20\d{2}\s*年[^。；;\n|]{0,24}(起|至今|以来|≥|大于|超过)|"
        r"(病史|病程|症状|诊断)[^。；;\n|]{0,18}\d+\s*年\s*(余|以上|起|以来|至今)?|"
        r"病史\s*[≥>大于不少于]*\s*\d+\s*年|病程\s*[≥>大于不少于]*\s*\d+\s*年|"
        r"病史≥?2年|病程≥?2年)",
        text,
    )
    if not historical_claim:
        return False
    if re.search(r"(溯源|需验证|需补充.{0,8}(既往|诊断|源文件)|病史来源)", text):
        return False
    if re.search(r"(既往病历|既往源文件|诊断证明|出院小结|既往检查|既往处方|门诊病历|住院病历)", text):
        return False
    if re.search(r"(主诉|现病史)[^。；;\n|]{0,36}\d+\s*年余", text) and re.search(r"(既往|门诊|住院|病历)", text):
        return False
    if re.search(r"(筛选[-—–]?基线病历|筛选病历|基线病历|研究病历|病历转述)", text):
        return True
    return True


def _has_fev1_vague_or_missing_support(reasoning: str) -> bool:
    text = reasoning or ""
    return bool(
        re.search(
            r"(OCR|肺功能|报告|数值|FEV1|预计值百分比)[^。；;\n|]{0,40}"
            r"(模糊|不完整|不明确|缺失|缺少|未提供|未见|未提示|未能|无法|不能|不可读)",
            text,
            re.IGNORECASE,
        )
        or re.search(
            r"(模糊|不完整|不明确|缺失|缺少|未提供|未见|未提示|未能|无法|不能|不可读)"
            r"[^。；;\n|]{0,40}(OCR|肺功能|报告|数值|FEV1|预计值百分比)",
            text,
            re.IGNORECASE,
        )
    )


def _rule_requires_explicit_unfavorable_researcher_component(result: ReviewResult) -> bool:
    """Detect D001-style compound exclusions that require an adverse judgment.

    These exclusions are not triggered by the clinical fact alone. The model
    often writes a plausible fact and then adds "triggered"; this gate requires
    the rule-specific adverse investigator component to be present too.
    """
    rule_header = f"{result.rule_id} {result.rule_name}"
    text = f"{rule_header} {result.reasoning or ''}"
    if re.search(r"(随机前|基线前|给药前|洗脱|半衰期|用药/治疗史|特定时间窗内用药)", rule_header):
        return False
    patterns = [
        r"其他.{0,8}皮肤病|影响评估|影响研究评估",
        r"慢性.{0,4}复发性.{0,8}感染|增加.{0,8}安全性风险",
        r"重大.{0,4}不稳定.{0,8}系统性疾病|不具备临床研究条件",
        r"(?:其它|其他).{0,8}实验室|实验室检查.{0,16}(?:有临床意义|不适合|不可接受|研究者判断)",
        r"有临床意义.{0,20}(?:不适合入组|研究者判断|不可接受风险)",
        r"精神.{0,8}疾病|影响用药依从性|自杀风险",
        r"IL-12|IL-17|IL-23|靶向药物.{0,12}疗效不佳",
        r"生命体征|体格检查|心电图|ECG|胸部CT|不可接受.{0,8}风险",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _has_incomplete_researcher_compound_logic(result: ReviewResult) -> bool:
    """A fact plus a required researcher judgment is incomplete if that judgment is missing."""
    reasoning = result.reasoning or ""
    if _is_systemic_disease_researcher_rule(result):
        if _has_missing_required_researcher_judgment(reasoning):
            return True
        if _has_ex11_specific_unfavorable_judgment(reasoning):
            return False
        return _rule_requires_explicit_unfavorable_researcher_component(result)
    if _has_explicit_unfavorable_researcher_judgment(reasoning):
        return False
    if _has_missing_required_researcher_judgment(reasoning):
        return True
    return _rule_requires_explicit_unfavorable_researcher_component(result)


def _neutralize_definitive_fail_wording(reasoning: str) -> str:
    """Remove hard-fail wording when parser downgrades a rule to review-needed."""
    text = reasoning or ""
    replacements = [
        (r"应按不通过处理", "需进一步评估"),
        (r"因此不通过", "因此需研究者评估"),
        (r"判定为不通过", "需研究者判断"),
        (r"尿检异常且有临床意义", "尿检异常"),
        (r"尿糖阳性已触发排除", "尿糖阳性需结合方案完整条件判断"),
        (r"此为活动性实验室异常，需研究者判断是否为急性疾病状态", "尿糖/潜血等尿检异常不能直接证明活动性感染或急性疾病状态"),
        (r"鉴于尿检异常，需进一步评估，除非后续补充明确排除证据", "尿检异常可转入相关实验室或泌尿系统风险评估，不能直接触发EX-07"),
        (r"病历主观否认与检验客观异常冲突", "病历否认活动性感染；尿检异常与EX-07主题不直接等同"),
        (r"且未排除临床意义，因此需研究者评估", "但尚未见研究者明确判断有临床意义及参与研究将构成不可接受风险"),
        (r"属于方案规定的有临床意义的实验室异常", "属于需结合方案完整条件判断的实验室异常"),
        (r"其存在已触发排除", "需结合方案完整条件判断"),
        (r"已构成明确的排除标准触发", "仍需按方案完整条件复核"),
        (r"硬性指标不通过", "仍需复核完整触发条件"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text


def _parent_rule_id(rule_id: str) -> Optional[str]:
    match = re.match(r"^((?:IN|EX)-\d+)$", rule_id or "")
    return match.group(1) if match else None


def _child_parent_rule_id(rule_id: str) -> Optional[str]:
    match = re.match(r"^((?:IN|EX)-\d+)[A-Za-z].*$", rule_id or "")
    return match.group(1) if match else None


def _referenced_rule_ids(text: str) -> set[str]:
    return set(RULE_ID_PATTERN.findall(text or ""))


def _format_child_id_list(children: List[ReviewResult], verdicts: set[str]) -> str:
    ids = [child.rule_id for child in children if child.verdict in verdicts]
    if not ids:
        return ""
    suffix = "等" if len(ids) > 8 else ""
    return "、".join(ids[:8]) + suffix


def _build_parent_reasoning(parent: ReviewResult, children: List[ReviewResult]) -> str:
    fail_ids = _format_child_id_list(children, {"fail"})
    if fail_ids:
        return f"父级汇总项，结论仅由同一父级子项决定：{fail_ids}明确不通过。"
    insufficient_ids = _format_child_id_list(children, {"insufficient"})
    investigator_ids = _format_child_id_list(children, {"investigator"})
    verify_ids = _format_child_id_list(children, {"pass_verify"})
    parts = []
    if insufficient_ids:
        parts.append(f"{insufficient_ids}证据不足")
    if investigator_ids:
        parts.append(f"{investigator_ids}需研究者判定")
    if verify_ids:
        parts.append(f"{verify_ids}为溯源或后续阶段复核提醒")
    if parts:
        return "父级汇总项，结论仅由同一父级子项决定：" + "；".join(parts) + "。"
    return "父级汇总项，同一父级子项均未见触发或不适用。"


def _reconcile_parent_rule_results(rule_results: List[ReviewResult]) -> bool:
    """Recompute parent rows from same-prefix children only.

    Rule IDs are reused across protocols, and the LLM can leak an adjacent
    child ID into a parent summary. A parent such as EX-07 must only summarize
    EX-07a/EX-07b/... rows, never EX-09g or another protocol's hard-coded ID
    semantics.
    """
    children_by_parent: dict[str, list[ReviewResult]] = {}
    by_id: dict[str, ReviewResult] = {}
    for result in rule_results:
        by_id[result.rule_id] = result
        child_parent = _child_parent_rule_id(result.rule_id)
        if child_parent:
            children_by_parent.setdefault(child_parent, []).append(result)

    changed = False
    for parent_id, children in children_by_parent.items():
        parent = by_id.get(parent_id)
        if parent is None:
            continue
        computed = "na"
        for child in children:
            computed = _more_conservative_verdict(computed, child.verdict)
        allowed_refs = {parent_id, *(child.rule_id for child in children)}
        external_refs = _referenced_rule_ids(parent.reasoning) - allowed_refs
        if parent.verdict != computed or external_refs:
            parent.verdict = computed
            parent.reasoning = _build_parent_reasoning(parent, children)
            changed = True
    return changed


def _has_unconfirmed_clinical_significance_fail(reasoning: str) -> bool:
    """Detect fail conclusions based on possible, not explicit, clinical significance."""
    text = reasoning or ""
    if _has_incomplete_ex20h_all_of_logic(text):
        return True
    if _has_explicit_clinical_significance_source(text):
        return False
    if re.search(r"(未排除|不能排除|尚未排除|未明确排除).{0,16}(临床意义|安全性风险|不可接受风险)", text):
        return True
    if re.search(r"(需|需要|待|尚需).{0,8}(研究者|医生|PI|医学监查).{0,12}(评估|判断|确认).{0,16}(临床意义|安全性风险|不可接受风险)", text):
        return True
    if re.search(r"(除非后续|待后续|需补充).{0,18}(排除证据|明确排除|研究者确认|临床意义)", text):
        return True
    if _mentions_ex20h_other_lab(text) and not _has_explicit_unacceptable_risk_source(text):
        return True
    return False


def _has_missing_current_phase_required_evidence(reasoning: str) -> bool:
    """Detect current-stage required evidence gaps masquerading as hard fail."""
    text = reasoning or ""
    if not re.search(r"(基线|D1|随机前|当前阶段)", text, re.IGNORECASE):
        return False
    return bool(
        re.search(
            r"(缺失|未提供|未见|未显示有效|无法确证|无法确认|不能确认|需等待|待补充|证据不足).{0,28}"
            r"(基线|D1|随机前|复测|结果|报告|记录|源文件|血生化|血常规|日志卡|评分|证明)",
            text,
            re.IGNORECASE,
        )
        or re.search(
            r"(基线|D1|随机前|复测|结果|报告|记录|源文件|血生化|血常规|日志卡|评分).{0,28}"
            r"(缺失|未提供|未见|未显示有效|无法确证|无法确认|不能确认|需等待|待补充|证据不足|不可读|无法读取|无法提取|未能提取|OCR严重损坏)",
            text,
            re.IGNORECASE,
        )
        or re.search(
            r"(不可读|无法读取|无法提取|未能提取|OCR严重损坏).{0,28}"
            r"(基线|D1|随机前|复测|结果|报告|记录|源文件|血生化|血常规|日志卡|评分|EOS|EO#)",
            text,
            re.IGNORECASE,
        )
        or re.search(
            r"无.{0,18}(其余|其它|其他)?(D1|基线|随机前|复测).{0,18}(报告|结果|记录|证明|证据)",
            text,
            re.IGNORECASE,
        )
    )


def _mentions_explicit_current_phase_requirement(text: str) -> bool:
    """Return true for actual baseline/randomization requirements, not source labels."""
    normalized = re.sub(r"筛选[-—–]基线", "筛选基线", text or "")
    return bool(
        re.search(
            r"(基线时|随机时|D1|随机前|基线前|给药前|当前阶段|本阶段|导入期间|导入期).{0,40}"
            r"(必须|需要|需|要求|应|结果|报告|记录|评分|依从性|洗脱|时间窗|确认|复核|评估)",
            normalized,
            re.IGNORECASE,
        )
        or re.search(
            r"(必须|需要|需|要求|应).{0,24}(基线时|随机时|D1|随机前|基线前|给药前|当前阶段|本阶段|导入期间|导入期)",
            normalized,
            re.IGNORECASE,
        )
    )


def _has_current_phase_pass_with_missing_required_evidence(reasoning: str) -> bool:
    """Detect pass conclusions that acknowledge a reached baseline/D1 evidence gap."""
    text = reasoning or ""
    if not _mentions_explicit_current_phase_requirement(text):
        return False
    if _has_missing_current_phase_required_evidence(text):
        return True
    return bool(
        re.search(
            r"(仅|只有|目前|当前|本次|证据包中)?[^。；;\n]{0,20}(筛选期|筛选)[^。；;\n]{0,40}"
            r"(基线|D1|随机前|给药前)[^。；;\n]{0,40}"
            r"(缺失|缺少|未提供|未见|无|待|需.{0,6}(确认|复核))",
            text,
            re.IGNORECASE,
        )
        or re.search(
            r"(基线|D1|随机前|给药前)[^。；;\n]{0,40}"
            r"(缺失|缺少|未提供|未见|无|待|需.{0,6}(确认|复核))[^。；;\n]{0,40}"
            r"(筛选期|筛选)",
            text,
            re.IGNORECASE,
        )
        or re.search(
            r"(基线|D1|随机前|给药前)[^。；;\n]{0,24}"
            r"(独立|正式|源文件|报告|记录|结果)[^。；;\n]{0,18}(缺失|缺少|未提供|未见|无)",
            text,
            re.IGNORECASE,
        )
    )


def _has_random_window_date_substitution_without_anchor(reasoning: str) -> bool:
    """Detect random-window passes that rely on guessed dates rather than an anchor."""
    text = reasoning or ""
    if not re.search(r"(随机前|基线前|给药前|随机日|随机日期|半衰期|洗脱期)", text, re.IGNORECASE):
        return False
    return bool(
        re.search(r"(距|距离).{0,8}(随机日|随机日期|基线日|给药日).{0,12}(约|推测|推断|估计)", text)
        or re.search(r"(随机日|随机日期|基线日|给药日)[（(]?(约|推测|推断|估计)", text)
        or re.search(
            r"(用|以|按).{0,12}(筛选日期|筛选期|报告日期|采样日期|检测日期|就诊日期).{0,18}"
            r"(替代|作为|推定|推测).{0,12}(随机|基线|给药)",
            text,
            re.IGNORECASE,
        )
    )


def _has_missing_conmed_log_with_explicit_time_window_denials(reasoning: str) -> bool:
    """Detect conmed-log absence when source notes explicitly deny prohibited use.

    A separate concomitant-medication log is good traceability, but if a source
    medical record explicitly denies the protocol-relevant prohibited medication
    or treatment categories within the matching time windows, absence of the
    standalone log must not become evidence insufficiency by itself.
    """
    text = reasoning or ""
    if not re.search(r"(未提供|缺少|缺失|未见).{0,18}(合并用药|用药记录|用药记录表|合并治疗|伴随用药)", text):
        return False
    if not re.search(r"(否认|未使用|未接受|未接种|无.{0,8}使用|无.{0,8}接受).{0,48}(近|随机前|基线前|给药前|周|月|半衰期|天)", text):
        return False
    prohibited_terms = (
        r"(免疫抑制剂|全身性免疫抑制|免疫治疗|变应原特异性免疫治疗|脱敏治疗|"
        r"活疫苗|减毒活疫苗|生物制剂|抗体|糖皮质激素|禁用药|禁止用药|禁止治疗|方案列明)"
    )
    return bool(re.search(prohibited_terms, text, re.IGNORECASE))


def _has_positive_washout_medication_uncertainty(reasoning: str) -> bool:
    """Detect actual prohibited/biologic exposure needing washout judgment.

    Explicit denials for other subitems must not wipe out a positive exposure
    history for a different washout subitem.
    """
    text = reasoning or ""
    positive_exposure = re.search(
        r"(使用|接受|注射|给药|末次|用药史显示|记录曾使用)[^。；;\n|]{0,100}"
        r"(单抗|生物制剂|抗IL|IL[-‑]4R|抗IgE|奥马珠|司普奇拜|度普利尤|TSLP|IgE)",
        text,
        re.IGNORECASE,
    )
    if not positive_exposure:
        return False
    uncertainty = re.search(
        r"(半衰期|洗脱|随机前|时间窗|10周|5个半衰期|子项f)[^。；;\n|]{0,100}"
        r"(未知|不明确|未明确|不确定|未提供|缺少|缺失|需|需要|待|判断|评估|确认|核实|计算)",
        text,
        re.IGNORECASE,
    ) or re.search(
        r"(需|需要|待|未提供|未明确|不明确|未知|不确定)[^。；;\n|]{0,60}"
        r"(半衰期|洗脱|随机前|时间窗|10周|5个半衰期|研究者判断|计算)",
        text,
        re.IGNORECASE,
    )
    return bool(uncertainty)


def _evidence_bundle_has_matching_denial_for_rule(result: ReviewResult, evidence_bundle: str) -> bool:
    """Return true when the source bundle contains denial evidence for this washout rule."""
    rule_text = f"{result.rule_id} {result.rule_name} {result.reasoning}"
    evidence = evidence_bundle or ""
    if not evidence:
        return False
    if not re.search(r"(合并|伴随|禁用|禁止|洗脱|用药|治疗|疫苗|糖皮质激素|免疫)", rule_text):
        return False

    rule_term_groups = [
        (r"(糖皮质激素|激素|中药)", r"(糖皮质激素|全身性长效糖皮质激素|中、短效全身性糖皮质激素|治疗AR的全身性中药制剂|中药制剂)"),
        (r"(免疫抑制|自身免疫|炎症性疾病)", r"(免疫抑制剂|全身性免疫抑制剂|治疗炎症性疾病|自身免疫性疾病)"),
        (r"(免疫治疗|变应原|脱敏)", r"(免疫治疗|变应原特异性免疫治疗|脱敏治疗)"),
        (r"(疫苗|活疫苗|减毒)", r"(活疫苗|减毒活疫苗|接种)"),
    ]
    source_term_pattern = ""
    for rule_pat, source_pat in rule_term_groups:
        if re.search(rule_pat, rule_text, re.IGNORECASE):
            source_term_pattern = source_pat
            break
    if not source_term_pattern:
        return False

    denial_pattern = (
        r"(否认|未使用|未接受|未接种|无[^。；;\n]{0,8}使用|无[^。；;\n]{0,8}接受)"
        r"[^。；;\n]{0,80}(近|随机前|基线前|给药前|周|月|半衰期|天)"
        r"[^。；;\n]{0,120}" + source_term_pattern
    )
    reverse_denial_pattern = (
        source_term_pattern
        +
        r"[^。；;\n]{0,120}(否认|未使用|未接受|未接种|无[^。；;\n]{0,8}使用|无[^。；;\n]{0,8}接受)"
    )
    return bool(
        re.search(denial_pattern, evidence, re.IGNORECASE)
        or re.search(reverse_denial_pattern, evidence, re.IGNORECASE)
    )


def _apply_explicit_conmed_denial_adjustments(rule_results: List[ReviewResult]) -> bool:
    changed = False
    for result in rule_results:
        if result.verdict not in {"insufficient", "investigator"}:
            continue
        text = f"{result.rule_id} {result.rule_name} {result.reasoning}"
        if _has_positive_washout_medication_uncertainty(result.reasoning):
            continue
        if not re.search(r"(合并|伴随|禁用|禁止|洗脱|用药|治疗|疫苗)", text):
            continue
        if not _has_missing_conmed_log_with_explicit_time_window_denials(result.reasoning):
            continue
        result.verdict = "pass_verify"
        result.reasoning = (
            result.reasoning.rstrip("。；; ")
            + "。单独合并用药记录表缺失不应作为证据不足；现有源文件已明确否认相关禁用用药/治疗类别并覆盖对应时间窗，按通过处理，保留溯源提醒以便归档时核对合并用药记录表。"
        )
        changed = True
    return changed


def _apply_evidence_bundle_conmed_denial_adjustments(
    rule_results: List[ReviewResult],
    evidence_bundle: str,
) -> bool:
    """Use the evidence bundle to prevent standalone conmed-log gaps becoming insufficiency."""
    changed = False
    for result in rule_results:
        if result.verdict not in {"insufficient", "investigator"}:
            continue
        if _has_positive_washout_medication_uncertainty(result.reasoning):
            continue
        if not re.search(r"(合并用药记录|用药记录|合并治疗|伴随用药|无法核实|未提供|缺失|未见)", result.reasoning or ""):
            continue
        if not _evidence_bundle_has_matching_denial_for_rule(result, evidence_bundle):
            continue
        result.verdict = "pass_verify"
        result.reasoning = (
            result.reasoning.rstrip("。；; ")
            + "。证据包中已有筛选/基线源文件明确否认本条相关禁用用药/治疗类别及时间窗；缺少单独合并用药记录表不单独构成证据不足，按通过处理并保留溯源提醒。"
        )
        changed = True
    return changed


def apply_missing_phase_anchor_date_adjustments(
    rule_results: List[ReviewResult],
    review_phase: Optional[Union[Dict[str, object], str]],
    anchor_dates: Dict[str, str],
) -> bool:
    """Do not let screening/report dates substitute for baseline/randomization anchors."""
    if isinstance(review_phase, dict):
        phase_info = review_phase
    else:
        phase_info = phase_by_id({"review_phases": []}, review_phase or "full")
    if not _phase_requires_randomization_anchor(phase_info):
        return False
    if str(anchor_dates.get("review_phase_anchor_date") or "").strip():
        return False

    changed = False
    for result in rule_results:
        reasoning = result.reasoning or ""
        if result.verdict != "fail":
            continue
        if not re.search(r"(随机前|基线前|给药前)", f"{result.rule_name} {reasoning}"):
            continue
        if not re.search(r"(筛选日期|至筛选|筛选期|报告日期|打印日期|就诊日期)", reasoning):
            continue
        result.verdict = "insufficient"
        result.reasoning = (
            _neutralize_definitive_fail_wording(reasoning).rstrip("。；; ")
            + "。本条依赖基线/随机前/给药前时间窗，但本次审核未提供基线/随机前锚点日期，证据中也未明确等价随机/给药日期；不得用筛选日期、报告日期或打印日期替代，应补充锚点日期后复核。"
        )
        changed = True
    return changed


def apply_current_phase_required_evidence_adjustments(
    rule_results: List[ReviewResult],
    review_phase: Optional[Union[Dict[str, object], str]],
    anchor_dates: Dict[str, str],
) -> bool:
    """Reached baseline/randomization rules cannot pass on screening-only evidence.

    The earlier guard only handled false hard-fail conclusions caused by missing
    randomization anchors. The reciprocal risk is a false pass: a rule says
    "baseline/D1/randomization" but the reasoning admits that only screening
    evidence exists. Keep this generic so it protects any protocol with staged
    eligibility, not a single MG-K10 rule ID.
    """
    if isinstance(review_phase, dict):
        phase_info = review_phase
    else:
        phase_info = phase_by_id({"review_phases": []}, review_phase or "full")
    if not _phase_requires_randomization_anchor(phase_info):
        return False

    has_anchor = bool(str(anchor_dates.get("review_phase_anchor_date") or "").strip())
    changed = False
    for result in rule_results:
        if result.verdict not in {"pass", "pass_verify"}:
            continue
        reasoning = result.reasoning or ""
        rule_text = f"{result.rule_name} {reasoning}"
        has_current_requirement = _mentions_explicit_current_phase_requirement(rule_text)
        has_random_anchor_substitution = (
            not has_anchor and _has_random_window_date_substitution_without_anchor(reasoning)
        )
        if not has_current_requirement and not has_random_anchor_substitution:
            continue
        if has_current_requirement and _has_current_phase_pass_with_missing_required_evidence(reasoning):
            result.verdict = "insufficient"
            if "当前阶段关键证据缺失" not in reasoning:
                result.reasoning = (
                    reasoning.rstrip("。；; ")
                    + "。当前阶段关键证据缺失：本条要求基线/D1/随机前源文件或结果时，不能用筛选期结果替代普通通过；应补充对应当前阶段源文件后复核。"
                )
            changed = True
            continue
        if has_random_anchor_substitution:
            result.verdict = "insufficient"
            result.reasoning = (
                _neutralize_definitive_fail_wording(reasoning).rstrip("。；; ")
                + "。本条依赖随机前/基线前/给药前时间窗，但本次审核未提供基线/随机前锚点日期，且推理中使用了约略或推定的随机/基线日期；不得用推定日期替代，应补充锚点日期后复核。"
            )
            changed = True
    return changed


def _apply_reasoning_verdict_consistency_adjustments(rule_results: List[ReviewResult]) -> bool:
    """Guard against semantic conflicts between the verdict cell and reasoning.

    The root failure mode is not a display typo. For complex exclusion criteria,
    the model can confuse "an abnormal/mentioned component exists" with
    "the protocol-defined exclusion trigger is met". The guard therefore checks
    the trigger semantics in the reasoning and only changes a fail cell when no
    definitive trigger is stated.
    """
    changed = False
    for result in rule_results:
        reasoning = result.reasoning or ""
        if (
            _is_systemic_disease_researcher_rule(result)
            and "不可接受" in reasoning
            and "不具备临床研究条件" not in reasoning
        ):
            result.reasoning = _normalize_ex11_component_wording(reasoning)
            changed = True
            reasoning = result.reasoning
        if (
            re.search(r"(梅毒|TPPA|TP-Ab|Anti-TP|TRUST|RPR)", f"{result.rule_name} {reasoning}", re.IGNORECASE)
            and result.verdict in {"pass", "pass_verify", "na"}
            and _has_incomplete_syphilis_exception_logic(reasoning)
        ):
            result.verdict = "investigator"
            reasoning = _neutralize_syphilis_exception_wording(reasoning)
            if "梅毒特异性抗体阳性" not in reasoning or "既往感染已治愈" not in reasoning:
                result.reasoning = (
                    reasoning.rstrip("。；; ")
                    + "。梅毒特异性抗体阳性不能因TRUST/RPR阴性单独按例外通过；方案例外还需研究者明确判断既往感染已治愈，当前依据未完整证明该例外。"
                )
            else:
                result.reasoning = reasoning
            changed = True
            continue
        if (
            re.search(r"(梅毒|TPPA|TP-Ab|Anti-TP|TRUST|RPR)", f"{result.rule_name} {reasoning}", re.IGNORECASE)
            and result.verdict == "fail"
            and _has_incomplete_syphilis_exception_logic(reasoning)
        ):
            result.verdict = "investigator"
            reasoning = _neutralize_definitive_fail_wording(_neutralize_syphilis_exception_wording(reasoning))
            if "不能因缺少“既往感染已治愈”判断而直接硬判不通过" not in reasoning:
                result.reasoning = (
                    reasoning.rstrip("。；; ")
                    + "。梅毒特异性抗体阳性不能因缺少“既往感染已治愈”判断而直接硬判不通过；当前也不能按例外通过，需研究者明确既往感染已治愈/当前非活动性感染状态后复核。"
                )
            else:
                result.reasoning = reasoning
            changed = True
            continue
        if (
            result.rule_type == "exclusion"
            and result.verdict in {"investigator", "insufficient"}
            and _child_parent_rule_id(result.rule_id)
            and (_referenced_rule_ids(reasoning) - {result.rule_id})
        ):
            positive_at = _last_semantic_index(POSITIVE_TRIGGER_PATTERNS, reasoning)
            negative_at = _last_semantic_index(NEGATIVE_TRIGGER_PATTERNS, reasoning)
            if negative_at >= 0 and (positive_at < 0 or negative_at >= positive_at or positive_at - negative_at <= 20):
                result.verdict = "pass"
                if "其他子项另行审核" not in reasoning:
                    result.reasoning = (
                        reasoning.rstrip("。；; ")
                        + "。本子项仅按自身触发条件判定，其他子项另行审核。"
                    )
                changed = True
                continue
        if (
            result.verdict in {"pass", "pass_verify", "na"}
            and _is_fev1_threshold_rule(result)
            and (
                not _has_fev1_interpretable_numeric_support(reasoning)
                or _has_fev1_vague_or_missing_support(reasoning)
            )
        ):
            result.verdict = "insufficient"
            if "FEV1占预计值百分比需要可解释数值证据" not in reasoning:
                result.reasoning = (
                    reasoning.rstrip("。；; ")
                    + "。FEV1占预计值百分比需要可解释数值证据；肺功能报告OCR模糊、数值不完整或仅写未提示异常，不能支撑本条普通通过，应补充可读肺功能源文件或结构化数值后复核。"
                )
            changed = True
            continue
        if (
            result.verdict == "pass"
            and result.rule_type == "inclusion"
            and _is_historical_diagnosis_duration_rule(result)
            and _has_screening_only_history_duration_support(reasoning)
        ):
            result.verdict = "pass_verify"
            if "病史来源需溯源验证" not in reasoning:
                result.reasoning = (
                    reasoning.rstrip("。；; ")
                    + "。病史来源需溯源验证：本条病程/既往确诊时长主要来自筛选或基线病历转述，未在推理依据中引用既往病历、诊断证明、既往处方或其它可追溯源文件；当前按通过处理并保留溯源提醒。"
                )
            changed = True
            continue
        if result.verdict in {"pass", "pass_verify", "na"} and _has_global_ie_substitution_for_researcher_component(result):
            result.verdict = "investigator"
            if "整体IE/可入组结论不能替代单条研究者判断" not in reasoning:
                result.reasoning = (
                    reasoning.rstrip("。；; ")
                    + "。整体IE/可入组结论不能替代单条研究者判断；该复合排除条款需研究者针对当前异常明确判断是否不适合入组、影响研究评估或构成不可接受风险，当前依据未完整证明，应按需研究者判定处理。"
                )
            changed = True
            continue
        if result.verdict != "fail":
            continue
        if result.rule_id == "EX-07" and _has_ex07_unrelated_lab_substitution(reasoning):
            result.verdict = "investigator"
            reasoning = _neutralize_definitive_fail_wording(reasoning)
            if not re.search(r"(尿糖/潜血等尿检异常|尿检异常).{0,12}不能直接证明活动性感染或急性疾病状态", reasoning):
                result.reasoning = (
                    reasoning.rstrip("。；; ")
                    + "。尿糖/潜血等尿检异常不能直接证明活动性感染或急性疾病状态；如认为该尿检异常有临床意义，应转入相关实验室或泌尿系统风险条款由研究者评估。"
                )
            else:
                result.reasoning = reasoning
            changed = True
            continue
        if _has_missing_current_phase_required_evidence(reasoning):
            result.verdict = "insufficient"
            reasoning = _neutralize_definitive_fail_wording(reasoning)
            if "当前阶段关键证据缺失" not in reasoning:
                result.reasoning = (
                    reasoning.rstrip("。；; ")
                    + "。当前阶段关键证据缺失时不能直接判定不通过；需补充对应基线/D1/随机前源文件后复核。"
                )
            else:
                result.reasoning = reasoning
            changed = True
            continue
        if (
            not _has_ex20g_liver_analyte_substitution(reasoning)
            and not _has_unconfirmed_clinical_significance_fail(reasoning)
            and _has_incomplete_researcher_compound_logic(result)
        ):
            result.verdict = "investigator"
            reasoning = _neutralize_definitive_fail_wording(reasoning)
            if "疾病存在、异常存在或用药存在本身不等于完整排除触发" not in reasoning:
                result.reasoning = (
                    reasoning.rstrip("。；; ")
                    + "。疾病存在、异常存在或用药存在本身不等于完整排除触发；此类复合条款还需研究者明确判断不具备临床研究条件、影响研究评估、增加安全性风险、疗效不佳、影响用药依从性、有自杀风险、构成不可接受风险或其它方案规定的不利组件，当前依据未完整证明，应按需研究者判断处理。"
                )
            else:
                result.reasoning = reasoning
            changed = True
            continue
        if _has_ex20g_liver_analyte_substitution(reasoning):
            result.verdict = "investigator"
            reasoning = _neutralize_definitive_fail_wording(reasoning)
            reasoning = re.sub(
                r"(?:已超过[^，。；;]{0,60}，)?触发EX-20g标准",
                "不能据此触发EX-20g标准",
                reasoning,
            )
            if "GGT不能替代ALT/AST/总胆红素触发EX-20g" not in reasoning:
                result.reasoning = (
                    reasoning.rstrip("。；; ")
                    + "。GGT不能替代ALT/AST/总胆红素触发EX-20g；如认为该GGT异常有临床意义，应按其它实验室异常由研究者评估。"
                )
            else:
                result.reasoning = reasoning
            changed = True
            continue
        if _has_unconfirmed_clinical_significance_fail(reasoning):
            result.verdict = "investigator"
            reasoning = _neutralize_definitive_fail_wording(reasoning)
            if _mentions_ex20h_other_lab(reasoning):
                if "EX-20h等复合条款必须同时满足实验室异常、有临床意义和研究者不可接受风险评估" not in reasoning:
                    result.reasoning = (
                        reasoning.rstrip("。；; ")
                        + "。EX-20h等复合条款必须同时满足实验室异常、有临床意义和研究者不可接受风险评估；当前依据未完整证明这些合取组件，应由研究者结合原始异常及参与风险判断。"
                    )
                else:
                    result.reasoning = reasoning
            elif "当前依据不足以作为definitive不通过" not in reasoning:
                result.reasoning = (
                    reasoning.rstrip("。；; ")
                    + "。当前依据不足以作为definitive不通过；存在需确认、未明确或研究者评估事项时，本条应按需研究者判断处理。"
                )
            else:
                result.reasoning = reasoning
            changed = True
            continue
        positive_at = _last_semantic_index(POSITIVE_TRIGGER_PATTERNS, reasoning)
        negative_at = _last_semantic_index(NEGATIVE_TRIGGER_PATTERNS, reasoning)
        investigator_at = _last_semantic_index(INVESTIGATOR_PATTERNS, reasoning)
        if investigator_at >= 0 and investigator_at >= positive_at:
            result.verdict = "investigator"
            reasoning = _neutralize_definitive_fail_wording(reasoning)
            if "当前依据不足以作为definitive不通过" not in reasoning:
                result.reasoning = (
                    reasoning.rstrip("。；; ")
                    + "。当前依据不足以作为definitive不通过；存在需确认、未明确或研究者评估事项时，本条应按需研究者判断处理。"
                )
            else:
                result.reasoning = reasoning
            changed = True
        elif negative_at >= 0 and negative_at >= positive_at:
            result.verdict = "pass"
            changed = True
    return changed


def _parse_summary(text: str) -> str:
    match = re.search(r"###\s*总结论\s*\n(.*?)$", text, re.DOTALL)
    if not match:
        match = re.search(r"##\s*总结论\s*\n(.*?)$", text, re.DOTALL)
    if not match:
        report_match = re.search(r"##\s*审核结论\s*\n(.*?)(?:\n---|\Z)", text, re.DOTALL)
        if report_match:
            section = report_match.group(1).strip()
            lines = []
            for line in section.split("\n"):
                stripped = line.strip()
                if not stripped:
                    continue
                if re.search(r"(✅|❌|⚠️|可入组|不可入组|待补证|\*\*)", stripped) and len(stripped) <= 40:
                    continue
                lines.append(stripped)
            return "\n".join(lines)
    if not match:
        return ""
    section = match.group(1).strip()
    lines = section.split("\n")
    summary_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"判定结果[：:]", stripped):
            continue
        summary_lines.append(stripped)
    return "\n".join(summary_lines)


def _summary_conflicts_with_overall(summary: str, overall_verdict: str) -> bool:
    if overall_verdict == "fail":
        return False
    return bool(re.search(r"(不可入组|不符合入组|明确的不通过|构成不可入组|definitive|触发排除标准|触发EX-)", summary or "", re.IGNORECASE))


def _summary_uses_legacy_needs_evidence_wording(summary: str, overall_verdict: str) -> bool:
    if overall_verdict not in {"insufficient", "investigator"}:
        return False
    return bool(re.search(r"(待补证|补充资料或研究者判断|需补充资料或研究者判断)", summary or ""))


def is_future_phase_verify_reasoning(reasoning: str) -> bool:
    """Classify pass_verify caused by future baseline/D1/randomization components."""
    text = reasoning or ""
    return bool(
        re.search(r"(后续阶段复核|后续阶段待复核|基线待后续阶段复核|基线/D1/随机前尚未到达)", text)
        or (
            re.search(r"(基线|D1|随机前)", text)
            and re.search(r"(尚未|未到|未发生|待复核|后续阶段)", text)
        )
    )


def is_source_traceability_verify_reasoning(reasoning: str) -> bool:
    """Classify pass_verify caused by historical-source provenance gaps."""
    text = reasoning or ""
    return bool(re.search(r"(溯源|既往源文件|更早.{0,8}(病历|诊断|检查|处方)|病史来源)", text))


def pass_verify_label(reasoning: str) -> str:
    if is_future_phase_verify_reasoning(reasoning):
        return "通过（后续阶段复核）"
    if is_source_traceability_verify_reasoning(reasoning):
        return "通过（溯源提醒）"
    return "通过（需验证）"


def _build_reconciled_summary(rule_results: List[ReviewResult], overall_verdict: str) -> str:
    issue_results = [r for r in rule_results if r.verdict in {"insufficient", "investigator"}]
    verify_results = [r for r in rule_results if r.verdict == "pass_verify"]
    fail_results = [r for r in rule_results if r.verdict == "fail"]
    if overall_verdict == "fail" and fail_results:
        ids = "、".join(r.rule_id for r in fail_results[:5])
        suffix = "等" if len(fail_results) > 5 else ""
        return f"存在明确不符合项：{ids}{suffix}，当前判定为不可入组。"
    if overall_verdict == "insufficient":
        insufficient_results = [r for r in rule_results if r.verdict == "insufficient"]
        ids = "、".join(r.rule_id for r in insufficient_results[:8])
        suffix = "等" if len(insufficient_results) > 8 else ""
        return f"未见可直接确认的不可入组项；{ids}{suffix}证据不足，需要补充相应源文件或资料后复核。"
    if overall_verdict == "investigator":
        investigator_results = [r for r in rule_results if r.verdict == "investigator"]
        ids = "、".join(r.rule_id for r in investigator_results[:8])
        suffix = "等" if len(investigator_results) > 8 else ""
        return f"未见可直接确认的不可入组项；{ids}{suffix}已有资料仍需研究者或医学监查作明确判断。"
    if overall_verdict == "pass" and verify_results:
        future_results = [r for r in verify_results if is_future_phase_verify_reasoning(r.reasoning)]
        trace_results = [r for r in verify_results if not is_future_phase_verify_reasoning(r.reasoning)]
        parts = []
        if trace_results:
            ids = "、".join(r.rule_id for r in trace_results[:8])
            suffix = "等" if len(trace_results) > 8 else ""
            parts.append(f"{ids}{suffix}为溯源提醒")
        if future_results:
            ids = "、".join(r.rule_id for r in future_results[:8])
            suffix = "等" if len(future_results) > 8 else ""
            parts.append(f"{ids}{suffix}为后续阶段复核提醒")
        return f"当前未见不符合、证据不足或需研究者判定项，整体按可入组处理；{'；'.join(parts)}。"
    return "当前可见证据未提示不符合项，所有已审核条目均通过或不适用。"


def extract_rule_ids(criteria_rules: str) -> List[str]:
    """Extract unique rule IDs from the configured criteria, preserving order."""
    seen: set[str] = set()
    rule_ids: List[str] = []
    for match in RULE_ID_PATTERN.finditer(criteria_rules or ""):
        rid = match.group(0)
        if rid not in seen:
            seen.add(rid)
            rule_ids.append(rid)
    return rule_ids


def extract_rule_titles(criteria_rules: str) -> Dict[str, str]:
    """Extract rule titles from markdown headings for fallback coverage rows."""
    titles: Dict[str, str] = {}
    for line in (criteria_rules or "").splitlines():
        match = re.match(r"^\s*#{2,6}\s*((?:IN|EX)-[A-Za-z0-9_.-]+)\s+(.+?)\s*$", line)
        if match:
            rid, title = match.groups()
            titles[rid] = title.strip()
    return titles


def _missing_expected_rule_ids(rule_results: List[ReviewResult], expected_rule_ids: List[str]) -> List[str]:
    present = {result.rule_id for result in rule_results}
    return [rid for rid in expected_rule_ids if rid not in present]


def _append_missing_rule_placeholders(
    rule_results: List[ReviewResult],
    missing_rule_ids: List[str],
    rule_titles: Dict[str, str],
) -> bool:
    if not missing_rule_ids:
        return False
    for rid in missing_rule_ids:
        rule_results.append(
            ReviewResult(
                rule_id=rid,
                rule_name=rule_titles.get(rid, "模型漏审规则"),
                rule_type="inclusion" if rid.startswith("IN-") else "exclusion",
                verdict="insufficient",
                reasoning="LLM输出缺少本条官方规则ID，系统已按证据不足处理；需重新审核或人工复核，不能把漏审视为通过。",
            )
        )
    return True


def parse_review_response(raw_response: str) -> dict:
    rule_results = _merge_duplicate_rule_results(_parse_rule_table(raw_response))
    group_results = _parse_group_table(raw_response)
    adjusted = _insert_missing_parent_rule_results(rule_results)
    adjusted = _apply_explicit_conmed_denial_adjustments(rule_results) or adjusted
    adjusted = _apply_reasoning_verdict_consistency_adjustments(rule_results) or adjusted
    adjusted = _reconcile_parent_rule_results(rule_results) or adjusted
    overall_verdict = _parse_overall_verdict(raw_response)
    overall_verdict = _recalculate_overall_verdict(rule_results, group_results, overall_verdict)
    summary = _parse_summary(raw_response)
    if (
        not summary
        or adjusted
        or _summary_uses_legacy_needs_evidence_wording(summary, overall_verdict)
        or _summary_conflicts_with_overall(summary, overall_verdict)
    ):
        summary = _build_reconciled_summary(rule_results, overall_verdict)
    logger.info(
        "Parsed LLM response: verdict=%s, %d rules, %d groups",
        overall_verdict, len(rule_results), len(group_results),
    )
    return {
        "overall_verdict": overall_verdict,
        "summary": summary,
        "rule_results": rule_results,
        "group_results": group_results,
    }


def _phase_id_from_review_phase(review_phase: Optional[Union[Dict[str, object], str]]) -> str:
    if isinstance(review_phase, dict):
        return str(review_phase.get("phase_id") or "")
    return str(review_phase or "")


def _phase_requires_randomization_anchor(phase_info: Dict[str, object]) -> bool:
    phase_text = " ".join(
        str(phase_info.get(key) or "")
        for key in ("phase_id", "name", "visit", "day_window", "description")
    )
    if re.search(r"(baseline|random|基线|随机|给药前|D1)", phase_text, re.IGNORECASE):
        return True
    return any(re.search(r"(随机|基线|给药前)", str(item or "")) for item in phase_info.get("required_items") or [])


def _recalculate_overall_verdict(
    rule_results: List[ReviewResult],
    group_results: List[GroupResult],
    current: str,
) -> str:
    if any(r.verdict == "fail" for r in rule_results) or any(g.verdict == "fail" for g in group_results):
        return "fail"
    if any(r.verdict == "insufficient" for r in rule_results) or any(g.verdict == "insufficient" for g in group_results):
        return "insufficient"
    if any(r.verdict == "investigator" for r in rule_results) or any(g.verdict == "investigator" for g in group_results):
        return "investigator"
    return "pass"


def apply_phase_timing_adjustments(
    rule_results: List[ReviewResult],
    review_phase: Optional[Union[Dict[str, object], str]],
) -> bool:
    """Prevent future baseline/D1 requirements from downgrading screening review."""
    if _phase_id_from_review_phase(review_phase) != "screening_run_in":
        return False
    changed = False
    future_timing_pattern = re.compile(r"(基线|D1|随机前).{0,16}(尚未|未到|未发生|待复核|后续阶段|尚未进行)")
    future_not_reached_pattern = re.compile(
        r"(尚未到|未到|尚未发生|尚未完成|当前尚未|尚未生成|未生成)[^。；;\n|]{0,30}"
        r"(基线|D1|随机|导入期|评价|评估|确认|时间点|日志|依从性|评分|血检|血常规)",
        re.IGNORECASE,
    )
    future_pass_reminder_pattern = re.compile(
        r"(基线时|随机时|D1|随机前|基线前|给药前|导入期间|导入期).{0,40}"
        r"(需|需要|应|必须|尚需|待|最终).{0,10}(确认|核对|复核|评估|判断|计算)",
        re.IGNORECASE,
    )
    screening_random_window_pattern = re.compile(
        r"(随机前|随机日期|随机窗口|洗脱期|半衰期).{0,36}(未到|未明确|尚未|待|需.{0,8}随机前|后续|筛选日期)",
        re.IGNORECASE,
    )
    screening_random_attention_pattern = re.compile(
        r"(洗脱|半衰期|生物制剂|单克隆抗体|抗体|禁用治疗|禁用药|末次用药|近期使用|用药背景).{0,80}"
        r"(不足|不够|未知|未明确|无法判断|需.{0,8}(研究者|核实|确认)|待.{0,8}(核实|确认)|风险|可能)",
        re.IGNORECASE,
    )
    for result in rule_results:
        if result.verdict in {"pass", "pass_verify", "na"}:
            reasoning = result.reasoning or ""
            timing_scope = f"{result.rule_name} {reasoning}"
            if screening_random_attention_pattern.search(timing_scope):
                result.verdict = "investigator"
                if "随机前重点关注" not in reasoning:
                    result.reasoning = (
                        reasoning.rstrip("。；; ")
                        + "。随机前重点关注：当前筛选期不直接判定不通过，但该条已暴露洗脱期/半衰期/随机前限制风险；随机或基线审核时必须以随机/基线锚点日期和源文件重新确认，不得仅凭筛选日期替代。"
                    )
                changed = True
                continue
            if (
                future_timing_pattern.search(timing_scope)
                or future_pass_reminder_pattern.search(timing_scope)
                or future_not_reached_pattern.search(timing_scope)
            ):
                result.verdict = "pass_verify"
                if "后续阶段复核提醒" not in reasoning:
                    result.reasoning = (
                        reasoning.rstrip("。；; ")
                        + "。后续阶段复核提醒：本条包含基线/D1/随机前或导入期后续组件，当前筛选期只能确认已到达部分，后续阶段需按相应源文件和锚点复核。"
                    )
                changed = True
            continue
        if result.verdict not in {"insufficient", "investigator"}:
            continue
        reasoning = result.reasoning or ""
        if not future_timing_pattern.search(reasoning) and not screening_random_window_pattern.search(reasoning):
            continue
        if screening_random_attention_pattern.search(reasoning):
            result.verdict = "investigator"
            if "随机前重点关注" not in reasoning:
                result.reasoning = (
                    reasoning.rstrip("。；; ")
                    + "。随机前重点关注：当前筛选期不直接判定不通过，但该条已暴露洗脱期/半衰期/随机前限制风险；随机或基线审核时必须以随机/基线锚点日期和源文件重新确认，不得仅凭筛选日期替代。"
                )
            changed = True
            continue
        if (
            any(term in reasoning for term in ("筛选期", "筛选"))
            and any(term in reasoning for term in ("满足", "已满足", "符合", "支持通过", "当前证据支持通过"))
        ) or screening_random_window_pattern.search(reasoning):
            result.verdict = "pass_verify"
            if "后续阶段复核" not in reasoning:
                result.reasoning = (
                    reasoning.rstrip("。；; ")
                    + "。后续阶段复核提醒：基线/D1/随机前尚未到达，不得用筛选日期替代随机/基线锚点，不作为筛选期证据不足或需研究者判定；后续阶段复核。"
                )
            changed = True
    return changed


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_review_messages(
    project_code: str,
    anchor_dates: Dict[str, str],
    criteria_rules: str,
    evidence_bundle: str,
    review_phase: Optional[Union[Dict[str, object], str]] = None,
    study_stage: str = "",
) -> List[Dict[str, str]]:
    """Build the system + user message pair for the review LLM."""
    if anchor_dates and any(anchor_dates.values()):
        anchor_lines = ["| 锚点 | 日期 | 来源 |", "|------|------|------|"]
        label_map = {
            "screening_date": "筛选日期",
            "icf_date": "ICF签署日期",
            "first_dosing_date": "首次给药日期",
            "birth_date": "出生日期",
            "review_phase_anchor_date": "本次基线/随机前审核锚点日期",
        }
        for key, label in label_map.items():
            val = anchor_dates.get(key, "")
            if val:
                anchor_lines.append(f"| {label} | {val} | 用户提供（请核实） |")
        anchor_table = "\n".join(anchor_lines)
    else:
        anchor_table = "（未提供结构化锚点日期。不得自行用打印日期、报告日期、上传日期替代；只有证据明确写明对应访视/随机/给药日期时才可作为锚点。）"

    if isinstance(review_phase, dict):
        phase_info = review_phase
    else:
        phase_info = phase_by_id({"review_phases": []}, review_phase or "full")
    phase_scope = render_phase_scope(phase_info, study_stage=study_stage)
    phase_id = str(phase_info.get("phase_id") or "")
    if phase_id == "screening_run_in":
        phase_timing_instruction = (
            "当前仅审核筛选期及此前已到达内容。若某条IN/EX同时包含“筛选”和“基线/D1/随机前”组件，"
            "本阶段只判定筛选期组件；基线/D1/随机前组件应写为“后续阶段待复核”，不得因此把本阶段结果降为证据不足或需研究者确认。"
            "例如筛选PASI/PGA/BSA已满足但基线尚未发生，本阶段IN-04应按筛选部分判定，并备注基线待后续阶段复核。\n"
        )
    else:
        phase_timing_instruction = (
            "对于当前阶段已经到达的“基线/D1/随机前”条款，不得用筛选期结果替代最终判定；"
            "若只有筛选期结果而缺少应到达的基线/D1源文件，应判为证据不足或需研究者确认，"
            "不得仅凭筛选期数值不达标判定 definitive 不通过，除非证据明确说明该筛选结果即为基线结果或基线复核仍不达标。\n"
            "入选标准或必做检查中写明“基线时”的项目（例如基线评分、基线EOS、基线血常规/生化/尿常规、D1随机前检查），"
            "必须有基线/D1/随机前源文件或证据明确说明该报告属于对应访视；筛选期采血、筛选报告或筛选病历转述不能替代普通通过，"
            "最多作为风险背景，缺失时应判为⚠️证据不足或⚠️需研究者判定。\n"
        )
    if _phase_requires_randomization_anchor(phase_info):
        phase_anchor_date = str(anchor_dates.get("review_phase_anchor_date") or "").strip()
        if phase_anchor_date:
            phase_anchor_instruction = (
                f"本次基线/随机前审核锚点日期：{phase_anchor_date}。凡依赖随机前/基线前/给药前X天、X周、X月、"
                "半衰期或访视窗口的条款，应优先以该日期作为时间窗锚点，并仍需核对证据原文是否支持该日期。\n"
            )
        else:
            phase_anchor_instruction = (
                "未提供本次基线/随机前审核锚点日期。凡依赖随机前/基线前/给药前时间窗的规则，"
                "若证据中也没有明确的基线、随机、给药或等价访视日期，不得用筛选日期、报告日期、打印日期或上传日期替代，"
                "该时间窗组件应判为⚠️证据不足或⚠️需研究者判定。\n"
            )
    else:
        phase_anchor_instruction = ""
    conmed_negative_evidence_instruction = (
        "合并/禁止用药或治疗洗脱条款需区分“缺单独表格”和“缺实质证据”。若筛选-基线病历、合并用药核查、"
        "研究病历或其它源文件明确否认相关禁用药物/治疗类别及对应时间窗，可作为阴性证据；"
        "不得仅因缺少单独的合并用药记录表判为⚠️证据不足。若只有病历转述但已逐项否认且无矛盾证据，"
        "可按✅通过（需验证：溯源提醒）处理，并提示归档时核对合并用药记录表。\n"
    )
    rule_ids = extract_rule_ids(criteria_rules)
    rule_id_checklist = ""
    if rule_ids:
        formatted_ids = "、".join(f"`{rid}`" for rid in rule_ids)
        rule_id_checklist = (
            "## 必须覆盖的规则ID清单\n"
            f"以下 {len(rule_ids)} 个规则ID必须全部出现在“逐条审核结果”表格中，不得合并、省略或只在总结中提及：\n"
            f"{formatted_ids}\n\n"
            "若某条规则对应的检查/评分/检验尚未到达当前审核阶段，仍必须保留该规则行，"
            "判定为—不适用或说明“未到本阶段”，不得把未到阶段误判为证据不足。\n"
        )

    user_prompt = (
        f"# 入排审核任务\n"
        f"项目：{project_code}\n\n"
        f"{phase_scope}\n\n"
        f"## 锚点日期（仅供参考，以证据原文为准）\n"
        f"{anchor_table}\n\n"
        f"## 审核规则\n"
        f"{criteria_rules}\n\n"
        f"{rule_id_checklist}\n\n"
        f"## 证据材料\n"
        f"{evidence_bundle}\n\n"
        f"## 审核要求\n"
        f"请严格按照规则逐条判定。注意证据层级需要分情境：ICF签署、当期体征/检查/评分以筛选-基线源文件优先；"
        f"既往诊断、最早症状、病程时长、既往治疗/用药/检查等历史事实，以既往病历、既往检查、既往处方、出院小结等源文件优先。\n"
        f"若某条要求'既往/病史/症状起病超过X年或X月'，但证据只来自筛选或基线病历中的转述，"
        f"且未见更早既往源文件支持、也没有矛盾证据，应判为✅通过（需验证：病史来源需溯源验证），"
        f"推理依据写明需要补充既往病历/诊断证明/既往检查或处方等源文件，不得写成普通✅通过；"
        f"但如果全表只有这类通过需验证提醒、没有❌不通过/⚠️证据不足/⚠️需研究者，整体总结论仍写pass。\n"
        f"逐条审核结果表必须逐项覆盖上述规则ID清单；如输出空间有限，优先保留表格完整性，"
        f"推理依据可压缩为一句关键原文引用。\n"
        f"每条规则必须先完成语义触发判断再写判定结果：EX条目先判断是否达到方案定义的排除触发条件，"
        f"IN条目先判断是否满足方案定义的纳入条件。EX条目若判❌不通过，推理依据必须明确写出"
        f"“触发判断：已触发”及触发子项/数值/阈值；若依据实际写的是未触发、未达阈值、需研究者评估，"
        f"则不得把判定结果写成❌不通过。\n"
        f"可能性不是排除触发：存在违规可能、存在隐患、未明确是否使用/发生、时间窗交接不清、需确认、待补充，"
        f"均不能直接判❌不通过，应判⚠️需研究者或⚠️证据不足；只有明确证据显示在方案时间窗内发生禁用事实或达到阈值，才可不通过。\n"
        f"实验室检查必须做检验项目名精确匹配：只有方案列明的项目及明确同义词可以触发对应阈值，"
        f"不得用相邻项目或同类项目替代。例如方案写ALT/AST/总胆红素≥1.5×ULN时，GGT、ALP、直接胆红素、"
        f"间接胆红素等不能触发该子项；若这些未列名项目异常，只能按其它有临床意义实验室异常交由研究者评估。\n"
        f"证据主题必须匹配当前条款主题：活动性感染/急性疾病条款需要感染或急性疾病的诊断、症状体征、"
        f"抗感染治疗或相关感染检查证据；尿糖、潜血、GGT等孤立检验异常不能证明活动性感染，"
        f"也不能推翻病历中否认活动性感染或急性疾病状态的原文。\n"
        f"肺功能/FEV1排除条款必须引用可解释数值证据，尤其是支气管舒张剂使用前FEV1占预计值百分比或等价字段；"
        f"肺功能报告标题、OCR模糊、数值不完整、仅写“未提示异常/未见异常”或整体可入组结论都不能证明FEV1>50%。"
        f"若无法读出FEV1占预计值百分比，应判为⚠️证据不足，而不是普通通过。\n"
        f"凡方案写“且/并且/同时/经研究者评估”的复合条件，必须把全部组件作为AND同时满足，不能弱化为OR。"
        f"例如EX-20h“任何其它实验室检查结果异常且有临床意义，经研究者评估如果参与研究将可能对参与者构成不可接受的风险”"
        f"必须同时引用：实验室异常、明确有临床意义、研究者评估参与研究可能构成不可接受风险；尿糖1+或“未排除临床意义”均不足以判❌不通过。\n"
        f"凡方案要求异常有临床意义或研究者评估不可接受风险，必须引用研究者/医生明确判断。"
        f"未排除临床意义、需研究者评估、除非后续补充排除证据，均不能直接判❌不通过，只能判⚠️需研究者。\n"
        f"研究者判断类复合条件不能缺项：若排除条件由“存在疾病/异常/用药/病史”等事实加上"
        f"“研究者判断不具备临床研究条件、可能影响研究评估、增加安全性风险、疗效不佳、影响依从性或有自杀风险”等不利判断组成，"
        f"必须同时引用事实和研究者不利判断。只有疾病/异常/用药存在，或只写未明确判断具备条件、必要时专科就诊、疗效不详，"
        f"不能判❌不通过，应判⚠️需研究者。\n"
        f"梅毒筛查例外必须完整：如果方案写梅毒特异性抗体阳性但允许“非特异性抗体阴性且研究者判断既往感染已治愈”的例外，"
        f"TPPA/TP-Ab/梅毒特异性抗体阳性不能仅凭TRUST/RPR阴性、目前无不适、未予治疗、非活动性感染或“可进入研究”判为通过；"
        f"必须同时引用非特异性抗体阴性和研究者明确判断既往感染已治愈。缺少治愈判断时判⚠️需研究者或⚠️证据不足。\n"
        f"当前是阶段性入排审核，不是默认全量终审；尚未到达的基线/随机前要求，"
        f"若不属于当前阶段应完成内容，应判为—不适用或说明未到本阶段，"
        f"不得扩大为证据不足。\n"
        f"{phase_anchor_instruction}"
        f"{phase_timing_instruction}"
        f"{conmed_negative_evidence_instruction}"
        f"输出前必须逐行执行系统提示中的DeepSeek输出前自检：父级规则ID不得遗漏；任何❌不通过必须有完整正向触发证据；"
        f"整体IE/可入组结论不得替代单条研究者判断；阈值子项和其它异常子项必须分流；例外缺项不得硬套通过或硬判失败。\n"
        f"涉及年龄判断时直接使用病历记载年龄，不要因缺失出生日期判证据不足。\n"
        f"每条给出：规则ID + 判定结果 + 推理依据（引用证据类别+原文关键句）。\n"
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


async def run_review(
    *,
    subject_id: str,
    project_code: str,
    anchor_dates: Dict[str, str],
    criteria_rules: str,
    evidence_bundle: str,
    output_dir: Optional[Path] = None,
    model: Optional[str] = None,
    review_phase: Optional[Union[Dict[str, object], str]] = None,
    study_stage: str = "",
) -> ReviewReport:
    """Run the full LLM enrollment review."""
    messages = build_review_messages(
        project_code=project_code,
        anchor_dates=anchor_dates,
        criteria_rules=criteria_rules,
        evidence_bundle=evidence_bundle,
        review_phase=review_phase,
        study_stage=study_stage,
    )

    expected_rule_ids = extract_rule_ids(criteria_rules)
    rule_titles = extract_rule_titles(criteria_rules)

    logger.info("Sending review request for subject %s (project %s)", subject_id, project_code)
    raw_response: str = await review_chat(messages, model=model)
    raw_attempts = [raw_response]
    logger.info("Received LLM response (%d chars)", len(raw_response))

    parsed = parse_review_response(raw_response)
    missing_rule_ids = _missing_expected_rule_ids(parsed["rule_results"], expected_rule_ids)
    if missing_rule_ids:
        logger.warning(
            "Review response for %s omitted %d/%d expected rules; retrying once: %s",
            subject_id,
            len(missing_rule_ids),
            len(expected_rule_ids),
            ", ".join(missing_rule_ids[:12]),
        )
        retry_messages = list(messages)
        retry_messages.append({
            "role": "user",
            "content": (
                "上一轮输出因缺少官方规则ID而不合格。请重新输出完整审核结果，必须逐行覆盖以下全部规则ID，"
                "不得只输出有问题的条目，不得省略通过/不适用条目："
                + "、".join(f"`{rid}`" for rid in expected_rule_ids)
                + "。请保留“审核结论”和“逐条审核结果”表格，表格中每条规则ID必须只出现一次。"
            ),
        })
        raw_response = await review_chat(retry_messages, model=model)
        raw_attempts.append(raw_response)
        logger.info("Received retry LLM response (%d chars)", len(raw_response))
        parsed = parse_review_response(raw_response)
        missing_rule_ids = _missing_expected_rule_ids(parsed["rule_results"], expected_rule_ids)
        if missing_rule_ids and _append_missing_rule_placeholders(parsed["rule_results"], missing_rule_ids, rule_titles):
            _reconcile_parent_rule_results(parsed["rule_results"])
            parsed["overall_verdict"] = _recalculate_overall_verdict(
                parsed["rule_results"],
                parsed["group_results"],
                parsed["overall_verdict"],
            )
            parsed["summary"] = _build_reconciled_summary(parsed["rule_results"], parsed["overall_verdict"])
    if _apply_evidence_bundle_conmed_denial_adjustments(parsed["rule_results"], evidence_bundle):
        _reconcile_parent_rule_results(parsed["rule_results"])
        parsed["overall_verdict"] = _recalculate_overall_verdict(
            parsed["rule_results"],
            parsed["group_results"],
            parsed["overall_verdict"],
        )
        parsed["summary"] = _build_reconciled_summary(parsed["rule_results"], parsed["overall_verdict"])
    if apply_missing_phase_anchor_date_adjustments(parsed["rule_results"], review_phase, anchor_dates):
        _reconcile_parent_rule_results(parsed["rule_results"])
        parsed["overall_verdict"] = _recalculate_overall_verdict(
            parsed["rule_results"],
            parsed["group_results"],
            parsed["overall_verdict"],
        )
        parsed["summary"] = _build_reconciled_summary(parsed["rule_results"], parsed["overall_verdict"])
    if apply_current_phase_required_evidence_adjustments(parsed["rule_results"], review_phase, anchor_dates):
        _reconcile_parent_rule_results(parsed["rule_results"])
        parsed["overall_verdict"] = _recalculate_overall_verdict(
            parsed["rule_results"],
            parsed["group_results"],
            parsed["overall_verdict"],
        )
        parsed["summary"] = _build_reconciled_summary(parsed["rule_results"], parsed["overall_verdict"])
    if apply_phase_timing_adjustments(parsed["rule_results"], review_phase):
        _reconcile_parent_rule_results(parsed["rule_results"])
        parsed["overall_verdict"] = _recalculate_overall_verdict(
            parsed["rule_results"],
            parsed["group_results"],
            parsed["overall_verdict"],
        )
        parsed["summary"] = _build_reconciled_summary(parsed["rule_results"], parsed["overall_verdict"])

    report = ReviewReport(
        subject_id=subject_id,
        project_code=project_code,
        overall_verdict=parsed["overall_verdict"],
        summary=parsed["summary"],
        rule_results=parsed["rule_results"],
        group_results=parsed["group_results"],
        anchor_dates=anchor_dates,
        model_used=model or REVIEW_MODEL,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        raw_path = output_dir / "review_raw.md"
        raw_path.write_text(raw_response, encoding="utf-8")
        logger.info("Saved raw response to %s", raw_path)
        if len(raw_attempts) > 1:
            for idx, attempt in enumerate(raw_attempts, start=1):
                attempt_path = output_dir / f"review_attempt_{idx}_raw.md"
                attempt_path.write_text(attempt, encoding="utf-8")
        report_path = output_dir / "review_report.md"
        report_path.write_text(report.to_markdown(), encoding="utf-8")
        logger.info("Saved report to %s", report_path)

    return report
