"""Source-object repair boundaries; no clinical interpretation or publication."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json


SOURCE_OBJECT_REPAIR_VERSION = "evidence-source-object-repair/v1"
CONTEXT_REPAIR_VERSION = "evidence-context-repair/v3"
PROSPECTIVE_REPAIR_VERSION = "evidence-prospective-repair/v2"
PROSPECTIVE_SCOPES = frozenset({"declared_intention", "prospective_or_conditional", "uncertain"})


class EvidenceSourceObjectError(ValueError):
    def __init__(self, message: str, candidate_refs: list[str], *, bounded_repair: bool):
        super().__init__(message)
        self.candidate_refs = tuple(candidate_refs)
        self.bounded_repair = bounded_repair


class EvidenceContextError(EvidenceSourceObjectError):
    """Invalid or undeclared source context, with an explicit repair target."""


class EvidenceDerivedSourceError(ValueError):
    """A derived candidate's cited source does not support its content."""

    def __init__(self, message: str, candidate_ref: str, *, collection: str):
        super().__init__(message)
        self.candidate_ref = candidate_ref
        self.collection = collection


class EvidenceNumericUnitError(ValueError):
    """A precisely identified numeric candidate lacks a declared unit."""

    def __init__(self, message: str, candidate_ref: str):
        super().__init__(message)
        self.candidate_ref = candidate_ref


class EvidenceProspectiveError(EvidenceSourceObjectError):
    """Explicit future/uncertain scope conflicts with actual-occurrence membership."""


class EvidenceDraftScopeError(EvidenceSourceObjectError):
    """Initial material cannot safely establish a bounded repair scope."""

    def __init__(self, message: str):
        super().__init__(message, [], bounded_repair=False)


