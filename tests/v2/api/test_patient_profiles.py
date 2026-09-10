"""Phase 5 Patient Profile HTTP API 合同测试（Slice 5.5，worker_03）。

通过真实 V2 应用（迁移到 head 的临时库）与
:class:`~app.services.patient_profile_service.PatientProfileService` 播种不可变
Profile revision，再经 HTTP 断言：

- ``GET /subjects/{sid}/review-episodes/{eid}/patient-profile``：当前链头 DTO，
  13 条泳道与中文标签、状态（含派生 stale）、证据导航上下文；未生成 404；
- ``GET .../patient-profile/history``：全部 revision 升序（generating/failed/
  succeeded 并存），跨受试者/未知节点 404；
- ``GET /subjects/{sid}/patient-profile-revisions/{id}``：按 ID 冻结读取，不派生
  stale；跨受试者/未知 ID 404；
- 证据深链契约：条目 ``locator_ids`` 保留 Phase 4 定位身份，``evidence_navigation``
  来自冻结权威元组，不泄露绝对路径；不显示入排主结论/行动数量/通过标签；
- 错误信封：404/422 为稳定中文 envelope，不泄露堆栈或存储类型；
- 500 事实性能回归：真实服务+投影全路径生成 500 事实 Profile，断言确定性排序、
  13 泳道全覆盖、幂等重读；测量并记录耗时（不设脆弱墙钟断言，供 Codex 验收）。
"""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime

import pytest

from app.domain.contracts.enums import (
    ExpectationStatus,
    FactGate,
    FactPolarity,
    GapType,
    GateOutcome,
    ProfileLane,
    ReviewStage,
)
from app.domain.contracts.evidence_expectations_v2 import EvidenceExpectationV2
from app.domain.contracts.facts import (
    AssertionBasis,
    ClinicalFactCandidateV2,
    FactGateResult,
)
from app.domain.contracts.patient_profile_v2 import (
    PROFILE_LANE_ORDER,
    ProfileHighlightReason,
    ProfileStatus,
    profile_items,
)
from app.services.patient_profile_service import PatientProfileService
from app.services.evidence_app_errors import AppInternalError
from app.storage.evidence_expectation_repository import EvidenceExpectationV2Repository
from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord
from app.storage.fact_repositories import (
    ClinicalFactV2Repository,
    FactGateResultRepository,
    FactNormalizationCandidateRepository,
)
from app.storage.models import ReviewEpisodeRecord
from tests.v2.projections.test_evidence_expectations import _template
from tests.v2.storage.test_fact_repositories import (
    _authority,
    _create_and_assert_fact_conflict_group,
    _date_range,
    _fact,
    _seed_chain as seed_fact_chain,
    _update_episode,
)

NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)

ERROR_KEYS = {"code", "title", "detail", "recovery_action", "correlation_id", "context"}


# ---------------------------------------------------------------- 播种助手


def _seed(client, prefix: str = "api"):
    """经应用会话工厂播种权威链并提交，使应用连接可见。"""
    factory = client.app.state.session_factory
    with factory() as session:
        chain = seed_fact_chain(session, prefix)
        session.commit()
        return chain


def _generate(client, chain, *, profile_lane: ProfileLane | None = None):
    """经应用会话工厂生成 Profile revision 并提交。"""
    factory = client.app.state.session_factory
    with factory() as session:
        if profile_lane is not None:
            ClinicalFactV2Repository(session).create(
                _fact(chain, profile_lane=profile_lane)
            )
        revision = PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        session.commit()
        return revision


def _record_status(client, chain, status: ProfileStatus):
    factory = client.app.state.session_factory
    with factory() as session:
        revision = PatientProfileService().record_status(
            session,
            authority=_authority(chain),
            status=status,
            created_at=NOW,
        )
        session.commit()
        return revision


def _bump_episode(client, review_episode_id: str, revision: int = 2) -> None:
    factory = client.app.state.session_factory
    with factory() as session:
        episode = session.get(ReviewEpisodeRecord, review_episode_id)
        _update_episode(session, episode, revision=revision)
        session.commit()


def _seed_conflict(client, chain) -> None:
    factory = client.app.state.session_factory
    with factory() as session:
        _create_and_assert_fact_conflict_group(chain, session)
        session.commit()


