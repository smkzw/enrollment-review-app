"""Deterministic freezing of the official inclusion/exclusion parent catalog.

The catalog is built from :mod:`app.protocols.section_index`, not from the
legacy deconstructor or from an Agent's proposed rule tree.  The section index
keeps the complete source range for each Word parent list item; this module
selects one phase, validates the official numbering and structure-backed source range, and
then materializes the existing immutable ``FrozenProtocolCatalog`` contract.

Formal render locator coverage is intentionally enforced by the later
``source_coverage`` publication gate.  Freezing must retain a complete OOXML
structure range when rendering is degraded; it must not turn a recoverable
locator problem into deletion of an official catalog member.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import re
from typing import Any

from app.domain.contracts.enums import (
    CatalogItemKind,
    CatalogKind,
    PhaseScope,
    StudyPhase,
)
from app.domain.contracts.protocol_ingestion import (
    FrozenCatalogItem,
    FrozenProtocolCatalog,
    ProtocolSourceSpan,
    frozen_catalog_content_hash,
    optional_source_excerpts_for_spans,
)
from .section_index import (
    EligibilitySection,
    OfficialParentRuleRange,
    ProtocolSectionIndex,
    is_placeholder_label,
)


CATALOG_BUILDER_VERSION = "official-parent-rules/v1"
_DEFAULT_FROZEN_AT = datetime(1970, 1, 1, tzinfo=timezone.utc)
_DEFAULT_FROZEN_BY = CATALOG_BUILDER_VERSION
_OFFICIAL_CODE_RE = re.compile(r"^(?P<prefix>IN|EX)-(?P<number>[0-9]{1,3})$")


class CatalogValidationError(ValueError):
    """Stable rejection raised before an official catalog can be frozen."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


# The longer name is useful to callers that distinguish construction errors
# from validation errors; both names intentionally identify one boundary.
OfficialParentCatalogError = CatalogValidationError
OfficialParentCatalogBuildError = CatalogValidationError


def _short_digest(*parts: object) -> str:
    payload = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _allowed_scopes(selected_phase: StudyPhase) -> frozenset[PhaseScope]:
    if selected_phase == StudyPhase.PHASE_II:
        return frozenset({PhaseScope.PHASE_II, PhaseScope.SHARED})
    if selected_phase == StudyPhase.PHASE_III:
        return frozenset({PhaseScope.PHASE_III, PhaseScope.SHARED})
    if selected_phase == StudyPhase.SEAMLESS_II_III:
        return frozenset(
            {
                PhaseScope.PHASE_II,
                PhaseScope.PHASE_III,
                PhaseScope.SHARED,
                PhaseScope.SEAMLESS_CANDIDATE,
            }
        )
    raise CatalogValidationError(
        "phase_invalid",
        "官方父规则目录必须绑定 II 期、III 期或已确认的无缝期别",
    )


def _selected_scope(selected_phase: StudyPhase) -> PhaseScope:
    if selected_phase == StudyPhase.PHASE_II:
        return PhaseScope.PHASE_II
    if selected_phase == StudyPhase.PHASE_III:
        return PhaseScope.PHASE_III
    if selected_phase == StudyPhase.SEAMLESS_II_III:
        return PhaseScope.SEAMLESS_CANDIDATE
    raise CatalogValidationError(
        "phase_invalid",
        "官方父规则目录不能选择 OTHER 期别",
    )


def _span_maps(
    source_spans: Iterable[ProtocolSourceSpan] | Mapping[str, ProtocolSourceSpan],
) -> tuple[dict[str, ProtocolSourceSpan], dict[str, ProtocolSourceSpan], tuple[ProtocolSourceSpan, ...]]:
    spans = tuple(source_spans.values()) if isinstance(source_spans, Mapping) else tuple(source_spans)
    by_id: dict[str, ProtocolSourceSpan] = {}
    by_ref: dict[str, ProtocolSourceSpan] = {}
    for span in spans:
        previous_id = by_id.get(span.source_span_id)
        if previous_id is not None and previous_id != span:
            raise CatalogValidationError(
                "source_span_duplicate",
                f"来源片段 ID 重复且内容不同：{span.source_span_id}",
            )
        previous_ref = by_ref.get(span.source_ref)
        if previous_ref is not None and previous_ref.source_span_id != span.source_span_id:
            raise CatalogValidationError(
                "source_ref_ambiguous",
                f"同一 source_ref 对应多个来源片段：{span.source_ref}",
            )
        by_id[span.source_span_id] = span
        by_ref[span.source_ref] = span
    return by_id, by_ref, spans


def _span_from_id(
    span_id: str,
    *,
    by_id: Mapping[str, ProtocolSourceSpan],
    by_ref: Mapping[str, ProtocolSourceSpan],
) -> ProtocolSourceSpan | None:
    return by_id.get(span_id) or by_ref.get(span_id)


