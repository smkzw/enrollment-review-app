"""中文原生、有界的证据规范化 Agent。

本模块实现 Slice 5.3 Evidence Normalizer 的中文原生 System Prompt、紧凑严格
JSON Schema、运行时解码器与有界传输适配器：

- 候选/unresolved-only 输出：只允许事实/事件/暴露候选与未解决项；发布事实、冲突
  裁决、Expectation、入排结论、ReviewRun、ActionRequest 由确定性代码负责；
- 中文原生临床措辞与 Slice 5.2 确定性门禁的权威边界一致；
- 紧凑严格 JSON Schema（extra=forbid、排序键、精简分隔）用于模型输出约束；
- 运行时解码器：仅做语义保持的 JSON 实例规范化（含断言对象的机械逐字还原），
  保留所有可操作的 schema 错误；
- 有界传输适配器：复用现有 Job/Step/Checkpoint/Lease/Idempotency 语义，限制传输重试
  与同会话 schema 修复预算，不引入新编排框架。

本模块只拥有 agent/contracts 层；逻辑文档切片/连续页组、页清单闭合与持久化
Job 定义分别由确定性规划层和持久任务层负责。
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from collections.abc import Mapping, Sequence
from datetime import datetime
from math import isfinite
from typing import Literal, Protocol

from pydantic import Field, ValidationError, model_validator

from app.domain.contracts.evidence_normalizer import (
    EvidenceNormalizerInput,
    EvidenceNormalizerOutput,
    EvidenceNormalizerUnresolvedItem,
)
from app.domain.contracts.common import ContractModel, ScalarValue
from app.domain.contracts.identifier_value import validate_identifier_value
from app.domain.contracts.agents import ModelConfigContract
from app.domain.contracts.enums import (
    AgentNode,
    DurationStatus,
    FactPolarity,
    GapType,
    ProfileLane,
    SourceStrength,
)
from app.domain.contracts.facts import (
    AssertionBasis,
    ClinicalEventCandidateV2,
    ClinicalFactCandidateV2,
    MedicationExposureCandidateV2,
    PartialDateRange,
)
from app.domain.contracts.selective_vision_observation import (
    SelectiveVisionObservationAttachment,
)
from app.domain.gates.fact_evidence_closure import derive_source_strength_from_metadata
from app.projections.normalizer_reference_aliases import NormalizerReferenceAliases


# ---------------------------------------------------------------------------
# Transport contracts
# ---------------------------------------------------------------------------


class EvidenceNormalizerAgentResponse(ContractModel):
    """传输层原始响应：保留逻辑会话与原文，用于审计与哈希。"""

    session_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class EvidenceNormalizerAgentCallError(RuntimeError):
    """传输失败，保留逻辑会话以便审计恢复。"""

    def __init__(self, session_id: str, message: str):
        super().__init__(message)
        self.session_id = session_id


class EvidenceNormalizerEmptyOutputError(ValueError):
    """模型未返回候选，也未逐页说明为何没有可抽取内容。"""


class EvidenceNormalizerTransport(Protocol):
    def start(self, *, prompt: str) -> EvidenceNormalizerAgentResponse: ...

    def continue_session(
        self, *, session_id: str, prompt: str
    ) -> EvidenceNormalizerAgentResponse: ...


SUPPORTED_EVIDENCE_NORMALIZER_PROVIDERS = frozenset(
    {
        "deepseek",
        "deepseek-api",
        "mtplx",
        "mtplx-api",
        "omlx",
        "local-omlx",
        "zhipu-coding-plan",
        "cms-router",
        "cms-smk",
        "opencode-go",
        "ollama-cloud",
    }
)
SUPPORTED_EVIDENCE_NORMALIZER_REASONING_EFFORTS = frozenset(
    {"default", "auto", "low", "medium", "high", "xhigh", "max"}
)
# GLM-5.3-Flash（zhipu-coding-plan Coding Plan 端点）只接受 low/high/max。
ZHIPU_EVIDENCE_NORMALIZER_BACKENDS = frozenset({"zhipu-coding-plan"})
SUPPORTED_GLM_NORMALIZER_REASONING_EFFORTS = frozenset({"low", "high", "max"})


def validate_evidence_normalizer_model_config(
    model_config: ModelConfigContract,
    *,
    require_normalizer_role: bool = True,
) -> None:
    """Validate the frozen model contract at every execution boundary."""
    provider = model_config.provider.strip().lower()
    effort = model_config.reasoning_effort.strip().lower()
    if provider not in SUPPORTED_EVIDENCE_NORMALIZER_PROVIDERS:
        raise ValueError("模型连接方式不适用于个例档案整理")
    if effort not in SUPPORTED_EVIDENCE_NORMALIZER_REASONING_EFFORTS:
        raise ValueError("模型思考强度不适用于个例档案整理")
    if provider in ZHIPU_EVIDENCE_NORMALIZER_BACKENDS and (
        effort not in SUPPORTED_GLM_NORMALIZER_REASONING_EFFORTS
    ):
        raise ValueError("GLM 证据规范化推理强度仅支持 low/high/max")
    if require_normalizer_role and (
        str(model_config.parameters.get("agent_node") or "")
        != AgentNode.EVIDENCE_NORMALIZER.value
    ):
        raise ValueError("模型配置不属于个例档案整理任务")
    raw_max_tokens = model_config.parameters.get("max_tokens")
    if isinstance(raw_max_tokens, bool) or not isinstance(raw_max_tokens, int):
        raise ValueError("模型最大输出长度无效")
    if raw_max_tokens < 1:
        raise ValueError("模型最大输出长度必须大于零")
    if "temperature" in model_config.parameters:
        raw_temperature = model_config.parameters["temperature"]
        if isinstance(raw_temperature, bool) or not isinstance(
            raw_temperature, (int, float)
        ):
            raise ValueError("模型采样温度无效")
        temperature = float(raw_temperature)
        if not isfinite(temperature) or not 0 <= temperature <= 2:
            raise ValueError("模型采样温度必须在 0 到 2 之间")


# ---------------------------------------------------------------------------
# Model-facing compact drafts
# ---------------------------------------------------------------------------


class EvidenceAssertionDraft(ContractModel):
    """模型只摘录断言语义；原文哈希由系统按摘录文本确定性生成。"""

    asserted_object: str = Field(min_length=1)
    assertion_text: str = Field(min_length=1)
    locator_id: str = Field(min_length=1)


class EvidenceFactDraft(ContractModel):
    candidate_ref: str = Field(min_length=1)
    value_kind: Literal["value", "identifier"] = "value"
    source_observation_refs: list[str] = Field(default_factory=list)
    fact_type: str = Field(min_length=1)
    profile_lane: ProfileLane
    supported_requirement_ids: list[str] = Field(default_factory=list)
    polarity: FactPolarity
    asserted_object: str = Field(min_length=1)
    raw_value: ScalarValue | None = None
    canonical_value: ScalarValue | None = None
    unit: str | None = None
    date_range: PartialDateRange | None = None
    record_time: datetime | None = None
    locator_ids: list[str] = Field(min_length=1)
    candidate_source_semantics: str = Field(min_length=1)
    assertion_basis: EvidenceAssertionDraft | None = None
    model_uncertainty: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_identifier(self):
        if self.value_kind == "identifier":
            validate_identifier_value(
                self.raw_value, self.canonical_value, self.unit,
                self.assertion_basis.assertion_text if self.assertion_basis else None,
            )
        return self


class EvidenceEventDraft(ContractModel):
    candidate_ref: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    profile_lane: ProfileLane
    start_range: PartialDateRange | None = None
    end_range: PartialDateRange | None = None
    duration_status: DurationStatus
    record_time: datetime | None = None
    fact_candidate_refs: list[str] = Field(min_length=1)
    locator_ids: list[str] = Field(min_length=1)
    candidate_source_semantics: str = Field(min_length=1)
    model_uncertainty: float = Field(ge=0, le=1)


class EvidenceExposureDraft(ContractModel):
    candidate_ref: str = Field(min_length=1)
    medication_name: str = Field(min_length=1)
    category: str | None = None
    indication: str | None = None
    dose: str | None = None
    unit: str | None = None
    frequency: str | None = None
    route: str | None = None
    start_range: PartialDateRange | None = None
    end_range: PartialDateRange | None = None
    duration_status: DurationStatus
    record_time: datetime | None = None
    fact_candidate_refs: list[str] = Field(min_length=1)
    locator_ids: list[str] = Field(min_length=1)
    candidate_source_semantics: str = Field(min_length=1)
    model_uncertainty: float = Field(ge=0, le=1)


class EvidenceNormalizerDraftOutput(ContractModel):
    """真实模型唯一输出形状；系统身份与审计字段不交给模型生成。"""

    schema_version: Literal["phase5/normalizer-draft/v3"] = (
        "phase5/normalizer-draft/v3"
    )
    fact_candidates: list[EvidenceFactDraft] = Field(default_factory=list)
    event_candidates: list[EvidenceEventDraft] = Field(default_factory=list)
    exposure_candidates: list[EvidenceExposureDraft] = Field(default_factory=list)
    actual_exposure_fact_refs: list[str]
    non_exposure_medication_fact_refs: list[str]
    unresolved_items: list[EvidenceNormalizerUnresolvedItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_candidate_refs(self) -> "EvidenceNormalizerDraftOutput":
        refs = [
            item.candidate_ref
            for item in (
                *self.fact_candidates,
                *self.event_candidates,
                *self.exposure_candidates,
            )
        ]
        if refs != list(dict.fromkeys(refs)):
            raise ValueError("candidate_ref 必须在本次响应内唯一")
        facts_by_ref = {item.candidate_ref: item for item in self.fact_candidates}
        fact_refs = set(facts_by_ref)
        for item in (*self.event_candidates, *self.exposure_candidates):
            unknown = set(item.fact_candidate_refs) - fact_refs
            if unknown:
                raise ValueError(
                    f"{item.candidate_ref} 引用了不存在的事实候选：{sorted(unknown)}"
                )
            fact_locator_ids = {
                locator_id
                for ref in item.fact_candidate_refs
                for locator_id in facts_by_ref[ref].locator_ids
            }
            unrelated_locators = set(item.locator_ids) - fact_locator_ids
            if unrelated_locators:
                raise ValueError(
                    f"{item.candidate_ref} 的定位未被关联事实覆盖："
                    f"{sorted(unrelated_locators)}"
                )
        event_occurrences: dict[tuple, list[EvidenceEventDraft]] = {}
        for item in self.event_candidates:
            start_text = item.start_range.source_text if item.start_range else None
            if (
                item.profile_lane != ProfileLane.TEST_EXAM_SCORE
                or item.duration_status != DurationStatus.SINGLE
                or not start_text
                or re.search(r"(?:[01]?\d|2[0-3])[:：][0-5]\d", start_text) is None
            ):
                continue
            key = (
                item.event_type,
                item.profile_lane,
                json.dumps(item.start_range.model_dump(mode="json"), sort_keys=True),
                (
                    json.dumps(item.end_range.model_dump(mode="json"), sort_keys=True)
                    if item.end_range is not None
                    else None
                ),
                item.duration_status,
                item.record_time,
                item.candidate_source_semantics,
            )
            event_occurrences.setdefault(key, []).append(item)
        duplicated_occurrences = [
            sorted(event.candidate_ref for event in group)
            for group in event_occurrences.values()
            if len(group) > 1
        ]
        if duplicated_occurrences:
            raise ValueError(
                "同一检验检查在同一明确时刻被拆成多条事件；请合并为一条事件，并合并其"
                f"事实引用与定位：{sorted(duplicated_occurrences)}"
            )
        actual_refs = self.actual_exposure_fact_refs
        if actual_refs != sorted(set(actual_refs)):
            raise ValueError("actual_exposure_fact_refs 必须升序且无重复")
        unknown_actual = set(actual_refs) - fact_refs
        if unknown_actual:
            raise ValueError(
                "actual_exposure_fact_refs 引用了不存在的事实候选："
                f"{sorted(unknown_actual)}"
            )
        invalid_actual = sorted(
            ref
            for ref in actual_refs
            if facts_by_ref[ref].profile_lane != ProfileLane.MEDICATION
            or facts_by_ref[ref].polarity != FactPolarity.AFFIRMED
        )
        if invalid_actual:
            raise ValueError(
                "actual_exposure_fact_refs 只能引用肯定的药物使用事实候选："
                f"{invalid_actual}"
            )
        non_exposure_refs = self.non_exposure_medication_fact_refs
        if non_exposure_refs != sorted(set(non_exposure_refs)):
            raise ValueError(
                "non_exposure_medication_fact_refs 必须升序且无重复"
            )
        unknown_non_exposure = set(non_exposure_refs) - fact_refs
        if unknown_non_exposure:
            raise ValueError(
                "non_exposure_medication_fact_refs 引用了不存在的事实候选："
                f"{sorted(unknown_non_exposure)}"
            )
        invalid_non_exposure = sorted(
            ref
            for ref in non_exposure_refs
            if facts_by_ref[ref].profile_lane != ProfileLane.MEDICATION
            or facts_by_ref[ref].polarity != FactPolarity.AFFIRMED
        )
        if invalid_non_exposure:
            raise ValueError(
                "non_exposure_medication_fact_refs 只能引用肯定的药物相关事实候选："
                f"{invalid_non_exposure}"
            )
        overlap = sorted(set(actual_refs) & set(non_exposure_refs))
        if overlap:
            raise ValueError(f"药物事实不能同时归入实际暴露与非暴露：{overlap}")
        affirmed_medication_refs = {
            ref
            for ref, fact in facts_by_ref.items()
            if fact.profile_lane == ProfileLane.MEDICATION
            and fact.polarity == FactPolarity.AFFIRMED
        }
        classified_medication_refs = set(actual_refs) | set(non_exposure_refs)
        if classified_medication_refs != affirmed_medication_refs:
            missing = sorted(affirmed_medication_refs - classified_medication_refs)
            unexpected = sorted(classified_medication_refs - affirmed_medication_refs)
            raise ValueError(
                "每条肯定药物相关事实都必须明确归入实际暴露或非暴露："
                f"未归类={missing}；错误归类={unexpected}"
            )
        exposure_refs = {
            ref
            for exposure in self.exposure_candidates
            for ref in exposure.fact_candidate_refs
        }
        if exposure_refs != set(actual_refs):
            missing = sorted(set(actual_refs) - exposure_refs)
            unexpected = sorted(exposure_refs - set(actual_refs))
            raise ValueError(
                "明确实际用药或治疗事实与暴露候选未闭合："
                f"缺少暴露={missing}；非实际暴露引用={unexpected}"
            )
        return self


# ---------------------------------------------------------------------------
# System contract (Chinese-native)
# ---------------------------------------------------------------------------

DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE = (
    "请从本次资料页组中逐页提取临床事实候选，并严格按指定结构返回。"
)

_PROMPT_LAYOUT_VERSION = "phase5/evidence-normalizer-prompt/v24"
_MAX_PROMPT_CHARS = 100_000


class EvidenceNormalizerPromptTooLong(ValueError):
    def __init__(self, actual_chars: int) -> None:
        self.actual_chars = actual_chars
        super().__init__(
            f"本次个例资料输入为 {actual_chars} 字符，超过单次处理上限 "
            f"{_MAX_PROMPT_CHARS}；请缩小连续页组后重试"
        )


_SET_LIKE_DRAFT_ARRAY_FIELDS = frozenset(
    {
        "affected_locator_ids",
        "affected_pages",
        "affected_requirement_ids",
        "fact_candidate_refs",
        "locator_ids",
        "supported_requirement_ids",
    }
)

# 视觉观察补充材料的硬边界声明（C-4）：只作来源绑定引用与 OCR 风险提示，
# 不覆盖 OCR/有效文本，不得作为唯一定位或断言依据，不得据此输出入排结论。
_VISUAL_OBSERVATION_PROMPT_BOUNDARY = (
    "以上 visual_observations 是对应页的选择性视觉观察引用材料与 OCR 风险提示，"
    "均为来源绑定的补充材料：不覆盖、不改写、不替代 pages.effective_text 与任何"
    " OCR 原文；观察正文与 risk_reasons 不得写入 effective_text、locator 或候选"
    "原文；一切事实/事件/暴露候选仍必须锚定 locators 中的真实 "
    "locator 与有效文本原句，不得以视觉观察作为唯一断言依据；不得据视觉观察输出"
    "入排结论、期望状态或“通过/不通过”标签；risk_reasons 仅提示对应页可能存在"
    " OCR 风险，不得用于隐藏、筛选或排序候选。若视觉观察提示手写、便签、图表"
    "或边注中有临床内容，而对应页的有效原文和定位没有这段内容，须以本页的"
    " unresolved_items 说明原件位置、可辨与不可辨部分及待核实问题；不要补造"
    " locator 或事实，也不要把书写者未明的批注当作研究者书面判断。"
)

_SCHEMA_REPAIR_CONTRACT = (
    "不得通过删除已有候选、清空四类列表、遗漏字段或取消逐页证据闭合来规避错误；"
    "若输入有效文本包含明确事实，必须重新阅读原始页文本并恢复对应候选，不能重复返回全空列表；"
    "肯定或否定候选必须补全指向原句与定位的 assertion_basis，未解决项必须补全受影响页或定位。"
    "若错误指出断言对象未逐字出现，必须从该候选已有 assertion_text 中直接截取最短连续临床名词"
    "作为 asserted_object 和 assertion_basis.asserted_object，两处必须填同一个字符串；"
    "对象因原句中的“无/未/有/等”等虚词而不连续时，必须连同虚词原样截取原句中的连续片段；"
    "不得添加原句未连续出现的修饰词或后缀，"
    "不得改写原句，也不得删除该候选来规避修复。"
    "若错误指出同一检验检查时点被拆成多条事件，必须合并为一条事件，并保留全部相关"
    "事实引用与定位；不得遗漏任何事实候选。"
    "若错误指出肯定或否定候选缺少规范值：原句明确给出定量结果时，必须把原数值和原单位分别填入"
    "raw_value、canonical_value 和 unit；原句只有定性存在或否认时，affirmed 的 raw_value 与"
    "canonical_value 均填 true，negated 均填 false，unit 填 JSON null。不得用说明文字代替值。"
    "持续状态与日期必须相容：ongoing 不得携带 end_range；ended 只能在原文明确"
    "给出终止日期并填写 end_range 时使用；两者不能同时明确时改为 unknown，不得删除候选。"
)

_SYSTEM_CONTRACT = (
    "你是临床证据规范化助手（Evidence Normalizer）。你的唯一任务是将本次调用"
    "提供的单逻辑文档连续页组内的已校对有效文本，转化为结构化候选与未解决项。"
    "本次调用仅处理一个逻辑文档 logical_document_id 的连续页 page_numbers 的"
    "有效文本。不得跨逻辑文档、跨受试者、跨审核节点、跨证据快照或虚构页码。所有"
    "引用的 locator_id 必须来自本次输入提供的 locators。localized_text "
    "是定位覆盖的有效原文；不得自创 locator、页码、坐标或红框；"
    "没有 localized_text 的 page_only 定位不能作为"
    "肯定或否定断言依据。"
    "输入 context 是本次调用冻结的资料语义：必须结合 document_type、source_party、"
    "current_review_stage 和 workflow_stage_id 理解正文及来源强度。document_record_time"
    "为空表示元数据未单独提供资料记录时间，不得用上传时间、筛选日期、操作时间或"
    "节点锚点补写；仅当正文有真实定位支持时，才可在候选中抽取 record_time。"
    "原文只有当地日期或钟点、未明示时区时，不得自行换算为 UTC 或填入 record_time；"
    "其临床发生日期仍应按原文精度保留在 date_range、start_range 或 end_range。"
    "related_requirements 是当前节点已经到期的方案资料要求，只用于提示应重点识别的"
    "事实类型和证据来源，不是入排判断指令。不得据此虚构正文未记载的事实、把未提及"
    "改写为否认，也不得输出要求是否满足或受试者是否符合。"
    "事实候选仅在正文实际支持某条 related_requirements 时，才把该 requirement_id 写入"
    "supported_requirement_ids；不得按标题、描述或相似词猜测绑定。未明确支持任何要求时"
    "必须返回空列表。绑定 ID 必须来自本次冻结输入。fact_type 是临床展示分类，不要求与"
    "资料要求的 fact_type 同名；是否支持该要求只由正文语义与显式 requirement_id 表达。"
    "只允许输出 fact_candidates、event_candidates、exposure_candidates、"
    "actual_exposure_fact_refs、non_exposure_medication_fact_refs 与 unresolved_items。"
    "必须逐条复核每一条 polarity=affirmed 且 profile_lane=medication 的事实候选，并且"
    "恰好归入以下两个清单之一，不得靠遗漏清单项回避判断。actual_exposure_fact_refs 是"
    "本次事实候选中原文明确证明受试者已经使用、正在使用、接受给药或已有生效医嘱的"
    "candidate_ref 升序去重清单；计划、建议、讨论、发放、领取、携回、退回、持有、"
    "药名清单、否认和不确定陈述均不得列入。该清单必须与所有 exposure_candidates 的"
    "fact_candidate_refs 并集完全一致，不能漏项，也不能多列。"
    "non_exposure_medication_fact_refs 只列计划、建议、讨论、发放、领取、携回、退回、持有、"
    "药名清单或其他不能证明实际使用的肯定药物相关事实；若原文明确记载既往某次实际给药或"
    "使用，即使来自筛选病历对既往史的转述，也必须归入 actual_exposure_fact_refs。绝不输出接受事实、冲突裁决、EvidenceExpectation"
    "状态、入排结论、ReviewRun、ActionRequest、blocking_level、节点主状态或任何"
    "“通过/不通过”标签。绝不输出模型置信度作为阈值；model_uncertainty 仅作为"
    "候选质量审计字段（0-1），不得用于筛选、隐藏或首屏排序。"
    "按需抽取 P5-R02 覆盖类别：人口学、目标疾病、症状体征、诊断与病程、现病史/"
    "既往史、过敏、感染与免疫、生育、家族史、社会/环境暴露、既往研究、献血/输血/"
    "移植、检验、检查、评分、手术/操作、非药物治疗及药物暴露。药物暴露必须保留"
    "原始药名/类别、适应证、剂量、单位、频次、途径、起止日期范围、持续状态和来"
    "源类型；本阶段不判断是否违反洗脱期。药名、类别、适应证及给药细节只能逐字取自"
    "有定位的原文；不得补全残缺药名，不得把常识、相似名称或模型推测写入候选字段。"
    "原文不完整或只能推测时，保留原始可见文字，并另建未解决项说明待核对内容。"
    "每条事实和事件必须从 ProfileLane 的 13 个稳定枚举中选择唯一 profile_lane。"
    "该字段只表示 Patient Profile 的临床主题归属，不表示风险、异常或入排判断；"
    "不得通过自创 fact_type/event_type 或项目特异标签绕过枚举。按下列互斥语义选择："
    "study_milestone 只收知情、筛选、随机、给药等研究节点；demographics 收人口学；"
    "target_disease 收目标疾病的诊断与病程；symptoms_signs 收症状与体征；"
    "medical_history 收不属于目标疾病、感染免疫或其他专项类别的一般病史；"
    "medication 收药物使用；non_drug_treatment 收手术、操作及其他非药物治疗；"
    "test_exam_score 收检验、检查与评分；allergy_infection_immune 收过敏、感染与免疫相关记录；"
    "reproductive 收生育、妊娠与避孕；social_environmental 收吸烟、饮酒、职业及环境暴露；"
    "special_history 只收家族史、既往研究、献血输血或移植等专项史；"
    "evidence_quality 只收资料质量与溯源问题。同一临床事件在事实与事件候选中必须使用同一主题归属。"
    "主题交叉时按临床对象而非句式选择：具名药物的使用、未使用及疗效记录归 medication；"
    "手术或操作史无论肯定还是否定均归 non_drug_treatment；量表条目、检查项目及其结果归"
    "test_exam_score，非量表叙述的主观症状归 symptoms_signs；target_disease 只收目标疾病本身"
    "的诊断、病程和疾病状态，鉴别诊断中被否认的其他疾病按其自身临床主题归类。"
    "exposure_candidates 只表示原文明确肯定发生的药物或治疗暴露，必须引用至少一条"
    "肯定的用药/治疗事实，而且原文必须明确陈述该受试者已经使用、正在使用、接受给药，"
    "或存在已经生效的明确医嘱。邮件讨论、审核意见、治疗建议、待核实条目、方案规则、"
    "假设性表述、药物名称清单或他人用药均不构成该受试者的实际暴露。药品的发放、领取、携回、"
    "带回、退回、清点、持有或计划使用，本身也不能证明已实际使用；只有同一有定位的原文另外明确记载"
    "已给药、已使用、正在使用或已生效医嘱时，才可形成暴露。可以按原文形成"
    "讨论或建议事实，但不得生成 exposure_candidate。疾病名称和症状名称不能作为药名。否认用药或否认病史仍须"
    "按原文生成对应的否定 fact_candidate，但不得额外生成 exposure_candidate。"
    "凡已生成事实候选且原文明确给出该事实的发生、采样、检查、手术或治疗日期，"
    "必须同时生成引用该事实的 event_candidate；肯定用药或治疗事实必须同时生成"
    "exposure_candidate。输出前必须逐条对账肯定用药事实、用药事件与药物暴露：同一药物的不同给药日期或剂量"
    "是不同暴露，不得因药名相同而合并或漏掉任何一次明确给药。原文没有日期时不得为了补齐事件而借用"
    "记录时间或节点锚点。"
    "同一份检验或检查报告中的同一次采样、检查或评分只生成一条 event_candidate，并在"
    "该事件中引用本次记录支持的全部事实候选及定位；不得按分析物、分项结果或单个指标"
    "重复生成多条同形事件。不同时间、不同标本、不同检查或彼此独立的给药仍分别形成事件。"
    "严格区分事件发生时间、起止范围、记录时间、资料上传时间和审核节点锚点。年/"
    "年月/日分别保留 precision 与确定性上下界（年：1-1至12-31；年月：当月首日"
    "至末日；日：上下界相同；未知：上下界为空，绝不借用筛选日、上传日或操作日）。"
    "持续状态仅用持续/已结束/间歇/单次/未知；“既往”不等于已结束，不得自动推断"
    "终止日期。ongoing 必须不带 end_range；ended 必须有原文明确给出的 end_range；"
    "持续状态与终止日期不能同时明确时使用 unknown，不得删除候选规避。"
    "每条明确临床陈述均单独形成事实候选，尤其是带数值和单位的检验、生命体征、评分"
    "或检查结果，不得改写成未解决项。被断言对象必须是 assertion_text 中逐字出现的最短"
    "临床名词或名词短语，例如原句“患者否认糖尿病病史”使用“糖尿病病史”，原句“收缩压"
    "120 mmHg”使用“收缩压”；不得扩写成问句、解释句、目标疾病说明或原文未出现的名称。"
    "原句以“无/未/有/等”等虚词分隔修饰语与对象时，必须连同虚词截取原句中的连续片段，"
    "例如原句“家族无遗传病病史”应使用“遗传病病史”，不得把被虚词隔开的"
    "“家族遗传病病史”当作逐字对象。"
    "未解决项只记录本次页组正文中确实出现但无法确认的内容，或本次页组自身明确可见的"
    "缺页、残缺和 OCR 风险。单页或单份资料未出现某项要求，不代表整个证据包缺失：不得"
    "据此生成未检查、未执行、未记录或需补充资料等跨文件缺口。跨文件完整性只由系统在"
    "全部页组处理完成后统一核对。不得因为原文只记录收缩压，就自行推断舒张压、心率"
    "缺失；不得从任何未提及内容制造未解决项。"
    "仅当未解决项能明确对应本次冻结的 related_requirements 时，才填写"
    "affected_requirement_ids 和 gap_type；两者必须同时提供或同时不提供："
    "无资料要求绑定时 affected_requirement_ids 必须为 [] 且 gap_type 必须为 null；"
    "有绑定时列表不得为空且 gap_type 不得为 null。ID 必须来自本次输入。"
    "不得从要求描述或正文沉默猜测缺口。referenced_file_missing 还必须给出"
    "referenced_file_id；其他缺口不得携带该字段。"
    "肯定/否定事实必须携带明确被断言对象、规范值与 assertion_basis。单一数值规范值必须"
    "填写真实单位，无量纲数值用 unitless。"
    "标识编号不是测量值：明确为编号时 value_kind=identifier，raw_value 与 canonical_value"
    "均逐字保存为相同字符串（包括前导零），unit=null；不得将检验、剂量、评分等测量值标为编号。"
    "其余事实 value_kind=value。"
    "血压、比较值或多分量结果可用只含数值、比较符、"
    "分隔符和阳性/阴性标记的紧凑字符串并保留共同单位，不得写成叙述句；其他文本或布尔"
    "规范值的 unit 必须是 JSON null，"
    "不得填写说明性文字。assertion_basis 只填写对象、原句和 locator；源文本哈希、运行号、"
    "调用号、候选主键和创建时间均由系统根据冻结输入补全，不得自行输出。候选使用本次响应"
    "内唯一的 candidate_ref；事件和暴露仅用 fact_candidate_refs 引用本次响应内的事实候选。"
    "否定必须来自指向被断言对象的明确否定原句；空白、未勾选、邻近句否定、"
    "缺页或未提及只能生成 unresolved_items 中的资料缺口，不得生成否定/正常事实。"
    "unknown 必须同时把 raw_value、canonical_value、unit 和 assertion_basis 填为 JSON null；"
    "不得携带被断言值、单位或依据。沉默与未提及不生成否认事实。"
    "candidate_source_semantics 只能逐字使用以下五个中文值之一：同期客观结果、"
    "既往原始资料、当前研究病历直接记录、筛选病历转述、无法确认来源；不得翻译成"
    "英文、缩写或自造标签。仅有筛选病历转述的阳性"
    "长期史可作为较弱事实并生成溯源提醒。来源语义必须同时受本次冻结的 "
    "document_type/source_party 和定位原文约束：筛选或当前研究病历直接记录的本研究操作、"
    "当次观察或书面判断使用“当前研究病历直接记录”；其中对既往病史、长期病程或既往用药的"
    "问询、摘述使用“筛选病历转述”。仅因原文出现过去日期、外院名称或既往用药，不得声称“既往原始资料”；"
    "只有定位实际属于已提供的既往原始记录时才可使用。同期检验检查报告使用“同期客观结果”。"
    "药名仅因版面自动换行而分布在同页相邻定位时，应按连续可见原文还原完整药名，并让事实、"
    "事件和暴露引用覆盖该药名的全部相邻定位，不得误报为残缺。跨页后仍缺字、定位不相邻或"
    "无法从连续可见文字唯一确定完整药名时，必须使用未解决编码 medication_name_incomplete，"
    "不得为该真正残缺药名生成事实、事件或 exposure_candidate；同一定位内其他完整药名仍须独立"
    "抽取，不得一并丢弃。来源语义为“无法确认来源”的用药陈述可保留为待溯源事实，"
    "但不得生成 exposure_candidate。每个候选的 locator_ids 必须升序、无重复"
    "且全部属于本调用可用集合；断言依据的 locator 必须在候选定位集合内且对象名"
    "一致。事件或暴露候选的每个 locator 还必须至少被其 fact_candidate_refs 引用的"
    "一条事实候选覆盖；不得只给事件或暴露增加表头、日期栏或报告页定位。"
    "精确重复候选通过稳定内容身份合并，但保留全部定位；值/极性/日期/持续"
    "状态不兼容时不得合并，改为并列候选并由确定性门禁归入冲突组（模型不得自行择优）。"
    "所有 message/reason/对象名称使用中文原生临床措辞。输出必须是一个严格符合"
    "指定 JSON Schema 的 JSON 对象，无 Markdown、无解释、无日志、无额外文字。"
    "不得复制 Schema 的 $defs/properties 定义字段。额外字段一律拒绝。"
    "对无法确认的页、字段、日期精度、单位、否定范围、OCR 风险等，在 unresolved_items"
    "中用中文说明 code/message/affected_pages/affected_locator_ids/reason，不得遗漏"
    "整页而不给出原因。若本次页组无任何可抽取事实，也返回空候选列表并通过"
    "unresolved_items 说明已逐页闭合，不得返回空字符串或省略字段。"
    "未解决项只能记录候选抽取后仍然存在的不确定性，不能替代清晰事实候选；同一条原文"
    "可以同时生成事实候选和日期、单位或来源未解决项。输入含 page_review 时，只能从"
    "accepted_pages 的 accepted_observations 中已核实事实和手写观察生成候选；条款证据关系仅作审核上下文，不能代替双读一致的具体事实。"
    "page_review_visual 定位的文字来自绑定的原始判读摘录，source_text_sha256是该摘录的哈希，不是页图哈希；"
    "pending_observation_groups仅合并重复元数据：shared适用于组内每一条observations.detail，position保留原顺序；"
    "各条仍是独立的待核对内容，不因分组而视为一致，不可用于生成已核实事实。"
    "可直接引用此定位及对应观察，不要求摘录出现在OCR文字内，不得改写摘录或拼接两个来源为连续原句。"
    "pending_observation_groups 仅供说明未解决项和定位原件，不得生成已采信事实候选。ocr_sidecar_pages 只用于"
    "文字锚定位与核对。R3 每个事实候选的 source_observation_refs 必须引用 accepted_observations 中的"
    "source_observation_ref，不得引用待核对项。不得覆盖页级对账，也不得从已舍弃页面的侧车文字另造候选。页级冲突"
    "必须保留。已采信观察的 context.time_text 仅是页读关联，不自动证明事件时间或用药起止时间；"
    "须在所引原文中核对日期与该事件的关系。就诊、处方、药品发放、实际使用及停药的时间不得互相代替。"
    "仅明确用药而未明确起止时间时，保留用药事实和暴露，起止范围使用未知，并记录具体时间缺口；"
    "不得因两个主读都填写同一关联日期就将其推断为开始或结束给药日。页级冲突"
    "必须保留为对应页面的未解决项，不得自行择优。兼容旧任务仅含 pages.effective_text 时，"
    "该字段是已经校对的当前有效文本：只要非空文本中有明确否定、肯定、数值、日期、用药"
    "或治疗陈述，就必须生成对应候选。除非文本本身为空、残缺或输入明确给出识别风险，"
    "否则不得把页面标为不可读，也不得仅靠未解决项闭合该页。"
)

# 允许的候选来源强度语义（与 facts.py 来源强度派生输入一致，模型侧使用）
_ALLOWED_CANDIDATE_SOURCE_SEMANTICS = frozenset(
    {
        "同期客观结果",
        "既往原始资料",
        "当前研究病历直接记录",
        "筛选病历转述",
        "无法确认来源",
    }
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def evidence_normalizer_prompt_template_sha256(prompt_template: str) -> str:
    """对模板、合同、生成 schema、修复规则与布局的完整可审计哈希。"""
    return _sha256(
        "\n\n".join(
            (
                _PROMPT_LAYOUT_VERSION,
                prompt_template.strip(),
                _SYSTEM_CONTRACT,
                _VISUAL_OBSERVATION_PROMPT_BOUNDARY,
                _SCHEMA_REPAIR_CONTRACT,
                _compact_schema(),
            )
        )
    )


def _strip_schema_titles(node) -> None:
    """剥离 pydantic 生成的装饰性 ``title`` 字段（不影响校验语义）。

    ``title`` 只是对象/字段名回显，对受限解码语法与模型行为均无约束作用；
    从提示与 ``response_format`` 中剥离可稳定缩小每份 Schema 的重复体积。
    """
    if isinstance(node, list):
        for item in node:
            _strip_schema_titles(item)
        return
    if not isinstance(node, dict):
        return
    node.pop("title", None)
    for value in node.values():
        _strip_schema_titles(value)


def evidence_normalizer_json_schema() -> dict:
    """返回适合约束生成的完整 schema，要求模型显式交代每个已定义字段。

    Pydantic 对带默认值字段默认不写入 ``required``，这适合普通 API 解码，但会让
    结构化生成模型用“省略字段”逃避逐页闭合与断言依据。这里仅收紧字段出现性；
    可空字段仍保留 ``null``，跨字段医学语义继续由运行时合同和确定性门禁负责。
    """
    schema = deepcopy(EvidenceNormalizerDraftOutput.model_json_schema())

    def require_declared_properties(node) -> None:
        if isinstance(node, list):
            for item in node:
                require_declared_properties(item)
            return
        if not isinstance(node, dict):
            return
        properties = node.get("properties")
        if isinstance(properties, dict) and properties:
            node["required"] = list(properties)
        for value in node.values():
            require_declared_properties(value)

    require_declared_properties(schema)
    _strip_schema_titles(schema)
    unresolved = schema.get("$defs", {}).get("EvidenceNormalizerUnresolvedItem")
    if not isinstance(unresolved, dict):
        raise RuntimeError("证据规范化生成结构缺少未解决项定义")
    linked_gap_types = [
        gap_type.value
        for gap_type in (
            GapType.RECORD_INCOMPLETE,
            GapType.DESCRIPTION_INSUFFICIENT,
            GapType.REQUIRED_PROCEDURE_NOT_DONE,
            GapType.RESULT_FIELDS_MISSING,
            GapType.DATE_OR_ANCHOR_MISSING,
            GapType.PROVENANCE_FOLLOWUP,
            GapType.OCR_OR_PARSE_RISK,
            GapType.HISTORICAL_SOURCE_UNAVAILABLE,
        )
    ]
    unresolved["oneOf"] = [
        {
            "properties": {
                "affected_requirement_ids": {"maxItems": 0},
                "gap_type": {"type": "null"},
                "referenced_file_id": {"type": "null"},
            }
        },
        {
            "properties": {
                "affected_requirement_ids": {"minItems": 1},
                "gap_type": {"enum": linked_gap_types},
                "referenced_file_id": {"type": "null"},
            }
        },
        {
            "properties": {
                "affected_requirement_ids": {"minItems": 1},
                "gap_type": {"const": GapType.REFERENCED_FILE_MISSING.value},
                "referenced_file_id": {"type": "string", "minLength": 1},
            }
        },
    ]
    return schema


def _compact_schema() -> str:
    return json.dumps(
        evidence_normalizer_json_schema(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def evidence_normalizer_compact_schema() -> str:
    """对外暴露的紧凑严格 JSON Schema 字符串（用于 prompt 与测试）。"""
    return _compact_schema()


def _visual_observation_prompt_payload(
    observations: Sequence[SelectiveVisionObservationAttachment],
) -> list[dict]:
    """观察附件的确定性提示投影（按身份哈希升序，不含密钥或图像）。

    OCR 风险提示必须指向具体 OCR 原文身份：未携带 OCR 绑定的观察只作为
    补充材料进入提示，其 ``risk_reasons`` 不渲染（置空），避免无来源的风险
    提示影响候选判断。
    """
    return [
        {
            "observation_identity_sha256": item.observation_identity_sha256,
            "source_ref": item.source_ref,
            "page_number": item.page_ordinal,
            "ocr_page_bound": item.ocr_page_id is not None,
            "ocr_page_id": item.ocr_page_id,
            "risk_reasons": (
                sorted(item.risk_reasons) if item.ocr_page_id is not None else []
            ),
            "observation_text": item.observation_text,
        }
        for item in sorted(observations, key=lambda item: item.observation_identity_sha256)
    ]


def _model_input_payload(evidence_input: EvidenceNormalizerInput, *, pending_details_retained: bool = False) -> dict:
    """Project the frozen audit contract into the smallest model-facing input.

    仅省略运行身份和哈希等模型不需要的审计字段。有效原文与
    定位原文均保持逐字不变，不向 ``effective_text`` 插入任何渲染标记。
    """
    payload = {
        "context": {
            "document_type": evidence_input.context.document_type,
            "source_party": evidence_input.context.source_party,
            "document_record_time": (
                evidence_input.context.document_record_time.model_dump(mode="json")
                if evidence_input.context.document_record_time is not None
                else None
            ),
            "current_review_stage": evidence_input.context.current_review_stage.value,
        },
        "related_requirements": [
            {
                "requirement_id": item.requirement_id,
                "fact_type": item.fact_type,
                "required_source_types": item.required_source_types,
                "allows_screening_record_transcription": (
                    item.allows_screening_record_transcription
                ),
                "requires_contemporaneous_objective_source": (
                    item.requires_contemporaneous_objective_source
                ),
                "description": item.description,
            }
            for item in evidence_input.related_requirements
        ],
        "ocr_sidecar_pages": [
            {
                "page_number": page.page_number,
                "sidecar_transcription": page.effective_text,
            }
            for page in evidence_input.pages
        ],
        "locators": [
            {
                "locator_id": item.locator_id,
                "page_number": item.page_number,
                "precision": item.precision.value,
                "localized_text": item.localized_text,
                **({"page_review_visual": True}
                   if item.page_review_visual is not None else {}),
            }
            for item in evidence_input.available_locators
        ],
    }
    if evidence_input.page_review is None:
        # 兼容 Phase 5 已冻结任务；R3 新任务必须携带页级判读附件。
        payload["pages"] = payload.pop("ocr_sidecar_pages")
        for page in payload["pages"]:
            page["effective_text"] = page.pop("sidecar_transcription")
        return payload

    reviews = {
        item.page_review_id: item for item in evidence_input.page_review.reviews
    }
    accepted_pages = []
    from app.projections.page_review_pending import pending_page_observations
    from app.projections.page_review_sources import accepted_observations
    for reconciliation in evidence_input.page_review.reconciliations:
        source_reviews = [reviews[item] for item in reconciliation.page_review_ids]
        facts = [
            fact.model_dump(mode="json")
            for review in source_reviews
            for fact in review.facts
            if fact.normalization_key in reconciliation.accepted_fact_keys
        ]
        accepted_pages.append(
            {
                "page_number": source_reviews[0].page_number,
                "accepted_facts": facts,
                "accepted_observations": accepted_observations(source_reviews, reconciliation,
                    include_clause_signals=evidence_input.page_review.visual_source_policy is None),
                "pending_observations": pending_page_observations(source_reviews, reconciliation,
                    page_texts={(page.source_document_version_id, page.page_number): page.effective_text
                                for page in evidence_input.pages}),
                "accepted_clause_signals": [
                    item.model_dump(mode="json")
                    for item in reconciliation.accepted_clause_signals
                    if item.region is not None
                ],
                "accepted_handwriting": [
                    item.model_dump(mode="json")
                    for item in reconciliation.accepted_handwriting
                ],
                "fact_conflicts": [
                    item.model_dump(mode="json")
                    for item in reconciliation.fact_conflicts
                ],
                "signal_conflicts": [
                    item.model_dump(mode="json")
                    for item in reconciliation.signal_conflicts
                ],
                "handwriting_conflicts": [
                    item.model_dump(mode="json")
                    for item in reconciliation.handwriting_conflicts
                ],
            }
        )
    from app.projections.page_review_model_input import compact_page_review_input
    payload["page_review"] = compact_page_review_input({
        "accepted_pages": sorted(
            accepted_pages, key=lambda item: item["page_number"]
        ),
        "page_dispositions": [
            {
                "page_number": item.page_number,
                "disposition": item.disposition.value,
                "discard_reason": item.discard_reason,
            }
            for item in evidence_input.page_review.entries
        ],
    })
    if pending_details_retained:
        from app.projections.page_review_model_input import retained_pending_summary
        payload["page_review"] = retained_pending_summary(payload["page_review"])
    return payload


def build_evidence_normalizer_prompt(
    evidence_input: EvidenceNormalizerInput,
    *,
    prompt_template: str,
    visual_observations: Sequence[SelectiveVisionObservationAttachment] | None = None,
    include_output_schema: bool = True,
    pending_details_retained: bool = False,
    reference_aliases: NormalizerReferenceAliases | None = None,
    verified_scope_prompt: bool = False,
) -> str:
    """从冻结输入构建唯一可审计的 prompt，不含隐藏自由文本。

    ``visual_observations`` 非空时追加来源绑定的视觉观察引用材料段与硬边界
    声明；该材料由运行级 ``visual_observation_scope_sha256`` 冻结并可重建复核，
    永不修改输入 JSON 中的有效文本或 locator。

    ``include_output_schema=False`` 供已在 ``response_format`` 中以 JSON Schema
    受限解码强制输出结构的传输使用：此时同一份 Schema 不再在提示内重复内嵌
    （消除重复 Schema）；输出结构约束本身不变，仍由同一 schema 与本地门禁负责。
    """
    payload = _model_input_payload(evidence_input, pending_details_retained=pending_details_retained)
    if reference_aliases is not None:
        payload = reference_aliases.transform(payload)
    system_contract = _SYSTEM_CONTRACT
    if verified_scope_prompt:
        if not pending_details_retained or evidence_input.page_review is None:
            raise ValueError("已核实观察提示须绑定双读结果及待核对原文保全方式")
        from app.agents.verified_evidence_prompt import VERIFIED_EVIDENCE_SYSTEM_CONTRACT
        system_contract = VERIFIED_EVIDENCE_SYSTEM_CONTRACT
    head = f"{prompt_template.strip()}\n\n{system_contract}\n\n"
    if reference_aliases is not None:
        from app.agents.verified_evidence_prompt import SHORT_REFERENCE_INSTRUCTION
        head += SHORT_REFERENCE_INSTRUCTION
    if include_output_schema:
        head += f"输出结构：{_compact_schema()}\n\n"
    sections = [
        head + f"本次输入：{json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}\n\n"
    ]
    if visual_observations:
        sections.append(
            "视觉观察补充材料（来源绑定引用，非 OCR 原文）：\n"
            f"{json.dumps(_visual_observation_prompt_payload(visual_observations), ensure_ascii=False, sort_keys=True)}\n\n"
            f"{_VISUAL_OBSERVATION_PROMPT_BOUNDARY}\n\n"
        )
    if pending_details_retained and evidence_input.page_review is not None:
        from app.agents.verified_evidence_prompt import RETAINED_PENDING_INSTRUCTION
        sections.append(RETAINED_PENDING_INSTRUCTION)
    else:
        sections.append(
        "现在逐页处理本次输入。有效文本中的每条明确临床陈述均须进入对应候选；"
        "确实无法确认的内容须进入关联具体页或定位的未解决项。仅返回完整 JSON 对象。"
        )
    prompt = "".join(sections)
    # Preserve the legacy guard; R3 cloud inputs must not inherit a local-model cap.
    if evidence_input.page_review is None and len(prompt) > _MAX_PROMPT_CHARS:
        raise EvidenceNormalizerPromptTooLong(len(prompt))
    return prompt


def _validation_error_summary(exc: ValidationError) -> str:
    errors = []
    for error in exc.errors(include_url=False, include_context=False, include_input=False):
        location = ".".join(str(part) for part in error["loc"])
        errors.append(f"{location}: {error['msg']}")
    return "；".join(errors)


# 机械逐字还原的漂移边界：低思考强度模型最常见的转写漂移是给对象添加 1-2 字
# 类别后缀（如“治疗/检查/使用”），或漏抄原句中 1-2 字虚词（如“无/有/等”）。
# 超出该漂移或短于最短修复长度时不做机械修复，交回逐字门禁与修复提示处理。
_MAX_ASSERTED_OBJECT_DRIFT_CHARS = 2
_MIN_MECHANICAL_OBJECT_CHARS = 3
_PLAIN_NUMERIC_SCALAR = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$"
)
_COMPACT_MEASUREMENT_SCALAR = re.compile(
    r"^[0-9.+\-<>=/()（）\[\]，,;；:：%％*×xX阳性阴性]+$"
)


def _mechanical_verbatim_repair(asserted_object: str, assertion_text: str) -> str | None:
    """从断言原句中机械还原逐字可验证的被断言对象；无法唯一还原时返回 None。

    只做两类不引入原句之外字符的语义保持修复，结果必须是折叠空白后
    assertion_text 的连续子串：
    - 去后缀/前缀：模型给对象添加了原句该处没有的 1-2 字后缀或前缀；
    - 补虚词：模型漏抄了原句中的 1-2 字虚词，原句中存在把模型对象作为子序列
      包含的唯一最短连续窗口。
    截取结果不唯一（多个等长候选并存）时返回 None，保留原样交由逐字门禁
    与 schema 修复提示处理，不替模型猜测临床对象。
    """
    obj = " ".join(asserted_object.split())
    text = " ".join(assertion_text.split())
    if len(obj) < _MIN_MECHANICAL_OBJECT_CHARS or obj in text:
        return None
    trimmed: set[str] = set()
    for size in range(1, _MAX_ASSERTED_OBJECT_DRIFT_CHARS + 1):
        if len(obj) - size < _MIN_MECHANICAL_OBJECT_CHARS:
            continue
        for candidate in (obj[:-size], obj[size:]):
            if candidate in text:
                trimmed.add(candidate)
    if trimmed:
        shortest = min(len(item) for item in trimmed)
        best = [item for item in trimmed if len(item) == shortest]
        return best[0] if len(best) == 1 else None
    windows: set[str] = set()
    for start, char in enumerate(text):
        if char != obj[0]:
            continue
        pos = start
        for expected in obj[1:]:
            pos = text.find(expected, pos + 1)
            if pos < 0:
                break
        else:
            window = text[start : pos + 1]
            if len(window) - len(obj) <= _MAX_ASSERTED_OBJECT_DRIFT_CHARS:
                windows.add(window)
    if windows:
        shortest = min(len(item) for item in windows)
        best = [item for item in windows if len(item) == shortest]
        return best[0] if len(best) == 1 else None
    return None


def _normalize_numeric_scalar(value: object, unit: object) -> object:
    """把模型以 JSON 字符串返回的单一有限数值还原为数值类型。"""
    if not isinstance(value, str):
        return value
    normalized = unicodedata.normalize("NFKC", value).strip()
    # 检验报告常把高低提示紧贴在数值后。原始值仍由 raw_value 完整保留；
    # canonical_value 只剥离这个不改变数值的末尾标记，避免被误判为文本事实。
    normalized = re.sub(r"[↑↓]+$", "", normalized).strip()
    if isinstance(unit, str) and not _PLAIN_NUMERIC_SCALAR.fullmatch(normalized):
        annotated = re.fullmatch(
            r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*"
            r"[\(（]([^\)）]+)[\)）]",
            normalized,
        )
        normalized_unit = unicodedata.normalize("NFKC", unit).strip()
        if annotated and normalized_unit and normalized_unit in annotated.group(2):
            normalized = annotated.group(1)
    if not _PLAIN_NUMERIC_SCALAR.fullmatch(normalized):
        return value
    number = float(normalized)
    if not isfinite(number):
        return value
    if number.is_integer() and not any(marker in normalized.lower() for marker in (".", "e")):
        return int(number)
    return number


def _restore_embedded_measurement_unit(value: object, unit: object) -> tuple[object, object]:
    """从紧贴在多分量数值末尾的单位逐字还原独立单位。"""
    if not isinstance(value, str) or unit != "unitless":
        return value, unit
    normalized = unicodedata.normalize("NFKC", value).strip()
    match = re.fullmatch(
        r"([0-9.+\-<>=/()（）\[\]，,;；:：%％*×xX]+)\s*([A-Za-zµμ]+)",
        normalized,
    )
    if not match:
        return value, unit
    return match.group(1), match.group(2)


def _normalize_compact_measurement_scalar(
    value: object, unit: object, asserted_object: object
) -> object:
    """去掉多分量规范值中重复的字段名和单位。"""
    if not isinstance(value, str) or not isinstance(unit, str):
        return value
    candidate = unicodedata.normalize("NFKC", value).strip()
    normalized_unit = unicodedata.normalize("NFKC", unit).strip()
    if isinstance(asserted_object, str):
        normalized_object = unicodedata.normalize("NFKC", asserted_object).strip()
        candidate = re.sub(
            rf"^{re.escape(normalized_object)}\s*[:：]\s*", "", candidate
        )
    candidate = re.sub(
        rf"\s*{re.escape(normalized_unit)}$", "", candidate, flags=re.IGNORECASE
    ).strip()
    compact = "".join(candidate.split())
    if re.search(r"\d", compact) and _COMPACT_MEASUREMENT_SCALAR.fullmatch(compact):
        return compact
    return value


def _normalize_dose_scalar(value: object, unit: object) -> object:
    """将暴露剂量中与独立 unit 完全重复的单一单位去除。"""
    if not isinstance(value, str) or not isinstance(unit, str):
        return value
    normalized_value = unicodedata.normalize("NFKC", value).strip()
    normalized_unit = unicodedata.normalize("NFKC", unit).strip()
    if not normalized_unit:
        return value
    match = re.fullmatch(
        rf"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*{re.escape(normalized_unit)}",
        normalized_value,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else value


def _normalize_evidence_json(value):
    """仅做语义保持的 JSON 实例规范化（不改变候选语义）。"""
    if isinstance(value, list):
        return [_normalize_evidence_json(item) for item in value]
    if not isinstance(value, dict):
        return value
    normalized = {key: _normalize_evidence_json(item) for key, item in value.items() if not (key == "$defs" and item == {})}
    for key in _SET_LIKE_DRAFT_ARRAY_FIELDS:
        items = normalized.get(key)
        if not isinstance(items, list) or not items:
            continue
        if all(isinstance(item, str) for item in items):
            normalized[key] = sorted(set(items))
        elif all(isinstance(item, int) and not isinstance(item, bool) for item in items):
            normalized[key] = sorted(set(items))
    # A model occasionally preserves the source value but omits its normalized
    # duplicate during schema repair. Copying the raw scalar verbatim is
    # lossless; interpreting or coercing it here would not be.
    if (
        normalized.get("polarity") in {"affirmed", "negated"}
        and normalized.get("canonical_value") is None
        and normalized.get("raw_value") is not None
    ):
        normalized["canonical_value"] = normalized["raw_value"]
    # JSON Schema 允许标量联合类型，部分模型会把带单位的单一数值写成字符串。
    # 只转换完整匹配的有限数值；范围、比较符、复合结果和说明文字继续原样进入门禁。
    if "canonical_value" in normalized and normalized.get("value_kind") != "identifier":
        normalized["canonical_value"] = _normalize_numeric_scalar(
            normalized["canonical_value"], normalized.get("unit")
        )
        normalized["canonical_value"], normalized["unit"] = (
            _restore_embedded_measurement_unit(
                normalized["canonical_value"], normalized.get("unit")
            )
        )
        normalized["canonical_value"] = _normalize_compact_measurement_scalar(
            normalized["canonical_value"],
            normalized.get("unit"),
            normalized.get("asserted_object"),
        )
    canonical_value = normalized.get("canonical_value")
    if (
        "fact_type" in normalized
        and isinstance(canonical_value, (int, float))
        and not isinstance(canonical_value, bool)
        and normalized.get("unit") is None
        and isinstance(normalized.get("asserted_object"), str)
        and normalized["asserted_object"].strip().endswith("百分比")
    ):
        normalized["unit"] = "%"
    if (
        "fact_type" in normalized
        and isinstance(canonical_value, str)
        and normalized.get("unit") is not None
        and (
            normalized.get("profile_lane") == ProfileLane.MEDICATION.value
            or re.search(r"\d", canonical_value) is None
        )
    ):
        normalized["unit"] = None
    if "medication_name" in normalized and "dose" in normalized:
        normalized["dose"] = _normalize_dose_scalar(
            normalized["dose"], normalized.get("unit")
        )
    # ``unknown`` already means that the source direction is unresolved.
    # Contradictory value details cannot promote it to an assertion.
    if normalized.get("polarity") == "unknown" and "fact_type" in normalized:
        for key in ("raw_value", "canonical_value", "unit", "assertion_basis"):
            normalized[key] = None
    # 去除单元素逻辑包裹（若模型错误包裹）
    if set(normalized) == {"kind", "operator", "children"} and normalized.get("kind") == "logical" and normalized.get("operator") in {"all", "any"} and isinstance(normalized.get("children"), list) and len(normalized["children"]) == 1:
        return normalized["children"][0]
    # 断言对象机械逐字还原：模型把断言对象“顺口化”（加类别后缀或漏抄虚词）时，
    # 从其已有 assertion_text 中确定性地还原唯一逐字片段；歧义时保持原样，
    # 逐字门禁仍按原合同拒绝。两处对象在草稿中一致时保持一致。
    basis = normalized.get("assertion_basis")
    if isinstance(basis, dict) and isinstance(basis.get("assertion_text"), str):
        original = basis.get("asserted_object")
        if isinstance(original, str):
            repaired = _mechanical_verbatim_repair(original, basis["assertion_text"])
            if repaired is not None:
                basis["asserted_object"] = repaired
                if normalized.get("asserted_object") == original:
                    normalized["asserted_object"] = repaired
    return normalized


def _normalize_locator_aliases(value, available_locator_ids: set[str]):
    """补回模型偶尔省略的系统定位前缀，不猜测其他未知定位。"""
    if isinstance(value, list):
        return [
            _normalize_locator_aliases(item, available_locator_ids) for item in value
        ]
    if not isinstance(value, dict):
        return value
    normalized = {
        key: _normalize_locator_aliases(item, available_locator_ids)
        for key, item in value.items()
    }
    locator_id = normalized.get("locator_id")
    if isinstance(locator_id, str) and locator_id not in available_locator_ids:
        prefixed = f"locator-{locator_id}"
        if prefixed in available_locator_ids:
            normalized["locator_id"] = prefixed
    for key in ("locator_ids", "affected_locator_ids"):
        locator_ids = normalized.get(key)
        if not isinstance(locator_ids, list):
            continue
        normalized[key] = [
            (
                f"locator-{item}"
                if isinstance(item, str)
                and item not in available_locator_ids
                and f"locator-{item}" in available_locator_ids
                else item
            )
            for item in locator_ids
        ]
    return normalized


def _demote_conflicting_duration_status(
    payload: dict,
    *,
    page_numbers: list[int] | None,
) -> dict:
    """保留日期与定位，将模型内部矛盾的持续状态降为未知。"""
    pages = sorted(set(page_numbers or []))
    unresolved = payload.setdefault("unresolved_items", [])
    for field, label in (
        ("event_candidates", "事件"),
        ("exposure_candidates", "用药或治疗"),
    ):
        candidates = payload.get(field)
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            status = candidate.get("duration_status")
            end_range = candidate.get("end_range")
            conflict = (status == "ongoing" and end_range is not None) or (
                status == "ended" and end_range is None
            )
            if not conflict:
                continue
            candidate["duration_status"] = "unknown"
            locator_ids = candidate.get("locator_ids")
            unresolved.append(
                {
                    "code": "duration_status_unclear",
                    "message": f"{label}的持续状态与终止时间不能同时明确",
                    "affected_pages": pages,
                    "affected_locator_ids": (
                        sorted(set(locator_ids))
                        if isinstance(locator_ids, list)
                        and all(isinstance(item, str) for item in locator_ids)
                        else []
                    ),
                    "affected_requirement_ids": [],
                    "gap_type": None,
                    "reason": "同一候选同时给出不相容的持续状态与终止时间；已保留原日期和定位，持续状态按未知处理，需回看原始资料核对",
                    "referenced_file_id": None,
                }
            )
    return payload


def _demote_invalid_date_ranges(
    payload: dict,
    *,
    page_numbers: list[int] | None,
) -> dict:
    """日期边界不能确定时仅降级精度，不从矛盾边界中选值。"""
    pages = sorted(set(page_numbers or []))
    unresolved = payload.setdefault("unresolved_items", [])
    allowed_keys = {"source_text", "precision", "lower_bound", "upper_bound"}
    for field in ("fact_candidates", "event_candidates", "exposure_candidates"):
        candidates = payload.get(field)
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            for range_field in ("date_range", "start_range", "end_range"):
                date_range = candidate.get(range_field)
                if not isinstance(date_range, dict) or not set(date_range) <= allowed_keys:
                    continue
                try:
                    PartialDateRange.model_validate(date_range)
                except ValidationError:
                    source_text = date_range.get("source_text")
                    candidate[range_field] = {
                        "source_text": source_text if isinstance(source_text, str) else None,
                        "precision": "unknown",
                        "lower_bound": None,
                        "upper_bound": None,
                    }
                    locator_ids = candidate.get("locator_ids")
                    unresolved.append(
                        {
                            "code": "date_range_unclear",
                            "message": "日期精度与上下界不一致，无法确定唯一日期范围",
                            "affected_pages": pages,
                            "affected_locator_ids": (
                                sorted(set(locator_ids))
                                if isinstance(locator_ids, list)
                                and all(isinstance(item, str) for item in locator_ids)
                                else []
                            ),
                            "affected_requirement_ids": [],
                            "gap_type": None,
                            "reason": "已保留原始日期文字和定位，日期范围按未知处理，需回看原始资料核对",
                            "referenced_file_id": None,
                        }
                    )
    return payload


def _check_forbidden_top_level(payload: dict) -> None:
    forbidden = {
        "accepted_facts",
        "clinical_facts",
        "facts",
        "gate_results",
        "gate_result",
        "conflict_groups",
        "expectations",
        "evidence_expectations",
        "profile",
        "patient_profile",
        "review_run",
        "action_requests",
        "blocking_level",
        "conclusion",
        "decision",
        "eligibility",
    }
    found = forbidden.intersection(payload.keys())
    if found:
        raise ValueError(f"输出包含禁止字段（候选/unresolved-only）：{sorted(found)}")


def _hydrate_draft_output(
    draft: EvidenceNormalizerDraftOutput,
    *,
    run_id: str,
    call_id: str,
    logical_document_id: str,
    page_numbers: list[int],
    created_at: datetime,
    locator_source_hashes: Mapping[str, str],
) -> EvidenceNormalizerOutput:
    """把模型语义草稿提升为领域候选；系统字段不由模型决定。"""
    invalid_asserted_objects = []
    for candidate in draft.fact_candidates:
        if candidate.assertion_basis is None:
            continue
        asserted_object = " ".join(candidate.assertion_basis.asserted_object.split())
        assertion_text = " ".join(candidate.assertion_basis.assertion_text.split())
        if asserted_object not in assertion_text:
            invalid_asserted_objects.append(candidate.assertion_basis.asserted_object)
    invalid_asserted_objects = list(dict.fromkeys(invalid_asserted_objects))
    if invalid_asserted_objects:
        raise ValueError(
            "以下断言对象必须逐字出现在各自断言原句中："
            + "；".join(invalid_asserted_objects)
        )

    facts: list[ClinicalFactCandidateV2] = []
    for candidate in draft.fact_candidates:
        basis = None
        if candidate.assertion_basis is not None:
            source_text_sha256 = locator_source_hashes.get(
                candidate.assertion_basis.locator_id
            )
            if source_text_sha256 is None:
                raise ValueError(
                    "断言依据定位不在系统冻结的定位摘要中："
                    f"{candidate.assertion_basis.locator_id}"
                )
            basis = AssertionBasis(
                asserted_object=candidate.assertion_basis.asserted_object,
                assertion_text=candidate.assertion_basis.assertion_text,
                locator_id=candidate.assertion_basis.locator_id,
                source_text_sha256=source_text_sha256,
            )
        try:
            fact = ClinicalFactCandidateV2(
                candidate_id=candidate.candidate_ref,
                value_kind=candidate.value_kind,
                source_observation_refs=candidate.source_observation_refs,
                run_id=run_id,
                call_id=call_id,
                fact_type=candidate.fact_type,
                profile_lane=candidate.profile_lane,
                supported_requirement_ids=sorted(
                    set(candidate.supported_requirement_ids)
                ),
                polarity=candidate.polarity,
                asserted_object=candidate.asserted_object,
                raw_value=candidate.raw_value,
                canonical_value=candidate.canonical_value,
                unit=candidate.unit,
                date_range=candidate.date_range,
                record_time=candidate.record_time,
                locator_ids=sorted(set(candidate.locator_ids)),
                candidate_source_semantics=candidate.candidate_source_semantics,
                assertion_basis=basis,
                model_uncertainty=candidate.model_uncertainty,
                created_at=created_at,
            )
        except ValidationError as exc:
            raise ValueError(
                f"事实候选 {candidate.candidate_ref}（{candidate.asserted_object}）"
                f"未通过合同校验：{_validation_error_summary(exc)}"
            ) from exc
        facts.append(fact)
    events = [
        ClinicalEventCandidateV2(
            candidate_id=candidate.candidate_ref,
            run_id=run_id,
            call_id=call_id,
            event_type=candidate.event_type,
            profile_lane=candidate.profile_lane,
            start_range=candidate.start_range,
            end_range=candidate.end_range,
            duration_status=candidate.duration_status,
            record_time=candidate.record_time,
            fact_candidate_ids=sorted(set(candidate.fact_candidate_refs)),
            locator_ids=sorted(set(candidate.locator_ids)),
            candidate_source_semantics=candidate.candidate_source_semantics,
            model_uncertainty=candidate.model_uncertainty,
            created_at=created_at,
        )
        for candidate in draft.event_candidates
    ]
    exposures = [
        MedicationExposureCandidateV2(
            candidate_id=candidate.candidate_ref,
            run_id=run_id,
            call_id=call_id,
            medication_name=candidate.medication_name,
            category=candidate.category,
            indication=candidate.indication,
            dose=candidate.dose,
            unit=candidate.unit,
            frequency=candidate.frequency,
            route=candidate.route,
            start_range=candidate.start_range,
            end_range=candidate.end_range,
            duration_status=candidate.duration_status,
            record_time=candidate.record_time,
            fact_candidate_ids=sorted(set(candidate.fact_candidate_refs)),
            locator_ids=sorted(set(candidate.locator_ids)),
            candidate_source_semantics=candidate.candidate_source_semantics,
            model_uncertainty=candidate.model_uncertainty,
            created_at=created_at,
        )
        for candidate in draft.exposure_candidates
    ]
    return EvidenceNormalizerOutput(
        run_id=run_id,
        call_id=call_id,
        logical_document_id=logical_document_id,
        page_numbers=sorted(set(page_numbers)),
        fact_candidates=facts,
        event_candidates=events,
        exposure_candidates=exposures,
        unresolved_items=draft.unresolved_items,
    )


def parse_evidence_normalizer_output(
    text: str,
    *,
    expected_run_id: str | None = None,
    expected_call_id: str | None = None,
    expected_logical_document_id: str | None = None,
    expected_page_numbers: list[int] | None = None,
    available_locator_ids: set[str] | None = None,
    locator_source_hashes: Mapping[str, str] | None = None,
    created_at: datetime | None = None,
    reference_aliases: NormalizerReferenceAliases | None = None,
) -> EvidenceNormalizerOutput:
    """解析模型原文为 ``EvidenceNormalizerOutput``，保留所有可操作错误。"""
    if not text or not text.strip():
        raise ValueError("模型返回空输出")
    stripped = text.strip()
    # 拒绝 Markdown 包裹
    if stripped.startswith("```"):
        raise ValueError("模型输出不得包含 Markdown 代码块")
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"模型输出不是合法 JSON：{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("模型输出顶层必须是 JSON 对象")
    _check_forbidden_top_level(payload)
    if reference_aliases is not None:
        payload = reference_aliases.transform(payload, expand=True)
    normalized = _normalize_locator_aliases(
        _demote_conflicting_duration_status(
            _demote_invalid_date_ranges(
                _normalize_evidence_json(payload),
                page_numbers=expected_page_numbers,
            ),
            page_numbers=expected_page_numbers,
        ),
        available_locator_ids or set(),
    )
    if "run_id" in normalized:
        # 仅保留给结构化测试注入与旧探针读取；真实传输 schema 不再让模型生成系统身份。
        if expected_page_numbers is not None and "page_numbers" in normalized:
            if sorted(normalized["page_numbers"]) != sorted(expected_page_numbers):
                raise ValueError(f"输出页清单与输入不一致：期望 {sorted(expected_page_numbers)}，实际 {sorted(normalized.get('page_numbers', []))}")
        try:
            output = EvidenceNormalizerOutput.model_validate(normalized)
        except ValidationError as exc:
            raise ValueError(_validation_error_summary(exc)) from exc
    else:
        if (
            expected_run_id is None
            or expected_call_id is None
            or expected_logical_document_id is None
            or expected_page_numbers is None
            or created_at is None
        ):
            raise ValueError("模型语义草稿缺少系统注入所需的调用身份或创建时间")
        try:
            draft = EvidenceNormalizerDraftOutput.model_validate(normalized)
            output = _hydrate_draft_output(
                draft,
                run_id=expected_run_id,
                call_id=expected_call_id,
                logical_document_id=expected_logical_document_id,
                page_numbers=expected_page_numbers,
                created_at=created_at,
                locator_source_hashes=locator_source_hashes or {},
            )
        except ValidationError as exc:
            raise ValueError(_validation_error_summary(exc)) from exc
    # 期望一致性校验（run/call/logical_document）
    if expected_run_id is not None and output.run_id != expected_run_id:
        raise ValueError(f"输出 run_id 与输入不一致：期望 {expected_run_id}，实际 {output.run_id}")
    if expected_call_id is not None and output.call_id != expected_call_id:
        raise ValueError(f"输出 call_id 与输入不一致：期望 {expected_call_id}，实际 {output.call_id}")
    if expected_logical_document_id is not None and output.logical_document_id != expected_logical_document_id:
        raise ValueError(f"输出 logical_document_id 与输入不一致")
    # locator 可用集合校验（若提供）
    if available_locator_ids is not None:
        for cand in output.fact_candidates:
            unknown = set(cand.locator_ids) - available_locator_ids
            if unknown:
                raise ValueError(f"事实候选引用了输入未提供的 locator：{sorted(unknown)}")
            if cand.assertion_basis is not None and cand.assertion_basis.locator_id not in available_locator_ids:
                raise ValueError(f"事实候选断言依据 locator 不在可用集合：{cand.assertion_basis.locator_id}")
        for cand in output.event_candidates:
            unknown = set(cand.locator_ids) - available_locator_ids
            if unknown:
                raise ValueError(f"事件候选引用了输入未提供的 locator：{sorted(unknown)}")
        for cand in output.exposure_candidates:
            unknown = set(cand.locator_ids) - available_locator_ids
            if unknown:
                raise ValueError(f"暴露候选引用了输入未提供的 locator：{sorted(unknown)}")
        for item in output.unresolved_items:
            unknown = set(item.affected_locator_ids) - available_locator_ids
            if unknown:
                raise ValueError(f"未解决项引用了输入未提供的 locator：{sorted(unknown)}")
    # 来源语义白名单（模型侧）
    for cand in output.fact_candidates:
        if cand.candidate_source_semantics not in _ALLOWED_CANDIDATE_SOURCE_SEMANTICS:
            raise ValueError(f"事实候选来源语义不在白名单：{cand.candidate_source_semantics}")
    for cand in output.event_candidates:
        if cand.candidate_source_semantics not in _ALLOWED_CANDIDATE_SOURCE_SEMANTICS:
            raise ValueError(f"事件候选来源语义不在白名单：{cand.candidate_source_semantics}")
    for cand in output.exposure_candidates:
        if cand.candidate_source_semantics not in _ALLOWED_CANDIDATE_SOURCE_SEMANTICS:
            raise ValueError(f"暴露候选来源语义不在白名单：{cand.candidate_source_semantics}")
    return output


def validate_evidence_normalizer_output(
    output: EvidenceNormalizerOutput,
    evidence_input: EvidenceNormalizerInput,
) -> EvidenceNormalizerOutput:
    """让结构化测试传输与真实文本传输经过同一组确定性边界校验。"""
    validated = parse_evidence_normalizer_output(
        json.dumps(output.model_dump(mode="json"), ensure_ascii=False, sort_keys=True),
        expected_run_id=evidence_input.run_id,
        expected_call_id=evidence_input.call_id,
        expected_logical_document_id=evidence_input.logical_document_id,
        expected_page_numbers=evidence_input.page_numbers,
        available_locator_ids=set(evidence_input.available_locator_ids),
    )
    return _validate_normalizer_semantics(validated, evidence_input)


def _validate_normalizer_semantics(
    validated: EvidenceNormalizerOutput,
    evidence_input: EvidenceNormalizerInput,
) -> EvidenceNormalizerOutput:
    """Shared post-parse checks for structured and actual model transports."""
    validated = _filter_supported_requirement_bindings(validated, evidence_input)
    from app.projections.page_review_sources import validate_accepted_candidate_sources
    validate_accepted_candidate_sources(validated, evidence_input.page_review,
                                        locator_inputs=evidence_input.available_locators)
    validated = _align_source_semantics(validated, evidence_input)
    validated = _enforce_exposure_source_fields(validated, evidence_input)
    validate_output_page_closure(validated, evidence_input)
    return validated


def _filter_supported_requirement_bindings(
    output: EvidenceNormalizerOutput,
    evidence_input: EvidenceNormalizerInput,
) -> EvidenceNormalizerOutput:
    """Validate explicit semantic bindings against the frozen requirement set.

    ``fact_type`` is a clinical display category, not a second foreign key. A
    source-backed fact may validly support a requirement whose expected evidence
    type uses a different vocabulary. Unknown requirement identities still fail
    closed; semantic support remains explicit in ``supported_requirement_ids``.
    """
    requirements = {
        requirement.requirement_id: requirement
        for requirement in evidence_input.related_requirements
    }
    filtered = output.model_copy(deep=True)
    for candidate in filtered.fact_candidates:
        for requirement_id in candidate.supported_requirement_ids:
            if requirement_id not in requirements:
                raise ValueError(
                    f"事实候选 {candidate.candidate_id} 绑定了本次冻结输入不存在的资料要求："
                    f"{requirement_id}"
                )
    for unresolved in filtered.unresolved_items:
        unknown = sorted(
            set(unresolved.affected_requirement_ids) - set(requirements)
        )
        if unknown:
            raise ValueError(
                f"未解决项绑定了本次冻结输入不存在的资料要求：{unknown}"
            )
    return filtered


def _align_source_semantics(
    output: EvidenceNormalizerOutput,
    evidence_input: EvidenceNormalizerInput,
) -> EvidenceNormalizerOutput:
    """将模型来源标签约束在冻结文档元数据允许的语义内。

    病历可以直接记录本研究事项，也可以转述既往情况，保留模型在两者之间的
    选择。检验/检查报告、既往原始资料和无法确认来源的资料则由冻结元数据给出
    唯一来源语义，避免正确候选仅因模型选错来源标签而被拒。
    """
    derived = derive_source_strength_from_metadata(
        evidence_input.context.document_type,
        evidence_input.context.source_party,
    )
    source_labels = {
        SourceStrength.CONTEMPORANEOUS_OBJECTIVE: "同期客观结果",
        SourceStrength.HISTORICAL_PRIMARY: "既往原始资料",
        SourceStrength.UNVERIFIABLE: "无法确认来源",
    }
    aligned = output.model_copy(deep=True)
    for candidate in (
        *aligned.fact_candidates,
        *aligned.event_candidates,
        *aligned.exposure_candidates,
    ):
        replacement = source_labels.get(derived)
        if derived in {
            SourceStrength.CURRENT_STUDY_CHART,
            SourceStrength.SCREENING_RECORD_TRANSCRIPTION,
        }:
            replacement = {
                "同期客观结果": "当前研究病历直接记录",
                "既往原始资料": "筛选病历转述",
            }.get(candidate.candidate_source_semantics)
        if replacement is not None:
            candidate.candidate_source_semantics = replacement
    return aligned


def _source_token(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).split()).casefold()


def _cited_source_text_in_page_order(
    evidence_input: EvidenceNormalizerInput,
    locator_ids: Sequence[str],
) -> str:
    """按页内原文顺序重建候选引用片段。

    locator ID 是内容身份，字典序不是临床文本阅读顺序。同页同源的
    多个定位都能在有效文本中唯一找到时，保留它们之间的真实文本；
    不能确定顺序时用不可被空白规范化吞掉的分隔符断开，禁止跨不相关
    定位拼出药名。
    """
    requested = set(locator_ids)
    locator_by_id = {
        locator.locator_id: locator
        for locator in evidence_input.available_locators
        if locator.locator_id in requested
    }
    page_text = {page.page_number: page.effective_text for page in evidence_input.pages}
    groups: dict[tuple[int, object, str], list[tuple[int, int, str]]] = {}
    fallback: list[str] = []
    for locator_id in locator_ids:
        locator = locator_by_id.get(locator_id)
        text = locator.localized_text if locator is not None else None
        if locator is None or not text:
            fallback.append(text or "")
            continue
        source = page_text.get(locator.page_number, "")
        start = source.find(text)
        if start < 0 or source.find(text, start + 1) >= 0:
            fallback.append(text)
            continue
        groups.setdefault(
            (locator.page_number, locator.source_layer, locator.source_text_sha256), []
        ).append((start, start + len(text), source))
    parts: list[str] = []
    for key in sorted(groups, key=lambda item: (item[0], str(item[1]), item[2])):
        spans = groups[key]
        source = spans[0][2]
        parts.append(source[min(span[0] for span in spans) : max(span[1] for span in spans)])
    parts.extend(fallback)
    return "␟".join(parts)


def _is_source_backed_cross_locator_span(
    value: str,
    locator_ids: Sequence[str],
    evidence_input: EvidenceNormalizerInput,
) -> bool:
    """仅承认必须由多个定位连续还原的值，不放行单定位内的残词。"""
    token = _source_token(value)
    cited = [
        locator
        for locator in evidence_input.available_locators
        if locator.locator_id in set(locator_ids) and locator.localized_text
    ]
    return (
        len(cited) >= 2
        and token in _source_token(_cited_source_text_in_page_order(evidence_input, locator_ids))
        and all(token not in _source_token(locator.localized_text or "") for locator in cited)
    )


def _enforce_exposure_source_fields(
    output: EvidenceNormalizerOutput,
    evidence_input: EvidenceNormalizerInput,
) -> EvidenceNormalizerOutput:
    """Keep model-supplied medication fields inside their cited source text.

    Medication identity is essential and fails closed when unsupported. Optional
    descriptions are cleared when they only reflect model knowledge; a later
    terminology layer may add classifications with its own provenance.
    药名残缺项只拦截其明确指向的药物事实及派生事件/暴露；同一定位中
    其他完整药名不受影响。无法确认来源的陈述可保留为待溯源事实，但不能
    发布为实际用药暴露。
    """
    filtered = output.model_copy(deep=True)
    facts_by_id = {item.candidate_id: item for item in filtered.fact_candidates}
    incomplete_fact_ids: set[str] = set()
    incomplete_exposure_ids: set[str] = set()
    resolved_cross_line_items: set[int] = set()
    for item in filtered.unresolved_items:
        if item.code not in {
            "medication_name_incomplete",
            "drug_name_split_across_lines",
        }:
            continue
        affected_locators = set(item.affected_locator_ids)
        detail = _source_token(f"{item.message}\n{item.reason}")
        medication_facts = [
            fact
            for fact in filtered.fact_candidates
            if fact.profile_lane == ProfileLane.MEDICATION
            and affected_locators.intersection(fact.locator_ids)
        ]
        matched_facts = [
            fact
            for fact in medication_facts
            if _source_token(fact.asserted_object) in detail
        ]
        if not matched_facts and len(medication_facts) == 1:
            matched_facts = medication_facts
        unresolved_facts = [
            fact
            for fact in matched_facts
            if not _is_source_backed_cross_locator_span(
                fact.asserted_object, fact.locator_ids, evidence_input
            )
        ]
        incomplete_fact_ids.update(fact.candidate_id for fact in unresolved_facts)

        matched_exposures = []
        for exposure in filtered.exposure_candidates:
            if (
                affected_locators.intersection(exposure.locator_ids)
                and _source_token(exposure.medication_name) in detail
            ):
                matched_exposures.append(exposure)
                if not _is_source_backed_cross_locator_span(
                    exposure.medication_name, exposure.locator_ids, evidence_input
                ):
                    incomplete_exposure_ids.add(exposure.candidate_id)
        if (
            (matched_facts or matched_exposures)
            and not unresolved_facts
            and all(
                _is_source_backed_cross_locator_span(
                    exposure.medication_name, exposure.locator_ids, evidence_input
                )
                for exposure in matched_exposures
            )
        ):
            resolved_cross_line_items.add(id(item))

    facts = [
        fact
        for fact in filtered.fact_candidates
        if fact.candidate_id not in incomplete_fact_ids
    ]
    events = [
        event
        for event in filtered.event_candidates
        if not incomplete_fact_ids.intersection(event.fact_candidate_ids)
    ]
    exposures = []
    optional_fields = ("category", "indication", "dose", "unit", "frequency", "route")
    for candidate in filtered.exposure_candidates:
        if (
            candidate.candidate_id in incomplete_exposure_ids
            or incomplete_fact_ids.intersection(candidate.fact_candidate_ids)
            or candidate.candidate_source_semantics in {
                "无法确认来源",
                "unverifiable_source",
            }
        ):
            continue
        cited_text = _source_token(
            _cited_source_text_in_page_order(evidence_input, candidate.locator_ids)
        )
        if _source_token(candidate.medication_name) not in cited_text:
            source_names = {
                fact.asserted_object
                for fact_id in candidate.fact_candidate_ids
                if (fact := facts_by_id.get(fact_id)) is not None
                and fact.polarity == FactPolarity.AFFIRMED
                and _source_token(fact.asserted_object) in cited_text
            }
            if len(source_names) != 1:
                raise ValueError(
                    f"用药暴露 {candidate.candidate_id} 的药名未逐字出现在所引原文中"
                )
            candidate = candidate.model_copy(
                update={"medication_name": source_names.pop()}
            )
        updates = {
            field: None
            for field in optional_fields
            if (value := getattr(candidate, field)) is not None
            and _source_token(value) not in cited_text
        }
        exposures.append(candidate.model_copy(update=updates))
    return filtered.model_copy(
        update={
            "fact_candidates": facts,
            "event_candidates": events,
            "exposure_candidates": exposures,
            "unresolved_items": [
                item
                for item in filtered.unresolved_items
                if id(item) not in resolved_cross_line_items
            ],
        }
    )


def validate_output_page_closure(
    output: EvidenceNormalizerOutput,
    evidence_input: EvidenceNormalizerInput,
) -> None:
    """每页必须被候选真实引用或被未解决项明确覆盖，禁止泛化空闭合。"""
    locator_pages = {
        locator_id: page.page_number
        for page in evidence_input.pages
        for locator_id in page.locator_ids
    }
    covered_pages: set[int] = set()
    for candidate in (
        list(output.fact_candidates)
        + list(output.event_candidates)
        + list(output.exposure_candidates)
    ):
        covered_pages.update(
            locator_pages[locator_id]
            for locator_id in candidate.locator_ids
            if locator_id in locator_pages
        )
    for item in output.unresolved_items:
        covered_pages.update(item.affected_pages)
        covered_pages.update(
            locator_pages[locator_id]
            for locator_id in item.affected_locator_ids
            if locator_id in locator_pages
        )
    missing = sorted(set(evidence_input.page_numbers) - covered_pages)
    if missing:
        raise ValueError(f"以下页面既无候选证据引用，也无逐页未解决说明：{missing}")


# ---------------------------------------------------------------------------
# Prompt repair
# ---------------------------------------------------------------------------


def _schema_repair_prompt(problem: str, *, include_output_schema: bool = True,
                          verified_scope_prompt: bool = False) -> str:
    schema_suffix = f"输出结构：{_compact_schema()}" if include_output_schema else ""
    repair_contract = _SCHEMA_REPAIR_CONTRACT
    if verified_scope_prompt:
        from app.agents.verified_evidence_prompt import VERIFIED_EVIDENCE_REPAIR_CONTRACT
        repair_contract = VERIFIED_EVIDENCE_REPAIR_CONTRACT
    return (
        "前一输出未能通过严格 JSON Schema 校验。"
        f"具体问题：{problem[:12000]}。"
        "请在同一会话内仅修正 JSON 结构与候选字段。不要输出运行号、调用号、逻辑文档号、"
        "页清单、候选主键、创建时间或源文本哈希；这些字段由系统补全。"
        f"{repair_contract}"
        "不得新增虚构 locator，不得输出发布事实、冲突裁决、Expectation 或入排结论。"
        "重新输出完整 JSON 对象，不要附加说明。"
        + schema_suffix
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class EvidenceNormalizerAttempt(ContractModel):
    """一次有界适配尝试（传输或 schema 修复）。"""

    attempt: int = Field(ge=1)
    session_id: str = Field(min_length=1)
    raw_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome: Literal["parsed", "schema_invalid", "transport_failed"]
    output: EvidenceNormalizerOutput | None = None
    issues: list[str] = Field(default_factory=list)
    error_code: Literal["EMPTY_OUTPUT", "PARTIAL_OUTPUT", "TRANSPORT_FAILED"] | None = None


class EvidenceNormalizerRunResult(ContractModel):
    """有界适配运行结果（不写发布事实/Profile，仅候选/unresolved）。"""

    status: Literal["已解析", "需要核对"]
    session_id: str = Field(min_length=1)
    attempts: list[EvidenceNormalizerAttempt] = Field(min_length=1)
    final_output: EvidenceNormalizerOutput | None = None


class EvidenceNormalizerRunner:
    """有界、同一会话的 Evidence Normalizer 适配运行器。

    传输失败与 schema 校验失败分别计入有界预算；超过预算后停止并保留已解析
    输出或需要核对的最后状态，不自动生成空 Profile。
    """

    def __init__(
        self,
        *,
        max_transport_retries: int = 2,
        max_schema_repairs: int = 2,
    ) -> None:
        if max_transport_retries < 0 or max_schema_repairs < 0:
            raise ValueError("重试上限必须为非负整数")
        self._max_transport_retries = max_transport_retries
        self._max_schema_repairs = max_schema_repairs

    def run(
        self,
        evidence_input: EvidenceNormalizerInput,
        transport: EvidenceNormalizerTransport,
        *,
        prompt_template: str,
        visual_observations: Sequence[SelectiveVisionObservationAttachment] | None = None,
        pending_details_retained: bool = False,
        compact_references: bool = False,
        verified_scope_prompt: bool = False,
    ) -> EvidenceNormalizerRunResult:
        # 传输层若已用 JSON Schema 受限解码强制输出结构（如 omlx json_schema
        # response_format），提示内不再重复内嵌同一份 Schema；其余传输保持
        # Schema 内嵌，输出结构约束不变。
        include_output_schema = not bool(
            getattr(transport, "enforces_output_json_schema", False)
        )
        attempts: list[EvidenceNormalizerAttempt] = []
        reference_aliases = (NormalizerReferenceAliases.from_payload(_model_input_payload(
            evidence_input, pending_details_retained=pending_details_retained))
            if compact_references else None)
        prompt = build_evidence_normalizer_prompt(
            evidence_input,
            prompt_template=prompt_template,
            visual_observations=visual_observations,
            include_output_schema=include_output_schema,
            pending_details_retained=pending_details_retained,
            reference_aliases=reference_aliases,
            verified_scope_prompt=verified_scope_prompt,
        )
        available = set(evidence_input.available_locator_ids)
        locator_source_hashes = {
            item.locator_id: item.source_text_sha256
            for item in evidence_input.available_locators
        }
        session_id: str | None = None
        raw_text: str | None = None

        # 初始传输（带重试）
        transport_failures = 0
        while True:
            try:
                if session_id is None:
                    response = transport.start(prompt=prompt)
                else:
                    # 若已有 session，继续使用 repair 逻辑（初始阶段不应走到此处）
                    response = transport.continue_session(session_id=session_id, prompt=prompt)
                session_id = response.session_id
                raw_text = response.text
                break
            except Exception as exc:  # noqa: BLE001
                # 记录一次传输失败尝试
                attempt_id = len(attempts) + 1
                sid = session_id or f"transport-failed-{attempt_id}"
                raw_sha = _sha256(str(exc))
                attempts.append(
                    EvidenceNormalizerAttempt(
                        attempt=attempt_id,
                        session_id=sid,
                        raw_output_sha256=raw_sha,
                        outcome="transport_failed",
                        output=None,
                        issues=[str(exc)[:2000]],
                        error_code="TRANSPORT_FAILED",
                    )
                )
                transport_failures += 1
                if transport_failures > self._max_transport_retries:
                    return EvidenceNormalizerRunResult(
                        status="需要核对",
                        session_id=sid,
                        attempts=attempts,
                        final_output=None,
                    )
                # 若已有 session，保留会话；否则重试 start
                continue

        assert session_id is not None and raw_text is not None

        # 尝试解析与 schema 修复循环
        schema_repairs = 0
        while True:
            attempt_id = len(attempts) + 1
            raw_sha = _sha256(raw_text or "")
            try:
                output = parse_evidence_normalizer_output(
                    raw_text or "",
                    expected_run_id=evidence_input.run_id,
                    expected_call_id=evidence_input.call_id,
                    expected_logical_document_id=evidence_input.logical_document_id,
                    expected_page_numbers=evidence_input.page_numbers,
                    available_locator_ids=available,
                    locator_source_hashes=locator_source_hashes,
                    created_at=evidence_input.created_at,
                    reference_aliases=reference_aliases,
                )
                if not (
                    output.fact_candidates
                    or output.event_candidates
                    or output.exposure_candidates
                    or output.unresolved_items
                ):
                    raise EvidenceNormalizerEmptyOutputError(
                        "模型未返回候选，也未逐页说明无可提取内容。"
                    )
                output = _validate_normalizer_semantics(output, evidence_input)
                attempts.append(
                    EvidenceNormalizerAttempt(
                        attempt=attempt_id,
                        session_id=session_id,
                        raw_output_sha256=raw_sha,
                        outcome="parsed",
                        output=output,
                        issues=[],
                        error_code=None,
                    )
                )
                return EvidenceNormalizerRunResult(
                    status="已解析",
                    session_id=session_id,
                    attempts=attempts,
                    final_output=output,
                )
            except Exception as exc:  # noqa: BLE001
                attempts.append(
                    EvidenceNormalizerAttempt(
                        attempt=attempt_id,
                        session_id=session_id,
                        raw_output_sha256=raw_sha,
                        outcome="schema_invalid",
                        output=None,
                        issues=[str(exc)[:2000]],
                        error_code=(
                            "EMPTY_OUTPUT"
                            if isinstance(exc, EvidenceNormalizerEmptyOutputError)
                            else "PARTIAL_OUTPUT"
                        ),
                    )
                )
                if schema_repairs >= self._max_schema_repairs:
                    return EvidenceNormalizerRunResult(
                        status="需要核对",
                        session_id=session_id,
                        attempts=attempts,
                        final_output=None,
                    )
                schema_repairs += 1
                repair_prompt = _schema_repair_prompt(
                    str(exc), include_output_schema=include_output_schema,
                    verified_scope_prompt=verified_scope_prompt,
                )
                try:
                    response = transport.continue_session(session_id=session_id, prompt=repair_prompt)
                    session_id = response.session_id
                    raw_text = response.text
                except Exception as exc2:  # noqa: BLE001
                    attempt_id2 = len(attempts) + 1
                    attempts.append(
                        EvidenceNormalizerAttempt(
                            attempt=attempt_id2,
                            session_id=session_id,
                            raw_output_sha256=_sha256(str(exc2)),
                            outcome="transport_failed",
                            issues=[str(exc2)[:2000]],
                            error_code="TRANSPORT_FAILED",
                        )
                    )
                    return EvidenceNormalizerRunResult(
                        status="需要核对",
                        session_id=session_id,
                        attempts=attempts,
                        final_output=None,
                    )