def _seed_expectation_gap(client, chain, gap_type=GapType.RECORD_INCOMPLETE) -> None:
    factory = client.app.state.session_factory
    with factory() as session:
        template = _template(
            session,
            chain,
            requirement_id="req",
            fact_type="vital_sign",
            due_stage=ReviewStage.SCREENING,
        )
        EvidenceExpectationV2Repository(session).project(
            EvidenceExpectationV2(
                expectation_id=f"{chain['run_id']}-exp-absent",
                authority=_authority(chain),
                template_id=template.template_id,
                status=ExpectationStatus.ABSENT,
                gap_type=gap_type,
                gap_detail="病历记录不完整",
                revision=1,
                locator_ids=[],
                coverage_fact_ids=[],
                source_coverage="none",
                created_at=NOW,
            )
        )
        session.commit()


def _bulk_fact(session, chain, i, locator_hash):
    """发布一条与最终门禁候选语义一致、泳道独立的事实（500 事实基准用）。"""
    lane = PROFILE_LANE_ORDER[i % len(PROFILE_LANE_ORDER)]
    candidate_id = f"bulk-cand-{i:04d}"
    gate_id = f"bulk-gate-{i:04d}"
    basis = AssertionBasis(
        asserted_object=f"指标{i}",
        assertion_text=f"指标{i} 数值 {i}",
        locator_id=chain["locator_id"],
        source_text_sha256=locator_hash,
    )
    FactNormalizationCandidateRepository(session).create(
        chain["call_id"],
        ClinicalFactCandidateV2(
            candidate_id=candidate_id,
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            fact_type=f"bulk_type_{i}",
            profile_lane=lane,
            polarity=FactPolarity.AFFIRMED,
            asserted_object=f"指标{i}",
            raw_value=str(i),
            canonical_value=str(i),
            unit="unitless",
            date_range=_date_range(),
            record_time=NOW,
            locator_ids=[chain["locator_id"]],
            candidate_source_semantics="objective_result",
            assertion_basis=basis,
            model_uncertainty=0.01,
            created_at=NOW,
        ),
    )
    FactGateResultRepository(session).create(
        FactGateResult(
            gate_result_id=gate_id,
            run_id=chain["run_id"],
            call_id=chain["call_id"],
            candidate_id=candidate_id,
            gate=FactGate.TRANSACTIONAL_PUBLISH,
            outcome=GateOutcome.ACCEPTED,
            reasons=[],
            created_at=NOW,
        )
    )
    return ClinicalFactV2Repository(session).create(
        _fact(
            chain,
            fact_id=f"bulk-{i:04d}",
            gate_id=gate_id,
            fact_type=f"bulk_type_{i}",
            profile_lane=lane,
            asserted_object=f"指标{i}",
            value=str(i),
            unit="unitless",
            date_range=_date_range(),
            source_candidate_ids=[candidate_id],
            gate_ids=[gate_id],
            assertion_basis=basis,
        )
    )


def _assert_error_envelope(body, *, code: str, status: int) -> None:
    assert set(body.keys()) == {"error"}
    error = body["error"]
    assert set(error.keys()) == ERROR_KEYS
    assert error["code"] == code
    assert error["title"]
    assert error["detail"]
    assert error["recovery_action"]
    assert len(error["correlation_id"]) == 32


def _latest_url(chain) -> str:
    return (
        f"/api/v2/subjects/{chain['subject_id']}/review-episodes/"
        f"{chain['review_episode_id']}/patient-profile"
    )


def _history_url(chain) -> str:
    return _latest_url(chain) + "/history"


def _revision_url(chain, revision_id: str) -> str:
    return (
        f"/api/v2/subjects/{chain['subject_id']}"
        f"/patient-profile-revisions/{revision_id}"
    )


# ---------------------------------------------------------------- 当前链头


