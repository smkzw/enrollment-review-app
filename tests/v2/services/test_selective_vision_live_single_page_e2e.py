"""Phase 5 单页真实视觉端到端（显式启用，默认跳过）。

Boundary:
  ACCEPT (LIVE: SELECTIVE_VISION_LIVE_E2E=1 且具备 Coding Plan 凭证) —
    1. 全新隔离数据目录（pytest tmp_path），零 D001/SAR/仓库旧结果耦合；
    2. 内容中立单页合成扫描件 -> 已冻结证据修订 -> 幂等入队独立视觉任务；
    3. 真实智谱 Coding Plan GLM-5.3-Flash 调用（/api/coding/paas/v4，
       thinking.enabled + source-locator 保真）；
    4. 成功观察非空、来源匹配、哈希链完整，以不可变 ``svo-`` 行落库；
    5. OCR 原文/哈希与页图字节全程不变；
    6. 修订 -> 任务的用户查询投影反映落盘结果，不以任务完成替代内容核对。
  REJECT —
    用 mock 运行结果冒充真实调用；静默跳过未配置凭证之外的场景；
    提供方失败关闭被当成成功；读取或修改既有项目结果。

Aligned to production surface (全部复用，不新增生产修改):
  app.services.selective_vision_postprocess_job_service (enqueue + get_revision_task)
  app.services.selective_vision_postprocess_executor (真实 runner，不注入)
  app.services.selective_vision_observation_service (短事务持久化)
  app.storage.selective_vision_observation_repository (不可变观察行)
  app.llm.independent_vlm (真实 Coding Plan 传输)
确定性种子夹具复用自:
  tests.v2.storage.test_ocr_repositories.make_*（与 postfreeze 编排测试同源）
"""

from __future__ import annotations

import asyncio
import os
import struct
import zlib
from hashlib import sha256
from typing import Any

import pytest

from app.domain.contracts.enums import (
    ExtractionRoute,
    PageArtifactStatus,
    SnapshotMemberOrigin,
    SnapshotStatus,
)
from app.domain.contracts.evidence_processing import EvidenceProcessingRevisionPage
from app.domain.contracts.selective_vision_observation import (
    SelectiveVisionObservationStatus,
)
from app.domain.publication import evidence_processing_manifest_hash
from app.evidence.artifacts import ArtifactStore
from app.evidence.selective_vision_review import (
    SELECTIVE_VISION_PLAN_VERSION,
    VISION_REASON_SCAN_OR_IMAGE_ONLY,
    SelectiveVisionObservation,
    SelectiveVisionReviewOutcome,
    build_selective_vision_prompts,
)
from app.llm import independent_vlm as vlm
from app.llm.independent_vlm import CODING_PLAN_BASE_URL
from app.services.selective_vision_observation_service import (
    SelectiveVisionObservationService,
)
from app.services.selective_vision_postprocess_executor import (
    SelectiveVisionPostprocessExecutorConfig,
    create_selective_vision_postprocess_executor,
    load_selective_vision_page_materials_for_revision,
)
from app.services.selective_vision_postprocess_job_service import (
    SELECTIVE_VISION_POSTPROCESS_JOB_TYPE,
    SELECTIVE_VISION_POSTPROCESS_STEP_ID,
    SelectiveVisionPostprocessJobService,
    enqueue_selective_vision_postprocess_for_revision,
)
from app.storage.codecs import utc_now
from app.storage.evidence_repositories import (
    BlobRepository,
    EvidenceSnapshotRepository,
    SourceDocumentRepository,
)
from app.storage.ocr_repositories import (
    EvidenceProcessingRevisionRepository,
    OCRProfileRepository,
    OcrPageRepository,
    PageArtifactRepository,
)
from app.storage.repositories import persist_fixture
from app.storage.selective_vision_observation_repository import (
    SelectiveVisionObservationRepository,
)
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner
from tests.v2.llm.test_independent_vlm import _resolve_live_api_key
from tests.v2.storage.test_ocr_repositories import (
    make_artifact,
    make_blob,
    make_ocr_page,
    make_profile,
    make_revision,
    make_snapshot,
    make_version,
)
from tests.v2.storage.test_repositories_roundtrip import FIXTURES

