from __future__ import annotations

from pydantic import Field, model_validator

from .common import VersionedModel
from .enums import GapType, JobEventType, LocatorPrecision, ReviewStage, UploadMode
from .review import FixtureV1


class ProtocolDiffExample(VersionedModel):
    current_protocol_version_id: str = Field(min_length=1)
    proposed_protocol_version_id: str = Field(min_length=1)
    added_rule_codes: list[str] = Field(min_length=1)
    deleted_rule_codes: list[str] = Field(min_length=1)
    changed_logic_or_window_codes: list[str] = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)


class UatWorkspaceFixture(VersionedModel):
    workspace_id: str = Field(min_length=1)
    protocol_diff: ProtocolDiffExample
    episodes: list[FixtureV1] = Field(min_length=12)

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

        if len(subject_stages) < 6:
            raise ValueError("UAT 工作区至少需要 6 名受试者")
        required_stages = {ReviewStage.SCREENING, ReviewStage.BASELINE}
        if any(stages != required_stages for stages in subject_stages.values()):
            raise ValueError("每名 UAT 受试者必须同时有筛选和基线 Episode")

        for fixture in self.episodes:
            if fixture.review_episode.stage == ReviewStage.BASELINE:
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
