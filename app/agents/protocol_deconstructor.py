"""Bounded, same-session adapter for the protocol deconstruction Agent."""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal, Protocol

from pydantic import Field, ValidationError
from app.agents.protocol_generation_schema import predicate_generation_schema
from app.agents.protocol_source_scope import constrain_source_schema, source_references

from app.domain.contracts.agent_io import (
    EvidenceRequirementDraft,
    ParentRuleCatalogMapping,
    ProtocolDeconstructionDraft,
    ProtocolDeconstructionInput,
    ProtocolMetadataDraft,
    ProtocolSemanticDeconstructionCandidate,
    ProtocolSemanticRuleRepair,
    SemanticEvidenceRequirement,
    SemanticRule,
    SemanticRuleComponent,
    ProcedureCatalogMapping,
    RuleComponentDraft,
)
from app.domain.contracts.agents import PromptVersion
from app.domain.contracts.common import VersionedModel
from app.domain.contracts.enums import AgentNode, ReviewStage, RuleKind
from app.domain.contracts.normalization import CoverageSummary, UnresolvedItem
from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
from app.domain.contracts.protocol_metadata import InterpretationConflict
from app.domain.contracts.rules import (
    EvidenceRequirement,
    Rule,
    RuleComponent,
    WorkflowStage,
    iter_atomic_predicates,
)
from app.protocols.deconstruction_gate import (
    ProtocolDeconstructionGate,
    ProtocolDeconstructionGateResult,
    ProtocolGateIssue,
)
from app.protocols.adaptive_batch_budget import estimate_text_tokens
from app.protocols.parent_rule_semantic_segmentation import (
    ParentRuleSegment,
    ParentSegmentationThresholds,
    clamp_parent_segment_concurrency,
    merge_parent_rule_segments,
    plan_parent_rule_segments,
    validate_segment_source_closure,
)


logger = logging.getLogger(__name__)


# Minimal quote glyph equivalence: curved ↔ straight single/double quotes only.
# Only these typographic variants are normalized; all other characters
# (words, digits, units, comparators, general punctuation, whitespace) remain strict.
_QUOTE_TRANSLATION = str.maketrans({
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
})

def _quote_normalize(text: str) -> str:
    """Normalize only quote glyphs; preserve all other characters."""
    return text.translate(_QUOTE_TRANSLATION)

class ProtocolAgentResponse(VersionedModel):
    session_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class ProtocolAgentCallError(RuntimeError):
    """Transport failure that retains the logical session for audit recovery."""

    def __init__(
        self,
        session_id: str,
        message: str,
        *,
        error_code: str = "SEMANTIC_CALL_FAILED",
    ):
        super().__init__(message)
        self.session_id = session_id
        self.error_code = error_code


class ProtocolParentSegmentError(RuntimeError):
    """Classified failure for one deterministic parent-rule segment."""

    def __init__(self, segment_id: str, error_code: str, message: str):
        super().__init__(f"{segment_id} [{error_code}] {message}")
        self.segment_id = segment_id
        self.error_code = error_code


ProtocolOutputKind = Literal["semantic_candidate", "semantic_rule_repair"]


class ProtocolWireError(ValueError):
    """Stable, machine-readable rejection for the current wire contract."""

    def __init__(self, code: str, message: str):
        self.code = code
        # ``error_code`` is intentionally an alias for callers that use the
        # persisted gate vocabulary rather than the exception's short name.
        self.error_code = code
        self.reason_code = code
        super().__init__(f"{code}: {message}")


# These are operational protection limits for one provider response.  They
# are deliberately kept outside the formal RuleExpression contract and are
# provisional until representative cross-study corpora calibrate them.
DNF_WIRE_MAX_GROUPS = 64
DNF_WIRE_MAX_ATOMS_PER_GROUP = 64
DNF_WIRE_MAX_ATOMS_PER_EXPRESSION = 512
DNF_WIRE_MAX_COMPONENTS_PER_RULE = 32
DNF_WIRE_MAX_REQUIREMENTS_PER_COMPONENT = 64

# 当前生产 wire 合同版本。字段契约或解析口径变化时提升：旧版本响应不能再被
# 当作当前生产方法读取（历史草稿仍按各自保存的内容原样读取）。
DNF_WIRE_VERSION = "dnf-v18"

# Compact semantic batches are sized from the actual prompt, not from protocol
# names or clinical content. Oversized multi-block parents may use the separate
# conservative planner below; ambiguous or single-block parents stay whole.
SEMANTIC_BATCH_MAX_INPUT_TOKENS = 16_000

DNF_WIRE_ERROR_CODES = {
    "unknown_field": "DNF_WIRE_UNKNOWN_FIELD",
    "legacy_graph_field": "DNF_WIRE_LEGACY_GRAPH_FIELD",
    "empty_group": "DNF_WIRE_EMPTY_GROUP",
    "duplicate_atom": "DNF_WIRE_DUPLICATE_ATOM",
    "duplicate_group": "DNF_WIRE_DUPLICATE_GROUP",
    "complexity_limit": "DNF_WIRE_COMPLEXITY_LIMIT",
    "missing_unit": "DNF_WIRE_MISSING_UNIT",
    "shape_mismatch": "DNF_WIRE_SHAPE_MISMATCH",
    "categorical_unit": "DNF_WIRE_CATEGORICAL_UNIT",
    "missing_semantic_proposition": "DNF_WIRE_MISSING_SEMANTIC_PROPOSITION",
    "proposition_shape": "DNF_WIRE_PROPOSITION_SHAPE",
}


_LEGACY_GRAPH_FIELDS = frozenset(
    {
        "node_id",
        "children",
        "root",
        "root_node_id",
        "exception_root",
        "exception_root_node_id",
        "nodes",
        "logical_nodes",
        "predicate_nodes",
        "edges",
        "edge_ids",
        "references",
        "predicate_id",
        "predicate",
        "operator",
        "existence_predicate_nodes",
        "scalar_predicate_nodes",
        "set_predicate_nodes",
        "not_logical_nodes",
        "all_any_logical_nodes",
    }
)


def _raise_wire_error(code: str, message: str) -> None:
    raise ProtocolWireError(code, message)


def _reject_legacy_graph_fields(value: Any, *, context: str) -> None:
    if not isinstance(value, Mapping):
        return
    found = sorted(set(value) & _LEGACY_GRAPH_FIELDS)
    if found:
        _raise_wire_error(
            DNF_WIRE_ERROR_CODES["legacy_graph_field"],
            f"{context} 不得包含旧图字段（未知字段）：{found}",
        )


class ProtocolAgentTransport(Protocol):
    def start(
        self,
        *,
        prompt: str,
        output_kind: ProtocolOutputKind = "semantic_candidate",
    ) -> ProtocolAgentResponse: ...

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
        output_kind: ProtocolOutputKind = "semantic_candidate",
    ) -> ProtocolAgentResponse: ...


class ProtocolSemanticBatchCache(Protocol):
    """Optional validated-batch cache owned by one durable deconstruction job."""

    def load(self, cache_key: str) -> str | None: ...

    def store(
        self,
        cache_key: str,
        response_text: str,
        *,
        cache_contract: str = "protocol-semantic-batch/v1",
    ) -> None: ...


class ProtocolDeconstructionAttempt(VersionedModel):
    # 实际上限由 ProtocolDeconstructorRunner 的结构修复和按冻结
    # 父规则数量计算的语义修复预算决定。运行记录不再复制一个
    # 会随预算演进而失效的静态上限。
    attempt: int = Field(ge=1)
    session_id: str = Field(min_length=1)
    raw_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome: Literal["通过完整性检查", "需要定向修正", "输出格式无效", "会话异常"]
    draft_id: str | None = None
    issues: list[ProtocolGateIssue] = Field(default_factory=list)


class ProtocolDeconstructionRunResult(VersionedModel):
    status: Literal["可以进入审阅", "需要核对"]
    same_session_id: str = Field(min_length=1)
    attempts: list[ProtocolDeconstructionAttempt] = Field(min_length=1)
    final_draft: ProtocolDeconstructionDraft | None = None
    final_gate_result: ProtocolDeconstructionGateResult | None = None


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_SYSTEM_CONTRACT = (
    "每项资料要求必须显式填写allows_screening_record_transcription和"
    "requires_contemporaneous_objective_source，不省略、不依赖默认值；"
    "按方案说明可接受的资料来源。无法确认来源政策时保留未解决项，不猜测。"
    "required_source_types只填写方案明确要求的资料类型，不把常用核对方式升级为必备文件；"
    "方案未限定文件类型时该列表为空，不能自行要求某种证件或证明。"
    "每个原子条件须用observation_policy说明观察范围、single/any/all/unresolved及逐字来源。"
    "只有方案明确以最近或最早一次结果为准时，single下提供selection的criterion=latest/earliest、"
    "ordering_attribute=date_range；不默认取最新、不挑有利值。条件性复查的触发、时限或替代关系"
    "不能由该排序表示时用unresolved保留完整原文，不以复查次数证明许可。"
    "观察政策来源须属于本组件来源，其摘录须同时保留在该原子source_locator中。"
    "selection还须明确window_order：within_window表示先限定时间范围再取一次，"
    "before_window_check表示先按先后选择再核时间有效性，not_applicable仅用于无时间限制，"
    "无法根据方案明确区分时为unresolved；不得默认退回采用更旧的有效记录。该顺序须引用方案依据。"
    "你正在解构一份已确认期别的研究方案。只处理本次输入中的研究期别；"
    "不要解释或比较另一研究期别。官方父规则目录和基线及以前必做项目录均已冻结，"
    "不得增加、删除、合并或调换成员。复杂条款可拆成子组件，但父规则官方编号和数量"
    "必须保持不变。必须保留原文中的且/或/例外、研究者复合判断、指标、阈值和单位。"
    "父条款中每个实质性要求都必须进入原子条件：病史时长、疾病状态、"
    "沟通与依从能力、时间窗、数值阈值和研究者判断都不得因为已引用部分原文而省略；"
    "随机/基线/筛选时间锚点和每一个访视实例。每个 RuleComponent 都会独立接受审核："
    "每个 RuleComponent 必须是一个完整、可独立裁决的条件单元，不是把同一官方条件按短句或"
    "单个原子条件任意拆开的容器；只有原文分支本身就是完整独立触发条件时才拆成多个组件。"
    "同一个排除触发条件中由‘且/同时’连接的必要条件必须保留在同一组件的 ALL 表达式中，"
    "不能拆成任一条件单独触发；同一原则适用于入组条件和其他规则。由‘或/任一/之一’连接的替代"
    "条件使用 ANY，或仅在每个分支本身就是完整独立触发条件时拆成多个组件。例外必须放入对应组件的 exception_expression，"
    "中文顿号、逗号和普通并列列举只表示原文术语清单，不自动构成 ALL 或 ANY；只有冻结原文"
    "直接出现‘或/任一/之一/任何一项/至少一项’等替代连接语时，才可把列举项拆成多个替代分支。"
    "同一禁止或要求类别中的清单应保留为一个完整谓词及其逐字来源，不得自行补写‘或’。"
    "不能改写成普通触发条件。source_span_ids 必须逐字复制 allowed_source_span_ids 中的完整值，"
    "即来源材料的 source_span_id；source_ref 只是原文位置，不是来源编号，不得用它替代，"
    "也不得省略编号前缀或自行缩写。"
    "你只输出本次响应合同指定的规则字段及其语义组件、资料要求。每个子组件内的"
    "source_span_ids 只填直接支撑该子组件的来源，source_excerpts 中的每一项都必须是"
    "该子组件来源里逐字存在的连续片段；若子组件语义由不连续的上位限定语、并列分支和结尾"
    "共同构成，应按原文顺序填写多个片段，不得把不连续文字拼成方案中不存在的新句子；"
    "若编号子项继承父级引导段中的时间锚点、主语或触发限定语，source_span_ids 必须同时引用"
    "父级引导段和当前子项，source_excerpts 分别保存父级与子项逐字片段，谓词也用 source_clauses"
    "分别绑定这些片段；不得只引用子项后再把父级文字补写进摘录。"
    "括号内的除外、除非或例外只作用于括号紧邻的触发分支，不得复制到括号之后由‘或’"
    "连接的兄弟分支。开放列举中的局部例外也不得豁免同时存在的其他触发情况；若保留单一"
    "宽泛触发谓词，组件级 exception_expression 必须明确表示该例外是唯一相关情况，否则"
    "应拆成不会互相豁免的独立触发组件。若原文以‘N天/周/月/年内’直接限定既往事件，但未点名筛选、随机、"
    "基线、知情同意或首次给药等回溯锚点，不得自行猜测或省略时间范围，应放入 "
    "unresolved_items 等待确认。若‘N年内发生N次’本身就是触发条件，应在数值谓词中保留次数"
    "并用 occurrence_window 保存频率周期；若它是较宽条件括号内某一子类的定义或示例，"
    "occurrence_window.minimum_count 与 duration 只能附着于该子类的谓词，不能附着于"
    "上位宽泛条件。保留上位条件原有范围及全部示例，不能把示例的频次变成上位条件的必要条件。不得把"
    "频率定义一律当成回溯锚点不明。若原文以‘N周≥N天’或‘每周至少N天’定义发生天数，"
    "数值谓词保留天数阈值和‘天/日’单位，并用 occurrence_window.duration 保留观察周期。"
    "每个 occurrence_window 还须填写 scope（occurrence-scope/v4）：kind 区分 anchored_lookback"
    "（明确日期前的一段期间）、calendar_period（明确日历期间）、anchored_period（明确日期起算的期间）、"
    "any_consecutive（连续滑动期间）及 unresolved；quantifier 按原文区分 single、every、any 或 unresolved。"
    "原文明说回溯时长但未命名日期时用unanchored_lookback、quantifier=single、anchor_type=null；"
    "应用时按已批准的当前筛选/基线节点政策分别回溯，不把该政策写成方案命名锚点。"
    "只有 anchored_lookback/anchored_period 填 anchor_type，其他类型填 null。不得把‘每月’机械等同"
    "日历月，也不得把‘任何连续期间’固定到筛选日；原文不能确定时保留 unresolved 和具体 unresolved_reason。"
    "scope.source_excerpts 须是本条件 source_clause/source_clauses 内的逐字依据；已明确时 unresolved_reason 为 null。"
    "scope.start_inclusive/end_inclusive分别保留统计期间起止当天是否计入，按原文填写true/false；"
    "未说明且不能从方案定义确定时填null，不把所有期间默认成闭区间。"
    "多个期间须另填occurrence_window.horizon：explicit_dates为明示起止日期，anchor_span为明示的"
    "两个节点，relative_window为原文明确的相对统计范围；明确不限期间才用unbounded，不能确定用"
    "unresolved并说明原因。所有依据须属于本条件原文，不从外层时间筛选自动复制统计范围。"
    "single时horizon为null。多个期间的scope.boundary_periods按原文为full_only/include_partial/"
    "unresolved；任一和每一均须核对首尾不完整周期，不按比例折算阈值。日历周起始星期明确时填"
    "calendar_week_start，否则null；其他周期为null。duration保留周期长度，不另造日历单位。"
    "每30天不等于任意连续30天，周期对齐未明不得擅改为滑动窗。"
    "连续或锚定期间另以scope.duration_basis区分calendar_span（连续日历天组成完整周期，"
    "如4周覆盖28个日历日，两端均计入）与boundary_offset（原文从边界日期偏移时长，再按原文"
    "开闭界限决定包含日期）；不能确定用unresolved，其他期间填null。不得靠强制半开边界修补"
    "连续天数，也不能把4周日历周期算成29天。"
    "计数期间与事实筛选的外层时间范围不可互相替代；频次与复查或观察选择的先后关系尚无结构表达时，"
    "保留原文并列入 unresolved_items，不得擅选优先级。"
    "频次定义只绑定其直接限定的事件或示例分支，不得套到同一父条款的其他兄弟病史。"
    "开放列举的上位类别必须保留独立判断路径，列举的子类不能取代上位类别。"
    "若输出使用DNF，上位条件应有自己的group，不与示例的限制合取；属于充分触发条件的"
    "子类可另有完整group，频次只在对应子类group内计算，不要求其他上位情形满足该频次。"
    "‘计划在治疗期间或研究完成后"
    "N周内’等未来计划应拆分并列分支；治疗期间或研究期间的分支分别用 prospective_period "
    "保存 treatment_period 或 study_period；研究完成后或末次给药后的分支分别用 "
    "prospective_window 保存 study_completion_date、last_dose_date 或 "
    "study_drug_administration_date 及原文时长，其中原文未指明首次或末次、"
    "仅写‘研究药物给药后’时才用 study_drug_administration_date，不得误写成"
    "回溯锚点待确认。"
    "不得把同一父规则的全部来源不加区分地套给每个子组件。父规则映射、流程必做项目、"
    "审核节点、方案身份、rule_id、parent_rule_id、rule_component_id、display_code、"
    "requirement_id、rule_component_id 绑定、规则类型和研究期别均由系统确定性装配，"
    "不得在语义草稿中重复生成。"
    "每个 value-bearing scalar/set 谓词都必须提供非空 unit；数值谓词的 source_term 必须逐字复制"
    "当前分支原文中的指标名称，并与 subject/attribute 绑定同一被测对象，"
    "不得用‘岁’、‘月’、‘ULN’等单位或阈值代替指标名，unit 保留原文单位；"
    "非测量或分类值显式使用 unitless；不携带 value 的 exists 谓词可以省略 unit。"
    "set_atoms.values 中每个值必须是原文中可独立核对的完整分类词项，"
    "不得把一个词拆成单字数组；只有原文明示枚举单字类别时才可保留单字值。"
    "不得输出由完整词项截断而来的单字分类值；应逐字保留原文中的完整行为、能力、"
    "疾病和状态名称。‘性别不限’、‘男女不限’等非限制性人群描述不是入组限制，"
    "不得虚构为男/女分类原子或性别 exists 原子，也不得为其生成资料要求。"
    "一个原子已完整表达条件时，"
    "不要再添加只为重复同一语义的 exists 或截断分类原子。"
    "只有原文否定词直接统辖当前谓词以 source_term/attribute 命名或以 values 逐字列出的"
    "对象时，才可使用 negated 或 ne/not_in；‘阴性’、‘不良事件’、‘非特异性’等结果词是"
    "原文分类内容，不得据此反转整个条件。"
    "若多个阈值共用前置指标名称，每个阈值谓词的 source_clauses 都必须包含一个带该指标名称的"
    "逐字片段和其自身阈值片段，使该阈值仍能独立核对；"
    "非数值谓词省略 source_term，不要用它重复整个原文子句。"
    "每个原子谓词必须用 source_clause 逐字复制直接支撑该谓词的最小连续原文子句；"
    "若语义由不连续的上位限定语、并列分支和结尾共同构成，改用 source_clauses 依原文顺序"
    "列出多个逐字片段，不得把不连续文字拼成方案中不存在的新句子；source_clause 与"
    "source_clauses 只能使用一种。"
    "评分、分级等无量纲数值显式填 unitless。time_constraint 必须绑定其限定的原子条件，"
    "按当前输出Schema规定的位置填写，不得只写在标题、原文摘录或资料要求中；"
    "筛选时、基线时等审核节点用资料要求的 due_stage "
    "表达。同一条件在筛选和基线都要核对时，只保留一个原子条件，并分别建立 due_stage 为"
    "screening 和 baseline 的资料要求；不得为表示审核阶段而复制原子条件。time_constraint "
    "主要用于‘随机前/基线前/筛选前/首次给药前’等相对日期窗；首次给药前必须使用"
    "first_dose_date，不能用笼统的 event_date。只能依据该谓词的逐字原文片段设置时间锚点和"
    "时间窗；当父级引导语或并列分支共享的一处时间限定语（如统一的‘随机前N周内’）确实统辖"
    "当前谓词时，应保留对应 time_constraint，并把共享限定语片段与当前分支自身文字分别逐字"
    "填入 source_clauses；仅出现在兄弟分支、不统辖当前谓词的‘随机前’不得套入，也不得为"
    "‘研究期间计划/需要’凭空添加天数或日期锚点。时间窗必须使用 upper_bound/lower_bound 并保留原文的 day/week/month/year"
    "单位，不得把周、月、年换算成 *_days；‘前N周/月内’不要额外输出原文未写的零日下界。"
    "exception_expression 只能作为子组件字段，不得放入 expression 内；逻辑操作符只用 all/any/not。"
    "资料要求的 due_stage 必须依据当前条款逐字可见的审核时点或冻结流程确定，不得为了"
    "‘再次确认’而把每个条件惯性复制到筛选、导入和基线；原文只要求一个节点时只建立一个"
    "资料要求。只读required_procedure_catalog提供方案既有流程上下文，不要求重新生成其中的项目；"
    "其来源不自动成为本条条件的来源，不得加入组件source_span_ids或扩展本批允许来源。"
    "若某阶段没有必做项目录条目但条款明确写有该阶段，仍保留该 due_stage，系统会"
    "确定性建立审核节点。若回溯条件以 baseline_date、randomization_date、first_dose_date "
    "或 study_drug_administration_date 为锚点，且方向为 before 或 on，必须至少建立一项 "
    "due_stage=baseline 的资料要求，用于基线、随机或首次给药前的最终复核；可以同时建立 "
    "screening 资料要求用于提前关注，但筛选期核对不能替代基线最终复核。"
    "包含‘随机前N时间内或计划在研究期间’的并列条款必须拆成各自完整"
    "分支：回溯分支使用 time_constraint，未来计划分支使用 prospective_period。"
    "资料要求可用可选字段 predicate_refs 声明它用于核实本组件哪些原子条件：role 为 trigger、exception 或 repeat_trigger；前两者对应 expression/exception_expression，repeat_trigger 必须同时给出旁置条件的 condition_id；group_index 与 atom_index 均为所引用表达式数组中的零基序位；同一 group 内 atom 顺序为 existence_atoms、scalar_atoms、set_atoms 依次排列。有明确原文依据时填写且不得重复或跨组件引用；没有把握时省略该字段，系统保留未归属，不得按 fact_type 或“组件内只有一条资料要求”猜测归属。一项资料可引用多个原子。流程必做项目资料要求不使用该字段。资料要求 description 只描述需要核对的资料或需要完成的评估，不得预设审核结果；"
    "不要写‘确认不存在’‘确认无异常’‘确认符合’‘确认不触发’等结论性措辞。"
    "requires_professional_judgment 表示原子条件本身需要专业人员评估，不表示每条资料要求"
    "都需要另一份研究者声明；医生诊断、医生评分记录本身可以承载该专业评估。仅在方案要求"
    "研究者对特定对象作出判断时，才在对应资料要求的 required_source_types 中列出"
    "investigator_assessment，并明确判断对象、适用节点和可接受记录。不得将该来源类型扩散到"
    "同组件内只需客观检查或一般病史的其他资料要求；不得仅因审核需要临床理解而设专业判断标记。"
    "若原文允许使用‘N天/周/月/年内的某项检查结果’，这是资料时效而不是"
    "临床事件回溯：必须为该项检查在原文指定的每个 due_stage 分别建立资料要求，"
    "并用 source_validity_window 保留原文时长和 day/week/month/year 单位；不得把它写成"
    "谓词 time_constraint，也不得用同组件的其他检查资料代替。"
    "半衰期倍数与半衰期时长必须分开：half_life_multiplier保留方案倍数；"
    "half_life_evidence仅在本条件所引正式方案原文明示单一半衰期时长及适用对象时填写，"
    "保留source_span_id、连续source_excerpt、其中逐字applies_to_quote及duration_quote；"
    "不得用记忆、药名、其他人群、范围端点、均值推算或倍数本身代替时长。"
    "没有明确时长时half_life_evidence=null，仍保留半衰期倍数要求，不能删除该时间条件。"
    "JSON 实例不得复制 Schema 的 $defs、properties "
    "等定义字段；ALL/ANY 必须至少"
    "包含两个子表达式，只有一个子表达式时直接输出该子表达式。"
    "输出必须是一个严格符合指定 JSON Schema 的 JSON 对象，不要输出 Markdown、说明、"
    "日志或额外文字。"
)


_FORMAL_DOMAIN_ID_CONTRACT = (
    "正式领域草稿中的每个原子条件都必须有唯一 predicate_id；相同的研究者判断若分别属于"
    "多个子项，也要使用不同而稳定的 predicate_id，不得跨子项复用身份。"
)


_INTERPRETATION_ANCHOR_CONTRACT = (
    "解释澄清只能出现在输入的 interpretation_clarifications 专用区；解释文字不是方案原文，"
    "不得写入任何 source_clause、source_clauses、source_excerpts 或 source_term，"
    "不得冒充方案原文，也不得改变官方编号、阈值、布尔逻辑或时间窗数量。"
    "只有解释澄清区存在、且其 anchor_resolutions 绑定当前父规则时：若某原子条件的原文以"
    "“N天/周/月/年内”限定既往事件且未命名回溯锚点，才可输出一个带 "
    "time_constraint(anchor_type=\"review_node_date\", direction=\"before\", "
    "upper_bound=原文时长与单位) 的正式原子条件；时长和单位必须逐字来自该原子条件的原文"
    "片段，不得改写数量、单位或方向，也不得省略原文窗口。同时必须按该解析声明的每个 "
    "target_review_stages 目标审核节点，在同一组件下分别建立 due_stage 资料要求；它们是"
    "同一核对义务的逐节点实例，不得复制原子条件，也不得把审核节点写成日期约束。"
    "解释澄清区不存在、当前父规则未被解析绑定、或解析声明的 ambiguous_source_refs 与该"
    "原子条件的来源定位不符时：不得使用 review_node_date，必须把未命名回溯锚点保留在 "
    "unresolved_items，也不得改用任何命名锚点猜测。"
)