VERSION_ID = "doc-live-e2e-1"
ARTIFACT_ID = "pa-live-e2e-1"
OCR_PAGE_ID = "op-live-e2e-1"
REVISION_ID = "rev-live-e2e-1"
SNAPSHOT_ID = "snap-live-e2e-1"
PAGE_ORDINAL = 1

# 内容中立样张正文（无研究号/疾病/药物/评分/访视/条款号）。
NEUTRAL_PAGE_LINES = (
    "SYNTHETIC VISION SELF-CHECK PAGE",
    "CONTENT-NEUTRAL SINGLE-PAGE MATERIAL",
    "FIELD      | VALUE | NOTE",
    "ALPHA-01   | 12.5  | OK",
    "BETA-02    | 8.0   | OK",
    "GAMMA-03   | 4.2   | REVIEW",
    "PAGE 1 OF 1 - GENERATED FOR PIPELINE SELF-TEST",
    "NO REAL CLINICAL CONTENT ON THIS PAGE",
)
RAW_TEXT = "\n".join(NEUTRAL_PAGE_LINES)

_FORBIDDEN_OUTPUT_TOKENS = ("D001", "SAR", "入排通过", "入排失败", "RECIST", "ECOG")


def _render_neutral_single_page_png() -> bytes:
    """仅用标准库生成内容中立的表格页 PNG。"""
    width, height = 640, 800
    pixels = bytearray(b"\xff\xff\xff" * width * height)

    def fill_rect(left: int, top: int, right: int, bottom: int) -> None:
        row = b"\x18\x18\x18" * max(0, right - left)
        for y in range(max(0, top), min(height, bottom)):
            start = (y * width + max(0, left)) * 3
            pixels[start : start + len(row)] = row

    # 标题块、分隔线与通用数据表；不含疾病、药物或方案特异信息。
    fill_rect(48, 52, 410, 66)
    fill_rect(48, 84, 330, 92)
    table_left, table_right = 48, 592
    table_top, row_height, rows = 150, 72, 5
    for y in range(table_top, table_top + row_height * rows + 1, row_height):
        fill_rect(table_left, y, table_right, y + 2)
    for x in (table_left, 280, 420, table_right - 2):
        fill_rect(x, table_top, x + 2, table_top + row_height * rows)
    for row_index in range(rows):
        y = table_top + 24 + row_index * row_height
        fill_rect(66, y, 210, y + 7)
        fill_rect(300, y, 360, y + 7)
        fill_rect(440, y, 548, y + 7)
    fill_rect(48, 560, 500, 568)
    fill_rect(48, 590, 390, 598)

    def chunk(kind: bytes, data: bytes) -> bytes:
        payload = kind + data
        return (
            struct.pack(">I", len(data))
            + payload
            + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)
        )

    scanlines = b"".join(
        b"\x00" + pixels[y * width * 3 : (y + 1) * width * 3]
        for y in range(height)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(scanlines, level=6))
        + chunk(b"IEND", b"")
    )


