"""Source-bound subcrop checks; proposals never qualify clinical facts."""
from __future__ import annotations

from app.domain.contracts.evidence import BoundingBox
from app.domain.contracts.local_region_read import LocalRegionRelativeBox, LocalizedRegionReadCandidate
from app.domain.page_normalization import normalize_text
from app.evidence.local_region_comparison import _plain_table_header, compare_local_region_read, region_ocr_fields


POSITION_TRIAL_VERSION = "local-region-position-trial/v6"


def _literal_crop_agreement(text: str, candidate: LocalizedRegionReadCandidate, index: int) -> bool:
    item = candidate.items[index]
    # This is only a witness for the entire printed transcript, not the
    # assignment of values to columns. Do not remove ordinals, marks or units.
    return (
        len(candidate.items) == 1 and item.script == "printed" and item.legibility == "clear"
        and item.proposed_bbox is not None and item.annotation_target is None
        and len(text.strip().splitlines()) == len(item.excerpt.strip().splitlines()) == 1
        and "<" not in text and ">" not in text
        and " ".join(text.split()) == " ".join(item.excerpt.split())
    )


def proposed_field_bbox(parent: BoundingBox, proposal: LocalRegionRelativeBox) -> BoundingBox:
    """Map relative coordinates to an outward-rounded, source-view pixel crop."""
    edges = (parent.x0, parent.y0, parent.x1, parent.y1)
    if any(not float(edge).is_integer() for edge in edges):
        raise ValueError("项目裁区须以整数像素原图区域为基础")
    x0, y0, x1, y1 = map(int, edges)
    width, height = x1 - x0, y1 - y0
    return BoundingBox(
        x0=x0 + width * proposal.x0 // 1000,
        y0=y0 + height * proposal.y0 // 1000,
        x1=x0 + (width * proposal.x1 + 999) // 1000,
        y1=y0 + (height * proposal.y1 + 999) // 1000,
    )


def compare_single_field_subcrop(text: str, candidate: LocalizedRegionReadCandidate, index: int) -> dict:
    item = candidate.items[index]
    fields, unresolved = region_ocr_fields(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    one_plain_row = (len(lines) == 2 and _plain_table_header(lines[0]) is not None
                     and len(fields) == 1 and lines[1] == fields[0].excerpt)
    # A plausible value somewhere in a crop is not enough. Reject partial
    # free-text extraction and crops containing multiple rows/objects.
    complete_single_field = (
        len(fields) == 1 and not unresolved
        and ("<table" in text.lower() or one_plain_row
             or normalize_text(text) == normalize_text(fields[0].excerpt))
    )
    comparison = compare_local_region_read(
        text, LocalizedRegionReadCandidate(items=[item], unresolved=[]),
    )
    reasons = list(comparison["items"][0]["reasons"])
    if not complete_single_field:
        reasons.append("裁区尚不能完整、唯一地对应一个项目")
    if item.proposed_bbox is None:
        reasons.append("没有可检查的位置提案")
    return {
        "item_index": index, "candidate_only": True,
        "comparison_contract": comparison["contract"],
        "source_position_verified": False, "formal_adoption_authorized": False,
        "single_field_transcription_agreement": not reasons,
        "literal_crop_transcription_agreement": _literal_crop_agreement(text, candidate, index),
        "field_assignment_verified": False,
        "status": "single_field_subcrop_agreement" if not reasons else "unresolved",
        "reasons": reasons,
    }
