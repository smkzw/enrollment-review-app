from __future__ import annotations

import json
import math
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VariableDef(BaseModel):
    # Keep the small dictionary independent of the contracts package's eager exports.
    model_config = ConfigDict(extra="forbid")
    variable_id: str = Field(pattern=r"^(?:[a-z][a-z0-9_]*|procedure:[A-Za-z0-9_.:-]+|drug_class:[a-z][a-z0-9_]*)$")
    label_zh: str = Field(min_length=1)
    value_type: Literal["number", "category", "boolean", "date", "exposure", "procedure"]
    canonical_unit: str | None = None
    unit_conversions: dict[str, float] = Field(default_factory=dict)
    aliases_zh: list[str] = Field(default_factory=list)
    plausible_range: tuple[float, float] | None = None
    domain: Literal["demographic", "lab", "vital", "score", "history", "medication", "procedure"]
    reference_ratio_of: str | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def validate_definition(self):
        if not self.label_zh.strip():
            raise ValueError("数据项目名称不能为空")
        if self.value_type == "number":
            if not self.canonical_unit or self.plausible_range is None:
                raise ValueError("数值项目须声明标准单位和合理范围")
            low, high = self.plausible_range
            if not all(math.isfinite(x) for x in (low, high)) or low >= high:
                raise ValueError("数值项目范围无效")
        elif self.unit_conversions or self.plausible_range is not None:
            raise ValueError("非数值项目不能声明数值换算或范围")
        if any(not key.strip() or not math.isfinite(value) or value <= 0
               for key, value in self.unit_conversions.items()):
            raise ValueError("单位换算须为明确的正倍率")
        if self.reference_ratio_of is not None and (
                self.value_type != "number" or self.canonical_unit != "×ULN"
                or self.reference_ratio_of == self.variable_id):
            raise ValueError("参考上限倍数须对应另一个明确的数值项目")
        return self

    def convert(self, value: int | float, unit: str) -> Decimal:
        """Only declared, dimension-preserving conversions; no guessed aliases."""
        normalize = lambda text: unicodedata.normalize("NFKC", text).replace(" ", "").replace("µ", "μ")
        if self.value_type != "number" or isinstance(value, bool) or not math.isfinite(value):
            raise ValueError("该项目不能进行数值换算")
        factors = {normalize(self.canonical_unit): 1.0}
        factors.update({normalize(key): factor for key, factor in self.unit_conversions.items()})
        if normalize(unit) not in factors:
            raise ValueError(f"{self.label_zh}的单位无法换算")
        return Decimal(str(value)) * Decimal(str(factors[normalize(unit)]))


def load_dictionary(project_variables=()) -> dict[str, VariableDef]:
    # JSON is a YAML 1.2 subset: keep these data files standard-library-readable.
    entries = json.loads(Path(__file__).with_name("core_variables.yaml").read_text())
    result = {}
    for item in [*(VariableDef.model_validate(value) for value in entries), *project_variables]:
        prior = result.get(item.variable_id)
        if prior is not None and prior != item:
            # The calculation capability is additive; historical clinical
            # labels, units and ranges must still match byte-for-byte in meaning.
            if (item.reference_ratio_of is not None
                    or prior.model_dump(exclude={"reference_ratio_of"}) != item.model_dump(exclude={"reference_ratio_of"})):
                raise ValueError("稳定数据项目身份不能对应不同定义")
            item = prior
        result[item.variable_id] = item
    for item in result.values():
        if item.reference_ratio_of is not None:
            operand = result.get(item.reference_ratio_of)
            if operand is None or operand.value_type != "number" or operand.reference_ratio_of is not None:
                raise ValueError("参考上限倍数必须引用已定义的原始数值，不能形成派生循环")
    return result


def load_drug_classes() -> dict[str, list[str]]:
    values = json.loads(Path(__file__).with_name("drug_classes.yaml").read_text())
    if any(not isinstance(key, str) or not isinstance(items, list)
           or any(not isinstance(item, str) or not item.strip() for item in items)
           for key, items in values.items()):
        raise ValueError("药物类别成员表无效")
    return values
