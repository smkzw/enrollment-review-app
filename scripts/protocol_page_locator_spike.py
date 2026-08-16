"""Evaluate conservative page hints for unaligned protocol structure blocks.

This is a read-only Phase 3 spike. It renders immutable copies in a temporary
directory, withholds authoritative paragraph locations one at a time, and
measures whether neighbouring authoritative locations in the same structural
container can recover the hidden page. It does not change production spans.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from app.domain.contracts.enums import (
    AlignmentStatus,
    DocumentPart,
    SourceLocatorPrecision,
)
from app.protocols.docx_structure import BlockKind, StructureBlock, extract_docx_structure
from app.protocols.ingestion import register_source_artifact
from app.protocols.rendering import pdf_page_texts, render_to_pdf
from app.protocols.source_alignment import align_blocks


REAL_PROTOCOLS = {
    "MG-K10-SAR": Path(
        "/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/"
        "MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx"
    ),
    "CMS-D001": Path(
        "/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/"
        "CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx"
    ),
}


@dataclass(frozen=True)
class TrialResult:
    max_page_gap: int
    attempted: int
    exact: int
    wrong: int
    ambiguous: int
    accuracy: float
    authoritative_total: int
    unaligned_candidates: int
    unaligned_recoverable: int
    recoverable_rate: float
    page_inversions: int


def _container(block: StructureBlock) -> tuple[object, ...]:
    """Return a deliberately narrow structural neighbourhood.

    Body paragraphs may interpolate only inside one section. Table paragraphs
    must additionally remain inside the same table cell path and top-level
    table. Header/footer text is excluded because it is physically repeated.
    """
    if block.document_part != DocumentPart.BODY:
        return ("excluded", block.source_ref)
    if block.table_path is None:
        return ("body", block.section_index)
    top_table = block.source_ref.split(".", 2)[1]
    return ("table-cell", block.section_index, top_table, block.table_path)


def _authoritative(block: StructureBlock, span) -> bool:
    return (
        block.kind == BlockKind.PARAGRAPH
        and block.document_part == DocumentPart.BODY
        and span.alignment_status == AlignmentStatus.ALIGNED
        and span.precision == SourceLocatorPrecision.TEXT_RANGE
        and span.render_page is not None
    )


def _predict(
    target: StructureBlock,
    anchors: list[tuple[StructureBlock, int]],
    *,
    max_page_gap: int,
    max_block_gap: int = 12,
) -> tuple[int | None, bool]:
    peers = [item for item in anchors if _container(item[0]) == _container(target)]
    previous = [item for item in peers if item[0].block_order < target.block_order]
    following = [item for item in peers if item[0].block_order > target.block_order]
    if not previous or not following:
        return None, False
    left = max(previous, key=lambda item: item[0].block_order)
    right = min(following, key=lambda item: item[0].block_order)
    left_distance = target.block_order - left[0].block_order
    right_distance = right[0].block_order - target.block_order
    if left_distance > max_block_gap or right_distance > max_block_gap:
        return None, False
    left_page, right_page = left[1], right[1]
    if left_page > right_page or right_page - left_page > max_page_gap:
        return None, left_page > right_page
    if left_page == right_page:
        return left_page, False
    if left_distance == right_distance:
        return None, False
    return (left_page if left_distance < right_distance else right_page), False


def _evaluate(label: str, source: Path, work_root: Path) -> dict[str, object]:
    work = work_root / label
    artifact = register_source_artifact(
        source, source_artifact_id=f"{label}-spike", storage_root=work
    )
    extraction = extract_docx_structure(
        source,
        snapshot_id=f"{label}-spike-snapshot",
        source_artifact=artifact,
        output_dir=work,
    )
    rendered = render_to_pdf(source, work / "rendered", source_artifact=artifact)
    if rendered.pdf_path is None:
        raise RuntimeError(f"{label} 渲染失败：{rendered.render_error}")
    pages = pdf_page_texts(rendered.pdf_path)
    alignment = align_blocks(
        extraction.blocks,
        snapshot_id=extraction.snapshot.snapshot_id,
        render_artifact_id=f"{label}-spike-render",
        page_texts=pages,
        recover_page_hints=False,
    )
    pairs = list(zip(extraction.blocks, alignment.spans, strict=True))
    authoritative = [
        (block, span.render_page)
        for block, span in pairs
        if _authoritative(block, span)
    ]
    anchors = [(block, int(page)) for block, page in authoritative]
    unaligned = [
        block
        for block, span in pairs
        if block.kind == BlockKind.PARAGRAPH
        and block.document_part == DocumentPart.BODY
        and span.alignment_status == AlignmentStatus.UNALIGNED
        and block.text.strip()
    ]

    results: list[TrialResult] = []
    for max_page_gap in (0, 1, 2):
        attempted = exact = wrong = ambiguous = inversions = 0
        for hidden, actual_page in anchors:
            remaining = [item for item in anchors if item[0].source_ref != hidden.source_ref]
            predicted, inversion = _predict(
                hidden, remaining, max_page_gap=max_page_gap
            )
            inversions += int(inversion)
            if predicted is None:
                ambiguous += 1
                continue
            attempted += 1
            if predicted == actual_page:
                exact += 1
            else:
                wrong += 1

        recoverable = 0
        unaligned_inversions = 0
        for block in unaligned:
            predicted, inversion = _predict(
                block, anchors, max_page_gap=max_page_gap
            )
            recoverable += int(predicted is not None)
            unaligned_inversions += int(inversion)
        inversions += unaligned_inversions
        results.append(
            TrialResult(
                max_page_gap=max_page_gap,
                attempted=attempted,
                exact=exact,
                wrong=wrong,
                ambiguous=ambiguous,
                accuracy=round(exact / attempted, 6) if attempted else 0.0,
                authoritative_total=len(anchors),
                unaligned_candidates=len(unaligned),
                unaligned_recoverable=recoverable,
                recoverable_rate=(
                    round(recoverable / len(unaligned), 6) if unaligned else 0.0
                ),
                page_inversions=inversions,
            )
        )

    return {
        "protocol": label,
        "pages": len(pages),
        "blocks": len(extraction.blocks),
        "alignment": {
            "aligned": alignment.aligned,
            "degraded": alignment.degraded,
            "unaligned": alignment.unaligned,
        },
        "authoritative_container_counts": dict(
            Counter(str(_container(block)) for block, _page in anchors)
        ),
        "trials": [asdict(item) for item in results],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    missing = [str(path) for path in REAL_PROTOCOLS.values() if not path.is_file()]
    if missing:
        raise SystemExit("真实方案文件缺失：" + "；".join(missing))
    with tempfile.TemporaryDirectory(prefix="protocol-page-spike-") as temp:
        reports = [
            _evaluate(label, path, Path(temp))
            for label, path in REAL_PROTOCOLS.items()
        ]
    payload = {
        "purpose": "Phase 3 页码定位恢复只读留一验证",
        "authority_rule": (
            "插值结果始终为降级定位提示，不得满足来源覆盖门槛；"
            "只有原始唯一文本范围与唯一表格页定位是正式来源定位。"
        ),
        "reports": reports,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
