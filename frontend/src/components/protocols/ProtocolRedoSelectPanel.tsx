/**
 * 重新解构项目选择与新版上传：选择目标正式项目后上传新版方案。
 * 若暂停前已有任务，仍可返回首页从恢复入口继续；保存/取消不改变正式版本。
 */

import { useRef, useState } from "react";
import { getProtocolWorkbenchRepository } from "../../api/protocolWorkbenchRepository";
import type {
  OfficialProjectView,
  ProjectOfficialVersionView,
} from "../../api/protocolWorkbenchTypes";
import { RouteLink } from "../../app/router";
import { useLoad } from "../../app/useLoad";
import { LoadingState } from "../shell/Feedback";
import { HistoryIcon, ProtocolFileIcon } from "../shell/icons";

interface ProtocolRedoSelectPanelProps {
  initialProjectId?: string | null;
  busy: boolean;
  error: string | null;
  onUpload: (file: File, projectId: string) => void;
  onStartFeedback: (projectId: string) => void;
}

export function ProtocolRedoSelectPanel({
  initialProjectId = null,
  busy,
  error,
  onUpload,
  onStartFeedback,
}: ProtocolRedoSelectPanelProps) {
  const repo = getProtocolWorkbenchRepository();
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(
    initialProjectId,
  );
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [invalidFile, setInvalidFile] = useState<string | null>(null);

  const projects = useLoad((signal) => repo.listOfficialProjects({ signal }), [repo]);
  const selectedProject =
    selectedProjectId === null
      ? null
      : (projects.state.status === "success"
          ? projects.state.data.find((project) => project.projectId === selectedProjectId)
          : undefined) ?? null;

  const history = useLoad(
    (signal) => {
      if (selectedProjectId === null) return Promise.resolve(null);
      return repo.getProjectOfficialVersion(selectedProjectId, { signal });
    },
    [repo, selectedProjectId],
    { enabled: selectedProjectId !== null },
  );
  const versionView: ProjectOfficialVersionView | null =
    history.state.status === "success" ? history.state.data : null;

  const handleFile = (file: File | undefined) => {
    if (file === undefined || busy) return;
    if (!file.name.toLowerCase().endsWith(".docx")) {
      setInvalidFile("当前仅支持 DOCX 方案文件，请选择正式方案新版文件后重试。");
      return;
    }
    setInvalidFile(null);
    if (selectedProjectId === null) {
      setInvalidFile("请先选择一个目标正式项目，再上传新版方案。");
      return;
    }
    onUpload(file, selectedProjectId);
  };

  const visibleError = invalidFile ?? error;

  if (projects.state.status === "loading") return <LoadingState />;
  if (projects.state.status === "error") {
    return (
      <div className="protocol-redo">
        <header className="page-head">
          <h1 className="page-head__title">重新解构已有项目</h1>
          <p className="page-head__note">
            无法读取正式项目列表，请稍后重试；若持续失败，请记录页面事项并联系系统支持。
          </p>
        </header>
        <div className="feedback feedback--error" role="alert">
          <p className="feedback__title">{projects.state.message}</p>
          <button type="button" className="button" onClick={projects.retry}>
            重试
          </button>
        </div>
        <p className="protocol-upload__back">
          <RouteLink to="/protocols" className="button button--quiet">
            返回方案工作台首页
          </RouteLink>
        </p>
      </div>
    );
  }

  const projectList = projects.state.data;

  if (projectList.length === 0) {
    return (
      <div className="protocol-redo">
        <header className="page-head">
          <h1 className="page-head__title">重新解构已有项目</h1>
          <p className="page-head__note">
            当前还没有已发布的正式项目。请先完成一次「首次解构新方案」并发布，之后即可在此上传新版方案。
          </p>
        </header>
        <div className="feedback feedback--empty">
          <p className="feedback__title">暂无正式项目</p>
          <p className="feedback__hint">
            返回首页选择「首次解构新方案」，建立并发布首个正式项目。
          </p>
        </div>
        <p className="protocol-upload__back">
          <RouteLink to="/protocols" className="button button--primary">
            返回方案工作台首页
          </RouteLink>
        </p>
      </div>
    );
  }

  return (
    <div className="protocol-redo">
      <header className="page-head">
        <h1 className="page-head__title">
          <HistoryIcon size={18} />
          重新解构已有项目
        </h1>
        <p className="page-head__note">
          请先明确选择一个已发布项目，再上传新版方案或按反馈修订。系统会逐项比较当前正式版本与新草稿；保存或取消都不会改变正式版本。
        </p>
      </header>

      <section className="protocol-redo__select" aria-labelledby="protocol-redo-select-title">
        <h2 id="protocol-redo-select-title" className="protocol-section__title">
          选择目标正式项目
        </h2>
        <div className="protocol-redo__projects">
          {projectList.map((project: OfficialProjectView) => (
            <button
              key={project.projectId}
              type="button"
              className={`protocol-redo__project${
                selectedProjectId === project.projectId
                  ? " protocol-redo__project--selected"
                  : ""
              }`}
              aria-pressed={selectedProjectId === project.projectId}
              onClick={() => setSelectedProjectId(project.projectId)}
            >
              <span className="protocol-redo__project-name">{project.projectName}</span>
              <span className="protocol-redo__project-meta">
                {project.protocolCode} · {project.studyPhaseLabel} · 正式版本{" "}
                {project.officialVersion}
              </span>
              <span className="protocol-redo__project-code">
                项目代号 {project.projectCode} · 规则第 {project.ruleSetRevision} 版
              </span>
            </button>
          ))}
        </div>
      </section>

      {selectedProject !== null && (
        <section
          className="protocol-redo__target"
          aria-labelledby="protocol-redo-target-title"
        >
          <h2 id="protocol-redo-target-title" className="protocol-section__title">
            目标项目与正式版本
          </h2>
          {history.state.status === "loading" && (
            <p className="protocol-redo__muted">正在读取该项目正式版本…</p>
          )}
          {history.state.status === "error" && (
            <p className="protocol-redo__target-error" role="alert">
              {history.state.message}
              <button type="button" className="button button--quiet" onClick={history.retry}>
                重试
              </button>
            </p>
          )}
          {versionView !== null && (
            <>
              <dl className="protocol-redo__target-grid">
                <div>
                  <dt>项目名称</dt>
                  <dd>{versionView.project.projectName}</dd>
                </div>
                <div>
                  <dt>方案编号</dt>
                  <dd>{versionView.project.protocolCode}</dd>
                </div>
                <div>
                  <dt>研究期别</dt>
                  <dd>{versionView.project.studyPhaseLabel}</dd>
                </div>
                <div>
                  <dt>当前正式版本</dt>
                  <dd>{versionView.project.officialVersion}</dd>
                </div>
                <div>
                  <dt>已发布版本</dt>
                  <dd>{versionView.publicationCount} 个规则版本</dd>
                </div>
                <div>
                  <dt>规则版本号</dt>
                  <dd>第 {versionView.project.ruleSetRevision} 版</dd>
                </div>
              </dl>
              <p className="protocol-redo__target-note">
                上传的新版方案只允许更新版本、日期与文件内容；方案编号与研究期别必须与目标项目一致，否则将阻止发布并提示原因。
              </p>
              <div className="protocol-redo__feedback-route">
                <div>
                  <strong>方案文件没有变化，只修正当前解构结果</strong>
                  <p>
                    系统会复制当前正式草稿并保留原有方案定位，随后可逐条填写反馈或手工修订；正式版本不会被直接改写。
                  </p>
                </div>
                <button
                  type="button"
                  className="button"
                  disabled={busy}
                  onClick={() => onStartFeedback(selectedProject.projectId)}
                >
                  {busy ? "正在准备…" : "不上传文件，按反馈修订"}
                </button>
              </div>
            </>
          )}
        </section>
      )}

      <section
        className="protocol-redo__upload"
        aria-labelledby="protocol-redo-upload-title"
      >
        <h2 id="protocol-redo-upload-title" className="protocol-section__title">
          方案文件有变化时，上传新版方案
        </h2>
        <div
          className={`protocol-upload__dropzone${
            dragOver ? " protocol-upload__dropzone--active" : ""
          }`}
          onDragOver={(event) => {
            event.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragOver(false);
            handleFile(event.dataTransfer.files[0]);
          }}
        >
          <ProtocolFileIcon size={32} />
          <p className="protocol-upload__hint">
            将新版 DOCX 方案拖放到此处，或点击选择文件
          </p>
          <button
            type="button"
            className="button button--primary"
            disabled={busy || selectedProjectId === null}
            onClick={() => inputRef.current?.click()}
          >
            {busy ? "正在登记新版方案…" : "选择新版方案文件"}
          </button>
          <input
            ref={inputRef}
            type="file"
            accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            className="protocol-upload__input"
            onChange={(event) => {
              handleFile(event.target.files?.[0]);
              event.currentTarget.value = "";
            }}
          />
        </div>
        {visibleError !== null && (
          <div className="feedback feedback--error" role="alert">
            <p className="feedback__title">{visibleError}</p>
          </div>
        )}
      </section>

      <p className="protocol-upload__back">
        <RouteLink to="/protocols" className="button button--quiet">
          返回方案工作台首页
        </RouteLink>
      </p>
    </div>
  );
}