def test_latest_profile_returns_complete_dto_with_lanes(client) -> None:
    chain = _seed(client)
    _generate(client, chain, profile_lane=ProfileLane.TARGET_DISEASE)

    response = client.get(_latest_url(chain))
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "succeeded"
    assert body["status_label"] == "已生成"
    assert body["revision"] == 1
    assert body["review_stage_label"] in {"筛选", "基线", "预筛选", "导入期"}

    # 13 条泳道按稳定展示顺序，绝不静默省略临床类别。
    assert [section["lane"] for section in body["lanes"]] == [
        lane.value for lane in PROFILE_LANE_ORDER
    ]
    lane_labels = {section["lane"]: section["lane_label"] for section in body["lanes"]}
    assert lane_labels["target_disease"] == "目标疾病"
    assert lane_labels["evidence_quality"] == "证据冲突与资料质量"

    # 事实条目落到已发布泳道，携带机器值 + 中文标签。
    fact_items = [
        item
        for section in body["lanes"]
        for item in section["items"]
        if item["kind"] == "fact"
    ]
    assert len(fact_items) == 1
    fact = fact_items[0]
    assert fact["lane"] == "target_disease"
    assert fact["lane_label"] == "目标疾病"
    assert fact["kind_label"] == "事实"
    assert fact["source_revision"] == 1
    assert fact["locator_ids"] == [chain["locator_id"]]
    assert fact["polarity"] == "affirmed"
    assert fact["polarity_label"] == "肯定"
    assert fact["source_strength_label"] == "同期客观结果"
    assert fact["value"] == "120/80"


def test_latest_profile_404_when_not_generated(client) -> None:
    chain = _seed(client)
    response = client.get(_latest_url(chain))
    assert response.status_code == 404
    body = response.json()
    _assert_error_envelope(body, code="NOT_FOUND", status=404)
    assert "还没有生成" in body["error"]["detail"]


def test_latest_profile_404_missing_episode(client) -> None:
    chain = _seed(client)
    url = (
        f"/api/v2/subjects/{chain['subject_id']}/review-episodes/"
        "no-such-episode/patient-profile"
    )
    response = client.get(url)
    assert response.status_code == 404
    _assert_error_envelope(response.json(), code="NOT_FOUND", status=404)


def test_latest_profile_404_cross_subject(client) -> None:
    chain_a = _seed(client, "api-a")
    _generate(client, chain_a, profile_lane=ProfileLane.DEMOGRAPHICS)
    # 用其他受试者路径读 A 的审核节点 -> 跨对象 404，不泄露 A 的 Profile。
    # （作用域守卫只核对审核节点归属受试者与路径受试者是否一致。）
    url = (
        f"/api/v2/subjects/other-subject/review-episodes/"
        f"{chain_a['review_episode_id']}/patient-profile"
    )
    response = client.get(url)
    assert response.status_code == 404
    _assert_error_envelope(response.json(), code="NOT_FOUND", status=404)


# ---------------------------------------------------------------- stale 派生


def test_latest_derives_stale_but_by_id_is_frozen(client) -> None:
    chain = _seed(client)
    revision = _generate(client, chain, profile_lane=ProfileLane.TARGET_DISEASE)
    assert client.get(_latest_url(chain)).json()["status"] == "succeeded"

    # 活动指针前移 -> 读取派生 stale，不改写历史行。
    _bump_episode(client, chain["review_episode_id"], revision=2)

    latest = client.get(_latest_url(chain))
    assert latest.status_code == 200
    assert latest.json()["status"] == "stale"
    assert latest.json()["status_label"] == "资料已更新，档案待重新生成"

    # 按 ID 读取保持冻结 succeeded（历史回放不被后期改写）。
    by_id = client.get(_revision_url(chain, revision.patient_profile_revision_id))
    assert by_id.status_code == 200
    assert by_id.json()["status"] == "succeeded"


# ---------------------------------------------------------------- 历史


def test_history_returns_all_revisions_in_order(client) -> None:
    chain = _seed(client)
    _record_status(client, chain, ProfileStatus.GENERATING)
    _record_status(client, chain, ProfileStatus.FAILED)
    _generate(client, chain, profile_lane=ProfileLane.DEMOGRAPHICS)

    response = client.get(_history_url(chain))
    assert response.status_code == 200
    body = response.json()
    assert body["subject_id"] == chain["subject_id"]
    assert body["review_episode_id"] == chain["review_episode_id"]
    assert [item["revision"] for item in body["items"]] == [1, 2, 3]
    assert [item["status"] for item in body["items"]] == [
        "generating",
        "failed",
        "succeeded",
    ]
    # 显式状态记录无投影：generating/failed 不带泳道/突出/生成时间。
    assert body["items"][0]["lanes"] == []
    assert body["items"][0]["highlights"] == []
    assert body["items"][0]["generated_at"] is None
    assert body["items"][2]["generated_at"] is not None

    # 状态记录不伪装成成功：succeeded 是链头完整投影。
    assert body["items"][2]["pending_review_count"] == 0


def test_history_empty_when_no_revision(client) -> None:
    chain = _seed(client)
    response = client.get(_history_url(chain))
    assert response.status_code == 200
    assert response.json()["items"] == []


