"""判断检索任务的用户可见状态与候选结果读取（只读，不触发模型）。"""

from __future__ import annotations

from sqlalchemy.orm import sessionmaker, Session

from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.judgment_search import JudgmentSearchCoverageSummary
from app.services.evidence_app_errors import AppNotFoundError
from app.services.judgment_search_job_service import JUDGMENT_SEARCH_JOB_TYPE
from app.storage.codecs import verify_payload_sha256
from app.storage.judgment_search_repository import JudgmentSearchSummaryRepository
from app.storage.repositories import EpisodeRepository
from app.workflow.errors import JobNotFoundError
from app.workflow.jobstore import JobStore

#: 面向用户的检索状态中文说明；只描述检索状态，绝不表述临床结论。
JUDGMENT_SEARCH_STATUS_LABELS = {
    "candidates_present": "已发现疑似研究者书面判断的内容，待人工核对原件",
    "all_supplied_pages_searched_without_candidate":
        "本次提交的全部资料中未检索到研究者书面判断",
    "coverage_incomplete": "检索尚未完成（部分页面未读取或内容不清）",
}

#: 面向用户的读道/通道中文名（内部枚举不直接出现在界面文案）。
_LANE_LABELS = {"main-A": "第一次识别", "main-B": "第二次识别"}
_CHANNEL_LABELS = {"handwritten": "手写内容", "printed_analysis": "打印病历分析"}


def _requirement_label(target_text: str | None) -> str:
    """从冻结的结构化目标提取一行临床可读摘要（内部 ID 不出现在界面）。

    优先组合官方规则编号 + 组件标题；无法解析时退回原文截断，绝不显示
    requirement_id 或 JSON 转储。
    """
    if not target_text:
        return "研究者书面判断"
    import json as _json
    try:
        data = _json.loads(target_text)
    except ValueError:
        text = " ".join(target_text.split())
        return text if len(text) <= 40 else text[:39] + "…"
    if isinstance(data, dict) and data.get("identity") == "judgment_search_target/control-v1":
        control = data.get("control")
        title = control.get("title") if isinstance(control, dict) else None
        if isinstance(title, str) and title.strip():
            title = " ".join(title.split())
            return "方案补充要求：" + (title if len(title) <= 50 else title[:49] + "…")
        return "方案补充要求的研究者书面判断"
    rule = data.get("rule", {}) if isinstance(data, dict) else {}
    component = data.get("component", {}) if isinstance(data, dict) else {}
    code = str(rule.get("official_code") or component.get("display_code") or "").strip()
    title = str(component.get("title") or "").strip()
    kind = str(rule.get("kind") or "").strip()
    kind_label = {"inclusion": "入选标准", "exclusion": "排除标准"}.get(kind, "")
    parts = [p for p in (kind_label, code) if p]
    head = " ".join(parts) if parts else "研究者书面判断"
    if title:
        text = " ".join(title.split())
        head = f"{head}：{text}" if len(head) + len(text) <= 60 else f"{head}：{text[:59 - len(head)]}…"
    return head


def judgment_search_status_labels(status: str) -> str:
    return JUDGMENT_SEARCH_STATUS_LABELS.get(status, "检索状态待更新")


def _load_job(session: Session, session_factory, *, subject_id: str,
              review_episode_id: str, job_id: str):
    store = JobStore(session)
    try:
        job = store.get_job(job_id)
    except JobNotFoundError as exc:
        raise AppNotFoundError() from exc
    if job.job_type != JUDGMENT_SEARCH_JOB_TYPE:
        raise AppNotFoundError()
    frozen = verify_payload_sha256(job.payload_json, job.payload_sha256)
    authority = frozen.get("authority", {})
    if (authority.get("subject_id") != subject_id
            or authority.get("review_episode_id") != review_episode_id):
        raise AppNotFoundError()
    return job, frozen


def judgment_search_job_status(session_factory: sessionmaker[Session], *, subject_id: str,
                               review_episode_id: str, job_id: str) -> dict:
    """判断检索任务的进度与每条要求的检索状态（中文标签，不含内部字段）。"""
    with session_factory() as session:
        job, frozen = _load_job(session, session_factory, subject_id=subject_id,
                                review_episode_id=review_episode_id, job_id=job_id)
        total_pages = len(frozen.get("pages", []))
        read_steps = [
            (step_id, state) for step_id, state in (
                (step.step_id, step.state) for step in store_steps(session, job_id)
            ) if step_id.startswith("read:")
        ]
        completed_reads = sum(1 for _, state in read_steps if state == "completed")
        authority = FactAuthority.model_validate(frozen["authority"])
        summaries = JudgmentSearchSummaryRepository(session).latest_for_authority(
            authority, job_id=job_id
        )
        requirement_results = [
            {
                "requirement_id": item["requirement_id"],
                "status": summaries[item["requirement_id"]].status.value,
                "status_label": judgment_search_status_labels(
                    summaries[item["requirement_id"]].status.value),
                "found_candidate_count": len(
                    summaries[item["requirement_id"]].found_candidates),
            }
            for item in frozen.get("requirements", [])
            if item["requirement_id"] in summaries
        ]
        return {
            "job_id": job_id,
            "state": job.state,
            "state_label": _job_state_label(job.state),
            "total_pages": total_pages,
            "completed_reads": completed_reads,
            "total_reads": len(read_steps),
            "requirement_results": requirement_results,
            "can_resume": job.state == "cancelled",
        }


