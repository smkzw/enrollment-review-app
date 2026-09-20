"""只读的同资料同配置批量耗时参考（正式审核批量 / 原件批量重新识别）。

边界（与既有批量执行链同源，但不参与其状态机）：

- 只读投影：只读取既有持久记录（jobs / job_steps / job_checkpoints / job_events、
  批次冻结载荷、审核准备上下文与权威元组），不创建任务、不写状态、不新表、不迁移、
  不调用模型；读取配置与识别方式由调用方传入，本模块不自行发现私有配置。
- 参考口径是「同一资料、同一配置、成员顺序完全相同的整个已完成批次墙钟」：
  父任务 created_at → 该父任务唯一的 COMPLETED 事件。它天然包含成员之间的维护
  回路轮询空隙、子任务排队与重试退避，是用户感知口径；既不是把子任务时长相加，
  也不是按页数推算（设计书要求按历史中位数估计并明确标注为估算）。
- 这是保守的同源历史参考，不是对新受试者的校准预测：没有同源历史时如实返回
  不可估算（时长全为 null），绝不借用其他受试者、其他节点、其他规模或改过配置的
  批次凑样本。

样本资格（任一条不满足即不计入；只记录稳定原因码，不写任何状态）：

- 父批次 state=completed、未被请求取消，且整个事件序列无失败/取消/重试/恢复/
  用户等待事件（父子任务同一规则）；
- 全部成员子任务当前 state=completed，成员步骤与检查点如实记录 completed，
  载荷哈希、归属与冻结身份全部可核实；
- 可比性身份完全一致：审核批量要求 routes 与 task_versions 等于当前配置、成员
  上下文权威元组等于当前审核节点权威元组；OCR 批量要求 profile_sha256 等于当前
  识别方式；成员顺序与来源四元组与本次选择完全一致；
- 时间戳存在且可比较，秒数有限且非负（无效或负时长一律拒绝）。

上限与缺失（显式约定）：

- 只扫描最近 HISTORY_LIMIT 个同项目同类型批次，多取一条仅用于 history_truncated；
- n=0 时长全为 null；n=1..2 只给中位数、区间为 null；n>=3 用标准库 statistics 的
  inclusive 四分位给出下界/上界，并给出中位数；
- 秒数按毫秒四舍五入（round(…, 3)），同一批记录输出完全可复现；
- 费用未知就是未知：本仓库没有任何已核实的单价/费率来源，也不存在「本地识别即
  免费」的依据，因此恒返回 amount=None / currency=None 与原因码，绝不返回 0 或
  折算金额；本模块也不做 token 聚合与费率表。
"""
from __future__ import annotations

import logging
import math
import statistics
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from sqlalchemy import func, select

from app.domain.contracts.enums import JobEventType, SnapshotStatus
from app.services import batch_evidence_reprocessing as ocr_batch_records
from app.services import batch_review_workflow as review_batch_records
from app.services.evidence_app_errors import EvidenceAppError
from app.services.evidence_reprocessing import ReprocessingError, _source
from app.services.fact_normalization_command_service import authority_from_active_episode
from app.services.page_review_job_service import route_identity
from app.services.prepared_review_workflow import current_review_task_versions
from app.storage.codecs import PersistedContractInvalid, to_utc_naive
from app.storage.evidence_repositories import EvidenceSnapshotRepository
from app.storage.models import JobRecord
from app.storage.repositories import (
    EpisodeRepository,
    ProjectRepository,
    RepositoryError,
    ScopeViolationError,
)
from app.storage.review_context_repository import ReviewContextV2Repository
from app.workflow.jobstore import EventRow, JobStore