_COMPACT_WIRE_COMPONENT_CONTRACT = (
    "每个atom须显式提供repeat_scheme，无复查采用要求填null；有要求时保留逐字来源、适用范围、"
    "许可/必做/禁止/研究者决定、触发条件、次数、期限及结果采用方式。来源未说明与尚未核实须区分。"
    "复查关系不是日期排序；不得默认一次、无限次、最后一次或有利结果。明确最后一次才用use_last_repeat，"
    "只说以复查为准而未规定多次采用时用use_single_repeat；无法结构化的限制保留原文并标unresolved。"
    "原文没有规定结果采用方式时result_use填not_specified，存在相关措辞但未能核清才填unresolved。"
    "time_limit分别保留初查/前次检查/方案节点作为参照、方向、数值单位和开闭边界；不把月年换成固定天数。"
    "触发条件不在这里判真，需引用完整原文；研究者许可不由检查日期、签名或次数证明。"
    f"compact wire 只能使用 wire_version='{DNF_WIRE_VERSION}' 的无引用 DNF。每个 expression 都是非空的"
    "alternative group 数组；一个 group 表示其中所有条件必须共同满足，多个 group 表示完整的"
    "替代路径。每个 group 必须同时携带 existence_atoms、scalar_atoms、set_atoms 三个数组；"
    "每个 atom 都必须带 negated。scalar_atoms 只承载数值标量 value（不得填字符串或布尔值），"
    "set_atoms 只承载非空字符串分类值 values 数组（单个分类值也必须使用 values 数组）；"
    "scalar_atoms 的 source_term 必须逐字保留原文指标名并绑定 subject/attribute，"
    "不得用‘岁’、‘月’、‘ULN’等单位或阈值代替指标名。"
    "set_atoms.values 必须保留原文完整分类词，不得输出‘已’、‘能’、‘斑’、"
    "‘稳’等截断字；只有原文明示枚举单字类别时才能使用单字值。"
    "set_atoms 的 unit 必须且只能是 unitless，不能使用‘非’等任意分类单位；scalar_atoms 的 unit"
    "保留原文单位，无量纲数值才使用 unitless；exists atom 可以省略 unit。"
    "同一官方条款中由‘且/同时/并且’连接的必要条件必须放在同一个 group，不能拆成兄弟组件；"
    "由原文‘或/任一/之一’连接的完整分支可成为多个 group；没有明确替代关系时不得凭空"
    "创建替代路径。开放列举的子类不能全部合取为上位类别成立的必要条件；子类定义需要"
    "结构化且原文支持它独立触发时，可保留上位路径并另列完整子类路径。不能确定子类是否"
    "独立触发时，在 unresolved_items 保留该定义及来源，不得删掉限制或收窄上位范围。"
    "顿号、逗号和普通并列列举本身不是独立触发依据，不能仅据标点建立多个 group，"
    "也不得自行补写‘或’。禁止把‘且’条件反向拆成替代路径。exception_expression 是独立的 DNF，"
    "不能把例外混入触发表达式；原文没有例外时必须填 null，绝不能输出三类 atom 都为空的 group。"
    "复查许可的触发条件单列 repeat_trigger_conditions，每项 condition_id 是本组件内的局部引用名，"
    "expression 沿用完整 DNF；由对应 repeat_scheme.trigger_condition_id 引用。不同复查要求的条件"
    "分别保留。明确要求研究者许可时，以permission_condition_id引用同一附加条件数组中的另一完整许可命题，"
    "不得与trigger_condition_id共用编号；investigator_discretion必须提供该引用。许可命题保留决定者、"
    "所针对检查及原文限定时间，核对明确同意或决定复查的书面内容，不能改写成签名或普通病情判断。"
    "许可条件中要求研究者作出同意或决定的原子须requires_professional_judgment=true，"
    "按书面判断的值表示，不改成普通semantic_proposition；同条件内其他数值或事实原子不因此改为专业判断。"
    "其他许可若原文没有额外批准要求，permission_condition_id填null；两类条件的作用范围均依原文，"
    "不得从time_limit.reference推断触发对象。不同复查要求"
    "的每个附加条件另列evidence_roles，按零起算group_index与atom_index逐原子引用（原子顺序为"
    "existence_atoms、scalar_atoms、set_atoms）；evidence_role.role按原文区分initial_observation、"
    "preceding_observation、target_observation、external_context或unresolved，source_excerpts保留支持该取证范围的逐字原文。"
    "研究者许可针对本次复查时使用target_observation，仅用于许可条件；须由原文明确检查对象，"
    "不因许可日期接近而推断适用，不把单次许可扩展到其他复查。初查值、前次复查值与外部用药背景"
    "须分开标明，不把整棵混合条件树套同一范围；"
    "未明使用unresolved，不以本次复查结果证明自身触发。"
    "不能合并成一棵共同触发树，不能混入入排 expression 或 exception_expression；附加条件自身的"
    "repeat_scheme 必须为 null。没有附加条件时填空数组。复查次数明确时 count_scope 按原文区分"
    "每次初查或当前节点；不能明确归属则 unresolved，不默认整个病史范围。合并结果时 result_combine"
    "保留原文的 sum/mean/minimum/maximum/all/any，其他或未明方式填 unresolved；不默认取平均或最佳值。"
    "no_repeat_result_use独立说明未提供复查记录时的原文结果政策：retain_initial（原文明示可采用初查）、"
    "no_result（原文明示须有复查才可采用结果）、unresolved（没有明确规定或无法确定）。"
    "若原文明示触发条件不成立时可采用初查，使用retain_initial_when_trigger_false；"
    "必须已有完整trigger_condition_id，不以缺记录或未核实代替条件不成立。"
    "不能仅因复查为optional或未见记录就推断retain_initial；这一字段不证明复查未发生或资料齐全。"
    "合并结果同时在result_population中明确initial_and_repeats（初查及复查）或repeats_only（仅复查），"
    "其他范围或原文无法明确则unresolved；非合并方式填null，不默认纳入初查或漏掉初查。"
    "复查规格使用repeat-scheme/v4。multi_initial_result仅在原文涉及多组初查的结果采用顺序时填写："
    "per_initial_then_all或per_initial_then_any表示每组先按复查规则采用结果，再要求各组全部或任一满足，"
    "source_excerpts保留对应逐字依据；原文涉及但顺序不明用unresolved，未涉及填null。"
    "不得从observation_policy、记录数量、日期或有利结果推断这一顺序，也不把不同初查的复查混成一组。"
    "只有 atom 自身 source_locator 的逐字片段中，否定词直接统辖该 atom 所指对象时，"
    "才允许使用 negated=true、ne 或 not_in：negated=true 要求‘无/没有/否认/未见/未使用/"
    "未接受/不存在’等否定词与该对象以 source_term/attribute 逐字命名的名称直接相连；"
    "not_in 的每个 values 都必须是紧随‘不属于/不在/不包括/非’等否定词之后的逐字分类值；"
    "ne 只对应原文‘≠/不等于/不是’加逐字比较值。‘阴性’、‘不良事件’、‘非特异性’等结果词"
    "或词内前缀是原文分类内容，不是否定标记；不得从沉默、分类值、相邻句或模型解释推导否定。"
    "不得自行发明单位、时间窗、否定范围或替代路径；只保留原文"
    "明确支持的语义。时间约束、频次窗口和未来计划窗直接作为 atom 字段传递；不要输出正式"
    "表达式包装或系统身份字段。provider 不生成节点引用、根引用或正式 predicate 身份，系统会在后续阶段装配。"
    "每个 atom 都必须显式给出 semantic_proposition：没有命题时填 null，不得省略该字段；"
    "scalar_atoms 和 set_atoms 只能填 null。只有条件本身是非确定性的语义命题、且原文没有"
    "可计算的数值、分类或日期比较时，才填写它的非空文字；不得用它代替本可结构化的阈值、"
    "分类值、时间窗或频次，也不得把已可计算的确定性条件改写成命题。"
    "semantic_proposition 只保留方案原文原方向的含义及其限定条件：不得反转原文语义，"
    "不得补充原文没有的人群、期间、否定或例外限定，也不得把原文的‘且/或’关系改写进该"
    "文字；它不参与数值、日期、频次和单位的计算，这些判断仍分别使用 scalar_atoms、"
    "set_atoms、time_constraint、occurrence_window 和 prospective_* 字段。"
    "semantic_proposition 只用于比较方式为 exists 且不携带 value、unit 的条件；不得与 "
    "requires_professional_judgment 混用（研究者判断仍按其专属字段表达），也不得与 "
    "occurrence_window 混用（频次必须结构化）。原文写的是计划、意愿或将来安排时，如实"
    "保留为对未来安排的陈述，不能写成已经履行、已经发生或已经具备；原文写的是已发生"
    "事实时，也不能改写成计划；未来安排仍须按上文要求用 prospective_period 或 "
    "prospective_window 同时保留原文期间和时长。该字段只声明‘这里有一个需要按方案"
    "来源核实含义的命题’，不表示命题已被核实，也不能用它替代原文未命名的回溯锚点、"
    "观察采用范围待核实或研究者专业判断的既有处理。"
    "资料要求的 predicate_refs 是允许的局部位置引用，不是系统身份：role 指 trigger、exception 或 repeat_trigger。"
    "repeat_trigger 必须同时填写其旁置条件的 condition_id，其他角色不得填写 condition_id；"
    "复查条件的资料归属须独立核实，不得继承原入排条件的来源要求。"
    "group_index 从零计数，atom_index 按该组 existence_atoms、scalar_atoms、set_atoms 合并顺序从零计数。"
    "仅在有来源依据时填写；无法确认归属时省略，不猜配。填写 predicate_refs 时同时明确"
    "allows_screening_record_transcription 和 requires_contemporaneous_objective_source，"
    "不得省略后依赖默认值；来源政策无法确定时保留未解决项，不猜测允许何种来源。"
    f"单个 expression 最多 {DNF_WIRE_MAX_GROUPS} 个 group，每个 group 最多 "
    f"{DNF_WIRE_MAX_ATOMS_PER_GROUP} 个 atom，单个 expression 总计最多 "
    f"{DNF_WIRE_MAX_ATOMS_PER_EXPRESSION} 个 atom；超过即拒绝，不能截断或静默合并。"
)


def protocol_prompt_template_sha256(prompt_template: str) -> str:
    """Hash every behavioral instruction, not only the caller's prefix."""
    return _sha256(
        prompt_template.strip()
        + "\n\n"
        + _SYSTEM_CONTRACT
        + "\n\n"
        + _INTERPRETATION_ANCHOR_CONTRACT
        + "\n\n"
        + _FORMAL_DOMAIN_ID_CONTRACT
        + "\n\n"
        + _COMPACT_WIRE_COMPONENT_CONTRACT
    )


def _semantic_generation_schema(
    model, allowed_source_span_ids: Sequence[str] = ()
) -> dict[str, object]:
    """Require explicit source policy in new output, retaining legacy read defaults."""
    schema = model.model_json_schema()
    requirement = schema["$defs"]["SemanticEvidenceRequirement"]
    for field in (
        "allows_screening_record_transcription",
        "requires_contemporaneous_objective_source",
    ):
        if field not in requirement["required"]:
            requirement["required"].append(field)
        requirement["properties"][field].pop("default", None)
    return constrain_source_schema(schema, allowed_source_span_ids)


def _compact_schema(allowed_source_span_ids: Sequence[str] = ()) -> str:
    schema = _semantic_generation_schema(
        ProtocolSemanticDeconstructionCandidate, allowed_source_span_ids
    )
    return json.dumps(
        schema,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _compact_repair_schema(allowed_source_span_ids: Sequence[str] = ()) -> str:
    return json.dumps(
        _semantic_generation_schema(ProtocolSemanticRuleRepair, allowed_source_span_ids),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _wire_nullable_string() -> dict[str, object]:
    return {"type": ["string", "null"]}


def _wire_time_quantity_schema(*, nullable: bool = True) -> dict[str, object]:
    return {
        "type": ["object", "null"] if nullable else "object",
        "additionalProperties": False,
        "properties": {
            "value": {"type": "integer", "minimum": 1},
            "unit": {
                "type": "string",
                "enum": ["day", "week", "month", "year"],
            },
        },
        "required": ["value", "unit"],
    }


def _wire_time_constraint_schema() -> dict[str, object]:
    return {
        "type": ["object", "null"],
        "additionalProperties": False,
        "properties": {
            "anchor_type": {
                "type": "string",
                "enum": [
                    "icf_date",
                    "screening_date",
                    "baseline_date",
                    "randomization_date",
                    "first_dose_date",
                    "study_drug_administration_date",
                    "last_dose_date",
                    "study_completion_date",
                    "event_date",
                    "review_node_date",
                ],
            },
            "direction": {
                "type": "string",
                "enum": ["before", "after", "on"],
            },
            "lower_bound_days": {"type": ["integer", "null"], "minimum": 0},
            "upper_bound_days": {"type": ["integer", "null"], "minimum": 0},
            "lower_bound": _wire_time_quantity_schema(),
            "upper_bound": _wire_time_quantity_schema(),
            "half_life_multiplier": {
                "type": ["number", "null"],
                "exclusiveMinimum": 0,
            },
            "half_life_evidence": {
                "type": ["object", "null"],
                "additionalProperties": False,
                "properties": {
                    "value": {"type": "string", "pattern": r"^\d+(?:\.\d+)?$"},
                    "unit": {"type": "string", "enum": ["minute", "hour", "day", "week"]},
                    "source_span_id": {"type": "string", "minLength": 1},
                    "source_excerpt": {"type": "string", "minLength": 1},
                    "applies_to_quote": {"type": "string", "minLength": 1},
                    "duration_quote": {"type": "string", "minLength": 1},
                },
                "required": ["value", "unit", "source_span_id", "source_excerpt", "applies_to_quote", "duration_quote"],
            },
            "combined_window_selection": {
                "type": ["string", "null"],
                "enum": ["longer_of_calendar_and_half_life", None],
            },
            "allow_partial_date": {"type": "boolean"},
        },
        "required": [
            "anchor_type",
            "direction",
            "allow_partial_date",
        ],
    }


_WIRE_NUMERIC_STRING_PATTERN = r"^[+-]?[0-9]+(\.[0-9]+)?$"


def _coerce_wire_number(value: Any) -> Any:
    """把 wire 层的数字字符串还原为数值标量；非数字字符串原样返回交由校验拒绝。"""

    if isinstance(value, str):
        text = value.strip()
        if re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?", text):
            if "." in text:
                return float(text)
            return int(text)
    return value


def _make_wire_schema_grammar_safe(schema: dict[str, object]) -> dict[str, object]:
    """就地移除本地语法引擎不支持的 ``type:"number"`` 节点。

    MTPLX（xgrammar 系）在编译 JSON Schema 的 number 类型时生成含
    look-ahead 的正则并被自身拒绝；number 一律改写为无前瞻数字字符串
    模式，解析端负责还原（pydantic 契约模型为 lax 模式，可自动 coerce）。
    """

    def walk(node: object) -> object:
        if isinstance(node, list):
            return [walk(item) for item in node]
        if not isinstance(node, dict):
            return node
        declared = node.get("type")
        if declared == "number":
            return {"type": "string", "pattern": _WIRE_NUMERIC_STRING_PATTERN}
        if isinstance(declared, list) and "number" in declared:
            branches: list[dict[str, object]] = []
            for member in declared:
                if member == "number":
                    branches.append(
                        {"type": "string", "pattern": _WIRE_NUMERIC_STRING_PATTERN}
                    )
                elif member == "null":
                    branches.append({"type": "null"})
                else:
                    branches.append({"type": member})
            return {"anyOf": branches}
        return {
            key: walk(value)
            for key, value in node.items()
            if key not in {"title", "default"}
        }

    walked = walk(schema)
    assert isinstance(walked, dict)
    return walked


def _wire_scalar_value_schema() -> dict[str, object]:
    """The compact scalar shape is reserved for numeric measurements.

    数值以无前瞻数字字符串约束表达：MTPLX/xgrammar 语法引擎在把
    ``type:"number"`` 编译为正则时会生成含 look-ahead 的模式并被自身
    拒绝；字符串数字模式无前瞻且可跨本地语法引擎移植。解析端
    :func:`_coerce_wire_number` 把该形式还原为数值标量。
    """

    return {"type": "string", "pattern": _WIRE_NUMERIC_STRING_PATTERN}


def _wire_categorical_value_schema() -> dict[str, object]:
    """Categorical membership is always an explicit non-empty string label."""

    return {
        "type": "string",
        "minLength": 1,
        "pattern": r"^[\s\S]*\S[\s\S]*$",
        "description": "原文中可独立核对的完整分类词项，不得截成单字",
    }


def _wire_semantic_proposition_schema() -> dict[str, object]:
    """必填可空命题字段：null 表示本条件不含非确定性语义命题。

    该字段只承载需要按方案来源核实含义的命题，不承载数值、分类或日期比较；
    因此 schema 不接受空字符串，也不提供数值类型。
    """

    return {
        "type": ["string", "null"],
        "minLength": 1,
        "pattern": r"^[\s\S]*\S[\s\S]*$",
        "description": (
            "原文非确定性语义命题的显式声明；无命题时必须显式填 null，"
            "scalar_atoms/set_atoms 只能填 null"
        ),
    }


def _wire_source_locator_schema(*, source_limit: int | None = None) -> dict[str, object]:
    """Require one non-empty, mutually exclusive exact source locator."""

    return {
        "type": "object",
        "additionalProperties": False,
        "minProperties": 1,
        "maxProperties": 1,
        "properties": {
            "source_clause": {"type": "string", "minLength": 1},
            "source_clauses": {
                "type": "array",
                "minItems": 1,
                **({"maxItems": source_limit} if source_limit is not None else {}),
                "items": {"type": "string", "minLength": 1},
            },
        },
    }


def _bounded_array(
    items: dict[str, object],
    *,
    minimum: int = 0,
    maximum: int | None = None,
) -> dict[str, object]:
    schema: dict[str, object] = {"type": "array", "items": items}
    if minimum:
        schema["minItems"] = minimum
    if maximum is not None:
        schema["maxItems"] = maximum
    return schema


def _wire_observation_policy_schema():
    from app.domain.contracts.observation_selection import ObservationOrdering, ObservationPolicy
    schema = ObservationPolicy.model_json_schema()
    definitions = schema.pop("$defs", {})
    definitions["ObservationOrdering"] = ObservationOrdering.provider_json_schema()
    selection = schema["properties"]["selection"]
    selection["anyOf"] = [definitions[item["$ref"].rsplit("/", 1)[-1]]
                          if "$ref" in item else item for item in selection["anyOf"]]
    return schema


def _wire_repeat_scheme_schema():
    from app.domain.contracts.repeat_scheme import RepeatScheme
    schema = RepeatScheme.model_json_schema()
    schema["properties"]["version"] = {"type": "string", "const": "repeat-scheme/v4"}
    return {"anyOf": [_inline_required_contract_schema(schema), {"type": "null"}]}


def _wire_occurrence_scope_schema():
    from app.domain.contracts.occurrence_scope import OccurrenceScope
    schema = OccurrenceScope.model_json_schema()
    schema["properties"]["version"] = {"type": "string", "const": "occurrence-scope/v4"}
    return _inline_required_contract_schema(schema)


def _wire_frequency_horizon_schema():
    from app.domain.contracts.rules import FrequencyHorizon
    return {"anyOf": [_inline_required_contract_schema(FrequencyHorizon.model_json_schema()), {"type": "null"}]}


def _inline_required_contract_schema(schema):
    definitions = schema.pop("$defs", {})

    def inline(node):
        if isinstance(node, list):
            return [inline(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            name = node["$ref"].rsplit("/", 1)[-1]
            node = {**definitions[name], **{key: value for key, value in node.items() if key != "$ref"}}
        result = {key: inline(value) for key, value in node.items() if key not in {"title", "default"}}
        if result.get("type") == "object":
            result["required"] = list(result.get("properties", {}))
        return result

    return inline(schema)


def _wire_repeat_evidence_roles_schema():
    from app.domain.contracts.repeat_scheme import RepeatEvidenceRoleReference
    return {"type": "array", "items": _inline_required_contract_schema(
        RepeatEvidenceRoleReference.model_json_schema()
    )}


def _wire_atom_common_properties(
    *,
    unit_schema: dict[str, object],
) -> dict[str, object]:
    return {
        "subject": {"type": "string", "minLength": 1},
        "attribute": {"type": "string", "minLength": 1},
        "source_term": _wire_nullable_string(),
        "source_locator": {"$ref": "#/$defs/wire_source_locator"},
        "unit": unit_schema,
        "applicable_population": _wire_nullable_string(),
        "requires_professional_judgment": {"type": "boolean"},
        "occurrence_window": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "properties": {
                "duration": {
                    **_wire_time_quantity_schema(nullable=False),
                },
                "minimum_count": {
                    "type": ["integer", "null"],
                    "minimum": 1,
                },
                "scope": _wire_occurrence_scope_schema(),
                "horizon": _wire_frequency_horizon_schema(),
            },
            "required": ["duration", "scope", "horizon"],
        },
        "prospective_window": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "properties": {
                "anchor_type": {
                    "type": "string",
                    "enum": [
                        "study_drug_administration_date",
                        "last_dose_date",
                        "study_completion_date",
                    ],
                },
                "upper_bound": _wire_time_quantity_schema(nullable=False),
            },
            "required": ["anchor_type", "upper_bound"],
        },
        "prospective_period": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["treatment_period", "study_period"],
                }
            },
            "required": ["period"],
        },
        "time_constraint": {"$ref": "#/$defs/wire_time_constraint"},
        "semantic_proposition": _wire_semantic_proposition_schema(),
        "repeat_scheme": _wire_repeat_scheme_schema(),
        "observation_policy": _wire_observation_policy_schema(),
        "negated": {"type": "boolean"},
    }


def _wire_atom_schema(
    *,
    shape: Literal["existence", "scalar", "set"],
    unit_schema: dict[str, object],
) -> dict[str, object]:
    properties = _wire_atom_common_properties(unit_schema=unit_schema)
    required = [
        "subject",
        "attribute",
        "source_locator",
        "requires_professional_judgment",
        "negated",
        "observation_policy",
        "semantic_proposition",
        "repeat_scheme",
    ]
    if shape in {"scalar", "set"}:
        properties["comparator"] = {
            "type": "string",
            "enum": (
                ["eq", "ne", "gt", "gte", "lt", "lte"]
                if shape == "scalar"
                else ["in", "not_in"]
            ),
        }
        required.extend(["comparator", "unit"])
        if shape == "scalar":
            properties["source_term"] = {
                "type": "string",
                "minLength": 1,
                "pattern": r"^[\s\S]*\S[\s\S]*$",
                "description": "逐字复制当前数值在原文中的指标名，不得填整句或解释词",
            }
            properties["value"] = _wire_scalar_value_schema()
            required.extend(["source_term", "value"])
        else:
            properties["values"] = {
                "type": "array",
                "minItems": 1,
                "items": _wire_categorical_value_schema(),
            }
            required.append("values")
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def _wire_existence_atom_schema() -> dict[str, object]:
    return _wire_atom_schema(
        shape="existence",
        unit_schema={"type": ["string", "null"], "minLength": 1},
    )


def _wire_value_atom_schema(shape: Literal["scalar", "set"]) -> dict[str, object]:
    return _wire_atom_schema(
        shape=shape,
        unit_schema=(
            {"const": "unitless"}
            if shape == "set"
            else {"type": "string", "minLength": 1, "pattern": r"^[\s\S]*\S[\s\S]*$"}
        ),
    )


def _wire_dnf_group_schema(*, atom_limit: int = DNF_WIRE_MAX_ATOMS_PER_GROUP) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "existence_atoms": {
                "type": "array",
                "maxItems": atom_limit,
                "items": _wire_existence_atom_schema(),
            },
            "scalar_atoms": {
                "type": "array",
                "maxItems": atom_limit,
                "items": _wire_value_atom_schema("scalar"),
            },
            "set_atoms": {
                "type": "array",
                "maxItems": atom_limit,
                "items": _wire_value_atom_schema("set"),
            },
        },
        "required": ["existence_atoms", "scalar_atoms", "set_atoms"],
    }


def _wire_evidence_requirement_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "fact_type": {"type": "string", "minLength": 1},
            "required_source_types": {
                "type": "array",
                "items": {"type": "string"},
            },
            "allows_screening_record_transcription": {"type": "boolean"},
            "requires_contemporaneous_objective_source": {"type": "boolean"},
            "due_stage": {
                "type": "string",
                "enum": ["pre_screening", "screening", "run_in", "baseline"],
            },
            "source_validity_window": _wire_time_quantity_schema(),
            "description": {"type": "string", "minLength": 1},
            # Optional explicit links to atoms in this component's DNF.
            # Omitted legacy outputs stay unattributed; never infer by fact_type.
            "predicate_refs": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "role": {
                            "type": "string",
                            "enum": ["trigger", "exception", "repeat_trigger"],
                        },
                        "condition_id": {"type": "string", "minLength": 1},
                        "evidence_roles": _wire_repeat_evidence_roles_schema(),
                        "group_index": {"type": "integer", "minimum": 0},
                        "atom_index": {"type": "integer", "minimum": 0},
                    },
                    "required": ["role", "group_index", "atom_index"],
                },
            },
        },
        "required": [
            "fact_type",
            "due_stage",
            "description",
            "allows_screening_record_transcription",
            "requires_contemporaneous_objective_source",
        ],
    }


