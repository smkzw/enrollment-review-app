"""Source statements for counting; neither eligibility judgments nor new facts."""
from typing import Literal

from pydantic import Field, StrictInt, model_serializer, model_validator

from app.domain.publication import canonical_hash
from .binding_qualification import BindingQualificationPairContext
from .common import ContractModel
from .frequency_period import FrequencySourceDate, FrequencyStatementPeriod
from .rules import OccurrenceWindow, WorkflowStage

FREQUENCY_EVIDENCE_VERSION = "frequency-evidence/v4"


class FrequencyEvidenceContext(ContractModel):
    version: Literal["frequency-evidence/v1", "frequency-evidence/v2", "frequency-evidence/v3", "frequency-evidence/v4"] = FREQUENCY_EVIDENCE_VERSION
    pair_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_job_id: str = Field(min_length=1)
    frozen_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    window: OccurrenceWindow
    members: list[BindingQualificationPairContext] = Field(min_length=1)
    workflow_stage: WorkflowStage

    @property
    def source_members(self):
        return self.members

    @model_validator(mode="after")
    def validate_context(self):
        ids = [item.pair_id for item in self.members]
        if ids != sorted(set(ids)):
            raise ValueError("频次原文配对须排序且不得重复")
        if any((item.identity_sha256, item.candidate_job_id, item.frozen_input_sha256)
               != (self.identity_sha256, self.candidate_job_id, self.frozen_input_sha256)
               for item in self.members):
            raise ValueError("频次核对不能混入其他要求或资料版本")
        for name in ("episode", "condition", "parent_source_context", "comparison_sha256",
                     "candidate_family", "identity_field"):
            if len({canonical_hash(getattr(item, name)) for item in self.members}) != 1:
                raise ValueError("频次核对的节点、条件与候选范围须一致")
        first = self.members[0]
        predicate = (first.condition.get("predicate") if first.candidate_family == "predicate"
                     else (first.condition.get("atom", {}).get("evaluation") or {}).get("predicate"))
        if not isinstance(predicate, dict) or predicate.get("occurrence_window") != self.window.model_dump(mode="json"):
            raise ValueError("计数期间必须来自本组冻结的方案要求")
        if (self.workflow_stage.workflow_stage_id != first.episode.get("workflow_stage_id")
                or self.workflow_stage.stage != first.episode.get("stage")):
            raise ValueError("频次核对须保留当前审核的正式节点说明")
        for key, field in (("fact_id", "fact"), ("locator_id", "locator")):
            seen = {}
            for member in self.members:
                identity, value = getattr(member, key), getattr(member, field)
                if identity in seen and seen[identity] != value:
                    raise ValueError("同一频次来源身份出现不同内容")
                seen[identity] = value
        if self.pair_id != canonical_hash(self.model_dump(mode="json", exclude={"pair_id"})):
            raise ValueError("频次核对身份与原文不一致")
        return self


class FrequencyQuote(ContractModel):
    pair_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    excerpt: str = Field(min_length=1)

    @model_validator(mode="after")
    def nonblank(self):
        if not self.excerpt.strip():
            raise ValueError("频次依据不能使用空白原文")
        return self


