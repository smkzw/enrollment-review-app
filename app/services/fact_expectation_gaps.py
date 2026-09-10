"""资料期望结构化缺口信号推导与修订重投影源重建的唯一共享入口。

原始终结（``fact_normalization_executor`` finalize）与人工事实修订重投影
（``fact_correction_service._reproject_expectations``）必须使用同一份信号推导：
否则修订重投影会丢弃原运行按未解决项/被拒候选结构化记录的风险（静默升级），
或在到期模板失去全部覆盖且无信号时以 ``ProjectionInputError`` 回滚整次合法修订。

边界（与投影器契约一致，缺口绝不从散文推断）：

- 具体信号只来自持久化结构化记录：逐页未解决项与被拒候选事务门禁；
- 到期模板无具体信号时补 ``fallback_only`` 兜底信号（研究者判断要求给
  ``observation_unverified``，其余给 ``record_incomplete``）；
- 修订重投影只选择当前权威下活动实体引用的运行，加上每条活动实体与本次修订
  目标沿不可变修订记录回溯可达的运行；绝不收集全部历史运行或已被丢弃的分支，
  也绝不因事实被取代而推断风险已解除；
- 被拒候选的压制使用当前未被取代的已发布事实所支持的资料要求，历史「曾经
  接受」的候选不得继续压制其风险信号；
- 先前期望中无法按所选源记录复核的具体输入信号，以非默认 ``observation_unverified``
  保守保留（detail 关联该先期同权威期望；具体/兜底按冻结的 ``input_gap_signals``
  精确判断，绝不从可见状态反推），绝不改写历史期望行，也绝不把旧缺口原样
  断言为事实；先期明确为兜底/无信号的期望允许在完整证据到达时解除，历史
  来源未知（None）按未解决保守处理。

本模块只依赖 domain/storage/workflow.errors，不依赖任何 service，避免循环导入。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Literal

from sqlalchemy.orm import Session

from app.domain.contracts.enums import (
    ExpectationStatus,
    FactGate,
    GapType,
    GateOutcome,
    SourceStrength,
)
from app.domain.contracts.evidence_expectations_v2 import CoverageGapSignal
from app.domain.contracts.evidence_normalizer import (
    PersistedEvidenceNormalizerUnresolvedItem,
)
from app.domain.contracts.fact_corrections import FactCorrectionV2
from app.domain.contracts.facts import (
    ClinicalFactCandidateV2,
    FactAuthority,
    FactGateResult,
)
from app.domain.contracts.judgment_search import (
    JudgmentSearchCoverageStatus,
    JudgmentSearchCoverageSummary,
)
from app.projections.evidence_expectations import stage_rank
from app.storage.evidence_expectation_repository import (
    EvidenceExpectationV2Repository,
)
from app.storage.fact_correction_repository import FactCorrectionRepository
from app.storage.judgment_search_repository import JudgmentSearchSummaryRepository
from app.storage.fact_repositories import (
    ClinicalEventV2Repository,
    ClinicalFactV2Repository,
    FactGateResultRepository,
    FactNormalizationCandidateRepository,
    FactNormalizationRunRepository,
    FactNormalizationUnresolvedItemRepository,
    MedicationExposureV2Repository,
    Phase5RepositoryError,
)
from app.storage.repositories import (
    EpisodeRepository,
    InvalidReferenceError,
    NotFoundError,
    list_expectation_templates,
)
from app.workflow.errors import StepFailure

__all__ = [
    "EXPECTATION_INPUT_INCOMPLETE_CODE",
    "ReprojectionLineageError",
    "corrections_by_new_entity",
    "expectation_gap_signals",
    "reconstruct_reprojection_gap_signals",
    "select_reprojection_source_runs",
    "trace_correction_lineage",
]

_EXPECTATION_INPUT_INCOMPLETE_CODE = "EVIDENCE_EXPECTATION_INPUT_INCOMPLETE"
EXPECTATION_INPUT_INCOMPLETE_CODE = _EXPECTATION_INPUT_INCOMPLETE_CODE

_TargetKind = Literal["fact", "event", "exposure"]


def expectation_gap_signals(
    session: Session,
    authority: FactAuthority,
    unresolved_items: list[PersistedEvidenceNormalizerUnresolvedItem],
    *,
    fact_candidates: list[ClinicalFactCandidateV2] | None = None,
    gate_results: list[FactGateResult] | None = None,
    accepted_requirements: set[str] | None = None,
    judgment_search_summaries: Mapping[str, JudgmentSearchCoverageSummary] | None = None,
    _templates_lookup=None,
    _episode_lookup=None,
) -> list[CoverageGapSignal]:
    """由未解决项与被拒候选门禁推导结构化缺口信号（终结与重投影共用）。

    ``_templates_lookup`` / ``_episode_lookup`` 仅供 ``fact_normalization_executor``
    的兼容别名注入其模块全局依赖（既有单测按模块名 monkeypatch 这两个名字）；
    缺省使用本模块绑定，生产行为与提取前完全一致。

    ``accepted_requirements``：显式「当前已接受资料要求」覆盖。None（原始终结）
    保持既有行为——由本次传入候选/门禁的 ACCEPTED 结果推导；修订重投影必须传入
    当前权威下未被取代的已发布事实所支持的资料要求集合：历史运行中「曾经接受」
    的候选可能已被取代或解除绑定，不得再据此压制被拒候选的具体风险信号。

    ``judgment_search_summaries``：当前权威下书面判断检索的每条要求最新覆盖
    摘要（requirement_id → summary）。双读完整且全部供给页均未检索到候选时，
    研究者判断要求的兜底缺口升级为 ``professional_judgment``（限定"本次提交
    资料"措辞）；检索发现候选或覆盖不完整时保持 ``observation_unverified``，
    不把候选当已确认判断、也不把检索失败当判断缺失。
    """
    templates_lookup = _templates_lookup or list_expectation_templates
    episode_lookup = _episode_lookup or EpisodeRepository
    templates = templates_lookup(
        session, authority.rule_set_id, authority.rule_set_revision
    )
    by_requirement = {template.requirement_id: template for template in templates}
    signals: list[CoverageGapSignal] = []
    for unresolved in unresolved_items:
        item = unresolved.item
        if item.gap_type is None:
            continue
        for requirement_id in item.affected_requirement_ids:
            template = by_requirement.get(requirement_id)
            if template is None:
                raise StepFailure(
                    retryable=False,
                    error_code=_EXPECTATION_INPUT_INCOMPLETE_CODE,
                    detail=f"未解决项引用的资料要求 {requirement_id} 没有当前规则修订模板。",
                )
            signals.append(CoverageGapSignal(
                kind=item.gap_type,
                detail=item.reason,
                referenced_file_id=item.referenced_file_id,
                applies_to_template_id=template.template_id,
            ))
    if fact_candidates and gate_results:
        final_outcome = {
            result.candidate_id: result
            for result in gate_results
            if result.gate == FactGate.TRANSACTIONAL_PUBLISH
        }
        if accepted_requirements is None:
            accepted_requirements = {
                requirement_id
                for candidate in fact_candidates
                if final_outcome.get(candidate.candidate_id) is not None
                and final_outcome[candidate.candidate_id].outcome == GateOutcome.ACCEPTED
                for requirement_id in candidate.supported_requirement_ids
            }
        for candidate in fact_candidates:
            result = final_outcome.get(candidate.candidate_id)
            if result is None or result.outcome == GateOutcome.ACCEPTED:
                continue
            detail = "原始资料中发现相关记录，但尚未通过事实完整性核对"
            if result.reasons:
                detail += "：" + "；".join(result.reasons)
            for requirement_id in candidate.supported_requirement_ids:
                if requirement_id in accepted_requirements:
                    continue
                template = by_requirement.get(requirement_id)
                if template is None:
                    raise StepFailure(
                        retryable=False,
                        error_code=_EXPECTATION_INPUT_INCOMPLETE_CODE,
                        detail=f"被拒候选引用的资料要求 {requirement_id} 没有当前规则修订模板。",
                    )
                signals.append(CoverageGapSignal(
                    kind=GapType.OCR_OR_PARSE_RISK,
                    detail=detail,
                    applies_to_template_id=template.template_id,
                ))
    unique = {
        json.dumps(signal.model_dump(mode="json"), ensure_ascii=False, sort_keys=True): signal
        for signal in signals
    }
    signals = [unique[key] for key in sorted(unique)]
    concrete_gap_types = {
        GapType.OBSERVATION_UNVERIFIED,
        GapType.REFERENCED_FILE_MISSING,
        GapType.PROFESSIONAL_JUDGMENT,
        GapType.REQUIRED_PROCEDURE_NOT_DONE,
        GapType.RESULT_FIELDS_MISSING,
        GapType.DESCRIPTION_INSUFFICIENT,
        GapType.OCR_OR_PARSE_RISK,
        GapType.RECORD_INCOMPLETE,
        GapType.DATE_OR_ANCHOR_MISSING,
    }
    signaled_template_ids = {
        signal.applies_to_template_id
        for signal in signals
        if signal.applies_to_template_id is not None
        and signal.kind in concrete_gap_types
    }
    episode = episode_lookup(session).get(authority.review_episode_id)
    for template in templates:
        if (
            template.template_id in signaled_template_ids
            or stage_rank(template.due_stage) > stage_rank(episode.stage)
            or (
                template.due_stage == episode.stage
                and template.workflow_stage_id != episode.workflow_stage_id
            )
        ):
            continue
        required_source_types = {
            item.strip().casefold() for item in template.required_source_types
        }
        needs_investigator_judgment = (
            "investigator_assessment" in required_source_types
        )
        if needs_investigator_judgment:
            search_summary = (judgment_search_summaries or {}).get(
                template.requirement_id
            )
            if (
                search_summary is not None
                and search_summary.status
                == JudgmentSearchCoverageStatus.ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE
            ):
                # 双读完整且本次提交的全部供给页均未检索到候选：报告限定范围的
                # 专业判断缺口；不宣称研究者从未判断，也不要求用户二次确认。
                signals.append(CoverageGapSignal(
                    fallback_only=True,
                    kind=GapType.PROFESSIONAL_JUDGMENT,
                    detail=(
                        "本次提交的资料中未见与该项要求对应的研究者书面判断，"
                        f"因此暂无法判定是否符合：{template.description}"
                        "（已对本次提交的全部资料完成两路独立检索）"
                    ),
                    applies_to_template_id=template.template_id,
                ))
                continue
            if (
                search_summary is not None
                and search_summary.status
                == JudgmentSearchCoverageStatus.CANDIDATES_PRESENT
            ):
                signals.append(CoverageGapSignal(
                    fallback_only=True,
                    kind=GapType.OBSERVATION_UNVERIFIED,
                    detail=(
                        "资料中已发现疑似研究者书面判断的内容，尚需对照原件核对"
                        f"其指向与作者后才能用于判定：{template.description}"
                    ),
                    applies_to_template_id=template.template_id,
                ))
                continue
        signals.append(
            CoverageGapSignal(
                fallback_only=True,
                kind=(
                    GapType.OBSERVATION_UNVERIFIED
                    if needs_investigator_judgment
                    else GapType.RECORD_INCOMPLETE
                ),
                detail=(
                    f"现有资料尚未核实是否包含本条要求的记录，暂无法判定：{template.description}"
                    if needs_investigator_judgment
                    else f"当前尚无已核实的相关记录：{template.description}"
                ),
                applies_to_template_id=template.template_id,
            )
        )
    return signals


class ReprojectionLineageError(ValueError):
    """修订谱系无法按不可变记录追溯（成环、汇聚分支、实体/运行缺失或跨权威）。"""


def corrections_by_new_entity(
    corrections: list[FactCorrectionV2],
) -> dict[str, FactCorrectionV2]:
    """按新实体建立修订入边索引；汇聚分支（同一新实体被指两次）直接拒绝。"""
    by_new: dict[str, FactCorrectionV2] = {}
    for item in corrections:
        existing = by_new.get(item.new_entity_id)
        if existing is not None:
            raise ReprojectionLineageError(
                f"新实体 {item.new_entity_id} 被修订 "
                f"{existing.correction_id} 与 {item.correction_id} 同时指向，"
                "谱系无法唯一追溯"
            )
        by_new[item.new_entity_id] = item
    return by_new


def trace_correction_lineage(
    by_new_entity: dict[str, FactCorrectionV2],
    *,
    target_kind: str,
    target_id: str,
) -> list[str]:
    """从修订目标沿不可变修订入边回溯全部祖先目标（含自身）；成环即拒绝。

    纯函数：只消费调用方提供的不可变修订合同，不做存储访问；迭代前进并以
    已访问集合防环，不存在无界递归。
    """
    chain = [target_id]
    visited = {target_id}
    current = target_id
    while True:
        parent = by_new_entity.get(current)
        if parent is None:
            return chain
        if parent.target_kind != target_kind:
            raise ReprojectionLineageError(
                f"修订 {parent.correction_id} 的目标类型 {parent.target_kind} "
                f"与本次修订类型 {target_kind} 不一致，谱系不可信"
            )
        if parent.target_id in visited:
            raise ReprojectionLineageError(
                f"修订谱系在 {parent.target_id} 成环，拒绝据此重投影资料期望"
            )
        visited.add(parent.target_id)
        chain.append(parent.target_id)
        current = parent.target_id


def select_reprojection_source_runs(
    session: Session,
    *,
    authority: FactAuthority,
    target_kind: _TargetKind,
    target_id: str,
) -> list[str]:
    """选择修订重投影允许使用的源运行（确定性升序、去重、逐运行校验权威）。

    选择范围 = 当前权威下每一条未被修订取代的活动事实/事件/暴露 ∪ 本次修订
    目标，各自沿不可变修订记录回溯全部祖先实体，取这些实体引用的运行。
    只修正当前目标而遗漏其他活动实体的谱系，会让它们原始运行的未解决项在
    无关修订后被静默丢弃。任一实体或运行缺失、跨权威即视为谱系损坏并拒绝；
    绝不纳入已被丢弃的分支或全部历史运行。
    """
    corrections = FactCorrectionRepository(session).list_by_authority(authority)
    by_new_entity = corrections_by_new_entity(corrections)
    superseded = {item.target_id for item in corrections}
    repositories = {
        "fact": ClinicalFactV2Repository(session),
        "event": ClinicalEventV2Repository(session),
        "exposure": MedicationExposureV2Repository(session),
    }
    entities: set[tuple[str, str]] = set()
    for kind, repository in repositories.items():
        for entity in repository.list_for_authority(authority):
            entity_id = getattr(entity, f"{kind}_id")
            if entity_id not in superseded:
                entities.add((kind, entity_id))
    entities.add((target_kind, target_id))
    lineage_entities: set[tuple[str, str]] = set()
    for kind, entity_id in sorted(entities):
        lineage_entities.update(
            (kind, ancestor_id)
            for ancestor_id in trace_correction_lineage(
                by_new_entity, target_kind=kind, target_id=entity_id
            )
        )
    run_ids: set[str] = set()
    for kind, entity_id in sorted(lineage_entities):
        try:
            entity = repositories[kind].get(entity_id)
        except (NotFoundError, InvalidReferenceError, Phase5RepositoryError) as exc:
            raise ReprojectionLineageError(
                f"修订谱系/活动实体 {kind} {entity_id} 不存在，拒绝重投影"
            ) from exc
        if entity.authority != authority:
            raise ReprojectionLineageError(
                f"实体 {entity_id} 的权威元组与本次修订不一致，拒绝重投影"
            )
        run_ids.add(entity.run_id)
    run_repository = FactNormalizationRunRepository(session)
    for run_id in sorted(run_ids):
        try:
            run = run_repository.get(run_id)
        except (NotFoundError, InvalidReferenceError, Phase5RepositoryError) as exc:
            raise ReprojectionLineageError(
                f"所选源运行 {run_id} 缺少持久化运行记录，拒绝重投影"
            ) from exc
        if run.authority != authority:
            raise ReprojectionLineageError(
                f"源运行 {run_id} 的权威元组与本次修订不一致，拒绝将其纳入重投影"
            )
    return sorted(run_ids)


def _signal_key(signal: CoverageGapSignal) -> str:
    """信号的结构化规范化键：五元组全等（kind/detail/file/模板/fallback）。"""
    from app.domain.publication import canonical_hash

    return canonical_hash(signal.model_dump(mode="json"))


def _prior_unreconfirmed_signals(
    session: Session,
    *,
    authority: FactAuthority,
    concrete_signals: list[CoverageGapSignal],
) -> list[CoverageGapSignal]:
    """先期无法按源记录复核的具体输入，以非默认 ``observation_unverified`` 保守保留。

    精确策略（绝不从可见状态反推，也绝不把旧临床缺口原样断言为事实）：

    - 只读取同一权威元组下该模板的最新期望；其他审核节点/旧权威不参与；
    - ``prior.status`` 为 ``observed`` / ``not_due``：无未解决状态，不补；
    - ``prior`` 为纯来源强度弱覆盖（``observed_weak`` + ``provenance_followup``，
      不依赖任何输入信号）：不补——弱覆盖由事实来源强度自然重放，除非出现
      具体不确定性依据；
    - 先期 ``input_gap_signals`` 为 ``[]`` 或纯 fallback 清单（明确已知）：
      不补——纯兜底缺口允许在完整证据到达时解除，不得无谓降级真实完整覆盖；
    - 先期 ``input_gap_signals`` 携带具体（非 fallback）信号时，逐模板做精确
      覆盖判定：只有当先期每一条适用该模板的具体信号都被当前重建信号以
      结构化规范化全等（kind/detail/referenced_file/模板绑定/fallback 五元组，
      绝不按 kind 或 detail 子串近似匹配）复现时才不补；任何一条未被复现
      （包括出现了另一条同 kind 不同 detail 的新信号）即补一条非默认
      ``observation_unverified``，其 detail 关联该先期同权威期望 ID。
      未复现只代表无法确认，绝不解释为已解决；
    - 先期 ``input_gap_signals`` 为 None（历史数据，来源未知）：未知按未解决
      处理，保守补 ``observation_unverified``，且不受任何当前新具体信号影响。
    """
    templates = list_expectation_templates(
        session, authority.rule_set_id, authority.rule_set_revision
    )
    episode = EpisodeRepository(session).get(authority.review_episode_id)
    repository = EvidenceExpectationV2Repository(session)
    pads: list[CoverageGapSignal] = []
    for template in templates:
        if stage_rank(template.due_stage) > stage_rank(episode.stage):
            continue
        prior = repository.latest_by_template(
            authority.review_episode_id, template.template_id
        )
        if prior is None or prior.authority != authority:
            continue
        if prior.status in (ExpectationStatus.OBSERVED, ExpectationStatus.NOT_DUE):
            continue
        if (
            prior.status == ExpectationStatus.OBSERVED_WEAK
            and prior.gap_type == GapType.PROVENANCE_FOLLOWUP
        ):
            continue
        prior_input = prior.input_gap_signals
        if prior_input is None:
            pads.append(_prior_pad_signal(template, prior, legacy_provenance=True))
            continue
        prior_concrete = [
            signal
            for signal in prior_input
            if not signal.fallback_only
            and signal.applies_to_template_id in (None, template.template_id)
        ]
        if not prior_concrete:
            continue
        current_concrete_keys = {
            _signal_key(signal)
            for signal in concrete_signals
            if not signal.fallback_only
            and signal.applies_to_template_id in (None, template.template_id)
        }
        if all(_signal_key(signal) in current_concrete_keys for signal in prior_concrete):
            continue
        pads.append(_prior_pad_signal(template, prior, legacy_provenance=False))
    return pads


def _prior_pad_signal(
    template, prior, *, legacy_provenance: bool
) -> CoverageGapSignal:
    reason = (
        "先前期望 "
        f"{prior.expectation_id} 的输入信号来源未知（历史数据），"
        "其未解决状态无法确认是否为兜底提示，保守保留较弱覆盖状态"
        if legacy_provenance
        else f"先前期望 {prior.expectation_id} 携带具体输入缺口信号，"
        "暂无法按所选源运行记录复核，保守保留较弱覆盖状态"
    )
    return CoverageGapSignal(
        kind=GapType.OBSERVATION_UNVERIFIED,
        fallback_only=False,
        detail=reason,
        applies_to_template_id=template.template_id,
    )


def reconstruct_reprojection_gap_signals(
    session: Session,
    *,
    authority: FactAuthority,
    target_kind: _TargetKind,
    target_id: str,
) -> list[CoverageGapSignal]:
    """按同一推导从所选源运行重建修订重投影的结构化缺口信号。

    具体信号来自所选运行的持久化未解决项与事务门禁结果；被拒候选的压制使用
    当前权威下未被取代的已发布事实所支持的资料要求（历史「曾经接受」的候选
    可能已被取代或解除绑定，不得据此继续压制）；到期模板按共用推导补 fallback
    兜底；先期无法按源记录复核的具体输入按保守策略保留。
    """
    run_ids = select_reprojection_source_runs(
        session, authority=authority, target_kind=target_kind, target_id=target_id
    )
    corrections = FactCorrectionRepository(session).list_by_authority(authority)
    superseded = {item.target_id for item in corrections}
    # 覆盖判定契约：``SourceStrength.UNVERIFIABLE`` 的事实既非完整也非较弱覆盖
    # （app/projections/evidence_expectations.py::_coverage_verdict 判为 none），
    # 因此也不得进入「当前已接受资料要求」去压制被拒候选的具体风险信号。
    accepted_requirements: set[str] = {
        requirement_id
        for fact in ClinicalFactV2Repository(session).list_for_authority(authority)
        if fact.fact_id not in superseded
        and fact.source_strength != SourceStrength.UNVERIFIABLE
        for requirement_id in fact.supported_requirement_ids
    }
    unresolved_items: list[PersistedEvidenceNormalizerUnresolvedItem] = []
    fact_candidates: list[ClinicalFactCandidateV2] = []
    gate_results: list[FactGateResult] = []
    for run_id in run_ids:
        unresolved_items.extend(
            FactNormalizationUnresolvedItemRepository(session).list_by_run(run_id)
        )
        fact_candidates.extend(
            candidate
            for candidate in FactNormalizationCandidateRepository(
                session
            ).list_by_run(run_id)
            if isinstance(candidate, ClinicalFactCandidateV2)
        )
        gate_results.extend(
            result
            for result in FactGateResultRepository(session).list_by_run(run_id)
            if result.gate == FactGate.TRANSACTIONAL_PUBLISH
        )
    unresolved_items.sort(key=lambda item: (item.run_id, item.unresolved_item_id))
    signals = expectation_gap_signals(
        session,
        authority,
        unresolved_items,
        fact_candidates=fact_candidates,
        gate_results=gate_results,
        accepted_requirements=accepted_requirements,
        judgment_search_summaries=JudgmentSearchSummaryRepository(
            session
        ).latest_for_authority(authority),
    )
    signals.extend(
        _prior_unreconfirmed_signals(
            session, authority=authority, concrete_signals=signals
        )
    )
    unique = {
        json.dumps(signal.model_dump(mode="json"), ensure_ascii=False, sort_keys=True): signal
        for signal in signals
    }
    return [unique[key] for key in sorted(unique)]
