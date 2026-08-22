"""Phase 5 Slice 5.2 纯确定性候选门禁（无存储/无模型）。

覆盖 PRD P5-R03 / 设计书 §4.2 中不依赖数据库的确定性校验：

- Gate POLARITY_AND_ASSERTED_OBJECT：极性/断言对象/AssertionBasis 闭包；
- Gate VALUE_UNIT_DATE_SOURCE：值/单位、部分日期边界、记录时间、来源派生输入；
- Gate PAGE_COVERAGE_AND_REFERENCE_CLOSURE 中的候选引用闭包（事件/暴露对事实候选的引用）。

所有函数均为纯函数：输入为已校验的 Pydantic 合同或批次 fixture，输出为
``(outcome, reasons, affected_scope)`` 或 ``list[str]`` 错误列表，不触发
文件、数据库或模型调用，不产生随机性与副作用。定位真实性、有效文本哈希、
页覆盖与 OCR 阻断由证据闭包适配器负责；精确去重与语义冲突不择优
由批量编排负责。

与 ``app/domain/contracts/facts.py`` 的协作：
- 已有合同层的 ``_validate_fact_polarity_value`` / ``_validate_duration_bounds``
  / ``PartialDateRange`` 校验在模型构造时已执行；本模块在门禁层复述相同的
  判定理由，产出 ``GateOutcome.REJECTED`` 与中文原因，不抛异常，便于批次聚合
  与 ``FactGateResult`` 持久化。
- 本模块不重复校验权威元组与发布稳定身份（Slice 5.1 已冻结），仅校验候选
  阶段的纯确定性语义。
"""

from __future__ import annotations

import calendar
import math
import re
from datetime import datetime

