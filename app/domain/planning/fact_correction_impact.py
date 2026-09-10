"""确定性人工事实修订影响范围规划（纯函数，无存储/模型）。

沿显式反向索引证明局部闭包：定位 → 资料版本、定位链接、事实引用、
FactRuleLink、资料期望、历史 Profile 类型化条目。任一必要链缺失、越过冻结
权威或无法双向闭合时，返回 ``scope_kind='node'`` 与中文回退原因。

禁止自由文本、相似度或模型猜测缩小范围。文档种子才会把同一资料版本下的
全部定位纳入起点；定位种子只记录所属资料版本，不把同文档无关定位算作相关。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.domain.contracts.fact_corrections import FactCorrectionImpactScope
from app.domain.contracts.facts import FactAuthority

__all__ = [
    "NODE_RECOMPUTE_MESSAGE",
    "SEED_KINDS",
    "FactCorrectionImpactEntity",
    "FactCorrectionImpactGraph",
    "FactCorrectionImpactIndexFlags",
    "FactCorrectionImpactSeed",
    "FactReplacementSignature",
    "LocatorDocumentBinding",
    "LocatorEntityLink",
    "ProfileRevisionIndex",
    "plan_fact_correction_impact",
]

NODE_RECOMPUTE_MESSAGE = "将重新整理本审核节点全部事实"

SEED_KINDS = frozenset({"locator", "document", "fact", "event", "exposure"})
SeedKind = Literal["locator", "document", "fact", "event", "exposure"]
EntityKind = Literal["fact", "event", "exposure", "conflict", "expectation"]


@dataclass(frozen=True)
class FactReplacementSignature:
    """拟发布事实的规则索引签名（fact_type + 资料要求身份），不含自由文本。"""

    fact_type: str
    supported_requirement_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.fact_type or self.fact_type.strip() == "":
            raise ValueError("替换签名的 fact_type 不得为空")
        if list(self.supported_requirement_ids) != sorted(set(self.supported_requirement_ids)):
            raise ValueError("替换签名的资料要求必须排序且不得重复")


@dataclass(frozen=True)
class FactCorrectionImpactSeed:
    """修订起点：定位、资料版本或已发布实体身份。"""

    kind: SeedKind
    ids: tuple[str, ...]
    replacement: FactReplacementSignature | None = None

    def __post_init__(self) -> None:
        if self.kind not in SEED_KINDS:
            raise ValueError(f"不支持的影响范围起点类型 {self.kind}")
        if any(not item or item.strip() == "" for item in self.ids):
            raise ValueError("影响范围起点 ID 不得为空")
        if list(self.ids) != sorted(set(self.ids)):
            raise ValueError("影响范围起点 ID 必须排序且不得重复")
        if self.replacement is not None and self.kind != "fact":
            raise ValueError("规则索引替换签名只适用于事实起点")


@dataclass(frozen=True)
class LocatorDocumentBinding:
    """定位到资料版本的显式反向索引。"""

    locator_id: str
    document_id: str
    processing_revision_id: str | None = None


@dataclass(frozen=True)
class LocatorEntityLink:
    """``fact_evidence_locator_links`` 定位反向索引的一行。"""

    locator_id: str
    entity_kind: EntityKind
    entity_id: str


@dataclass(frozen=True)
class FactCorrectionImpactEntity:
    """冻结权威下一条已发布实体的显式引用闭包。"""

    entity_kind: EntityKind
    entity_id: str
    authority: FactAuthority
    locator_ids: tuple[str, ...] = ()
    fact_ids: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()
    exposure_ids: tuple[str, ...] = ()
    fact_type: str | None = None
    supported_requirement_ids: tuple[str, ...] = ()
    requirement_id: str | None = None

    def __post_init__(self) -> None:
        for label, values in (
            ("定位", self.locator_ids),
            ("事实引用", self.fact_ids),
            ("事件引用", self.event_ids),
            ("暴露引用", self.exposure_ids),
            ("资料要求", self.supported_requirement_ids),
        ):
            if list(values) != sorted(set(values)):
                raise ValueError(f"{self.entity_kind} {self.entity_id} 的{label}必须排序且不得重复")


@dataclass(frozen=True)
class ProfileRevisionIndex:
    """历史 Profile revision 的类型化条目反向索引。"""

    revision_id: str
    authority: FactAuthority
    status: str
    item_refs: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if list(self.item_refs) != sorted(set(self.item_refs)):
            raise ValueError(f"Profile {self.revision_id} 条目反向索引必须排序且不得重复")


@dataclass(frozen=True)
class FactCorrectionImpactIndexFlags:
    """调用方是否提供了证明局部闭包所必需的全部反向索引。

    ``False`` 表示该链根本没有被装入，与“装入后为空集”不同；空集仍可证明闭包。
    """

    locator_documents: bool = True
    locator_entities: bool = True
    event_facts: bool = True
    exposure_facts: bool = True
    conflict_members: bool = True
    rule_links: bool = True
    expectations: bool = True
    profile_items: bool = True
    frozen_locators: bool = True
    requirement_templates: bool = True


@dataclass(frozen=True)
class FactCorrectionImpactGraph:
    """当前冻结权威下用于证明影响范围的显式反向索引快照。"""

    authority: FactAuthority
    frozen_locator_ids: tuple[str, ...]
    locator_documents: tuple[LocatorDocumentBinding, ...]
    locator_entities: tuple[LocatorEntityLink, ...]
    entities: tuple[FactCorrectionImpactEntity, ...]
    event_fact_links: tuple[tuple[str, str], ...] = ()
    exposure_fact_links: tuple[tuple[str, str], ...] = ()
    rule_link_ids_by_fact: tuple[tuple[str, tuple[str, ...]], ...] = ()
    requirement_expectation_ids: tuple[tuple[str, tuple[str, ...]], ...] = ()
    fact_type_expectation_ids: tuple[tuple[str, tuple[str, ...]], ...] = ()
    profile_revisions: tuple[ProfileRevisionIndex, ...] = ()
    indexes: FactCorrectionImpactIndexFlags = FactCorrectionImpactIndexFlags()

    def __post_init__(self) -> None:
        if list(self.frozen_locator_ids) != sorted(set(self.frozen_locator_ids)):
            raise ValueError("冻结定位清单必须排序且不得重复")


def plan_fact_correction_impact(
    seed: FactCorrectionImpactSeed,
    graph: FactCorrectionImpactGraph,
) -> FactCorrectionImpactScope:
    """由显式反向索引证明局部闭包；无法证明时回退整个审核节点。"""

    missing = _missing_index_reason(graph.indexes)
    if missing is not None:
        return _node_scope(missing)
    if not seed.ids:
        return _node_scope("修订起点为空，无法证明局部闭包")

    try:
        indexes = _IndexView(graph)
    except ValueError as exc:
        return _node_scope(str(exc))

    integrity = _prove_index_integrity(indexes)
    if integrity is not None:
        return _node_scope(integrity)

    if seed.kind == "fact" and seed.replacement is None:
        return _node_scope("事实修订缺少规则索引替换签名，无法证明局部闭包")

    signature_gap = _replacement_signature_gap(seed, indexes)
    if signature_gap is not None:
        return _node_scope(signature_gap)

    collected = _expand(seed, indexes)
    if isinstance(collected, str):
        return _node_scope(collected)

    closure = _prove_local_closure(collected, indexes)
    if closure is not None:
        return _node_scope(closure)

    return FactCorrectionImpactScope(
        scope_kind="local",
        fallback_reason=None,
        affected_locator_ids=sorted(collected.locators),
        affected_document_ids=sorted(collected.documents),
        affected_fact_ids=sorted(collected.facts),
        affected_event_ids=sorted(collected.events),
        affected_exposure_ids=sorted(collected.exposures),
        affected_conflict_group_ids=sorted(collected.conflicts),
        affected_rule_link_ids=sorted(collected.rule_links),
        affected_expectation_ids=sorted(collected.expectations),
        affected_profile_revision_ids=sorted(collected.profiles),
    )


def _node_scope(detail: str) -> FactCorrectionImpactScope:
    reason = detail.strip()
    if NODE_RECOMPUTE_MESSAGE not in reason:
        reason = f"{NODE_RECOMPUTE_MESSAGE}：{reason}"
    return FactCorrectionImpactScope(scope_kind="node", fallback_reason=reason)


def _missing_index_reason(flags: FactCorrectionImpactIndexFlags) -> str | None:
    checks = (
        (flags.frozen_locators, "完整处理修订定位清单缺失或无法证明闭包"),
        (flags.locator_documents, "定位到资料版本的反向索引缺失或无法证明闭包"),
        (flags.locator_entities, "定位到实体的反向索引缺失或无法证明闭包"),
        (flags.event_facts, "事实引用缺少事件反向索引"),
        (flags.exposure_facts, "事实引用缺少暴露反向索引"),
        (flags.conflict_members, "冲突组成员引用无法闭合"),
        (flags.rule_links, "规则索引反向链缺失或无法证明闭包"),
        (flags.expectations, "资料期望反向索引缺失或无法证明闭包"),
        (flags.profile_items, "历史 Profile 未提供类型化条目反向索引"),
    )
    for present, reason in checks:
        if not present:
            return reason
    return None


class _IndexView:
    def __init__(self, graph: FactCorrectionImpactGraph) -> None:
        self.authority = graph.authority
        self.frozen_locators = frozenset(graph.frozen_locator_ids)
        self.locator_document = {
            item.locator_id: item.document_id for item in graph.locator_documents
        }
        if len(self.locator_document) != len(graph.locator_documents):
            raise ValueError("同一位置出现重复的资料版本反向索引")

        self.entities: dict[tuple[str, str], FactCorrectionImpactEntity] = {}
        for entity in graph.entities:
            key = (entity.entity_kind, entity.entity_id)
            if key in self.entities:
                raise ValueError(f"实体反向索引重复：{entity.entity_kind} {entity.entity_id}")
            self.entities[key] = entity

        self.locator_entities: dict[str, set[tuple[str, str]]] = {}
        for link in graph.locator_entities:
            self.locator_entities.setdefault(link.locator_id, set()).add(
                (link.entity_kind, link.entity_id)
            )

        self.events_by_fact: dict[str, set[str]] = {}
        for event_id, fact_id in graph.event_fact_links:
            self.events_by_fact.setdefault(fact_id, set()).add(event_id)

        self.exposures_by_fact: dict[str, set[str]] = {}
        for exposure_id, fact_id in graph.exposure_fact_links:
            self.exposures_by_fact.setdefault(fact_id, set()).add(exposure_id)

        self.rule_links_by_fact: dict[str, tuple[str, ...]] = {}
        for fact_id, link_ids in graph.rule_link_ids_by_fact:
            if fact_id in self.rule_links_by_fact:
                raise ValueError(f"规则索引反向链重复：事实 {fact_id}")
            if list(link_ids) != sorted(set(link_ids)):
                raise ValueError(f"事实 {fact_id} 的规则索引必须排序且不得重复")
            self.rule_links_by_fact[fact_id] = link_ids

        self.requirement_expectations = _unique_id_map(
            graph.requirement_expectation_ids, "资料要求期望反向索引"
        )
        self.fact_type_expectations = _unique_id_map(
            graph.fact_type_expectation_ids, "事实类型期望反向索引"
        )
        self.requirement_templates = graph.indexes.requirement_templates
        self.profiles = graph.profile_revisions
        self.documents_to_locators: dict[str, set[str]] = {}
        for locator_id, document_id in self.locator_document.items():
            self.documents_to_locators.setdefault(document_id, set()).add(locator_id)


def _unique_id_map(
    items: tuple[tuple[str, tuple[str, ...]], ...], label: str
) -> dict[str, tuple[str, ...]]:
    mapped: dict[str, tuple[str, ...]] = {}
    for key, values in items:
        if key in mapped:
            raise ValueError(f"{label}重复：{key}")
        if list(values) != sorted(set(values)):
            raise ValueError(f"{label} {key} 必须排序且不得重复")
        mapped[key] = values
    return mapped


@dataclass
class _Collected:
    locators: set[str]
    documents: set[str]
    facts: set[str]
    events: set[str]
    exposures: set[str]
    conflicts: set[str]
    expectations: set[str]
    rule_links: set[str]
    profiles: set[str]


def _prove_index_integrity(indexes: _IndexView) -> str | None:
    for entity in indexes.entities.values():
        if entity.authority != indexes.authority:
            return "受影响实体与当前审核节点权威不一致"
        if entity.entity_kind == "fact" and (
            entity.fact_type is None or entity.fact_type.strip() == ""
        ):
            return "事实缺少类型化 fact_type，无法证明局部闭包"
        if entity.entity_kind == "expectation" and (
            entity.fact_type is None
            or entity.fact_type.strip() == ""
            or entity.requirement_id is None
            or entity.requirement_id.strip() == ""
        ):
            return "资料期望缺少类型化 fact_type/requirement_id，无法证明局部闭包"
        declared = set(entity.locator_ids)
        reverse = {
            locator_id
            for locator_id, refs in indexes.locator_entities.items()
            if (entity.entity_kind, entity.entity_id) in refs
        }
        if declared != reverse:
            return "定位链接与实体声明不一致"
        unknown = declared - indexes.frozen_locators
        if unknown:
            return "定位不属于当前冻结的完整处理修订"
        if any(locator_id not in indexes.locator_document for locator_id in declared):
            return "定位到资料版本的反向索引缺失或无法证明闭包"

    for (kind, entity_id), entity in indexes.entities.items():
        if kind == "event":
            reverse = {
                fact_id
                for fact_id, event_ids in indexes.events_by_fact.items()
                if entity_id in event_ids
            }
            if set(entity.fact_ids) != reverse:
                return "事实引用缺少事件反向索引"
        elif kind == "exposure":
            reverse = {
                fact_id
                for fact_id, exposure_ids in indexes.exposures_by_fact.items()
                if entity_id in exposure_ids
            }
            if set(entity.fact_ids) != reverse:
                return "事实引用缺少暴露反向索引"
        elif kind == "conflict":
            if entity.fact_ids:
                expected_kind = "fact"
                members = entity.fact_ids
            elif entity.event_ids:
                expected_kind = "event"
                members = entity.event_ids
            else:
                expected_kind = "exposure"
                members = entity.exposure_ids
            for member_id in members:
                if (expected_kind, member_id) not in indexes.entities:
                    return "冲突组成员引用无法闭合"
        elif kind == "expectation":
            for fact_id in entity.fact_ids:
                if ("fact", fact_id) not in indexes.entities:
                    return "资料期望反向索引缺失或无法证明闭包"

    for fact_id, event_ids in indexes.events_by_fact.items():
        if ("fact", fact_id) not in indexes.entities:
            return "事实引用缺少事件反向索引"
        for event_id in event_ids:
            if ("event", event_id) not in indexes.entities:
                return "事实引用缺少事件反向索引"
    for fact_id, exposure_ids in indexes.exposures_by_fact.items():
        if ("fact", fact_id) not in indexes.entities:
            return "事实引用缺少暴露反向索引"
        for exposure_id in exposure_ids:
            if ("exposure", exposure_id) not in indexes.entities:
                return "事实引用缺少暴露反向索引"

    for fact_id in indexes.rule_links_by_fact:
        if ("fact", fact_id) not in indexes.entities:
            return "规则索引反向链缺失或无法证明闭包"

    known_sources = {
        (kind, entity_id) for (kind, entity_id) in indexes.entities
    }
    for profile in indexes.profiles:
        if profile.authority != indexes.authority:
            continue
        if profile.status in {"generating", "failed"}:
            if profile.item_refs:
                return "历史 Profile 未提供类型化条目反向索引"
            continue
        if profile.status not in {"succeeded", "stale"}:
            return "历史 Profile 未提供类型化条目反向索引"
        for kind, source_id in profile.item_refs:
            if (kind, source_id) not in known_sources:
                return "历史 Profile 未提供类型化条目反向索引"
    return None


def _needed_signature_expectations(
    seed: FactCorrectionImpactSeed, indexes: _IndexView
) -> set[str] | str | None:
    if seed.kind != "fact" or seed.replacement is None:
        return None
    old_types: set[str] = set()
    old_reqs: set[str] = set()
    for fact_id in seed.ids:
        entity = indexes.entities.get(("fact", fact_id))
        if entity is None:
            return "修订起点不在当前冻结证据闭包中"
        if entity.fact_type:
            old_types.add(entity.fact_type)
        old_reqs.update(entity.supported_requirement_ids)
    new_types = {seed.replacement.fact_type}
    new_reqs = set(seed.replacement.supported_requirement_ids)
    if old_types == new_types and old_reqs == new_reqs:
        return None
    if not indexes.requirement_templates:
        return "替换后的规则索引无法由模板/资料要求反向索引证明闭包"
    needed_types = old_types | new_types
    needed_reqs = old_reqs | new_reqs
    if any(item not in indexes.fact_type_expectations for item in needed_types):
        return "替换后的规则索引无法由模板/资料要求反向索引证明闭包"
    if any(item not in indexes.requirement_expectations for item in needed_reqs):
        return "替换后的规则索引无法由模板/资料要求反向索引证明闭包"
    extra: set[str] = set()
    for item in needed_types:
        extra.update(indexes.fact_type_expectations[item])
    for item in needed_reqs:
        extra.update(indexes.requirement_expectations[item])
    return extra


def _replacement_signature_gap(
    seed: FactCorrectionImpactSeed, indexes: _IndexView
) -> str | None:
    extra = _needed_signature_expectations(seed, indexes)
    if isinstance(extra, str):
        return extra
    return None


def _signature_expectations(
    seed: FactCorrectionImpactSeed, indexes: _IndexView
) -> set[str]:
    extra = _needed_signature_expectations(seed, indexes)
    if extra is None or isinstance(extra, str):
        return set()
    return extra


def _expand(seed: FactCorrectionImpactSeed, indexes: _IndexView) -> _Collected | str:
    collected = _Collected(
        locators=set(),
        documents=set(),
        facts=set(),
        events=set(),
        exposures=set(),
        conflicts=set(),
        expectations=set(),
        rule_links=set(),
        profiles=set(),
    )
    if seed.kind == "locator":
        unknown = [item for item in seed.ids if item not in indexes.locator_document]
        if unknown:
            return "修订起点不在当前冻结证据闭包中"
        collected.locators.update(seed.ids)
    elif seed.kind == "document":
        for document_id in seed.ids:
            locators = indexes.documents_to_locators.get(document_id)
            if not locators:
                return "修订起点不在当前冻结证据闭包中"
            collected.locators.update(locators)
            collected.documents.add(document_id)
    elif seed.kind == "fact":
        missing = [item for item in seed.ids if ("fact", item) not in indexes.entities]
        if missing:
            return "修订起点不在当前冻结证据闭包中"
        collected.facts.update(seed.ids)
    elif seed.kind == "event":
        missing = [item for item in seed.ids if ("event", item) not in indexes.entities]
        if missing:
            return "修订起点不在当前冻结证据闭包中"
        collected.events.update(seed.ids)
    elif seed.kind == "exposure":
        missing = [item for item in seed.ids if ("exposure", item) not in indexes.entities]
        if missing:
            return "修订起点不在当前冻结证据闭包中"
        collected.exposures.update(seed.ids)
    else:
        raise ValueError(f"不支持的影响范围起点类型 {seed.kind}")

    changed = True
    while changed:
        changed = False
        before = _snapshot(collected)

        for locator_id in list(collected.locators):
            document_id = indexes.locator_document.get(locator_id)
            if document_id is None:
                return "定位到资料版本的反向索引缺失或无法证明闭包"
            collected.documents.add(document_id)
            for kind, entity_id in indexes.locator_entities.get(locator_id, set()):
                _add_entity(collected, kind, entity_id)

        for fact_id in list(collected.facts):
            entity = indexes.entities.get(("fact", fact_id))
            if entity is None:
                return "修订起点不在当前冻结证据闭包中"
            collected.locators.update(entity.locator_ids)
            collected.events.update(indexes.events_by_fact.get(fact_id, set()))
            collected.exposures.update(indexes.exposures_by_fact.get(fact_id, set()))
            collected.rule_links.update(indexes.rule_links_by_fact.get(fact_id, ()))
            for other in indexes.entities.values():
                if other.entity_kind == "conflict" and fact_id in other.fact_ids:
                    collected.conflicts.add(other.entity_id)
                if other.entity_kind == "expectation" and fact_id in other.fact_ids:
                    collected.expectations.add(other.entity_id)
            collected.expectations.update(_signature_expectations(seed, indexes))

        for event_id in list(collected.events):
            entity = indexes.entities.get(("event", event_id))
            if entity is None:
                return "事实引用缺少事件反向索引"
            collected.locators.update(entity.locator_ids)
            collected.facts.update(entity.fact_ids)
            for other in indexes.entities.values():
                if other.entity_kind == "conflict" and event_id in other.event_ids:
                    collected.conflicts.add(other.entity_id)

        for exposure_id in list(collected.exposures):
            entity = indexes.entities.get(("exposure", exposure_id))
            if entity is None:
                return "事实引用缺少暴露反向索引"
            collected.locators.update(entity.locator_ids)
            collected.facts.update(entity.fact_ids)
            for other in indexes.entities.values():
                if other.entity_kind == "conflict" and exposure_id in other.exposure_ids:
                    collected.conflicts.add(other.entity_id)

        for conflict_id in list(collected.conflicts):
            entity = indexes.entities.get(("conflict", conflict_id))
            if entity is None:
                return "冲突组成员引用无法闭合"
            collected.locators.update(entity.locator_ids)
            collected.facts.update(entity.fact_ids)
            collected.events.update(entity.event_ids)
            collected.exposures.update(entity.exposure_ids)

        for expectation_id in list(collected.expectations):
            entity = indexes.entities.get(("expectation", expectation_id))
            if entity is None:
                return "资料期望反向索引缺失或无法证明闭包"
            collected.locators.update(entity.locator_ids)
            collected.facts.update(entity.fact_ids)

        if _snapshot(collected) != before:
            changed = True

    for profile in indexes.profiles:
        if profile.authority != indexes.authority:
            continue
        if profile.status in {"generating", "failed"}:
            continue
        for kind, source_id in profile.item_refs:
            if _source_is_collected(collected, kind, source_id):
                collected.profiles.add(profile.revision_id)
                break
    return collected


def _add_entity(collected: _Collected, kind: str, entity_id: str) -> None:
    if kind == "fact":
        collected.facts.add(entity_id)
    elif kind == "event":
        collected.events.add(entity_id)
    elif kind == "exposure":
        collected.exposures.add(entity_id)
    elif kind == "conflict":
        collected.conflicts.add(entity_id)
    elif kind == "expectation":
        collected.expectations.add(entity_id)


def _source_is_collected(collected: _Collected, kind: str, source_id: str) -> bool:
    mapping = {
        "fact": collected.facts,
        "event": collected.events,
        "exposure": collected.exposures,
        "conflict": collected.conflicts,
        "expectation": collected.expectations,
    }
    bucket = mapping.get(kind)
    return bucket is not None and source_id in bucket


def _snapshot(collected: _Collected) -> tuple[tuple[str, ...], ...]:
    return (
        tuple(sorted(collected.locators)),
        tuple(sorted(collected.documents)),
        tuple(sorted(collected.facts)),
        tuple(sorted(collected.events)),
        tuple(sorted(collected.exposures)),
        tuple(sorted(collected.conflicts)),
        tuple(sorted(collected.expectations)),
        tuple(sorted(collected.rule_links)),
    )


def _prove_local_closure(collected: _Collected, indexes: _IndexView) -> str | None:
    if collected.locators - indexes.frozen_locators:
        return "定位不属于当前冻结的完整处理修订"
    if any(locator_id not in indexes.locator_document for locator_id in collected.locators):
        return "定位到资料版本的反向索引缺失或无法证明闭包"

    expected_documents = {
        indexes.locator_document[locator_id] for locator_id in collected.locators
    }
    if collected.documents != expected_documents:
        return "定位到资料版本的反向索引缺失或无法证明闭包"

    for locator_id in collected.locators:
        for kind, entity_id in indexes.locator_entities.get(locator_id, set()):
            if not _source_is_collected(collected, kind, entity_id):
                return "定位到实体的反向索引缺失或无法证明闭包"

    for fact_id in collected.facts:
        entity = indexes.entities[("fact", fact_id)]
        if not set(entity.locator_ids) <= collected.locators:
            return "定位链接与实体声明不一致"
        if not set(indexes.events_by_fact.get(fact_id, set())) <= collected.events:
            return "事实引用缺少事件反向索引"
        if not set(indexes.exposures_by_fact.get(fact_id, set())) <= collected.exposures:
            return "事实引用缺少暴露反向索引"
        if set(indexes.rule_links_by_fact.get(fact_id, ())) - collected.rule_links:
            return "规则索引反向链缺失或无法证明闭包"

    for event_id in collected.events:
        entity = indexes.entities[("event", event_id)]
        if not set(entity.fact_ids) <= collected.facts:
            return "事实引用缺少事件反向索引"
        if not set(entity.locator_ids) <= collected.locators:
            return "定位链接与实体声明不一致"
    for exposure_id in collected.exposures:
        entity = indexes.entities[("exposure", exposure_id)]
        if not set(entity.fact_ids) <= collected.facts:
            return "事实引用缺少暴露反向索引"
        if not set(entity.locator_ids) <= collected.locators:
            return "定位链接与实体声明不一致"
    for conflict_id in collected.conflicts:
        entity = indexes.entities[("conflict", conflict_id)]
        if not set(entity.fact_ids) <= collected.facts:
            return "冲突组成员引用无法闭合"
        if not set(entity.event_ids) <= collected.events:
            return "冲突组成员引用无法闭合"
        if not set(entity.exposure_ids) <= collected.exposures:
            return "冲突组成员引用无法闭合"
    for expectation_id in collected.expectations:
        entity = indexes.entities[("expectation", expectation_id)]
        if not set(entity.fact_ids) <= collected.facts:
            return "资料期望反向索引缺失或无法证明闭包"

    expected_profiles = set()
    for profile in indexes.profiles:
        if profile.authority != indexes.authority or profile.status in {"generating", "failed"}:
            continue
        if any(
            _source_is_collected(collected, kind, source_id)
            for kind, source_id in profile.item_refs
        ):
            expected_profiles.add(profile.revision_id)
    if collected.profiles != expected_profiles:
        return "历史 Profile 未提供类型化条目反向索引"
    return None
