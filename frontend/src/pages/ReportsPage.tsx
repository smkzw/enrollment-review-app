import { useMemo } from "react";
import {
  getCatalogRepository,
  type CatalogEpisodeView,
  type CatalogProjectView,
  type CatalogSubjectView,
} from "../api";
import {
  getEligibilityReviewRepository,
  type EligibilityClauseView,
} from "../api/eligibility-review";
import { updateParams, useHashRoute } from "../app/router";
import { useLoad } from "../app/useLoad";
import { ErrorState, EmptyState, LoadingState } from "../components/shell/Feedback";
import { formatSnapshotVersion } from "../domain/labels";

function centerLabel(subject: CatalogSubjectView): string {
  if (subject.centerCode !== null && subject.centerName !== null) {
    return `${subject.centerCode}｜${subject.centerName}`;
  }
  return subject.centerCode ?? subject.centerName ?? "中心信息尚未填写";
}

function episodeLabel(episode: CatalogEpisodeView): string {
  return episode.workflowStageLabel ?? episode.stageLabel;
}

function formatGeneratedAt(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function isUndetermined(clause: EligibilityClauseView): boolean {
  return clause.decision === "professional_judgment" || clause.decision === "conflict";
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

function SubjectInformation({
  project,
  subject,
  episode,
}: {
  project: CatalogProjectView;
  subject: CatalogSubjectView;
  episode: CatalogEpisodeView;
}) {
  return (
    <section className="reports-print__section" aria-labelledby="reports-subject-title">
      <h3 id="reports-subject-title">受试者信息</h3>
      <table className="reports-print__table reports-print__subject-table">
        <tbody>
          <tr>
            <th scope="row">受试者代号</th>
            <td>{subject.subjectCode}</td>
            <th scope="row">中心</th>
            <td>{centerLabel(subject)}</td>
          </tr>
          <tr>
            <th scope="row">项目</th>
            <td>{project.projectName}</td>
            <th scope="row">研究期别</th>
            <td>{project.studyPhaseLabel}</td>
          </tr>
          <tr>
            <th scope="row">性别</th>
            <td>{subject.sex ?? "未填写"}</td>
            <th scope="row">年龄</th>
            <td>{subject.ageYears === null ? "未填写" : `${subject.ageYears} 岁`}</td>
          </tr>
          <tr>
            <th scope="row">审核节点</th>
            <td colSpan={3}>{episodeLabel(episode)}</td>
          </tr>
        </tbody>
      </table>
    </section>
  );
}

function UndeterminedSection({ clauses }: { clauses: ReadonlyArray<EligibilityClauseView> }) {
  const items = clauses.filter(isUndetermined);
  return (
    <section className="reports-print__section" aria-labelledby="reports-undetermined-title">
      <h3 id="reports-undetermined-title">
        无法判定清单 <span className="section-count">{items.length}</span>
      </h3>
      {items.length === 0 ? (
        <p className="reports-print__empty">本次结果中没有无法判定条款。</p>
      ) : (
        <ol className="reports-print__undetermined-list">
          {items.map((clause) => (
            <li key={clause.ruleCode}>
              <div className="reports-print__clause-line">
                <strong>{clause.ruleCode}</strong>
                <span className="reports-print__decision">{clause.decisionLabel}</span>
              </div>
              <p>{clause.textSummary}</p>
              <p className="reports-print__reason">{clause.reason}</p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function DecisionTable({ clauses }: { clauses: ReadonlyArray<EligibilityClauseView> }) {
  return (
    <section className="reports-print__section" aria-labelledby="reports-decisions-title">
      <h3 id="reports-decisions-title">逐条判定</h3>
      <table className="reports-print__table reports-print__decision-table">
        <thead>
          <tr>
            <th scope="col">条款</th>
            <th scope="col">类别</th>
            <th scope="col">判定</th>
            <th scope="col">原因</th>
          </tr>
        </thead>
        <tbody>
          {clauses.map((clause) => (
            <tr key={clause.ruleCode}>
              <th scope="row">
                <span>{clause.ruleCode}</span>
                <small>{clause.textSummary}</small>
              </th>
              <td>
                {clause.ruleKind === "inclusion"
                  ? "入选标准"
                  : clause.ruleKind === "exclusion"
                    ? "排除标准"
                    : "流程要求"}
              </td>
              <td>
                <span className="reports-print__badge">{clause.decisionLabel}</span>
              </td>
              <td className="reports-print__reason">{clause.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function EligibilityReport({
  project,
  subject,
  episode,
  clauses,
  ruleSetRevision,
}: {
  project: CatalogProjectView;
  subject: CatalogSubjectView;
  episode: CatalogEpisodeView;
  clauses: ReadonlyArray<EligibilityClauseView>;
  ruleSetRevision: number;
}) {
  const generatedAt = useMemo(() => formatGeneratedAt(new Date()), []);
  return (
    <article className="reports-print" data-testid="reports-print">
      <header className="reports-print__head">
        <div>
          <p className="reports-print__eyebrow">入排审核结果</p>
          <h2>{subject.subjectCode} · {episodeLabel(episode)}</h2>
        </div>
        <button
          type="button"
          className="button button--primary reports-print__action"
          onClick={() => window.print()}
        >
          生成打印版
        </button>
      </header>
      <SubjectInformation project={project} subject={subject} episode={episode} />
      <UndeterminedSection clauses={clauses} />
      <DecisionTable clauses={clauses} />
      <footer className="reports-print__footnote">
        资料版本：{formatSnapshotVersion(episode.revision, null)} · 档案版本：{formatSnapshotVersion(ruleSetRevision, null)} · 生成时间：{generatedAt}
      </footer>
    </article>
  );
}

export function ReportsPage() {
  const { params } = useHashRoute();
  const projectParam = params.get("project");
  const subjectParam = params.get("subject");
  const episodeParam = params.get("episode");

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
  const eligibility = useLoad(
    (signal) =>
      getEligibilityReviewRepository().getEligibilityReview(
        selectedSubject?.subjectId ?? "",
        selectedEpisode?.reviewEpisodeId ?? "",
        { signal },
      ),
    [selectedSubject?.subjectId, selectedEpisode?.reviewEpisodeId],
    { enabled: selectedSubject !== null && selectedEpisode !== null },
  );

  const setProject = (projectId: string) =>
    updateParams({ project: projectId, subject: null, episode: null });
  const setSubject = (subjectId: string) =>
    updateParams({ subject: subjectId, episode: null });
  const setEpisode = (episodeId: string) => updateParams({ episode: episodeId });

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
  if (eligibility.state.status === "loading") return <LoadingState />;
  if (eligibility.state.status === "error") {
    return <ErrorState message={eligibility.state.message} onRetry={eligibility.retry} />;
  }

  const report = eligibility.state.data;
  return (
    <div className="reports">
      <header className="page-head">
        <h1 className="page-head__title">报告</h1>
        <p className="page-head__note">选择项目、受试者和审核节点，查看完整的入排审核结果并生成打印版。</p>
      </header>
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
      <EligibilityReport
        project={selectedProject}
        subject={selectedSubject}
        episode={selectedEpisode}
        clauses={report.clauses}
        ruleSetRevision={report.ruleSetRevision}
      />
    </div>
  );
}

export default ReportsPage;