from app.domain.contracts.enums import (
    DatePrecision,
    DurationStatus,
    FactGate,
    FactPolarity,
    GateOutcome,
)
from app.domain.contracts.fact_gates import GateVerdict
from app.domain.contracts.facts import (
    ClinicalEventCandidateV2,
    ClinicalFactCandidateV2,
    FactGateResult,
    MedicationExposureCandidateV2,
    PartialDateRange,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


# --------------------------------------------------------------------------- 基础工具

def _is_blank(value: str | None) -> bool:
    return value is None or not value.strip()


def _require_utc_errors(value: datetime | None, field_label: str) -> list[str]:
    if value is None:
        return []
    if value.tzinfo is None or value.utcoffset() is None:
        return [f"{field_label} 必须携带 UTC 时区"]
    if value.utcoffset().total_seconds() != 0:  # type: ignore[union-attr]
        return [f"{field_label} 必须使用 UTC 时区"]
    return []


def _validate_unit_string(unit: str | None, label: str) -> list[str]:
    if unit is None:
        return []
    if _is_blank(unit):
        return [f"{label} 不能为空或空白"]
    stripped = unit.strip()
    if stripped != unit:
        return [f"{label} 前后不能为空格"]
    if len(unit) > 64:
        return [f"{label} 长度不得超过 64"]
    if "\n" in unit or "\r" in unit or "\t" in unit:
        return [f"{label} 不能包含控制字符"]
    return []


def _affected_locators(candidate) -> list[str]:
    locs = getattr(candidate, "locator_ids", []) or []
    return sorted(set(locs))


# --------------------------------------------------------------------------- 极性 / 断言对象

def validate_fact_polarity_assertion(candidate: ClinicalFactCandidateV2) -> list[str]:
    """校验事实候选的极性与断言依据闭包（Gate POLARITY_AND_ASSERTED_OBJECT）。

    规则（PRD P5-R03）：
    - UNKNOWN 不得携带被断言值/单位/断言依据；
    - AFFIRMED/NEGATED 必须携带规范值、非空 asserted_object、非空 AssertionBasis，
      且 basis 的 locator_id 属于候选 locator_ids、asserted_object 一致、assertion_text
      非空、source_text_sha256 为 64 位十六进制；
    - 抑制“邻近句否定”“空白否认”：否定事实必须有指向被断言对象的明确否定原句，本门禁仅校验
      结构闭包（对象一致、定位归属、哈希格式、文本非空）；语义否定词的临床判定不在本阶段。
    - 沉默/未提及不生成否定事实的能力由上游 Normalizer 保证，本门禁仅拒绝结构不闭合的候选。
    """
    errors: list[str] = []
    pol = candidate.polarity
    if pol == FactPolarity.UNKNOWN:
        if candidate.canonical_value is not None or candidate.raw_value is not None:
            errors.append("未知极性候选不能携带被断言值")
        if candidate.unit is not None:
            errors.append("未知极性候选不能携带单位")
        if candidate.assertion_basis is not None:
            errors.append("未知极性候选不能携带断言依据")
        return errors

    # AFFIRMED / NEGATED
    if _is_blank(candidate.asserted_object):
        errors.append("肯定或否定候选必须声明非空被断言对象")
    if candidate.canonical_value is None:
        errors.append("肯定或否定候选必须携带规范值")
    else:
        if isinstance(candidate.canonical_value, float) and not math.isfinite(candidate.canonical_value):
            errors.append("候选规范数值必须是有限数")
    if candidate.assertion_basis is None:
        errors.append("肯定或否定候选必须携带明确断言依据")
        return errors

    basis = candidate.assertion_basis
    if _is_blank(basis.asserted_object):
        errors.append("断言依据被断言对象不能为空")
    if _is_blank(basis.assertion_text):
        errors.append("断言依据文本不能为空或空白")
    elif len(basis.assertion_text.strip()) < 2:
        errors.append("断言依据文本过短，必须为指向被断言对象的明确语句")
    if basis.locator_id not in candidate.locator_ids:
        errors.append("断言依据定位必须属于候选事实的定位集合")
    if basis.asserted_object != candidate.asserted_object:
        errors.append("候选被断言对象必须与断言依据对象一致")
    if not _SHA256.match(basis.source_text_sha256):
        errors.append("断言依据原文哈希必须为 64 位十六进制小写")
    return errors


# --------------------------------------------------------------------------- 值 / 单位

def validate_fact_value_unit(candidate: ClinicalFactCandidateV2) -> list[str]:
    """校验事实候选的值/单位语义（Gate VALUE_UNIT_DATE_SOURCE 子项）。

    - 数值（int/float，非 bool）必须声明单位；无量纲显式使用 ``unitless``；
    - 非数值（str/bool）不应携带单位；
    - 数值必须有限；单位字符串需满足基本格式。
    """
    errors: list[str] = []
    val = candidate.canonical_value
    unit = candidate.unit

    # 单位格式先验
    errors.extend(_validate_unit_string(unit, "单位"))

    if val is None:
        # UNKNOWN 已在极性门禁中拒绝；此处不再重复
        return errors

    is_numeric = isinstance(val, (int, float)) and not isinstance(val, bool)
    if is_numeric:
        if not unit:
            errors.append("数值候选必须声明单位；无量纲值显式使用 unitless")
        elif unit and unit.strip() == "":
            errors.append("数值候选单位不能为空白")
        if isinstance(val, float) and not math.isfinite(val):
            errors.append("候选规范数值必须是有限数")
    else:
        # 文本/布尔事实不应携带单位（避免把 string 值误标单位）
        if unit is not None:
            errors.append("非数值事实不应携带单位")
        if isinstance(val, str) and _is_blank(val):
            errors.append("文本规范值不能为空或空白")

    # raw_value 若存在，检查非空（不强制与 canonical_value 一致，由 Normalizer 负责）
    if candidate.raw_value is not None and isinstance(candidate.raw_value, str) and _is_blank(candidate.raw_value):
        errors.append("原始值文本不能为空或空白")
    return errors


def validate_exposure_value_unit(candidate: MedicationExposureCandidateV2) -> list[str]:
    """校验用药暴露候选的剂量/单位/频次/途径（Gate VALUE_UNIT_DATE_SOURCE 子项）。

    - ``dose`` 与 ``unit`` 必须同有同无；单有 unit 无 dose 拒绝；
    - ``unit``/``frequency``/``route`` 若提供必须非空、去空格、无控制字符；
    - ``medication_name`` 已在合同层保证非空，此处仅补充空白检查。
    """
    errors: list[str] = []
    if _is_blank(candidate.medication_name):
        errors.append("用药暴露药名不能为空或空白")

    has_dose = not _is_blank(candidate.dose)
    has_unit = candidate.unit is not None and not _is_blank(candidate.unit)

    if has_unit and not has_dose:
        errors.append("暴露单位不能在无剂量时单独出现")
    # dose 本身若提供，检查空白
    if candidate.dose is not None and _is_blank(candidate.dose):
        errors.append("暴露剂量不能为空白")
    # unit 格式
    errors.extend(_validate_unit_string(candidate.unit, "暴露单位"))
    # frequency / route / category / indication 若提供，检查非空
    for label, value in (
        ("暴露频次", candidate.frequency),
        ("暴露途径", candidate.route),
        ("暴露类别", candidate.category),
        ("暴露适应证", candidate.indication),
    ):
        if value is not None and _is_blank(value):
            errors.append(f"{label} 不能为空白")

    return errors


# --------------------------------------------------------------------------- 部分日期边界

def validate_partial_date_range(dr: PartialDateRange | None, label: str = "日期范围") -> list[str]:
    """校验部分日期的精度与确定性上下界（Gate VALUE_UNIT_DATE_SOURCE 子项）。

    年/年月/日/未知四档的确定性边界规则与 ``app/domain/contracts/facts.py`` 的
    ``PartialDateRange.validate_range`` 一致，本函数以错误列表形式复述，便于门禁聚合：
    - UNKNOWN 上下界必须为空，不借用筛选/上传/操作日期；
    - DAY 上下界相同；
    - MONTH 当月首日至末日；
    - YEAR 当年 1/1 至 12/31。
    """
    if dr is None:
        return []
    errors: list[str] = []
    prec = dr.precision
    lb = dr.lower_bound
    ub = dr.upper_bound

    if prec == DatePrecision.UNKNOWN:
        if lb is not None or ub is not None:
            errors.append(f"{label}：未知日期不能携带上下界；不得借用筛选/上传/操作日期")
        return errors

    if lb is None or ub is None:
        errors.append(f"{label}：已知日期精度必须提供确定性上下界")
        return errors
    if ub < lb:
        errors.append(f"{label}：日期上界不能早于下界")

    if prec == DatePrecision.DAY:
        if lb != ub:
            errors.append(f"{label}：日精度日期上下界必须相同")
    elif prec == DatePrecision.MONTH:
        if lb.year != ub.year or lb.month != ub.month:
            errors.append(f"{label}：月精度上下界必须属于同一月份")
        if lb.day != 1:
            errors.append(f"{label}：月精度下界必须是当月首日")
        last_day = calendar.monthrange(ub.year, ub.month)[1]
        if ub.day != last_day:
            errors.append(f"{label}：月精度上界必须是当月末日")
    elif prec == DatePrecision.YEAR:
        if lb.month != 1 or lb.day != 1:
            errors.append(f"{label}：年精度下界必须是当年 1 月 1 日")
        if ub.month != 12 or ub.day != 31:
            errors.append(f"{label}：年精度上界必须是当年 12 月 31 日")
        if lb.year != ub.year:
            errors.append(f"{label}：年精度上下界必须属于同一年")
    # source_text 若提供，检查非空（不参与身份，仅用于溯源展示）
    if dr.source_text is not None and _is_blank(dr.source_text):
        errors.append(f"{label}：溯源原文不能为空白")
    return errors


def validate_duration_bounds(
    start_range: PartialDateRange | None,
    end_range: PartialDateRange | None,
    duration_status: DurationStatus,
    label_prefix: str = "持续状态",
) -> list[str]:
    """校验持续状态与起止范围的时态一致性（Gate VALUE_UNIT_DATE_SOURCE 子项）。

    - ENDED 必须显式给出终止范围，不得由“既往”推断；
    - ONGOING 不得携带终止范围；
    - 起止均有且均为已知日期时，开始下界不得晚于结束上界；
    - 未知日期的比较予以跳过（由上游 PartialDateRange 保证未知无边界）。
    """
    errors: list[str] = []
    errors.extend(validate_partial_date_range(start_range, "开始范围"))
    errors.extend(validate_partial_date_range(end_range, "结束范围"))

    if duration_status == DurationStatus.ENDED and end_range is None:
        errors.append(f"{label_prefix}：已结束暴露必须由资料明确给出终止日期，不得由“既往”推断")
    if duration_status == DurationStatus.ONGOING and end_range is not None:
        errors.append(f"{label_prefix}：持续暴露不能携带终止日期范围")
    if start_range is not None and end_range is not None:
        lb = start_range.lower_bound
        ub = end_range.upper_bound
        # 仅当两侧均为已知日期时才可比较
        if lb is not None and ub is not None and lb > ub:
            errors.append(f"{label_prefix}：开始范围不能晚于结束范围")
    return errors


# --------------------------------------------------------------------------- 记录时间

def validate_record_time(
    record_time: datetime | None,
    created_at: datetime,
    label: str = "记录时间",
) -> list[str]:
    """校验记录时间的时区与合理性（Gate VALUE_UNIT_DATE_SOURCE 子项）。

    - 必须为 UTC（与 Phase 4 合同边界一致，拒绝 naive 与非 UTC）；
    - 若提供，合理性检查：年份 1900-2100，避免明显非法远未来；
    - 不与 ``created_at`` 强制前后关系（创建时间为候选生成时间，记录时间可早可晚），
      仅在记录时间远晚于创建时间（> 1 天）时给出提醒式错误，保持确定性且不依赖当前墙钟。
    区分点：事件发生时间（``date_range``/``start_range``）与记录时间分开校验，
    不把上传/操作/筛选日当作记录时间。
    """
    errors: list[str] = []
    errors.extend(_require_utc_errors(record_time, label))
    errors.extend(_require_utc_errors(created_at, "创建时间"))
    if record_time is None:
        return errors
    # 年份合理性
    if not (1900 <= record_time.year <= 2100):
        errors.append(f"{label} 年份超出合理范围 1900-2100")
    if not (1900 <= created_at.year <= 2100):
        errors.append("创建时间年份超出合理范围 1900-2100")
    # 远未来：记录时间晚于创建时间超过 1 天，视为异常（确定性，不依赖 now）
    if record_time.tzinfo is not None and created_at.tzinfo is not None:
        delta = record_time - created_at
        if delta.total_seconds() > 86400:
            errors.append(f"{label} 不应晚于创建时间超过 1 天")
    return errors


# --------------------------------------------------------------------------- 来源派生输入

_ALLOWED_CANDIDATE_SOURCE_SEMANTICS = frozenset(
    {
        "同期客观结果",
        "既往原始资料",
        "当前研究病历直接记录",
        "筛选病历转述",
        "无法确认来源",
        # 英文别名（兼容历史 fixture 的客观/转述标记，确定性派生不依赖它们作阈值）
        "objective_result",
        "historical_primary",
        "current_chart",
        "screening_transcript",
        "unverifiable_source",
        "contemporaneous_objective",
    }
)


def validate_source_derivation_inputs(
    candidate_source_semantics: str | None,
    label: str = "来源语义",
) -> list[str]:
    """校验来源派生输入的完整性（Gate VALUE_UNIT_DATE_SOURCE 子项）。

    来源强度由文档类型/来源方/定位元数据确定性派生；本门禁仅校验候选阶段的
    ``candidate_source_semantics`` 输入完整性：
    - 必须非空、去空格、无控制字符、长度 ≤128；
    - 弱来源（筛选病历转述）的阳性长期史可在本门禁通过，但需由下游覆盖层
      生成溯源提醒（不在本门禁拒绝）；
    - 不把模型置信度当作阈值（PRD P5-R03）。
    """
    errors: list[str] = []
    if candidate_source_semantics is None or _is_blank(candidate_source_semantics):
        errors.append(f"{label} 不能为空或空白")
        return errors
    stripped = candidate_source_semantics.strip()
    if stripped != candidate_source_semantics:
        errors.append(f"{label} 前后不能为空格")
    if len(candidate_source_semantics) > 128:
        errors.append(f"{label} 长度不得超过 128")
    if "\n" in candidate_source_semantics or "\r" in candidate_source_semantics or "\t" in candidate_source_semantics:
        errors.append(f"{label} 不能包含控制字符")
    # 允许的语义标签为开放集：仅当完全不在已知集合时给出信息性提示，不拒绝？
    # 为保持确定性与可测试性，若使用完全未知标签则拒绝，提示调用方使用已知来源语义。
    # 兼容部分：允许任意非空中文/英文短语，但长度已限；未知标签仅在严格模式下拒绝。
    # 本实现：若不在已知集合且包含非预期字符，仍视为可接受（避免过度拒绝项目特异语义），
    # 故不额外报错；下游覆盖层会区分“无法确认来源”。
    return errors


# --------------------------------------------------------------------------- 候选引用闭包

def validate_linked_candidate_locator_closure(
    candidate: ClinicalEventCandidateV2 | MedicationExposureCandidateV2,
    fact_candidates_by_id: dict[str, ClinicalFactCandidateV2],
) -> list[str]:
    """保证事件/用药的证据定位确实属于其引用事实，而非同节点任意事实。"""
    missing = sorted(set(candidate.fact_candidate_ids) - set(fact_candidates_by_id))
    errors = [f"引用了不存在的事实候选 {fact_id}" for fact_id in missing]
    if missing:
        return errors

    allowed_locator_ids = {
        locator_id
        for fact_id in candidate.fact_candidate_ids
        for locator_id in fact_candidates_by_id[fact_id].locator_ids
    }
    unrelated = sorted(set(candidate.locator_ids) - allowed_locator_ids)
    if unrelated:
        errors.append(
            "证据定位不属于所引用事实候选：" + "、".join(unrelated)
        )
    return errors

def validate_candidate_reference_closure(
    *,
    fact_candidates: list[ClinicalFactCandidateV2],
    event_candidates: list[ClinicalEventCandidateV2],
    exposure_candidates: list[MedicationExposureCandidateV2],
    run_id: str,
    call_id: str,
) -> dict[str, list[str]]:
    """校验事件/暴露对事实候选的引用闭包（Gate PAGE_COVERAGE_AND_REFERENCE_CLOSURE 子项）。

    纯确定性校验，不依赖数据库：
    - 事件/暴露的 ``run_id``/``call_id`` 必须与批次一致；
    - ``fact_candidate_ids`` 必须在同一批次的事实候选集合中闭合；
    - ``locator_ids`` 已在合同层保证排序去重，此处仅校验批次内 run/call 一致性；
    - 返回 ``{candidate_id: [errors]}``，无错误则不出现在结果中。
    """
    errors_by_id: dict[str, list[str]] = {}
    fact_candidates_by_id = {c.candidate_id: c for c in fact_candidates}

    # 事实候选自身：校验 run/call 一致性与来源语义
    for fact_candidate in fact_candidates:
        cur: list[str] = []
        if fact_candidate.run_id != run_id:
            cur.append(f"事实候选 {fact_candidate.candidate_id} 的 run_id 与批次不一致")
        if fact_candidate.call_id != call_id:
            cur.append(f"事实候选 {fact_candidate.candidate_id} 的 call_id 与批次不一致")
        # 允许空？已在合同层保证 locator_ids 非空
        if cur:
            errors_by_id[fact_candidate.candidate_id] = cur

    for event_candidate in event_candidates:
        cur = []
        if event_candidate.run_id != run_id:
            cur.append(f"事件候选 {event_candidate.candidate_id} 的 run_id 与批次不一致")
        if event_candidate.call_id != call_id:
            cur.append(f"事件候选 {event_candidate.candidate_id} 的 call_id 与批次不一致")
        cur.extend(
            f"事件候选 {event_candidate.candidate_id} {error}"
            for error in validate_linked_candidate_locator_closure(
                event_candidate, fact_candidates_by_id
            )
        )
        if cur:
            errors_by_id[event_candidate.candidate_id] = cur

    for exposure_candidate in exposure_candidates:
        cur = []
        if exposure_candidate.run_id != run_id:
            cur.append(f"暴露候选 {exposure_candidate.candidate_id} 的 run_id 与批次不一致")
        if exposure_candidate.call_id != call_id:
            cur.append(f"暴露候选 {exposure_candidate.candidate_id} 的 call_id 与批次不一致")
        cur.extend(
            f"暴露候选 {exposure_candidate.candidate_id} {error}"
            for error in validate_linked_candidate_locator_closure(
                exposure_candidate, fact_candidates_by_id
            )
        )
        if cur:
            errors_by_id[exposure_candidate.candidate_id] = cur

    # 检测跨种类 ID 重复（同一 candidate_id 在多个列表中）
    all_ids = [c.candidate_id for c in fact_candidates] + [c.candidate_id for c in event_candidates] + [c.candidate_id for c in exposure_candidates]
    seen: set[str] = set()
    dups: set[str] = set()
    for cid in all_ids:
        if cid in seen:
            dups.add(cid)
        seen.add(cid)
    for dup in dups:
        # 将错误附加到该 ID 的现有错误列表或新建
        msg = f"候选 ID {dup} 在批次内重复"
        errors_by_id.setdefault(dup, []).append(msg)

    return errors_by_id


# --------------------------------------------------------------------------- 组合门禁：单候选

def gate_fact_candidate(
    candidate: ClinicalFactCandidateV2,
) -> dict[FactGate, GateVerdict]:
    """对单个事实候选执行纯确定性门禁，返回逐门的裁决字典。

    门禁顺序遵循设计书 §4.2，但本模块仅覆盖纯确定性子集：
    - ``POLARITY_AND_ASSERTED_OBJECT``
    - ``VALUE_UNIT_DATE_SOURCE``（值/单位、日期、记录时间、来源）

    合同与权威/定位/页覆盖等门禁由相应适配器负责，此处不重复。
    """
    verdicts: dict[FactGate, GateVerdict] = {}

    # 极性/断言
    pol_errors = validate_fact_polarity_assertion(candidate)
    verdicts[FactGate.POLARITY_AND_ASSERTED_OBJECT] = GateVerdict(
        candidate_id=candidate.candidate_id,
        gate=FactGate.POLARITY_AND_ASSERTED_OBJECT,
        outcome=GateOutcome.ACCEPTED if not pol_errors else GateOutcome.REJECTED,
        reasons=pol_errors,
        affected_scope=_affected_locators(candidate) if pol_errors else [],
    )

    # 值/单位 + 日期 + 记录时间 + 来源
    v_errors: list[str] = []
    v_errors.extend(validate_fact_value_unit(candidate))
    v_errors.extend(validate_partial_date_range(candidate.date_range, "事实日期范围"))
    v_errors.extend(validate_record_time(candidate.record_time, candidate.created_at, "事实记录时间"))
    v_errors.extend(validate_source_derivation_inputs(candidate.candidate_source_semantics, "事实来源语义"))

    verdicts[FactGate.VALUE_UNIT_DATE_SOURCE] = GateVerdict(
        candidate_id=candidate.candidate_id,
        gate=FactGate.VALUE_UNIT_DATE_SOURCE,
        outcome=GateOutcome.ACCEPTED if not v_errors else GateOutcome.REJECTED,
        reasons=v_errors,
        affected_scope=_affected_locators(candidate) if v_errors else [],
    )
    return verdicts


def gate_event_candidate(
    candidate: ClinicalEventCandidateV2,
    fact_id_set: set[str] | None = None,
) -> dict[FactGate, GateVerdict]:
    """对单个事件候选执行纯确定性门禁。"""
    verdicts: dict[FactGate, GateVerdict] = {}

    # 引用闭包（若提供 fact_id_set）
    ref_errors: list[str] = []
    if fact_id_set is not None:
        for fid in candidate.fact_candidate_ids:
            if fid not in fact_id_set:
                ref_errors.append(f"事件候选 {candidate.candidate_id} 引用了不存在的事实候选 {fid}")
    verdicts[FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE] = GateVerdict(
        candidate_id=candidate.candidate_id,
        gate=FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE,
        outcome=GateOutcome.ACCEPTED if not ref_errors else GateOutcome.REJECTED,
        reasons=ref_errors,
        affected_scope=sorted(set(candidate.fact_candidate_ids)) if ref_errors else [],
    )

    # 值/日期/持续/记录时间/来源
    v_errors: list[str] = []
    v_errors.extend(validate_duration_bounds(candidate.start_range, candidate.end_range, candidate.duration_status, "事件持续状态"))
    v_errors.extend(validate_record_time(candidate.record_time, candidate.created_at, "事件记录时间"))
    v_errors.extend(validate_source_derivation_inputs(candidate.candidate_source_semantics, "事件来源语义"))

    verdicts[FactGate.VALUE_UNIT_DATE_SOURCE] = GateVerdict(
        candidate_id=candidate.candidate_id,
        gate=FactGate.VALUE_UNIT_DATE_SOURCE,
        outcome=GateOutcome.ACCEPTED if not v_errors else GateOutcome.REJECTED,
        reasons=v_errors,
        affected_scope=_affected_locators(candidate) if v_errors else [],
    )
    return verdicts


def gate_exposure_candidate(
    candidate: MedicationExposureCandidateV2,
    fact_id_set: set[str] | None = None,
) -> dict[FactGate, GateVerdict]:
    """对单个暴露候选执行纯确定性门禁。"""
    verdicts: dict[FactGate, GateVerdict] = {}

    ref_errors: list[str] = []
    if fact_id_set is not None:
        for fid in candidate.fact_candidate_ids:
            if fid not in fact_id_set:
                ref_errors.append(f"暴露候选 {candidate.candidate_id} 引用了不存在的事实候选 {fid}")
    verdicts[FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE] = GateVerdict(
        candidate_id=candidate.candidate_id,
        gate=FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE,
        outcome=GateOutcome.ACCEPTED if not ref_errors else GateOutcome.REJECTED,
        reasons=ref_errors,
        affected_scope=sorted(set(candidate.fact_candidate_ids)) if ref_errors else [],
    )

    v_errors: list[str] = []
    v_errors.extend(validate_exposure_value_unit(candidate))
    v_errors.extend(validate_duration_bounds(candidate.start_range, candidate.end_range, candidate.duration_status, "暴露持续状态"))
    v_errors.extend(validate_record_time(candidate.record_time, candidate.created_at, "暴露记录时间"))
    v_errors.extend(validate_source_derivation_inputs(candidate.candidate_source_semantics, "暴露来源语义"))

    verdicts[FactGate.VALUE_UNIT_DATE_SOURCE] = GateVerdict(
        candidate_id=candidate.candidate_id,
        gate=FactGate.VALUE_UNIT_DATE_SOURCE,
        outcome=GateOutcome.ACCEPTED if not v_errors else GateOutcome.REJECTED,
        reasons=v_errors,
        affected_scope=_affected_locators(candidate) if v_errors else [],
    )
    return verdicts


def batch_gate_candidates(
    *,
    fact_candidates: list[ClinicalFactCandidateV2],
    event_candidates: list[ClinicalEventCandidateV2],
    exposure_candidates: list[MedicationExposureCandidateV2],
    run_id: str,
    call_id: str,
) -> dict[str, dict[FactGate, GateVerdict]]:
    """批次级纯确定性门禁：聚合引用闭包与各候选的逐门裁决。

    返回 ``{candidate_id: {gate: verdict}}``，便于上游持久化为 ``FactGateResult``
    并计算受影响范围。引用闭包错误会覆盖单候选的 ``PAGE_COVERAGE_AND_REFERENCE_CLOSURE``
    裁决；其他门的裁决保持纯确定性。
    """
    # 先计算引用闭包错误表
    closure_errors = validate_candidate_reference_closure(
        fact_candidates=fact_candidates,
        event_candidates=event_candidates,
        exposure_candidates=exposure_candidates,
        run_id=run_id,
        call_id=call_id,
    )
    fact_id_set = {c.candidate_id for c in fact_candidates}
    result: dict[str, dict[FactGate, GateVerdict]] = {}

    for fact_candidate in fact_candidates:
        verdicts = gate_fact_candidate(fact_candidate)
        # 叠加闭包错误（若该事实候选自身有 run/call 不一致）
        if fact_candidate.candidate_id in closure_errors:
            ce = closure_errors[fact_candidate.candidate_id]
            # 将闭包错误合并到引用门禁（事实候选本身不引用其他事实，但可能有 run/call 错误）
            verdicts[FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE] = GateVerdict(
                candidate_id=fact_candidate.candidate_id,
                gate=FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE,
                outcome=GateOutcome.REJECTED,
                reasons=ce,
                affected_scope=_affected_locators(fact_candidate),
            )
        result[fact_candidate.candidate_id] = verdicts

    for event_candidate in event_candidates:
        verdicts = gate_event_candidate(event_candidate, fact_id_set=fact_id_set)
        if event_candidate.candidate_id in closure_errors:
            ce = closure_errors[event_candidate.candidate_id]
            # 引用失败优先以闭包错误为准（已包含 run/call + 悬空引用）
            existing = verdicts[FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE]
            merged = list(existing.reasons) + [m for m in ce if m not in existing.reasons]
            # 去重但保持确定性顺序（排序）
            merged_sorted = sorted(set(merged))
            verdicts[FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE] = GateVerdict(
                candidate_id=event_candidate.candidate_id,
                gate=FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE,
                outcome=GateOutcome.REJECTED,
                reasons=merged_sorted,
                affected_scope=sorted(set(existing.affected_scope) | set(event_candidate.fact_candidate_ids)),
            )
        result[event_candidate.candidate_id] = verdicts

    for exposure_candidate in exposure_candidates:
        verdicts = gate_exposure_candidate(exposure_candidate, fact_id_set=fact_id_set)
        if exposure_candidate.candidate_id in closure_errors:
            ce = closure_errors[exposure_candidate.candidate_id]
            existing = verdicts[FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE]
            merged = list(existing.reasons) + [m for m in ce if m not in existing.reasons]
            merged_sorted = sorted(set(merged))
            verdicts[FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE] = GateVerdict(
                candidate_id=exposure_candidate.candidate_id,
                gate=FactGate.PAGE_COVERAGE_AND_REFERENCE_CLOSURE,
                outcome=GateOutcome.REJECTED,
                reasons=merged_sorted,
                affected_scope=sorted(set(existing.affected_scope) | set(exposure_candidate.fact_candidate_ids)),
            )
        result[exposure_candidate.candidate_id] = verdicts

    return result

# --------------------------------------------------------------------------- 与持久化合同的衔接

def verdict_to_gate_result(
    verdict: GateVerdict,
    *,
    run_id: str,
    call_id: str,
    gate_result_id: str,
    created_at: datetime,
) -> FactGateResult:
    """将纯确定性裁决转为可持久化的 ``FactGateResult`` 合同。

    保持纯确定性边界：本函数仅做合同字段搬运，不触发数据库或
    权威校验；调用方负责在仓储层通过 ``FactGateResultRepository.create`` 持久化。
    ``created_at`` 必须为 UTC，与 ``GateVerdict`` 的受影响范围一起原样写入
    ``FactGateResult``，便于按候选聚合受影响范围与阻断展示。
    """
    return FactGateResult(
        gate_result_id=gate_result_id,
        run_id=run_id,
        call_id=call_id,
        candidate_id=verdict.candidate_id,
        gate=verdict.gate,
        outcome=verdict.outcome,
        reasons=list(verdict.reasons),
        created_at=created_at,
    )


def verdicts_to_gate_results(
    batch_verdicts: dict[str, dict[FactGate, GateVerdict]],
    *,
    run_id: str,
    call_id: str,
    created_at: datetime,
    id_prefix: str = "gate",
) -> list[FactGateResult]:
    """将批次裁决扁平化为 ``FactGateResult`` 列表（确定性排序）。"""
    results: list[FactGateResult] = []
    for candidate_id in sorted(batch_verdicts.keys()):
        gate_map = batch_verdicts[candidate_id]
        for gate in sorted(gate_map.keys(), key=lambda g: g.value):
            verdict = gate_map[gate]
            gate_result_id = f"{id_prefix}-{candidate_id}-{gate.value}"
            results.append(
                FactGateResult(
                    gate_result_id=gate_result_id,
                    run_id=run_id,
                    call_id=call_id,
                    candidate_id=candidate_id,
                    gate=gate,
                    outcome=verdict.outcome,
                    reasons=list(verdict.reasons),
                    created_at=created_at,
                )
            )
    return results


def merge_gate_verdict_maps(
    *verdict_maps: dict[str, dict[FactGate, GateVerdict]],
) -> dict[str, dict[FactGate, GateVerdict]]:
    """把多个门禁模块的结果收敛为唯一 candidate+gate 裁决。

    同一门的结果按 ``BLOCKED > REJECTED > ACCEPTED`` 合并，原因与影响范围取
    确定性并集。这样页闭包等共享门禁只持久化一次，不依赖模块执行顺序。
    """
    priority = {
        GateOutcome.ACCEPTED: 0,
        GateOutcome.REJECTED: 1,
        GateOutcome.BLOCKED: 2,
    }
    merged: dict[str, dict[FactGate, GateVerdict]] = {}
    for verdict_map in verdict_maps:
        for candidate_id, gates in verdict_map.items():
            target = merged.setdefault(candidate_id, {})
            for gate, verdict in gates.items():
                existing = target.get(gate)
                if existing is None:
                    target[gate] = verdict
                    continue
                outcome = max((existing.outcome, verdict.outcome), key=priority.__getitem__)
                target[gate] = GateVerdict(
                    candidate_id=candidate_id,
                    gate=gate,
                    outcome=outcome,
                    reasons=sorted(set(existing.reasons) | set(verdict.reasons)),
                    affected_scope=sorted(
                        set(existing.affected_scope) | set(verdict.affected_scope)
                    ),
                )
    return {
        candidate_id: dict(sorted(gates.items(), key=lambda item: item[0].value))
        for candidate_id, gates in sorted(merged.items())
    }
