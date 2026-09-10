"""Deterministic frozen batches for semantic phase-applicability review.

This planner is deliberately model-free. It turns the already frozen full
protocol coverage manifest into bounded :class:`PhaseApplicabilityFrozenPackage`
instances. ``owned_units`` are the only units for which an Agent may return a
result; ``context_units`` are read-only source context and may be repeated in
neighboring packages. The default packing policy may combine adjacent small,
structurally related heading runs without changing ownership or source order.

The planner does not infer phase applicability.  It only preserves the source
order, the selected/opposite phase pair, and the source closure required by the
Worker 01 hydration and publication gate.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from typing import Literal

from pydantic import Field, model_validator

from app.domain.contracts.common import ContractModel
from app.domain.contracts.phase_applicability import (
    PhaseApplicabilityFrozenPackage,
    stable_phase_applicability_package_id,
)
from app.domain.contracts.protocol_controls import (
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    StructureUnitKind,
)
from app.domain.contracts.enums import PhaseScope, StudyPhase

PHASE_APPLICABILITY_PLAN_V1_VERSION = "phase5/phase-applicability-plan/v1"
PHASE_APPLICABILITY_PLAN_V2_VERSION = "phase5/phase-applicability-plan/v2"
PHASE_APPLICABILITY_PLAN_VERSION = PHASE_APPLICABILITY_PLAN_V2_VERSION
PHASE_APPLICABILITY_DEFAULT_BATCH_PACKING_POLICY = "adjacent_small_heading_runs"
PHASE_APPLICABILITY_SAME_HEADING_BATCH_PACKING_POLICY = "same_heading_runs"

__all__ = [
    "PHASE_APPLICABILITY_PLAN_V1_VERSION",
    "PHASE_APPLICABILITY_PLAN_V2_VERSION",
    "PHASE_APPLICABILITY_PLAN_VERSION",
    "PHASE_APPLICABILITY_DEFAULT_BATCH_PACKING_POLICY",
    "PHASE_APPLICABILITY_SAME_HEADING_BATCH_PACKING_POLICY",
    "PhaseApplicabilityContextCatalog",
    "PhaseApplicabilityPlanningError",
    "PhaseApplicabilityFrozenPlan",
    "build_phase_applicability_context_catalog",
    "build_phase_applicability_batches",
    "build_phase_applicability_plan",
    "build_phase_applicability_frozen_packages",
    "plan_phase_applicability_packages",
    "plan_phase_applicability_batches",
]


class PhaseApplicabilityPlanningError(ValueError):
    """A deterministic planning failure raised before any Agent call."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class PhaseApplicabilityContextCatalog(ContractModel):
    """Source-ordered, model-free context anchors for one full manifest.

    The catalog stores only system-owned structure-unit IDs.  It is a
    selection aid for widening evidence supplied to an Agent; it does not
    assign applicability and it never changes package ownership.
    """

    schema_version: Literal[PHASE_APPLICABILITY_PLAN_V2_VERSION] = (
        PHASE_APPLICABILITY_PLAN_V2_VERSION
    )
    coverage_manifest_id: str = Field(min_length=1)
    structure_unit_ids: list[str] = Field(min_length=1)
    explicit_phase_structure_unit_ids: list[str] = Field(default_factory=list)
    study_design_phase_structure_unit_ids: list[str] = Field(default_factory=list)
    visit_flow_structure_unit_ids: list[str] = Field(default_factory=list)
    cross_reference_structure_unit_ids: list[str] = Field(default_factory=list)
    table_anchor_structure_unit_ids: list[str] = Field(default_factory=list)
    global_authority_structure_unit_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_catalog(self) -> "PhaseApplicabilityContextCatalog":
        if len(self.structure_unit_ids) != len(set(self.structure_unit_ids)):
            raise ValueError("上下文目录结构单元不得重复")
        known = set(self.structure_unit_ids)
        for field_name in (
            "explicit_phase_structure_unit_ids",
            "study_design_phase_structure_unit_ids",
            "visit_flow_structure_unit_ids",
            "cross_reference_structure_unit_ids",
            "table_anchor_structure_unit_ids",
            "global_authority_structure_unit_ids",
        ):
            values = list(getattr(self, field_name))
            if len(values) != len(set(values)):
                raise ValueError(f"上下文目录 {field_name} 不得重复")
            if not set(values) <= known:
                raise ValueError(f"上下文目录 {field_name} 引用了清单外结构单元")
            if values != [
                unit_id for unit_id in self.structure_unit_ids if unit_id in set(values)
            ]:
                raise ValueError(f"上下文目录 {field_name} 必须保持全文来源顺序")
        return self

    @property
    def anchor_structure_unit_ids(self) -> tuple[str, ...]:
        """Return only compact global authority anchors in source order.

        The other catalog fields remain full-manifest indexes. Explicit phase
        units and cross-reference sources are selected per target below; they
        are deliberately not copied into every package.
        """

        anchor_ids = set(self.global_authority_structure_unit_ids)
        return tuple(
            unit_id for unit_id in self.structure_unit_ids if unit_id in anchor_ids
        )