METHOD = "same-source-batch-history/v1"
# 与两个批量入口及各自 API Member 模型一致：subject/review_episode/snapshot/complete。
MEMBER_KEYS = ("subject_id", "review_episode_id", "snapshot_id", "complete_id")
MEMBER_LIMIT = 50
HISTORY_LIMIT = 100
COST_UNKNOWN_REASON = "no_verified_billing_basis"
# 失败、取消、人工重试、恢复与用户等待：任一出现即不能当作成功完成样本。
_REJECTED_EVENT_TYPES = frozenset({
    JobEventType.STEP_FAILED, JobEventType.FAILED, JobEventType.RETRY_SCHEDULED,
    JobEventType.CANCEL_REQUESTED, JobEventType.CANCELLED, JobEventType.WAITING_USER,
    JobEventType.USER_RESUMED, JobEventType.USER_UPDATED,
})
# 恢复路径另以载荷标记出现（步骤从 running 恢复为 completed、退避重置等）。
_RECOVERY_EVENT_REASONS = frozenset({
    "lease_recovery", "attempt_budget_exhausted_during_recovery", "recovery_attempts_exhausted",
})
logger = logging.getLogger(__name__)


def estimate_processing_batch(session, *, project_id: str, kind: Literal["review", "ocr"],
                              members: Sequence[Mapping[str, str]],
                              routes: Mapping[Any, Any] | None = None,
                              adapter: Any = None) -> dict:
    """同资料同配置的历史批量耗时参考；只读，不返回费用金额。

    返回 ``{project_id, kind, member_count, method, sample_count, median_seconds,
    lower_seconds, upper_seconds, source_batch_ids, excluded_count, history_truncated,
    cost}``：``excluded_count`` 是扫描到但未计为样本的最近批次数量（不同选择、
    不同配置、状态或事件不合格、载荷/归属/时间戳无法核实等），
    ``sample_count == 0`` 时三个时长字段全为 null（不可估算）。
    """
    requested = _requested_member_keys(members)
    if kind not in ("review", "ocr"):
        raise ScopeViolationError("暂不支持该批量类型。")
    identity = _comparability_identity(session, project_id=project_id, kind=kind,
                                       requested=requested, routes=routes, adapter=adapter)
    rows, history_truncated = _recent_project_batches(session, project_id=project_id, kind=kind)
    durations: list[float] = []
    source_batch_ids: list[str] = []
    excluded_count = 0
    for row in rows:
        seconds = _sample_seconds(session, kind=kind, row=row, requested=requested, identity=identity)
        if seconds is None:
            excluded_count += 1
            continue
        durations.append(seconds)
        source_batch_ids.append(row.job_id)
    median_seconds, lower_seconds, upper_seconds = _duration_summary(durations)
    return {"project_id": project_id, "kind": kind, "member_count": len(requested),
            "method": METHOD, "sample_count": len(durations),
            "median_seconds": median_seconds, "lower_seconds": lower_seconds,
            "upper_seconds": upper_seconds, "source_batch_ids": source_batch_ids,
            "excluded_count": excluded_count, "history_truncated": history_truncated,
            "cost": {"amount": None, "currency": None, "reason": COST_UNKNOWN_REASON}}


def _requested_member_keys(members) -> tuple[tuple[str, str, str, str], ...]:
    """校验本次选择：1..50 个不同审核节点、四元组齐全，保持提交顺序。"""
    if (not isinstance(members, Sequence) or isinstance(members, (str, bytes, bytearray))
            or not 1 <= len(members) <= MEMBER_LIMIT):
        raise ScopeViolationError(f"请一次选择1至{MEMBER_LIMIT}份不同的审核资料")
    keys: list[tuple[str, str, str, str]] = []
    episodes: set[str] = set()
    for item in members:
        if (not isinstance(item, Mapping) or set(item) != set(MEMBER_KEYS)
                or any(not isinstance(item[key], str) or not item[key].strip()
                       for key in MEMBER_KEYS)):
            raise ScopeViolationError("批量成员资料不完整，请刷新后重新选择。")
        if item["review_episode_id"] in episodes:
            raise ScopeViolationError("同一审核节点不能在本批中重复提交。")
        episodes.add(item["review_episode_id"])
        keys.append(tuple(item[key] for key in MEMBER_KEYS))
    return tuple(keys)


