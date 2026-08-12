from __future__ import annotations

from pydantic import Field, model_validator

from .common import VersionedModel
from .enums import (
    ComponentDecision,
    EpisodeMainStatus,
    GapType,
    JobEventType,
    LocatorPrecision,
    LogicalOperator,
    ReviewStage,
    UploadMode,
)
from .review import FixtureV1
from .rules import RuleSet


class ProtocolDiffExample(VersionedModel):
    current_protocol_version_id: str = Field(min_length=1)
    proposed_protocol_version_id: str = Field(min_length=1)
    current_rule_set: RuleSet
    proposed_rule_set_draft: RuleSet
    added_rule_codes: list[str] = Field(min_length=1)
    deleted_rule_codes: list[str] = Field(min_length=1)
    changed_logic_or_window_codes: list[str] = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_rule_set_diff(self) -> "ProtocolDiffExample":
        current = {rule.official_code: rule for rule in self.current_rule_set.rules}
        proposed = {
            rule.official_code: rule for rule in self.proposed_rule_set_draft.rules
        }
        if self.current_rule_set.protocol_version_id != self.current_protocol_version_id:
            raise ValueError("当前 RuleSet 与当前方案版本不一致")
        if (
            self.proposed_rule_set_draft.protocol_version_id
            != self.proposed_protocol_version_id
        ):
            raise ValueError("修订草案 RuleSet 与拟议方案版本不一致")

        added = sorted(set(proposed) - set(current))
        deleted = sorted(set(current) - set(proposed))
        changed = sorted(
            code
            for code in set(current) & set(proposed)
            if current[code].model_dump(mode="json")
            != proposed[code].model_dump(mode="json")
        )
        if self.added_rule_codes != added:
            raise ValueError("新增规则编号必须由两版 RuleSet 实际差异推导")
        if self.deleted_rule_codes != deleted:
            raise ValueError("删除规则编号必须由两版 RuleSet 实际差异推导")
        if self.changed_logic_or_window_codes != changed:
            raise ValueError("逻辑或时间窗变更必须由两版 RuleSet 实际差异推导")
        return self


