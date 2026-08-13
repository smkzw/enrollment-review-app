/**
 * 新建项目页面（UAT-P1-02）。
 * 页面只承载本地演示选择；完成后保留项目、方案版本、研究期别和独立审核节点摘要。
 */

import { useState } from "react";
import { getDefaultRepository } from "../api";
import { navigate, RouteLink } from "../app/router";
import { useLoad } from "../app/useLoad";
import { useSessionState } from "../app/useSessionState";
import { UAT_KEY_CREATED_PROJECT } from "../app/uatTrialState";
import {
  ProjectCreationDialog,
  type CreatedProjectView,
} from "../components/board/ProjectCreationDialog";
import { ErrorState, LoadingState } from "../components/shell/Feedback";
import { stageLabel } from "../domain/labels";

const STUDY_PHASE_LABELS: Readonly<Record<string, string>> = {
  phase_i: "Ⅰ期",
  phase_ii: "Ⅱ期",
  phase_iii: "Ⅲ期",
  phase_iv: "Ⅳ期",
};

function displayStudyPhase(value: string): string {
  return STUDY_PHASE_LABELS[value] ?? value;
}

function parseCreatedProject(value: unknown): CreatedProjectView | null {
  if (typeof value !== "object" || value === null) return null;
  const candidate = value as Record<string, unknown>;
  const stage = candidate.selectedStage;
  if (
    typeof candidate.projectCode !== "string" ||
    typeof candidate.projectName !== "string" ||
    typeof candidate.protocolVersion !== "string" ||
    typeof candidate.studyPhase !== "string" ||
    (stage !== "pre_screening" && stage !== "screening" && stage !== "run_in" && stage !== "baseline")
  ) {
    return null;
  }
  return {
    projectCode: candidate.projectCode,
    projectName: candidate.projectName,
    protocolVersion: candidate.protocolVersion,
    studyPhase: candidate.studyPhase,
    selectedStage: stage,
  };
}

export function ProjectCreationPage() {
  const { state, retry } = useLoad(
    () => getDefaultRepository().getBoard(),
    [],
  );
  const [createdProject, setCreatedProject, resetCreatedProject] =
    useSessionState<CreatedProjectView | null>(
      UAT_KEY_CREATED_PROJECT,
      null,
      (value) => (value === null ? null : parseCreatedProject(value)),
    );
  const [isDialogOpen, setIsDialogOpen] = useState(true);

  if (state.status === "loading") {
    return <LoadingState />;
  }
  if (state.status === "error") {
    return <ErrorState message={state.message} onRetry={retry} />;
  }

  const board = state.data;
  const handleClose = () => navigate("/board");
  const resetDemo = () => {
    resetCreatedProject();
    setIsDialogOpen(true);
  };

  return (
    <div className="project-creation-page">
      <header className="page-head">
        <h1 className="page-head__title">新建项目</h1>
        <p className="page-head__note">
          本次试用数据仅用于体验操作，不会写入正式项目资料。
        </p>
      </header>

      {createdProject === null ? (
        <section className="project-creation-page__intro" aria-labelledby="project-creation-intro-title">
          <h2 id="project-creation-intro-title">从方案建立一个新的审核项目</h2>
          <p>
            先核对方案版本，再确认研究期别，最后选择一个独立审核节点。筛选期和基线/随机前不会合并。
          </p>
        </section>
      ) : (
        <section
          className="project-creation-result"
          aria-labelledby="project-creation-result-title"
          role="status"
        >
          <div className="project-creation-result__head">
            <div>
              <p className="project-creation-result__eyebrow">本次试用项目</p>
              <h2 id="project-creation-result-title">项目已建立</h2>
            </div>
            <span className="status-badge status-badge--ok">已保存本次选择</span>
          </div>

          <p className="project-creation-result__current">
            当前位置：{stageLabel[createdProject.selectedStage]}
          </p>

          <dl className="project-creation-result__summary">
            <div>
              <dt>项目名称</dt>
              <dd>{createdProject.projectName}</dd>
            </div>
            <div>
              <dt>项目标识</dt>
              <dd>{createdProject.projectCode}</dd>
            </div>
            <div>
              <dt>方案版本</dt>
              <dd>{createdProject.protocolVersion}</dd>
            </div>
            <div>
              <dt>研究期别</dt>
              <dd>{displayStudyPhase(createdProject.studyPhase)}</dd>
            </div>
            <div>
              <dt>当前审核节点</dt>
              <dd>{stageLabel[createdProject.selectedStage]}</dd>
            </div>
          </dl>

          <div className="project-creation-result__stage-proof" aria-label="阶段独立性说明">
            <span className="project-creation-result__stage project-creation-result__stage--current">
              当前已进入：{stageLabel[createdProject.selectedStage]}
            </span>
            <span className="project-creation-result__stage">
              基线/随机前：另一个独立审核节点
            </span>
          </div>

          <p className="project-creation-result__note">
            筛选期与基线/随机前是两个独立审核节点，不合并为一个总状态。新项目未带入旧项目或其他阶段资料。
          </p>
          <div className="project-creation-result__empty">
            <strong>当前项目尚无受试者资料</strong>
            <span>本次试用只保留方案、研究期别和审核节点选择。</span>
          </div>

          <div className="project-creation-result__actions">
            <button type="button" className="button" onClick={resetDemo}>
              恢复试用初始状态
            </button>
            <RouteLink to="/board" className="button button--quiet">
              返回原项目看板
            </RouteLink>
          </div>
        </section>
      )}

      {isDialogOpen && createdProject === null && (
        <ProjectCreationDialog
          project={board.project}
          stages={board.stages}
          onComplete={(project) => {
            setCreatedProject(project);
            setIsDialogOpen(false);
          }}
          onClose={handleClose}
        />
      )}
    </div>
  );
}

export default ProjectCreationPage;
