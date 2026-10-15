"""Project directory projection; evidence readiness is not eligibility judgment."""
from dataclasses import dataclass

from app.domain.contracts.review import ReviewEpisode, Subject
from app.storage.repositories import (
    EpisodeRepository, ProjectRepository, SubjectRepository,
    ScopeViolationError, get_workflow_stages_by_ids,
)


@dataclass(frozen=True)
class ProjectEvidenceNode:
    episode: ReviewEpisode
    display_name: str


@dataclass(frozen=True)
class ProjectEvidenceSubject:
    subject: Subject
    nodes: tuple[ProjectEvidenceNode, ...]


def project_evidence_overview(session, project_id: str) -> tuple[ProjectEvidenceSubject, ...]:
    ProjectRepository(session).get(project_id)
    subjects = SubjectRepository(session).list_by_project(project_id)
    episodes = EpisodeRepository(session).list_by_project(project_id)
    by_subject: dict[str, list[ProjectEvidenceNode]] = {item.subject_id: [] for item in subjects}
    stages = get_workflow_stages_by_ids(session, [
        item.workflow_stage_id for item in episodes if item.workflow_stage_id is not None
    ])
    for episode in episodes:
        if episode.subject_id not in by_subject:
            raise ScopeViolationError("项目审核节点与受试者登记不一致")
        stage = stages.get(episode.workflow_stage_id)
        by_subject[episode.subject_id].append(ProjectEvidenceNode(
            episode=episode, display_name=stage.display_name if stage else "",
        ))
    return tuple(ProjectEvidenceSubject(subject=item, nodes=tuple(by_subject[item.subject_id]))
                 for item in sorted(subjects, key=lambda item: (item.subject_code, item.subject_id)))