def _seed_frozen_revision(
    session_factory,
    data_paths,
    *,
    png_bytes: bytes,
    png_sha256: str,
) -> dict[str, Any]:
    """播种：内容寻址页图 + 源版本 + 快照 + vision_ocr 页产物/OCR + 冻结修订。"""
    store = ArtifactStore(data_paths)
    stored = store.put("page_image", png_bytes)
    assert stored.sha256 == png_sha256

    with session_factory() as session, session.begin():
        fixture = FIXTURES[0]
        persist_fixture(session, fixture)
        scope = (
            fixture.project.project_id,
            fixture.subject.subject_id,
            fixture.review_episode.review_episode_id,
        )

        blob = make_blob(b"synthetic-single-page-scan-live-e2e")
        BlobRepository(session).get_or_create_by_sha256(blob)
        version = make_version(
            version_id=VERSION_ID,
            logical_id="log-live-e2e-1",
            blob_sha=blob.sha256,
            scope=scope,
            page_count=1,
        )
        SourceDocumentRepository(session).create_version(version)
        snapshot = make_snapshot(
            snapshot_id=SNAPSHOT_ID,
            scope=scope,
            members=[("log-live-e2e-1", VERSION_ID, SnapshotMemberOrigin.ADDED)],
        )
        EvidenceSnapshotRepository(session).create_full(snapshot)
        EvidenceSnapshotRepository(session).transition_status(
            SNAPSHOT_ID,
            event="worker_start",
            new_status=SnapshotStatus.PROCESSING,
            actor="tester",
            reason="start",
        )
        profile = OCRProfileRepository(session).get_or_create(make_profile())
        assert profile.extraction_route == ExtractionRoute.VISION_OCR
        PageArtifactRepository(session).get_or_create(
            make_artifact(
                artifact_id=ARTIFACT_ID,
                version_id=VERSION_ID,
                page_image=png_sha256,
                page_input=png_sha256,
                status=PageArtifactStatus.SUCCEEDED,
            )
        )
        page = OcrPageRepository(session).create(
            make_ocr_page(
                page_id=OCR_PAGE_ID,
                artifact_id=ARTIFACT_ID,
                profile_sha=profile.profile_sha256,
                page_input=png_sha256,
                raw_text=RAW_TEXT,
            )
        )
        entry = EvidenceProcessingRevisionPage(
            entry_id="e-live-e2e-1",
            position=PAGE_ORDINAL,
            source_document_version_id=VERSION_ID,
            page_number=PAGE_ORDINAL,
            original_frame=None,
            page_artifact_id=ARTIFACT_ID,
            ocr_page_id=page.ocr_page_id,
            status=PageArtifactStatus.SUCCEEDED,
        )
        manifest_hash = evidence_processing_manifest_hash(
            entries=[
                (
                    VERSION_ID,
                    PAGE_ORDINAL,
                    None,
                    ARTIFACT_ID,
                    page.ocr_page_id,
                    PageArtifactStatus.SUCCEEDED.value,
                )
            ]
        )
        EvidenceProcessingRevisionRepository(session).create(
            make_revision(
                {
                    "project_id": scope[0],
                    "subject_id": scope[1],
                    "episode_id": scope[2],
                    "entry": entry,
                    "manifest_hash": manifest_hash,
                },
                evidence_processing_revision_id=REVISION_ID,
                evidence_snapshot_id=SNAPSHOT_ID,
            )
        )
        return {
            "revision_id": REVISION_ID,
            "page_artifact_id": ARTIFACT_ID,
            "ocr_page_id": page.ocr_page_id,
            "raw_text": page.raw_text,
            "raw_text_sha256": page.raw_text_sha256,
            "image_sha": png_sha256,
        }


def _load_materials(session_factory, data_paths):
    with session_factory() as session:
        return load_selective_vision_page_materials_for_revision(
            session,
            evidence_processing_revision_id=REVISION_ID,
            artifact_store=ArtifactStore(data_paths),
        )


def _assert_ocr_and_image_immutable(session_factory, data_paths, seeded, png_bytes):
    with session_factory() as session:
        ocr = OcrPageRepository(session).get(seeded["ocr_page_id"])
        assert ocr.raw_text == seeded["raw_text"]
        assert ocr.raw_text_sha256 == seeded["raw_text_sha256"]
        artifact = PageArtifactRepository(session).get(seeded["page_artifact_id"])
        assert artifact.page_image_sha256 == seeded["image_sha"]
    assert (
        ArtifactStore(data_paths).read_by_sha("page_image", seeded["image_sha"])
        == png_bytes
    )


# ---------------------------------------------------------------------------
# 确定性预检：同一条种子/装载/规划链，不触网；保证 live 用例失败可归因远端。
# ---------------------------------------------------------------------------


