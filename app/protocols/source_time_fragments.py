"""Literal source time cues, without interpreting their clinical scope."""

from __future__ import annotations

import re
import unicodedata

from app.domain.contracts.enums import ReviewStage


STUDY_PERIOD_SOURCE_PATTERN = re.compile(
    r"(?:(?:试验|研究)(?:期间|过程中)|整个试验|整个研究|至(?:试验|研究)结束|"
    r"until\s+(?:study\s+)?completion|throughout\s+the\s+study)",
    re.IGNORECASE,
)
TREATMENT_PERIOD_SOURCE_PATTERN = re.compile(
    r"(?:治疗期(?:间|内)?|(?:治疗|用药|给药)过程中|用药期间|给药期间|during\s+(?:the\s+)?treatment)",
    re.IGNORECASE,
)


_COMBINED_SCREENING_RUN_IN = re.compile(r"(?:筛选\s*[/／]\s*导入|导入\s*[/／]\s*筛选)期")


def frozen_review_stage_aliases(source) -> dict[ReviewStage, ReviewStage]:
    """Resolve a joint visit name only when its frozen source is unambiguous."""

    materials = {item.source_span_id: item for item in source.source_materials}
    if len(materials) != len(source.source_materials):
        return {}
    catalog = source.required_procedure_catalog
    if not catalog.visit_tables:
        return {}
    from app.protocols.procedure_catalog import _derive_visit_stage, _without_display_footnotes
    joint_visits = []
    inventoried_visits = set()
    for table in catalog.visit_tables:
        root = materials.get(table.table_source_span_id)
        if root is None:
            return {}
        for column in table.columns:
            if not column.source_span_ids or not column.visit_instance:
                return {}
            for ref, excerpt in zip(column.source_span_ids, column.source_excerpts, strict=True):
                material = materials.get(ref)
                if (material is None or material.text != excerpt or excerpt not in root.text
                        or not material.source_ref.startswith(root.source_ref + ".r")):
                    return {}
            cells: dict[str, list[str]] = {}
            for ref, excerpt in zip(column.source_span_ids, column.source_excerpts, strict=True):
                cells.setdefault(materials[ref].source_ref.rpartition(".p")[0], []).append(excerpt)
            projected = " / ".join(dict.fromkeys(_without_display_footnotes("\n".join(values))
                                                 for values in cells.values()))
            derived = _derive_visit_stage(projected)
            if projected != column.visit_instance or derived is None:
                return {}
            canonical = derived if isinstance(derived, ReviewStage) else None
            if canonical != column.review_stage or canonical == ReviewStage.SCREENING:
                return {}
            inventoried_visits.add((column.visit_instance, column.review_stage))
            if _COMBINED_SCREENING_RUN_IN.search(projected):
                # A single cell may itself contain several headers. Do not let
                # the winning stage conceal a separate screening occurrence.
                if _derive_visit_stage(_COMBINED_SCREENING_RUN_IN.sub("", projected)) == ReviewStage.SCREENING:
                    return {}
                if canonical != ReviewStage.RUN_IN:
                    return {}
                joint_visits.append(column.visit_instance)
    if len(joint_visits) != 1:
        return {}
    if any((item.visit_instance, item.review_stage) not in inventoried_visits for item in catalog.items):
        return {}
    if any(item.visit_instance == joint_visits[0] and item.review_stage != ReviewStage.RUN_IN
           for item in catalog.items):
        return {}
    if not any(item.visit_instance == joint_visits[0] for item in catalog.items):
        return {}
    return {ReviewStage.SCREENING: ReviewStage.RUN_IN}


_QUANTITY = (
    r"(?:\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万半]+"
    r"(?:点[零〇一二三四五六七八九]+)?|one|two|three|four|five|six|seven|"
    r"eight|nine|ten|half|an?)"
)
_INTRADAY_DURATION = re.compile(
    rf"(?<![A-Za-z]){_QUANTITY}\s*[-－]?\s*"
    r"(?:小时|钟头|分钟|hours?|hrs?|h|minutes?|mins?)(?![A-Za-z])",
    re.IGNORECASE,
)


def intraday_time_fragments(text: str) -> list[str]:
    """Return normalized literal fragments; absence is not proof of completeness."""

    source = unicodedata.normalize("NFKC", text)
    titles = list(re.finditer(r"《[^》]*》", source))
    return sorted({
        re.sub(r"\s+", "", match.group())
        for match in _INTRADAY_DURATION.finditer(source)
        if not any(title.start() <= match.start() < title.end() for title in titles)
    })