def _comparability_identity(session, *, project_id: str, kind: str, requested, routes,
                            adapter) -> dict:
    """冻结本次选择的可比性身份，并用既有只读校验器核对当前资料/节点身份。"""
    ProjectRepository(session).get(project_id)
    identity: dict[str, Any] = {"project_id": project_id, "kind": kind}
    if kind == "review":
        if not isinstance(routes, Mapping):
            raise ScopeViolationError("缺少当前读取配置，无法给出同配置耗时参考。")
        identity["routes"] = {lane.value: route_identity(route) for lane, route in routes.items()}
        identity["task_versions"] = current_review_task_versions()
        identity["authorities"] = {key[1]: _current_review_authority(
            session, project_id=project_id, key=key) for key in requested}
        return identity
    fingerprint = getattr(adapter, "profile_fingerprint", None)
    if not isinstance(fingerprint, str) or not fingerprint.strip():
        raise ScopeViolationError("缺少当前识别方式，无法给出同配置耗时参考。")
    identity["profile_sha256"] = fingerprint
    for key in requested:
        _require_current_ocr_source(session, project_id=project_id, key=key)
    return identity


def _current_review_authority(session, *, project_id: str, key):
    """审核节点当前权威元组；必须覆盖本次选择的原件与完成修订。"""
    subject_id, review_episode_id, snapshot_id, complete_id = key
    try:
        authority = authority_from_active_episode(session, review_episode_id)
    except (EvidenceAppError, RepositoryError) as exc:
        raise ScopeViolationError("所选审核节点当前没有可用的活动资料版本，请刷新后重新选择。") from exc
    if (authority.project_id, authority.subject_id, authority.review_episode_id) != (
            project_id, subject_id, review_episode_id):
        raise ScopeViolationError("所选审核节点不属于当前研究项目。")
    if (authority.evidence_snapshot_v2_id, authority.complete_processing_revision_id) != (
            snapshot_id, complete_id):
        raise ScopeViolationError("所选审核资料与当前启用的资料版本不一致，请刷新后重新选择。")
    return authority


def _require_current_ocr_source(session, *, project_id: str, key) -> None:
    """原件与完整修订必须属于该受试者/节点，且仍是当前启用版本。"""
    subject_id, review_episode_id, snapshot_id, complete_id = key
    try:
        _source(session, project_id=project_id, subject_id=subject_id,
                review_episode_id=review_episode_id, snapshot_id=snapshot_id,
                complete_id=complete_id)
    except (ReprocessingError, RepositoryError) as exc:
        raise ScopeViolationError("所选资料不存在或不属于当前受试者和审核节点，请刷新后重新选择。") from exc
    try:
        episode = EpisodeRepository(session).get(review_episode_id)
    except RepositoryError as exc:
        raise ScopeViolationError("找不到对应的审核节点，请刷新后重新选择。") from exc
    if (episode.active_evidence_snapshot_id != snapshot_id
            or episode.active_evidence_processing_revision_id != complete_id
            or EvidenceSnapshotRepository(session).current_status(snapshot_id) != SnapshotStatus.ACTIVE):
        raise ScopeViolationError("所选资料的当前版本已变化，请刷新后重新选择。")


def _recent_project_batches(session, *, project_id: str, kind: str) -> tuple[list[JobRecord], bool]:
    """最近 HISTORY_LIMIT 个同项目同类型批次；多取一条仅用于 history_truncated。"""
    job_type, owner = (review_batch_records.BATCH_JOB_TYPE, review_batch_records.OWNER) \
        if kind == "review" else (ocr_batch_records.BATCH_JOB_TYPE, ocr_batch_records.OWNER)
    rows = list(session.scalars(select(JobRecord).where(
        JobRecord.job_type == job_type,
        func.json_extract(JobRecord.payload_json, "$.execution_owner") == owner,
        func.json_extract(JobRecord.payload_json, "$.project_id") == project_id,
    ).order_by(JobRecord.created_at.desc(), JobRecord.job_id.desc()).limit(HISTORY_LIMIT + 1)))
    return rows[:HISTORY_LIMIT], len(rows) > HISTORY_LIMIT