def test_seeded_single_page_chain_is_content_neutral_and_eligible(
    session_factory, data_paths
):
    png_bytes = _render_neutral_single_page_png()
    png_sha = sha256(png_bytes).hexdigest()
    seeded = _seed_frozen_revision(
        session_factory,
        data_paths,
        png_bytes=png_bytes,
        png_sha256=png_sha,
    )

    with session_factory() as session:
        revision = EvidenceProcessingRevisionRepository(session).get(
            seeded["revision_id"]
        )
        assert len(revision.manifest) == 1
        assert revision.manifest[0].page_artifact_id == ARTIFACT_ID
        assert revision.manifest[0].ocr_page_id == seeded["ocr_page_id"]
        assert revision.manifest_sha256

    materials = _load_materials(session_factory, data_paths)
    assert len(materials) == 1
    material = materials[0]
    assert material.source_ref == VERSION_ID
    assert material.page_ordinal == PAGE_ORDINAL
    assert material.page_image_sha256 == png_sha
    assert material.image_bytes == png_bytes
    assert material.extraction_route == ExtractionRoute.VISION_OCR.value
    assert not material.native_extraction_anomaly

    async def runner(plan, inputs):
        assert len(plan.eligible) == 1
        assert plan.eligible[0].reasons == (VISION_REASON_SCAN_OR_IMAGE_ONLY,)
        page = inputs[0]
        return SelectiveVisionReviewOutcome(
            plan=plan,
            observations=(
                SelectiveVisionObservation(
                    source_refs=(page.source_ref,),
                    page_ordinals=(page.page_ordinal,),
                    reasons=(VISION_REASON_SCAN_OR_IMAGE_ONLY,),
                    text=f"source_ref={page.source_ref}\nfixture sanity observation",
                    model="mock-vlm",
                    finish_reason="stop",
                    usage={"total_tokens": 1},
                ),
            ),
        )

    service = SelectiveVisionObservationService(
        session_factory, review_runner=runner, default_model_id="mock-vlm"
    )
    result = asyncio.run(service.run_postprocess(materials))
    assert result.closed_error is None
    assert len(result.observations) == 1
    assert result.observations[0].source_ref == VERSION_ID
    assert result.observations[0].observation_text
    _assert_ocr_and_image_immutable(session_factory, data_paths, seeded, png_bytes)


# ---------------------------------------------------------------------------
# LIVE：真实智谱 Coding Plan GLM-5.3-Flash 单页端到端。
# ---------------------------------------------------------------------------