# ---------------------------------------------------------------- 按 ID 冻结


def test_single_revision_by_id_frozen(client) -> None:
    chain = _seed(client)
    revision = _generate(client, chain, profile_lane=ProfileLane.TARGET_DISEASE)
    response = client.get(_revision_url(chain, revision.patient_profile_revision_id))
    assert response.status_code == 200
    body = response.json()
    assert body["patient_profile_revision_id"] == revision.patient_profile_revision_id
    assert body["status"] == "succeeded"
    assert body["revision"] == 1


def test_single_revision_by_id_404_unknown(client) -> None:
    chain = _seed(client)
    response = client.get(_revision_url(chain, "no-such-revision"))
    assert response.status_code == 404
    _assert_error_envelope(response.json(), code="NOT_FOUND", status=404)


def test_single_revision_by_id_404_cross_subject(client) -> None:
    chain_a = _seed(client, "api-a")
    revision = _generate(client, chain_a, profile_lane=ProfileLane.DEMOGRAPHICS)
    # 用其他受试者路径读取 A 的 revision -> 跨受试者 404。
    url = (
        f"/api/v2/subjects/other-subject"
        f"/patient-profile-revisions/{revision.patient_profile_revision_id}"
    )
    response = client.get(url)
    assert response.status_code == 404
    _assert_error_envelope(response.json(), code="NOT_FOUND", status=404)


# ---------------------------------------------------------------- 证据深链


def test_deep_link_contract_preserves_locators_and_navigation(client) -> None:
    chain = _seed(client)
    _generate(client, chain, profile_lane=ProfileLane.TARGET_DISEASE)
    body = client.get(_latest_url(chain)).json()

    nav = body["evidence_navigation"]
    assert nav == {
        "project_id": chain["project_id"],
        "subject_id": chain["subject_id"],
        "review_episode_id": chain["review_episode_id"],
        "evidence_snapshot_v2_id": chain["evidence_snapshot_v2_id"],
        "complete_processing_revision_id": chain["complete_processing_revision_id"],
    }

    items = [item for section in body["lanes"] for item in section["items"]]
    item_locators = [item["locator_ids"] for item in items]
    # 条目定位是 Phase 4 定位身份，绝不泄露绝对本地路径。
    assert all(locator_ids for locator_ids in item_locators)
    assert all(
        chain["locator_id"] in locator_ids for locator_ids in item_locators
    )
    assert len(body["evidence_locators"]) == 1
    locator = body["evidence_locators"][0]
    assert locator["locator_id"] == chain["locator_id"]
    assert locator["page_artifact_id"] == chain["page_artifact_id"]
    assert locator["source_document_version_id"] == chain["doc_id"]
    assert locator["page_number"] == 1
    assert locator["source_layer"] == "raw_ocr"
    assert locator["source_layer_label"] == "原始识别文字"
    assert locator["precision"] == "text_range"
    assert locator["precision_label"] == "原文文字"
    assert locator["excerpt"] == "ALT 5"
    assert locator["degradation_reason"] == "仅有文本范围"
    assert locator["bbox"] is None
    assert locator["coordinate_frame"] is None
    raw = client.get(_latest_url(chain)).text
    assert "/Users/" not in raw and chain["locator_id"] in raw


def test_locator_resolution_rejects_other_complete_revision(client) -> None:
    chain_a = _seed(client, "locator-a")
    with pytest.raises(AppInternalError, match="冻结资料版本不一致"):
        client.app.state.evidence_api_read_service.locators_by_ids(
            ["another-revision-locator"],
            complete_processing_revision_id=chain_a[
                "complete_processing_revision_id"
            ],
        )


def test_unverified_observation_is_not_presented_as_missing_judgment(client) -> None:
    chain = _seed(client)
    _seed_expectation_gap(client, chain, GapType.OBSERVATION_UNVERIFIED)
    _generate(client, chain)
    body = client.get(_latest_url(chain)).json()
    items = [item for lane in body["lanes"] for item in lane["items"]
             if item["gap_type"] == "observation_unverified"]
    assert len(items) == 1
    assert items[0]["gap_type_label"] == "资料尚待核实"
    assert items[0]["expectation_status_label"] == "资料尚待核实"