def _sample_seconds(session, *, kind: str, row: JobRecord, requested, identity) -> float | None:
    """一个历史批次的完整墙钟秒数；不符合样本资格返回 None。"""
    batch_id = row.job_id
    if row.state != "completed" or row.cancel_requested:
        return _exclude(batch_id, "batch_not_completed")
    try:
        _, payload = _batch_material(kind, session, batch_id)
    except (PersistedContractInvalid, RepositoryError):
        return _exclude(batch_id, "batch_payload_unverifiable")
    if payload.get("project_id") != identity["project_id"]:
        return _exclude(batch_id, "batch_project_mismatch")
    if kind == "review":
        if (payload.get("routes") != identity["routes"]
                or payload.get("task_versions") != identity["task_versions"]):
            return _exclude(batch_id, "review_config_mismatch")
        batch_keys = _review_member_keys(session, payload, identity["authorities"],
                                         expected_count=len(requested))
    else:
        if payload.get("profile_sha256") != identity["profile_sha256"]:
            return _exclude(batch_id, "ocr_profile_mismatch")
        batch_keys = _ocr_member_keys(payload)
    if batch_keys is None:
        return _exclude(batch_id, "batch_members_unverifiable")
    if batch_keys != requested:
        return _exclude(batch_id, "member_selection_mismatch")
    if not _members_completed(session, kind=kind, batch_id=batch_id, payload=payload,
                              member_count=len(requested)):
        return _exclude(batch_id, "member_completion_unverified")
    return _completed_window_seconds(session, row)


def _exclude(batch_id: str, reason: str) -> None:
    """排除一个历史批次：只记录稳定原因码，不写状态、不影响其他批次。"""
    logger.debug("批量耗时样本排除 %s：%s", batch_id, reason)
    return None


def _batch_material(kind: str, session, batch_id: str):
    """复用两个批量模块既有的载荷哈希/合同/归属读取校验器（只读）。"""
    return (review_batch_records.material(session, batch_id) if kind == "review"
            else ocr_batch_records.material(session, batch_id))


def _batch_children(kind: str, session, batch_id: str, payload):
    """已核实归属的成员子任务；审核批量按 context_id 归类，OCR 批量按成员序号归类。"""
    return (review_batch_records.owned_workflows(session, batch_id, payload) if kind == "review"
            else ocr_batch_records.owned_children(session, batch_id, payload))


def _batch_validate(kind: str, session, batch_id: str, payload, owned) -> None:
    """复用既有的「已完成成员检查点」校验器；不满足即抛存储层错误。"""
    validator = (review_batch_records.validate_completed_members if kind == "review"
                 else ocr_batch_records.validate_completed_members)
    validator(session, batch_id, payload, owned)


def _ocr_member_keys(payload) -> tuple[tuple[str, str, str, str], ...] | None:
    """OCR 批次成员来源四元组；结构不完整返回 None。"""
    members = payload.get("members")
    if not isinstance(members, list):
        return None
    keys = []
    for item in members:
        if (not isinstance(item, Mapping)
                or any(not isinstance(item.get(key), str) for key in MEMBER_KEYS)):
            return None
        keys.append(tuple(item[key] for key in MEMBER_KEYS))
    return tuple(keys)


def _review_member_keys(session, payload, authorities, *, expected_count: int
                        ) -> tuple[tuple[str, str, str, str], ...] | None:
    """审核批次成员来源四元组：由冻结上下文的权威元组推导，且必须等于当前权威元组。

    审核批次的成员身份是 ``context_id``（API 亦如此），而估算的选择键是原件与完成
    修订；这里用「上下文自身的 context_sha256 + 权威元组」把两者对齐：节点当前
    revision、方案/规则版本、活动资料指针与本次选择不一致的历史批次一律不采用。
    成员数不同直接排除，避免为不可能命中的批次逐个读取上下文。
    """
    members = payload.get("members")
    if not isinstance(members, list) or len(members) != expected_count:
        return None
    keys: list[tuple[str, str, str, str]] = []
    for item in members:
        if not isinstance(item, Mapping):
            return None
        if item.get("review_episode_id") not in authorities:
            return None
        context_id, context_sha256 = item.get("context_id"), item.get("context_sha256")
        if not isinstance(context_id, str) or not isinstance(context_sha256, str):
            return None
        try:
            context = ReviewContextV2Repository(session).get(context_id)
        except (PersistedContractInvalid, RepositoryError):
            return None
        if context.context_sha256 != context_sha256:
            return None
        authority = context.authority
        if (authority.subject_id, authority.review_episode_id) != (
                item.get("subject_id"), item.get("review_episode_id")):
            return None
        if authorities.get(authority.review_episode_id) != authority:
            return None
        keys.append((authority.subject_id, authority.review_episode_id,
                     authority.evidence_snapshot_v2_id, authority.complete_processing_revision_id))
    if len({key[1] for key in keys}) != len(keys):
        return None
    return tuple(keys)


