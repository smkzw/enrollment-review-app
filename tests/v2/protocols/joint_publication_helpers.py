"""同源跨章联合发布的合成夹具：真实 control JobRunner 完成 + gate checkpoint。

为重新解构发布测试（Workbench 谱系/取消/保存/解释断言的调用方）提供一个
可复用的正例来源：给定 ``(source_input, draft, source_spans, draft_revision_id)``，
在独立临时数据目录内完成：

1. 用给定输入重建一致的合成结构快照、期别适用图与单期投影（保留原
   ``extraction_snapshot_id`` / ``phase_projection_id`` 身份，不发明新 ID），
   冻结成真实的方案解构来源任务（含 ``freeze_deconstruction_input`` 检查点）；
2. 经真实 ``ProtocolControlJobService.create_from_deconstruction`` 绑定草稿修订
   建立控制任务；
3. 用真实 ``JobRunner`` 与确定性合成传输完成发现、深析、定义核对、水合与
   发布门禁（不 mock 门禁、不伪造完成状态）；
4. 返回 ``(control_job_id, control_checkpoint_id)``，供
   ``ProtocolPublicationRequest`` 的 ``control_job_id`` / ``control_checkpoint_id``
   消费。

真实层：来源冻结、控制作业执行、gate checkpoint、发布事务与全部确定性校验。
模拟层：仅 Agent 传输（发现/深析/来源解释响应为确定性合成文本）。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Mapping

from app.domain.contracts.agent_io import (
    ProtocolDeconstructionDraft,
    ProtocolDeconstructionInput,
)
from app.domain.contracts.enums import (
    ApplicabilityGranularity,
    ExtractionStatus,
    PhaseScope,
)
from app.domain.contracts.protocol_ingestion import (
    ExtractionCoverage,
    ProtocolExtractionSnapshot,
    ProtocolSourceSpan,
)
from app.domain.contracts.protocol_metadata import (
    PhaseApplicabilityBlock,
    PhaseApplicabilityGraph,
    PhaseProjection,
)
from app.protocols.docx_structure import (
    BlockKind,
    StructureBlock,
    block_set_hash,
    serialize_blocks,
)
from app.services.job_service import JobService, StepSpec
from app.services.protocol_control_execution import STEP_GATE, _SOURCE_STEP_ORDER
from app.services.protocol_control_job_service import ProtocolControlJobService
from app.services.protocol_workbench_service import (
    PROTOCOL_DECONSTRUCTION_JOB_TYPE,
    STEP_GENERATE as SOURCE_STEP_GENERATE,
)
from app.storage.repositories import NotFoundError, ProtocolDraftRevisionRepository
from app.workflow.jobstore import JobStore

# 复用既有确定性合成传输与 Runner 装配（含固定的测试时钟），不另建框架。
from tests.v2.services.test_protocol_control_execution import (
    NOW,
    _DeepTransport,
    _DiscoveryTransport,
    _build_runner,
    _now,
)

__all__ = ["NOW", "seed_joint_control_publication"]


def _synthetic_structure(
    source_input: ProtocolDeconstructionInput,
    source_spans: Mapping[str, ProtocolSourceSpan],
) -> tuple[tuple[StructureBlock, ...], PhaseApplicabilityGraph, PhaseProjection]:
    """从原文定位与单期材料重建同源段落块集、期别适用图与单期投影。

    原夹具（slice3/slice4）不携带结构提取结果；这里按材料正文逐 ``source_ref``
    构造匹配的合成原始段落，保持来源身份 ID 不变。
    """

    materials = {
        item.source_span_id: item.text for item in source_input.source_materials
    }
    spans_by_ref: dict[str, list[ProtocolSourceSpan]] = {}
    for span in source_spans.values():
        spans_by_ref.setdefault(span.source_ref, []).append(span)

    blocks: list[StructureBlock] = []
    graph_blocks: list[PhaseApplicabilityBlock] = []
    for source_ref, group in sorted(
        spans_by_ref.items(),
        key=lambda item: min(span.block_order for span in item[1]),
    ):
        lead = group[0]
        if lead.table_path:
            raise ValueError(
                "合成冻结输入夹具仅支持正文段落来源片段；"
                f"来源片段 {lead.source_span_id} 携带表格定位，需按原表结构扩展夹具。"
            )
        texts = {materials.get(span.source_span_id, "") for span in group}
        if any(not text.strip() for text in texts):
            raise ValueError("合成来源缺少正文，不能缩小整源覆盖范围。")
        if len(texts) != 1:
            raise ValueError("同一合成段落的不同原文片段无法唯一重建，不能选择其中一个。")
        text = texts.pop()
        block = StructureBlock(
            source_ref=source_ref,
            document_part=lead.document_part,
            section_index=lead.section_index,
            block_order=min(span.block_order for span in group),
            kind=BlockKind.PARAGRAPH,
            text=text,
        )
        blocks.append(block)
        graph_blocks.append(
            PhaseApplicabilityBlock(
                block_id=f"phase-{source_ref}",
                snapshot_id=source_input.extraction_snapshot_id,
                source_ref=source_ref,
                source_span_ids=sorted(
                    {span.source_span_id for span in group}
                ),
                granularity=ApplicabilityGranularity.PARAGRAPH,
                source_order=block.block_order,
                text=text,
                phase_scopes=[PhaseScope.SHARED],
            )
        )
    if not blocks:
        raise ValueError("给定来源没有可覆盖的正文材料，不能建立合成冻结输入。")

    graph_id = f"graph:{source_input.phase_projection_id}"
    phase_graph = PhaseApplicabilityGraph(
        graph_id=graph_id,
        snapshot_id=source_input.extraction_snapshot_id,
        blocks=graph_blocks,
        detected_phase_scopes=[PhaseScope.SHARED],
    )
    projection = PhaseProjection(
        projection_id=source_input.phase_projection_id,
        graph_id=graph_id,
        selected_phase=source_input.selected_phase,
        blocks=list(graph_blocks),
    )
    return tuple(blocks), phase_graph, projection


def _freeze_source_job(
    session_factory,
    data_paths,
    source_input: ProtocolDeconstructionInput,
    draft: ProtocolDeconstructionDraft,
    source_spans: Mapping[str, ProtocolSourceSpan],
    draft_revision_id: str,
    *,
    key: str,
) -> str:
    """按给定输入冻结真实的方案解构来源任务，返回来源任务编号。

    与生产 ``seed_review_session`` 同一口径：``generate_draft`` 步骤检查点
    记录该来源实际产出的 ``draft_id`` / ``draft_revision_id``，控制任务建立时
    据此核对草稿修订未被替换。
    """

    blocks, phase_graph, projection = _synthetic_structure(
        source_input, source_spans
    )
    serialized = serialize_blocks(blocks)
    content_sha256 = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    # 与运行时 _load_snapshot_blocks 相同的完整性口径：文件哈希 = 规范块集哈希。
    assert block_set_hash(blocks) == content_sha256
    snapshot = ProtocolExtractionSnapshot(
        snapshot_id=source_input.extraction_snapshot_id,
        source_artifact_id=f"artifact-joint-publication-{key}",
        source_sha256=source_input.protocol_file_sha256,
        parser_name="synthetic-joint-publication-fixture",
        parser_version="1",
        status=ExtractionStatus.COMPLETED,
        coverage=ExtractionCoverage(
            paragraph_count=len(blocks),
            table_count=0,
            section_count=1,
            nested_table_count=0,
        ),
        content_sha256=content_sha256,
        content_storage_ref=f"blobs/protocol_blocks/joint-publication-{key}.json",
        created_at=NOW,
    )

    snapshot_path = data_paths.blobs_dir / snapshot.content_storage_ref
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(serialized, encoding="utf-8")

    steps: list[StepSpec] = []
    previous: str | None = None
    # The production order now includes generation and later review/publish.
    # This fixture freezes only the source through its actual draft output.
    source_steps = _SOURCE_STEP_ORDER[:_SOURCE_STEP_ORDER.index(SOURCE_STEP_GENERATE) + 1]
    for step_id in source_steps:
        steps.append(
            StepSpec(
                step_id=step_id,
                name=step_id,
                depends_on=(previous,) if previous is not None else (),
            )
        )
        previous = step_id
    source = JobService(session_factory, now=_now).create_job(
        idempotency_key=f"joint-publication-source-{key}",
        job_type=PROTOCOL_DECONSTRUCTION_JOB_TYPE,
        payload={"source_input": source_input.model_dump(mode="json")},
        steps=steps,
    )

    checkpoint = {
        "source_input": source_input.model_dump(mode="json"),
        "extraction_snapshot": snapshot.model_dump(mode="json"),
        "phase_graph": phase_graph.model_dump(mode="json"),
        "phase_projection": projection.model_dump(mode="json"),
        "source_spans": {
            span_id: span.model_dump(mode="json")
            for span_id, span in source_spans.items()
        },
    }
    draft_checkpoint = {
        "draft_id": draft.draft_id,
        "draft_revision_id": draft_revision_id,
    }
    with session_factory() as session, session.begin():
        store = JobStore(session, now=_now)
        lease = store.claim_job(source.job_id, "joint-publication-source-seed")
        if lease is None:
            raise RuntimeError(
                f"合成来源任务 {source.job_id} 无法认领，不能冻结解构输入。"
            )
        for step in steps:
            store.start_step(lease, step.step_id)
            store.complete_step(
                lease,
                step.step_id,
                checkpoint_payload=(
                    draft_checkpoint
                    if step.step_id == SOURCE_STEP_GENERATE
                    else checkpoint
                ),
            )
        store.finish_success(lease)
    return source.job_id


def seed_joint_control_publication(
    session_factory,
    data_paths,
    source_input: ProtocolDeconstructionInput,
    draft: ProtocolDeconstructionDraft,
    source_spans: Mapping[str, ProtocolSourceSpan],
    draft_revision_id: str,
    *,
    key: str | None = None,
    idempotency_key: str | None = None,
) -> tuple[str, str]:
    """为给定来源/草稿修订完成真实控制作业，返回 ``(control_job_id, control_checkpoint_id)``。

    - ``source_input`` / ``source_spans``：调用方既有的同源冻结输入
      （例如 ``confirmed_fixture()`` 的产物）；身份 ID 原样保留。
    - ``draft`` / ``draft_revision_id``：已保存的草稿及其修订 ID；辅助函数按
      发布事务同一口径预检修订与草稿一致，再由 ``create_from_deconstruction``
      冻结进控制任务载荷。
    - ``key`` / ``idempotency_key``：可选唯一键；缺省自动生成，便于同一来源
      建立多个已完成作业（用于错配拒绝路径）。
    """

    if not source_spans:
        raise ValueError("合成联合发布夹具需要非空来源片段集合。")
    try:
        with session_factory() as session:
            revision = ProtocolDraftRevisionRepository(session).get(
                draft_revision_id
            )
    except NotFoundError as exc:
        raise ValueError(
            f"草稿修订 {draft_revision_id} 尚未保存；请先经 ProtocolDraftService "
            "保存首稿再调用本夹具。"
        ) from exc
    if (revision.project_id, revision.protocol_version_id, revision.study_phase) != (
        source_input.project_id,
        source_input.protocol_version_id,
        source_input.selected_phase,
    ):
        raise ValueError("草稿修订与方案解构输入的项目/版本/期别不一致。")
    if revision.content != draft:
        raise ValueError("草稿修订内容与给定草稿不一致；请传入该修订的真实内容。")

    key = key or uuid.uuid4().hex[:12]
    idempotency_key = idempotency_key or f"joint-publication-control-{key}"
    source_job_id = _freeze_source_job(
        session_factory, data_paths, source_input, draft, source_spans,
        draft_revision_id, key=key,
    )

    result = ProtocolControlJobService(
        session_factory,
        data_paths=data_paths,
        max_discovery_units_per_batch=256,
        discovery_context_radius=1,
        max_deep_units_per_batch=2,
        actor="system",
        workflow_stages=tuple(draft.proposed_workflow_stages),
        now=_now,
    ).create_from_deconstruction(
        source_job_id=source_job_id,
        draft_revision_id=draft_revision_id,
        idempotency_key=idempotency_key,
    )

    # 深析候选的原文摘录必须是片段的连续原文；slice 系列夹具的 span.excerpt
    # 是占位文本，真实原文以冻结单期材料为准，缺失时才回退片段摘录。
    materials = {
        item.source_span_id: item.text for item in source_input.source_materials
    }
    excerpts = {}
    for span_id, span in source_spans.items():
        text = materials.get(span_id) or (span.excerpt or "")
        if text.strip():
            excerpts[span_id] = text
    runner, _ = _build_runner(
        data_paths,
        session_factory,
        _DiscoveryTransport(),
        _DeepTransport(excerpts),
    )
    if not runner.run_job(result.job_id):
        raise RuntimeError(
            f"合成控制作业 {result.job_id} 未完成；不能作为发布依据。"
        )

    with session_factory() as session:
        store = JobStore(session, now=_now)
        job = store.get_job(result.job_id)
        if job.state != "completed":
            step_states = {
                step.step_id: (step.state, step.error_code)
                for step in store.list_steps(result.job_id)
                if step.state != "completed"
            }
            details: list[str] = []
            for step_id, (state, error_code) in step_states.items():
                if error_code is None or error_code == "DEPENDENCY_FAILED":
                    continue
                for checkpoint_id, payload in store.list_checkpoints(
                    result.job_id, step_id
                ):
                    brief = json.dumps(
                        payload, ensure_ascii=False, default=str
                    )[:900]
                    details.append(f"{step_id}/{checkpoint_id}: {brief}")
            raise RuntimeError(
                f"控制作业 {result.job_id} 状态为 {job.state}"
                f"（未完成步骤：{step_states}；最近失败明细：{details}），"
                "不能作为发布依据。"
            )
        checkpoint = store.get_last_checkpoint(result.job_id, STEP_GATE)
    if checkpoint is None:
        raise RuntimeError(
            f"控制作业 {result.job_id} 缺少发布门禁检查点，不能作为发布依据。"
        )
    return result.job_id, checkpoint[0]
