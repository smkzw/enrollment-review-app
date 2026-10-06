"""Source-bound question purpose, not proof that patient records were read."""

from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel


class RecordSemantics(ContractModel):
    target_kind: Literal["event_history", "other", "unresolved"]
    record_obligation: Literal["required", "not_required_by_source", "unresolved"]
    proposition_direction: Literal["event_present", "event_absent", "unresolved"]
    source_excerpts: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_source(self):
        if any(not item.strip() for item in self.source_excerpts):
            raise ValueError("记录用途须保留非空逐字来源")
        if len(self.source_excerpts) != len(set(self.source_excerpts)):
            raise ValueError("记录用途不能重复来源片段")
        if self.target_kind != "event_history" and self.proposition_direction != "unresolved":
            raise ValueError("非既往事件条件不能声明事件发生方向")
        return self


RECORD_SEMANTICS_GUIDANCE = (
    "record_semantics只说明条件询问对象与方案记录义务，不声明资料齐全或患者情况。"
    "target_kind区分既往事件/病史event_history、其他other、尚未核清unresolved；"
    "record_obligation独立区分required、not_required_by_source、unresolved。既往事件也可能"
    "要求指定记录，不能把两者当互斥类别。只有核过父级限定、相关章节与资料要求后才声明"
    "not_required_by_source，不能依据局部条文没写必须或当前事实数量推断。"
    "proposition_direction说明本条件自身命题（不含外层negated）的事件发生方向："
    "event_present、event_absent或unresolved；非既往事件填unresolved，不反转否定。"
    "source_excerpts逐字引用本条件source_locator内的依据，相关来源须一并保留；"
    "方案没有写未记录按未发生时不得伪造这句原文。该处理来自用户的工作稿政策，仍须另外核"
    "本次资料范围。未核清用途填null或unresolved，不根据疾病、药物名称或关键词猜分类。"
)