def test_highlight_dto_has_structured_reasons(client) -> None:
    chain = _seed(client)
    _seed_conflict(client, chain)
    _seed_expectation_gap(client, chain)

    revision = _generate(client, chain)
    assert revision.pending_review_count == 2
    body = client.get(_latest_url(chain)).json()
    assert body["pending_review_count"] == len(body["highlights"]) == 2
    reasons = [
        reason for highlight in body["highlights"] for reason in highlight["reasons"]
    ]
    labels = [
        label for highlight in body["highlights"] for label in highlight["reason_labels"]
    ]
    assert ProfileHighlightReason.UNRESOLVED_CONFLICT.value in reasons
    assert ProfileHighlightReason.CURRENT_DUE_EXPECTATION_GAP.value in reasons
    assert "未解决冲突" in labels
    assert "当前到期资料缺口" in labels
    highlighted_ids = {h["item_id"] for h in body["highlights"]}
    all_ids = {
        item["item_id"] for section in body["lanes"] for item in section["items"]
    }
    assert highlighted_ids <= all_ids


# ---------------------------------------------------------------- 内容边界


def test_no_verdict_or_action_fields_exposed(client) -> None:
    chain = _seed(client)
    _generate(client, chain, profile_lane=ProfileLane.TARGET_DISEASE)
    body = client.get(_latest_url(chain)).json()
    raw = json.dumps(body, ensure_ascii=False)
    # 不显示入排主结论、行动数量、通过/不通过标签。
    for forbidden in (
        "inclusion_met",
        "exclusion_triggered",
        "action_count",
        "responsibility",
        "通过",
        "不通过",
        "enrollment",
        "verdict",
    ):
        assert forbidden not in raw


def test_error_envelope_does_not_leak_internal_errors(client) -> None:
    chain = _seed(client)
    response = client.get(
        f"/api/v2/subjects/{chain['subject_id']}/patient-profile-revisions/ghost"
    )
    assert response.status_code == 404
    body = response.json()
    _assert_error_envelope(body, code="NOT_FOUND", status=404)
    raw = json.dumps(body, ensure_ascii=False)
    assert "sqlalchemy" not in raw.lower()
    assert "NotFoundError" not in raw


# ---------------------------------------------------------------- 500 事实


def test_500_fact_projection_and_deterministic_ordering(client) -> None:
    """500 事实全路径（服务+投影+HTTP 读取）正确性与确定性排序回归。

    覆盖 13 条泳道；两次读取条目排序完全一致；重读幂等。计时仅记录并报告给
    Codex，不做脆弱墙钟断言（性能验收由 Codex 负责）。
    """
    chain = _seed(client, "bulk")
    factory = client.app.state.session_factory
    with factory() as session:
        locator_row = session.get(
            EvidenceLocatorArtifactRecord, chain["locator_id"]
        )
        locator_hash = locator_row.source_text_sha256
        for i in range(500):
            _bulk_fact(session, chain, i, locator_hash)
        session.commit()

    with factory() as session:
        revision = PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        session.commit()

    items = profile_items(revision)
    assert len(items) == 500

    t0 = time.perf_counter()
    first = client.get(_latest_url(chain)).json()
    t1 = time.perf_counter()
    second = client.get(_latest_url(chain)).json()
    t2 = time.perf_counter()

    assert first["status"] == "succeeded"
    lane_sections = first["lanes"]
    assert [s["lane"] for s in lane_sections] == [
        lane.value for lane in PROFILE_LANE_ORDER
    ]
    # 13 条泳道全覆盖（500 事实按 13 泳道循环分布，无空泳道被省略）。
    assert all(s["items"] for s in lane_sections)
    first_ids = [item["item_id"] for s in lane_sections for item in s["items"]]
    second_ids = [item["item_id"] for s in second["lanes"] for item in s["items"]]
    assert len(first_ids) == 500
    # 500 个条目共享同一原文定位时，详情只返回一份，不随条目数重复膨胀。
    assert [item["locator_id"] for item in first["evidence_locators"]] == [
        chain["locator_id"]
    ]
    assert first_ids == second_ids  # 确定性排序：两次读取完全一致
    # 每个泳道内按 (kind, source_id) 稳定排序。
    for section in lane_sections:
        keys = [(item["kind"], item["source_id"]) for item in section["items"]]
        assert keys == sorted(keys)

    # 计时仅供 Codex 性能验收参考，不做墙钟断言。
    print(
        f"[benchmark] 500-fact latest read took "
        f"{(t1 - t0):.3f}s and {(t2 - t1):.3f}s (read/repeat)"
    )
