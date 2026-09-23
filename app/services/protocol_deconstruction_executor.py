"""Production step executor for ``protocol_deconstruction`` durable jobs.

Dispatches by ``StepContext.step_id``, reads prior checkpoints from the job
store, and returns only the current step checkpoint payload. User-boundary
steps defer with recoverable retry until the workbench API completes them.
"""
from __future__ import annotations

import hashlib
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
    ProtocolDeconstructionAttempt,
    ProtocolDeconstructionRunResult,
    ProtocolDeconstructorRunner,
    ProtocolSemanticBatchCache,
    build_protocol_deconstruction_prompt,
    protocol_prompt_template_sha256,
)
from app.agents.protocol_semantic_model_router import (
    ProtocolSemanticRouteAttemptRecord,
    ProtocolSemanticRouteAudit,
    build_transport_for_candidate,
    candidate_availability_error,
    classify_protocol_semantic_task_grade,
    dumps_route_audit,
    resolve_route_mode,
    route_failure_detail,
    semantic_repair_limit_for_candidate,
    select_protocol_semantic_route_candidates,
    summarize_run_result_for_route,
)
from app.config import DECONSTRUCT_BACKEND, DECONSTRUCT_ROUTE_MODE, DEEPSEEK_API_KEY
from app.domain.contracts.agents import PromptVersion
from app.domain.contracts.agent_io import ProtocolDeconstructionInput
from app.domain.contracts.enums import (
    AgentNode,
    ExtractionStatus,
    JobEventType,
    PhaseScope,
    RenderStatus,
    StudyPhase,
)
from app.domain.contracts.protocol_ingestion import (
    ProtocolExtractionSnapshot,
    ProtocolSourceArtifact,
    ProtocolSourceSpan,
)
from app.domain.contracts.protocol_metadata import (
    PhaseApplicabilityGraph,
    PhaseProjection,
    ProtocolIdentityDecision,
    StudyPhaseSelection,
)
from app.protocols.deconstruction_gate import (
    DECONSTRUCTION_GATE_VERSION,
    ProtocolDeconstructionGate,
    ProtocolGateIssue,
)
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
from app.protocols.ingestion import (
    ProtocolFileKind,
    SourceIngestionError,
    detect_format,
)
from app.protocols.metadata import (
    MetadataExtractionError,
    extract_protocol_metadata,
    resolve_protocol_identity,
)
from app.protocols.phase_detection import build_phase_applicability_graph
from app.protocols.rendering import RenderingError, pdf_page_texts, render_to_pdf
from app.protocols.source_alignment import AlignmentResult, align_blocks
from app.services.protocol_draft_service import ProtocolDraftService
from app.services.protocol_workbench_service import (
    PROTOCOL_DECONSTRUCTION_STEPS,
    STEP_AWAIT_IDENTITY,
    STEP_AWAIT_REVIEW,
    STEP_EXTRACT,
    STEP_FREEZE,
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


class _ProtocolSemanticBatchFileCache(ProtocolSemanticBatchCache):
    """Job-scoped, content-addressed cache for validated semantic batches."""

    def __init__(self, data_paths: DataPaths, job_id: str) -> None:
        self._data_paths = data_paths
        self._root = data_paths.blobs_dir / "protocol-semantic-batches" / job_id

    def _path(self, cache_key: str) -> Path:
        if len(cache_key) != 64 or any(
            char not in "0123456789abcdef" for char in cache_key
        ):
            raise ValueError("方案语义批次缓存标识无效")
        return self._root / f"{cache_key}.json"

    def load(self, cache_key: str) -> str | None:
        path = self._path(cache_key)
        if not path.is_file() or path.is_symlink():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            response_text = payload["response_text"]
            if payload.get("cache_key") != cache_key or not isinstance(
                response_text, str
            ):
                return None
            if hashlib.sha256(response_text.encode("utf-8")).hexdigest() != payload.get(
                "response_sha256"
            ):
                return None
            return response_text
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def store(
        self,
        cache_key: str,
        response_text: str,
        *,
        cache_contract: str = "protocol-semantic-batch/v1",
    ) -> None:
        payload = {
            "cache_contract": cache_contract,
            "cache_key": cache_key,
            "response_sha256": hashlib.sha256(
                response_text.encode("utf-8")
            ).hexdigest(),
            "response_text": response_text,
        }
        self._data_paths.boundary.atomic_write_bytes(
            self._path(cache_key),
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
        )


SEMANTIC_PREVIEW_CONTRACT = "protocol-semantic-preview/v1"


def _semantic_preview_path(data_paths: DataPaths, job_id: str) -> Path:
    return data_paths.blobs_dir / "protocol-semantic-preview" / job_id / "partial-candidate.json"


def _persist_semantic_batch_progress(
    config: ProtocolDeconstructionExecutorConfig,
    job_id: str,
    batch_index: int,
    batch_total: int,
    candidate: Any,
) -> None:
    """逐批持久化已验证语义候选：预览文件 + 任务进度事件（只读投影，非正式草稿）。

    与批缓存不同，这里保存的是“截至本批的合并候选”，供工作台在生成期间
    只读预览；发布权威仍只来自完整运行结束后的不可变草稿 revision。
    """
    candidate_payload = candidate.model_dump(mode="json")
    rule_codes = [rule.official_code for rule in candidate.proposed_rules]
    record = {
        "contract": SEMANTIC_PREVIEW_CONTRACT,
        "job_id": job_id,
        "batch_index": batch_index,
        "batch_total": batch_total,
        "updated_at": config.now().isoformat(),
        "rule_codes": rule_codes,
        "rule_count": len(rule_codes),
        "unresolved_count": len(candidate.unresolved_items),
        "candidate": candidate_payload,
    }
    path = _semantic_preview_path(config.data_paths, job_id)
    config.data_paths.boundary.atomic_write_bytes(
        path,
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )
    with config.session_factory() as session, session.begin():
        store = JobStore(session, now=config.now)
        store.append_event(
            store.make_event(
                job_id=job_id,
                event_type=JobEventType.SEMANTIC_BATCH_PROGRESS,
                step_id=STEP_GENERATE,
                progress_completed=batch_index,
                progress_total=batch_total,
                payload={
                    "进度说明": f"已生成语义批次 {batch_index}/{batch_total}（{len(rule_codes)} 条父规则已有候选）",
                    "规则编号": rule_codes,
                    "未决数": len(candidate.unresolved_items),
                },
            )
        )


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
            STEP_FREEZE: lambda ctx: _handle_freeze(ctx, config),
            STEP_GENERATE: lambda ctx: _handle_generate(ctx, config),
            STEP_INTEGRITY: lambda ctx: _handle_integrity(ctx, config),
        }
        try:
            from app.llm.mtplx_model_lifecycle import MtplxOwnershipError, require_local_deployment_job

            try:
                require_local_deployment_job(context.job_payload)
            except MtplxOwnershipError as exc:
                raise StepFailure(retryable=False, error_code="MODEL_DEPLOYMENT_CHANGED", detail=str(exc)) from exc
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
    # 方案 PDF 上传入口已下线：仅 DOCX 具备原生结构通道；历史任务或被篡改的
    # 登记格式不得回落到纯文本猜测。
    _mime, kind = detect_format(source_path)
    if kind != ProtocolFileKind.DOCX:
        raise StepFailure(
            retryable=False,
            error_code="UNSUPPORTED_STRUCTURE_FORMAT",
            detail=(
                f"方案结构提取仅支持 DOCX，检测到 {kind.value}：{source_path}；"
                "方案 PDF 上传入口已下线，请以 DOCX 重新上传正式方案。"
            ),
        )
    try:
        extraction = extract_docx_structure(
            source_path,
            snapshot_id=snapshot_id,
            source_artifact=artifact,
            output_dir=config.data_paths.blobs_dir,
        )
    except SourceIngestionError as exc:
        raise StepFailure(
            retryable=False,
            error_code="STRUCTURE_EXTRACTION_FAILED",
            detail=f"方案结构读取未完成：{exc}",
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
        render_kind = "test_page_texts"
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
        render_kind = "libreoffice"

    alignment: AlignmentResult = align_blocks(
        blocks,
        snapshot_id=snapshot.snapshot_id,
        render_artifact_id=render_artifact_id,
        page_texts=page_texts,
    )
    return {
        "render_artifact_id": render_artifact_id,
        "render_kind": render_kind,
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


def _persist_route_audit(
    config: ProtocolDeconstructionExecutorConfig,
    job_id: str,
    audit: ProtocolSemanticRouteAudit,
) -> dict[str, Any]:
    """Write the explicit route ledger under the durable job blob boundary."""

    payload = audit.as_audit_dict()
    target = (
        config.data_paths.blobs_dir
        / "protocol-semantic-route-audits"
        / job_id
        / "route-audit.json"
    )
    config.data_paths.boundary.atomic_write_bytes(
        target,
        dumps_route_audit(audit),
    )
    return payload


def load_persisted_route_audit(
    config: ProtocolDeconstructionExecutorConfig,
    job_id: str,
) -> dict[str, Any] | None:
    """Read the job-scoped route ledger; never reuse another job's audit."""

    target = (
        config.data_paths.blobs_dir
        / "protocol-semantic-route-audits"
        / job_id
        / "route-audit.json"
    )
    if not target.is_file() or target.is_symlink():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("audit_contract") != "protocol-semantic-route-audit/v1":
        return None
    if payload.get("job_id") != job_id:
        return None
    return payload


def _grade_generate_task(
    package: ProtocolDeconstructionInputPackage,
    *,
    prompt_template: str,
) -> tuple[Any, list[Any]]:
    """Classify once at generate entry and return ordered route candidates."""

    parent_items = [
        item
        for item in package.source_input.parent_rule_catalog.items
        if item.official_code is not None
    ]
    parent_rule_count = len(parent_items)
    selected_codes = [
        item.official_code for item in parent_items[:1] if item.official_code
    ]
    batch_total = 1 if parent_rule_count <= 1 else max(2, parent_rule_count)
    prompt_text = build_protocol_deconstruction_prompt(
        package.source_input,
        prompt_template=prompt_template,
        requested_rule_codes=selected_codes or None,
        batch_number=1 if selected_codes else None,
        batch_total=1 if selected_codes else None,
        compact=False,
        scoped_source=True,
    )
    decision = classify_protocol_semantic_task_grade(
        parent_rule_count=parent_rule_count,
        prompt_text=prompt_text,
        batch_total=batch_total,
    )
    route_mode = resolve_route_mode(DECONSTRUCT_ROUTE_MODE)
    candidates = select_protocol_semantic_route_candidates(
        decision.grade,
        route_mode=route_mode,
    )
    return decision, candidates


def _run_semantic_generation_with_routing(
    *,
    context: StepContext,
    config: ProtocolDeconstructionExecutorConfig,
    package: ProtocolDeconstructionInputPackage,
    prompt_version: PromptVersion,
    batch_progress: Callable[[int, int, Any], None] | None = None,
) -> tuple[ProtocolDeconstructionRunResult, dict[str, Any]]:
    """Run whole-attempt graded fallback with an auditable candidate ledger."""

    route_mode = resolve_route_mode(DECONSTRUCT_ROUTE_MODE)
    batch_cache = _ProtocolSemanticBatchFileCache(config.data_paths, context.job_id)

    if config.transport is not None or config.transport_factory is not None:
        runner = ProtocolDeconstructorRunner(gate=config.gate)
        transport = _resolve_transport(config)
        result = runner.run(
            package.source_input,
            prompt_version=prompt_version,
            prompt_template=config.prompt_template,
            transport=transport,
            source_spans=package.source_spans,
            batch_cache=batch_cache,
            transport_factory=config.transport_factory,
            batch_progress=batch_progress,
        )
        backend = getattr(transport, "_backend", "injected")
        model = getattr(transport, "_model", "injected")
        effort = getattr(transport, "_reasoning_effort", "injected")
        outcome, error_class, session_id = summarize_run_result_for_route(result)
        audit = ProtocolSemanticRouteAudit(
            job_id=context.job_id,
            route_mode="pinned" if route_mode == "pinned" else "graded",
            grade_decision=None,
            ordered_candidates=[],
            attempts=[
                ProtocolSemanticRouteAttemptRecord(
                    route_attempt=1,
                    grade="injected_transport",
                    backend=str(backend),
                    model=str(model),
                    reasoning_effort=str(effort),
                    outcome=outcome,
                    error_class=error_class,
                    detail=None if outcome == "accepted" else route_failure_detail(result),
                    session_id=session_id,
                )
            ],
            final_identity=f"{backend}:{model}:{effort}",
            final_outcome=outcome,
        )
        return result, _persist_route_audit(config, context.job_id, audit)

    if route_mode == "pinned":
        runner = ProtocolDeconstructorRunner(gate=config.gate)
        transport = _resolve_transport(config)
        result = runner.run(
            package.source_input,
            prompt_version=prompt_version,
            prompt_template=config.prompt_template,
            transport=transport,
            source_spans=package.source_spans,
            batch_cache=batch_cache,
            transport_factory=lambda: _resolve_transport(config),
            batch_progress=batch_progress,
        )
        outcome, error_class, session_id = summarize_run_result_for_route(result)
        candidate = select_protocol_semantic_route_candidates(
            "complex_protocol_semantic",
            route_mode="pinned",
        )[0]
        audit = ProtocolSemanticRouteAudit(
            job_id=context.job_id,
            route_mode="pinned",
            grade_decision=None,
            ordered_candidates=[candidate],
            attempts=[
                ProtocolSemanticRouteAttemptRecord(
                    route_attempt=1,
                    grade="pinned",
                    backend=candidate.backend,
                    model=candidate.model,
                    reasoning_effort=candidate.reasoning_effort,
                    outcome=outcome,
                    error_class=error_class,
                    detail=None if outcome == "accepted" else route_failure_detail(result),
                    session_id=session_id,
                )
            ],
            final_identity=candidate.identity,
            final_outcome=outcome,
        )
        return result, _persist_route_audit(config, context.job_id, audit)

    decision, candidates = _grade_generate_task(
        package,
        prompt_template=config.prompt_template,
    )
    audit = ProtocolSemanticRouteAudit(
        job_id=context.job_id,
        route_mode="graded",
        grade_decision=decision,
        ordered_candidates=list(candidates),
    )
    last_result: ProtocolDeconstructionRunResult | None = None
    for index, candidate in enumerate(candidates, start=1):
        semantic_repair_limit = semantic_repair_limit_for_candidate(
            candidate,
            decision.grade,
        )
        skip_reason = candidate_availability_error(candidate)
        if skip_reason is not None:
            audit.attempts.append(
                ProtocolSemanticRouteAttemptRecord(
                    route_attempt=index,
                    grade=decision.grade,
                    backend=candidate.backend,
                    model=candidate.model,
                    reasoning_effort=candidate.reasoning_effort,
                    outcome="skipped_unavailable",
                    error_class="PROVIDER_UNAVAILABLE",
                    detail=skip_reason,
                    semantic_repair_limit=semantic_repair_limit,
                    discarded_merged_candidate=False,
                )
            )
            continue
        try:
            transport = build_transport_for_candidate(candidate)
        except ValueError as exc:
            audit.attempts.append(
                ProtocolSemanticRouteAttemptRecord(
                    route_attempt=index,
                    grade=decision.grade,
                    backend=candidate.backend,
                    model=candidate.model,
                    reasoning_effort=candidate.reasoning_effort,
                    outcome="skipped_unavailable",
                    error_class="PROVIDER_UNAVAILABLE",
                    detail=str(exc),
                    semantic_repair_limit=semantic_repair_limit,
                )
            )
            continue
        try:
            runner = ProtocolDeconstructorRunner(
                gate=config.gate,
                max_semantic_repairs=semantic_repair_limit,
            )
            result = runner.run(
                package.source_input,
                prompt_version=prompt_version,
                prompt_template=config.prompt_template,
                transport=transport,
                source_spans=package.source_spans,
                batch_cache=batch_cache,
                transport_factory=lambda candidate=candidate: build_transport_for_candidate(
                    candidate
                ),
                batch_progress=batch_progress,
            )
        except ProtocolAgentCallError as exc:
            error_code = getattr(exc, "error_code", "SEMANTIC_CALL_FAILED")
            audit.attempts.append(
                ProtocolSemanticRouteAttemptRecord(
                    route_attempt=index,
                    grade=decision.grade,
                    backend=candidate.backend,
                    model=candidate.model,
                    reasoning_effort=candidate.reasoning_effort,
                    outcome="failed",
                    error_class=error_code,
                    detail=str(exc),
                    session_id=getattr(exc, "session_id", None),
                    semantic_repair_limit=semantic_repair_limit,
                    discarded_merged_candidate=True,
                )
            )
            continue
        last_result = result
        outcome, error_class, session_id = summarize_run_result_for_route(result)
        accepted = outcome == "accepted"
        audit.attempts.append(
            ProtocolSemanticRouteAttemptRecord(
                route_attempt=index,
                grade=decision.grade,
                backend=candidate.backend,
                model=candidate.model,
                reasoning_effort=candidate.reasoning_effort,
                outcome=outcome,
                error_class=error_class,
                detail=None if accepted else route_failure_detail(result),
                session_id=session_id,
                semantic_repair_limit=semantic_repair_limit,
                discarded_merged_candidate=not accepted,
            )
        )
        if accepted:
            audit.final_identity = candidate.identity
            audit.final_outcome = "accepted"
            return result, _persist_route_audit(config, context.job_id, audit)
        # Whole-attempt boundary: discard this provider's merged candidate and
        # start the next provider with a fresh transport/session identity.
    audit.final_outcome = "exhausted"
    payload = _persist_route_audit(config, context.job_id, audit)
    if last_result is not None:
        return last_result, payload
    detail = "方案语义模型路由候选均已显式跳过或失败，未产出可用草稿。"
    if audit.attempts:
        last = audit.attempts[-1]
        if last.detail:
            detail = last.detail
        if all(item.outcome == "skipped_unavailable" for item in audit.attempts):
            detail = (
                f"{detail}；请确认已设置 ENROLLMENT_ENV_FILE "
                "或已注入声明路由所需凭据后重试"
            )
    issue = ProtocolGateIssue(
        issue_code="SEMANTIC_ROUTE_EXHAUSTED",
        check_name="semantic_model_routing",
        level="阻止发布",
        problem=detail,
        impact="当前作业无法进入草稿审阅",
        next_action=(
            "请核对 ENROLLMENT_ENV_FILE / DECONSTRUCT_GLM_API_KEY / "
            "DEEPSEEK_API_KEY / MTPLX 连通性后重试"
        ),
        affected_refs=["semantic_route_audit"],
        repair_scope=["semantic_route"],
    )
    empty = ProtocolDeconstructionRunResult(
        status="需要核对",
        same_session_id="protocol-route-exhausted",
        attempts=[
            ProtocolDeconstructionAttempt(
                attempt=1,
                session_id="protocol-route-exhausted",
                raw_output_sha256="0" * 64,
                outcome="会话异常",
                issues=[issue],
            )
        ],
    )
    return empty, payload


def _resolve_transport(config: ProtocolDeconstructionExecutorConfig) -> Any:
    if config.transport is not None:
        return config.transport
    if config.transport_factory is not None:
        return config.transport_factory()
    backend = DECONSTRUCT_BACKEND.strip().lower()
    from app.agents.protocol_semantic_transport import (
        OpenAICompatibleProtocolAgentTransport,
        SUPPORTED_PROTOCOL_DECONSTRUCTION_BACKENDS,
    )

    if backend not in SUPPORTED_PROTOCOL_DECONSTRUCTION_BACKENDS:
        raise StepFailure(
            retryable=False,
            error_code="SEMANTIC_PROVIDER_UNSUPPORTED",
            detail="方案语义解构服务的模型连接方式不受支持；请核对 DECONSTRUCT_BACKEND 配置后重试。",
        )
    if backend == "deepseek" and not DEEPSEEK_API_KEY:
        raise StepFailure(
            retryable=True,
            error_code="SEMANTIC_PROVIDER_UNAVAILABLE",
            detail="方案语义解构服务尚未配置，暂不能生成草稿；请联系维护人员完成模型接入后重试。",
        )
    if backend in {"zhipu-coding-plan", "glm", "cms-router", "cms-smk", "opencode-go"}:
        from app.llm.provider_profiles import resolve_openai_connection

        try:
            resolve_openai_connection(
                backend,
                role_base_url_env="DECONSTRUCT_BASE_URL",
                role_api_key_env="DECONSTRUCT_API_KEY",
            )
        except ValueError:
            raise StepFailure(
                retryable=True,
                error_code="SEMANTIC_PROVIDER_UNAVAILABLE",
                detail="方案语义解构服务尚未配置，暂不能生成草稿；请核对所选供应商的专用凭据。",
            )
    return OpenAICompatibleProtocolAgentTransport(backend=backend)


def _semantic_failure_detail(result: ProtocolDeconstructionRunResult) -> str:
    """Keep bounded schema/gate diagnostics when no draft can be persisted."""
    base = "方案语义解构尚未产出可用草稿，请稍后重试或联系维护人员。"
    diagnostics: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for attempt in reversed(result.attempts):
        for issue in reversed(attempt.issues):
            problem = " ".join(issue.problem.split())[:700]
            next_action = " ".join(issue.next_action.split())[:300]
            fingerprint = (issue.issue_code, problem, next_action)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            diagnostics.append(
                f"{issue.issue_code}: {problem}；下一步：{next_action}"
            )
            if len(diagnostics) >= 3:
                break
        if len(diagnostics) >= 3:
            break
    if not diagnostics:
        return base
    return base + " 最近诊断：" + "；".join(diagnostics)[:3000]


def _assemble_input_package(
    context: StepContext,
    config: ProtocolDeconstructionExecutorConfig,
    merged: dict[str, Any],
) -> ProtocolDeconstructionInputPackage:
    artifact = _artifact_from_checkpoint(merged)
    snapshot = _snapshot_from_checkpoint(merged)
    blocks = _load_blocks(config, snapshot)
    spans = _spans_from_checkpoint(merged)
    identity = ProtocolIdentityDecision.model_validate(merged["identity_decision"])
    phase_selection = StudyPhaseSelection.model_validate(merged["phase_selection"])
    phase_graph = PhaseApplicabilityGraph.model_validate(merged["phase_graph"])
    project_id = f"draft-project-{context.job_id[:12]}"
    protocol_version_id = f"draft-version-{context.job_id[:12]}"
    return ProtocolDeconstructionInputAssembler(
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


def _handle_freeze(
    context: StepContext,
    config: ProtocolDeconstructionExecutorConfig,
) -> dict[str, Any]:
    """Persist deterministic single-phase catalogs before any model call."""
    merged = _merged_prior_checkpoints(config, context.job_id, before_step=STEP_FREEZE)
    package = _assemble_input_package(context, config, merged)
    return {
        "source_input": package.source_input.model_dump(mode="json"),
        "source_spans": {
            key: span.model_dump(mode="json")
            for key, span in package.source_spans.items()
        },
        "phase_projection": package.projection.model_dump(mode="json"),
        "parent_rule_count": len(package.parent_rule_catalog.items),
        "required_procedure_count": len(package.required_procedure_catalog.items),
    }


def _handle_generate(context: StepContext, config: ProtocolDeconstructionExecutorConfig) -> dict[str, Any]:
    route_audit_payload: dict[str, Any] | None = None
    merged = _merged_prior_checkpoints(config, context.job_id, before_step=STEP_GENERATE)
    source_input = ProtocolDeconstructionInput.model_validate(merged["source_input"])
    source_spans = {
        span.source_span_id: span for span in _spans_from_checkpoint(merged)
    }
    package = ProtocolDeconstructionInputPackage(
        source_input=source_input,
        source_spans=source_spans,
        projection=PhaseProjection.model_validate(merged["phase_projection"]),
        parent_rule_catalog=source_input.parent_rule_catalog,
        required_procedure_catalog=source_input.required_procedure_catalog,
    )
    project_id = source_input.project_id
    protocol_version_id = source_input.protocol_version_id

    actor = str(context.job_payload.get("actor") or "系统")
    baseline_draft = None
    if context.job_payload.get("session_kind") == "re_deconstruction":
        from app.services.protocol_draft_service import (
            FormalBaselineError,
            resolve_formal_baseline_revision,
        )

        target_project_id = context.job_payload.get("target_project_id")
        try:
            with config.session_factory() as session:
                baseline_draft = resolve_formal_baseline_revision(
                    session=session,
                    project_id=target_project_id,
                ).content
        except FormalBaselineError as exc:
            raise StepFailure(
                retryable=False,
                error_code=exc.code,
                detail=f"{str(exc)}（{exc.recovery}）",
            ) from exc
        except Exception as exc:  # noqa: BLE001 - 基线解析必须 fail-closed
            raise StepFailure(
                retryable=False,
                error_code="FORMAL_BASELINE_READ_FAILED",
                detail="读取当前正式草稿基线失败，无法生成本次重新解构差异。"
                "请联系维护人员核对不可变发布链后重试。",
            ) from exc

    # 模型运行结束后，草稿不可变记录与 Job 步骤检查点分属
    # 两个短事务。若进程或租约在两者之间中断，重试必须使用
    # 已持久化的草稿重建检查点，不得再次调用模型。
    with config.session_factory() as session:
        persisted = ProtocolDraftRevisionRepository(session).find_by_generation_scope(
            project_id=project_id,
            protocol_version_id=protocol_version_id,
        )
    if len(persisted) > 1:
        raise StepFailure(
            retryable=False,
            error_code="SEMANTIC_DRAFT_RECOVERY_CONFLICT",
            detail="本次方案解构存在多份已保存首稿，无法确定应恢复哪一份。"
            "请联系维护人员核对草稿历史。",
        )

    revision = persisted[0] if persisted else None
    final_draft = revision.content if revision is not None else None
    gate = None
    if revision is None:
        prompt_version = PromptVersion(
            prompt_version_id="protocol-deconstructor/v1",
            node=AgentNode.PROTOCOL_DECONSTRUCTOR,
            template_sha256=protocol_prompt_template_sha256(config.prompt_template),
            schema_version_id="protocol-deconstruction-draft/v1",
        )
        batch_progress: Callable[[int, int, Any], None] = (
            lambda batch_index, batch_total, candidate: _persist_semantic_batch_progress(
                config, context.job_id, batch_index, batch_total, candidate
            )
        )
        if config.draft_response_builder is not None:
            draft_json = config.draft_response_builder(package)
            transport = _FakeSingleResponseTransport(draft_json)
            runner = ProtocolDeconstructorRunner(gate=config.gate)
            try:
                result = runner.run(
                    package.source_input,
                    prompt_version=prompt_version,
                    prompt_template=config.prompt_template,
                    transport=transport,
                    source_spans=package.source_spans,
                    batch_cache=_ProtocolSemanticBatchFileCache(
                        config.data_paths,
                        context.job_id,
                    ),
                    batch_progress=batch_progress,
                )
            except ProtocolAgentCallError as exc:
                error_code = getattr(exc, "error_code", "SEMANTIC_CALL_FAILED")
                raise StepFailure(
                    retryable=True,
                    error_code=error_code,
                    detail=f"方案语义解构调用未完成，请稍后重试。（{exc}）",
                ) from exc
        else:
            try:
                result, route_audit_payload = _run_semantic_generation_with_routing(
                    context=context,
                    config=config,
                    package=package,
                    prompt_version=prompt_version,
                    batch_progress=batch_progress,
                )
            except ProtocolAgentCallError as exc:
                error_code = getattr(exc, "error_code", "SEMANTIC_CALL_FAILED")
                raise StepFailure(
                    retryable=True,
                    error_code=error_code,
                    detail=f"方案语义解构调用未完成，请稍后重试。（{exc}）",
                ) from exc

        if result.final_draft is None:
            detail = _semantic_failure_detail(result)
            if route_audit_payload is not None:
                detail = (
                    detail
                    + " 模型路由审计："
                    + json.dumps(
                        {
                            "route_mode": route_audit_payload.get("route_mode"),
                            "final_outcome": route_audit_payload.get("final_outcome"),
                            "attempts": [
                                {
                                    "route_attempt": item.get("route_attempt"),
                                    "backend": item.get("backend"),
                                    "model": item.get("model"),
                                    "outcome": item.get("outcome"),
                                    "error_class": item.get("error_class"),
                                }
                                for item in route_audit_payload.get("attempts", [])
                            ],
                        },
                        ensure_ascii=False,
                    )
                )
            raise StepFailure(
                retryable=True,
                error_code="SEMANTIC_DRAFT_MISSING",
                detail=detail,
            )
        final_draft = result.final_draft
        gate = result.final_gate_result
        with config.session_factory() as session:
            with session.begin():
                revision = ProtocolDraftService(session).save_initial_draft(
                    final_draft,
                    actor=actor,
                    created_at=config.now(),
                    baseline=baseline_draft,
                )

    assert revision is not None
    assert final_draft is not None
    if baseline_draft is not None:
        from app.protocols.deconstruction_gate import ProtocolDraftDiffDeclaration

        gate = (config.gate or ProtocolDeconstructionGate()).evaluate(
            package.source_input,
            final_draft,
            source_spans=package.source_spans,
            previous_draft=baseline_draft,
            declared_diff=ProtocolDraftDiffDeclaration(
                **revision.diff.model_dump(mode="python")
            ),
        )
    elif gate is None:
        gate = (config.gate or ProtocolDeconstructionGate()).evaluate(
            package.source_input,
            final_draft,
            source_spans=package.source_spans,
        )

    payload = {
        "draft_id": revision.draft_id,
        "draft_revision_id": revision.revision_id,
        "draft_status": revision.status.value,
        "semantic_status": (
            "可以进入审阅" if gate.publishable else "需要核对"
        ),
        "source_input": package.source_input.model_dump(mode="json"),
        "source_spans": {
            key: span.model_dump(mode="json")
            for key, span in package.source_spans.items()
        },
        "gate_result": gate.model_dump(mode="json"),
        "gate_version": DECONSTRUCTION_GATE_VERSION,
        "publishable": gate.publishable,
    }
    if route_audit_payload is not None:
        payload["semantic_route_audit"] = route_audit_payload
    return payload


def _handle_integrity(context: StepContext, config: ProtocolDeconstructionExecutorConfig) -> dict[str, Any]:
    merged = _merged_prior_checkpoints(config, context.job_id, before_step=STEP_INTEGRITY)
    if (
        merged.get("gate_result")
        and merged.get("gate_version") == DECONSTRUCTION_GATE_VERSION
    ):
        gate_raw = merged["gate_result"]
        return {
            "gate_result": gate_raw,
            "gate_version": DECONSTRUCTION_GATE_VERSION,
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
        "gate_version": DECONSTRUCTION_GATE_VERSION,
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

    def start(
        self,
        *,
        prompt: str,
        output_kind: str = "semantic_candidate",
    ) -> ProtocolAgentResponse:
        self.start_prompts.append(prompt)
        return ProtocolAgentResponse(session_id="test-session", text=self._text)

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
        output_kind: str = "semantic_candidate",
    ) -> ProtocolAgentResponse:
        self.repair_prompts.append((session_id, prompt))
        return ProtocolAgentResponse(session_id=session_id, text=self._text)
