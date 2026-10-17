"""Node-specific extraction targets from a reviewed, frozen rule package."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.contracts.enums import ReviewStage
from app.domain.contracts.rules import EvidenceRequirement, RuleSet
from app.domain.policies import STAGE_RANK
from app.domain.variables.dictionary import VariableDef, load_dictionary


@dataclass(frozen=True)
class ExtractionTargets:
    requirements: tuple[EvidenceRequirement, ...]
    variables: tuple[VariableDef, ...]


def unread_extraction_targets(previous: ExtractionTargets, current: ExtractionTargets) -> tuple[list[str], list[str]]:
    """A saved observation scope never proves newly requested or changed targets."""
    variables = {item.variable_id: item for item in previous.variables}
    requirements = {item.requirement_id: item for item in previous.requirements}
    return (sorted(item.variable_id for item in current.variables if variables.get(item.variable_id) != item),
            sorted(item.requirement_id for item in current.requirements if requirements.get(item.requirement_id) != item))


def build_extraction_targets(rule_set: RuleSet, stage: ReviewStage,
                             requirements: list[EvidenceRequirement]) -> ExtractionTargets:
    definitions = load_dictionary(rule_set.variable_definitions or ())
    reviews = {item.official_code: item for item in rule_set.review_records or ()}
    selected = []
    variable_ids = set()
    for item in sorted(requirements, key=lambda value: value.requirement_id):
        if STAGE_RANK[item.due_stage] > STAGE_RANK[stage]:
            continue
        review = reviews.get(item.procedure_catalog_item_id)
        if review is not None and review.note == "excluded":
            continue
        selected.append(item)
        if item.variable_id is not None:
            variable_ids.add(item.variable_id)
        if review is not None:
            variable_ids.update(review.result_variables)
    missing = variable_ids - definitions.keys()
    if missing:
        raise ValueError("已发布资料要求引用了未保存的数据项目")
    variable_ids.update(definitions[key].reference_ratio_of for key in tuple(variable_ids)
                        if definitions[key].reference_ratio_of is not None)
    return ExtractionTargets(tuple(selected), tuple(definitions[key] for key in sorted(variable_ids)))
