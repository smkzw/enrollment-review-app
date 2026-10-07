"""共享工作台来源（``workbench:<shared_project_id>``）最小持久合同测试。

来源只是任务 payload 元数据：显式命名空间校验、按持久身份解析（不使用
浏览器本地映射）、未绑定来源不返回任何历史项目。
"""
from __future__ import annotations

from datetime import datetime
import json

import pytest
from sqlalchemy import select

from app.services.job_service import JobService
from app.services.protocol_workbench_service import (
    PROTOCOL_DECONSTRUCTION_JOB_TYPE,
    ProtocolWorkbenchService,
    ProtocolWorkbenchError,
)
from app.storage.models import JobRecord
from app.storage.codecs import utc_now
from app.services.workbench_project_origin import (
    WORKBENCH_ORIGIN_PAYLOAD_KEY,
    WorkbenchOriginError,
    job_workbench_origin,
    normalize_workbench_origin,
)


def _now() -> datetime:
    return datetime(2026, 10, 7, 12, 0)


def test_normalize_workbench_origin_requires_explicit_namespace():
    assert (
        normalize_workbench_origin(" workbench:proj_user_9 ")
        == "workbench:proj_user_9"
    )
    # 裸共享编号、其他命名空间、空编号、空值一律拒绝，不做宽容猜测。
    for rejected in (
        "proj_user_9",
        "shared:proj_user_9",
        "workbench:",
        "workbench:bad id",
        "",
        "   ",
    ):
        try:
            normalize_workbench_origin(rejected)
        except WorkbenchOriginError:
            continue
        raise AssertionError(f"应拒绝非法来源: {rejected!r}")
    assert job_workbench_origin({}) is None
    with pytest.raises(WorkbenchOriginError):
        job_workbench_origin({WORKBENCH_ORIGIN_PAYLOAD_KEY: "proj_user_9"})


def test_resolve_workbench_origin_unbound_when_no_persisted_job(
    data_paths, session_factory
):
    service = ProtocolWorkbenchService(
        session_factory, data_paths=data_paths, now=_now
    )
    view = service.resolve_workbench_origin("workbench:proj_user_9")
    assert view.entry_state == "unbound"
    assert view.job_id is None
    assert view.project is None


def test_resolve_workbench_origin_finds_persisted_job_by_payload_identity(
    data_paths, session_factory
):
    jobs = JobService(session_factory, now=_now)
    created = jobs.create_job(
        idempotency_key="workbench-origin-resolve",
        job_type=PROTOCOL_DECONSTRUCTION_JOB_TYPE,
        payload={
            "session_kind": "first_deconstruction",
            "file_name": "protocol.docx",
            WORKBENCH_ORIGIN_PAYLOAD_KEY: "workbench:proj_user_9",
        },
        steps=[],
    )
    service = ProtocolWorkbenchService(
        session_factory, data_paths=data_paths, now=_now
    )
    view = service.resolve_workbench_origin("workbench:proj_user_9")
    assert view.entry_state == "job_in_progress"
    assert view.job_id == created.job_id
    assert view.file_name == "protocol.docx"
    # 其他来源不共享该任务：不同 shared_project_id 不得假判为已绑定。
    other = service.resolve_workbench_origin("workbench:proj_user_other")
    assert other.entry_state == "unbound"


def test_corrupted_matching_job_is_not_unbound(data_paths, session_factory):
    jobs = JobService(session_factory, now=_now)
    created = jobs.create_job(idempotency_key="corrupt", job_type=PROTOCOL_DECONSTRUCTION_JOB_TYPE,
        payload={WORKBENCH_ORIGIN_PAYLOAD_KEY: "workbench:proj_user_9"}, steps=[])
    with session_factory() as session, session.begin():
        row = session.get(JobRecord, created.job_id)
        row.payload_json = json.dumps({WORKBENCH_ORIGIN_PAYLOAD_KEY: "workbench:proj_user_9", "changed": True})
    service = ProtocolWorkbenchService(session_factory, data_paths=data_paths, now=_now)
    with pytest.raises(ProtocolWorkbenchError) as error:
        service.resolve_workbench_origin("workbench:proj_user_9")
    assert error.value.code == "WORKBENCH_ORIGIN_RECORD_INVALID"