def _scope_error(rule: OfficialParentRuleRange, selected_phase: StudyPhase) -> str | None:
    scopes = set(rule.phase_scopes)
    allowed = _allowed_scopes(selected_phase)
    selected = _selected_scope(selected_phase)
    if not scopes or PhaseScope.UNKNOWN in scopes:
        return "期别未解析"
    if PhaseScope.MIXED in scopes:
        return "期别适用范围为 mixed"
    if selected_phase == StudyPhase.SEAMLESS_II_III:
        return None if scopes <= allowed else "包含未允许的期别范围"
    if selected in scopes:
        return None if scopes <= allowed else "同时包含其他期别，不能投影到单一期别"
    if PhaseScope.SHARED in scopes:
        return None if scopes <= allowed else "共享范围同时混入其他期别"
    # A complete opposite-phase range is safe to leave out only when another
    # range in the same section supplies the selected phase.  The caller uses
    # this marker for phase isolation and reports it if a category becomes
    # empty after filtering.
    return "仅属于未选期别"


def _select_phase_rules(
    rules: Sequence[OfficialParentRuleRange],
    selected_phase: StudyPhase,
) -> tuple[tuple[OfficialParentRuleRange, ...], tuple[tuple[OfficialParentRuleRange, str], ...]]:
    selected: list[OfficialParentRuleRange] = []
    errors: list[tuple[OfficialParentRuleRange, str]] = []
    selected_scope = _selected_scope(selected_phase)
    for rule in rules:
        reason = _scope_error(rule, selected_phase)
        scopes = set(rule.phase_scopes)
        if reason is None:
            selected.append(rule)
            continue
        # Do not leak an opposite-phase rule into a selected catalog.  It is
        # only a valid omission when its range is unambiguously opposite to the
        # selected scope and carries no shared/ambiguous marker.
        if (
            reason == "仅属于未选期别"
            and selected_phase != StudyPhase.SEAMLESS_II_III
            and selected_scope not in scopes
            and PhaseScope.SHARED not in scopes
            and not scopes & {PhaseScope.UNKNOWN, PhaseScope.MIXED}
        ):
            continue
        errors.append((rule, reason))
    return tuple(selected), tuple(errors)


def _opposite_only(
    rules: Sequence[OfficialParentRuleRange],
    selected_phase: StudyPhase,
) -> bool:
    """Whether a non-empty category is wholly owned by the other phase."""

    if not rules or selected_phase == StudyPhase.SEAMLESS_II_III:
        return False
    return all(_scope_error(rule, selected_phase) == "仅属于未选期别" for rule in rules)


def _section_candidates(
    sections: Sequence[EligibilitySection],
    selected_phase: StudyPhase,
) -> tuple[
    tuple[EligibilitySection, tuple[OfficialParentRuleRange, ...], tuple[OfficialParentRuleRange, ...]],
    ...,
]:
    candidates: list[
        tuple[
            EligibilitySection,
            tuple[OfficialParentRuleRange, ...],
            tuple[OfficialParentRuleRange, ...],
        ]
    ] = []
    invalid: list[tuple[EligibilitySection, tuple[tuple[OfficialParentRuleRange, str], ...]]] = []
    for section in sections:
        inclusion, inclusion_errors = _select_phase_rules(section.inclusion_rules, selected_phase)
        exclusion, exclusion_errors = _select_phase_rules(section.exclusion_rules, selected_phase)
        errors = (*inclusion_errors, *exclusion_errors)
        if not inclusion and _opposite_only(section.inclusion_rules, selected_phase):
            errors = (*errors, (section.inclusion_rules[0], "仅属于未选期别"))
        if not exclusion and _opposite_only(section.exclusion_rules, selected_phase):
            errors = (*errors, (section.exclusion_rules[0], "仅属于未选期别"))
        if errors:
            invalid.append((section, tuple(errors)))
            continue
        if inclusion and exclusion:
            candidates.append((section, inclusion, exclusion))

    if candidates:
        def body_pair(section: EligibilitySection) -> int:
            return int(
                ".t" not in section.inclusion_heading_ref
                and ".t" not in section.exclusion_heading_ref
            )

        return tuple(
            sorted(
                candidates,
                key=lambda item: (
                    -body_pair(item[0]),
                    -(len(item[1]) + len(item[2])),
                    -len(item[1]),
                    item[0].start_block_order,
                    item[0].section_id,
                ),
            )
        )

    # Preserve the most useful deterministic failure when a section has a
    # selected-phase member but also contains an unresolved/mixed member.
    if invalid:
        preferred = sorted(
            invalid,
            key=lambda item: (
                -sum(
                    _scope_error(rule, selected_phase) is None
                    for rule in item[0].rules
                ),
                item[0].start_block_order,
                item[0].section_id,
            ),
        )[0]
        rule, reason = preferred[1][0]
        if reason == "仅属于未选期别":
            raise CatalogValidationError(
                "wrong_phase",
                f"官方父规则仅属于未选期别：{rule.source_ref}",
            )
        raise CatalogValidationError(
            "phase_unresolved_or_mixed",
            f"官方父规则期别未解析或混合：{rule.source_ref}（{reason}）",
        )
    raise CatalogValidationError(
        "zero_rules",
        "选定期别没有同时包含入选和排除官方父规则",
    )


