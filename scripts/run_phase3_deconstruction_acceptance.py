#!/usr/bin/env python3
"""Run reproducible Phase 3 deconstruction acceptance on real protocols."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agents.protocol_semantic_transport import DeepSeekProtocolAgentTransport
from app.agents.protocol_deconstructor import (
    ProtocolDeconstructorRunner,
    protocol_prompt_template_sha256,
)
from app.domain.contracts.agents import PromptVersion
from app.domain.contracts.enums import (
    AgentNode,
    MetadataResolutionStatus,
    PhaseScope,
    StudyPhase,
)
from app.domain.contracts.protocol_metadata import StudyPhaseSelection
from app.protocols.deconstruction_service import ProtocolDeconstructionInputAssembler
from app.protocols.docx_structure import extract_docx_structure
from app.protocols.ingestion import register_source_artifact
from app.protocols.metadata import extract_protocol_metadata, resolve_protocol_identity
from app.protocols.phase_detection import build_phase_applicability_graph
from app.protocols.rendering import pdf_page_texts, render_to_pdf
from app.protocols.source_alignment import align_blocks


DEFAULT_OUTPUT = (
    ROOT
    / ".trellis/tasks/08-14-phase3-protocol-deconstruction/metrics/real-agent-acceptance"
)
PROMPT_TEMPLATE = (
    "请以资深临床试验医学监查人员的专业语义解构本次已确认期别的正式研究方案。"
    "逐条保留官方父规则，准确表达每个必要条件、替代条件、例外、时间锚点、专业判断，"
    "并把基线及以前每个必做项目映射到其独立审核节点。"
)
PROTOCOLS = {
    "mg-iii": {
        "path": Path(
            "/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/"
            "MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx"
        ),
        "phase": StudyPhase.PHASE_III,
        "expected_parent": {"IN": 7, "EX": 16},
        "expected_procedure": 41,
    },
    "d001-ii": {
        "path": Path(
            "/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/"
            "CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx"
        ),
        "phase": StudyPhase.PHASE_II,
        "expected_parent": {"IN": 6, "EX": 30},
        "expected_procedure": 50,
    },
}


def _json_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _source_state(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _build_package(name: str, work_dir: Path):
    config = PROTOCOLS[name]
    path = config["path"]
    phase = config["phase"]
    if not isinstance(path, Path) or not path.is_file():
        raise FileNotFoundError(f"真实方案不存在：{path}")
    if not isinstance(phase, StudyPhase):
        raise TypeError("真实方案期别配置无效")

    now = datetime.now(timezone.utc)
    artifact = register_source_artifact(
        path,
        source_artifact_id=f"phase3-acceptance-{name}",
        storage_root=work_dir,
    )
    extraction = extract_docx_structure(
        path,
        snapshot_id=f"phase3-acceptance-{name}-snapshot",
        source_artifact=artifact,
        output_dir=work_dir,
    )
    rendered = render_to_pdf(path, work_dir / "rendered", source_artifact=artifact)
    if rendered.status.value != "succeeded" or rendered.pdf_path is None:
        raise RuntimeError(f"方案渲染失败：{rendered.render_error}")
    alignment = align_blocks(
        extraction.blocks,
        snapshot_id=extraction.snapshot.snapshot_id,
        render_artifact_id=f"phase3-acceptance-{name}-render",
        page_texts=pdf_page_texts(rendered.pdf_path),
    )
    detection = build_phase_applicability_graph(
        extraction.blocks,
        snapshot_id=extraction.snapshot.snapshot_id,
        source_span_ids={span.source_ref: span.source_span_id for span in alignment.spans},
    )
    metadata = extract_protocol_metadata(
        extraction.blocks,
        snapshot_id=extraction.snapshot.snapshot_id,
        file_name=path.name,
    )
    identity = resolve_protocol_identity(
        metadata,
        identity_decision_id=f"phase3-acceptance-{name}-identity",
        study_phase=phase,
    )
    candidate_ids = [
        candidate.candidate_id
        for candidate in detection.phase_candidates
        if (
            phase == StudyPhase.PHASE_II
            and PhaseScope.PHASE_II in candidate.phase_scopes
        )
        or (
            phase == StudyPhase.PHASE_III
            and PhaseScope.PHASE_III in candidate.phase_scopes
        )
    ]
    selection = StudyPhaseSelection(
        selection_id=f"phase3-acceptance-{name}-selection",
        snapshot_id=extraction.snapshot.snapshot_id,
        selected_phase=phase,
        candidate_ids=candidate_ids[:1] or [f"phase3-acceptance-{name}-candidate"],
        status=MetadataResolutionStatus.CONFIRMED,
        confirmed_by="Phase 3 真实方案验收",
        confirmed_at=now,
    )
    return ProtocolDeconstructionInputAssembler(frozen_at=now).assemble(
        project_id=f"phase3-acceptance-{name}-project",
        protocol_version_id=f"phase3-acceptance-{name}-version",
        source_artifact=artifact,
        extraction=extraction,
        alignment=alignment,
        phase_detection=detection,
        identity_decision=identity,
        phase_selection=selection,
    )


def _catalog_counts(package) -> dict[str, int]:
    codes = [item.official_code or "" for item in package.parent_rule_catalog.items]
    return {
        "IN": sum(code.startswith("IN-") for code in codes),
        "EX": sum(code.startswith("EX-") for code in codes),
    }


def run(name: str, *, output_dir: Path, build_only: bool) -> dict[str, object]:
    config = PROTOCOLS[name]
    source_path = config["path"]
    if not isinstance(source_path, Path):
        raise TypeError("真实方案路径配置无效")
    source_before = _source_state(source_path)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix=f"phase3-{name}-") as temp:
        package = _build_package(name, Path(temp))
        source_input = package.source_input
        prompt_chars = len(
            json.dumps(source_input.model_dump(mode="json"), ensure_ascii=False)
        )
        summary: dict[str, object] = {
            "protocol": name,
            "phase": source_input.selected_phase.value,
            "identity": source_input.identity_decision.model_dump(mode="json"),
            "parent_counts": _catalog_counts(package),
            "parent_total": len(package.parent_rule_catalog.items),
            "procedure_total": len(package.required_procedure_catalog.items),
            "source_material_total": len(source_input.source_materials),
            "allowed_source_total": len(source_input.allowed_source_span_ids),
            "prompt_payload_characters": prompt_chars,
            "source_unchanged": _source_state(source_path) == source_before,
            "build_seconds": round(time.monotonic() - started, 3),
        }
        if summary["parent_counts"] != config["expected_parent"]:
            raise RuntimeError(f"{name} 父规则目录数量与冻结验收值不一致：{summary}")
        if summary["procedure_total"] != config["expected_procedure"]:
            raise RuntimeError(f"{name} 必做项目录数量与冻结验收值不一致：{summary}")
        _json_write(output_dir / name / "input-summary.json", summary)
        if build_only:
            return summary

        prompt_version = PromptVersion(
            prompt_version_id="protocol-deconstructor/phase3-v1",
            node=AgentNode.PROTOCOL_DECONSTRUCTOR,
            template_sha256=protocol_prompt_template_sha256(PROMPT_TEMPLATE),
            schema_version_id="protocol-deconstruction-draft/v1",
        )
        transport = DeepSeekProtocolAgentTransport()
        agent_started = time.monotonic()
        result = ProtocolDeconstructorRunner().run(
            source_input,
            prompt_version=prompt_version,
            prompt_template=PROMPT_TEMPLATE,
            transport=transport,
            source_spans=package.source_spans,
        )
        summary.update(
            {
                "agent_seconds": round(time.monotonic() - agent_started, 3),
                "status": result.status,
                "attempt_count": len(result.attempts),
                "session_id": result.same_session_id,
                "issue_codes_by_attempt": [
                    [issue.issue_code for issue in attempt.issues]
                    for attempt in result.attempts
                ],
                "source_unchanged_after_agent": _source_state(source_path)
                == source_before,
            }
        )
        _json_write(output_dir / name / "acceptance-summary.json", summary)
        _json_write(
            output_dir / name / "run-result.json",
            result.model_dump(mode="json"),
        )
        if result.final_draft is not None:
            _json_write(
                output_dir / name / "final-draft.json",
                result.final_draft.model_dump(mode="json"),
            )
        _json_write(
            output_dir / name / "conversation.json",
            list(transport.history(result.same_session_id)),
        )
        return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "protocol",
        choices=[*PROTOCOLS, "all"],
        help="要验收的真实方案与期别",
    )
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    targets = list(PROTOCOLS) if args.protocol == "all" else [args.protocol]
    results = [
        run(name, output_dir=args.output_dir, build_only=args.build_only)
        for name in targets
    ]
    print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