def test_live_single_page_real_vision_e2e_on_coding_plan(
    session_factory, data_paths, monkeypatch
):
    """显式启用：SELECTIVE_VISION_LIVE_E2E=1 + Coding Plan 凭证。

    断言只保留标量/哈希/状态与合成正文（无密钥、无真实临床材料）。
    """
    if os.getenv("SELECTIVE_VISION_LIVE_E2E", "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        pytest.skip(
            "Set SELECTIVE_VISION_LIVE_E2E=1 to run the real single-page vision e2e"
        )
    api_key = _resolve_live_api_key()
    if not api_key:
        pytest.skip(
            "No INDEPENDENT_VLM_API_KEY / OMP zhipu-coding-plan credential available"
        )
    png_bytes = _render_neutral_single_page_png()
    png_sha = sha256(png_bytes).hexdigest()

    monkeypatch.setenv("INDEPENDENT_VLM_PROVIDER", "zhipu-coding-plan")
    monkeypatch.setenv("INDEPENDENT_VLM_BASE_URL", CODING_PLAN_BASE_URL)
    monkeypatch.setenv("INDEPENDENT_VLM_API_KEY", api_key)
    monkeypatch.setenv("INDEPENDENT_VLM_MODEL", "glm-5.3-flash")
    monkeypatch.setenv("INDEPENDENT_VLM_REASONING_EFFORT", "high")
    monkeypatch.delenv("SELECTIVE_VISION_ENABLED", raising=False)
    vlm.reset_independent_vlm_client()
    try:
        cfg = vlm.require_independent_vlm_config()
        assert cfg["provider"] == "zhipu-coding-plan"
        assert cfg["base_url"] == CODING_PLAN_BASE_URL
        assert "glm" in cfg["model"].lower()
        client = vlm.get_independent_vlm_client()
        assert "/api/coding/paas/v4" in str(client.base_url), (
            f"live call must target the Coding Plan endpoint, got {client.base_url}"
        )

        seeded = _seed_frozen_revision(
            session_factory,
            data_paths,
            png_bytes=png_bytes,
            png_sha256=png_sha,
        )

        first = enqueue_selective_vision_postprocess_for_revision(
            session_factory, seeded["revision_id"], trigger="live_e2e"
        )
        second = enqueue_selective_vision_postprocess_for_revision(
            session_factory, seeded["revision_id"], trigger="live_e2e"
        )
        assert first.created is True
        assert second.job_id == first.job_id
        assert second.created is False

        # 真实执行器：不注入 review_runner，走 independent_vlm 真实传输。
        executor = create_selective_vision_postprocess_executor(
            SelectiveVisionPostprocessExecutorConfig(
                session_factory=session_factory,
                data_paths=data_paths,
            )
        )
        assert JobRunner(
            session_factory,
            {SELECTIVE_VISION_POSTPROCESS_JOB_TYPE: executor},
            worker_id="svo-live-e2e-worker",
            now=utc_now,
            poll_interval=0.01,
        ).run_once()

        with session_factory() as session:
            store = JobStore(session, now=utc_now)
            job_snapshot = store.snapshot(first.job_id)
            assert job_snapshot.state == "completed", (
                f"visual postprocess job ended in state={job_snapshot.state}"
            )
            view = SelectiveVisionPostprocessJobService(
                session_factory
            ).get_revision_task(seeded["revision_id"])

        assert view.found is True
        assert view.state == "completed"
        assert view.plan_supported is True
        assert view.eligible_page_count == 1
        assert view.observation_page_count == 1, (
            "任务投影必须反映已落盘的成功观察页数"
        )
        assert not view.closed_page_count
        assert view.closed_failure_kind is None

        if view.closed_page_count:
            with session_factory() as session:
                checkpoint = JobStore(session, now=utc_now).get_last_checkpoint(
                    first.job_id, SELECTIVE_VISION_POSTPROCESS_STEP_ID
                )
            kind = (
                (checkpoint[1] or {}).get("closed_failure_kind")
                if checkpoint
                else "unknown"
            )
            if kind == "source_fidelity":
                system_prompt, user_prompt = build_selective_vision_prompts(
                    reasons=[VISION_REASON_SCAN_OR_IMAGE_ONLY]
                )
                diagnostic = asyncio.run(
                    vlm.independent_vlm_page_chat(
                        user_prompt,
                        [
                            vlm.PageVisionInput(
                                source_ref=VERSION_ID,
                                page_ordinal=PAGE_ORDINAL,
                                media_type="image/png",
                                image_bytes=png_bytes,
                            )
                        ],
                        system_prompt=system_prompt,
                    )
                )
                pytest.fail(
                    "live call closed with source_fidelity; raw diagnostic text: "
                    f"{diagnostic.text!r}"
                )
            pytest.fail(f"Coding Plan live call closed the vision task: kind={kind}")

        with session_factory() as session:
            rows = SelectiveVisionObservationRepository(session).list_by_page_artifact(
                seeded["page_artifact_id"]
            )
        succeeded = [
            row
            for row in rows
            if row.status == SelectiveVisionObservationStatus.SUCCEEDED
        ]
        assert len(succeeded) == 1, (
            f"exactly one immutable succeeded observation expected, got {len(rows)}"
        )
        row = succeeded[0]
        assert row.source_document_version_id == VERSION_ID
        assert row.source_ref == VERSION_ID
        assert row.page_ordinal == PAGE_ORDINAL
        assert row.page_image_sha256 == png_sha
        assert row.ocr_page_id == seeded["ocr_page_id"]
        assert row.ocr_raw_text_sha256 == seeded["raw_text_sha256"]
        assert row.plan_version == SELECTIVE_VISION_PLAN_VERSION
        assert row.risk_reasons == [VISION_REASON_SCAN_OR_IMAGE_ONLY]
        assert row.failure_kind is None
        assert row.observation_text, "成功观察必须携带非空正文"
        assert f"source_ref={VERSION_ID}" in row.observation_text
        assert "glm" in (row.model_id or "").lower()
        assert row.prompt_version
        assert len(row.prompt_sha256) == 64
        assert len(row.observation_identity_sha256) == 64
        assert row.usage, "真实调用应携带用量信息"
        for token in _FORBIDDEN_OUTPUT_TOKENS:
            assert token not in (row.observation_text or ""), (
                f"observation body must stay content-neutral: {token}"
            )

        # 脱敏审计输出：仅标量与哈希指纹，不含密钥与原始响应全文。
        print(
            "\n[live-e2e] model=%s text_len=%d usage=%s identity=%s prompt_sha=%s"
            % (
                row.model_id,
                len(row.observation_text or ""),
                sorted(row.usage.keys()) if isinstance(row.usage, dict) else row.usage,
                row.observation_identity_sha256[:12],
                row.prompt_sha256[:12],
            )
        )

        _assert_ocr_and_image_immutable(
            session_factory, data_paths, seeded, png_bytes
        )
    finally:
        vlm.reset_independent_vlm_client()