def _validate_numbering(
    rules: Sequence[OfficialParentRuleRange],
    *,
    category: str,
) -> None:
    if not rules:
        raise CatalogValidationError(
            "zero_rules",
            f"官方{category}规则为零",
        )
    numbers = [rule.number for rule in rules]
    if any(number < 1 for number in numbers):
        raise CatalogValidationError(
            "numbering_invalid",
            f"官方{category}规则编号必须为正整数",
        )
    if len(numbers) != len(set(numbers)):
        raise CatalogValidationError(
            "numbering_duplicate",
            f"官方{category}编号重复",
        )
    expected = list(range(1, len(numbers) + 1))
    if numbers != expected:
        raise CatalogValidationError(
            "numbering_non_contiguous",
            f"官方{category}编号缺失或不连续：实际 {numbers}，期望 {expected}",
        )
    prefix = "IN" if category == "入选" else "EX"
    for rule in rules:
        match = _OFFICIAL_CODE_RE.fullmatch(rule.official_code)
        if match is None or match.group("prefix") != prefix or int(match.group("number")) != rule.number:
            raise CatalogValidationError(
                "numbering_invalid",
                f"官方{category}编号与结构编号不一致：{rule.official_code}",
            )


def _validate_source_range(
    rule: OfficialParentRuleRange,
    *,
    snapshot_id: str,
    by_id: Mapping[str, ProtocolSourceSpan],
    by_ref: Mapping[str, ProtocolSourceSpan],
) -> tuple[str, ...]:
    if rule.missing_source_refs:
        raise CatalogValidationError(
            "source_range_incomplete",
            f"官方父规则来源范围不完整：{rule.source_ref}",
        )
    if not rule.source_span_ids:
        raise CatalogValidationError(
            "source_range_missing",
            f"官方父规则没有来源片段：{rule.source_ref}",
        )
    if len(rule.source_span_ids) != len(set(rule.source_span_ids)):
        raise CatalogValidationError(
            "source_span_duplicate",
            f"官方父规则来源片段重复：{rule.source_ref}",
        )
    source_refs = set(rule.source_refs)
    resolved: list[str] = []
    for span_id in rule.source_span_ids:
        span = _span_from_id(span_id, by_id=by_id, by_ref=by_ref)
        if span is None:
            raise CatalogValidationError(
                "source_span_missing",
                f"官方父规则引用不存在的来源片段：{span_id}",
            )
        if span.snapshot_id != snapshot_id:
            raise CatalogValidationError(
                "source_snapshot_mismatch",
                f"官方父规则来源片段属于另一快照：{span_id}",
            )
        if span.source_ref not in source_refs:
            raise CatalogValidationError(
                "source_range_mismatch",
                f"来源片段不属于官方父规则完整范围：{span_id}",
            )
        resolved.append(span.source_span_id)
    return tuple(resolved)


def _validate_label(rule: OfficialParentRuleRange, *, category: str) -> None:
    if is_placeholder_label(rule.label):
        raise CatalogValidationError(
            "placeholder",
            f"官方{category}规则标签为空或占位：{rule.source_ref}",
        )


def _item_id(
    *,
    section_id: str,
    snapshot_id: str,
    selected_phase: StudyPhase,
    rule: OfficialParentRuleRange,
    source_span_ids: Sequence[str],
) -> str:
    return "parent:" + _short_digest(
        CATALOG_BUILDER_VERSION,
        snapshot_id,
        selected_phase.value,
        section_id,
        rule.category,
        rule.official_code,
        rule.source_ref,
        tuple(rule.source_refs),
        tuple(source_span_ids),
    )


def _catalog_id(snapshot_id: str, selected_phase: StudyPhase, rules: Sequence[OfficialParentRuleRange]) -> str:
    return "catalog:" + _short_digest(
        CATALOG_BUILDER_VERSION,
        CatalogKind.OFFICIAL_PARENT_RULES.value,
        snapshot_id,
        selected_phase.value,
        tuple(
            (
                rule.category,
                rule.official_code,
                rule.source_ref,
                tuple(rule.source_refs),
                tuple(rule.source_span_ids),
            )
            for rule in rules
        ),
    )


