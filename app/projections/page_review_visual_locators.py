"""R3 视觉定位纯投影：把已采信页级视觉来源集合投影为诚实降级定位工件。

本模块只做纯函数投影：消费 ``PageVisualEvidenceSourceSet`` 的已验证序列化，
不物化来源、不写存储、不发布、不改既有修订，也不重复
``materialize_page_visual_evidence_sources`` 的服务端物化。每条已采信事实/
手写来源的每条主读读道各产生一个定位工件：摘录逐字来自原始判读读道，两条
读道摘录不同时各自保留，绝不合成合并句或发明事实。

诚实边界：

- 定位固定 ``page_excerpt`` 精度、``degraded`` 真实性、无任何坐标；视觉
  路线不执行原文检索消歧，``unique_match`` 只表示定位身份由读道与摘录哈希
  唯一内容寻址，不代表做过检索消歧或页上无重复文本。
- ``source_text_sha256`` 永远是所选判读摘录的真实 sha256；页图哈希只存在
  于类型化视觉溯源绑定中，原图哈希与摘录文本哈希严格分立。
- 内容寻址不等于来源真实性：持久化、回读与发布前必须按仓库记录重新核对
  权威绑定与原记录（本投影不承担该职责）。
"""
from __future__ import annotations

import hashlib

from app.domain.contracts.enums import (
    DisambiguationOutcome,
    LocatorAuthenticity,
    LocatorPrecision,
    LocatorSourceLayer,
)
from app.domain.contracts.evidence_locator import (
    EvidenceLocatorArtifact,
    PageReviewVisualProvenance,
    locator_anchor_hash,
)
from app.domain.page_review_evidence_sources import (
    PageVisualEvidenceSourceSet,
    VisualFactReading,
    VisualHandwritingReading,
)
from app.domain.publication import canonical_hash

PAGE_REVIEW_VISUAL_LOCATOR_ALGORITHM_VERSION = "page_review_visual_locator/v1"

#: 视觉定位的固定中文降级原因：无坐标、不做原文检索消歧。
VISUAL_LOCATOR_DEGRADATION_REASON = (
    "视觉摘录定位：来自页级双主读判读的逐字摘录，不绘制坐标红框，"
    "不执行原文检索消歧"
)


def _excerpt_sha256(excerpt: str) -> str:
    return hashlib.sha256(excerpt.encode("utf-8")).hexdigest()


def visual_locator_id(
    *,
    source_set_id: str,
    source_target_id: str,
    page_review_id: str,
    excerpt_sha256: str,
) -> str:
    """视觉定位的确定性内容身份（来源集合、来源目标、读道与摘录哈希）。"""
    return "visual-locator:" + canonical_hash({
        "identity": "page_review_visual_locator/v1",
        "source_set_id": source_set_id,
        "source_target_id": source_target_id,
        "page_review_id": page_review_id,
        "excerpt_sha256": excerpt_sha256,
    })[:32]


def project_visual_locators(
    source_set: PageVisualEvidenceSourceSet,
) -> tuple[EvidenceLocatorArtifact, ...]:
    """把一个页级视觉来源集合投影为不可变降级定位工件（纯函数）。

    输入先按 ``model_validate(model_dump())`` 重验证：上游合同对象未冻结，
    ``model_copy``/字段改写可以绕过其验证器。来源集合与原始判读读道保持
    不变；空来源集合产生空元组。
    """
    source_set = PageVisualEvidenceSourceSet.model_validate(source_set.model_dump())

    def build_locator(
        reading: VisualFactReading | VisualHandwritingReading,
        source_target_id: str,
    ) -> EvidenceLocatorArtifact:
        excerpt = reading.observation.region.excerpt
        excerpt_sha256 = _excerpt_sha256(excerpt)
        return EvidenceLocatorArtifact(
            locator_id=visual_locator_id(
                source_set_id=source_set.source_set_id,
                source_target_id=source_target_id,
                page_review_id=reading.page_review_id,
                excerpt_sha256=excerpt_sha256,
            ),
            page_artifact_id=source_set.page_artifact_id,
            ocr_page_id=None,
            source_document_version_id=source_set.source_document_version_id,
            page_number=source_set.page_number,
            source_layer=LocatorSourceLayer.PAGE_REVIEW_VISUAL,
            source_text_sha256=excerpt_sha256,
            target_id=source_target_id,
            precision=LocatorPrecision.PAGE_EXCERPT,
            bbox=None,
            coordinate_frame=None,
            sidecar_sha256=None,
            text_start=None,
            text_end=None,
            excerpt=excerpt,
            anchor_hash=locator_anchor_hash(
                page_artifact_id=source_set.page_artifact_id,
                source_layer=LocatorSourceLayer.PAGE_REVIEW_VISUAL,
                source_text_sha256=excerpt_sha256,
                precision=LocatorPrecision.PAGE_EXCERPT,
                target_id=source_target_id,
                excerpt=excerpt,
                disambiguation=DisambiguationOutcome.UNIQUE_MATCH,
                degradation_reason=None,
            ),
            disambiguation=DisambiguationOutcome.UNIQUE_MATCH,
            locator_algorithm_version=PAGE_REVIEW_VISUAL_LOCATOR_ALGORITHM_VERSION,
            authenticity=LocatorAuthenticity.DEGRADED,
            degradation_reason=VISUAL_LOCATOR_DEGRADATION_REASON,
            page_review_visual=PageReviewVisualProvenance(
                source_set_id=source_set.source_set_id,
                coverage_id=source_set.coverage_id,
                processing_revision_id=source_set.evidence_processing_revision_id,
                source_target_id=source_target_id,
                page_review_id=reading.page_review_id,
                page_image_sha256=source_set.page_image_sha256,
            ),
            created_at=source_set.created_at,
        )

    locators: list[EvidenceLocatorArtifact] = []
    for fact_source in source_set.fact_sources:
        for reading in fact_source.readings:
            locators.append(build_locator(reading, fact_source.fact_source_id))
    for handwriting_source in source_set.handwriting_sources:
        for reading in handwriting_source.readings:
            locators.append(build_locator(reading, handwriting_source.handwriting_source_id))
    return tuple(locators)


__all__ = [
    "PAGE_REVIEW_VISUAL_LOCATOR_ALGORITHM_VERSION",
    "VISUAL_LOCATOR_DEGRADATION_REASON",
    "project_visual_locators",
    "visual_locator_id",
]