class FrequencyStatement(ContractModel):
    statement_index: StrictInt = Field(ge=0)
    source_pair_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    kind: Literal["stated_total", "individual_occurrence", "individual_day", "unresolved"]
    count: StrictInt | None = Field(default=None, ge=0)
    count_relation: Literal["eq", "gte", "gt", "lte", "lt", "unresolved"] | None = None
    count_unit: Literal["occurrences", "days", "unresolved"]
    count_excerpt: str | None = Field(default=None, min_length=1)
    period_excerpt: str | None = Field(default=None, min_length=1)
    period: FrequencyStatementPeriod | None = None
    occurrence_date: FrequencySourceDate | None = None
    explanation: str = Field(min_length=1)

    def source_key(self):
        key = (self.source_pair_id, self.kind, self.count, self.count_unit,
               self.count_excerpt, self.period_excerpt)
        if self.count_relation is not None:
            key = (*key, self.count_relation)
        if self.period is not None:
            key = (*key, canonical_hash(self.period.model_dump(mode="json")))
        return (*key, "occurrence_date", canonical_hash(self.occurrence_date.model_dump(mode="json"))) if self.occurrence_date is not None else key

    @model_serializer(mode="wrap")
    def preserve_old_period(self, handler):
        value = handler(self)
        if self.period is None:
            value.pop("period", None)
        if self.count_relation is None:
            value.pop("count_relation", None)
        if self.occurrence_date is None:
            value.pop("occurrence_date", None)
        return value

    @model_validator(mode="after")
    def require_original_count(self):
        if not self.explanation.strip():
            raise ValueError("频次核对须说明原文依据或具体疑问")
        if self.kind == "stated_total":
            if self.count is None or self.count_unit == "unresolved" or not self.count_excerpt:
                raise ValueError("明确总数须同时保留数值、单位及逐字原文")
        elif self.count is not None:
            raise ValueError("逐次记录或未决内容不能由模型补算次数")
        if self.kind != "stated_total" and self.count_relation is not None:
            raise ValueError("仅明确总数记载可保留次数上下限关系")
        if self.kind in {"individual_occurrence", "individual_day"} and not self.count_excerpt:
            raise ValueError("逐次发生须保留描述该次发生的原文，不得由汇总次数展开")
        if self.kind == "individual_day" and self.count_unit != "days":
            raise ValueError("单日记载只能用于发生天数，不能充作独立发作次数")
        if self.occurrence_date is not None and self.kind not in {"individual_occurrence", "individual_day"}:
            raise ValueError("逐次发生日期不能用于汇总计数或未决记载")
        if self.period is not None:
            if self.kind != "stated_total" or self.period_excerpt is None:
                raise ValueError("计数期间仅对应明确总数，并须保留期间原文")
            if any(quote not in self.period_excerpt for quote in self.period.source_quotes()):
                raise ValueError("日期、时长和锚点摘录须属于本条计数期间原文")
        for text in (self.count_excerpt, self.period_excerpt):
            if text is not None and not text.strip():
                raise ValueError("频次或期间摘录不得为空白")
        return self


class FrequencyRelationship(ContractModel):
    left_statement_index: StrictInt = Field(ge=0)
    right_statement_index: StrictInt = Field(ge=0)
    relation: Literal["same_occurrence", "distinct_occurrence"]
    quotes: list[FrequencyQuote] = Field(min_length=2)
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_relationship(self):
        if self.left_statement_index >= self.right_statement_index:
            raise ValueError("发生关系两端须不同并按身份排序")
        if not self.explanation.strip():
            raise ValueError("同次或异次须说明明确依据，不得仅凭记录条数推断")
        return self

    def local_key(self):
        return self.left_statement_index, self.right_statement_index, self.relation


class FrequencyEvidenceResult(ContractModel):
    pair_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewed_source_pair_ids: list[str]
    statements: list[FrequencyStatement]
    relationships: list[FrequencyRelationship]
    unresolved_notes: list[str]

    @model_validator(mode="after")
    def validate_result(self):
        ids = self.reviewed_source_pair_ids
        if ids != sorted(set(ids)) or {item.source_pair_id for item in self.statements} != set(ids):
            raise ValueError("频次原文须逐条核对且不得重复")
        if [item.statement_index for item in self.statements] != list(range(len(self.statements))):
            raise ValueError("同组声明须使用连续局部序号，不充作临床事实身份")
        if len({item.source_key() for item in self.statements}) != len(self.statements):
            raise ValueError("不能将同一摘录的相同声明重复列为多次发生")
        links = [item.local_key()[:2] for item in self.relationships]
        if len(links) != len(set(links)):
            raise ValueError("同一来源对应不得重复或同时声明同次与异次")
        individual = {item.statement_index for item in self.statements if item.kind == "individual_occurrence"}
        if any(not {left, right} <= individual for left, right in links):
            raise ValueError("汇总或未决原文不能充作逐次发生记录")
        for link in self.relationships:
            required = {self.statements[index].source_pair_id
                        for index in (link.left_statement_index, link.right_statement_index)}
            if {quote.pair_id for quote in link.quotes} != required:
                raise ValueError("发生关系须引用对应两条声明的原文")
        if any(not note.strip() for note in self.unresolved_notes):
            raise ValueError("频次疑问不得为空白")
        return self


class FrequencyEvidencePayload(ContractModel):
    results: list[FrequencyEvidenceResult]

    @model_validator(mode="after")
    def validate_unique(self):
        ids = [item.pair_id for item in self.results]
        if len(ids) != len(set(ids)):
            raise ValueError("同一频次要求不得重复返回")
        return self