def judgment_search_job_results(session_factory: sessionmaker[Session], *, subject_id: str,
                                review_episode_id: str, job_id: str) -> dict:
    """每条要求的完整检索结果：候选摘录（含原件定位）与未完成缺口，供原件核对。"""
    with session_factory() as session:
        job, frozen = _load_job(session, session_factory, subject_id=subject_id,
                                review_episode_id=review_episode_id, job_id=job_id)
        authority = FactAuthority.model_validate(frozen["authority"])
        summaries = JudgmentSearchSummaryRepository(session).latest_for_authority(
            authority, job_id=job_id
        )
        results = []
        for item in frozen.get("requirements", []):
            requirement_id = item["requirement_id"]
            summary = summaries.get(requirement_id)
            if summary is None:
                results.append({
                    "requirement_id": requirement_id,
                    "requirement_label": _requirement_label(item.get("target_text")),
                    "status": None,
                    "status_label": "尚未完成检索",
                    "found_candidates": [],
                    "incomplete_pages": [],
                })
                continue
            results.append({
                "requirement_id": requirement_id,
                "requirement_label": _requirement_label(item.get("target_text")),
                "status": summary.status.value,
                "status_label": judgment_search_status_labels(summary.status.value),
                "found_candidates": [
                    {
                        "lane": candidate.lane.value,
                        "lane_label": _LANE_LABELS.get(candidate.lane.value, candidate.lane.value),
                        "channel": candidate.channel.value,
                        "channel_label": _CHANNEL_LABELS.get(candidate.channel.value, candidate.channel.value),
                        "source_document_version_id": candidate.source_document_version_id,
                        "page_artifact_id": candidate.page_artifact_id,
                        "page_number": candidate.page_number,
                        "excerpts": [excerpt.model_dump(mode="json")
                                     for excerpt in candidate.candidates],
                    }
                    for candidate in summary.found_candidates
                ],
                "incomplete_pages": _incomplete_pages(summary),
            })
        return {
            "job_id": job_id,
            "state": job.state,
            "searched_page_count": len(frozen.get("pages", [])),
            "results": results,
        }


def _incomplete_pages(summary: JudgmentSearchCoverageSummary) -> list[dict]:
    pages: dict[tuple[str, str, int], dict] = {}

    # 面向用户的原生中文：复用模块级 _LANE_LABELS/_CHANNEL_LABELS，
    # 不在函数内重复定义（避免将来只改其一导致内部枚举泄漏给用户）。
    def lane(value: str) -> str:
        return _LANE_LABELS.get(value, value)

    def channel(value: str) -> str:
        return _CHANNEL_LABELS.get(value, value)

    def mark(gap, reason: str) -> None:
        key = (gap.source_document_version_id, gap.page_artifact_id, gap.page_number)
        pages.setdefault(key, {
            "source_document_version_id": gap.source_document_version_id,
            "page_artifact_id": gap.page_artifact_id,
            "page_number": gap.page_number,
            "reasons": [],
        })
        pages[key]["reasons"].append(reason)

    for gap in summary.pages_without_lane_result:
        mark(gap, f"{lane(gap.lane.value)}未完成该页检索")
    for gap in summary.unreadable_channels:
        mark(gap, f"{lane(gap.lane.value)}的{channel(gap.channel.value)}未能读取")
    for gap in summary.ambiguous_channels:
        mark(gap, f"{lane(gap.lane.value)}的{channel(gap.channel.value)}存在歧义")
    return [pages[number] for number in sorted(pages)]


def store_steps(session: Session, job_id: str):
    return JobStore(session).list_steps(job_id)


def _job_state_label(state: str) -> str:
    from app.api.v2.vocabulary import JOB_STATE_LABELS

    return JOB_STATE_LABELS.get(state, "状态待更新")


__all__ = [
    "JUDGMENT_SEARCH_STATUS_LABELS",
    "judgment_search_job_results",
    "judgment_search_job_status",
    "judgment_search_status_labels",
]
