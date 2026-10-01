"""One bounded, source-linked cross-batch review of calculation definitions."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import Field, model_validator

from app.domain.contracts.common import ContractModel
from app.domain.publication import canonical_hash

SCOPE_REVIEW_VERSION = "phase5/control-definition-scope/v1"


class DefinitionScopeChoice(ContractModel):
    definition_key: str = Field(min_length=1)
    consumer_keys: list[str] = Field(default_factory=list)
    complete: bool
    unresolved_aspects: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_choice(self) -> "DefinitionScopeChoice":
        if len(self.consumer_keys) != len(set(self.consumer_keys)):
            raise ValueError("同一计算定义不能重复登记消费者")
        if self.complete and (not self.consumer_keys or self.unresolved_aspects):
            raise ValueError("无消费者或仍有疑问时不能声明影响范围已核清")
        return self


class DefinitionScopeReview(ContractModel):
    version: Literal[SCOPE_REVIEW_VERSION]
    inventory_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    items: list[DefinitionScopeChoice]

    @model_validator(mode="after")
    def validate_items(self) -> "DefinitionScopeReview":
        keys = [item.definition_key for item in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError("同一计算定义不能重复核对")
        return self


def frozen_scope_inventory(
    definitions: Sequence[Mapping[str, object]],
    consumers: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    body = {
        "definitions": sorted(definitions, key=lambda item: str(item["key"])),
        "consumers": sorted(consumers, key=lambda item: str(item["key"])),
    }
    return {**body, "sha256": canonical_hash(body)}


def build_definition_scope_prompt(inventory: Mapping[str, object]) -> str:
    return (
        "你是本系统内置方案 Agent 的全批次来源定义影响范围核对步骤。"
        "输入已包含本次冻结方案中全部已深审的计算定义，以及全部可选的官方子条件和补充要求原子。"
        "逐项核对定义由哪些条件实际消费；只能返回清单中的 key，不修改定义、条件或原文，"
        "不判断受试者入排，不按相同词语、数值、父编号猜测依赖。"
        "每个 definition_key 必须恰好返回一次。只有在列出的全部冻结候选中已核清影响范围、"
        "消费者非空且没有疑问时 complete 才能为 true；否则 complete=false 并写具体疑问。"
        "某项是否属于其他批次不影响选择；不得忽略跨章节或共用定义。"
        "这是有界核对，不得补造清单外的条件。只返回符合 Schema 的 JSON。\n"
        f"版本：{SCOPE_REVIEW_VERSION}\n"
        f"冻结清单：{json.dumps(inventory, ensure_ascii=False, sort_keys=True)}"
    )


def definition_scope_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_definition_scope_v1",
            "strict": True,
            "schema": DefinitionScopeReview.model_json_schema(),
        },
    }


def validate_definition_scope_review(
    review: DefinitionScopeReview,
    inventory: Mapping[str, object],
) -> None:
    if review.inventory_sha256 != inventory["sha256"]:
        raise ValueError("计算定义核对与冻结来源清单不一致")
    expected_definitions = {str(item["key"]) for item in inventory["definitions"]}
    available_consumers = {str(item["key"]) for item in inventory["consumers"]}
    if {item.definition_key for item in review.items} != expected_definitions:
        raise ValueError("计算定义核对未逐项覆盖冻结定义")
    for item in review.items:
        if not set(item.consumer_keys) <= available_consumers:
            raise ValueError("计算定义核对引用了未冻结的消费者")
        if not item.complete and not item.unresolved_aspects:
            raise ValueError("未核清的定义必须说明具体疑问")