def _wire_component_schema(
    *,
    group_limit: int = DNF_WIRE_MAX_GROUPS,
    requirement_limit: int = DNF_WIRE_MAX_REQUIREMENTS_PER_COMPONENT,
    source_limit: int | None = None,
    allowed_source_span_ids: Sequence[str] = (),
) -> dict[str, object]:
    source_id_schema: dict[str, object] = {"type": "string", "minLength": 1}
    if allowed_source_span_ids:
        source_id_schema = {"type": "string", "enum": list(allowed_source_span_ids)}
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string", "minLength": 1},
            "expression": {
                "type": "array",
                "minItems": 1,
                "maxItems": group_limit,
                "items": {"$ref": "#/$defs/wire_dnf_group"},
            },
            "exception_expression": {
                "type": ["array", "null"],
                "minItems": 1,
                "maxItems": group_limit,
                "items": {"$ref": "#/$defs/wire_dnf_group"},
            },
            "repeat_trigger_conditions": {
                "type": "array",
                "items": {
                    "type": "object", "additionalProperties": False,
                    "properties": {
                        "condition_id": {"type": "string", "minLength": 1},
                        "expression": {
                            "type": "array", "minItems": 1, "maxItems": group_limit,
                            "items": {"$ref": "#/$defs/wire_dnf_group"},
                        },
                    },
                    "required": ["condition_id", "expression", "evidence_roles"],
                },
            },
            "evidence_requirements": {
                "type": "array",
                "minItems": 1,
                "maxItems": requirement_limit,
                "items": _wire_evidence_requirement_schema(),
            },
            "source_span_ids": _bounded_array(
                source_id_schema, minimum=1, maximum=source_limit
            ),
            "source_excerpts": _bounded_array(
                {"type": "string"}, minimum=1, maximum=source_limit
            ),
        },
        "required": [
            "title",
            "expression",
            "repeat_trigger_conditions",
            "evidence_requirements",
            "source_span_ids",
            "source_excerpts",
        ],
    }


def _wire_rule_schema(
    *,
    official_codes: Sequence[str] = (),
    component_limit: int = DNF_WIRE_MAX_COMPONENTS_PER_RULE,
    group_limit: int = DNF_WIRE_MAX_GROUPS,
    atom_limit: int = DNF_WIRE_MAX_ATOMS_PER_GROUP,
    requirement_limit: int = DNF_WIRE_MAX_REQUIREMENTS_PER_COMPONENT,
    source_limit: int | None = None,
    allowed_source_span_ids: Sequence[str] = (),
) -> dict[str, object]:
    official_code_schema: dict[str, object] = {
        "type": "string",
        "pattern": "^(IN|EX)-[0-9]{2}$",
    }
    if official_codes:
        official_code_schema = {"type": "string", "enum": list(official_codes)}
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "official_code": official_code_schema,
            "components": {
                "type": "array",
                "minItems": 1,
                "maxItems": component_limit,
                "items": _wire_component_schema(
                    group_limit=group_limit,
                    requirement_limit=requirement_limit,
                    source_limit=source_limit,
                    allowed_source_span_ids=allowed_source_span_ids,
                ),
            },
        },
        "required": ["official_code", "components"],
    }


def _wire_unresolved_schema(
    *, allowed_source_span_ids: Sequence[str] = (), source_limit: int | None = None
) -> dict[str, object]:
    source_ref_schema: dict[str, object] = {"type": "string"}
    if allowed_source_span_ids:
        source_ref_schema = {"type": "string", "enum": list(allowed_source_span_ids)}
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "code": {"type": "string", "minLength": 1},
            "affected_scope": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "source_refs": _bounded_array(
                source_ref_schema, maximum=source_limit
            ),
        },
        "required": ["code", "affected_scope", "source_refs"],
    }


def _omlx_wire_schema(
    output_kind: ProtocolOutputKind,
    *,
    official_codes: Sequence[str] = (),
    allowed_source_span_ids: Sequence[str] = (),
    component_limit: int = DNF_WIRE_MAX_COMPONENTS_PER_RULE,
    group_limit: int = DNF_WIRE_MAX_GROUPS,
    atom_limit: int = DNF_WIRE_MAX_ATOMS_PER_GROUP,
    requirement_limit: int = DNF_WIRE_MAX_REQUIREMENTS_PER_COMPONENT,
) -> dict[str, object]:
    """Strict, reference-free provider contract; never use it as a domain model."""

    if output_kind == "semantic_candidate":
        rules_key = "proposed_rules"
        required = [
            "wire_version",
            "candidate_id",
            "batch_id",
            "proposed_rules",
            "structural_warnings",
            "unresolved_items",
            "created_by_agent_call_id",
        ]
        properties = {
            "wire_version": {"const": DNF_WIRE_VERSION},
            "candidate_id": {"type": "string", "minLength": 1},
            "batch_id": {"type": "string", "minLength": 1},
            rules_key: {
                "type": "array",
                "minItems": len(official_codes) or 1,
                "maxItems": len(official_codes) or 3,
                "items": _wire_rule_schema(
                    official_codes=official_codes,
                    component_limit=component_limit,
                    group_limit=group_limit,
                    atom_limit=atom_limit,
                    requirement_limit=requirement_limit,
                    source_limit=len(allowed_source_span_ids) or None,
                    allowed_source_span_ids=allowed_source_span_ids,
                ),
            },
            "structural_warnings": {
                "type": "array",
                "maxItems": max(4, len(official_codes) * 4),
                "items": _wire_unresolved_schema(
                    allowed_source_span_ids=allowed_source_span_ids,
                    source_limit=len(allowed_source_span_ids) or None,
                ),
            },
            "unresolved_items": {
                "type": "array",
                "maxItems": max(4, len(official_codes) * 4),
                "items": _wire_unresolved_schema(
                    allowed_source_span_ids=allowed_source_span_ids,
                    source_limit=len(allowed_source_span_ids) or None,
                ),
            },
            "created_by_agent_call_id": {"type": "string", "minLength": 1},
        }
        name = "protocol_semantic_batch_wire_candidate"
    elif output_kind == "semantic_rule_repair":
        rules_key = "replacement_rules"
        required = [
            "wire_version",
            "candidate_id",
            "batch_id",
            "replacement_rules",
            "replacement_structural_warnings",
            "replacement_unresolved_items",
        ]
        properties = {
            "wire_version": {"const": DNF_WIRE_VERSION},
            "candidate_id": {"type": "string", "minLength": 1},
            "batch_id": {"type": "string", "minLength": 1},
            rules_key: {
                "type": "array",
                "minItems": len(official_codes) or 1,
                "maxItems": len(official_codes) or 3,
                "items": _wire_rule_schema(
                    official_codes=official_codes,
                    component_limit=component_limit,
                    group_limit=group_limit,
                    atom_limit=atom_limit,
                    requirement_limit=requirement_limit,
                    source_limit=len(allowed_source_span_ids) or None,
                    allowed_source_span_ids=allowed_source_span_ids,
                ),
            },
            "replacement_structural_warnings": {
                "type": "array",
                "maxItems": max(4, len(official_codes) * 4),
                "items": _wire_unresolved_schema(
                    allowed_source_span_ids=allowed_source_span_ids,
                    source_limit=len(allowed_source_span_ids) or None,
                ),
            },
            "replacement_unresolved_items": {
                "type": "array",
                "maxItems": max(4, len(official_codes) * 4),
                "items": _wire_unresolved_schema(
                    allowed_source_span_ids=allowed_source_span_ids,
                    source_limit=len(allowed_source_span_ids) or None,
                ),
            },
        }
        name = "protocol_semantic_batch_wire_repair"
    else:  # pragma: no cover - guarded by the Literal contract and callers
        raise ValueError(f"未知的方案解构输出类型：{output_kind}")
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }
    schema["$defs"] = {
        "wire_source_locator": _wire_source_locator_schema(
            source_limit=len(allowed_source_span_ids) or None
        ),
        "wire_time_constraint": _wire_time_constraint_schema(),
        "wire_dnf_group": _wire_dnf_group_schema(atom_limit=atom_limit),
    }
    return schema


def protocol_output_response_format(
    output_kind: ProtocolOutputKind,
    *,
    compact: bool = False,
    official_codes: Sequence[str] = (),
    allowed_source_span_ids: Sequence[str] = (),
    component_limit: int = DNF_WIRE_MAX_COMPONENTS_PER_RULE,
    group_limit: int = DNF_WIRE_MAX_GROUPS,
    atom_limit: int = DNF_WIRE_MAX_ATOMS_PER_GROUP,
    requirement_limit: int = DNF_WIRE_MAX_REQUIREMENTS_PER_COMPONENT,
) -> dict[str, object]:
    """Return the strict provider schema for one semantic response kind."""
    if compact:
        schema = _omlx_wire_schema(
            output_kind,
            official_codes=official_codes,
            allowed_source_span_ids=allowed_source_span_ids,
            component_limit=component_limit,
            group_limit=group_limit,
            atom_limit=atom_limit,
            requirement_limit=requirement_limit,
        )
        constrain_source_schema(schema, allowed_source_span_ids)
        schema = _make_wire_schema_grammar_safe(schema)
        schema_name = (
            "protocol_semantic_batch_wire_candidate"
            if output_kind == "semantic_candidate"
            else "protocol_semantic_batch_wire_repair"
        )
        return {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": schema,
            },
        }
    if output_kind == "semantic_candidate":
        schema_name = "protocol_semantic_deconstruction_candidate"
        schema = _semantic_generation_schema(
            ProtocolSemanticDeconstructionCandidate, allowed_source_span_ids
        )
    elif output_kind == "semantic_rule_repair":
        schema_name = "protocol_semantic_rule_repair"
        schema = _semantic_generation_schema(ProtocolSemanticRuleRepair, allowed_source_span_ids)
    else:  # pragma: no cover - guarded by the Literal contract and callers
        raise ValueError(f"未知的方案解构输出类型：{output_kind}")
    # The semantic gate already requires atomic provenance. Enforce its presence
    # during generation without inventing source text or changing stored contracts.
    schema["$defs"]["AtomicPredicate"] = predicate_generation_schema(
        schema["$defs"]["AtomicPredicate"], schema["$defs"]["Comparator"])
    if official_codes:
        rules = schema["properties"][
            "proposed_rules" if output_kind == "semantic_candidate" else "replacement_rules"
        ]
        rules["minItems"] = rules["maxItems"] = len(official_codes)
        schema["$defs"]["SemanticRule"]["properties"]["official_code"]["enum"] = list(official_codes)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema_name,
            "strict": True,
            "schema": schema,
        },
    }


def _repair_batch_id(rule_codes: Sequence[str]) -> str:
    """Return the one stable identity for a targeted parent-rule repair."""

    ordered_codes = tuple(rule_codes)
    if not ordered_codes:
        raise ValueError("局部修订必须至少指定一个官方父规则")
    return "repair:" + ",".join(ordered_codes)


def _batch_source_span_ids(
    source_input: ProtocolDeconstructionInput,
    requested_rule_codes: Sequence[str] | None,
) -> tuple[str, ...]:
    """Return only source spans explicitly owned by the selected parent rules."""

    catalog_items = sorted(
        source_input.parent_rule_catalog.items,
        key=lambda item: item.position,
    )
    selected_codes = (
        {code for code in requested_rule_codes}
        if requested_rule_codes is not None
        else {
            item.official_code
            for item in catalog_items
            if item.official_code is not None
        }
    )
    selected_span_ids = {
        span_id
        for item in catalog_items
        if item.official_code in selected_codes
        for span_id in item.source_span_ids
    }
    # Preserve the frozen input order while refusing globally allowed but
    # procedure-only/ownerless spans.
    return tuple(
        span_id
        for span_id in source_input.allowed_source_span_ids
        if span_id in selected_span_ids
    )


def _interpretation_clarifications(
    source_input: ProtocolDeconstructionInput,
    rule_codes: set[str] | None,
) -> list[dict[str, object]]:
    """解释澄清专用提示区。

    只携带显式锚点解析及其解释摘录，与方案原文区完全分离；解释文字永远
    不进入 source_materials 或任何 source_clause/source_excerpts。当前批
    次未涉及的解析不进入提示，避免诱导跨规则套用。
    """

    entries: list[dict[str, object]] = []
    for source in source_input.interpretation_sources:
        resolutions = [
            resolution
            for resolution in source.anchor_resolutions
            if rule_codes is None
            or set(resolution.affected_rule_refs) & rule_codes
        ]
        if not resolutions:
            continue
        entries.append(
            {
                "interpretation_source_id": source.interpretation_source_id,
                "source_type": source.source_type.value,
                "source_ref": source.source_ref,
                "excerpt": source.excerpt,
                "explanation": source.explanation,
                "anchor_resolutions": [
                    {
                        "resolution_id": resolution.resolution_id,
                        "affected_rule_refs": list(resolution.affected_rule_refs),
                        "ambiguous_source_refs": list(
                            resolution.ambiguous_source_refs
                        ),
                        "target_review_stages": [
                            stage.value for stage in resolution.target_review_stages
                        ],
                        "resolution_mode": resolution.resolution_mode.value,
                    }
                    for resolution in resolutions
                ],
            }
        )
    return entries


def _batch_prompt_payload(
    source_input: ProtocolDeconstructionInput,
    requested_rule_codes: Sequence[str] | None,
    *,
    batch_number: int | None,
    batch_total: int | None,
    candidate_id: str | None,
    batch_id: str | None = None,
    agent_call_id: str | None = None,
    scoped_source_span_ids: Sequence[str] | None = None,
) -> dict[str, object]:
    """Build only the frozen context and source blocks needed by one batch."""

    catalog_items = sorted(
        source_input.parent_rule_catalog.items,
        key=lambda item: item.position,
    )
    selected_codes = (
        {code for code in requested_rule_codes}
        if requested_rule_codes is not None
        else {
            item.official_code
            for item in catalog_items
            if item.official_code is not None
        }
    )
    selected_items = [
        item for item in catalog_items if item.official_code in selected_codes
    ]
    owned_span_ids = _batch_source_span_ids(source_input, requested_rule_codes)
    if scoped_source_span_ids is None:
        selected_span_ids = owned_span_ids
    else:
        scoped = tuple(dict.fromkeys(scoped_source_span_ids))
        if not scoped or not set(scoped) <= set(owned_span_ids):
            raise ValueError("父规则分段来源必须属于当前官方父规则")
        selected_span_ids = tuple(
            span_id for span_id in owned_span_ids if span_id in set(scoped)
        )
    selected_span_id_set = set(selected_span_ids)
    selected_materials = [
        material
        for material in sorted(
            source_input.source_materials,
            key=lambda material: material.block_order,
        )
        if material.source_span_id in selected_span_id_set
    ]
    resolved_batch_id = batch_id or (
        f"{batch_number}/{batch_total}"
        if batch_number is not None and batch_total is not None
        else "all"
    )
    batch_rule_codes = (
        list(requested_rule_codes)
        if requested_rule_codes is not None
        else [item.official_code for item in catalog_items]
    )
    return {
        "project_id": source_input.project_id,
        "protocol_version_id": source_input.protocol_version_id,
        "protocol_file_sha256": source_input.protocol_file_sha256,
        "extraction_snapshot_id": source_input.extraction_snapshot_id,
        "phase_projection_id": source_input.phase_projection_id,
        "selected_phase": source_input.selected_phase.value,
        "batch_id": resolved_batch_id,
        "batch_rule_codes": batch_rule_codes,
        "candidate_id": candidate_id,
        "created_by_agent_call_id": agent_call_id,
        "allowed_source_span_ids": list(selected_span_ids),
        "required_procedure_catalog": [
            item.model_dump(mode="json")
            for item in sorted(
                source_input.required_procedure_catalog.items,
                key=lambda item: item.position,
            )
        ],
        "parent_rule_catalog": [
            item.model_copy(
                update={
                    "source_span_ids": tuple(
                        span_id
                        for span_id in item.source_span_ids
                        if span_id in selected_span_id_set
                    ),
                    "source_excerpts": tuple(
                        excerpt
                        for span_id, excerpt in zip(
                            item.source_span_ids,
                            item.source_excerpts,
                            strict=True,
                        )
                        if span_id in selected_span_id_set
                    )
                    if item.source_excerpts
                    else (),
                }
            ).model_dump(mode="json")
            for item in selected_items
        ],
        "source_materials": [
            material.model_dump(mode="json") for material in selected_materials
        ],
        "interpretation_clarifications": _interpretation_clarifications(
            source_input, set(batch_rule_codes)
        ),
    }


def build_protocol_deconstruction_prompt(
    source_input: ProtocolDeconstructionInput,
    *,
    prompt_template: str,
    requested_rule_codes: Sequence[str] | None = None,
    batch_number: int | None = None,
    batch_total: int | None = None,
    candidate_id: str | None = None,
    batch_id: str | None = None,
    agent_call_id: str | None = None,
    compact: bool = False,
    scoped_source: bool = False,
    scoped_source_span_ids: Sequence[str] | None = None,
) -> str:
    """Build one auditable prompt from frozen input, without hidden free text."""
    payload = (
        _batch_prompt_payload(
            source_input,
            requested_rule_codes,
            batch_number=batch_number,
            batch_total=batch_total,
            candidate_id=candidate_id,
            batch_id=batch_id,
            agent_call_id=agent_call_id,
            scoped_source_span_ids=scoped_source_span_ids,
        )
        if compact or scoped_source
        else {
            **source_input.model_dump(
                mode="json", exclude={"interpretation_sources"}
            ),
            "interpretation_clarifications": _interpretation_clarifications(
                source_input, None
            ),
        }
    )
    batch_instruction = ""
    if requested_rule_codes is not None:
        batch_instruction = (
            "\n系统将按冻结目录顺序分批接收语义结果。本次 proposed_rules 必须且只能"
            f"返回这些官方父规则：{list(requested_rule_codes)}；保持给定顺序。"
            "这是传输分批，不是删除其他父规则；后续批次必须沿用相同 candidate_id。\n"
        )
        if compact:
            batch_instruction += (
                f"created_by_agent_call_id 必须继续使用 {agent_call_id!r}。\n"
                if agent_call_id
                else "首批生成的 created_by_agent_call_id 必须由后续所有批次原样复用。\n"
            )
    compact_instruction = (
        (
            f"\n本次使用服务端携带的 wire_version={DNF_WIRE_VERSION!r} 严格 JSON 合同；它只承载本批语义，"
            + _COMPACT_WIRE_COMPONENT_CONTRACT
            + "expression 和 exception_expression（无例外时为 null）必须是非空 group 数组；"
            "每个 group 必须同时提供 existence_atoms、scalar_atoms、set_atoms 数组。"
            "每个 atom 的原文定位必须放入 source_locator 对象；连续原文只填 source_clause，"
            "不连续片段只填 source_clauses；source_locator 必须且只能包含一个字段，且至少包含一个非空片段。"
            "严格只为本次明确的 1-3 个父规则返回最小完整 DNF；不得输出旧 wire 字段或正式领域身份。\n"
        )
        if compact
        else ""
    )
    schema_suffix = "" if compact else (
        f"输出结构：{_compact_schema(payload['allowed_source_span_ids'])}"
    )
    return (
        f"{prompt_template.strip()}\n\n"
        f"{_SYSTEM_CONTRACT}\n\n"
        f"{_INTERPRETATION_ANCHOR_CONTRACT}\n\n"
        f"{'' if compact else _FORMAL_DOMAIN_ID_CONTRACT + chr(10) + chr(10)}"
        f"{batch_instruction}"
        f"{compact_instruction}"
        f"输入：{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
        f"{schema_suffix}"
    )


def _next_batch_prompt(
    rule_codes: Sequence[str],
    *,
    batch_number: int,
    batch_total: int,
    candidate_id: str,
    agent_call_id: str | None = None,
    source_input: ProtocolDeconstructionInput | None = None,
    compact: bool = False,
    scoped_source: bool = False,
) -> str:
    if source_input is not None:
        return build_protocol_deconstruction_prompt(
            source_input,
            prompt_template=(
                f"继续返回冻结目录的第 {batch_number}/{batch_total} 批语义结果。"
                f"candidate_id 必须继续使用 {candidate_id!r}。"
                + (
                    f"created_by_agent_call_id 必须继续使用 {agent_call_id!r}。"
                    if agent_call_id
                    else ""
                )
            ),
            requested_rule_codes=rule_codes,
            batch_number=batch_number,
            batch_total=batch_total,
            candidate_id=candidate_id,
            agent_call_id=agent_call_id,
            compact=compact,
            scoped_source=scoped_source,
        )
    if compact:
        return (
            f"继续返回冻结目录的第 {batch_number}/{batch_total} 批语义结果。"
            f"candidate_id 必须继续使用 {candidate_id!r}；proposed_rules 必须且只能"
            f"按顺序返回 {list(rule_codes)}。不得重复前批，不得提前返回后批，不得省略本批父规则。"
            f"输出 wire_version={DNF_WIRE_VERSION!r} 的完整 JSON 对象，不要附加说明。"
            + _COMPACT_WIRE_COMPONENT_CONTRACT
        )
    return (
        f"继续返回冻结目录的第 {batch_number}/{batch_total} 批语义结果。"
        f"candidate_id 必须继续使用 {candidate_id!r}；proposed_rules 必须且只能"
        f"按顺序返回 {list(rule_codes)}。不得重复前批，不得提前返回后批，不得省略本批父规则。"
        "输出完整 JSON 对象，不要附加说明。输出结构："
        + _compact_schema()
    )


def _batch_schema_repair_prompt(
    rule_codes: Sequence[str],
    *,
    candidate_id: str | None,
    agent_call_id: str | None,
    batch_id: str | None,
    problem: str,
    compact: bool = False,
    allowed_source_span_ids: Sequence[str] = (),
) -> str:
    identity = (
        f"candidate_id 必须继续使用 {candidate_id!r}；" if candidate_id else ""
    )
    provenance = (
        "created_by_agent_call_id 必须继续使用 "
        f"{agent_call_id!r}；"
        if agent_call_id
        else ""
    )
    batch_identity = (
        f"batch_id 必须继续使用 {batch_id!r}；"
        if compact and batch_id
        else ""
    )
    schema_suffix = (
        (
            f"本次响应格式由服务端携带的 wire_version={DNF_WIRE_VERSION!r} 严格 JSON 合同定义；"
            + _COMPACT_WIRE_COMPONENT_CONTRACT
            + "expression 和 exception_expression 必须使用非空 group 数组；每个 group 同时提供三类 atom 数组。"
            "每个 atom 的 source_locator 只能包含 source_clause 或 source_clauses 其中一个字段；不要附加解释。"
        )
        if compact
        else "输出结构：" + _compact_schema(allowed_source_span_ids)
    )
    return (
        "本批输出无法按冻结目录合并。"
        + identity
        + provenance
        + batch_identity
        + f"proposed_rules 必须且只能按顺序返回 {list(rule_codes)}。"
        + f"具体问题：{problem[:12000]}。"
        + "仅修正本批 JSON 结构和列出的父规则，不要返回其他批次或说明文字。"
        + schema_suffix
    )