class UatWorkspaceFixture(VersionedModel):
    workspace_id: str = Field(min_length=1)
    protocol_diff: ProtocolDiffExample
    primary_subject_ids: list[str] = Field(min_length=6, max_length=6)
    stage_template_episode_ids: list[str] = Field(min_length=2, max_length=2)
    episodes: list[FixtureV1] = Field(min_length=14, max_length=14)

    @model_validator(mode="after")
    def validate_uat_coverage(self) -> "UatWorkspaceFixture":
        subject_stages: dict[str, set[ReviewStage]] = {}
        screening_snapshots: dict[str, str] = {}
        local_ids: dict[str, set[str]] = {
            "episode": set(),
            "snapshot": set(),
            "run": set(),
            "assessment": set(),
            "action": set(),
        }
        gap_types: set[GapType] = set()
        precisions: set[LocatorPrecision] = set()
        job_events: set[JobEventType] = set()
        max_profile_events = 0
        logical_operators: set[LogicalOperator] = set()
        time_constraint_count = 0
        rollup_statuses: set[EpisodeMainStatus] = set()

        def inspect_expression(expression) -> None:
            nonlocal time_constraint_count
            if expression.kind == "predicate":
                if expression.time_constraint is not None:
                    time_constraint_count += 1
                return
            logical_operators.add(expression.operator)
            for child in expression.children:
                inspect_expression(child)

        for fixture in self.episodes:
            subject_id = fixture.subject.subject_id
            stage = fixture.review_episode.stage
            subject_stages.setdefault(subject_id, set()).add(stage)
            local_ids["episode"].add(fixture.review_episode.review_episode_id)
            local_ids["snapshot"].add(fixture.evidence_snapshot.evidence_snapshot_id)
            local_ids["run"].update(item.review_run_id for item in fixture.review_runs)
            local_ids["assessment"].update(item.assessment_id for item in fixture.final_assessments)
            local_ids["action"].update(item.action_id for item in fixture.actions)
            gap_types.update(item.gap_type for item in fixture.actions)
            gap_types.update(gap for item in fixture.final_assessments for gap in item.gap_types)
            gap_types.update(
                item.gap_type
                for item in fixture.evidence_expectations
                if item.gap_type is not None
            )
            precisions.update(item.precision for item in fixture.evidence_spans)
            job_events.update(item.event_type for item in fixture.job_events)
            max_profile_events = max(max_profile_events, len(fixture.patient_profile.events))
            rollup_statuses.add(fixture.episode_rollup.main_status)
            for rule in fixture.rule_set.rules:
                for component in rule.components:
                    inspect_expression(component.expression)
                    if component.exception_expression is not None:
                        inspect_expression(component.exception_expression)

            composite = next(
                (
                    component
                    for rule in fixture.rule_set.rules
                    for component in rule.components
                    if component.rule_component_id == "component-ex-01"
                ),
                None,
            )
            if composite is None or composite.expression.kind != "logical":
                raise ValueError("UAT 关键复合排除规则结构缺失")
            root = composite.expression
            if (
                root.operator != LogicalOperator.ALL
                or len(root.children) != 3
                or root.children[0].kind != "predicate"
                or not root.children[0].predicate.requires_professional_judgment
                or root.children[1].kind != "logical"
                or root.children[1].operator != LogicalOperator.ANY
                or root.children[2].kind != "logical"
                or root.children[2].operator != LogicalOperator.NOT
            ):
                raise ValueError("UAT 关键复合排除规则 ALL/ANY/NOT 语义漂移")
            medication_node = next(
                (
                    child
                    for child in root.children[1].children
                    if child.kind == "predicate"
                    and child.predicate.subject == "medication"
                    and child.predicate.attribute == "prohibited_exposure"
                ),
                None,
            )
            window = medication_node.time_constraint if medication_node else None
            if (
                window is None
                or window.anchor_type.value != "randomization_date"
                or window.direction.value != "before"
                or window.upper_bound_days != 28
                or window.lower_bound_days is not None
            ):
                raise ValueError("UAT 关键随机前 28 天时间窗语义漂移")

            if stage == ReviewStage.SCREENING:
                if fixture.evidence_snapshot.upload_mode != UploadMode.FULL:
                    raise ValueError("UAT 筛选 Episode 必须提供全量快照")
                screening_snapshots[subject_id] = fixture.evidence_snapshot.evidence_snapshot_id

        episode_by_id = {
            fixture.review_episode.review_episode_id: fixture
            for fixture in self.episodes
        }
        if len(self.primary_subject_ids) != len(set(self.primary_subject_ids)):
            raise ValueError("UAT 主要受试者 ID 不得重复")
        if not set(self.stage_template_episode_ids) <= set(episode_by_id):
            raise ValueError("UAT 阶段模板 Episode 引用越界")
        if set(self.primary_subject_ids) & {
            episode_by_id[item].subject.subject_id
            for item in self.stage_template_episode_ids
        }:
            raise ValueError("阶段模板不得伪装成主要筛选/基线受试者")

        required_stages = {ReviewStage.SCREENING, ReviewStage.BASELINE}
        if any(
            subject_stages.get(subject_id) != required_stages
            for subject_id in self.primary_subject_ids
        ):
            raise ValueError("每名 UAT 受试者必须同时有筛选和基线 Episode")
        template_stages = {
            episode_by_id[item].review_episode.stage
            for item in self.stage_template_episode_ids
        }
        if template_stages != {ReviewStage.PRE_SCREENING, ReviewStage.RUN_IN}:
            raise ValueError("UAT 阶段模板必须覆盖预筛和导入/洗脱期")
        if set().union(*subject_stages.values()) != set(ReviewStage):
            raise ValueError("UAT 工作区必须覆盖全部审核阶段")

        for fixture in self.episodes:
            if (
                fixture.subject.subject_id in self.primary_subject_ids
                and fixture.review_episode.stage == ReviewStage.BASELINE
            ):
                if fixture.evidence_snapshot.upload_mode != UploadMode.INCREMENTAL:
                    raise ValueError("UAT 基线 Episode 必须演示增量快照")
                if fixture.evidence_snapshot.prior_snapshot_id != screening_snapshots[fixture.subject.subject_id]:
                    raise ValueError("UAT 基线快照必须引用同一受试者的筛选快照")
                if any(
                    item.decision == ComponentDecision.NOT_DUE
                    for item in fixture.final_assessments
                ):
                    raise ValueError("UAT 基线必须按当前快照重算，不能复制 not_due")

        if logical_operators != set(LogicalOperator):
            raise ValueError("UAT 工作区必须实际覆盖 ALL、ANY、NOT")
        if time_constraint_count == 0:
            raise ValueError("UAT 工作区必须包含可执行时间锚点/窗口")
        required_rollup_statuses = {
            EpisodeMainStatus.CLEAR_BARRIER,
            EpisodeMainStatus.CURRENT_GAP,
            EpisodeMainStatus.NO_CLEAR_BARRIER,
        }
        if not required_rollup_statuses <= rollup_statuses:
            raise ValueError("UAT 工作区必须覆盖明确障碍、当前缺口和未见明确障碍")

        for label in ("episode", "snapshot", "run"):
            if len(local_ids[label]) != len(self.episodes):
                raise ValueError(f"UAT {label} ID 必须全局唯一")
        if len(local_ids["assessment"]) != sum(
            len(item.final_assessments) for item in self.episodes
        ):
            raise ValueError("UAT FinalAssessment ID 必须全局唯一")
        if len(local_ids["action"]) != sum(len(item.actions) for item in self.episodes):
            raise ValueError("UAT ActionRequest ID 必须全局唯一")

        required_gaps = {
            GapType.RECORD_INCOMPLETE,
            GapType.REFERENCED_FILE_MISSING,
            GapType.REQUIRED_PROCEDURE_NOT_DONE,
            GapType.RESULT_FIELDS_MISSING,
            GapType.PROFESSIONAL_JUDGMENT,
            GapType.SOURCE_CONFLICT,
            GapType.OCR_OR_PARSE_RISK,
            GapType.FUTURE_STAGE_NOT_DUE,
            GapType.PROVENANCE_FOLLOWUP,
            GapType.HISTORICAL_SOURCE_UNAVAILABLE,
        }
        if not required_gaps <= gap_types:
            raise ValueError("UAT 工作区未覆盖全部核心缺口类型")
        if precisions != set(LocatorPrecision):
            raise ValueError("UAT 工作区必须覆盖四级 EvidenceSpan")
        if not {JobEventType.STEP_FAILED, JobEventType.RETRY_SCHEDULED, JobEventType.COMPLETED} <= job_events:
            raise ValueError("UAT 工作区必须包含失败、重试和完成事件")
        if max_profile_events < 6:
            raise ValueError("UAT Patient Profile 必须提供至少 6 类可浏览事件")
        return self