def _unique_object(text: str) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("来源对象修复不能选择重复JSON字段")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("来源对象修复不能接受非JSON数值")

    value = json.loads(text, object_pairs_hook=unique, parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError("来源对象修复只接受一个完整对象")
    return value


def _canonical_sets(value, set_fields):
    if isinstance(value, list):
        return [_canonical_sets(item, set_fields) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: _canonical_sets(item, set_fields) for key, item in value.items()}
    for key in set_fields:
        items = result.get(key)
        if isinstance(items, list) and all(isinstance(item, (str, int))
                                          and not isinstance(item, bool) for item in items):
            result[key] = sorted(set(items), key=lambda item: (type(item).__name__, str(item)))
    return result


class EvidencePendingContextRetention:
    """Format recovery cannot remove an already proposed pending source relation."""

    def __init__(self, sources: dict[str, frozenset[str | None]]):
        self._sources = sources

    @classmethod
    def capture(cls, text: str):
        try:
            payload = _unique_object(text)
        except ValueError:
            return None
        facts = payload.get("fact_candidates")
        if not isinstance(facts, list):
            return None
        sources = {}
        refs = []
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            ref = fact.get("candidate_ref")
            refs.append(ref)
            basis = fact.get("assertion_basis")
            contexts = basis.get("contextual_qualifiers") if isinstance(basis, dict) else None
            cited = [item["source"] for item in contexts
                     if isinstance(item, dict) and item.get("source") is not None] if isinstance(contexts, list) else []
            if not cited:
                continue
            if not isinstance(ref, str) or not ref:
                raise EvidenceDraftScopeError("另处背景缺少唯一候选身份，不能安全补答")
            sources[ref] = frozenset(source.get("locator_id")
                if isinstance(source, dict) and isinstance(source.get("locator_id"), str) else None
                for source in cited)
        if not sources:
            return None
        if any(refs.count(ref) != 1 for ref in sources):
            raise EvidenceDraftScopeError("另处背景候选身份重复，不能安全补答")
        return cls(sources)

    def validate(self, text: str) -> None:
        proposal = self.capture(text)
        if proposal is None or any(ref not in proposal._sources
                or not ids <= proposal._sources[ref] for ref, ids in self._sources.items()):
            raise EvidenceDraftScopeError("补答不得删除或替换既有另处来源以解除归属待核状态")


class EvidenceSourceObjectRepair:
    """Freeze siblings and source fields before asking for a bounded proposal."""

    def __init__(self, previous_text: str, candidate_refs: tuple[str, ...], *, set_fields):
        self._previous = _unique_object(previous_text)
        facts = self._previous.get("fact_candidates")
        if not isinstance(facts, list) or not all(isinstance(item, dict) for item in facts):
            raise ValueError("来源对象修复缺少事实候选清单")
        refs = [item.get("candidate_ref") for item in facts]
        if (not all(isinstance(ref, str) for ref in refs) or len(refs) != len(set(refs))
                or not candidate_refs or not set(candidate_refs) <= set(refs)):
            raise ValueError("来源对象修复目标不属于唯一候选身份")
        self.candidate_refs = candidate_refs
        self._set_fields = frozenset(set_fields)
        self.precondition_sha256 = hashlib.sha256(previous_text.encode()).hexdigest()

    def instruction(self) -> str:
        return (
            "本次只修断言对象的逐字关系，不重新提取整页。目标候选："
            + json.dumps(self.candidate_refs, ensure_ascii=False)
            + "。候选身份、数量、顺序、其他候选、事件、暴露及未解决项必须保留；"
            "目标的原文、定位、时间、单位和支持要求不变。不得为逐字匹配删除布尔命题的动作或属性。"
            "若原文无法逐字表示完整正命题，可仅将该目标改为observed_state/affirmed，"
            "原值和规范值均为已有断言原句的完整文字、单位null；这是记录的表现，不是对象存在或符合方案。"
            "不能确定则保留失败，不删除条目或改写其他内容以通过校验。"
        )

    def validate(self, proposed_text: str) -> None:
        proposed = _unique_object(proposed_text)
        facts = proposed.get("fact_candidates")
        old_facts = self._previous["fact_candidates"]
        if not isinstance(facts, list) or len(facts) != len(old_facts):
            raise ValueError("来源对象修复不得删除或增加事实候选")
        frozen = deepcopy(proposed)
        for index, (old, new) in enumerate(zip(old_facts, facts, strict=True)):
            if not isinstance(new, dict) or new.get("candidate_ref") != old["candidate_ref"]:
                raise ValueError("来源对象修复不得重排或更换候选身份")
            if old["candidate_ref"] not in self.candidate_refs:
                continue
            old_basis, new_basis = old.get("assertion_basis"), new.get("assertion_basis")
            if not isinstance(old_basis, dict) or not isinstance(new_basis, dict):
                raise ValueError("来源对象修复不得删除断言依据")
            old_bool = isinstance(old.get("canonical_value"), bool) or isinstance(old.get("raw_value"), bool)
            new_bool = isinstance(new.get("canonical_value"), bool) or isinstance(new.get("raw_value"), bool)
            object_changed = (
                new.get("asserted_object") != old.get("asserted_object")
                or new_basis.get("asserted_object") != old_basis.get("asserted_object")
            )
            literal_record = (
                old_bool and not new_bool
                and new.get("assertion_scope") == "observed_state"
                and new.get("polarity") == "affirmed"
                and new.get("raw_value") == old_basis.get("assertion_text")
                and new.get("canonical_value") == old_basis.get("assertion_text")
                and new.get("unit") is None
            )
            if old_bool and object_changed and not literal_record:
                raise ValueError("布尔命题不能因逐字修复删除或替换原有动作、属性或对象")
            target = frozen["fact_candidates"][index]
            for key in ("asserted_object",):
                if key in old:
                    target[key] = old[key]
            target["assertion_basis"]["asserted_object"] = old_basis["asserted_object"]
            if literal_record:
                for key in ("assertion_scope", "polarity", "raw_value", "canonical_value", "unit"):
                    if key in old:
                        target[key] = old[key]
                    else:
                        target.pop(key, None)
        if _canonical_sets(frozen, self._set_fields) != _canonical_sets(self._previous, self._set_fields):
            raise ValueError("来源对象修复改动了未授权候选、来源或关联内容")


class EvidenceContextRepair(EvidenceSourceObjectRepair):
    def instruction(self) -> str:
        return (
            "本次只修目标断言的contextual_qualifiers，不重新提取整页。目标候选："
            + json.dumps(self.candidate_refs, ensure_ascii=False)
            + "。其他候选背景、对象、值、单位、原文、定位、时间、事件和疑问全部冻结。"
            "仅按目标已有原文声明真实限定关系；缺字段不能机械补空列表。"
            "原答已提出另处背景来源时，须保留另处来源及其待核状态；可以去重，"
            "不能清空、改成同句限定或换掉原有定位来解除归属疑问。"
            "没有背景时显式返回空列表；无法确定归属则保留失败，不借邻项标签。"
        )

    def validate(self, proposed_text: str) -> None:
        pending = EvidencePendingContextRetention.capture(json.dumps(self._previous, ensure_ascii=False))
        if pending is not None:
            pending.validate(proposed_text)
        proposed = _unique_object(proposed_text)
        facts = proposed.get("fact_candidates")
        old_facts = self._previous["fact_candidates"]
        if not isinstance(facts, list) or len(facts) != len(old_facts):
            raise ValueError("背景修复不得删除或增加事实候选")
        frozen = deepcopy(proposed)
        for index, (old, new) in enumerate(zip(old_facts, facts, strict=True)):
            if not isinstance(new, dict) or new.get("candidate_ref") != old["candidate_ref"]:
                raise ValueError("背景修复不得重排或更换候选身份")
            if old["candidate_ref"] not in self.candidate_refs:
                continue
            old_basis, new_basis = old.get("assertion_basis"), new.get("assertion_basis")
            if not isinstance(old_basis, dict) or not isinstance(new_basis, dict):
                raise ValueError("背景修复不得删除断言依据")
            target = frozen["fact_candidates"][index]["assertion_basis"]
            if "contextual_qualifiers" in old_basis:
                target["contextual_qualifiers"] = old_basis["contextual_qualifiers"]
            else:
                target.pop("contextual_qualifiers", None)
        if _canonical_sets(frozen, self._set_fields) != _canonical_sets(self._previous, self._set_fields):
            raise ValueError("背景修复改动了未授权候选、来源或关联内容")


class EvidenceProspectiveRepair(EvidenceSourceObjectRepair):
    """Only withdraw occurrence certainty, never promote or relabel an action."""

    def __init__(self, previous_text, candidate_refs, *, set_fields):
        super().__init__(previous_text, candidate_refs, set_fields=set_fields)
        targets = set(candidate_refs)
        for fact in self._previous["fact_candidates"]:
            if fact["candidate_ref"] not in targets:
                continue
            if fact.get("assertion_scope") not in PROSPECTIVE_SCOPES:
                raise ValueError("未来事项修复不能改变已发生事项的含义")
            basis = fact.get("assertion_basis")
            contexts = basis.get("contextual_qualifiers", []) if isinstance(basis, dict) else []
            if any(isinstance(item, dict) and item.get("source") is not None for item in contexts):
                raise ValueError("未来事项修复不能清除另处背景待核依据")
        for key in ("event_candidates", "exposure_candidates"):
            items = self._previous.get(key, [])
            if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
                raise ValueError("事件或暴露形状不足以锁定修复依赖")
            refs = [item.get("fact_candidate_refs") for item in items]
            if any(not isinstance(group, list)
                    or any(not isinstance(ref, str) or not ref.strip() for ref in group)
                    for group in refs):
                raise ValueError("事件或暴露引用形状不足以锁定修复依赖")
            if any(targets.intersection(group) for group in refs):
                raise ValueError("未来事项已被事件或暴露引用，须保留失败，不能自动撤回或替换支撑")

    def instruction(self):
        return ("本次仅撤回目标未来/未确认事项的发生断言，不重读整页："
            + json.dumps(self.candidate_refs, ensure_ascii=False)
            + "。目标原有assertion_scope、对象、身份、定位、日期及其他字段冻结；"
            "只可将polarity改为unknown，raw_value、canonical_value、unit、assertion_basis置null，"
            "supported_requirement_ids清空。从两个肯定药物分类清单移除目标引用，"
            "其他清单成员、兄弟、事件、暴露及疑问逐项不变。不得把未来使用改名为已完成宣教，"
            "不得改为否认、造用药或删除候选。宿主保留原答摘录与来源，未知不是未做。")

    def validate(self, proposed_text):
        proposed = _unique_object(proposed_text)
        facts = proposed.get("fact_candidates")
        old_facts = self._previous["fact_candidates"]
        if not isinstance(facts, list) or len(facts) != len(old_facts):
            raise ValueError("未来事项修复不得增删候选")
        frozen = deepcopy(proposed)
        targets = set(self.candidate_refs)
        changed_fields = ("polarity", "raw_value", "canonical_value", "unit", "assertion_basis", "supported_requirement_ids")
        for index, (old, new) in enumerate(zip(old_facts, facts, strict=True)):
            if not isinstance(new, dict) or new.get("candidate_ref") != old["candidate_ref"]:
                raise ValueError("未来事项修复不得换号或重排")
            if old["candidate_ref"] not in targets:
                continue
            if (new.get("polarity") != "unknown"
                    or any(new.get(key) is not None for key in changed_fields[1:5])
                    or new.get("supported_requirement_ids") != []):
                raise ValueError("未来事项只能保留未知，不得变成已完成或否认")
            for key in changed_fields:
                if key in old:
                    frozen["fact_candidates"][index][key] = old[key]
                else:
                    frozen["fact_candidates"][index].pop(key, None)
        for key in ("actual_exposure_fact_refs", "non_exposure_medication_fact_refs"):
            old_refs, new_refs = self._previous.get(key), proposed.get(key)
            if not isinstance(old_refs, list) or not isinstance(new_refs, list):
                raise ValueError("未来事项修复缺少显式药物分类清单")
            if sorted(new_refs) != sorted(ref for ref in old_refs if ref not in targets):
                raise ValueError("未来事项修复只能取消目标的肯定清单成员资格")
            frozen[key] = old_refs
        if _canonical_sets(frozen, self._set_fields) != _canonical_sets(self._previous, self._set_fields):
            raise ValueError("未来事项修复改动了未授权对象、兄弟、来源或依赖")

    def retained_questions(self):
        result = []
        for fact in self._previous["fact_candidates"]:
            if fact["candidate_ref"] not in self.candidate_refs:
                continue
            basis = fact.get("assertion_basis")
            excerpt = basis.get("assertion_text") if isinstance(basis, dict) else None
            result.append({"code": "occurrence_not_confirmed",
                "message": f"{fact.get('asserted_object')}尚不能作为已发生事实",
                "reason": (f"原始回答摘录（尚待核实）：{excerpt}。" if excerpt else "")
                    + "原答的发生状态与断言或分类不一致；保留原答及定位，不代表明确未做或实际使用。",
                "affected_locator_ids": fact.get("locator_ids", [])})
        return result
