"""Production step executor for ``protocol_deconstruction`` durable jobs.

Dispatches by ``StepContext.step_id``, reads prior checkpoints from the job
store, and returns only the current step checkpoint payload. User-boundary
steps defer with recoverable retry until the workbench API completes them.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.agents.protocol_deconstructor import (
    ProtocolAgentCallError,
    ProtocolAgentResponse,
    ProtocolDeconstructorRunner,
    protocol_prompt_template_sha256,
)
from app.config import DEEPSEEK_API_KEY
from app.domain.contracts.agents import PromptVersion
from app.domain.contracts.enums import AgentNode, ExtractionStatus, PhaseScope, RenderStatus, StudyPhase
from app.domain.contracts.protocol_ingestion import (
    ProtocolExtractionSnapshot,
    ProtocolSourceArtifact,
    ProtocolSourceSpan,
)
from app.domain.contracts.protocol_metadata import (
    ProtocolIdentityDecision,
    StudyPhaseSelection,
)
from app.protocols.deconstruction_gate import ProtocolDeconstructionGate
from app.protocols.deconstruction_service import (
    ProtocolDeconstructionInputAssemblyError,
    ProtocolDeconstructionInputAssembler,
    ProtocolDeconstructionInputPackage,
)
from app.protocols.docx_structure import (
    StructureBlock,
    StructureExtractionError,
    extract_docx_structure,
)
from app.protocols.ingestion import SourceIngestionError
from app.protocols.metadata import (
    MetadataExtractionError,
    extract_protocol_metadata,
    resolve_protocol_identity,
)
from app.protocols.phase_detection import build_phase_applicability_graph
from app.protocols.rendering import pdf_page_texts, render_to_pdf
from app.protocols.source_alignment import AlignmentResult, align_blocks
from app.services.protocol_draft_service import ProtocolDraftService
from app.services.protocol_workbench_service import (
    PROTOCOL_DECONSTRUCTION_STEPS,
    STEP_AWAIT_IDENTITY,
    STEP_AWAIT_REVIEW,
    STEP_EXTRACT,
    STEP_GENERATE,
    STEP_IDENTIFY,
    STEP_INTEGRITY,
    STEP_PUBLISH,
    STEP_REGISTER,
    STEP_RENDER,
)
from app.storage.codecs import utc_now
from app.storage.config import DataPaths
from app.storage.repositories import ProtocolDraftRevisionRepository
from app.workflow.errors import StepFailure
from app.workflow.jobstore import JobStore
from app.workflow.runner import StepContext, StepExecutor

_DEFAULT_PROMPT = (
    "请以资深临床试验医学监查人员的专业语义解构本次已确认期别的正式研究方案。"
    "逐条保留官方父规则，准确表达每个必要条件、替代条件、例外、时间锚点、专业判断，"
    "并把基线及以前每个必做项目映射到其独立审核节点。"
)

_CHECKPOINT_ORDER: tuple[str, ...] = tuple(
    step.step_id for step in PROTOCOL_DECONSTRUCTION_STEPS
)

Now = Callable[[], datetime]


@dataclass
class ProtocolDeconstructionExecutorConfig:
    """Injectable production/test configuration for the protocol executor."""

    data_paths: DataPaths
    session_factory: sessionmaker[Session]
    now: Now = utc_now
    transport: Any | None = None
    transport_factory: Callable[[], Any] | None = None
    prompt_template: str = _DEFAULT_PROMPT
    page_texts_builder: Callable[[tuple[StructureBlock, ...]], list[str]] | None = None
    draft_response_builder: Callable[[ProtocolDeconstructionInputPackage], str] | None = None
    gate: ProtocolDeconstructionGate | None = None


def create_protocol_deconstruction_executor(
    config: ProtocolDeconstructionExecutorConfig,
) -> StepExecutor:
    """Build the ``protocol_deconstruction`` step executor."""

    def execute(context: StepContext) -> dict[str, Any]:
        if context.last_checkpoint is not None:
            return dict(context.last_checkpoint)
        handlers = {
            STEP_REGISTER: lambda ctx: _handle_register(ctx, config),
            STEP_EXTRACT: lambda ctx: _handle_extract(ctx, config),
            STEP_RENDER: lambda ctx: _handle_render(ctx, config),
            STEP_IDENTIFY: lambda ctx: _handle_identify(ctx, config),
            STEP_GENERATE: lambda ctx: _handle_generate(ctx, config),
            STEP_INTEGRITY: lambda ctx: _handle_integrity(ctx, config),
        }
        try:
            handler = handlers.get(context.step_id)
            if handler is None:
                raise StepFailure(
                    retryable=False,
                    error_code="STEP_UNSUPPORTED",
                    detail="当前解构阶段暂时无法自动执行，请刷新任务状态或联系维护人员。",
                )
            return handler(context)
        except StepFailure:
            raise
        except StructureExtractionError as exc:
            raise StepFailure(
                retryable=False,
                error_code="STRUCTURE_EXTRACTION_FAILED",
                detail=f"方案结构读取未完成：{exc}",
            ) from exc
        except MetadataExtractionError as exc:
            raise StepFailure(
                retryable=False,
                error_code="METADATA_EXTRACTION_FAILED",
                detail=f"方案元信息识别未完成：{exc}",
            ) from exc
        except ProtocolDeconstructionInputAssemblyError as exc:
            raise StepFailure(
                retryable=False,
                error_code="INPUT_ASSEMBLY_FAILED",
                detail=f"方案输入组装未完成：{exc}",
            ) from exc
        except SourceIngestionError as exc:
            raise StepFailure(
                retryable=False,
                error_code="SOURCE_UNAVAILABLE",
                detail=f"无法读取已登记的方案文件：{exc}",
            ) from exc

    return execute


def _merged_prior_checkpoints(
    config: ProtocolDeconstructionExecutorConfig,
    job_id: str,
    *,
    before_step: str | None = None,
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    with config.session_factory() as session:
        store = JobStore(session, now=config.now)
        for step_id in _CHECKPOINT_ORDER:
            if before_step is not None and step_id == before_step:
                break
            checkpoint = store.get_last_checkpoint(job_id, step_id)
            if checkpoint is None:
                continue
            _, payload = checkpoint
            merged.update(
                {key: value for key, value in payload.items() if key != "attempt"}
            )
    return merged


def _artifact_from_checkpoint(merged: dict[str, Any]) -> ProtocolSourceArtifact:
    storage_ref = merged.get("storage_ref")
    if not storage_ref:
        raise StepFailure(
            retryable=False,
            error_code="SOURCE_REFERENCE_MISSING",
            detail="已登记方案缺少存储引用，无法在不依赖原始上传路径的情况下继续解构。",
        )
    uploaded_at = merged.get("uploaded_at")
    if isinstance(uploaded_at, str):
        uploaded_at = datetime.fromisoformat(uploaded_at)
    if uploaded_at is None:
        uploaded_at = utc_now()
    return ProtocolSourceArtifact(
        source_artifact_id=str(merged["source_artifact_id"]),
        file_name=str(merged.get("file_name") or "protocol.docx"),
        sha256=str(merged["sha256"]),
        mime_type=str(merged.get("mime_type") or ""),
        size_bytes=int(merged.get("size_bytes") or 0),
        storage_ref=str(storage_ref),
        uploaded_at=uploaded_at,
    )


def _source_path(config: ProtocolDeconstructionExecutorConfig, artifact: ProtocolSourceArtifact) -> Path:
    path = config.data_paths.blobs_dir / artifact.storage_ref
    if not path.is_file():
        raise StepFailure(
            retryable=True,
            error_code="SOURCE_BLOB_MISSING",
            detail="已登记方案副本暂时不可用，请稍后重试；若持续失败，请重新上传方案。",
        )
    return path


def _load_blocks(
    config: ProtocolDeconstructionExecutorConfig,
    snapshot: ProtocolExtractionSnapshot,
) -> tuple[StructureBlock, ...]:
    blob_path = config.data_paths.blobs_dir / snapshot.content_storage_ref
    if not blob_path.is_file():
        raise StepFailure(
            retryable=True,
            error_code="STRUCTURE_BLOB_MISSING",
            detail="方案结构快照暂时不可用，请稍后重试；若持续失败，请重新上传方案。",
        )
    payload = json.loads(blob_path.read_text(encoding="utf-8"))
    return tuple(StructureBlock.model_validate(item) for item in payload)


def _snapshot_from_checkpoint(merged: dict[str, Any]) -> ProtocolExtractionSnapshot:
    raw = merged.get("extraction_snapshot")
    if not raw:
        raise StepFailure(
            retryable=False,
            error_code="SNAPSHOT_MISSING",
            detail="方案结构提取结果尚未写入，无法继续后续步骤。",
        )
    return ProtocolExtractionSnapshot.model_validate(raw)


def _spans_from_checkpoint(merged: dict[str, Any]) -> tuple[ProtocolSourceSpan, ...]:
    raw = merged.get("source_spans") or {}
    if isinstance(raw, list):
        return tuple(ProtocolSourceSpan.model_validate(item) for item in raw)
    return tuple(
        ProtocolSourceSpan.model_validate(value) for value in raw.values()
    )


def _default_page_texts(blocks: tuple[StructureBlock, ...]) -> list[str]:
    parts = [block.text for block in blocks if block.text]
    return ["\n".join(parts)]


def _handle_register(context: StepContext, config: ProtocolDeconstructionExecutorConfig) -> dict[str, Any]:
    # API 写入首个检查点前若 runner 已取得租约，源登记信息仍可从 Job
    # payload 恢复；后续检查点优先覆盖 payload 中的同名字段。
    merged = dict(context.job_payload)
    merged.update(
        _merged_prior_checkpoints(config, context.job_id, before_step=STEP_REGISTER)
    )
    required = ("source_artifact_id", "sha256", "storage_ref")
    if all(merged.get(key) for key in required):
        return {key: merged[key] for key in (*required, "file_name", "mime_type", "size_bytes", "uploaded_at") if key in merged}
    raise StepFailure(
        retryable=False,
        error_code="REGISTER_INCOMPLETE",
        detail="方案登记信息不完整，无法开始结构提取。",
    )


def _handle_extract(context: StepContext, config: ProtocolDeconstructionExecutorConfig) -> dict[str, Any]:
    merged = _merged_prior_checkpoints(config, context.job_id, before_step=STEP_EXTRACT)
    artifact = _artifact_from_checkpoint(merged)
    source_path = _source_path(config, artifact)
    snapshot_id = f"{context.job_id}-snapshot"
    try:
        extraction = extract_docx_structure(
            source_path,
            snapshot_id=snapshot_id,
            source_artifact=artifact,
            output_dir=config.data_paths.blobs_dir,
        )
    except StructureExtractionError as exc:
        raise StepFailure(
            retryable=False,
            error_code="STRUCTURE_EXTRACTION_FAILED",
            detail=str(exc),
        ) from exc
    if extraction.snapshot.status != ExtractionStatus.COMPLETED:
        raise StepFailure(
            retryable=False,
            error_code="STRUCTURE_NEEDS_REVIEW",
            detail="方案结构提取需要人工核对，暂不能自动进入下一步。",
        )
    return {
        "snapshot_id": extraction.snapshot.snapshot_id,
        "extraction_snapshot": extraction.snapshot.model_dump(mode="json"),
        "content_storage_ref": extraction.snapshot.content_storage_ref,
        "content_sha256": extraction.snapshot.content_sha256,
        "block_count": len(extraction.blocks),
    }


def _handle_render(context: StepContext, config: ProtocolDeconstructionExecutorConfig) -> dict[str, Any]:
    merged = _merged_prior_checkpoints(config, context.job_id, before_step=STEP_RENDER)
    artifact = _artifact_from_checkpoint(merged)
    snapshot = _snapshot_from_checkpoint(merged)
    blocks = _load_blocks(config, snapshot)
    source_path = _source_path(config, artifact)
    render_artifact_id = f"{context.job_id}-render"

    if config.page_texts_builder is not None:
        page_texts = config.page_texts_builder(blocks)
        render_status = RenderStatus.SUCCEEDED.value
        pdf_sha256 = None
        page_count = 1
    else:
        render_dir = config.data_paths.blobs_dir / "renders" / context.job_id
        rendered = render_to_pdf(
            source_path,
            render_dir,
            source_artifact=artifact,
        )
        if rendered.status not in (RenderStatus.SUCCEEDED, RenderStatus.DEGRADED):
            raise StepFailure(
                retryable=True,
                error_code="RENDER_FAILED",
                detail=(
                    rendered.render_error
                    or "方案渲染暂时失败，请确认本机文档转换组件可用后重试。"
                ),
            )
        if rendered.pdf_path is None:
            raise StepFailure(
                retryable=True,
                error_code="RENDER_FAILED",
                detail="方案渲染未产出可读页面，请稍后重试。",
            )
        page_texts = pdf_page_texts(rendered.pdf_path)
        render_status = rendered.status.value
        pdf_sha256 = rendered.pdf_sha256
        page_count = rendered.page_count

    alignment: AlignmentResult = align_blocks(
        blocks,
        snapshot_id=snapshot.snapshot_id,
        render_artifact_id=render_artifact_id,
        page_texts=page_texts,
    )
    return {
        "render_artifact_id": render_artifact_id,
        "render_status": render_status,
        "pdf_sha256": pdf_sha256,
        "page_count": page_count,
        "aligned_count": alignment.aligned,
        "degraded_count": alignment.degraded,
        "unaligned_count": alignment.unaligned,
        "source_spans": {
            span.source_span_id: span.model_dump(mode="json")
            for span in alignment.spans
        },
    }


def _handle_identify(context: StepContext, config: ProtocolDeconstructionExecutorConfig) -> dict[str, Any]:
    merged = _merged_prior_checkpoints(config, context.job_id, before_step=STEP_IDENTIFY)
    artifact = _artifact_from_checkpoint(merged)
    snapshot = _snapshot_from_checkpoint(merged)
    blocks = _load_blocks(config, snapshot)
    spans = _spans_from_checkpoint(merged)
    spans_by_ref = {span.source_ref: span.source_span_id for span in spans}

    phase_detection = build_phase_applicability_graph(
        blocks,
        snapshot_id=snapshot.snapshot_id,
        source_span_ids=spans_by_ref,
    )
    metadata = extract_protocol_metadata(
        blocks,
        snapshot_id=snapshot.snapshot_id,
        file_name=artifact.file_name,
        source_spans={span.source_span_id: span for span in spans},
    )
    identity = resolve_protocol_identity(
        metadata,
        identity_decision_id=f"{context.job_id}-identity",
    )
    phase_candidates = [
        {
            "candidate_id": candidate.candidate_id,
            "phase": _phase_label_from_scopes(candidate.phase_scopes),
            "excerpt": candidate.excerpt,
        }
        for candidate in phase_detection.phase_candidates
        if _phase_label_from_scopes(candidate.phase_scopes) is not None
    ]
    return {
        "snapshot_id": snapshot.snapshot_id,
        "awaiting_user": "identity",
        "identity_decision": identity.model_dump(mode="json"),
        "phase_candidates": phase_candidates,
        "metadata_candidates": [
            item.model_dump(mode="json") for item in metadata.candidates
        ],
        "metadata_conflicts": [
            item.model_dump(mode="json") for item in metadata.conflicts
        ],
        "metadata_extraction": {
            "snapshot_id": metadata.snapshot_id,
            "candidates": [
                item.model_dump(mode="json") for item in metadata.candidates
            ],
            "conflicts": [
                item.model_dump(mode="json") for item in metadata.conflicts
            ],
        },
        "phase_selection_id": f"{context.job_id}-phase-selection",
        "phase_graph": phase_detection.graph.model_dump(mode="json"),
    }


def _resolve_transport(config: ProtocolDeconstructionExecutorConfig) -> Any:
    if config.transport is not None:
        return config.transport
    if config.transport_factory is not None:
        return config.transport_factory()
    if not DEEPSEEK_API_KEY:
        raise StepFailure(
            retryable=True,
            error_code="SEMANTIC_PROVIDER_UNAVAILABLE",
            detail="方案语义解构服务尚未配置，暂不能生成草稿；请联系维护人员完成模型接入后重试。",
        )
    from app.agents.deepseek_protocol_transport import DeepSeekProtocolAgentTransport

    return DeepSeekProtocolAgentTransport()


def _handle_generate(context: StepContext, config: ProtocolDeconstructionExecutorConfig) -> dict[str, Any]:
    merged = _merged_prior_checkpoints(config, context.job_id, before_step=STEP_GENERATE)
    artifact = _artifact_from_checkpoint(merged)
    snapshot = _snapshot_from_checkpoint(merged)
    blocks = _load_blocks(config, snapshot)
    spans = _spans_from_checkpoint(merged)
    identity = ProtocolIdentityDecision.model_validate(merged["identity_decision"])
    phase_selection = StudyPhaseSelection.model_validate(merged["phase_selection"])
    from app.domain.contracts.protocol_metadata import PhaseApplicabilityGraph

    phase_graph = PhaseApplicabilityGraph.model_validate(merged["phase_graph"])

    project_id = f"draft-project-{context.job_id[:12]}"
    protocol_version_id = f"draft-version-{context.job_id[:12]}"
    package = ProtocolDeconstructionInputAssembler(
        frozen_at=datetime.now(timezone.utc)
    ).assemble(
        project_id=project_id,
        protocol_version_id=protocol_version_id,
        source_artifact=artifact,
        blocks=blocks,
        snapshot=snapshot,
        source_spans=spans,
        phase_graph=phase_graph,
        identity_decision=identity,
        phase_selection=phase_selection,
    )

    prompt_version = PromptVersion(
        prompt_version_id="protocol-deconstructor/v1",
        node=AgentNode.PROTOCOL_DECONSTRUCTOR,
        template_sha256=protocol_prompt_template_sha256(config.prompt_template),
        schema_version_id="protocol-deconstruction-draft/v1",
    )
    if config.draft_response_builder is not None:
        draft_json = config.draft_response_builder(package)
        transport = _FakeSingleResponseTransport(draft_json)
    else:
        transport = _resolve_transport(config)

    runner = ProtocolDeconstructorRunner(gate=config.gate)
    try:
        result = runner.run(
            package.source_input,
            prompt_version=prompt_version,
            prompt_template=config.prompt_template,
            transport=transport,
            source_spans=package.source_spans,
        )
    except ProtocolAgentCallError as exc:
        raise StepFailure(
            retryable=True,
            error_code="SEMANTIC_CALL_FAILED",
            detail=f"方案语义解构调用未完成，请稍后重试。（{exc}）",
        ) from exc

    if result.final_draft is None:
        raise StepFailure(
            retryable=True,
            error_code="SEMANTIC_DRAFT_MISSING",
            detail="方案语义解构尚未产出可用草稿，请稍后重试或联系维护人员。",
        )

    actor = str(context.job_payload.get("actor") or "系统")
    with config.session_factory() as session:
        with session.begin():
            draft_service = ProtocolDraftService(session)
            revision = draft_service.save_initial_draft(
                result.final_draft,
                actor=actor,
                created_at=config.now(),
            )

    gate = result.final_gate_result
    if gate is None:
        gate = (config.gate or ProtocolDeconstructionGate()).evaluate(
            package.source_input,
            result.final_draft,
            source_spans=package.source_spans,
        )

    return {
        "draft_id": revision.draft_id,
        "draft_revision_id": revision.revision_id,
        "draft_status": revision.status.value,
        "semantic_status": result.status,
        "source_input": package.source_input.model_dump(mode="json"),
        "source_spans": {
            key: span.model_dump(mode="json")
            for key, span in package.source_spans.items()
        },
        "gate_result": gate.model_dump(mode="json"),
        "publishable": gate.publishable,
    }


def _handle_integrity(context: StepContext, config: ProtocolDeconstructionExecutorConfig) -> dict[str, Any]:
    merged = _merged_prior_checkpoints(config, context.job_id, before_step=STEP_INTEGRITY)
    if merged.get("gate_result"):
        gate_raw = merged["gate_result"]
        return {
            "gate_result": gate_raw,
            "publishable": merged.get("publishable", False),
            "awaiting_user": "review",
        }

    from app.domain.contracts.agent_io import ProtocolDeconstructionInput

    source_input = ProtocolDeconstructionInput.model_validate(merged["source_input"])
    spans = _spans_from_checkpoint(merged)
    with config.session_factory() as session:
        revision = ProtocolDraftRevisionRepository(session).get(
            str(merged["draft_revision_id"])
        )
    gate = (config.gate or ProtocolDeconstructionGate()).evaluate(
        source_input,
        revision.content,
        source_spans={span.source_span_id: span for span in spans},
    )
    return {
        "gate_result": gate.model_dump(mode="json"),
        "publishable": gate.publishable,
        "awaiting_user": "review",
    }


def _phase_label_from_scopes(scopes: list[PhaseScope]) -> str | None:
    scope_set = frozenset(scopes)
    if scope_set == frozenset({PhaseScope.PHASE_II}):
        return StudyPhase.PHASE_II.value
    if scope_set == frozenset({PhaseScope.PHASE_III}):
        return StudyPhase.PHASE_III.value
    if scope_set == frozenset({PhaseScope.PHASE_II, PhaseScope.PHASE_III}):
        return StudyPhase.SEAMLESS_II_III.value
    if PhaseScope.PHASE_II in scope_set and PhaseScope.PHASE_III not in scope_set:
        return StudyPhase.PHASE_II.value
    if PhaseScope.PHASE_III in scope_set and PhaseScope.PHASE_II not in scope_set:
        return StudyPhase.PHASE_III.value
    return None


class _FakeSingleResponseTransport:
    """Test transport returning one pre-built JSON draft response."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.start_prompts: list[str] = []
        self.repair_prompts: list[tuple[str, str]] = []

    def start(self, *, prompt: str) -> ProtocolAgentResponse:
        self.start_prompts.append(prompt)
        return ProtocolAgentResponse(session_id="test-session", text=self._text)

    def continue_session(self, *, session_id: str, prompt: str) -> ProtocolAgentResponse:
        self.repair_prompts.append((session_id, prompt))
        return ProtocolAgentResponse(session_id=session_id, text=self._text)