class PhaseApplicabilityFrozenPlan(ContractModel):
    """Auditable plan for one selected-phase manifest's ambiguous units.

    ``expected_structure_unit_ids`` contains only Agent-owned ambiguous units;
    structurally explicit units are deterministic context and are intentionally
    absent.  An all-explicit manifest therefore has no packages.
    """

    schema_version: Literal[
        PHASE_APPLICABILITY_PLAN_V1_VERSION,
        PHASE_APPLICABILITY_PLAN_V2_VERSION,
    ] = PHASE_APPLICABILITY_PLAN_V2_VERSION
    plan_id: str
    coverage_manifest_id: str
    protocol_version_id: str
    study_phase: StudyPhase
    max_owned_units_per_batch: int
    context_radius: int
    batch_packing_policy: Literal[
        "adjacent_small_heading_runs",
        "same_heading_runs",
    ]
    expected_structure_unit_ids: list[str]
    packages: list[PhaseApplicabilityFrozenPackage]

    @model_validator(mode="before")
    @classmethod
    def load_historical_plan(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        if (
            value.get("schema_version") == PHASE_APPLICABILITY_PLAN_V1_VERSION
            and "batch_packing_policy" not in value
        ):
            return {
                **value,
                "batch_packing_policy": (
                    PHASE_APPLICABILITY_SAME_HEADING_BATCH_PACKING_POLICY
                ),
            }
        return value

    @model_validator(mode="after")
    def validate_plan(self) -> "PhaseApplicabilityFrozenPlan":
        if self.max_owned_units_per_batch < 1:
            raise ValueError("max_owned_units_per_batch 必须为正整数")
        if self.context_radius < 0:
            raise ValueError("context_radius 不能为负数")
        if not self.packages and self.expected_structure_unit_ids:
            raise ValueError("仍有待判断结构单元时冻结计划不得没有批次")
        if len(self.expected_structure_unit_ids) != len(
            set(self.expected_structure_unit_ids)
        ):
            raise ValueError("计划 expected_structure_unit_ids 不得重复")
        if any(
            len(package.owned_units) > self.max_owned_units_per_batch
            for package in self.packages
        ):
            raise ValueError("冻结批次超过 max_owned_units_per_batch")
        package_ids = [package.package_id for package in self.packages]
        if len(package_ids) != len(set(package_ids)):
            raise ValueError("冻结期别语义批次身份不得重复")
        ordinals = [package.package_ordinal for package in self.packages]
        if ordinals != list(range(1, len(self.packages) + 1)):
            raise ValueError("冻结期别语义批次序号必须连续")
        owned_ids = [
            unit.structure_unit_id
            for package in self.packages
            for unit in package.owned_units
        ]
        if owned_ids != self.expected_structure_unit_ids:
            raise ValueError("计划 owned 结构单元必须完整覆盖且保持原文顺序")
        if any(
            package.coverage_manifest_id != self.coverage_manifest_id
            or package.protocol_version_id != self.protocol_version_id
            or package.selected_phase != self.study_phase
            for package in self.packages
        ):
            raise ValueError("冻结批次必须绑定同一全文清单、方案版本和选定期别")
        if self.schema_version == PHASE_APPLICABILITY_PLAN_V1_VERSION:
            if (
                self.batch_packing_policy
                != PHASE_APPLICABILITY_SAME_HEADING_BATCH_PACKING_POLICY
            ):
                raise ValueError("v1 冻结计划不得使用新的跨标题打包策略")
            expected_plan_id = _stable_plan_id_v1(
                self.coverage_manifest_id,
                self.max_owned_units_per_batch,
                self.context_radius,
                package_ids,
            )
        else:
            expected_plan_id = _stable_plan_id(
                self.coverage_manifest_id,
                self.max_owned_units_per_batch,
                self.context_radius,
                self.batch_packing_policy,
                package_ids,
            )
        if self.plan_id != expected_plan_id:
            raise ValueError("plan_id 必须由系统根据冻结批次生成")
        return self


def _stable_plan_id(
    manifest_id: str,
    max_owned_units_per_batch: int,
    context_radius: int,
    batch_packing_policy: str,
    package_ids: Sequence[str],
) -> str:
    payload = json.dumps(
        [
            manifest_id,
            max_owned_units_per_batch,
            context_radius,
            batch_packing_policy,
            list(package_ids),
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "papl-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _stable_plan_id_v1(
    manifest_id: str,
    max_owned_units_per_batch: int,
    context_radius: int,
    package_ids: Sequence[str],
) -> str:
    payload = json.dumps(
        [
            manifest_id,
            max_owned_units_per_batch,
            context_radius,
            list(package_ids),
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "papl-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _ordered_units(
    coverage_manifest: ProtocolSectionCoverageManifest,
) -> tuple[ProtocolStructureUnit, ...]:
    units = tuple(
        sorted(
            coverage_manifest.units,
            key=lambda unit: (unit.source_order, unit.structure_unit_id),
        )
    )
    if tuple(coverage_manifest.units) != units:
        raise PhaseApplicabilityPlanningError(
            "manifest_order_invalid",
            "全文覆盖清单结构单元必须先按原文顺序冻结。",
        )
    return units


def _heading_runs(
    units: Sequence[ProtocolStructureUnit],
) -> tuple[tuple[ProtocolStructureUnit, ...], ...]:
    """Return exact heading-path runs in source order."""

    runs: list[list[ProtocolStructureUnit]] = []
    for unit in units:
        heading = tuple(unit.heading_path)
        if not runs or tuple(runs[-1][0].heading_path) != heading:
            runs.append([])
        runs[-1].append(unit)
    return tuple(tuple(run) for run in runs)


_TABLE_ROW_REF = re.compile(r"^(?P<table>.+?)\.r\d+(?:\.c\d+)?(?:\.p\d+)?$")

_STUDY_DESIGN_PHASE_TERMS = (
    "研究设计",
    "试验设计",
    "方案设计",
    "研究阶段",
    "研究期别",
    "phase",
    "study design",
    "study phase",
    "trial design",
)
_PHASE_HEADING_RE = re.compile(
    r"(?:\bphase\s*(?:ii|iii|2|3)\b|"
    r"(?:^|[\s（(])(?:第\s*)?(?:ii|iii|2|3|二|三|Ⅱ|Ⅲ)\s*期)",
    re.IGNORECASE,
)
_VISIT_FLOW_HEADING_TERMS = (
    "访视",
    "访视流程",
    "访视安排",
    "研究流程",
    "试验流程",
    "visit",
    "schedule",
    "flow",
    "follow-up",
)
_CROSS_REFERENCE_TERMS = (
    "参见",
    "见表",
    "详见",
    "见第",
    "见图",
    "见附录",
    "见上述",
    "见下",
    "同前",
    "交叉引用",
    "cross-reference",
    "refer",
    "see",
)

_TABLE_REFERENCE_RE = re.compile(
    r"(?:参见|详见|见|refer(?:\s+to)?|see)\s*(?:第\s*)?"
    r"(?:表格?|table)\s*(?P<number>[0-9０-９一二三四五六七八九十百]+)",
    re.IGNORECASE,
)
_TABLE_TITLE_NUMBER_RE = re.compile(
    r"(?:表格?|table)\s*(?P<number>[0-9０-９一二三四五六七八九十百]+)",
    re.IGNORECASE,
)
_HEADING_NUMBER_PREFIX_RE = re.compile(
    r"^\s*(?:第\s*)?(?:[0-9]+(?:[.．][0-9]+)*|[一二三四五六七八九十百]+|[IVXLC]+)"
    r"\s*[、.．:：\-\s]*",
    re.IGNORECASE,
)
_PLACEHOLDER_HEADINGS = {
    "（无标题）",
    "(无标题)",
    "（上级标题未识别）",
    "(上级标题未识别)",
}
_HEADING_REFERENCE_TERM_SPLIT_RE = re.compile(r"[^0-9a-z\u4e00-\u9fff]+", re.IGNORECASE)


def _unit_text(unit: ProtocolStructureUnit) -> str:
    table = unit.table_context
    headers = () if table is None else (*table.row_headers, *table.column_headers)
    return " ".join((*unit.heading_path, unit.excerpt, *headers)).casefold()


def _matches_terms(unit: ProtocolStructureUnit, terms: Sequence[str]) -> bool:
    haystack = _unit_text(unit)
    return any(term.casefold() in haystack for term in terms)


def _heading_text(unit: ProtocolStructureUnit) -> str:
    return " ".join(unit.heading_path).strip().casefold()


def _is_heading_anchor(unit: ProtocolStructureUnit) -> bool:
    """Recognize a heading source without treating body wording as a role."""

    return (
        bool(unit.heading_path)
        and unit.excerpt.strip().casefold() == unit.heading_path[-1].strip().casefold()
    )


def _is_study_design_heading(unit: ProtocolStructureUnit) -> bool:
    heading = _heading_text(unit)
    if any(term.casefold() in heading for term in _STUDY_DESIGN_PHASE_TERMS):
        return True
    return bool(
        _PHASE_HEADING_RE.search(heading)
        and any(term in heading for term in ("方案", "研究", "设计", "protocol"))
    )


def _is_visit_flow_heading(unit: ProtocolStructureUnit) -> bool:
    heading = _heading_text(unit)
    return any(term.casefold() in heading for term in _VISIT_FLOW_HEADING_TERMS)


def _heading_label(value: str) -> str:
    return _HEADING_NUMBER_PREFIX_RE.sub("", value.strip()).casefold()


def _target_mentions_heading(
    targets: Sequence[ProtocolStructureUnit],
    heading: ProtocolStructureUnit,
) -> bool:
    """Return whether a target directly names a frozen leaf heading.

    A compact authority catalog often contains a phase-specific heading but
    not the paragraph below it.  When target text names that leaf heading, the
    heading's same-section body is source closure, not unrelated global
    context.  Short generic labels are excluded to avoid widening packages for
    incidental words such as ``检查`` or ``访视``.
    """

    if not _is_heading_anchor(heading) or not heading.heading_path:
        return False
    title = _heading_label(heading.heading_path[-1])
    terms = tuple(
        term for term in _HEADING_REFERENCE_TERM_SPLIT_RE.split(title) if len(term) >= 4
    )
    if not terms:
        return False
    target_text = " ".join(target.excerpt for target in targets).casefold()
    return title in target_text or any(term in target_text for term in terms)


def _meaningful_heading_path(unit: ProtocolStructureUnit) -> tuple[str, ...]:
    return tuple(
        segment.strip().casefold()
        for segment in unit.heading_path
        if segment.strip() and segment.strip() not in _PLACEHOLDER_HEADINGS
    )


def _packing_heading_path(unit: ProtocolStructureUnit) -> tuple[str, ...]:
    """Return a numbering-insensitive path used only for adjacent packing."""

    return tuple(
        label
        for segment in unit.heading_path
        if segment.strip() not in _PLACEHOLDER_HEADINGS
        if (label := _heading_label(segment))
    )


def _shares_packing_heading_ancestor(
    left: Sequence[ProtocolStructureUnit],
    right: Sequence[ProtocolStructureUnit],
) -> bool:
    if not left or not right:
        return False
    left_path = _packing_heading_path(left[0])
    right_path = _packing_heading_path(right[0])
    if not left_path or not right_path:
        return False
    common = 0
    for left_segment, right_segment in zip(left_path, right_path):
        if left_segment != right_segment:
            break
        common += 1
    return common >= 1


def _heading_run_has_table_target(
    run: Sequence[ProtocolStructureUnit],
    study_phase: StudyPhase,
) -> bool:
    return any(
        unit.table_context is not None
        and not _is_structurally_explicit(unit, study_phase)
        for unit in run
    )


def _can_pack_adjacent_heading_runs(
    left_run: Sequence[ProtocolStructureUnit],
    right_run: Sequence[ProtocolStructureUnit],
    *,
    study_phase: StudyPhase,
) -> bool:
    """Keep cross-heading packing structural and conservative.

    Table targets retain their table-local closure as an independent packet.
    Non-table runs may share a batch only when their normalized heading paths
    have a real common ancestor; unrelated top-level chapters never merge.
    """

    if _heading_run_has_table_target(
        left_run, study_phase
    ) or _heading_run_has_table_target(
        right_run,
        study_phase,
    ):
        return False
    return _shares_packing_heading_ancestor(left_run, right_run)


def _shares_meaningful_heading_ancestor(
    left: ProtocolStructureUnit,
    right: ProtocolStructureUnit,
) -> bool:
    left_path = _meaningful_heading_path(left)
    right_path = _meaningful_heading_path(right)
    common = 0
    for left_segment, right_segment in zip(left_path, right_path):
        if left_segment != right_segment:
            break
        common += 1
    # A single shared top-level chapter is too broad for a package.  Keep it
    # only when one unit is that chapter itself; otherwise require a deeper
    # structural branch to avoid importing sibling sections wholesale.
    return common >= 2 or (common > 0 and min(len(left_path), len(right_path)) == 1)


def _normalize_reference_number(value: str) -> str:
    digits = "０１２３４５６７８９"
    value = value.translate(str.maketrans(digits, "0123456789"))
    if value.isdigit():
        return str(int(value))
    if value == "十":
        return "10"
    if value in {"百"}:
        return "100"
    chinese = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    if value in chinese:
        return str(chinese[value])
    if len(value) == 2 and value[0] == "十" and value[1] in chinese:
        return str(10 + chinese[value[1]])
    if len(value) == 2 and value[1] == "十" and value[0] in chinese:
        return str(chinese[value[0]] * 10)
    return value.casefold()


def _table_number(unit: ProtocolStructureUnit) -> str | None:
    candidates = [*unit.heading_path, unit.excerpt]
    for value in candidates:
        match = _TABLE_TITLE_NUMBER_RE.search(value)
        if match:
            return _normalize_reference_number(match.group("number"))
    return None


def _is_cross_reference_source(unit: ProtocolStructureUnit) -> bool:
    return _matches_terms(unit, _CROSS_REFERENCE_TERMS)


def _table_key(unit: ProtocolStructureUnit) -> tuple[str, str] | None:
    if unit.table_context is None:
        return None
    for source_ref in (unit.source_ref, *unit.member_source_refs):
        match = _TABLE_ROW_REF.match(source_ref)
        if match:
            return ("source", match.group("table"))
    # Synthetic/legacy structure units may only carry table coordinates.  A
    # non-empty outer path is still a deterministic table key in that shape.
    outer_path = tuple(unit.table_context.table_path[:-2])
    if outer_path:
        return ("path", ",".join(str(value) for value in outer_path))
    return ("heading", "\x1f".join(unit.heading_path))


def _selected_scope(study_phase: StudyPhase) -> PhaseScope:
    return {
        StudyPhase.PHASE_II: PhaseScope.PHASE_II,
        StudyPhase.PHASE_III: PhaseScope.PHASE_III,
        StudyPhase.SEAMLESS_II_III: PhaseScope.SEAMLESS_CANDIDATE,
    }[study_phase]


def _admissible_explicit_scopes(study_phase: StudyPhase) -> set[PhaseScope]:
    scopes = {_selected_scope(study_phase), PhaseScope.SHARED}
    if study_phase == StudyPhase.PHASE_II:
        scopes.add(PhaseScope.PHASE_III)
    elif study_phase == StudyPhase.PHASE_III:
        scopes.add(PhaseScope.PHASE_II)
    else:
        # A seamless manifest has no single opposite phase, but an explicitly
        # phase-labelled II/III unit is still a known structural context.
        scopes.update({PhaseScope.PHASE_II, PhaseScope.PHASE_III})
    return scopes


def _is_structurally_explicit(
    unit: ProtocolStructureUnit,
    study_phase: StudyPhase,
) -> bool:
    scopes = tuple(unit.phase_scopes)
    return (
        len(scopes) == 1
        and scopes[0] not in {PhaseScope.UNKNOWN, PhaseScope.MIXED}
        and scopes[0] in _admissible_explicit_scopes(study_phase)
    )


def _table_anchor_ids(
    units: Sequence[ProtocolStructureUnit],
) -> set[str]:
    table_units = [unit for unit in units if unit.table_context is not None]
    table_titles = {
        unit.heading_path[-1].strip()
        for unit in table_units
        if unit.heading_path and unit.heading_path[-1].strip()
    }
    return {
        unit.structure_unit_id
        for unit in units
        if unit.table_context is not None or unit.excerpt.strip() in table_titles
    }


def _compact_global_authority_ids(
    units: Sequence[ProtocolStructureUnit],
) -> set[str]:
    """Keep one structural anchor per authority heading plus role headers."""

    selected: set[str] = set()
    first_by_role_heading: dict[tuple[str, ...], str] = {}
    table_authority_paths = [
        tuple(unit.heading_path)
        for unit in units
        if unit.table_context is not None
    ]
    for unit in units:
        role = _is_study_design_heading(unit) or _is_visit_flow_heading(unit)
        if not role:
            continue
        heading_key = tuple(unit.heading_path)
        has_descendant_table_authority = any(
            len(path) > len(heading_key)
            and path[: len(heading_key)] == heading_key
            for path in table_authority_paths
        )
        if not has_descendant_table_authority:
            first_by_role_heading.setdefault(heading_key, unit.structure_unit_id)
        if unit.unit_kind == StructureUnitKind.TABLE_HEADER:
            selected.add(unit.structure_unit_id)
    selected.update(first_by_role_heading.values())
    return selected


def build_phase_applicability_context_catalog(
    coverage_manifest: ProtocolSectionCoverageManifest,
) -> PhaseApplicabilityContextCatalog:
    """Build full-manifest structural anchors without deciding applicability."""

    units = _ordered_units(coverage_manifest)
    structure_unit_ids = [unit.structure_unit_id for unit in units]
    table_anchor_ids = _table_anchor_ids(units)
    study_design_ids = [
        unit.structure_unit_id for unit in units if _is_study_design_heading(unit)
    ]
    visit_flow_ids = [
        unit.structure_unit_id for unit in units if _is_visit_flow_heading(unit)
    ]
    compact_global_ids = _compact_global_authority_ids(
        units,
    )
    return PhaseApplicabilityContextCatalog(
        coverage_manifest_id=coverage_manifest.manifest_id,
        structure_unit_ids=structure_unit_ids,
        explicit_phase_structure_unit_ids=[
            unit.structure_unit_id
            for unit in units
            if _is_structurally_explicit(unit, coverage_manifest.study_phase)
        ],
        study_design_phase_structure_unit_ids=study_design_ids,
        visit_flow_structure_unit_ids=visit_flow_ids,
        cross_reference_structure_unit_ids=[
            unit.structure_unit_id for unit in units if _is_cross_reference_source(unit)
        ],
        table_anchor_structure_unit_ids=[
            unit.structure_unit_id
            for unit in units
            if unit.structure_unit_id in table_anchor_ids
        ],
        global_authority_structure_unit_ids=[
            unit.structure_unit_id
            for unit in units
            if unit.structure_unit_id in compact_global_ids
        ],
    )


def _local_context_units(
    run: Sequence[ProtocolStructureUnit],
    owned: Sequence[ProtocolStructureUnit],
    radius: int,
) -> tuple[ProtocolStructureUnit, ...]:
    if radius <= 0 or not owned:
        return ()
    owned_ids = {unit.structure_unit_id for unit in owned}
    positions = [
        index for index, unit in enumerate(run) if unit.structure_unit_id in owned_ids
    ]
    if not positions:
        return ()
    start = max(0, min(positions) - radius)
    end = min(len(run), max(positions) + radius + 1)
    return tuple(
        unit for unit in run[start:end] if unit.structure_unit_id not in owned_ids
    )


def _closing_heading_after_explicit_segment(
    units: Sequence[ProtocolStructureUnit],
    owned: Sequence[ProtocolStructureUnit],
    study_phase: StudyPhase,
) -> ProtocolStructureUnit | None:
    """Return only the heading that closes an intervening explicit phase branch."""

    if not owned:
        return None
    last_owned = max(owned, key=lambda unit: unit.source_order)
    owned_path = _meaningful_heading_path(last_owned)
    if not owned_path:
        return None

    crossed_explicit_segment = False
    for unit in units:
        if unit.source_order <= last_owned.source_order:
            continue
        if _is_structurally_explicit(unit, study_phase):
            crossed_explicit_segment = True
            continue
        if not crossed_explicit_segment or not _is_heading_anchor(unit):
            return None
        candidate_path = _meaningful_heading_path(unit)
        if candidate_path[: len(owned_path)] != owned_path:
            return unit
        return None
    return None


def _package_context_units(
    units: Sequence[ProtocolStructureUnit],
    catalog: PhaseApplicabilityContextCatalog,
    owned: Sequence[ProtocolStructureUnit],
    local_context: Sequence[ProtocolStructureUnit],
    *,
    study_phase: StudyPhase,
) -> tuple[ProtocolStructureUnit, ...]:
    by_id = {unit.structure_unit_id: unit for unit in units}
    owned_ids = {unit.structure_unit_id for unit in owned}
    context_ids = set(catalog.anchor_structure_unit_ids)
    context_ids.update(unit.structure_unit_id for unit in local_context)
    if closing_heading := _closing_heading_after_explicit_segment(
        units,
        owned,
        study_phase,
    ):
        context_ids.add(closing_heading.structure_unit_id)

    # A clinical subsection is one semantic reading unit even when batching
    # splits its paragraphs or table rows. Keep the complete exact subsection
    # as read-only context. For table members, the final heading segment is the
    # table title, so the containing subsection is the parent path. Sibling
    # subsections and broader chapter bodies remain out of scope.
    owned_section_paths: set[tuple[str, ...]] = set()
    for unit in owned:
        if unit.table_context is None and _table_number(unit) is None:
            continue
        section_path = (
            tuple(unit.heading_path[:-1])
            if unit.table_context is not None and len(unit.heading_path) > 1
            else tuple(unit.heading_path)
        )
        meaningful_section_path = tuple(
            segment
            for segment in section_path
            if segment.strip() and segment.strip() not in _PLACEHOLDER_HEADINGS
        )
        if len(meaningful_section_path) >= 2:
            owned_section_paths.add(section_path)
    context_ids.update(
        unit.structure_unit_id
        for unit in units
        if tuple(unit.heading_path) in owned_section_paths
    )

    # If a target directly names a phase-specific leaf heading already present
    # in the compact authority catalog, freeze that heading's complete body.
    # A title without its operative paragraph is not enough for semantic phase
    # comparison and would force the Agent to infer missing protocol text.
    explicit_heading_anchors = [
        by_id[unit_id]
        for unit_id in tuple(context_ids)
        if unit_id in by_id
        if unit_id in catalog.explicit_phase_structure_unit_ids
        if _is_heading_anchor(by_id[unit_id])
    ]
    phase_scopes_by_title: dict[str, set[PhaseScope]] = {}
    for anchor in explicit_heading_anchors:
        phase_scopes_by_title.setdefault(
            _heading_label(anchor.heading_path[-1]),
            set(),
        ).update(anchor.phase_scopes)
    paired_titles = {
        title
        for title, scopes in phase_scopes_by_title.items()
        if {PhaseScope.PHASE_II, PhaseScope.PHASE_III} <= scopes
    }
    referenced_heading_paths = {
        tuple(anchor.heading_path)
        for anchor in explicit_heading_anchors
        if _heading_label(anchor.heading_path[-1]) in paired_titles
        if _target_mentions_heading(owned, anchor)
    }
    if referenced_heading_paths:
        context_ids.update(
            unit.structure_unit_id
            for unit in units
            if tuple(unit.heading_path) in referenced_heading_paths
            and unit.structure_unit_id in catalog.explicit_phase_structure_unit_ids
        )

    target_heading_labels = {
        label
        for target in owned
        if (path := _packing_heading_path(target))
        for label in path[-1:]
        if len(label) >= 2
    }

    # A phase-specific design paragraph may point back to the target rule
    # family instead of living under that rule's heading.  Recover that
    # reverse reference from the frozen source itself.  Restrict candidates to
    # already indexed, explicitly scoped study-design units so a generic body
    # mention cannot widen every package.
    reverse_reference_units = [
        unit
        for unit_id in catalog.study_design_phase_structure_unit_ids
        if unit_id in catalog.explicit_phase_structure_unit_ids
        if (unit := by_id[unit_id]).unit_kind == StructureUnitKind.PARAGRAPH
        if any(label in unit.excerpt.casefold() for label in target_heading_labels)
    ]
    reverse_reference_scopes = {
        scope for unit in reverse_reference_units for scope in unit.phase_scopes
    }
    if {PhaseScope.PHASE_II, PhaseScope.PHASE_III} <= reverse_reference_scopes:
        context_ids.update(unit.structure_unit_id for unit in reverse_reference_units)

    target_table_keys = {key for unit in owned if (key := _table_key(unit)) is not None}
    target_table_titles = {
        unit.heading_path[-1].strip()
        for unit in owned
        if unit.table_context is not None and unit.heading_path
    }

    # The catalog is a full-manifest audit index, not a package payload.  Add
    # explicit non-table phase units only when they share a meaningful heading
    # branch with the target. Table phase units are included only for a target
    # table itself, where the complete target-table closure is added below.
    for unit_id in catalog.explicit_phase_structure_unit_ids:
        unit = by_id[unit_id]
        if any(
            _shares_meaningful_heading_ancestor(unit, target) for target in owned
        ) and (unit.table_context is None or _table_key(unit) in target_table_keys):
            context_ids.add(unit_id)

    # A target table is an indivisible frozen evidence closure.  Every row,
    # header, note, and the structural title unit must remain visible even
    # when rows are split across owned batches.  This is deliberately scoped
    # to the target table keys; the full catalog is never copied wholesale.
    for unit in units:
        same_table = _table_key(unit) in target_table_keys
        is_target_title = unit.excerpt.strip() in target_table_titles
        if same_table or is_target_title:
            context_ids.add(unit.structure_unit_id)

    # Resolve references carried by the target or its local neighborhood.  An
    # unresolved reference remains visible as its own frozen source unit; no
    # synthetic target or protocol-wide cross-reference list is created.
    reference_sources = tuple(
        {unit.structure_unit_id: unit for unit in (*owned, *local_context)}.values()
    )
    for source in reference_sources:
        if not _is_cross_reference_source(source):
            continue
        # The source heading path is structural context, not a reference
        # expression.  Searching it would make every sibling table appear
        # referenced merely because it shares the same chapter.
        reference_text = source.excerpt.casefold()
        table_number_match = _TABLE_REFERENCE_RE.search(reference_text)
        if table_number_match:
            referenced_number = _normalize_reference_number(
                table_number_match.group("number")
            )
            for unit_id in catalog.table_anchor_structure_unit_ids:
                candidate = by_id[unit_id]
                if _table_number(candidate) == referenced_number:
                    context_ids.add(unit_id)

        # Match explicit heading labels only against already-indexed authority
        # or phase units. Generic prose mentions do not widen the package.
        referenced_table_keys: set[tuple[str, str]] = set()
        for candidate in units:
            candidate_labels = {
                _heading_label(segment)
                for segment in candidate.heading_path
                if _heading_label(segment)
            }
            if not any(
                len(label) >= 2 and label in reference_text
                for label in candidate_labels
            ):
                continue
            candidate_id = candidate.structure_unit_id
            if candidate_id in catalog.anchor_structure_unit_ids:
                context_ids.add(candidate_id)
            if (
                candidate_table_key := _table_key(candidate)
            ) is not None and _table_number(candidate) is not None:
                referenced_table_keys.add(candidate_table_key)

        # A heading-only reference may identify one table unambiguously.  If
        # it names a heading shared by several phase tables, retain compact
        # headers/authority anchors but do not duplicate every member row from
        # all matching tables.  An explicit table number above still closes
        # the complete referenced table deterministically.
        if len(referenced_table_keys) == 1:
            referenced_key = next(iter(referenced_table_keys))
            for unit_id in catalog.table_anchor_structure_unit_ids:
                candidate = by_id[unit_id]
                if _table_key(candidate) == referenced_key:
                    context_ids.add(unit_id)

        # Local cross-reference sources are already in the package. Keep this
        # explicit branch so a future local-selector change cannot drop an
        # unresolved source; owned sources remain targets, not context.
        if source.structure_unit_id not in owned_ids:
            context_ids.add(source.structure_unit_id)

    return tuple(
        sorted(
            (
                by_id[unit_id]
                for unit_id in context_ids
                if unit_id in by_id and unit_id not in owned_ids
            ),
            key=lambda unit: (unit.source_order, unit.structure_unit_id),
        )
    )


def _build_phase_applicability_chunks(
    units: Sequence[ProtocolStructureUnit],
    catalog: PhaseApplicabilityContextCatalog,
    *,
    study_phase: StudyPhase,
    max_owned_units_per_batch: int,
    context_radius: int,
    batch_packing_policy: str,
) -> list[tuple[tuple[ProtocolStructureUnit, ...], tuple[ProtocolStructureUnit, ...]]]:
    """Pack ordered target runs while preserving each run's local closure."""

    chunks: list[
        tuple[tuple[ProtocolStructureUnit, ...], tuple[ProtocolStructureUnit, ...]]
    ] = []
    group: list[
        tuple[tuple[ProtocolStructureUnit, ...], tuple[ProtocolStructureUnit, ...]]
    ] = []

    def flush_group() -> None:
        if not group:
            return
        targets = tuple(target for _run, run_targets in group for target in run_targets)
        for start in range(0, len(targets), max_owned_units_per_batch):
            owned = targets[start : start + max_owned_units_per_batch]
            owned_ids = {unit.structure_unit_id for unit in owned}
            local_context: list[ProtocolStructureUnit] = []
            offset = 0
            for run, run_targets in group:
                run_ids = {
                    unit.structure_unit_id
                    for unit in targets[offset : offset + len(run_targets)]
                }
                owned_in_run = tuple(
                    unit
                    for unit in run_targets
                    if unit.structure_unit_id in (run_ids & owned_ids)
                )
                local_context.extend(
                    _local_context_units(run, owned_in_run, context_radius)
                )
                offset += len(run_targets)
            context = _package_context_units(
                units,
                catalog,
                owned,
                local_context,
                study_phase=study_phase,
            )
            chunks.append((owned, context))
        group.clear()

    for run in _heading_runs(units):
        ambiguous = tuple(
            unit for unit in run if not _is_structurally_explicit(unit, study_phase)
        )
        if not ambiguous:
            # An explicit-only heading run is a structural boundary.  Its
            # units remain available through the normal context selectors.
            flush_group()
            continue

        if (
            batch_packing_policy
            == PHASE_APPLICABILITY_SAME_HEADING_BATCH_PACKING_POLICY
        ):
            flush_group()
            group.append((run, ambiguous))
            flush_group()
            continue

        if len(ambiguous) > max_owned_units_per_batch:
            flush_group()
            group.append((run, ambiguous))
            flush_group()
            continue

        if group and not _can_pack_adjacent_heading_runs(
            group[-1][0],
            run,
            study_phase=study_phase,
        ):
            flush_group()
        elif group and (
            sum(len(run_targets) for _run, run_targets in group) + len(ambiguous)
            > max_owned_units_per_batch
        ):
            # Keep each complete heading run intact.  Only a single run that
            # is itself oversized may be split by ``flush_group`` below.
            flush_group()
        group.append((run, ambiguous))

    flush_group()
    return chunks


def plan_phase_applicability_batches(
    coverage_manifest: ProtocolSectionCoverageManifest,
    *,
    max_owned_units_per_batch: int = 12,
    max_batch_size: int | None = None,
    context_radius: int = 1,
    batch_packing_policy: Literal[
        "adjacent_small_heading_runs",
        "same_heading_runs",
    ] = PHASE_APPLICABILITY_DEFAULT_BATCH_PACKING_POLICY,
) -> PhaseApplicabilityFrozenPlan:
    """Build source-ordered phase-applicability packages.

    ``max_owned_units_per_batch`` counts only Agent-owned target units. A
    neighboring unit added by ``context_radius`` is read-only context and
    never changes package ownership. Structurally explicit phase units are
    never owned. The default ``adjacent_small_heading_runs`` policy combines
    adjacent non-table runs only when they share a normalized heading ancestor
    and the complete addition keeps the group within one batch; a single run
    that exceeds the limit retains the same-heading split behavior. The
    package identity is derived from the manifest identity, ordinal and owned
    structure identities; no model output participates in the identity.
    """

    if max_batch_size is not None:
        if (
            max_owned_units_per_batch != 12
            and max_owned_units_per_batch != max_batch_size
        ):
            raise PhaseApplicabilityPlanningError(
                "batch_size_ambiguous",
                "max_owned_units_per_batch 与 max_batch_size 不一致。",
            )
        max_owned_units_per_batch = max_batch_size
    if max_owned_units_per_batch < 1:
        raise PhaseApplicabilityPlanningError(
            "batch_size_invalid",
            "max_owned_units_per_batch 必须为正整数。",
        )
    if context_radius < 0:
        raise PhaseApplicabilityPlanningError(
            "context_radius_invalid",
            "context_radius 不能为负数。",
        )
    if batch_packing_policy not in {
        PHASE_APPLICABILITY_DEFAULT_BATCH_PACKING_POLICY,
        PHASE_APPLICABILITY_SAME_HEADING_BATCH_PACKING_POLICY,
    }:
        raise PhaseApplicabilityPlanningError(
            "batch_packing_policy_invalid",
            "不支持的期别语义批次打包策略。",
        )
    if coverage_manifest.study_phase == StudyPhase.OTHER:
        raise PhaseApplicabilityPlanningError(
            "phase_invalid",
            "期别适用性批次必须绑定 II 期、III 期或无缝 II/III 期。",
        )

    units = _ordered_units(coverage_manifest)
    catalog = build_phase_applicability_context_catalog(coverage_manifest)
    chunks = _build_phase_applicability_chunks(
        units,
        catalog,
        study_phase=coverage_manifest.study_phase,
        max_owned_units_per_batch=max_owned_units_per_batch,
        context_radius=context_radius,
        batch_packing_policy=batch_packing_policy,
    )

    packages: list[PhaseApplicabilityFrozenPackage] = []
    total = len(chunks)
    for ordinal, (owned, context) in enumerate(chunks, start=1):
        owned_ids = [unit.structure_unit_id for unit in owned]
        package_spans = sorted(
            {span_id for unit in (*owned, *context) for span_id in unit.source_span_ids}
        )
        packages.append(
            PhaseApplicabilityFrozenPackage(
                package_id=stable_phase_applicability_package_id(
                    coverage_manifest.manifest_id,
                    ordinal,
                    owned_ids,
                ),
                coverage_manifest_id=coverage_manifest.manifest_id,
                protocol_version_id=coverage_manifest.protocol_version_id,
                protocol_document_sha256=coverage_manifest.protocol_document_sha256,
                snapshot_id=coverage_manifest.snapshot_id,
                package_ordinal=ordinal,
                selected_phase=coverage_manifest.study_phase,
                opposite_phase=(
                    StudyPhase.PHASE_III
                    if coverage_manifest.study_phase == StudyPhase.PHASE_II
                    else StudyPhase.PHASE_II
                    if coverage_manifest.study_phase == StudyPhase.PHASE_III
                    else None
                ),
                owned_units=list(owned),
                context_units=list(context),
                frozen_source_span_ids=package_spans,
            )
        )

    expected_ids = [
        unit.structure_unit_id
        for unit in units
        if not _is_structurally_explicit(unit, coverage_manifest.study_phase)
    ]
    package_ids = [package.package_id for package in packages]
    return PhaseApplicabilityFrozenPlan(
        plan_id=_stable_plan_id(
            coverage_manifest.manifest_id,
            max_owned_units_per_batch,
            context_radius,
            batch_packing_policy,
            package_ids,
        ),
        coverage_manifest_id=coverage_manifest.manifest_id,
        protocol_version_id=coverage_manifest.protocol_version_id,
        study_phase=coverage_manifest.study_phase,
        max_owned_units_per_batch=max_owned_units_per_batch,
        context_radius=context_radius,
        batch_packing_policy=batch_packing_policy,
        expected_structure_unit_ids=expected_ids,
        packages=packages,
    )


build_phase_applicability_plan = plan_phase_applicability_batches
build_phase_applicability_batches = plan_phase_applicability_batches
plan_phase_applicability_packages = plan_phase_applicability_batches
build_phase_applicability_frozen_packages = plan_phase_applicability_batches
