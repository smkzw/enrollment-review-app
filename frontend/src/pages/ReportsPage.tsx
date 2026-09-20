import {
  getCatalogRepository,
  type CatalogEpisodeView,
  type CatalogProjectView,
  type CatalogSubjectView,
} from "../api";
import { createReviewHistoryHttp } from "../api/review-history/reviewHistoryHttp";
import { FrozenReviewReport, reviewTime } from "../components/review/FrozenReviewReport";
import { updateParams, useHashRoute } from "../app/router";
import { useLoad } from "../app/useLoad";
import { ErrorState, EmptyState, LoadingState } from "../components/shell/Feedback";
import { ArrowLeft } from "lucide-react";
import { PreparedReviewPanel } from "../components/review/PreparedReviewPanel";
import { useApplicationMode } from "../app/applicationMode";
const historyRepository = createReviewHistoryHttp();

function centerLabel(subject: CatalogSubjectView): string {
  if (subject.centerCode !== null && subject.centerName !== null) {
    return `${subject.centerCode}｜${subject.centerName}`;
  }
  return subject.centerCode ?? subject.centerName ?? "中心信息尚未填写";
}

function episodeLabel(episode: CatalogEpisodeView): string {
  return episode.workflowStageLabel ?? episode.stageLabel;
}

interface ReportSelectionProps {
  projects: ReadonlyArray<CatalogProjectView>;
  selectedProject: CatalogProjectView;
  subjects: ReadonlyArray<CatalogSubjectView>;
  selectedSubject: CatalogSubjectView;
  episodes: ReadonlyArray<CatalogEpisodeView>;
  selectedEpisode: CatalogEpisodeView;
  onProjectChange: (projectId: string) => void;
  onSubjectChange: (subjectId: string) => void;
  onEpisodeChange: (episodeId: string) => void;
}