def _repair_prompt(
    issues: Sequence[ProtocolGateIssue],
    *,
    attempt: int,
    parsed_draft_available: bool,
    replacement_rule_codes: Sequence[str] = (),
    repair_batch_id: str | None = None,
    compact: bool = False,
    include_frozen_context: bool = False,
    candidate: ProtocolSemanticDeconstructionCandidate | None = None,
    source_input: ProtocolDeconstructionInput | None = None,
) -> str:
    repair_items = [
        {
            "问题代码": issue.issue_code,
            "问题": issue.problem,
            "影响范围": issue.affected_refs,
            "只允许修正": issue.repair_scope,
            "下一步": issue.next_action,
        }
        for issue in issues
    ]
    if parsed_draft_available and replacement_rule_codes:
        instruction = (
            "已有完整语义草稿通过结构解析。本次只能返回 ProtocolSemanticRuleRepair，"
            "candidate_id 必须与前稿一致；replacement_rules 必须且只能完整替换以下"
            "父规则。replacement_unresolved_items 和 replacement_structural_warnings 也只填本次父规则"
            "修订后仍然真实存在的事项；已解决的不得残留，非本次父规则的不得重复返回。"
            f"官方父规则：{list(replacement_rule_codes)}。不要返回整份草稿，不要返回未列出的父规则；"
            "系统会保持其他父规则完全不变。"
        )
    else:
        instruction = (
            "前一响应从未成功解析为完整草稿，因此不存在可保留的空草稿。"
            "请使用原会话中的冻结目录和方案原文，重新输出包含全部官方父规则"
            "及全部子规则的完整语义草稿；严禁输出空列表、错误占位符或部分草稿。"
        )
    schema_suffix = ""
    resolved_repair_batch_id = repair_batch_id
    if parsed_draft_available and replacement_rule_codes:
        resolved_repair_batch_id = repair_batch_id or _repair_batch_id(
            replacement_rule_codes
        )
        schema_suffix = (
            (
                "\n本次响应格式由服务端携带的扁平 wire JSON 合同定义；batch_id 必须为 "
                + resolved_repair_batch_id
                + "；"
                + _COMPACT_WIRE_COMPONENT_CONTRACT
                + "expression 和 exception_expression 必须使用非空 group 数组；每个 group 同时提供三类 atom 数组；每个 atom 的 source_locator 只能包含 source_clause 或 source_clauses 其中一个字段，不要附加解释。"
            )
            if compact
            else "\n局部修正输出结构：" + _compact_repair_schema(
                _batch_source_span_ids(source_input, replacement_rule_codes)
                if source_input is not None else ()
            )
        )
    elif compact:
        schema_suffix = (
            f"\n本次响应格式由服务端携带的 wire_version={DNF_WIRE_VERSION!r} 严格 JSON 合同定义；"
            + _COMPACT_WIRE_COMPONENT_CONTRACT
            + "expression 和 exception_expression 必须使用非空 group 数组；每个 group 同时提供三类 atom 数组；每个 atom 的 source_locator 只能包含 source_clause 或 source_clauses 其中一个字段，不要附加解释。"
        )
    candidate_context = ""
    if (compact or include_frozen_context) and candidate is not None and source_input is not None:
        selected_payload = _batch_prompt_payload(
            source_input,
            replacement_rule_codes,
            batch_number=None,
            batch_total=None,
            candidate_id=candidate.candidate_id,
            batch_id=resolved_repair_batch_id,
        )
        candidate_context = (
            "\n本次是定向修订，需保留的当前目标规则和本批原文如下；"
            "只返回 replacement_rules："
            + json.dumps(
                {
                    "candidate_id": candidate.candidate_id,
                    "batch_id": resolved_repair_batch_id,
                    "current_target_rule_codes": list(replacement_rule_codes),
                    "frozen_batch_input": selected_payload,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return (
        (_SYSTEM_CONTRACT + "\n" if include_frozen_context else "")
        + f"这是同一会话的第 {attempt} 次定向修正。"
        + instruction
        + "不得通过删除目录项、改官方编号、改来源或改访视实例规避问题。"
        "重新输出完整 JSON 对象，不要附加说明："
        + json.dumps(repair_items, ensure_ascii=False, sort_keys=True)
        + candidate_context
        + schema_suffix
    )


def _validation_error_summary(exc: ValidationError) -> str:
    """Preserve every actionable schema error without echoing huge inputs."""

    errors = []
    for error in exc.errors(include_url=False, include_context=False, include_input=False):
        location = ".".join(str(part) for part in error["loc"])
        errors.append(f"{location}: {error['msg']}")
    return "；".join(errors)


def _normalize_model_json(value):
    """Apply only semantics-preserving JSON-instance normalization."""

    if isinstance(value, list):
        return [_normalize_model_json(item) for item in value]
    if not isinstance(value, dict):
        return value
    normalized = {
        key: _normalize_model_json(item)
        for key, item in value.items()
        if not (key == "$defs" and item == {})
    }
    expression = normalized.get("expression")
    if (
        isinstance(expression, dict)
        and "exception_expression" in expression
        and normalized.get("exception_expression") is None
    ):
        normalized["exception_expression"] = expression.pop(
            "exception_expression"
        )
    if normalized.get("operator") == "and":
        normalized["operator"] = "all"
    elif normalized.get("operator") == "or":
        normalized["operator"] = "any"
    numeric_value = normalized.get("value")
    source_clause = normalized.get("source_clause")
    source_clauses = normalized.get("source_clauses")
    if (
        isinstance(source_clause, str)
        and isinstance(source_clauses, list)
        and source_clause in source_clauses
    ):
        normalized["source_clause"] = None
    if (
        "comparator" in normalized
        and isinstance(numeric_value, (int, float))
        and not isinstance(numeric_value, bool)
        and not normalized.get("unit")
    ):
        normalized["unit"] = "__missing_from_agent__"
    if normalized.get("lower_bound_days") == 0:
        normalized["lower_bound_days"] = None
    if (
        set(normalized) == {"kind", "operator", "children"}
        and normalized.get("kind") == "logical"
        and normalized.get("operator") in {"all", "any"}
        and isinstance(normalized.get("children"), list)
        and len(normalized["children"]) == 1
    ):
        return normalized["children"][0]
    return normalized


_WIRE_TIME_UNITS = frozenset({"day", "week", "month", "year"})
_WIRE_ANCHOR_TYPES = frozenset(
    {
        "icf_date",
        "screening_date",
        "baseline_date",
        "randomization_date",
        "first_dose_date",
        "study_drug_administration_date",
        "last_dose_date",
        "study_completion_date",
        "event_date",
        # 仅在解释澄清专用区显式解析未命名回溯锚点时可用；门禁对无绑定
        # 使用失败关闭。
        "review_node_date",
    }
)
_WIRE_TIME_DIRECTIONS = frozenset({"before", "after", "on"})
_WIRE_PROSPECTIVE_ANCHOR_TYPES = frozenset(
    {
        "study_drug_administration_date",
        "last_dose_date",
        "study_completion_date",
    }
)
_WIRE_PROTOCOL_PERIODS = frozenset({"treatment_period", "study_period"})
_WIRE_EXISTENCE_COMPARATORS = frozenset({"exists"})
_WIRE_SCALAR_COMPARATORS = frozenset({"eq", "ne", "gt", "gte", "lt", "lte"})
_WIRE_SET_COMPARATORS = frozenset({"in", "not_in"})
_WIRE_COMPARATORS = (
    _WIRE_EXISTENCE_COMPARATORS
    | _WIRE_SCALAR_COMPARATORS
    | _WIRE_SET_COMPARATORS
)

def _wire_time_quantity(value: Any) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("wire 时间数量必须是对象或 null")
    unknown_keys = set(value) - {"value", "unit"}
    if unknown_keys:
        raise ValueError(f"wire 时间数量含未知字段：{sorted(unknown_keys)}")
    raw_value = value.get("value")
    raw_unit = value.get("unit")
    if raw_value is None and raw_unit is None:
        return None
    if raw_value is None or raw_unit is None:
        raise ValueError("wire 时间数量的 value 和 unit 必须同时提供")
    if (
        isinstance(raw_value, bool)
        or not isinstance(raw_value, int)
        or raw_value <= 0
    ):
        raise ValueError("wire 时间数量的 value 必须是正整数")
    if not isinstance(raw_unit, str) or raw_unit not in _WIRE_TIME_UNITS:
        raise ValueError("wire 时间数量的 unit 必须是 day/week/month/year")
    return {"value": raw_value, "unit": raw_unit}


def _wire_time_constraint(value: Any) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("wire 时间约束必须是对象或 null")
    allowed_keys = {
        "anchor_type",
        "direction",
        "lower_bound_days",
        "upper_bound_days",
        "lower_bound",
        "upper_bound",
        "half_life_multiplier",
        "half_life_evidence",
        "combined_window_selection",
        "allow_partial_date",
    }
    unknown_keys = set(value) - allowed_keys
    if unknown_keys:
        raise ValueError(f"wire 时间约束含未知字段：{sorted(unknown_keys)}")
    anchor_type = value.get("anchor_type")
    direction = value.get("direction")
    lower_bound = _wire_time_quantity(value.get("lower_bound"))
    upper_bound = _wire_time_quantity(value.get("upper_bound"))
    lower_bound_days = value.get("lower_bound_days")
    upper_bound_days = value.get("upper_bound_days")
    half_life_multiplier = _coerce_wire_number(value.get("half_life_multiplier"))
    half_life_evidence = value.get("half_life_evidence")
    if half_life_evidence is not None and not isinstance(half_life_evidence, Mapping):
        raise ValueError("wire 半衰期依据必须是对象或 null")
    combined_window_selection = value.get("combined_window_selection")
    allow_partial_date = value.get("allow_partial_date")
    if (
        anchor_type is None
        and direction is None
        and lower_bound_days is None
        and upper_bound_days is None
        and lower_bound is None
        and upper_bound is None
        and half_life_multiplier is None
        and half_life_evidence is None
        and combined_window_selection is None
        and (allow_partial_date is None or allow_partial_date is False)
    ):
        return None
    if not isinstance(anchor_type, str) or anchor_type not in _WIRE_ANCHOR_TYPES:
        raise ValueError("wire 时间约束的 anchor_type 必须是有效非空锚点")
    if not isinstance(direction, str) or direction not in _WIRE_TIME_DIRECTIONS:
        raise ValueError("wire 时间约束的 direction 必须是有效非空方向")
    if not isinstance(allow_partial_date, bool):
        raise ValueError("wire 时间约束的 allow_partial_date 必须是布尔值")
    for name, bound in (
        ("lower_bound_days", lower_bound_days),
        ("upper_bound_days", upper_bound_days),
    ):
        if bound is not None and (
            isinstance(bound, bool) or not isinstance(bound, int) or bound < 0
        ):
            raise ValueError(f"wire 时间约束的 {name} 必须是非负整数")
    if half_life_multiplier is not None and (
        isinstance(half_life_multiplier, bool)
        or not isinstance(half_life_multiplier, (int, float))
        or half_life_multiplier <= 0
    ):
        raise ValueError("wire 时间约束的 half_life_multiplier 必须是正数")
    if combined_window_selection is not None and combined_window_selection != (
        "longer_of_calendar_and_half_life"
    ):
        raise ValueError(
            "wire 时间约束的 combined_window_selection 必须是 "
            "longer_of_calendar_and_half_life 或 null"
        )
    return {
        "anchor_type": anchor_type,
        "direction": direction,
        "lower_bound_days": lower_bound_days,
        "upper_bound_days": upper_bound_days,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "half_life_multiplier": half_life_multiplier,
        "half_life_evidence": half_life_evidence,
        "combined_window_selection": combined_window_selection,
        "allow_partial_date": allow_partial_date,
    }


def _wire_occurrence_window(value: Any) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("wire occurrence_window 必须是对象或 null")
    unknown_keys = set(value) - {"duration", "minimum_count", "scope", "horizon"}
    if unknown_keys:
        raise ValueError(f"wire occurrence_window 含未知字段：{sorted(unknown_keys)}")
    duration = _wire_time_quantity(value.get("duration"))
    minimum_count = value.get("minimum_count")
    if duration is None and minimum_count is None and value.get("scope") is None and value.get("horizon") is None:
        return None
    if duration is None:
        raise ValueError("wire occurrence_window 的 duration 必须是完整时间数量")
    if minimum_count is not None and (
        isinstance(minimum_count, bool)
        or not isinstance(minimum_count, int)
        or minimum_count <= 0
    ):
        raise ValueError("wire occurrence_window 的 minimum_count 必须是正整数")
    result = {"duration": duration, "minimum_count": minimum_count}
    if value.get("scope") is not None:
        from app.domain.contracts.occurrence_scope import OccurrenceScope
        result["scope"] = OccurrenceScope.model_validate(value["scope"]).model_dump(mode="json")
    if value.get("horizon") is not None:
        from app.domain.contracts.rules import FrequencyHorizon
        result["horizon"] = FrequencyHorizon.model_validate(value["horizon"]).model_dump(mode="json")
    return result


def _wire_prospective_window(value: Any) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("wire prospective_window 必须是对象或 null")
    unknown_keys = set(value) - {"anchor_type", "upper_bound"}
    if unknown_keys:
        raise ValueError(f"wire prospective_window 含未知字段：{sorted(unknown_keys)}")
    anchor_type = value.get("anchor_type")
    upper_bound = _wire_time_quantity(value.get("upper_bound"))
    if anchor_type is None and upper_bound is None:
        return None
    if not isinstance(anchor_type, str) or anchor_type not in _WIRE_PROSPECTIVE_ANCHOR_TYPES:
        raise ValueError("wire prospective_window 的 anchor_type 必须是有效非空锚点")
    if upper_bound is None:
        raise ValueError("wire prospective_window 的 upper_bound 必须是完整时间数量")
    return {"anchor_type": anchor_type, "upper_bound": upper_bound}


def _wire_prospective_period(value: Any) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("wire prospective_period 必须是对象或 null")
    unknown_keys = set(value) - {"period"}
    if unknown_keys:
        raise ValueError(f"wire prospective_period 含未知字段：{sorted(unknown_keys)}")
    period = value.get("period")
    if period is None:
        return None
    if not isinstance(period, str) or period not in _WIRE_PROTOCOL_PERIODS:
        raise ValueError("wire prospective_period 的 period 必须是有效非空期间")
    return {"period": period}


def _wire_numeric_scalar_value(value: Any) -> int | float:
    coerced = _coerce_wire_number(value)
    if (
        isinstance(coerced, bool)
        or not isinstance(coerced, (int, float))
        or not math.isfinite(coerced)
    ):
        _raise_wire_error(
            DNF_WIRE_ERROR_CODES["shape_mismatch"],
            "wire scalar atom 的 value 必须是有限数值标量；字符串或布尔分类值必须放入 set_atoms.values",
        )
    return coerced


def _wire_categorical_value(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        _raise_wire_error(
            DNF_WIRE_ERROR_CODES["shape_mismatch"],
            "wire set atom 的 values 必须是非空字符串分类值；数值必须放入 scalar_atoms.value",
        )
    return value


def _wire_atom(
    value: Any,
    *,
    shape: Literal["existence", "scalar", "set"],
) -> dict[str, object]:
    """Validate one DNF atom without accepting provider-owned identity."""

    if not isinstance(value, Mapping):
        raise ValueError("wire atom 必须是对象")
    _reject_legacy_graph_fields(value, context=f"wire {shape} atom")
    common_keys = {
        "subject",
        "attribute",
        "source_term",
        "source_locator",
        "unit",
        "applicable_population",
        "requires_professional_judgment",
        "occurrence_window",
        "prospective_window",
        "prospective_period",
        "time_constraint",
        "negated",
        "semantic_proposition",
    }
    common_keys.add("observation_policy")
    common_keys.add("repeat_scheme")
    shape_keys = {
        "scalar": {"comparator", "value"},
        "set": {"comparator", "values"},
        "existence": set(),
    }[shape]
    unknown_keys = set(value) - common_keys - shape_keys
    if unknown_keys:
        raise ValueError(f"wire {shape} atom 含未知字段：{sorted(unknown_keys)}")
    missing = {
        "subject",
        "attribute",
        "source_locator",
        "requires_professional_judgment",
        "negated",
        "observation_policy",
        "repeat_scheme",
    } - set(value)
    if "semantic_proposition" not in value:
        # 新生产合同把命题字段列为必填可空：缺失即视为旧方法或残缺输出，
        # 不能默认补 null 后继续读取。
        _raise_wire_error(
            DNF_WIRE_ERROR_CODES["missing_semantic_proposition"],
            f"wire {shape} atom 缺少 semantic_proposition；"
            "每个 atom 都必须显式给出命题或 null，不得省略字段",
        )
    if shape in {"scalar", "set"}:
        missing |= (
            {"comparator", "unit", "value" if shape == "scalar" else "values"}
            - set(value)
        )
    if missing:
        raise ValueError(f"wire {shape} atom 缺少字段：{sorted(missing)}")
    if not isinstance(value["negated"], bool):
        raise ValueError(f"wire {shape} atom 的 negated 必须是布尔值")
    for name in ("subject", "attribute"):
        if not isinstance(value[name], str) or not value[name].strip():
            raise ValueError(f"wire {shape} atom 的 {name} 必须是非空字符串")
    for name in ("source_term", "applicable_population"):
        item = value.get(name)
        if item is not None and (not isinstance(item, str) or not item.strip()):
            raise ValueError(f"wire {shape} atom 的 {name} 必须是字符串或 null")

    source_locator = value["source_locator"]
    if not isinstance(source_locator, Mapping):
        raise ValueError("wire source_locator 必须是对象")
    locator_keys = set(source_locator)
    if locator_keys not in ({"source_clause"}, {"source_clauses"}):
        raise ValueError(
            "wire source_locator 必须且只能包含 source_clause 或 source_clauses"
        )
    if "source_clause" in source_locator:
        source_clause = source_locator["source_clause"]
        if not isinstance(source_clause, str) or not source_clause.strip():
            raise ValueError("wire source_locator.source_clause 必须是非空字符串")
        source_clauses: list[str] = []
    else:
        source_clause = None
        raw_source_clauses = source_locator["source_clauses"]
        if not isinstance(raw_source_clauses, list) or not raw_source_clauses:
            raise ValueError(
                "wire source_locator.source_clauses 必须是非空字符串数组"
            )
        if not all(
            isinstance(item, str) and item.strip() for item in raw_source_clauses
        ):
            raise ValueError(
                "wire source_locator.source_clauses 必须是非空字符串数组"
            )
        source_clauses = list(raw_source_clauses)
        if len(source_clauses) != len(set(source_clauses)):
            raise ValueError("wire source_clauses 不得包含重复片段")

    professional = value["requires_professional_judgment"]
    if not isinstance(professional, bool):
        raise ValueError("wire atom 的 requires_professional_judgment 必须是布尔值")
    unit = value.get("unit")
    if unit is not None and (not isinstance(unit, str) or not unit.strip()):
        raise ValueError("wire atom 的 unit 必须是非空字符串或 null")

    comparator = "exists"
    raw_value: int | float | list[str] | None = None
    if shape == "scalar":
        comparator = value["comparator"]
        if comparator not in _WIRE_SCALAR_COMPARATORS:
            raise ValueError("wire scalar atom 的 comparator 无效")
        raw_value = _wire_numeric_scalar_value(value["value"])
    elif shape == "set":
        comparator = value["comparator"]
        if comparator not in _WIRE_SET_COMPARATORS:
            raise ValueError("wire set atom 的 comparator 无效")
        values = value["values"]
        if not isinstance(values, list) or not values:
            raise ValueError("wire set atom 的 values 必须是非空数组")
        raw_value = [_wire_categorical_value(item) for item in values]
    if value["negated"] and comparator in {"ne", "not_in"}:
        _raise_wire_error(
            DNF_WIRE_ERROR_CODES["shape_mismatch"],
            "wire atom 不得同时使用 negated=true 和 ne/not_in；"
            "否定必须选择一种无歧义表达",
        )
    if shape in {"scalar", "set"}:
        if not isinstance(unit, str) or not unit.strip():
            _raise_wire_error(
                DNF_WIRE_ERROR_CODES["missing_unit"],
                "wire value-bearing atom 必须提供非空 unit；"
                "非测量或分类值显式使用 unitless",
            )
        if shape == "set" and unit != "unitless":
            _raise_wire_error(
                DNF_WIRE_ERROR_CODES["categorical_unit"],
                "wire categorical atom 的 unit 必须且只能是 unitless",
            )
    if shape == "scalar":
        source_term = value.get("source_term")
        if not isinstance(source_term, str) or not source_term.strip():
            _raise_wire_error(
                DNF_WIRE_ERROR_CODES["shape_mismatch"],
                "wire scalar atom 必须用 source_term 逐字填写原文指标名",
            )

    occurrence_window = _wire_occurrence_window(value.get("occurrence_window"))
    raw_proposition = value["semantic_proposition"]
    if raw_proposition is not None:
        if not isinstance(raw_proposition, str) or not raw_proposition.strip():
            _raise_wire_error(
                DNF_WIRE_ERROR_CODES["proposition_shape"],
                f"wire {shape} atom 的 semantic_proposition 必须是非空字符串或 null",
            )
        if shape != "existence" or unit is not None:
            _raise_wire_error(
                DNF_WIRE_ERROR_CODES["proposition_shape"],
                "wire semantic_proposition 只用于不携带 value、unit 的非确定性条件；"
                "数值和分类判断仍须使用 scalar_atoms/set_atoms",
            )
        if professional:
            _raise_wire_error(
                DNF_WIRE_ERROR_CODES["proposition_shape"],
                "wire semantic_proposition 不得与 requires_professional_judgment 混用；"
                "研究者判断仍按其专属字段表达",
            )
        if occurrence_window is not None:
            _raise_wire_error(
                DNF_WIRE_ERROR_CODES["proposition_shape"],
                "wire semantic_proposition 不得与 occurrence_window 混用；"
                "频次必须结构化保存",
            )

    result = {
        "subject": value["subject"],
        "attribute": value["attribute"],
        "source_term": value.get("source_term"),
        "source_clause": source_clause,
        "source_clauses": source_clauses,
        "comparator": comparator,
        "value": raw_value,
        "unit": unit,
        "applicable_population": value.get("applicable_population"),
        "requires_professional_judgment": professional,
        "occurrence_window": occurrence_window,
        "prospective_window": _wire_prospective_window(
            value.get("prospective_window")
        ),
        "prospective_period": _wire_prospective_period(
            value.get("prospective_period")
        ),
        "semantic_proposition": raw_proposition,
        "unit_match_policy": "exact_canonical_label",
        "time_constraint": _wire_time_constraint(value.get("time_constraint")),
        "negated": value["negated"],
    }
    from app.domain.contracts.observation_selection import ObservationPolicy
    observation_clauses = (
        list(source_clauses) if source_clauses
        else ([source_clause] if source_clause else [])
    )
    policy_payload = dict(value["observation_policy"])
    if observation_clauses:
        raw_excerpts = list(policy_payload.get("source_excerpts") or [])
        raw_span_ids = list(policy_payload.get("source_span_ids") or [])
        if len(raw_span_ids) == 1 and len(raw_excerpts) > 1:
            merged = _merge_wire_observation_fragments(raw_excerpts, observation_clauses)
            if len(merged) == 1:
                policy_payload["source_excerpts"] = merged
                raw_excerpts = merged
        anchored_excerpts = _anchor_wire_source_excerpts(
            raw_excerpts, observation_clauses
        )
        if anchored_excerpts != raw_excerpts:
            policy_payload["source_excerpts"] = anchored_excerpts
    policy = ObservationPolicy.model_validate(policy_payload)
    result["observation_policy"] = policy.model_dump(mode="json")
    if value["repeat_scheme"] is not None:
        from app.domain.contracts.repeat_scheme import RepeatScheme
        scheme = RepeatScheme.model_validate(value["repeat_scheme"])
        if observation_clauses:
            anchored_repeat = _anchor_wire_source_excerpts(
                list(scheme.source_excerpts), observation_clauses
            )
            if anchored_repeat != list(scheme.source_excerpts):
                scheme = scheme.model_copy(update={"source_excerpts": anchored_repeat})
        scheme.require_current_extraction()
        result["repeat_scheme"] = scheme.model_dump(mode="json")
    return result


def _anchor_wire_source_excerpts(
    excerpts: list[str],
    clauses: Sequence[str],
) -> list[str]:
    """宿主侧观察/复查摘录锚定：整句超引时确定性回收到条件自身原文片段。

    实测模型（方案语义远端/本地各档）常把观察依据写成覆盖整个来源句的
    引文，而原子条件的逐字原文只是其中一个片段；这属于可由宿主无损回收
    的引文范围偏差，不应要求模型重做整批。仅处理三种确定性情情形：
    逐字命中、引号规范化命中、以及摘录唯一包含一个条件片段的超集情形；
    其余差异保持原样，由严格门禁拒绝。
    """
    if not clauses:
        return list(excerpts)
    anchored: list[str] = []
    for excerpt in excerpts:
        if any(excerpt in clause for clause in clauses):
            anchored.append(excerpt)
            continue
        recovered = _recover_exact_excerpt(excerpt, clauses)
        if any(recovered in clause for clause in clauses):
            anchored.append(recovered)
            continue
        contained = [clause for clause in clauses if clause in excerpt]
        if contained:
            # 超集可能覆盖多个条件片段；取唯一最长的片段作为最具体锚点，
            # 长度并列时保持歧义不猜。
            longest = max(len(clause) for clause in contained)
            longest_clauses = [
                clause for clause in contained if len(clause) == longest
            ]
            if len(longest_clauses) == 1:
                anchored.append(longest_clauses[0])
                continue
        anchored.append(excerpt)
    return anchored


def _merge_wire_observation_fragments(
    excerpts: list[str],
    clauses: Sequence[str],
) -> list[str]:
    """把"单来源多片段"的观察摘录按原文顺序并回一个逐字摘录。

    实测模型会把同一来源的观察依据拆成多个片段（模仿 source_clauses 的
    多片段形态），而观察政策合同要求来源与摘录逐项对应。仅当全部片段能
    在同一个条件原文片段中按给定顺序找到时，用首片段起点到末片段终点的
    原文子串并回单一摘录；任何缺失/乱序/跨片段情形都保持原样交给门禁。
    """
    if len(excerpts) <= 1:
        return list(excerpts)
    for clause in clauses:
        positions: list[int] = []
        cursor = 0
        ok = True
        for excerpt in excerpts:
            start = clause.find(excerpt, cursor)
            if start < 0:
                ok = False
                break
            positions.append(start)
            cursor = start + len(excerpt)
        if ok:
            merged = clause[positions[0]:cursor]
            return [merged]
    return list(excerpts)


def _canonical_wire_value(value: object) -> object:
    """Return a JSON-compatible value whose ordering is semantic-stable."""

    if isinstance(value, Mapping):
        return {
            str(key): _canonical_wire_value(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        return [_canonical_wire_value(item) for item in value]
    return value


def _canonical_wire_atom(
    shape: str,
    atom: Mapping[str, object],
) -> dict[str, object]:
    """Canonical identity payload; it intentionally excludes no provenance."""

    canonical = dict(atom)
    canonical["shape"] = shape
    # Set membership is commutative.  Keep the received list untouched in the
    # domain model, but sort it only for duplicate detection and identity.
    if shape == "set" and isinstance(canonical.get("value"), list):
        canonical["value"] = sorted(
            canonical["value"],
            key=lambda item: json.dumps(
                _canonical_wire_value(item),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    # source_clauses is an ordered reconstruction path through the protocol
    # text.  Its order is provenance, not set membership, so it must remain in
    # the identity payload exactly as received.
    return _canonical_wire_value(canonical)


def _canonical_wire_atom_key(shape: str, atom: Mapping[str, object]) -> str:
    return json.dumps(
        _canonical_wire_atom(shape, atom),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _canonical_wire_group_key(
    atoms: Sequence[tuple[str, Mapping[str, object]]],
) -> str:
    canonical_atoms = [
        _canonical_wire_atom(shape, atom) for shape, atom in atoms
    ]
    canonical_atoms.sort(
        key=lambda atom: json.dumps(
            atom,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return json.dumps(
        canonical_atoms,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _system_predicate_id(
    *,
    identity_prefix: str,
    group_key: str,
    atom_key: str,
) -> str:
    """Create a stable formal identity without provider/session metadata."""

    digest = _sha256(
        "dnf-v1\n"
        + identity_prefix
        + "\n"
        + group_key
        + "\n"
        + atom_key
    )
    return f"predicate:{identity_prefix}:{digest}"


def _wire_atom_expression(atom: Mapping[str, object]) -> dict[str, object]:
    predicate = dict(atom)
    negated = bool(predicate.pop("negated"))
    time_constraint = predicate.pop("time_constraint")
    expression: dict[str, object] = {
        "kind": "predicate",
        "predicate": predicate,
        "time_constraint": time_constraint,
    }
    if negated:
        return {"kind": "logical", "operator": "not", "children": [expression]}
    return expression


def _wire_dnf_expression(
    value: Any,
    *,
    identity_prefix: str,
    label: str,
    source_text: str,
) -> tuple[dict[str, object], list[list[str]]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"wire {label} 必须是非空 alternative group 数组")
    if len(value) > DNF_WIRE_MAX_GROUPS:
        _raise_wire_error(
            DNF_WIRE_ERROR_CODES["complexity_limit"],
            f"wire {label} 的 group 数量超过上限 {DNF_WIRE_MAX_GROUPS}",
        )
    groups: list[dict[str, object]] = []
    group_predicate_ids: list[list[str]] = []
    group_identity_keys: set[str] = set()
    expression_atom_count = 0
    group_keys = {"existence_atoms", "scalar_atoms", "set_atoms"}
    for group_index, group in enumerate(value, start=1):
        if not isinstance(group, Mapping):
            raise ValueError(f"wire {label} 的第 {group_index} 个 group 必须是对象")
        _reject_legacy_graph_fields(
            group,
            context=f"wire {label} 的第 {group_index} 个 group",
        )
        unknown_keys = set(group) - group_keys
        if unknown_keys:
            raise ValueError(
                f"wire {label} 的 group 含未知字段：{sorted(unknown_keys)}"
            )
        if set(group) != group_keys:
            raise ValueError(
                f"wire {label} 的 group 必须同时提供 existence_atoms、scalar_atoms、set_atoms"
            )
        atoms: list[tuple[str, dict[str, object]]] = []
        atom_identity_keys: set[str] = set()
        for shape, field in (
            ("existence", "existence_atoms"),
            ("scalar", "scalar_atoms"),
            ("set", "set_atoms"),
        ):
            raw_atoms = group[field]
            if not isinstance(raw_atoms, list):
                raise ValueError(f"wire {label}.{field} 必须是数组")
            if len(raw_atoms) > DNF_WIRE_MAX_ATOMS_PER_GROUP:
                _raise_wire_error(
                    DNF_WIRE_ERROR_CODES["complexity_limit"],
                    f"wire {label} 的第 {group_index} 个 group 的 {field} 数量"
                    f"超过上限 {DNF_WIRE_MAX_ATOMS_PER_GROUP}",
                )
            for raw_atom in raw_atoms:
                atom = _wire_atom(raw_atom, shape=shape)
                atom_key = _canonical_wire_atom_key(shape, atom)
                if atom_key in atom_identity_keys:
                    _raise_wire_error(
                        DNF_WIRE_ERROR_CODES["duplicate_atom"],
                        f"wire {label} 的第 {group_index} 个 group 含重复 atom",
                    )
                atom_identity_keys.add(atom_key)
                atoms.append((shape, atom))
        if not atoms:
            _raise_wire_error(
                DNF_WIRE_ERROR_CODES["empty_group"],
                f"wire {label} 的第 {group_index} 个 group 不能为空",
            )
        if len(atoms) > DNF_WIRE_MAX_ATOMS_PER_GROUP:
            _raise_wire_error(
                DNF_WIRE_ERROR_CODES["complexity_limit"],
                f"wire {label} 的第 {group_index} 个 group 的 atom 总数超过上限 "
                f"{DNF_WIRE_MAX_ATOMS_PER_GROUP}",
            )
        expression_atom_count += len(atoms)
        if expression_atom_count > DNF_WIRE_MAX_ATOMS_PER_EXPRESSION:
            _raise_wire_error(
                DNF_WIRE_ERROR_CODES["complexity_limit"],
                f"wire {label} 的 atom 总数超过上限 "
                f"{DNF_WIRE_MAX_ATOMS_PER_EXPRESSION}",
            )
        group_key = _canonical_wire_group_key(atoms)
        if group_key in group_identity_keys:
            _raise_wire_error(
                DNF_WIRE_ERROR_CODES["duplicate_group"],
                f"wire {label} 含重复 alternative group",
            )
        group_identity_keys.add(group_key)
        hydrated_atoms: list[dict[str, object]] = []
        for shape, atom in atoms:
            atom_with_identity = dict(atom)
            atom_with_identity["predicate_id"] = _system_predicate_id(
                identity_prefix=identity_prefix,
                group_key=group_key,
                atom_key=_canonical_wire_atom_key(shape, atom),
            )
            hydrated_atoms.append(atom_with_identity)
        children = [_wire_atom_expression(atom) for atom in hydrated_atoms]
        groups.append(
            children[0]
            if len(children) == 1
            else {"kind": "logical", "operator": "all", "children": children}
        )
        group_predicate_ids.append(
            [atom["predicate_id"] for atom in hydrated_atoms]
        )
    expression = (
        groups[0]
        if len(groups) == 1
        else {"kind": "logical", "operator": "any", "children": groups}
    )
    return expression, group_predicate_ids



def _resolve_wire_predicate_refs(
    value: Any,
    *,
    trigger_groups: list[list[str]],
    exception_groups: list[list[str]] | None,
    repeat_groups: Mapping[str, list[list[str]]] | None = None,
) -> list[str]:
    """Map optional DNF position refs to system predicate_ids; never invent links."""

    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("wire predicate_refs 必须是数组或省略")
    if not value:
        raise ValueError("wire predicate_refs 若提供则不得为空")
    resolved: list[str] = []
    seen: set[tuple[str, str | None, int, int]] = set()
    for index, item in enumerate(value, start=1):
        if not isinstance(item, Mapping):
            raise ValueError(f"wire predicate_refs 第 {index} 项必须是对象")
        unknown = set(item) - {"role", "group_index", "atom_index", "condition_id"}
        if unknown:
            raise ValueError(
                f"wire predicate_refs 第 {index} 项含未知字段：{sorted(unknown)}"
            )
        role = item.get("role")
        group_index = item.get("group_index")
        atom_index = item.get("atom_index")
        if role not in {"trigger", "exception", "repeat_trigger"}:
            raise ValueError(f"wire predicate_refs 第 {index} 项 role 无效")
        condition_id = item.get("condition_id")
        if role == "repeat_trigger":
            if not isinstance(condition_id, str) or condition_id not in (repeat_groups or {}):
                raise ValueError("资料要求须明确引用本组件已有的复查触发条件")
        elif "condition_id" in item:
            raise ValueError("只有复查触发条件引用可携带 condition_id")
        if not isinstance(group_index, int) or isinstance(group_index, bool) or group_index < 0:
            raise ValueError(f"wire predicate_refs 第 {index} 项 group_index 无效")
        if not isinstance(atom_index, int) or isinstance(atom_index, bool) or atom_index < 0:
            raise ValueError(f"wire predicate_refs 第 {index} 项 atom_index 无效")
        key = (role, condition_id, group_index, atom_index)
        if key in seen:
            raise ValueError("wire predicate_refs 不得重复")
        seen.add(key)
        groups = ((repeat_groups or {})[condition_id] if role == "repeat_trigger"
                  else trigger_groups if role == "trigger" else exception_groups)
        if groups is None:
            raise ValueError("资料要求引用了不存在的例外表达式")
        if group_index >= len(groups):
            raise ValueError("资料要求引用了不存在的条件组")
        if atom_index >= len(groups[group_index]):
            raise ValueError("资料要求引用了不存在的原子条件")
        resolved.append(groups[group_index][atom_index])
    return resolved


def _wire_semantic_rule(value: Any) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("wire semantic rule 必须是对象")
    _reject_legacy_graph_fields(value, context="wire semantic rule")
    unknown_rule_keys = set(value) - {"official_code", "components"}
    if unknown_rule_keys:
        raise ValueError(f"wire semantic rule 含未知字段：{sorted(unknown_rule_keys)}")
    components = value.get("components")
    if not isinstance(components, list) or not components:
        raise ValueError("wire semantic rule components 不能为空")
    if len(components) > DNF_WIRE_MAX_COMPONENTS_PER_RULE:
        _raise_wire_error(
            DNF_WIRE_ERROR_CODES["complexity_limit"],
            "wire semantic rule 的 component 数量超过上限 "
            f"{DNF_WIRE_MAX_COMPONENTS_PER_RULE}",
        )
    hydrated_components: list[dict[str, object]] = []
    for component_index, component in enumerate(components, start=1):
        if not isinstance(component, Mapping):
            raise ValueError("wire semantic component 必须是对象")
        _reject_legacy_graph_fields(
            component,
            context=f"wire semantic component {component_index}",
        )
        unknown_component_keys = set(component) - {
            "title",
            "expression",
            "exception_expression",
            "repeat_trigger_conditions",
            "evidence_requirements",
            "source_span_ids",
            "source_excerpts",
        }
        if unknown_component_keys:
            raise ValueError(
                "wire semantic component 含未知字段："
                f"{sorted(unknown_component_keys)}"
            )
        source_span_ids = component.get("source_span_ids")
        source_excerpts = component.get("source_excerpts")
        if not isinstance(source_span_ids, list) or not source_span_ids:
            raise ValueError("wire semantic component 缺少 source_span_ids")
        if not isinstance(source_excerpts, list) or not source_excerpts:
            raise ValueError("wire semantic component 缺少 source_excerpts")
        if not all(
            isinstance(excerpt, str) and excerpt.strip()
            for excerpt in source_excerpts
        ):
            raise ValueError("wire semantic component 的 source_excerpts 必须是非空字符串数组")
        source_text = "\n".join(source_excerpts)
        expression, trigger_groups = _wire_dnf_expression(
            component.get("expression"),
            identity_prefix=(
                f"{value.get('official_code', 'unknown')}:c{component_index}:trigger"
            ),
            label="expression",
            source_text=source_text,
        )
        exception_payload = component.get("exception_expression")
        if exception_payload is None:
            exception_expression = None
            exception_groups = None
        else:
            exception_expression, exception_groups = _wire_dnf_expression(
                exception_payload,
                identity_prefix=(
                    f"{value.get('official_code', 'unknown')}:c{component_index}:exception"
                ),
                label="exception_expression",
                source_text=source_text,
            )
        requirements = component.get("evidence_requirements")
        ancillary = component.get("repeat_trigger_conditions", [])
        if not isinstance(ancillary, list):
            raise ValueError("复查触发条件须单独列出，不能混入入排条件")
        repeat_conditions = []
        repeat_groups = {}
        for index, condition in enumerate(ancillary):
            if not isinstance(condition, Mapping) or set(condition) != {"condition_id", "expression", "evidence_roles"}:
                raise ValueError("复查触发条件须保留自己的身份与完整条件关系")
            condition_id = condition["condition_id"]
            if not isinstance(condition_id, str) or not condition_id.strip() or condition_id in repeat_groups:
                raise ValueError("复查触发条件身份须非空且不得重复")
            repeat_expression, condition_groups = _wire_dnf_expression(
                condition["expression"],
                identity_prefix=f"{value.get('official_code', 'unknown')}:c{component_index}:repeat:{index}",
                label="repeat_trigger_conditions", source_text=source_text,
            )
            from app.domain.contracts.repeat_scheme import RepeatEvidenceRoleReference, resolve_repeat_evidence_roles
            if not isinstance(condition["evidence_roles"], list):
                raise ValueError("复查取证范围须逐项列出")
            roles = resolve_repeat_evidence_roles(
                [RepeatEvidenceRoleReference.model_validate(item) for item in condition["evidence_roles"]],
                condition_groups, require_complete=True,
            )
            repeat_conditions.append({"condition_id": condition["condition_id"], "expression": repeat_expression,
                                      "predicate_evidence_roles": {key: role.model_dump(mode="json")
                                                                   for key, role in roles.items()}})
            repeat_groups[condition_id] = condition_groups
        def verify_policy_sources(node):
            if node is None:
                return
            if node["kind"] == "logical":
                for child in node["children"]:
                    verify_policy_sources(child)
                return
            policy = node["predicate"].get("observation_policy")
            scheme = node["predicate"].get("repeat_scheme")
            if scheme is not None and scheme["permission"] == "investigator_discretion":
                permission = next((item["expression"] for item in repeat_conditions
                                   if item["condition_id"] == scheme["permission_condition_id"]), None)
                def contains_judgment(expression):
                    if expression is None:
                        return False
                    if expression["kind"] == "predicate":
                        return expression["predicate"]["requires_professional_judgment"]
                    return any(contains_judgment(child) for child in expression["children"])
                if not contains_judgment(permission):
                    raise ValueError("研究者复查许可须保留明确的书面判断条件，不能用普通命题或签名代替")
            if policy is not None and (
                not set(policy["source_span_ids"]) <= set(source_span_ids)
                or any(not any(text in excerpt for excerpt in source_excerpts)
                       for text in policy["source_excerpts"])
            ):
                raise ValueError("观察选择来源不属于本组件原文")
        verify_policy_sources(expression)
        verify_policy_sources(exception_expression)
        for condition in repeat_conditions:
            verify_policy_sources(condition["expression"])
        if not isinstance(requirements, list) or not requirements:
            raise ValueError("wire evidence_requirements 不能为空")
        if len(requirements) > DNF_WIRE_MAX_REQUIREMENTS_PER_COMPONENT:
            _raise_wire_error(
                DNF_WIRE_ERROR_CODES["complexity_limit"],
                "wire evidence_requirements 数量超过上限 "
                f"{DNF_WIRE_MAX_REQUIREMENTS_PER_COMPONENT}",
            )
        hydrated_requirements: list[dict[str, object]] = []
        allowed_requirement_keys = {
            "fact_type",
            "required_source_types",
            "allows_screening_record_transcription",
            "requires_contemporaneous_objective_source",
            "due_stage",
            "source_validity_window",
            "description",
            "predicate_refs",
        }
        for requirement in requirements:
            if not isinstance(requirement, Mapping):
                raise ValueError("wire evidence requirement 必须是对象")
            unknown_requirement_keys = set(requirement) - allowed_requirement_keys
            if unknown_requirement_keys:
                raise ValueError(
                    "wire evidence requirement 含未知字段："
                    f"{sorted(unknown_requirement_keys)}"
                )
            if not {
                "allows_screening_record_transcription",
                "requires_contemporaneous_objective_source",
            }.issubset(requirement):
                raise ValueError("资料要求须明确来源政策，不得省略")
            predicate_ids = _resolve_wire_predicate_refs(
                requirement.get("predicate_refs"),
                trigger_groups=trigger_groups,
                exception_groups=exception_groups,
                repeat_groups=repeat_groups,
            )
            hydrated = {
                "fact_type": requirement.get("fact_type"),
                "required_source_types": requirement.get(
                    "required_source_types", []
                ),
                "allows_screening_record_transcription": requirement[
                    "allows_screening_record_transcription"
                ],
                "requires_contemporaneous_objective_source": requirement[
                    "requires_contemporaneous_objective_source"
                ],
                "due_stage": requirement.get("due_stage"),
                "source_validity_window": _wire_time_quantity(
                    requirement.get("source_validity_window")
                ),
                "description": requirement.get("description"),
            }
            if predicate_ids:
                hydrated["predicate_ids"] = predicate_ids
            hydrated_requirements.append(hydrated)
        hydrated_components.append(
            {
                "title": component.get("title"),
                "expression": expression,
                "exception_expression": exception_expression,
                "repeat_trigger_conditions": repeat_conditions,
                "evidence_requirements": hydrated_requirements,
                "source_span_ids": source_span_ids,
                "source_excerpts": source_excerpts,
            }
        )
    return {
        "official_code": value.get("official_code"),
        "components": hydrated_components,
    }


def _wire_unresolved_items(value: Any) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("wire unresolved items 必须是数组")
    return [dict(item) if isinstance(item, Mapping) else item for item in value]


def _parse_wire_semantic_candidate(
    payload: Any,
    *,
    expected_batch_id: str | None = None,
) -> tuple[ProtocolSemanticDeconstructionCandidate, str]:
    if not isinstance(payload, Mapping):
        raise ValueError("wire semantic candidate 必须是 JSON 对象")
    _reject_legacy_graph_fields(payload, context="wire semantic candidate")
    allowed_keys = {
        "wire_version",
        "candidate_id",
        "batch_id",
        "proposed_rules",
        "structural_warnings",
        "unresolved_items",
        "created_by_agent_call_id",
    }
    unknown_keys = set(payload) - allowed_keys
    if unknown_keys:
        raise ValueError(f"wire semantic candidate 含未知字段：{sorted(unknown_keys)}")
    required_keys = {
        "wire_version",
        "candidate_id",
        "batch_id",
        "proposed_rules",
        "structural_warnings",
        "unresolved_items",
        "created_by_agent_call_id",
    }
    missing_keys = required_keys - set(payload)
    if missing_keys:
        raise ValueError(f"wire semantic candidate 缺少字段：{sorted(missing_keys)}")
    if payload.get("wire_version") != DNF_WIRE_VERSION:
        raise ValueError(
            f"wire semantic candidate 的 wire_version 必须是 {DNF_WIRE_VERSION}"
        )
    batch_id = payload.get("batch_id")
    if not isinstance(batch_id, str) or not batch_id:
        raise ValueError("wire semantic candidate 缺少 batch_id")
    if expected_batch_id is not None and batch_id != expected_batch_id:
        raise ValueError(
            f"wire 批次身份不一致；应为 {expected_batch_id}，实际为 {batch_id}"
        )
    rules = payload.get("proposed_rules")
    if not isinstance(rules, list):
        raise ValueError("wire semantic candidate 缺少 proposed_rules")
    candidate = ProtocolSemanticDeconstructionCandidate.model_validate(
        {
            "candidate_id": payload.get("candidate_id"),
            "proposed_rules": [_wire_semantic_rule(rule) for rule in rules],
            "structural_warnings": _wire_unresolved_items(
                payload.get("structural_warnings")
            ),
            "unresolved_items": _wire_unresolved_items(payload.get("unresolved_items")),
            "created_by_agent_call_id": payload.get("created_by_agent_call_id"),
        }
    )
    return candidate, batch_id


def _parse_wire_semantic_repair(
    payload: Any,
    *,
    expected_batch_id: str | None = None,
) -> tuple[ProtocolSemanticRuleRepair, str]:
    if not isinstance(payload, Mapping):
        raise ValueError("wire semantic repair 必须是 JSON 对象")
    _reject_legacy_graph_fields(payload, context="wire semantic repair")
    allowed_keys = {
        "wire_version",
        "candidate_id",
        "batch_id",
        "replacement_rules",
        "replacement_structural_warnings",
        "replacement_unresolved_items",
    }
    unknown_keys = set(payload) - allowed_keys
    if unknown_keys:
        raise ValueError(f"wire semantic repair 含未知字段：{sorted(unknown_keys)}")
    required_keys = {
        "wire_version",
        "candidate_id",
        "batch_id",
        "replacement_rules",
        "replacement_structural_warnings",
        "replacement_unresolved_items",
    }
    missing_keys = required_keys - set(payload)
    if missing_keys:
        raise ValueError(f"wire semantic repair 缺少字段：{sorted(missing_keys)}")
    if payload.get("wire_version") != DNF_WIRE_VERSION:
        raise ValueError(
            f"wire semantic repair 的 wire_version 必须是 {DNF_WIRE_VERSION}"
        )
    batch_id = payload.get("batch_id")
    if not isinstance(batch_id, str) or not batch_id:
        raise ValueError("wire semantic repair 缺少 batch_id")
    if expected_batch_id is not None and batch_id != expected_batch_id:
        raise ValueError(
            f"wire 修订身份不一致；应为 {expected_batch_id}，实际为 {batch_id}"
        )
    rules = payload.get("replacement_rules")
    if not isinstance(rules, list):
        raise ValueError("wire semantic repair 缺少 replacement_rules")
    repair = ProtocolSemanticRuleRepair.model_validate(
        {
            "candidate_id": payload.get("candidate_id"),
            "replacement_rules": [_wire_semantic_rule(rule) for rule in rules],
            "replacement_structural_warnings": _wire_unresolved_items(
                payload.get("replacement_structural_warnings")
            ),
            "replacement_unresolved_items": _wire_unresolved_items(
                payload.get("replacement_unresolved_items")
            ),
        }
    )
    return repair, batch_id


_STAGE_DISPLAY_NAMES = {
    ReviewStage.PRE_SCREENING: "预筛选审核",
    ReviewStage.SCREENING: "筛选期审核",
    ReviewStage.RUN_IN: "筛选/导入期审核",
    ReviewStage.BASELINE: "基线审核",
}


_RULE_KIND_BY_PREFIX = {
    "IN": RuleKind.INCLUSION,
    "EX": RuleKind.EXCLUSION,
}


def _neutral_evidence_description(
    description: str,
    *,
    fact_type: str,
    due_stage: ReviewStage,
) -> str:
    if re.search(
        r"(?:确认|证明|判定|确保).{0,80}"
        r"(?:不存在|无异常|无不可接受|符合|满足|不符合|触发|未触发|排除)",
        description,
    ):
        return f"{_STAGE_DISPLAY_NAMES[due_stage]}：核对{fact_type}"
    return description


def _component_display_code(official_code: str, index: int, total: int) -> str:
    if total == 1:
        return official_code
    suffix = chr(ord("a") + index) if index < 26 else f"-{index + 1:02d}"
    return f"{official_code}{suffix}"


def _locator_projection(text: str) -> tuple[str, list[int]]:
    """Deprecated: kept for compatibility; new code uses _quote_normalize only."""
    projected: list[str] = []
    indexes: list[int] = []
    for index, original in enumerate(text):
        for char in unicodedata.normalize("NFKC", original).lower():
            if char.isspace() or unicodedata.category(char).startswith("P"):
                continue
            projected.append(char)
            indexes.append(index)
    return "".join(projected), indexes


def _recover_exact_excerpt(excerpt: str, sources: Sequence[str]) -> str:
    """Restore excerpt only when quote-glyph-normalized match is unique and contiguous.

    - Exact match is returned unchanged.
    - Otherwise, both excerpt and each source are normalized via _QUOTE_TRANSLATION
      (curved ↔ straight single/double quotes only). Length is preserved, so
      normalized indices map directly to original indices.
    - If the normalized excerpt occurs exactly once across all normalized sources
      (unique contiguous match), the original source substring with authentic
      quote glyphs is returned.
    - All other differences (words, digits, units, comparators, general punctuation,
      whitespace) remain strict and will not be restored; multiple or zero matches
      also fail and the original excerpt is returned for the strict gate to reject.
    """
    for source in sources:
        if excerpt in source:
            return excerpt
    normalized_excerpt = _quote_normalize(excerpt)
    # Search normalized space; translation is 1:1 so indices are stable.
    matches: list[tuple[str, int, int]] = []
    for source in sources:
        normalized_source = _quote_normalize(source)
        start = normalized_source.find(normalized_excerpt)
        while start >= 0:
            end = start + len(normalized_excerpt)
            matches.append((source, start, end))
            start = normalized_source.find(normalized_excerpt, start + 1)
    if len(matches) != 1:
        return excerpt
    source, start, end = matches[0]
    return source[start:end]


def _recover_exact_fragments(excerpt: str, sources: Sequence[str]) -> list[str]:
    """Split a fabricated shared-prefix clause only when two exact pieces are unique."""

    recovered = _recover_exact_excerpt(excerpt, sources)
    if any(recovered in source for source in sources):
        return [recovered]
    candidates: set[tuple[str, str]] = set()
    for split_at in range(2, len(excerpt) - 1):
        left, right = excerpt[:split_at], excerpt[split_at:]
        if len(right) < 2:
            continue
        for source in sources:
            left_start = source.find(left)
            while left_start >= 0:
                right_start = source.find(right, left_start + len(left))
                if right_start >= 0:
                    candidates.add((left, right))
                left_start = source.find(left, left_start + 1)
    if len(candidates) == 1:
        return list(next(iter(candidates)))
    return [excerpt]


def _visit_slug(visit: str) -> str:
    """访视实例的稳定短标识（前 8 位 SHA-256），用于多访视节点 id。"""
    import hashlib

    return hashlib.sha256(visit.encode("utf-8")).hexdigest()[:8]


def _hydrate_semantic_candidate(
    source_input: ProtocolDeconstructionInput,
    candidate: ProtocolSemanticDeconstructionCandidate,
) -> ProtocolDeconstructionDraft:
    """Assemble catalog-owned structure without asking the Agent to copy it."""

    semantic_rules_by_code = {
        rule.official_code: rule for rule in candidate.proposed_rules
    }
    expected_codes = [
        item.official_code
        for item in sorted(
            source_input.parent_rule_catalog.items,
            key=lambda value: value.position,
        )
    ]
    actual_codes = [rule.official_code for rule in candidate.proposed_rules]
    if actual_codes != expected_codes:
        raise ValueError(
            "语义草稿必须按冻结目录顺序逐项完整覆盖父规则；"
            f"应为 {expected_codes}，实际为 {actual_codes}"
        )
    source_materials = {
        material.source_span_id: material.text
        for material in source_input.source_materials
    }
    parent_mappings: list[ParentRuleCatalogMapping] = []
    proposed_rules: list[Rule] = []
    component_drafts: list[RuleComponentDraft] = []
    requirement_drafts: list[EvidenceRequirementDraft] = []
    stage_requirements: dict[ReviewStage, list[str]] = {}
    used_predicate_ids: set[str] = set()
    for item in sorted(
        source_input.parent_rule_catalog.items, key=lambda value: value.position
    ):
        semantic_rule = semantic_rules_by_code.get(item.official_code or "")
        rule_id = f"rule:{item.official_code}" if semantic_rule is not None else None
        parent_mappings.append(
            ParentRuleCatalogMapping(
                catalog_item_id=item.item_id,
                proposed_rule_id=(
                    rule_id if rule_id is not None else f"missing:{item.official_code}"
                ),
                source_span_ids=list(item.source_span_ids),
            )
        )
        if semantic_rule is None or item.official_code is None:
            continue
        components: list[RuleComponent] = []
        for component_index, semantic_component in enumerate(
            semantic_rule.components
        ):
            component_id = f"component:{item.official_code}:{component_index + 1:02d}"
            source_span_ids = list(semantic_component.source_span_ids)
            mapped_source_texts = [
                source_materials[span_id]
                for span_id in source_span_ids
                if span_id in source_materials
            ]
            source_excerpts = [
                _recover_exact_excerpt(excerpt, mapped_source_texts)
                for excerpt in semantic_component.source_excerpts
            ]
            expression = semantic_component.expression.model_copy(deep=True)
            exception_expression = (
                semantic_component.exception_expression.model_copy(deep=True)
                if semantic_component.exception_expression is not None
                else None
            )
            excerpt_sources = ["\n".join(source_excerpts)]
            repeat_conditions = [item.model_copy(deep=True) for item in semantic_component.repeat_trigger_conditions]
            predicate_id_remap: dict[str, str] = {}
            for root in (expression, exception_expression, *(item.expression for item in repeat_conditions)):
                if root is None:
                    continue
                for predicate_index, predicate in enumerate(
                    iter_atomic_predicates(root), start=1
                ):
                    original_predicate_id = predicate.predicate_id
                    if original_predicate_id in used_predicate_ids:
                        candidate_id = (
                            f"{original_predicate_id}:{component_id}:"
                            f"{predicate_index:02d}"
                        )
                        suffix = 2
                        while candidate_id in used_predicate_ids:
                            candidate_id = (
                                f"{original_predicate_id}:{component_id}:"
                                f"{predicate_index:02d}:{suffix}"
                            )
                            suffix += 1
                        predicate.predicate_id = candidate_id
                    used_predicate_ids.add(predicate.predicate_id)
                    predicate_id_remap[original_predicate_id] = predicate.predicate_id
                    if predicate.source_clause:
                        fragments = _recover_exact_fragments(
                            predicate.source_clause, excerpt_sources
                        )
                        if len(fragments) == 1:
                            predicate.source_clause = fragments[0]
                        else:
                            predicate.source_clause = None
                            predicate.source_clauses = fragments
                    if predicate.source_clauses:
                        predicate.source_clauses = [
                            fragment
                            for clause in predicate.source_clauses
                            for fragment in _recover_exact_fragments(
                                clause, excerpt_sources
                            )
                        ]
            for condition in repeat_conditions:
                condition.predicate_evidence_roles = {
                    predicate_id_remap[key]: role for key, role in condition.predicate_evidence_roles.items()
                }
            evidence_requirements = [
                EvidenceRequirement(
                    requirement_id=f"requirement:{component_id}:{index + 1:02d}",
                    rule_component_id=component_id,
                    fact_type=requirement.fact_type,
                    required_source_types=requirement.required_source_types,
                    allows_screening_record_transcription=(
                        requirement.allows_screening_record_transcription
                    ),
                    requires_contemporaneous_objective_source=(
                        requirement.requires_contemporaneous_objective_source
                    ),
                    due_stage=requirement.due_stage,
                    source_validity_window=requirement.source_validity_window,
                    description=_neutral_evidence_description(
                        requirement.description,
                        fact_type=requirement.fact_type,
                        due_stage=requirement.due_stage,
                    ),
                    predicate_ids=[
                        predicate_id_remap[predicate_id]
                        for predicate_id in requirement.predicate_ids
                    ],
                )
                for index, requirement in enumerate(
                    semantic_component.evidence_requirements
                )
            ]
            component = RuleComponent(
                rule_component_id=component_id,
                parent_rule_id=rule_id,
                display_code=_component_display_code(
                    item.official_code,
                    component_index,
                    len(semantic_rule.components),
                ),
                title=semantic_component.title,
                expression=expression,
                exception_expression=exception_expression,
                repeat_trigger_conditions=repeat_conditions,
                evidence_requirements=evidence_requirements,
            )
            components.append(component)
            draft_component_id = f"draft-component:{component_id}"
            component_drafts.append(
                RuleComponentDraft(
                    draft_component_id=draft_component_id,
                    parent_official_code=item.official_code,
                    proposed_component=component,
                    source_refs=source_span_ids,
                    source_excerpts=source_excerpts,
                )
            )
            for requirement in component.evidence_requirements:
                stage_requirements.setdefault(requirement.due_stage, []).append(
                    requirement.requirement_id
                )
                requirement_drafts.append(
                    EvidenceRequirementDraft(
                        draft_requirement_id=(
                            f"draft-requirement:{requirement.requirement_id}"
                        ),
                        draft_component_id=draft_component_id,
                        proposed_requirement=requirement,
                        source_refs=source_span_ids,
                    )
                )
        rule_source_text = "\n".join(
            source_materials[span_id]
            for span_id in item.source_span_ids
            if span_id in source_materials
        )
        proposed_rules.append(
            Rule(
                rule_id=rule_id,
                official_code=item.official_code,
                kind=_RULE_KIND_BY_PREFIX[item.official_code[:2]],
                source_text=rule_source_text or item.label,
                study_phase=source_input.selected_phase,
                components=components,
            )
        )

    procedure_mappings: list[ProcedureCatalogMapping] = []
    # 按（审核阶段, 访视实例）分组：同一阶段多个访视实例各自独立节点，
    # 不能由最后一个节点覆盖；单实例阶段保留兼容节点 id（stage:<stage>）。
    visit_groups: dict[tuple[str, str], list] = {}
    for item in sorted(
        source_input.required_procedure_catalog.items,
        key=lambda value: value.position,
    ):
        visit_groups.setdefault(
            (item.review_stage.value, item.visit_instance or ""), []
        ).append(item)
    stage_visit_count = {
        stage_value: sum(1 for group in visit_groups if group[0] == stage_value)
        for stage_value in {group[0] for group in visit_groups}
    }
    stage_first_node: dict[str, str] = {}
    workflow_stages: list[WorkflowStage] = []
    for (stage_value, visit), items in visit_groups.items():
        stage = ReviewStage(stage_value)
        multi_visit = stage_visit_count[stage_value] > 1
        node_id = (
            f"stage:{stage_value}"
            if not multi_visit
            else f"stage:{stage_value}:{_visit_slug(visit)}"
        )
        stage_first_node.setdefault(stage_value, node_id)
        display_name = _STAGE_DISPLAY_NAMES[stage]
        if multi_visit:
            display_name = f"{display_name}（{visit}）"
        node_requirement_ids: list[str] = []
        for item in items:
            if item.review_stage is None:
                raise ValueError(f"必做项目缺少审核阶段：{item.item_id}")
            requirement_id = f"requirement:{item.item_id}"
            requirement = EvidenceRequirement(
                requirement_id=requirement_id,
                procedure_catalog_item_id=item.item_id,
                fact_type="方案规定的访视操作或结果",
                due_stage=item.review_stage,
                description=f"{item.visit_instance}：{item.label}",
            )
            requirement_drafts.append(
                EvidenceRequirementDraft(
                    draft_requirement_id=f"draft-{requirement_id}",
                    procedure_catalog_item_id=item.item_id,
                    proposed_requirement=requirement,
                    source_refs=list(item.source_span_ids),
                )
            )
            procedure_mappings.append(
                ProcedureCatalogMapping(
                    catalog_item_id=item.item_id,
                    proposed_requirement_ids=[requirement_id],
                    proposed_workflow_stage_id=node_id,
                    source_span_ids=list(item.source_span_ids),
                )
            )
            node_requirement_ids.append(requirement_id)
        workflow_stages.append(
            WorkflowStage(
                workflow_stage_id=node_id,
                stage=stage,
                display_name=display_name,
                visit_instance=visit or None,
                due_requirement_ids=node_requirement_ids,
            )
        )

    # 组件资料要求（无访视实例）确定性挂到其 due_stage 的第一个访视节点。
    workflow_stages_by_id = {
        stage.workflow_stage_id: stage for stage in workflow_stages
    }
    for stage, requirement_ids in stage_requirements.items():
        node_id = stage_first_node.get(stage.value)
        if node_id is None:
            # A rule can explicitly name a review point even when the schedule
            # table has no standalone procedure row there. Preserve that point
            # instead of silently orphaning its evidence requirements.
            node_id = f"stage:{stage.value}"
            stage_first_node[stage.value] = node_id
            workflow_stages_by_id[node_id] = WorkflowStage(
                workflow_stage_id=node_id,
                stage=stage,
                display_name=_STAGE_DISPLAY_NAMES[stage],
                due_requirement_ids=[],
            )
        listed = workflow_stages_by_id[node_id]
        workflow_stages_by_id[node_id] = listed.model_copy(
            update={
                "due_requirement_ids": [
                    *listed.due_requirement_ids,
                    *requirement_ids,
                ]
            }
        )
    workflow_stages = list(workflow_stages_by_id.values())
    catalog_position = {
        item.item_id: item.position
        for item in source_input.required_procedure_catalog.items
    }
    # Visit grouping determines workflow nodes, but the immutable procedure
    # mapping list must retain the protocol catalog's source order.
    procedure_mappings.sort(key=lambda item: catalog_position[item.catalog_item_id])
    identity = source_input.identity_decision
    source_refs = list(source_input.allowed_source_span_ids)
    return ProtocolDeconstructionDraft(
        draft_id=f"draft:{candidate.candidate_id}",
        project_id=source_input.project_id,
        protocol_version_id=source_input.protocol_version_id,
        selected_phase=source_input.selected_phase,
        draft_revision=1,
        proposed_rules=proposed_rules,
        proposed_workflow_stages=workflow_stages,
        protocol_metadata=ProtocolMetadataDraft(
            protocol_code_candidate=identity.protocol_code,
            title_candidate=identity.project_name,
            version_candidate=identity.official_version,
            date_candidate=(
                str(identity.official_date.value) if identity.official_date else "未知"
            ),
            study_phase_candidates=[source_input.selected_phase.value],
            source_refs=source_refs,
        ),
        component_drafts=component_drafts,
        evidence_requirement_drafts=requirement_drafts,
        parent_catalog_mappings=parent_mappings,
        procedure_catalog_mappings=procedure_mappings,
        coverage=CoverageSummary(processed_refs=source_refs),
        structural_warnings=candidate.structural_warnings,
        unresolved_items=candidate.unresolved_items,
        source_refs=source_refs,
        created_by_agent_call_id=candidate.created_by_agent_call_id,
    )


def hydrate_semantic_preview(
    source_input: ProtocolDeconstructionInput,
    candidate: ProtocolSemanticDeconstructionCandidate,
) -> tuple[ProtocolDeconstructionDraft, list[str]]:
    """生成期间的只读预览水合：只覆盖已验证批次，未覆盖父规则单列待生成。

    通过把冻结目录缩减到已覆盖项来复用完整水合逻辑（同一 wire/ID/来源映射），
    不建立第二套草稿权威；返回的草稿对象只用于工作台只读投影，
    不会被保存为草稿 revision，也不能进入完整性检查或发布。
    """
    covered = {
        rule.official_code for rule in candidate.proposed_rules
    }
    full_catalog = source_input.parent_rule_catalog
    reduced_items = [
        item for item in full_catalog.items if item.official_code in covered
    ]
    pending = [
        item.official_code
        for item in sorted(full_catalog.items, key=lambda value: value.position)
        if item.official_code is not None and item.official_code not in covered
    ]
    if len(reduced_items) == len(full_catalog.items):
        return _hydrate_semantic_candidate(source_input, candidate), []
    if not reduced_items:
        raise ValueError("预览候选没有覆盖任何冻结父规则")
    reduced_input = source_input.model_copy(
        update={
            "parent_rule_catalog": full_catalog.model_copy(
                update={"items": reduced_items}
            )
        }
    )
    return _hydrate_semantic_candidate(reduced_input, candidate), pending


def semantic_candidate_from_draft(
    draft: ProtocolDeconstructionDraft,
) -> ProtocolSemanticDeconstructionCandidate:
    """Recover the semantic layer needed to resume a persisted repair session."""

    mappings = {
        item.proposed_component.rule_component_id: item
        for item in draft.component_drafts
    }
    semantic_rules: list[SemanticRule] = []
    for rule in draft.proposed_rules:
        components: list[SemanticRuleComponent] = []
        for component in rule.components:
            mapping = mappings.get(component.rule_component_id)
            if mapping is None:
                raise ValueError(
                    f"规则组件缺少语义草稿来源映射：{component.rule_component_id}"
                )
            components.append(
                SemanticRuleComponent(
                    title=component.title,
                    expression=component.expression.model_copy(deep=True),
                    exception_expression=(
                        component.exception_expression.model_copy(deep=True)
                        if component.exception_expression is not None
                        else None
                    ),
                    repeat_trigger_conditions=[item.model_copy(deep=True) for item in component.repeat_trigger_conditions],
                    evidence_requirements=[
                        SemanticEvidenceRequirement(
                            fact_type=requirement.fact_type,
                            required_source_types=requirement.required_source_types,
                            allows_screening_record_transcription=(
                                requirement.allows_screening_record_transcription
                            ),
                            requires_contemporaneous_objective_source=(
                                requirement.requires_contemporaneous_objective_source
                            ),
                            due_stage=requirement.due_stage,
                            source_validity_window=requirement.source_validity_window,
                            description=requirement.description,
                            predicate_ids=list(requirement.predicate_ids),
                        )
                        for requirement in component.evidence_requirements
                    ],
                    source_span_ids=mapping.source_refs,
                    source_excerpts=mapping.source_excerpts,
                )
            )
        semantic_rules.append(
            SemanticRule(official_code=rule.official_code, components=components)
        )
    candidate_id = draft.draft_id.removeprefix("draft:")
    return ProtocolSemanticDeconstructionCandidate(
        candidate_id=candidate_id,
        proposed_rules=semantic_rules,
        structural_warnings=draft.structural_warnings,
        unresolved_items=draft.unresolved_items,
        created_by_agent_call_id=draft.created_by_agent_call_id,
    )


def revise_protocol_draft_from_feedback(
    source_input: ProtocolDeconstructionInput,
    current_draft: ProtocolDeconstructionDraft,
    *,
    target_rule_code: str,
    feedback_note: str,
    transport: ProtocolAgentTransport,
) -> ProtocolDeconstructionDraft:
    """依据一条明确的原文理解纠错，局部重新解构指定父规则。

    反馈是输入资料，不是发布权威。返回内容必须使用当前
    candidate_id，且只能替换指定官方父规则；其他规则由程序原样保留。
    """

    note = feedback_note.strip()
    if not note:
        raise ValueError("原文理解纠错必须写明具体问题和期望修正")
    current = semantic_candidate_from_draft(current_draft)
    current_codes = [rule.official_code for rule in current.proposed_rules]
    if target_rule_code not in current_codes:
        raise ValueError(f"当前草稿中找不到入排标准 {target_rule_code}")
    target = next(
        rule for rule in current.proposed_rules if rule.official_code == target_rule_code
    )
    compact = _uses_compact_wire_contract(transport)
    repair_batch_id = _repair_batch_id([target_rule_code])
    output_contract = (
        f"本次响应格式由服务端携带的 wire_version={DNF_WIRE_VERSION!r} 严格 JSON 合同定义；只返回 replacement_rules，"
        f"batch_id 必须为 {repair_batch_id}；"
        + _COMPACT_WIRE_COMPONENT_CONTRACT
        + "expression 和 exception_expression 必须使用非空 group 数组；每个 group 同时提供三类 atom 数组；"
        "每个 atom 的 source_locator 只能包含 source_clause 或 source_clauses 其中一个字段；不要附加解释。"
        if compact
        else "输出结构：" + _compact_repair_schema(
            _batch_source_span_ids(source_input, [target_rule_code])
        )
    )
    compact_source_context = (
        json.dumps(
            _batch_prompt_payload(
                source_input,
                [target_rule_code],
                batch_number=1,
                batch_total=1,
                candidate_id=current.candidate_id,
                batch_id=repair_batch_id,
            ),
            ensure_ascii=False,
            sort_keys=True,
        )
        if compact
        else json.dumps(
            {
                **source_input.model_dump(
                    mode="json",
                    exclude={
                        "interpretation_source_ids",
                        "interpretation_sources",
                    },
                ),
                "interpretation_clarifications": _interpretation_clarifications(
                    source_input, {target_rule_code}
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    prompt = (
        "你正在根据医学监查员指出的原文理解错误，局部修正已有方案"
        "解构草稿。用户反馈不能改变方案权威；仅当给定方案原文支持时"
        "才能修正。你必须只返回 ProtocolSemanticRuleRepair JSON，"
        f"candidate_id 必须为 {current.candidate_id!r}，replacement_rules 必须且只能"
        f"包含 {target_rule_code}。不得修改官方编号、增删其他父规则或伪造来源。\n\n"
        "本次是最小范围纠错，不是重写整条规则。除用户明确指出且方案原文支持修改的字段外，"
        "目标规则中现有的子项、谓词、ALL/ANY/NOT 逻辑、数值和单位、频次结构、时间限定、"
        "例外、资料要求、应完成阶段和来源片段都必须逐字段原样保留；compact wire 不得自行生成身份。"
        "输出前必须把 replacement_rules 与当前目标规则逐字段比较；任何无关变化都要撤销。\n\n"
        f"用户指出的问题：{note}\n\n"
        f"当前目标规则：{target.model_dump_json()}\n\n"
        f"冻结的方案输入：{compact_source_context}\n\n"
        f"{output_contract}"
    )
    _configure_transport_output_scope(transport, source_input, [target_rule_code])
    response = transport.start(
        prompt=prompt,
        output_kind="semantic_rule_repair",
    )
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            repair = _parse_semantic_repair(
                response.text,
                compact=compact,
                expected_batch_id=(
                    repair_batch_id if compact else None
                ),
            )
            _validate_semantic_repair(
                repair,
                expected_codes=[target_rule_code],
                expected_candidate_id=current.candidate_id,
                expected_batch_id=repair_batch_id if compact else None,
                source_input=source_input,
            )
            revised = _apply_semantic_repair(
                current,
                repair,
                expected_codes=[target_rule_code],
            )
            hydrated = _hydrate_semantic_candidate(source_input, revised)
            # 局部修订必须追加到当前不可变草稿链；语义候选 ID 只是模型会话
            # 身份，不能反向生成一个新的 draft_id。
            return hydrated.model_copy(
                update={
                    "draft_id": current_draft.draft_id,
                    "draft_revision": current_draft.draft_revision,
                    "previous_draft_id": current_draft.previous_draft_id,
                }
            )
        except Exception as exc:
            last_error = exc
            if attempt == 1:
                break
            response = transport.continue_session(
                session_id=response.session_id,
                prompt=(
                    "上一响应无法作为指定父规则的局部修订读取。"
                    f"问题：{str(exc)[:12000]}。请只返回符合下列结构的 JSON："
                    + (
                        f"服务端携带的 wire_version={DNF_WIRE_VERSION!r} 严格 JSON 合同；batch_id 必须为 "
                        f"{repair_batch_id}；"
                        + _COMPACT_WIRE_COMPONENT_CONTRACT
                        + "expression 和 exception_expression 必须使用非空 group 数组；每个 group 同时提供三类 atom 数组；"
                        "每个 atom 的 source_locator 只能包含 source_clause 或 source_clauses 其中一个字段；不要附加解释。"
                        if compact
                        else _compact_repair_schema(
                            _batch_source_span_ids(source_input, [target_rule_code])
                        )
                    )
                ),
                output_kind="semantic_rule_repair",
            )
    raise ProtocolAgentCallError(
        response.session_id,
        f"反馈修订经过一次结构纠正后仍无法读取：{last_error}",
    )


def _parse_semantic_candidate(
    text: str,
    *,
    compact: bool = False,
    expected_batch_id: str | None = None,
) -> ProtocolSemanticDeconstructionCandidate:
    payload = json.loads(text)
    if compact:
        try:
            candidate, _batch_id = _parse_wire_semantic_candidate(
                payload,
                expected_batch_id=expected_batch_id,
            )
            return candidate
        except ValidationError as exc:
            raise ValueError(_validation_error_summary(exc)) from exc
    payload = _normalize_model_json(payload)
    try:
        return ProtocolSemanticDeconstructionCandidate.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(_validation_error_summary(exc)) from exc


def _validate_semantic_batch(
    candidate: ProtocolSemanticDeconstructionCandidate,
    *,
    expected_codes: Sequence[str],
    expected_candidate_id: str | None,
    expected_agent_call_id: str | None = None,
    source_input: ProtocolDeconstructionInput | None = None,
) -> None:
    actual_codes = [rule.official_code for rule in candidate.proposed_rules]
    if actual_codes != list(expected_codes):
        raise ValueError(
            "本批官方父规则与冻结顺序不一致；"
            f"应为 {list(expected_codes)}，实际为 {actual_codes}"
        )
    if (
        expected_candidate_id is not None
        and candidate.candidate_id != expected_candidate_id
    ):
        raise ValueError("后续批次不得更换 candidate_id")
    if (
        expected_agent_call_id is not None
        and candidate.created_by_agent_call_id != expected_agent_call_id
    ):
        raise ValueError("后续批次不得更换 created_by_agent_call_id")
    if source_input is None:
        return
    _validate_batch_source_closure(
        source_input,
        expected_codes=expected_codes,
        rules=candidate.proposed_rules,
        warning_items=candidate.structural_warnings,
        unresolved_items=candidate.unresolved_items,
    )


def _validate_batch_source_closure(
    source_input: ProtocolDeconstructionInput,
    *,
    expected_codes: Sequence[str],
    rules: Sequence[SemanticRule],
    warning_items: Sequence[UnresolvedItem],
    unresolved_items: Sequence[UnresolvedItem],
) -> None:
    selected = set(expected_codes)
    selected_source_ids = set(
        _batch_source_span_ids(source_input, expected_codes)
    )
    component_source_ids = {
        source_span_id
        for rule in rules
        for component in rule.components
        for source_span_id in component.source_span_ids
    }
    issue_source_ids = {
        source_ref
        for item in (*warning_items, *unresolved_items)
        for source_ref in item.source_refs
    }
    invalid_source_ids = (component_source_ids | issue_source_ids) - selected_source_ids
    if invalid_source_ids:
        raise ValueError(
            "本批来源片段不属于选定父规则来源闭包（跨批次、流程来源或无归属）："
            f"{sorted(invalid_source_ids)}"
        )
    for rule in rules:
        for component in rule.components:
            outside_component = set(source_references(
                component.model_dump(mode="json")
            )) - set(component.source_span_ids)
            if outside_component:
                raise ValueError(
                    "观察、复查或其他嵌套来源不属于本组件声明的原文："
                    f"{sorted(outside_component)}"
                )
    foreign_codes = {
        code
        for item in (*warning_items, *unresolved_items)
        for ref in item.affected_scope
        for code in re.findall(r"(?:IN|EX)-\d{2}", ref)
    } - selected
    if foreign_codes:
        raise ValueError(f"本批待确认事项污染了其他父规则：{sorted(foreign_codes)}")


def _validate_semantic_repair(
    repair: ProtocolSemanticRuleRepair,
    *,
    expected_codes: Sequence[str],
    expected_candidate_id: str,
    expected_batch_id: str | None = None,
    source_input: ProtocolDeconstructionInput | None = None,
) -> None:
    if expected_batch_id is not None:
        canonical_batch_id = _repair_batch_id(expected_codes)
        if expected_batch_id != canonical_batch_id:
            raise ValueError(
                "局部修订 expected_batch_id 不是目标父规则集合的规范身份；"
                f"应为 {canonical_batch_id}，实际为 {expected_batch_id}"
            )
    actual_codes = [rule.official_code for rule in repair.replacement_rules]
    if actual_codes != list(expected_codes):
        raise ValueError(
            "局部修订官方父规则与目标集合不一致；"
            f"应为 {list(expected_codes)}，实际为 {actual_codes}"
        )
    if repair.candidate_id != expected_candidate_id:
        raise ValueError("局部修订不得更换 candidate_id")
    if source_input is not None:
        _validate_batch_source_closure(
            source_input,
            expected_codes=expected_codes,
            rules=repair.replacement_rules,
            warning_items=repair.replacement_structural_warnings,
            unresolved_items=repair.replacement_unresolved_items,
        )


def _merge_semantic_batches(
    batches: Sequence[ProtocolSemanticDeconstructionCandidate],
    *,
    expected_codes: Sequence[str] | None = None,
    expected_candidate_id: str | None = None,
    source_input: ProtocolDeconstructionInput | None = None,
) -> ProtocolSemanticDeconstructionCandidate:
    if not batches:
        raise ValueError("没有可合并的语义批次")
    first = batches[0]
    merged_codes = [
        rule.official_code for batch in batches for rule in batch.proposed_rules
    ]
    if len(merged_codes) != len(set(merged_codes)):
        raise ValueError("语义批次之间存在重复官方父规则")
    if expected_codes is not None and merged_codes != list(expected_codes):
        raise ValueError(
            "语义批次未精确闭合冻结父规则目录；"
            f"应为 {list(expected_codes)}，实际为 {merged_codes}"
        )
    candidate_id = expected_candidate_id or first.candidate_id
    if any(batch.candidate_id != candidate_id for batch in batches):
        raise ValueError("语义批次之间不得更换 candidate_id")
    if source_input is not None:
        for batch in batches:
            batch_codes = [rule.official_code for rule in batch.proposed_rules]
            _validate_batch_source_closure(
                source_input,
                expected_codes=batch_codes,
                rules=batch.proposed_rules,
                warning_items=batch.structural_warnings,
                unresolved_items=batch.unresolved_items,
            )
    call_ids = [batch.created_by_agent_call_id for batch in batches]
    if any(call_id != call_ids[0] for call_id in call_ids[1:]):
        raise ValueError(
            "语义批次之间不得更换 created_by_agent_call_id；"
            f"实际为 {call_ids}"
        )
    return ProtocolSemanticDeconstructionCandidate(
        candidate_id=candidate_id,
        proposed_rules=[
            rule for batch in batches for rule in batch.proposed_rules
        ],
        structural_warnings=[
            item for batch in batches for item in batch.structural_warnings
        ],
        unresolved_items=[
            item for batch in batches for item in batch.unresolved_items
        ],
        created_by_agent_call_id=first.created_by_agent_call_id,
    )


def _parse_semantic_repair(
    text: str,
    *,
    compact: bool = False,
    expected_batch_id: str | None = None,
) -> ProtocolSemanticRuleRepair:
    payload = json.loads(text)
    if compact:
        try:
            repair, _batch_id = _parse_wire_semantic_repair(
                payload,
                expected_batch_id=expected_batch_id,
            )
            return repair
        except ValidationError as exc:
            raise ValueError(_validation_error_summary(exc)) from exc
    payload = _normalize_model_json(payload)
    try:
        return ProtocolSemanticRuleRepair.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(_validation_error_summary(exc)) from exc


def _apply_semantic_repair(
    candidate: ProtocolSemanticDeconstructionCandidate,
    repair: ProtocolSemanticRuleRepair,
    *,
    expected_codes: Sequence[str],
) -> ProtocolSemanticDeconstructionCandidate:
    if repair.candidate_id != candidate.candidate_id:
        raise ValueError("局部修正不得更换 candidate_id")
    actual_codes = [rule.official_code for rule in repair.replacement_rules]
    if set(actual_codes) != set(expected_codes) or len(actual_codes) != len(
        expected_codes
    ):
        raise ValueError(
            "局部修正必须且只能替换指定父规则；"
            f"应为 {list(expected_codes)}，实际为 {actual_codes}"
        )
    replacements = {rule.official_code: rule for rule in repair.replacement_rules}
    selected = set(expected_codes)

    def scoped_rule_codes(item: UnresolvedItem) -> set[str]:
        return {
            code
            for ref in item.affected_scope
            for code in re.findall(r"(?:IN|EX)-\d{2}", ref)
        }

    for item in (
        *repair.replacement_structural_warnings,
        *repair.replacement_unresolved_items,
    ):
        item_codes = scoped_rule_codes(item)
        if not item_codes or not item_codes <= selected:
            raise ValueError("局部修正返回了指定父规则之外的待确认事项")

    def outside_selected(item: UnresolvedItem) -> bool:
        return scoped_rule_codes(item).isdisjoint(selected)

    merged = candidate.model_copy(
        update={
            "proposed_rules": [
                replacements.get(rule.official_code, rule)
                for rule in candidate.proposed_rules
            ],
            "structural_warnings": [
                item for item in candidate.structural_warnings if outside_selected(item)
            ]
            + repair.replacement_structural_warnings,
            "unresolved_items": [
                item for item in candidate.unresolved_items if outside_selected(item)
            ]
            + repair.replacement_unresolved_items,
        },
        deep=True,
    )
    return ProtocolSemanticDeconstructionCandidate.model_validate(
        merged.model_dump(mode="json")
    )


def _affected_rule_codes(
    draft: ProtocolDeconstructionDraft,
    issues: Sequence[ProtocolGateIssue],
    *,
    fallback_all: bool = True,
) -> list[str]:
    refs = {ref for issue in issues for ref in issue.affected_refs}
    affected: list[str] = []
    for rule in draft.proposed_rules:
        identifiers = {rule.rule_id, rule.official_code}
        for component in rule.components:
            identifiers.update(
                {
                    component.rule_component_id,
                    component.display_code,
                }
            )
            expressions = [component.expression]
            if component.exception_expression is not None:
                expressions.append(component.exception_expression)
            for expression in expressions:
                identifiers.update(
                    predicate.predicate_id
                    for predicate in iter_atomic_predicates(expression)
                )
        if identifiers & refs:
            affected.append(rule.official_code)
    if affected or not fallback_all:
        return affected
    return [rule.official_code for rule in draft.proposed_rules]


def _repair_issues_for_rules(
    draft: ProtocolDeconstructionDraft,
    issues: Sequence[ProtocolGateIssue],
    selected_codes: Sequence[str],
) -> list[ProtocolGateIssue]:
    selected = set(selected_codes)
    allowed_refs: set[str] = set()
    for rule in draft.proposed_rules:
        if rule.official_code not in selected:
            continue
        allowed_refs.update({rule.rule_id, rule.official_code})
        for component in rule.components:
            allowed_refs.update(
                {component.rule_component_id, component.display_code}
            )
            expressions = [component.expression]
            if component.exception_expression is not None:
                expressions.append(component.exception_expression)
            for expression in expressions:
                allowed_refs.update(
                    predicate.predicate_id
                    for predicate in iter_atomic_predicates(expression)
                )

    scoped: list[ProtocolGateIssue] = []
    for issue in issues:
        affected_refs = [ref for ref in issue.affected_refs if ref in allowed_refs]
        if not affected_refs:
            continue
        repair_scope = [ref for ref in issue.repair_scope if ref in allowed_refs]
        scoped.append(
            issue.model_copy(
                update={
                    "affected_refs": affected_refs,
                    "repair_scope": repair_scope or affected_refs,
                }
            )
        )
    return scoped


def _select_repair_rule_codes(
    draft: ProtocolDeconstructionDraft,
    issues: Sequence[ProtocolGateIssue],
    attempt_counts: Mapping[str, int],
    *,
    limit: int,
) -> list[str]:
    """Give every affected parent a repair turn before repeatedly revisiting one."""

    affected = _affected_rule_codes(draft, issues, fallback_all=False)
    official_order = {
        rule.official_code: index for index, rule in enumerate(draft.proposed_rules)
    }
    return sorted(
        affected,
        key=lambda code: (attempt_counts.get(code, 0), official_order[code]),
    )[:limit]


def _issue_severity_by_rule(
    draft: ProtocolDeconstructionDraft,
    issues: Sequence[ProtocolGateIssue],
) -> dict[str, tuple[int, int, int]]:
    counts: dict[str, list[int]] = {
        rule.official_code: [0, 0, 0] for rule in draft.proposed_rules
    }
    for issue in issues:
        for code in _affected_rule_codes(draft, [issue], fallback_all=False):
            if issue.level == "阻止发布":
                counts[code][0] += 1
            elif issue.level == "需要核对":
                counts[code][1] += 1
            counts[code][2] += 1
    return {code: tuple(values) for code, values in counts.items()}


def regressing_rule_codes(
    previous_draft: ProtocolDeconstructionDraft,
    previous_issues: Sequence[ProtocolGateIssue],
    revised_draft: ProtocolDeconstructionDraft,
    revised_issues: Sequence[ProtocolGateIssue],
    selected_codes: Sequence[str],
) -> set[str]:
    refined_prints = _refined_time_anchor_fingerprints(
        previous_draft,
        previous_issues,
        revised_draft,
        revised_issues,
        selected_codes,
    )
    refined_fingerprints = {
        fingerprint
        for prints in refined_prints.values()
        for fingerprint in prints
    }
    # A proven refinement is not a new problem: exclude it from both the
    # severity counts and the fingerprint comparison. Everything else —
    # including any fingerprint that merely moved — still regresses.
    revised_countable = [
        issue
        for issue in revised_issues
        if (issue.issue_code, tuple(sorted(issue.affected_refs)))
        not in refined_fingerprints
    ]
    previous = _issue_severity_by_rule(previous_draft, previous_issues)
    revised = _issue_severity_by_rule(revised_draft, revised_countable)
    previous_fingerprints = _issue_fingerprints_by_rule(
        previous_draft, previous_issues
    )
    revised_fingerprints = _issue_fingerprints_by_rule(
        revised_draft, revised_countable
    )
    return {
        code
        for code in selected_codes
        if revised.get(code, (0, 0, 0)) > previous.get(code, (0, 0, 0))
        or bool(
            revised_fingerprints.get(code, set())
            - previous_fingerprints.get(code, set())
        )
    }


def _issue_fingerprints_by_rule(
    draft: ProtocolDeconstructionDraft,
    issues: Sequence[ProtocolGateIssue],
) -> dict[str, set[tuple[str, tuple[str, ...]]]]:
    fingerprints: dict[str, set[tuple[str, tuple[str, ...]]]] = {
        rule.official_code: set() for rule in draft.proposed_rules
    }
    for issue in issues:
        for code in _affected_rule_codes(draft, [issue], fallback_all=False):
            fingerprints[code].add(
                (issue.issue_code, tuple(sorted(issue.affected_refs)))
            )
    return fingerprints


# The only allowed issue refinement: a local semantic revision may resolve a
# parent-source coverage gap by covering the missing span, and the covering
# component may then expose a genuine unanchored lookback on that same span.
# Generic gate vocabulary only; no project- or content-specific logic.
_COVERAGE_MISSING_ISSUE_CODE = "PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING"
_TIME_ANCHOR_UNRESOLVED_ISSUE_CODE = "TIME_ANCHOR_UNRESOLVED"


def _refined_time_anchor_fingerprints(
    previous_draft: ProtocolDeconstructionDraft,
    previous_issues: Sequence[ProtocolGateIssue],
    revised_draft: ProtocolDeconstructionDraft,
    revised_issues: Sequence[ProtocolGateIssue],
    selected_codes: Sequence[str],
) -> dict[str, set[tuple[str, tuple[str, ...]]]]:
    """Return refined ``TIME_ANCHOR_UNRESOLVED`` fingerprints per parent rule.

    A revised unresolved-time-anchor issue counts as a refinement of one
    previous ``PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING`` issue only when both
    hold on the same official parent rule and the revised predicate's owning
    component cites only spans the previous issue listed as missing. Mixed
    source ownership is ambiguous and stays rejected by the caller.
    """
    selected = set(selected_codes)
    missing_spans: dict[str, set[str]] = {}
    for issue in previous_issues:
        if issue.issue_code != _COVERAGE_MISSING_ISSUE_CODE:
            continue
        matched = set(
            _affected_rule_codes(previous_draft, [issue], fallback_all=False)
        )
        for code in matched & selected:
            missing_spans.setdefault(code, set()).update(
                ref for ref in issue.affected_refs if ref not in matched
            )
    if not missing_spans:
        return {}
    owners: dict[str, tuple[str, frozenset[str]]] = {}
    for item in revised_draft.component_drafts:
        expressions = [item.proposed_component.expression]
        if item.proposed_component.exception_expression is not None:
            expressions.append(item.proposed_component.exception_expression)
        for expression in expressions:
            for predicate in iter_atomic_predicates(expression):
                owners.setdefault(
                    predicate.predicate_id,
                    (item.parent_official_code, frozenset(item.source_refs)),
                )
    refined: dict[str, set[tuple[str, tuple[str, ...]]]] = {}
    for issue in revised_issues:
        if issue.issue_code != _TIME_ANCHOR_UNRESOLVED_ISSUE_CODE:
            continue
        matched = set(
            _affected_rule_codes(revised_draft, [issue], fallback_all=False)
        )
        fingerprint = (issue.issue_code, tuple(sorted(issue.affected_refs)))
        for ref in issue.affected_refs:
            owner = owners.get(ref)
            if owner is None:
                continue
            parent_code, source_refs = owner
            if parent_code not in matched:
                continue
            missing = missing_spans.get(parent_code, set())
            if source_refs and source_refs <= missing:
                refined.setdefault(parent_code, set()).add(fingerprint)
    return refined


def _restore_candidate_rules(
    revised: ProtocolSemanticDeconstructionCandidate,
    previous: ProtocolSemanticDeconstructionCandidate,
    restore_codes: set[str],
) -> ProtocolSemanticDeconstructionCandidate:
    previous_by_code = {rule.official_code: rule for rule in previous.proposed_rules}
    return revised.model_copy(
        update={
            "proposed_rules": [
                previous_by_code[rule.official_code]
                if rule.official_code in restore_codes
                else rule
                for rule in revised.proposed_rules
            ]
        },
        deep=True,
    )


def _parse_protocol_draft(
    text: str,
    source_input: ProtocolDeconstructionInput | None = None,
) -> ProtocolDeconstructionDraft:
    payload = json.loads(text)
    normalized = _normalize_model_json(payload)
    if "candidate_id" in normalized:
        if source_input is None:
            raise ValueError("语义候选必须绑定冻结的方案解构输入")
        candidate = _parse_semantic_candidate(text)
        return _hydrate_semantic_candidate(source_input, candidate)
    try:
        return ProtocolDeconstructionDraft.model_validate(normalized)
    except ValidationError as exc:
        raise ValueError(_validation_error_summary(exc)) from exc


def _format_issue(message: str) -> ProtocolGateIssue:
    return ProtocolGateIssue(
        issue_code="AGENT_OUTPUT_SCHEMA_INVALID",
        check_name="tree_integrity",
        level="阻止发布",
        problem="模型返回的结构化草稿无法读取：" + message[:12000],
        impact="当前输出不能进入方案审阅，也不能自动修成看似合理的规则。",
        next_action="请在同一会话中仅修正输出结构，并重新返回完整草稿。",
        affected_refs=["protocol_draft"],
        repair_scope=["protocol_draft_json"],
    )


def _call_issue(error: ProtocolAgentCallError) -> ProtocolGateIssue:
    timeout = error.error_code == "TRANSPORT_TIMEOUT"
    quota = error.error_code == "QUOTA_EXHAUSTED"
    base = (
        "模型服务可用额度已耗尽，需等待恢复或调整已授权的接入。" if quota
        else "等待模型返回超时。" if timeout
        else "模型调用未完成。"
    )
    detail = str(error).strip()
    problem = base if not detail or detail == base else f"{base}服务返回：{detail[:800]}"
    return ProtocolGateIssue(
        issue_code=("AGENT_CALL_QUOTA_EXHAUSTED" if quota else
                    "AGENT_CALL_TRANSPORT_TIMEOUT" if timeout else "AGENT_CALL_FAILED"),
        check_name="tree_integrity",
        level="阻止发布",
        problem=problem,
        impact="本次未取得完整方案解构结果，不能进入方案审阅。",
        next_action="保留本次资料与调用记录，检查模型服务后再从有效记录恢复；不要按输出格式错误反复修改。",
        affected_refs=["protocol_draft"],
        repair_scope=["model_service"],
    )


def _uses_compact_wire_contract(transport: ProtocolAgentTransport) -> bool:
    return bool(getattr(transport, "uses_compact_wire_contract", False))


def _supports_parent_rule_segmentation(
    transport: ProtocolAgentTransport,
) -> bool:
    declared = getattr(transport, "supports_parent_rule_segmentation", None)
    if declared is None:
        # Compatibility for existing compact transports; new providers should
        # declare the capability explicitly.
        return _uses_compact_wire_contract(transport)
    return bool(declared)


def _compact_transport_history(
    transport: ProtocolAgentTransport,
    session_id: str,
    *,
    context: str,
) -> None:
    if not getattr(transport, "supports_bounded_batch_context", _uses_compact_wire_contract(transport)):
        return
    compactor = getattr(transport, "compact_session_history", None)
    if not callable(compactor):
        raise ValueError("当前模型连接未提供有界会话整理能力")
    compactor(session_id=session_id, context=context)


def _configure_transport_output_scope(
    transport: ProtocolAgentTransport,
    source_input: ProtocolDeconstructionInput,
    rule_codes: Sequence[str],
    *,
    allowed_source_span_ids: Sequence[str] | None = None,
) -> None:
    """Bound provider output by the frozen size of the current rule batch."""
    configure = getattr(transport, "configure_output_scope", None)
    if not callable(configure):
        return
    selected_codes = set(rule_codes)
    selected = [
        item
        for item in source_input.parent_rule_catalog.items
        if item.official_code in selected_codes
    ]
    if len(selected) != len(rule_codes):
        raise ValueError("输出批次与冻结父规则目录不一致")
    span_counts = [len(item.source_span_ids) for item in selected]
    max_span_count = max(span_counts, default=1)
    owned_source_span_ids = tuple(
        dict.fromkeys(
            span_id
            for item in selected
            for span_id in item.source_span_ids
        )
    )
    if allowed_source_span_ids is None:
        scoped_source_span_ids = owned_source_span_ids
    else:
        scoped_source_span_ids = tuple(dict.fromkeys(allowed_source_span_ids))
        if not scoped_source_span_ids or not set(scoped_source_span_ids) <= set(
            owned_source_span_ids
        ):
            raise ValueError("输出分段来源必须属于当前官方父规则")
    configure(
        official_codes=tuple(rule_codes),
        allowed_source_span_ids=scoped_source_span_ids,
        component_limit=min(
            DNF_WIRE_MAX_COMPONENTS_PER_RULE,
            max(4, max_span_count * 2),
        ),
        group_limit=min(DNF_WIRE_MAX_GROUPS, max(2, max_span_count)),
        atom_limit=min(
            DNF_WIRE_MAX_ATOMS_PER_GROUP,
            max(4, max_span_count * 2),
        ),
        requirement_limit=min(
            DNF_WIRE_MAX_REQUIREMENTS_PER_COMPONENT,
            max(4, max_span_count * 2),
        ),
    )


def _plan_semantic_rule_batches(
    source_input: ProtocolDeconstructionInput,
    *,
    prompt_template: str,
    batch_size: int,
    compact: bool,
) -> list[list[str]]:
    """Pack ordered parent rules under the actual batch-scoped prompt budget."""

    expected_codes = [
        item.official_code
        for item in sorted(
            source_input.parent_rule_catalog.items,
            key=lambda item: item.position,
        )
        if item.official_code is not None
    ]
    effective_batch_size = min(batch_size, 3)

    batches: list[list[str]] = []
    current: list[str] = []
    # Use the maximum possible batch total while planning. The final batch
    # number changes only a few characters and cannot make this estimate less
    # conservative.
    planning_total = max(1, len(expected_codes))
    for code in expected_codes:
        candidate = [*current, code]
        prompt = build_protocol_deconstruction_prompt(
            source_input,
            prompt_template=prompt_template,
            requested_rule_codes=candidate,
            batch_number=planning_total,
            batch_total=planning_total,
            compact=compact,
            scoped_source=True,
        )
        over_budget = (
            estimate_text_tokens(prompt) > SEMANTIC_BATCH_MAX_INPUT_TOKENS
        )
        if current and (over_budget or len(candidate) > effective_batch_size):
            batches.append(current)
            current = [code]
        else:
            current = candidate
    if current:
        batches.append(current)
    return batches


def _semantic_batch_cache_key(
    transport: ProtocolAgentTransport,
    *,
    prompt: str,
    batch_id: str,
    rule_codes: Sequence[str],
    cache_contract: str = "protocol-semantic-batch/v1",
    source_input: ProtocolDeconstructionInput | None = None,
    prompt_template: str | None = None,
) -> str | None:
    identity_builder = getattr(transport, "semantic_cache_identity", None)
    if not callable(identity_builder):
        return None
    payload = {
        "cache_contract": cache_contract,
        "transport": identity_builder(output_kind="semantic_candidate"),
        "prompt": prompt,
        "batch_id": batch_id,
        "rule_codes": list(rule_codes),
    }
    if source_input is not None:
        payload["protocol_file_sha256"] = source_input.protocol_file_sha256
        payload["extraction_snapshot_id"] = source_input.extraction_snapshot_id
    if prompt_template is not None:
        payload["prompt_template_sha256"] = _sha256(prompt_template.strip())
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _validate_cached_semantic_batch(
    text: str,
    *,
    source_input: ProtocolDeconstructionInput,
    rule_codes: Sequence[str],
    candidate_id: str | None,
    agent_call_id: str | None,
) -> ProtocolSemanticDeconstructionCandidate | None:
    try:
        candidate = _parse_semantic_candidate(text)
        _validate_semantic_batch(
            candidate,
            expected_codes=rule_codes,
            expected_candidate_id=candidate_id,
            expected_agent_call_id=agent_call_id,
            source_input=source_input,
        )
        return candidate
    except Exception:
        return None


def _parent_segmentation_thresholds() -> ParentSegmentationThresholds:
    from app.config import (
        DECONSTRUCT_PARENT_SEGMENT_MAX_CONCURRENCY,
        DECONSTRUCT_PARENT_SEGMENT_MAX_UNITS_PER_SEGMENT,
        DECONSTRUCT_PARENT_SEGMENT_MIN_OBLIGATIONS,
        DECONSTRUCT_PARENT_SEGMENT_MIN_SOURCE_SPANS,
        DECONSTRUCT_PARENT_SEGMENT_SOFT_INPUT_TOKENS,
        DECONSTRUCT_PARENT_SEGMENT_SOFT_TOKENS,
        DECONSTRUCT_PARENT_SEGMENTATION_ENABLED,
    )

    return ParentSegmentationThresholds(
        enabled=DECONSTRUCT_PARENT_SEGMENTATION_ENABLED,
        soft_input_tokens=DECONSTRUCT_PARENT_SEGMENT_SOFT_INPUT_TOKENS,
        min_source_spans=DECONSTRUCT_PARENT_SEGMENT_MIN_SOURCE_SPANS,
        min_obligations=DECONSTRUCT_PARENT_SEGMENT_MIN_OBLIGATIONS,
        max_concurrency=DECONSTRUCT_PARENT_SEGMENT_MAX_CONCURRENCY,
        segment_soft_tokens=DECONSTRUCT_PARENT_SEGMENT_SOFT_TOKENS,
        max_units_per_segment=DECONSTRUCT_PARENT_SEGMENT_MAX_UNITS_PER_SEGMENT,
    )


def _collect_parent_segment(
    source_input: ProtocolDeconstructionInput,
    *,
    prompt_template: str,
    segment: ParentRuleSegment,
    transport_factory: Callable[[], ProtocolAgentTransport],
    batch_cache: ProtocolSemanticBatchCache | None,
) -> ProtocolSemanticDeconstructionCandidate:
    transport = transport_factory()
    if not _supports_parent_rule_segmentation(transport):
        raise ProtocolParentSegmentError(
            segment.segment_id,
            "SEGMENTATION_UNSUPPORTED",
            "当前模型传输未声明支持父规则分段",
        )
    compact = _uses_compact_wire_contract(transport)
    _configure_transport_output_scope(
        transport,
        source_input,
        [segment.parent_official_code],
        allowed_source_span_ids=segment.source_span_ids,
    )
    prompt = build_protocol_deconstruction_prompt(
        source_input,
        prompt_template=(
            prompt_template.strip()
            + "\n本次只解构该官方父规则的一个冻结结构分段；不得补写本分段未提供的兄弟分段内容。"
        ),
        requested_rule_codes=[segment.parent_official_code],
        batch_id=segment.segment_id,
        compact=compact,
        scoped_source=True,
        scoped_source_span_ids=segment.source_span_ids,
    )
    cache_key = _semantic_batch_cache_key(
        transport,
        prompt=prompt,
        batch_id=segment.segment_id,
        rule_codes=[segment.parent_official_code],
        cache_contract="protocol-semantic-parent-segment/v1",
        source_input=source_input,
        prompt_template=prompt_template,
    )
    cached_text = (
        batch_cache.load(cache_key)
        if batch_cache is not None and cache_key is not None
        else None
    )
    if cached_text is not None:
        cached = _validate_cached_semantic_batch(
            cached_text,
            source_input=source_input,
            rule_codes=[segment.parent_official_code],
            candidate_id=None,
            agent_call_id=None,
        )
        if cached is not None:
            validate_segment_source_closure(cached, segment)
            return cached

    response: ProtocolAgentResponse | None = None
    for transport_attempt in range(2):
        try:
            response = transport.start(
                prompt=prompt,
                output_kind="semantic_candidate",
            )
            break
        except ProtocolAgentCallError as exc:
            if exc.error_code != "TRANSPORT_TIMEOUT" or transport_attempt:
                raise ProtocolParentSegmentError(
                    segment.segment_id,
                    exc.error_code,
                    str(exc),
                ) from exc
            retry_transport = transport_factory()
            if not _supports_parent_rule_segmentation(retry_transport):
                raise ProtocolParentSegmentError(
                    segment.segment_id,
                    "SEGMENTATION_UNSUPPORTED",
                    "同模型重试传输未声明支持父规则分段",
                ) from exc
            if _uses_compact_wire_contract(retry_transport) != compact:
                raise ProtocolParentSegmentError(
                    segment.segment_id,
                    "TRANSPORT_IDENTITY_CHANGED",
                    "同分段重试时输出合同发生变化",
                ) from exc
            _configure_transport_output_scope(
                retry_transport,
                source_input,
                [segment.parent_official_code],
                allowed_source_span_ids=segment.source_span_ids,
            )
            retry_cache_key = _semantic_batch_cache_key(
                retry_transport,
                prompt=prompt,
                batch_id=segment.segment_id,
                rule_codes=[segment.parent_official_code],
                cache_contract="protocol-semantic-parent-segment/v1",
                source_input=source_input,
                prompt_template=prompt_template,
            )
            if retry_cache_key != cache_key:
                raise ProtocolParentSegmentError(
                    segment.segment_id,
                    "TRANSPORT_IDENTITY_CHANGED",
                    "同分段重试时模型或请求合同发生变化",
                ) from exc
            transport = retry_transport
    assert response is not None
    for attempt in range(2):
        try:
            candidate = _parse_semantic_candidate(
                response.text,
                compact=compact,
                expected_batch_id=segment.segment_id if compact else None,
            )
            _validate_semantic_batch(
                candidate,
                expected_codes=[segment.parent_official_code],
                expected_candidate_id=None,
                source_input=source_input,
            )
            validate_segment_source_closure(candidate, segment)
            if batch_cache is not None and cache_key is not None:
                batch_cache.store(
                    cache_key,
                    candidate.model_dump_json(),
                    cache_contract="protocol-semantic-parent-segment/v1",
                )
            return candidate
        except ProtocolAgentCallError as exc:
            raise ProtocolParentSegmentError(
                segment.segment_id,
                exc.error_code,
                str(exc),
            ) from exc
        except Exception as exc:
            if attempt:
                raise ProtocolParentSegmentError(
                    segment.segment_id,
                    "SCHEMA_INVALID",
                    f"结构修复后仍不完整：{exc}",
                ) from exc
            try:
                response = transport.continue_session(
                    session_id=response.session_id,
                    prompt=_batch_schema_repair_prompt(
                        [segment.parent_official_code],
                        candidate_id=None,
                        agent_call_id=None,
                        batch_id=segment.segment_id,
                        problem=str(exc),
                        compact=compact,
                        allowed_source_span_ids=segment.source_span_ids,
                    )
                    + "\n本分段每个产生义务的规则组件都必须在 source_span_ids 中引用至少一个"
                    + "正文来源标识；不得只引用父级限定语。正文来源标识："
                    + json.dumps(
                        list(segment.body_source_span_ids),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    output_kind="semantic_candidate",
                )
            except ProtocolAgentCallError as call_exc:
                raise ProtocolParentSegmentError(
                    segment.segment_id,
                    call_exc.error_code,
                    str(call_exc),
                ) from call_exc
    raise AssertionError("unreachable")


def _try_collect_parent_segments(
    source_input: ProtocolDeconstructionInput,
    *,
    prompt_template: str,
    parent_prompt: str,
    rule_codes: Sequence[str],
    transport_factory: Callable[[], ProtocolAgentTransport] | None,
    batch_cache: ProtocolSemanticBatchCache | None,
    candidate_id: str | None,
    agent_call_id: str | None,
) -> ProtocolSemanticDeconstructionCandidate | None:
    if transport_factory is None or len(rule_codes) != 1:
        return None
    item = next(
        (
            item
            for item in source_input.parent_rule_catalog.items
            if item.official_code == rule_codes[0]
        ),
        None,
    )
    if item is None:
        return None
    thresholds = _parent_segmentation_thresholds()
    plan = plan_parent_rule_segments(
        item,
        source_materials=source_input.source_materials,
        token_estimate=estimate_text_tokens(parent_prompt),
        thresholds=thresholds,
    )
    if plan is None:
        return None
    try:
        with ThreadPoolExecutor(
            max_workers=min(
                len(plan.segments),
                clamp_parent_segment_concurrency(thresholds.max_concurrency),
            ),
            thread_name_prefix="protocol-parent-segment",
        ) as pool:
            candidates = list(
                pool.map(
                    lambda segment: _collect_parent_segment(
                        source_input,
                        prompt_template=prompt_template,
                        segment=segment,
                        transport_factory=transport_factory,
                        batch_cache=batch_cache,
                    ),
                    plan.segments,
                )
            )
        digest = _sha256(
            json.dumps(
                {
                    "protocol_file_sha256": source_input.protocol_file_sha256,
                    "extraction_snapshot_id": source_input.extraction_snapshot_id,
                    "parent_official_code": plan.parent_official_code,
                    "segment_ids": [segment.segment_id for segment in plan.segments],
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )[:24]
        merged = merge_parent_rule_segments(
            candidates,
            plan=plan,
            candidate_id=candidate_id or f"parent-segment-candidate:{digest}",
            agent_call_id=agent_call_id or f"parent-segment-call:{digest}",
        )
        _validate_semantic_batch(
            merged,
            expected_codes=rule_codes,
            expected_candidate_id=candidate_id,
            expected_agent_call_id=agent_call_id,
            source_input=source_input,
        )
        logger.info(
            "protocol parent segmentation accepted",
            extra={
                "official_code": plan.parent_official_code,
                "segment_count": len(plan.segments),
            },
        )
        return merged
    except Exception as exc:
        if (
            isinstance(exc, ProtocolParentSegmentError)
            and exc.error_code == "QUOTA_EXHAUSTED"
            and isinstance(exc.__cause__, ProtocolAgentCallError)
        ):
            raise exc.__cause__
        logger.warning(
            "protocol parent segmentation fell back to whole parent: %s",
            exc,
            extra={"official_code": item.official_code},
        )
        return None


def _collect_initial_semantic_response(
    source_input: ProtocolDeconstructionInput,
    *,
    prompt_template: str,
    transport: ProtocolAgentTransport,
    batch_size: int,
    batch_cache: ProtocolSemanticBatchCache | None = None,
    transport_factory: Callable[[], ProtocolAgentTransport] | None = None,
    batch_progress: Callable[[int, int, ProtocolSemanticDeconstructionCandidate], None]
    | None = None,
) -> tuple[ProtocolAgentResponse, str | None]:
    compact = _uses_compact_wire_contract(transport)
    segmentation_supported = _supports_parent_rule_segmentation(transport)
    expected_codes = [
        item.official_code
        for item in sorted(
            source_input.parent_rule_catalog.items,
            key=lambda item: item.position,
        )
        if item.official_code is not None
    ]
    batches = _plan_semantic_rule_batches(
        source_input,
        prompt_template=prompt_template,
        batch_size=batch_size,
        compact=compact,
    )
    if len(batches) <= 1:
        rule_codes = batches[0] if batches else expected_codes
        initial_prompt = build_protocol_deconstruction_prompt(
            source_input,
            prompt_template=prompt_template,
            requested_rule_codes=(rule_codes if batches else None),
            batch_number=1 if compact else None,
            batch_total=1 if compact else None,
            compact=compact,
            scoped_source=True,
        )
        segmented = (
            _try_collect_parent_segments(
                source_input,
                prompt_template=prompt_template,
                parent_prompt=initial_prompt,
                rule_codes=rule_codes,
                transport_factory=transport_factory,
                batch_cache=batch_cache,
                candidate_id=None,
                agent_call_id=None,
            )
            if segmentation_supported
            else None
        )
        if segmented is not None:
            return ProtocolAgentResponse(
                session_id="protocol-parent-segments-"
                + _sha256(segmented.model_dump_json())[:16],
                text=segmented.model_dump_json(),
            ), None
        _configure_transport_output_scope(
            transport, source_input, rule_codes
        )
        response = transport.start(
            prompt=initial_prompt,
            output_kind="semantic_candidate",
        )
        if not compact:
            return response, None
        try:
            candidate, _batch_id = _parse_wire_semantic_candidate(
                json.loads(response.text),
                expected_batch_id="1/1",
            )
        except Exception:
            # Let the runner issue its normal bounded structural diagnostic.
            return response, None
        try:
            _validate_semantic_batch(
                candidate,
                expected_codes=rule_codes,
                expected_candidate_id=None,
                source_input=source_input,
            )
            return (
                response.model_copy(update={"text": candidate.model_dump_json()}),
                None,
            )
        except Exception as exc:
            return response, f"单批 wire 语义结果无法闭合冻结父规则：{exc}"

    _configure_transport_output_scope(transport, source_input, batches[0])
    first_prompt = build_protocol_deconstruction_prompt(
        source_input,
        prompt_template=prompt_template,
        requested_rule_codes=batches[0],
        batch_number=1 if compact else None,
        batch_total=len(batches) if compact else None,
        compact=compact,
        scoped_source=True,
    )
    current_cache_key = (
        _semantic_batch_cache_key(
            transport,
            prompt=first_prompt,
            batch_id=f"1/{len(batches)}",
            rule_codes=batches[0],
            source_input=source_input,
            prompt_template=prompt_template,
        )
    )
    first_cached_text = (
        batch_cache.load(current_cache_key)
        if batch_cache is not None and current_cache_key is not None
        else None
    )
    current_cached = (
        _validate_cached_semantic_batch(
            first_cached_text,
            source_input=source_input,
            rule_codes=batches[0],
            candidate_id=None,
            agent_call_id=None,
        )
        if first_cached_text is not None
        else None
    )
    if current_cached is None and segmentation_supported:
        current_cached = _try_collect_parent_segments(
            source_input,
            prompt_template=prompt_template,
            parent_prompt=first_prompt,
            rule_codes=batches[0],
            transport_factory=transport_factory,
            batch_cache=batch_cache,
            candidate_id=None,
            agent_call_id=None,
        )
    transport_started = current_cached is None
    if transport_started:
        response = transport.start(
            prompt=first_prompt,
            output_kind="semantic_candidate",
        )
        session_id: str | None = response.session_id
    else:
        response = ProtocolAgentResponse(
            session_id="protocol-semantic-cache",
            text=current_cached.model_dump_json(),
        )
        session_id = None
    collected: list[ProtocolSemanticDeconstructionCandidate] = []
    candidate_id: str | None = None
    agent_call_id: str | None = None
    for batch_index, rule_codes in enumerate(batches, start=1):
        batch_candidate = current_cached
        problem = ""
        batch_id = f"{batch_index}/{len(batches)}"
        for schema_attempt in range(2 if batch_candidate is None else 0):
            try:
                batch_candidate = _parse_semantic_candidate(
                    response.text,
                    compact=compact,
                    expected_batch_id=batch_id if compact else None,
                )
                _validate_semantic_batch(
                    batch_candidate,
                    expected_codes=rule_codes,
                    expected_candidate_id=candidate_id,
                    expected_agent_call_id=agent_call_id,
                    source_input=source_input,
                )
            except Exception as exc:
                problem = str(exc)
                if schema_attempt == 1:
                    return response, (
                        f"第 {batch_index}/{len(batches)} 批经过一次结构修复后仍无法合并："
                        + problem
                    )
                try:
                    response = transport.continue_session(
                        session_id=session_id,
                        prompt=_batch_schema_repair_prompt(
                            rule_codes,
                            candidate_id=candidate_id,
                            agent_call_id=agent_call_id,
                            batch_id=batch_id,
                            problem=problem,
                            compact=compact,
                            allowed_source_span_ids=_batch_source_span_ids(
                                source_input, rule_codes
                            ),
                        ),
                        output_kind="semantic_candidate",
                    )
                except ProtocolAgentCallError:
                    raise
                except Exception as exc:
                    return response, (
                        f"第 {batch_index}/{len(batches)} 批结构修复调用未完成：{exc}"
                    )
                if response.session_id != session_id:
                    return response, "分批结构修复切换了会话，已停止"
                continue
            break
        if batch_candidate is None:
            return response, problem or "本批没有可合并的语义结果"
        if (
            current_cached is None
            and batch_cache is not None
            and current_cache_key is not None
        ):
            batch_cache.store(current_cache_key, batch_candidate.model_dump_json())
        if candidate_id is None:
            candidate_id = batch_candidate.candidate_id
        if agent_call_id is None:
            agent_call_id = batch_candidate.created_by_agent_call_id
        collected.append(batch_candidate)
        if batch_progress is not None:
            # 逐批进度只做宿主侧持久化/预览；上报失败不回滚已验证批次，
            # 也不得中断生成（证据仍在批缓存与最终草稿中）。
            try:
                batch_progress(
                    batch_index,
                    len(batches),
                    _merge_semantic_batches(list(collected)),
                )
            except Exception:  # noqa: BLE001 - 进度上报不得破坏生成本体
                logger.warning(
                    "方案语义批次 %s/%s 的进度上报失败，生成继续。",
                    batch_index,
                    len(batches),
                    exc_info=True,
                )
                batch_progress = None
        if batch_index == len(batches):
            break
        next_rule_codes = batches[batch_index]
        _configure_transport_output_scope(transport, source_input, next_rule_codes)
        next_prompt = _next_batch_prompt(
            next_rule_codes,
            batch_number=batch_index + 1,
            batch_total=len(batches),
            candidate_id=candidate_id,
            agent_call_id=agent_call_id,
            source_input=source_input,
            compact=compact,
            scoped_source=True,
        )
        current_cache_key = (
            _semantic_batch_cache_key(
                transport,
                prompt=next_prompt,
                batch_id=f"{batch_index + 1}/{len(batches)}",
                rule_codes=next_rule_codes,
                source_input=source_input,
                prompt_template=prompt_template,
            )
        )
        cached_text = (
            batch_cache.load(current_cache_key)
            if batch_cache is not None and current_cache_key is not None
            else None
        )
        current_cached = (
            _validate_cached_semantic_batch(
                cached_text,
                source_input=source_input,
                rule_codes=next_rule_codes,
                candidate_id=candidate_id,
                agent_call_id=agent_call_id,
            )
            if cached_text is not None
            else None
        )
        if current_cached is None and segmentation_supported:
            current_cached = _try_collect_parent_segments(
                source_input,
                prompt_template=prompt_template,
                parent_prompt=next_prompt,
                rule_codes=next_rule_codes,
                transport_factory=transport_factory,
                batch_cache=batch_cache,
                candidate_id=candidate_id,
                agent_call_id=agent_call_id,
            )
        if current_cached is not None:
            response = ProtocolAgentResponse(
                session_id=session_id or "protocol-semantic-cache",
                text=current_cached.model_dump_json(),
            )
            continue
        try:
            if not transport_started:
                response = transport.start(
                    prompt=next_prompt,
                    output_kind="semantic_candidate",
                )
                session_id = response.session_id
                transport_started = True
            else:
                assert session_id is not None
                _compact_transport_history(
                    transport,
                    session_id,
                    context=(
                        "已完成方案解构批次 "
                        f"{batch_id}；candidate_id={candidate_id!r}。"
                        "只保留冻结上下文和下一批明确身份，"
                        "不要复述上一批原文或输出。"
                    ),
                )
                response = transport.continue_session(
                    session_id=session_id,
                    prompt=next_prompt,
                    output_kind="semantic_candidate",
                )
        except ProtocolAgentCallError:
            raise
        except Exception as exc:
            return response, (
                f"第 {batch_index + 1}/{len(batches)} 批调用未完成：{exc}"
            )
        if session_id is None or response.session_id != session_id:
            return response, "分批语义解构切换了会话，已停止"

    merged = _merge_semantic_batches(
        collected,
        expected_codes=expected_codes,
        expected_candidate_id=candidate_id,
        source_input=source_input,
    )
    resolved_session_id = session_id or (
        "protocol-semantic-cache-" + _sha256(merged.model_dump_json())[:16]
    )
    if session_id is None:
        restore = getattr(transport, "restore_history", None)
        if callable(restore):
            restore(
                session_id=resolved_session_id,
                messages=[
                    {
                        "role": "user",
                        "content": "已从本任务验证批次恢复方案语义草稿。",
                    },
                    {"role": "assistant", "content": merged.model_dump_json()},
                ],
            )
    return ProtocolAgentResponse(
        session_id=resolved_session_id,
        text=merged.model_dump_json(),
    ), None


class ProtocolDeconstructorRunner:
    """Run bounded structural retries and isolated parent-rule repairs."""

    MAX_SCHEMA_REPAIRS = 2
    MAX_LOCAL_SCHEMA_REPAIRS = 1
    # Real mixed-phase protocols have needed fourteen isolated parent repairs
    # after a structurally valid first draft. The runtime also grants at least
    # one turn per frozen parent so fair rotation cannot starve a late rule.
    MAX_SEMANTIC_REPAIRS = 16
    MAX_RULES_PER_REPAIR = 3
    INITIAL_RULE_BATCH_SIZE = 3

    def __init__(
        self,
        gate: ProtocolDeconstructionGate | None = None,
        *,
        max_semantic_repairs: int | None = None,
    ):
        if max_semantic_repairs is not None and max_semantic_repairs < 0:
            raise ValueError("语义修订次数不能为负数")
        self._gate = gate or ProtocolDeconstructionGate()
        self._max_semantic_repairs = max_semantic_repairs

    def run(
        self,
        source_input: ProtocolDeconstructionInput,
        *,
        prompt_version: PromptVersion,
        prompt_template: str,
        transport: ProtocolAgentTransport,
        source_spans: Mapping[str, ProtocolSourceSpan],
        interpretation_conflicts: Sequence[InterpretationConflict] = (),
        batch_cache: ProtocolSemanticBatchCache | None = None,
        transport_factory: Callable[[], ProtocolAgentTransport] | None = None,
        batch_progress: Callable[[int, int, ProtocolSemanticDeconstructionCandidate], None]
        | None = None,
    ) -> ProtocolDeconstructionRunResult:
        if prompt_version.node != AgentNode.PROTOCOL_DECONSTRUCTOR:
            raise ValueError("提示词版本不属于方案解构节点")
        if prompt_version.template_sha256 != protocol_prompt_template_sha256(
            prompt_template
        ):
            raise ValueError("提示词正文与已登记版本哈希不一致")

        try:
            response, collection_error = _collect_initial_semantic_response(
                source_input,
                prompt_template=prompt_template,
                transport=transport,
                batch_size=self.INITIAL_RULE_BATCH_SIZE,
                batch_cache=batch_cache,
                transport_factory=transport_factory,
                batch_progress=batch_progress,
            )
        except Exception as exc:
            session_id = getattr(exc, "session_id", "protocol-call-unavailable")
            issue = (
                _call_issue(exc) if isinstance(exc, ProtocolAgentCallError)
                else _format_issue(f"方案解构调用未完成：{exc}")
            )
            return ProtocolDeconstructionRunResult(
                status="需要核对",
                same_session_id=session_id,
                attempts=[
                    ProtocolDeconstructionAttempt(
                        attempt=1,
                        session_id=session_id,
                        raw_output_sha256=_sha256(str(exc)),
                        outcome="会话异常",
                        issues=[issue],
                    )
                ],
            )
        session_id = response.session_id
        compact = _uses_compact_wire_contract(transport)
        attempts: list[ProtocolDeconstructionAttempt] = []
        final_draft: ProtocolDeconstructionDraft | None = None
        final_gate: ProtocolDeconstructionGateResult | None = None
        current_candidate: ProtocolSemanticDeconstructionCandidate | None = None
        replacement_rule_codes: list[str] = []
        semantic_repair_counts: dict[str, int] = {}

        if collection_error is not None:
            issue = _format_issue(collection_error)
            return ProtocolDeconstructionRunResult(
                status="需要核对",
                same_session_id=session_id,
                attempts=[
                    ProtocolDeconstructionAttempt(
                        attempt=1,
                        session_id=session_id,
                        raw_output_sha256=_sha256(response.text),
                        outcome="输出格式无效",
                        issues=[issue],
                    )
                ],
            )

        attempt_number = 0
        schema_repairs = 0
        semantic_repairs = 0
        local_schema_repairs = 0
        semantic_repair_limit = (
            self._max_semantic_repairs
            if self._max_semantic_repairs is not None
            else max(
                self.MAX_SEMANTIC_REPAIRS,
                len(source_input.parent_rule_catalog.items),
            )
        )
        while True:
            attempt_number += 1
            raw_hash = _sha256(response.text)
            candidate_for_attempt: ProtocolSemanticDeconstructionCandidate | None = None
            parsed_response = False
            repair_batch_id = (
                _repair_batch_id(replacement_rule_codes)
                if compact and current_candidate is not None and replacement_rule_codes
                else None
            )
            try:
                if current_candidate is not None and replacement_rule_codes:
                    repair = _parse_semantic_repair(
                        response.text,
                        compact=compact,
                        expected_batch_id=repair_batch_id,
                    )
                    if (
                        current_candidate.candidate_id.startswith(
                            "parent-segment-candidate:"
                        )
                        and repair.candidate_id != current_candidate.candidate_id
                    ):
                        repair = repair.model_copy(
                            update={"candidate_id": current_candidate.candidate_id}
                        )
                    _validate_semantic_repair(
                        repair,
                        expected_codes=replacement_rule_codes,
                        expected_candidate_id=current_candidate.candidate_id,
                        expected_batch_id=repair_batch_id,
                        source_input=source_input,
                    )
                    candidate_for_attempt = _apply_semantic_repair(
                        current_candidate,
                        repair,
                        expected_codes=replacement_rule_codes,
                    )
                    draft = _hydrate_semantic_candidate(
                        source_input, candidate_for_attempt
                    )
                else:
                    payload = json.loads(response.text)
                    if "candidate_id" in payload:
                        if compact and "batch_id" in payload:
                            # Any explicit wire identity must be validated as
                            # wire; never fall back to Pydantic's extra-field
                            # handling and silently discard a wrong batch ID.
                            candidate_for_attempt = _parse_semantic_candidate(
                                response.text,
                                compact=True,
                                expected_batch_id="1/1",
                            )
                            _validate_semantic_batch(
                                candidate_for_attempt,
                                expected_codes=[
                                    item.official_code
                                    for item in sorted(
                                        source_input.parent_rule_catalog.items,
                                        key=lambda item: item.position,
                                    )
                                    if item.official_code is not None
                                ],
                                expected_candidate_id=None,
                                source_input=source_input,
                            )
                        else:
                            # A multi-batch collection is returned as the
                            # hydrated domain candidate; only that internal
                            # handoff is allowed to omit the wire batch ID.
                            candidate_for_attempt = _parse_semantic_candidate(
                                response.text,
                                compact=False,
                            )
                        draft = _hydrate_semantic_candidate(
                            source_input, candidate_for_attempt
                        )
                    else:
                        draft = _parse_protocol_draft(response.text, source_input)
            except Exception as exc:
                issues = [_format_issue(str(exc))]
                attempts.append(
                    ProtocolDeconstructionAttempt(
                        attempt=attempt_number,
                        session_id=session_id,
                        raw_output_sha256=raw_hash,
                        outcome="输出格式无效",
                        issues=issues,
                    )
                )
            else:
                parsed_response = True
                gate_result = self._gate.evaluate(
                    source_input,
                    draft,
                    source_spans=source_spans,
                    interpretation_conflicts=interpretation_conflicts,
                )
                issues = [issue for check in gate_result.checks for issue in check.issues]
                if (
                    current_candidate is not None
                    and candidate_for_attempt is not None
                    and replacement_rule_codes
                    and final_draft is not None
                    and final_gate is not None
                ):
                    previous_issues = [
                        issue for check in final_gate.checks for issue in check.issues
                    ]
                    regressing_codes = regressing_rule_codes(
                        final_draft,
                        previous_issues,
                        draft,
                        issues,
                        replacement_rule_codes,
                    )
                    if regressing_codes:
                        candidate_for_attempt = _restore_candidate_rules(
                            candidate_for_attempt,
                            current_candidate,
                            regressing_codes,
                        )
                        draft = _hydrate_semantic_candidate(
                            source_input, candidate_for_attempt
                        )
                        gate_result = self._gate.evaluate(
                            source_input,
                            draft,
                            source_spans=source_spans,
                            interpretation_conflicts=interpretation_conflicts,
                        )
                        issues = [
                            issue
                            for check in gate_result.checks
                            for issue in check.issues
                        ]
                final_draft = draft
                final_gate = gate_result
                if candidate_for_attempt is not None:
                    current_candidate = candidate_for_attempt
                    replacement_rule_codes = _select_repair_rule_codes(
                        draft,
                        issues,
                        semantic_repair_counts,
                        limit=self.MAX_RULES_PER_REPAIR,
                    )
                attempts.append(
                    ProtocolDeconstructionAttempt(
                        attempt=attempt_number,
                        session_id=session_id,
                        raw_output_sha256=raw_hash,
                        outcome=(
                            "通过完整性检查"
                            if gate_result.publishable
                            else "需要定向修正"
                        ),
                        draft_id=draft.draft_id,
                        issues=issues,
                    )
                )
                if gate_result.publishable:
                    return ProtocolDeconstructionRunResult(
                        status="可以进入审阅",
                        same_session_id=session_id,
                        attempts=attempts,
                        final_draft=draft,
                        final_gate_result=gate_result,
                    )

            if not parsed_response and current_candidate is not None:
                if local_schema_repairs >= self.MAX_LOCAL_SCHEMA_REPAIRS:
                    break
                local_schema_repairs += 1
                repair_issues = issues
            elif current_candidate is None:
                if schema_repairs >= self.MAX_SCHEMA_REPAIRS:
                    break
                schema_repairs += 1
                repair_issues = issues
            else:
                local_schema_repairs = 0
                if (
                    semantic_repairs >= semantic_repair_limit
                    or not replacement_rule_codes
                ):
                    break
                semantic_repairs += 1
                for code in replacement_rule_codes:
                    semantic_repair_counts[code] = (
                        semantic_repair_counts.get(code, 0) + 1
                    )
                repair_issues = _repair_issues_for_rules(
                    draft,
                    issues,
                    replacement_rule_codes,
                )
            try:
                output_kind: ProtocolOutputKind = (
                    "semantic_rule_repair"
                    if current_candidate is not None and replacement_rule_codes
                    else "semantic_candidate"
                )
                repair_prompt = _repair_prompt(
                    repair_issues,
                    attempt=attempt_number,
                    parsed_draft_available=current_candidate is not None,
                    replacement_rule_codes=replacement_rule_codes,
                    repair_batch_id=repair_batch_id,
                    compact=compact,
                    candidate=current_candidate,
                    source_input=source_input,
                    include_frozen_context=bool(getattr(
                        transport, "supports_bounded_batch_context", False
                    )),
                )
                _configure_transport_output_scope(
                    transport,
                    source_input,
                    replacement_rule_codes or [
                        item.official_code
                        for item in source_input.parent_rule_catalog.items
                        if item.official_code is not None
                    ],
                )
                if current_candidate is not None:
                    _compact_transport_history(
                        transport,
                        session_id,
                        context=(
                            "已完成冻结批次语义候选；"
                            f"candidate_id={current_candidate.candidate_id!r}；"
                            f"本次定向修订父规则={replacement_rule_codes}。"
                            "仅依据后续修订提示和其中提供的目标规则/原文返回。"
                        ),
                    )
                restart_from_checkpoint = session_id.startswith(
                    "protocol-parent-segments-"
                ) or session_id == "protocol-semantic-cache"
                if restart_from_checkpoint:
                    response = transport.start(
                        prompt=repair_prompt,
                        output_kind=output_kind,
                    )
                    session_id = response.session_id
                else:
                    response = transport.continue_session(
                        session_id=session_id,
                        prompt=repair_prompt,
                        output_kind=output_kind,
                    )
            except Exception as exc:
                attempts.append(
                    ProtocolDeconstructionAttempt(
                        attempt=attempt_number + 1,
                        session_id=getattr(exc, "session_id", session_id),
                        raw_output_sha256=_sha256(str(exc)),
                        outcome="会话异常",
                        issues=[
                            _call_issue(exc) if isinstance(exc, ProtocolAgentCallError)
                            else _format_issue(f"定向修正调用未完成：{exc}")
                        ],
                    )
                )
                break
            if response.session_id != session_id:
                attempts.append(
                    ProtocolDeconstructionAttempt(
                        attempt=attempt_number + 1,
                        session_id=response.session_id,
                        raw_output_sha256=_sha256(response.text),
                        outcome="会话异常",
                        issues=[
                            _format_issue(
                                "定向修正返回了新的会话，已停止，避免丢失原上下文。"
                            )
                        ],
                    )
                )
                break

        return ProtocolDeconstructionRunResult(
            status="需要核对",
            same_session_id=session_id,
            attempts=attempts,
            final_draft=final_draft,
            final_gate_result=final_gate,
        )
