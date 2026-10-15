/**
 * 从方案新建项目的本地演示流程（UAT-P1-02）。
 * 只在浏览器会话中记录选择，不写入正式项目或受试者资料。
 */

import { useEffect, useId, useRef, useState } from "react";
import { stageLabel } from "../../domain/labels";
import type { ReviewStage } from "../../domain/enums";
import type { ProjectSummaryView, StageInfoView } from "../../domain/viewModels";
import { CheckIcon, CloseIcon, OpenIcon } from "../shell/icons";

export interface CreatedProjectView {
  projectCode: string;
  projectName: string;
  protocolVersion: string;
  studyPhase: string;
  selectedStage: ReviewStage;
}

interface ProjectCreationDialogProps {
  project: ProjectSummaryView;
  stages: ReadonlyArray<StageInfoView>;
  onComplete: (project: CreatedProjectView) => void;
  onClose: () => void;
}

type CreationStep = "protocol" | "phase" | "stage";

const STUDY_PHASE_LABELS: Readonly<Record<string, string>> = {
  phase_i: "Ⅰ期",
  phase_ii: "Ⅱ期",
  phase_iii: "Ⅲ期",
  phase_iv: "Ⅳ期",
};

function displayStudyPhase(value: string): string {
  return STUDY_PHASE_LABELS[value] ?? value;
}

const STEP_LABELS: ReadonlyArray<{ id: CreationStep; label: string }> = [
  { id: "protocol", label: "方案信息" },
  { id: "phase", label: "研究期别" },
  { id: "stage", label: "审核节点" },
];

export function ProjectCreationDialog({
  project,
  stages,
  onComplete,
  onClose,
}: ProjectCreationDialogProps) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const [step, setStep] = useState<CreationStep>("protocol");
  const [selectedStudyPhase, setSelectedStudyPhase] = useState(project.studyPhase);
  const [selectedStage, setSelectedStage] = useState<ReviewStage | null>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const completeCreation = () => {
    if (selectedStage === null) return;
    onComplete({
      projectCode: "本次试用项目",
      projectName: project.projectName,
      protocolVersion: project.protocolVersion,
      studyPhase: selectedStudyPhase,
      selectedStage,
    });
  };

  return (
    <div
      className="project-create-dialog-scrim"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="project-create-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <header className="project-create-dialog__head">
          <div>
            <p className="project-create-dialog__eyebrow">从正式方案创建项目</p>
            <h2 id={titleId} className="project-create-dialog__title">
              {step === "protocol" && "确认方案信息"}
              {step === "phase" && "确认研究期别"}
              {step === "stage" && "选择进入的审核节点"}
            </h2>
          </div>
          <button
            ref={closeRef}
            type="button"
            className="icon-button"
            aria-label="关闭新建项目"
            title="关闭新建项目"
            onClick={onClose}
          >
            <CloseIcon size={17} />
          </button>
        </header>

        <ol className="project-create-steps" aria-label="新建项目步骤">
          {STEP_LABELS.map((item, index) => (
            <li
              key={item.id}
              className={`project-create-step${step === item.id ? " project-create-step--current" : ""}`}
              aria-current={step === item.id ? "step" : undefined}
            >
              <span className="project-create-step__number">{index + 1}</span>
              <span>{item.label}</span>
            </li>
          ))}
        </ol>

        <div className="project-create-dialog__body">
          <p className="project-create-dialog__notice">
            本次试用数据仅用于体验操作，不会写入正式项目资料。
          </p>

          {step === "protocol" && (
            <div className="project-create-panel">
              <p className="project-create-panel__lead">
                已载入一份正式方案版本，请核对后继续。
              </p>
              <dl className="project-create-summary">
                <div>
                  <dt>项目名称</dt>
                  <dd>{project.projectName}</dd>
                </div>
                <div>
                  <dt>项目标识</dt>
                  <dd>本次试用项目</dd>
                </div>
                <div>
                  <dt>方案版本</dt>
                  <dd>{project.protocolVersion}</dd>
                </div>
                <div>
                  <dt>方案日期</dt>
                  <dd>{project.protocolOfficialDate}</dd>
                </div>
              </dl>
              <p className="project-create-panel__hint">
                下一步需要你单独确认研究期别；研究期别确认后，还要选择具体审核节点。
              </p>
            </div>
          )}

          {step === "phase" && (
            <div className="project-create-panel">
              <p className="project-create-panel__lead">
                方案版本 {project.protocolVersion} 标注的研究期别为：
              </p>
              <label className="project-phase-option">
                <input
                  type="radio"
                  name="study-phase"
                  value={project.studyPhase}
                  checked={selectedStudyPhase === project.studyPhase}
                  onChange={(event) => setSelectedStudyPhase(event.target.value)}
                />
                <span>
                  <strong>{displayStudyPhase(project.studyPhase)}</strong>
                  <small>研究期别确认后，筛选和基线仍分别作为审核节点。</small>
                </span>
              </label>
              <p className="project-create-panel__hint">
                请确认研究期别，再进入审核节点选择。不能用研究期别代替审核节点。
              </p>
            </div>
          )}

          {step === "stage" && (
            <div className="project-create-panel">
              <p className="project-create-panel__lead">
                请选择本次进入的一个审核节点。阶段之间互相独立，不会合并状态。
              </p>
              <div className="project-stage-options" role="radiogroup" aria-label="选择审核节点">
                {stages.map((stage) => (
                  <label
                    key={stage.workflowStageId}
                    className={`project-stage-option${selectedStage === stage.stage ? " project-stage-option--selected" : ""}`}
                  >
                    <input
                      type="radio"
                      name="review-stage"
                      value={stage.stage}
                      checked={selectedStage === stage.stage}
                      onChange={() => setSelectedStage(stage.stage)}
                    />
                    <span className="project-stage-option__text">
                      <strong>{stageLabel[stage.stage]}</strong>
                      <small>{stage.visitWindow}</small>
                    </span>
                    {stage.reviewRequired && (
                      <span className="project-stage-option__required">需审核</span>
                    )}
                  </label>
                ))}
              </div>
              <p className="project-create-panel__hint">
                例如选择筛选期后，基线/随机前仍会作为另一个独立审核节点保留。
              </p>
            </div>
          )}
        </div>

        <footer className="project-create-dialog__actions">
          {step === "protocol" && (
            <button
              type="button"
              className="button button--primary"
              onClick={() => setStep("phase")}
            >
              <OpenIcon size={15} />
              确认方案并继续
            </button>
          )}
          {step === "phase" && (
            <button
              type="button"
              className="button button--primary"
              disabled={selectedStudyPhase === ""}
              onClick={() => setStep("stage")}
            >
              <CheckIcon size={15} />
              确认研究期别并继续
            </button>
          )}
          {step === "stage" && (
            <button
              type="button"
              className="button button--primary"
              disabled={selectedStage === null}
              onClick={completeCreation}
            >
              <OpenIcon size={15} />
              创建项目并进入{selectedStage === null ? "所选节点" : stageLabel[selectedStage]}
            </button>
          )}
          <button type="button" className="button button--quiet" onClick={onClose}>
            稍后再做
          </button>
        </footer>
      </section>
    </div>
  );
}