def test_first_upload_replay_and_cancelled_replacement(data_paths, session_factory):
    service = ProtocolWorkbenchService(session_factory, data_paths=data_paths, now=_now)
    source = data_paths.root / "test.docx"
    source.write_bytes(b"synthetic protocol")
    args = dict(upload_path=source, original_name="test.docx", workbench_origin="workbench:proj_user_9")
    first = service.start_first_deconstruction(**args, idempotency_key="first")
    assert service.start_first_deconstruction(**args, idempotency_key="first").job_id == first.job_id
    with pytest.raises(ProtocolWorkbenchError) as error:
        service.start_first_deconstruction(**args, idempotency_key="duplicate")
    assert error.value.code == "WORKBENCH_ORIGIN_ALREADY_BOUND"
    service.jobs.cancel(first.job_id)
    replacement = service.start_first_deconstruction(**args, idempotency_key="replacement")
    assert replacement.job_id != first.job_id
    with session_factory() as session:
        assert session.get(JobRecord, first.job_id).state == "cancelled"


def test_published_project_and_pending_redo_remain_distinct(session_factory, data_paths):
    from tests.v2.protocols.test_redeconstruction_backend import _control_refs
    from tests.v2.protocols.slice4_helpers import confirmed_fixture

    service = ProtocolWorkbenchService(session_factory, data_paths=data_paths, now=utc_now)
    source = data_paths.root / "first.docx"
    source.write_bytes(b"synthetic protocol")
    origin = "workbench:proj_user_9"
    first = service.start_first_deconstruction(upload_path=source, original_name=source.name,
        idempotency_key="origin-first", workbench_origin=origin)
    source_input, draft, spans = confirmed_fixture()
    service.seed_review_session(first.job_id, source_input=source_input, draft=draft, source_spans=spans, wait_at="publish")
    published = service.publish_first_project(first.job_id, idempotency_key="origin-publish",
        actor="测试用户",
        **_control_refs(service, data_paths, first.job_id))
    assert service.resolve_workbench_origin(origin).entry_state == "project_published"
    args = dict(upload_path=source, original_name=source.name, project_id=published.project_id, workbench_origin=origin)
    redo = service.start_re_deconstruction(**args, idempotency_key="origin-redo")
    view = service.resolve_workbench_origin(origin)
    assert view.entry_state == "job_in_progress"
    assert view.project.project_id == published.project_id
    assert view.job_id == redo.job_id
    assert service.start_re_deconstruction(**args, idempotency_key="origin-redo").job_id == redo.job_id
    with pytest.raises(ProtocolWorkbenchError) as error:
        service.start_re_deconstruction(**args, idempotency_key="second-redo")
    assert error.value.code == "WORKBENCH_ORIGIN_ALREADY_BOUND"
    service.jobs.cancel(redo.job_id)
    view = service.resolve_workbench_origin(origin)
    assert view.job_state == "cancelled" and view.project.project_id == published.project_id
    feedback = service.start_feedback_re_deconstruction(project_id=published.project_id,
        idempotency_key="origin-feedback", workbench_origin=origin)
    assert service.resolve_workbench_origin(origin).job_id == feedback.job_id


def test_redo_rejects_an_unbound_origin_before_creating_job(data_paths, session_factory):
    service = ProtocolWorkbenchService(session_factory, data_paths=data_paths, now=_now)
    source = data_paths.root / "other.docx"
    source.write_bytes(b"synthetic protocol")
    with pytest.raises(ProtocolWorkbenchError) as error:
        service.start_re_deconstruction(upload_path=source, original_name=source.name,
            project_id="other-project", idempotency_key="mismatch", workbench_origin="workbench:proj_other")
    assert error.value.code == "WORKBENCH_ORIGIN_PROJECT_MISMATCH"
    with session_factory() as session:
        assert session.execute(select(JobRecord.job_id)).first() is None