def freeze_official_parent_rules(
    section_index: ProtocolSectionIndex,
    selected_phase: StudyPhase,
    *,
    source_spans: Iterable[ProtocolSourceSpan]
    | Mapping[str, ProtocolSourceSpan]
    | None = None,
    frozen_at: datetime | None = None,
    frozen_by: str = _DEFAULT_FROZEN_BY,
) -> FrozenProtocolCatalog:
    """Freeze one selected phase's official inclusion/exclusion parent rules.

    Opposite-phase ranges are omitted only when they are unambiguously
    phase-specific.  Unknown, mixed, malformed, or partially sourced ranges
    are hard failures; they are never silently projected into the catalog.
    """

    if not isinstance(section_index, ProtocolSectionIndex):
        raise CatalogValidationError("section_index_invalid", "必须提供 ProtocolSectionIndex")
    spans_input = section_index.source_spans if source_spans is None else source_spans
    by_id, by_ref, spans = _span_maps(spans_input)
    snapshot_id = section_index.snapshot_id
    if not snapshot_id:
        raise CatalogValidationError("snapshot_missing", "目录快照不能为空")
    if any(span.snapshot_id != snapshot_id for span in spans):
        raise CatalogValidationError("source_snapshot_mismatch", "来源片段与目录快照不一致")
    candidates = _section_candidates(section_index.sections, selected_phase)
    section, inclusion, exclusion = candidates[0]
    _validate_numbering(inclusion, category="入选")
    _validate_numbering(exclusion, category="排除")

    ordered_rules = (*inclusion, *exclusion)
    source_ids_by_ref: dict[str, tuple[str, ...]] = {}
    for rule, category in (
        *((rule, "入选") for rule in inclusion),
        *((rule, "排除") for rule in exclusion),
    ):
        _validate_label(rule, category=category)
        source_ids_by_ref[rule.source_ref] = _validate_source_range(
            rule,
            snapshot_id=snapshot_id,
            by_id=by_id,
            by_ref=by_ref,
        )

    items: list[FrozenCatalogItem] = []
    for position, rule in enumerate(ordered_rules):
        source_ids = source_ids_by_ref[rule.source_ref]
        source_excerpts = optional_source_excerpts_for_spans(
            source_ids,
            by_id=by_id,
            by_ref=by_ref,
        )
        items.append(
            FrozenCatalogItem(
                item_id=_item_id(
                    section_id=section.section_id,
                    snapshot_id=snapshot_id,
                    selected_phase=selected_phase,
                    rule=rule,
                    source_span_ids=source_ids,
                ),
                kind=CatalogItemKind.PARENT_RULE,
                official_code=rule.official_code,
                label=rule.label,
                position=position,
                source_span_ids=source_ids,
                source_excerpts=source_excerpts,
            )
        )

    frozen_timestamp = _DEFAULT_FROZEN_AT if frozen_at is None else frozen_at
    if frozen_timestamp.tzinfo is None:
        raise CatalogValidationError("timestamp_invalid", "frozen_at 必须带时区")
    if not frozen_by.strip():
        raise CatalogValidationError("freezer_invalid", "frozen_by 不能为空")
    payload: dict[str, Any] = {
        "catalog_id": _catalog_id(snapshot_id, selected_phase, ordered_rules),
        "snapshot_id": snapshot_id,
        "catalog_kind": CatalogKind.OFFICIAL_PARENT_RULES,
        "study_phase": selected_phase,
        "items": tuple(items),
        "frozen_at": frozen_timestamp,
        "frozen_by": frozen_by,
        "schema_version": "fixture/v1",
    }
    payload["catalog_sha256"] = frozen_catalog_content_hash(
        FrozenProtocolCatalog.model_construct(**payload)
    )
    return FrozenProtocolCatalog.model_validate(payload)


# Public aliases mirror the required-procedure sidecar and keep the operation
# discoverable without introducing another catalog contract.
build_official_parent_catalog = freeze_official_parent_rules
build_official_parent_rules_catalog = freeze_official_parent_rules
build_official_parent_rule_catalog = freeze_official_parent_rules
build_parent_rule_catalog = freeze_official_parent_rules
freeze_official_parent_catalog = freeze_official_parent_rules
freeze_parent_rule_catalog = freeze_official_parent_rules


__all__ = [
    "CATALOG_BUILDER_VERSION",
    "CatalogValidationError",
    "OfficialParentCatalogError",
    "OfficialParentCatalogBuildError",
    "build_official_parent_catalog",
    "build_official_parent_rule_catalog",
    "build_official_parent_rules_catalog",
    "build_parent_rule_catalog",
    "freeze_official_parent_catalog",
    "freeze_official_parent_rules",
    "freeze_parent_rule_catalog",
]