function ReportSelection({
  projects,
  selectedProject,
  subjects,
  selectedSubject,
  episodes,
  selectedEpisode,
  onProjectChange,
  onSubjectChange,
  onEpisodeChange,
}: ReportSelectionProps) {
  return (
    <section className="reports-controls" aria-label="选择报告对象">
      <label>
        <span>项目</span>
        <select
          aria-label="选择项目"
          value={selectedProject.projectId}
          onChange={(event) => onProjectChange(event.target.value)}
        >
          {projects.map((project) => (
            <option key={project.projectId} value={project.projectId}>
              {project.projectName} · {project.studyPhaseLabel} · 方案 {project.officialVersion}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>受试者</span>
        <select
          aria-label="选择受试者"
          value={selectedSubject.subjectId}
          onChange={(event) => onSubjectChange(event.target.value)}
        >
          {subjects.map((subject) => (
            <option key={subject.subjectId} value={subject.subjectId}>
              {subject.subjectCode} · {centerLabel(subject)}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>审核节点</span>
        <select
          aria-label="选择审核节点"
          value={selectedEpisode.reviewEpisodeId}
          onChange={(event) => onEpisodeChange(event.target.value)}
        >
          {episodes.map((episode) => (
            <option key={episode.reviewEpisodeId} value={episode.reviewEpisodeId}>
              {episodeLabel(episode)}
            </option>
          ))}
        </select>
      </label>
    </section>
  );
}

export function ReportsPage() {
  const { canModify } = useApplicationMode();
  const { params } = useHashRoute();
  const projectParam = params.get("project");
  const subjectParam = params.get("subject");
  const episodeParam = params.get("episode");
  const runParam = params.get("run");

  const projects = useLoad((signal) => getCatalogRepository().listProjects(signal), []);
  const projectList = projects.state.status === "success" ? projects.state.data : [];
  const selectedProject =
    projectParam === null
      ? projectList[0] ?? null
      : projectList.find((project) => project.projectId === projectParam) ?? null;
  const subjects = useLoad(
    (signal) => getCatalogRepository().listSubjects(selectedProject?.projectId ?? "", signal),
    [selectedProject?.projectId],
    { enabled: selectedProject !== null },
  );
  const subjectList =
    subjects.state.status === "success"
      ? subjects.state.data.filter((subject) => subject.projectId === selectedProject?.projectId)
      : [];
  const selectedSubject =
    subjectParam === null
      ? subjectList[0] ?? null
      : subjectList.find((subject) => subject.subjectId === subjectParam) ?? null;
  const episodes = useLoad(
    (signal) => getCatalogRepository().listEpisodes(selectedSubject?.subjectId ?? "", signal),
    [selectedSubject?.subjectId],
    { enabled: selectedSubject !== null },
  );
  const episodeList =
    episodes.state.status === "success"
      ? episodes.state.data.filter((episode) => episode.subjectId === selectedSubject?.subjectId)
      : [];
  const selectedEpisode =
    episodeParam === null
      ? episodeList[0] ?? null
      : episodeList.find((episode) => episode.reviewEpisodeId === episodeParam) ?? null;
  const history = useLoad(
    (signal) =>
      historyRepository.listRuns(
        selectedSubject?.subjectId ?? "",
        selectedEpisode?.reviewEpisodeId ?? "",
        { signal },
      ),
    [selectedSubject?.subjectId, selectedEpisode?.reviewEpisodeId],
    { enabled: selectedSubject !== null && selectedEpisode !== null },
  );
  const runs = history.state.status === "success"
    && history.state.data.subjectId === selectedSubject?.subjectId
    && history.state.data.reviewEpisodeId === selectedEpisode?.reviewEpisodeId
      ? history.state.data.items : [];
  const selectedRun = runParam === null ? runs.at(-1) ?? null
    : runs.find((run) => run.reviewRunId === runParam) ?? null;
  const detail = useLoad(
    (signal) => historyRepository.getRun(selectedSubject?.subjectId ?? "",
      selectedEpisode?.reviewEpisodeId ?? "", selectedRun?.reviewRunId ?? "", { signal }),
    [selectedSubject?.subjectId, selectedEpisode?.reviewEpisodeId, selectedRun?.reviewRunId],
    { enabled: selectedRun !== null },
  );

  const setProject = (projectId: string) =>
    updateParams({ project: projectId, subject: null, episode: null, run: null, action: null, workflow: null, review_request: null });
  const setSubject = (subjectId: string) =>
    updateParams({ subject: subjectId, episode: null, run: null, action: null, workflow: null, review_request: null });
  const setEpisode = (episodeId: string) => updateParams({ episode: episodeId, run: null, action: null, workflow: null, review_request: null });

  if (projects.state.status === "loading") return <LoadingState />;
  if (projects.state.status === "error") {
    return <ErrorState message={projects.state.message} onRetry={projects.retry} />;
  }
  if (projectList.length === 0) {
    return <EmptyState message="当前还没有已保存的项目。" hint="请先在方案工作台确认研究方案。" />;
  }
  if (selectedProject === null) {
    return <ErrorState message="链接中的项目不存在，请重新选择。" onRetry={() => updateParams({ project: null, subject: null, episode: null })} />;
  }
  if (subjects.state.status === "loading") return <LoadingState />;
  if (subjects.state.status === "error") {
    return <ErrorState message={subjects.state.message} onRetry={subjects.retry} />;
  }
  if (subjectList.length === 0) {
    return <EmptyState message="这个项目还没有受试者。" hint="请先在受试者资料目录中登记受试者。" />;
  }
  if (selectedSubject === null) {
    return <ErrorState message="链接中的受试者不属于当前项目，请重新选择。" onRetry={() => updateParams({ subject: null, episode: null })} />;
  }
  if (episodes.state.status === "loading") return <LoadingState />;
  if (episodes.state.status === "error") {
    return <ErrorState message={episodes.state.message} onRetry={episodes.retry} />;
  }
  if (episodeList.length === 0) {
    return <EmptyState message="该受试者还没有审核节点。" hint="请先在方案工作台确认审核节点。" />;
  }
  if (selectedEpisode === null) {
    return <ErrorState message="链接中的审核节点不存在，请重新选择。" onRetry={() => updateParams({ episode: null })} />;
  }
  const report = detail.state.status === "success"
    && detail.state.data.run.reviewRunId === selectedRun?.reviewRunId
    && detail.state.data.context.subjectId === selectedSubject.subjectId
    && detail.state.data.context.reviewEpisodeId === selectedEpisode.reviewEpisodeId
      ? detail.state.data : null;
  return (
    <div className="reports">
      <header className="page-head">
        <h1 className="page-head__title">报告</h1>
      </header>
      <div className="reports-toolbar">
        {params.has("worklist") && <a className="button"
          href={`#/actions?${new URLSearchParams(params.get("worklist") ?? "")}`}>
          <ArrowLeft size={16} aria-hidden="true" />返回待办事项
        </a>}
        <ReportSelection
          projects={projectList}
          selectedProject={selectedProject}
          subjects={subjectList}
          selectedSubject={selectedSubject}
          episodes={episodeList}
          selectedEpisode={selectedEpisode}
          onProjectChange={setProject}
          onSubjectChange={setSubject}
          onEpisodeChange={setEpisode}
        />
        {runs.length > 0 && (
          <section className="reports-controls reports-controls--run" aria-label="选择审核记录">
            <label>
              <span>审核记录</span>
              <select aria-label="选择审核记录" value={selectedRun?.reviewRunId ?? ""}
                onChange={(event) => updateParams({ run: event.target.value, action: null })}>
                {selectedRun === null && <option value="">请重新选择审核记录</option>}
                {[...runs].reverse().map((run) => <option key={run.reviewRunId} value={run.reviewRunId}>
                  {reviewTime(run.completedAt ?? run.startedAt)} · {run.status === "completed" ? "记录已保存，打开查看" : "尚未完成"}
                </option>)}
              </select>
            </label>
          </section>
        )}
      </div>
      {canModify && <PreparedReviewPanel key={`${selectedEpisode.reviewEpisodeId}:${params.get("workflow") ?? "new"}`}
        episode={selectedEpisode} workflowId={params.get("workflow")} requestKey={params.get("review_request")}
        onRequestKey={(key) => updateParams({ project: selectedProject.projectId,
          subject: selectedSubject.subjectId, episode: selectedEpisode.reviewEpisodeId, review_request: key })}
        onStarted={(workflow) => updateParams({ project: selectedProject.projectId,
          subject: selectedSubject.subjectId, episode: selectedEpisode.reviewEpisodeId, workflow })}
        onPublished={(run) => { updateParams({ project: selectedProject.projectId,
          subject: selectedSubject.subjectId, episode: selectedEpisode.reviewEpisodeId, run }); history.retry(); }}
        onNewReview={() => { updateParams({ workflow: null, review_request: null }); episodes.retry(); }} />}
      {history.state.status === "loading" ? <LoadingState />
        : history.state.status === "error" ? <ErrorState message={history.state.message} onRetry={history.retry} />
        : runs.length === 0 ? <EmptyState message="该节点尚无正式审核记录。" hint="审核完成后，报告会保留当时的资料与结论。" />
        : selectedRun === null ? <ErrorState message="链接中的审核记录不属于该节点。" onRetry={() => updateParams({ run: null })} />
        : detail.state.status === "error" ? <ErrorState message={detail.state.message} onRetry={detail.retry} />
        : report === null ? <LoadingState /> : <FrozenReviewReport report={report} onActionChanged={detail.retry} focusActionId={params.get("action")} />}
    </div>
  );
}

export default ReportsPage;
