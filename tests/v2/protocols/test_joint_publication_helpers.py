"""joint_publication_helpers 的可运行正例与拒绝路径。

覆盖执行合同验证项：

- 同源冻结输入 + 真实 control JobRunner 完成返回不可变 gate checkpoint；
- gate 检查点携带整源覆盖处置（含无额外控制的确定性单元闭包）；
- 发布事务真实消费 ``(control_job_id, control_checkpoint_id)``；
- 缺失 / 错配 checkpoint 被拒绝且不落任何正式规则版本。
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy import select

from app.domain.contracts.protocol_controls import ProtocolControlBatchPlan
from app.protocols.protocol_control_gate import CONTROL_PUBLICATION_GATE_VERSION
from app.projections.clause_pack import project_clause_pack, verify_clause_pack
from app.services.protocol_control_execution import (
    CANDIDATE_CONTROL_PACKAGE_RESULT_KIND,
    FORMAL_CATALOG_STATUS_NOT_MATERIALIZED,
    STEP_GATE,
)
from app.services.protocol_draft_service import ProtocolDraftService
from app.services.protocol_publication_service import (
    ProtocolPublicationRequest,
    ProtocolPublicationService,
    PublicationLineageError,
)
from app.storage.codecs import verify_payload_sha256
from app.storage.control_catalog_repository import ControlCatalogPublicationRepository
from app.storage.models import JobCheckpointRecord, JobStepRecord, RuleSetRecord
from app.storage.repositories import get_rule_set
from app.workflow.jobstore import JobStore

from tests.v2.protocols.joint_publication_helpers import seed_joint_control_publication
from tests.v2.protocols.slice4_helpers import confirmed_fixture
from tests.v2.services.test_protocol_control_execution import NOW, _now


def _save_first_draft(session_factory, draft):
    with session_factory() as session, session.begin():
        revision = ProtocolDraftService(session).save_initial_draft(
            draft, actor="测试", created_at=NOW
        )
    return revision.revision_id


@pytest.mark.parametrize("conflicting", [False, True])
def test_synthetic_source_reconstruction_cannot_omit_or_choose_material(conflicting):
    from tests.v2.protocols.joint_publication_helpers import _synthetic_structure

    source, _draft, spans = confirmed_fixture()
    if conflicting:
        other = source.source_materials[1]
        spans[other.source_span_id] = spans[other.source_span_id].model_copy(
            update={"source_ref": spans[source.source_materials[0].source_span_id].source_ref}
        )
        message = "无法唯一重建"
    else:
        source.source_materials = source.source_materials[1:]
        message = "缺少正文"
    with pytest.raises(ValueError, match=message):
        _synthetic_structure(source, spans)


def test_seed_completes_real_control_job_and_returns_immutable_gate_checkpoint(
    data_paths, session_factory
) -> None:
    source_input, draft, spans = confirmed_fixture()
    revision_id = _save_first_draft(session_factory, draft)

    control_job_id, control_checkpoint_id = seed_joint_control_publication(
        session_factory, data_paths, source_input, draft, spans, revision_id,
    )

    with session_factory() as session:
        store = JobStore(session, now=_now)
        job = store.get_job(control_job_id)
        assert job.state == "completed"
        assert not job.cancel_requested
        gate_step = session.get(JobStepRecord, (control_job_id, STEP_GATE))
        assert gate_step is not None and gate_step.state == "completed"
        checkpoint_row = session.get(JobCheckpointRecord, control_checkpoint_id)
        assert checkpoint_row is not None
        assert (checkpoint_row.job_id, checkpoint_row.step_id) == (
            control_job_id,
            STEP_GATE,
        )
        # 不可变历史：最新 gate checkpoint 即返回的保存依据，载荷哈希自洽。
        latest = store.get_last_checkpoint(control_job_id, STEP_GATE)
        assert latest is not None and latest[0] == control_checkpoint_id
        gate_payload = verify_payload_sha256(
            checkpoint_row.payload_json, checkpoint_row.payload_sha256
        )
        job_payload = verify_payload_sha256(job.payload_json, job.payload_sha256)

    assert gate_payload["stage"] == STEP_GATE
    assert gate_payload["gate_version"] == CONTROL_PUBLICATION_GATE_VERSION
    assert gate_payload["accepted"] is True
    assert gate_payload["result_kind"] == CANDIDATE_CONTROL_PACKAGE_RESULT_KIND
    assert gate_payload["formal_catalog_status"] == FORMAL_CATALOG_STATUS_NOT_MATERIALIZED

    # 冻结身份：控制任务载荷绑定同一来源与同一草稿修订。
    assert job_payload["draft_revision_id"] == revision_id
    assert job_payload["source_input"] == source_input.model_dump(mode="json")
    assert job_payload["source_spans"] == {
        span_id: span.model_dump(mode="json") for span_id, span in spans.items()
    }

    # 整源覆盖：处置计划覆盖全部结构单元，水合批次（含确定性单元闭包）
    # 逐一给出处置，不因"无额外控制"而留空。
    plan = ProtocolControlBatchPlan.model_validate(gate_payload["publication_plan"])
    manifest_unit_ids = {
        item["structure_unit_id"] for item in job_payload["coverage_manifest"]["units"]
    }
    assert plan.expected_structure_unit_ids
    assert set(plan.expected_structure_unit_ids) == manifest_unit_ids
    disposed_unit_ids = {
        unit_id
        for batch in gate_payload["batch_dispositions"]
        for unit_id in batch["owned_structure_unit_ids"]
    }
    assert disposed_unit_ids == manifest_unit_ids
    candidates = [
        candidate
        for batch in gate_payload["batch_dispositions"]
        for candidate in batch["candidates"]
    ]
    assert candidates
    assert gate_payload["candidate_ids"] == sorted(
        candidate["control_candidate_id"] for candidate in candidates
    )


def test_seed_supports_joint_publication_and_rejects_broken_checkpoint_lineage(
    data_paths, session_factory
) -> None:
    source_input, draft, spans = confirmed_fixture()
    revision_id = _save_first_draft(session_factory, draft)
    control_job_id, control_checkpoint_id = seed_joint_control_publication(
        session_factory, data_paths, source_input, draft, spans, revision_id,
        key="joint-helpers-primary", idempotency_key="joint-helpers-primary-control",
    )
    _other_job_id, other_checkpoint_id = seed_joint_control_publication(
        session_factory, data_paths, source_input, draft, spans, revision_id,
        key="joint-helpers-secondary", idempotency_key="joint-helpers-secondary-control",
    )

    service = ProtocolPublicationService(session_factory, now=_now)
    request = ProtocolPublicationRequest(
        idempotency_key="joint-helpers-publish",
        draft_revision_id=revision_id,
        source_input=source_input,
        source_spans=spans,
        actor="测试",
        published_at=NOW,
        control_job_id=control_job_id,
        control_checkpoint_id=control_checkpoint_id,
    )

    # 缺失 checkpoint：不能凭空把未保存的整理结果当作发布依据。
    with pytest.raises(PublicationLineageError, match="补充审核要求"):
        service.publish(replace(request, control_checkpoint_id="missing-checkpoint"))

    # 错配 checkpoint：另一作业的保存依据不能顶替当前任务的门禁记录。
    with pytest.raises(PublicationLineageError, match="补充审核要求"):
        service.publish(replace(request, control_checkpoint_id=other_checkpoint_id))

    with session_factory() as session:
        assert session.scalar(select(RuleSetRecord.rule_set_id)) is None

    published = service.publish(request)
    with session_factory() as session:
        rule_set = get_rule_set(
            session, published.rule_set_id, published.rule_set_revision
        )
        controls = ControlCatalogPublicationRepository(session).get_for_rule_set(
            published.rule_set_id, published.rule_set_revision
        )
        assert controls is not None
        pack = project_clause_pack(rule_set, control_publication=controls)
        verify_clause_pack(pack)
    assert {item.official_code for item in rule_set.rules} == {
        item.official_code for item in draft.proposed_rules
    }
    assert pack.clauses
    assert pack.restricted_clauses == []
    assert controls.catalog.controls
    assert pack.control_publication.publication_id == controls.publication_id
    assert service.publish(request).replay is True
