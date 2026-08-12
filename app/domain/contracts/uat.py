from __future__ import annotations

from pydantic import Field, model_validator

from .common import VersionedModel
from .enums import GapType, JobEventType, LocatorPrecision, ReviewStage, UploadMode
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