def _members_completed(session, *, kind: str, batch_id: str, payload, member_count: int) -> bool:
    """全部成员子任务已完成、检查点如实记录 completed，且事件与归属可核实。"""
    store = JobStore(session)
    steps = store.list_steps(batch_id)
    if ({item.step_id for item in steps} != {f"member_{index}" for index in range(member_count)}
            or any(item.state != "completed" for item in steps)):
        return False
    try:
        owned = _batch_children(kind, session, batch_id, payload)
        _batch_validate(kind, session, batch_id, payload, owned)
    except (PersistedContractInvalid, RepositoryError):
        return False
    if len(owned) != member_count:
        return False
    for index in range(member_count):
        checkpoint = store.get_last_checkpoint(batch_id, f"member_{index}")
        if checkpoint is None or checkpoint[1].get("member_state") != "completed":
            return False
    for child, _source in owned.values():
        # 成员子任务当前必须仍为 completed：后续单独重试过的子任务不能充当原样本。
        if (child.state != "completed" or child.cancel_requested
                or _completed_window_seconds(session, child) is None):
            return False
    return True


def _completed_window_seconds(session, row: JobRecord) -> float | None:
    """父批次 created_at → 唯一 COMPLETED 事件；非有限或负时长一律拒绝。"""
    events = _verified_events(JobStore(session), row.job_id)
    if events is None:
        return _exclude(row.job_id, "batch_events_invalid")
    created_at = to_utc_naive(row.created_at)
    completed_at = to_utc_naive(events[-1].event.occurred_at)
    if created_at is None or completed_at is None:
        return _exclude(row.job_id, "timestamps_missing")
    seconds = (completed_at - created_at).total_seconds()
    if not math.isfinite(seconds) or seconds < 0:
        return _exclude(row.job_id, "duration_invalid")
    return seconds


def _verified_events(store: JobStore, job_id: str) -> list[EventRow] | None:
    """无非正常事件、且以唯一 COMPLETED 收束的事件序列；否则 None。"""
    events = store.list_event_rows(job_id)
    if not events or events[-1].event.event_type != JobEventType.COMPLETED:
        return None
    completed = 0
    previous_at = None
    for item in events:
        event = item.event
        occurred_at = to_utc_naive(event.occurred_at)
        if occurred_at is None or (previous_at is not None and occurred_at < previous_at):
            return None
        previous_at = occurred_at
        if event.event_type in _REJECTED_EVENT_TYPES:
            return None
        if (event.payload.get("recovered_from_checkpoint")
                or event.payload.get("reason") in _RECOVERY_EVENT_REASONS):
            return None
        if event.event_type == JobEventType.COMPLETED:
            completed += 1
    return events if completed == 1 else None


def _duration_summary(durations: list[float]) -> tuple[float | None, float | None, float | None]:
    """n=0 全部 null；n=1..2 只给中位数；n>=3 给中位数与 inclusive 四分位区间。"""
    values = sorted(durations)
    if not values:
        return None, None, None
    median_seconds = round(float(statistics.median(values)), 3)
    if len(values) < 3:
        return median_seconds, None, None
    lower, _, upper = statistics.quantiles(values, n=4, method="inclusive")
    return median_seconds, round(float(lower), 3), round(float(upper), 3)
