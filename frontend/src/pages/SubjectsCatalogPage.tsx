/** 正式受试者资料目录：只展示 V2 已真实保存的项目、受试者、审核节点与证据入口。
 *
 * 新增/删除受试者入口：新增弹窗校验受试者代号与年龄，保存失败保留用户输入并给出
 * 中文恢复动作；删除必须先确认。系统会一并删除自动建立但尚未承载资料的空审核
 * 节点；已有资料或审核内容的受试者由后端拒绝，页面展示 409 恢复动作。
 */
import { useEffect, useState } from "react";
import { CatalogApiError, getCatalogRepository } from "../api";
import { RouteLink, updateParams, useHashRoute } from "../app/router";
import { useLoad } from "../app/useLoad";
import { EmptyState, ErrorState, LoadingState } from "../components/shell/Feedback";
import type { CatalogEpisodeView, CatalogSubjectView } from "../api/catalog";

/** 失败文案：业务错误信封给中文说明 + 恢复动作；其余给统一恢复文案。 */
function actionErrorText(error: unknown): string {
  if (error instanceof CatalogApiError) {
    return error.recoveryAction.length > 0
      ? `${error.message} ${error.recoveryAction}`
      : error.message;
  }
  return "暂时无法完成操作，请稍后重试。";
}

function centerLabel(code: string | null, name: string | null): string {
  if (code !== null && name !== null) return `${code}｜${name}`;
  return code ?? name ?? "中心信息尚未填写";
}

function evidenceState(episode: CatalogEpisodeView): string {
  if (episode.activeEvidenceProcessingRevisionId !== null) return `${episode.stageLabel}资料当前有效`;
  if (episode.activeEvidenceSnapshotId !== null) return "资料已确认，正在等待整理";
  if (episode.latestEvidenceSnapshotId !== null) return "资料已上传，尚待整理和确认";
  return "尚未建立资料版本";
}

interface SubjectFormDraft {
  subjectCode: string;
  centerCode: string;
  centerName: string;
  sex: string;
  ageYears: string;
}

const EMPTY_DRAFT: SubjectFormDraft = {
  subjectCode: "",
  centerCode: "",
  centerName: "",
  sex: "",
  ageYears: "",
};

/** Esc 关闭确认弹窗；忙碌时不响应，避免误关正在提交的操作。 */
function useEscapeToClose(open: boolean, busy: boolean, onClose: () => void): void {
  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) {
        event.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, busy, onClose]);
}

export function SubjectsCatalogPage() {
  const { params } = useHashRoute();
  const projects = useLoad((signal) => getCatalogRepository().listProjects(signal), []);
  const projectList = projects.state.status === "success" ? projects.state.data : [];
  const projectParam = params.get("project");
  const selectedProject =
    projectList.find((project) => project.projectId === projectParam) ??
    (projectList.length === 1 ? projectList[0] : null);

  const subjects = useLoad(
    (signal) => getCatalogRepository().listSubjects(selectedProject?.projectId ?? "", signal),
    [selectedProject?.projectId],
    { enabled: selectedProject !== null },
  );
  const subjectList = subjects.state.status === "success" ? subjects.state.data : [];
  const subjectParam = params.get("subject");
  const selectedSubject =
    subjectList.find((subject) => subject.subjectId === subjectParam) ??
    subjectList[0] ??
    null;

  const episodes = useLoad(
    (signal) => getCatalogRepository().listEpisodes(selectedSubject?.subjectId ?? "", signal),
    [selectedSubject?.subjectId],
    { enabled: selectedSubject !== null },
  );
  const episodeList = episodes.state.status === "success" ? episodes.state.data : [];

  // 新增受试者弹窗状态。
  const [createOpen, setCreateOpen] = useState(false);
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createFieldError, setCreateFieldError] = useState<string | null>(null);
  const [createDraft, setCreateDraft] = useState<SubjectFormDraft>(EMPTY_DRAFT);

  // 删除受试者确认弹窗状态。
  const [deleteTarget, setDeleteTarget] = useState<CatalogSubjectView | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEscapeToClose(createOpen, createBusy, () => setCreateOpen(false));
  useEscapeToClose(deleteTarget !== null, deleteBusy, () => setDeleteTarget(null));

  function openCreate(): void {
    setCreateDraft(EMPTY_DRAFT);
    setCreateFieldError(null);
    setCreateError(null);
    setCreateOpen(true);
  }

  async function submitCreate(): Promise<void> {
    if (selectedProject === null) return;
    const code = createDraft.subjectCode.trim();
    if (code.length === 0) {
      setCreateFieldError("请填写受试者代号。");
      return;
    }
    let ageYears: number | null = null;
    if (createDraft.ageYears.trim().length > 0) {
      const parsed = Number(createDraft.ageYears);
      if (!Number.isFinite(parsed) || parsed < 0) {
        setCreateFieldError("年龄应填写大于等于 0 的数字。");
        return;
      }
      ageYears = parsed;
    }
    setCreateFieldError(null);
    setCreateError(null);
    setCreateBusy(true);
    try {
      const created = await getCatalogRepository().createSubject(selectedProject.projectId, {
        subjectCode: code,
        centerCode: createDraft.centerCode.trim() || null,
        centerName: createDraft.centerName.trim() || null,
        sex: createDraft.sex || null,
        ageYears,
      });
      setCreateOpen(false);
      updateParams({ subject: created.subjectId });
      subjects.retry();
    } catch (error) {
      setCreateError(actionErrorText(error));
    } finally {
      setCreateBusy(false);
    }
  }

  async function confirmDelete(): Promise<void> {
    if (deleteTarget === null) return;
    setDeleteError(null);
    setDeleteBusy(true);
    try {
      await getCatalogRepository().deleteSubject(
        deleteTarget.projectId,
        deleteTarget.subjectId,
      );
      if (selectedSubject?.subjectId === deleteTarget.subjectId) {
        updateParams({ subject: null });
      }
      setDeleteTarget(null);
      subjects.retry();
    } catch (error) {
      // 删除失败（如 409 已纳入审核安排）：保留确认弹窗并展示恢复动作，同时刷新列表。
      setDeleteError(actionErrorText(error));
      subjects.retry();
    } finally {
      setDeleteBusy(false);
    }
  }

  if (projects.state.status === "loading") return <LoadingState />;
  if (projects.state.status === "error") {
    return <ErrorState message={projects.state.message} onRetry={projects.retry} />;
  }

  return (
    <div className="subjects catalog-page">
      <header className="page-head">
        <h1 className="page-head__title">受试者与资料</h1>
        <p className="page-head__note">
          按项目和受试者查看各审核节点的资料版本。不同审核节点相互独立，后续资料不会覆盖此前节点的记录。
        </p>
      </header>

      {projectList.length === 0 ? (
        <EmptyState message="当前还没有已保存的项目。" hint="请先在方案工作台上传并确认研究方案。" />
      ) : (
        <section className="catalog-selection" aria-labelledby="catalog-project-title">
          <div className="catalog-selection__head">
            <div>
              <h2 id="catalog-project-title">选择项目</h2>
              <p>方案中包含多个研究期别时，每个已选择期别都是独立项目。</p>
            </div>
            <div className="catalog-selection__actions">
              <select
                aria-label="选择项目"
                value={selectedProject?.projectId ?? ""}
                onChange={(event) => updateParams({ project: event.target.value, subject: null })}
              >
                <option value="" disabled>请选择项目</option>
                {projectList.map((project) => (
                  <option key={project.projectId} value={project.projectId}>
                    {project.projectCode} · {project.projectName} · {project.studyPhaseLabel} · 方案 {project.officialVersion}
                  </option>
                ))}
              </select>
              {selectedProject !== null && (
                <button type="button" className="button button--primary" onClick={openCreate}>
                  新增受试者
                </button>
              )}
            </div>
          </div>
        </section>
      )}

      {selectedProject !== null && subjects.state.status === "loading" && <LoadingState />}
      {subjects.state.status === "error" && (
        <ErrorState message={subjects.state.message} onRetry={subjects.retry} />
      )}
      {selectedProject !== null && subjects.state.status === "success" && subjectList.length === 0 && (
        <EmptyState message="这个项目还没有受试者。" hint="点击上方“新增受试者”登记后，可在这里按审核节点上传资料。" />
      )}

      {subjectList.length > 0 && (
        <div className="catalog-layout">
          <aside className="catalog-subjects" aria-label="受试者列表">
            <h2>受试者</h2>
            <ul>
              {subjectList.map((subject) => (
                <li key={subject.subjectId} className="catalog-subject-item">
                  <button
                    type="button"
                    className={`catalog-subject-item__select${subject.subjectId === selectedSubject?.subjectId ? " is-active" : ""}`}
                    onClick={() => updateParams({ subject: subject.subjectId })}
                  >
                    <strong>{subject.subjectCode}</strong>
                    <span>{centerLabel(subject.centerCode, subject.centerName)}</span>
                  </button>
                  <button
                    type="button"
                    className="catalog-subject-item__delete"
                    aria-label={`删除受试者 ${subject.subjectCode}`}
                    onClick={() => {
                      setDeleteError(null);
                      setDeleteTarget(subject);
                    }}
                  >
                    删除
                  </button>
                </li>
              ))}
            </ul>
          </aside>

          <section className="catalog-episodes" aria-labelledby="catalog-episodes-title">
            <header>
              <div>
                <h2 id="catalog-episodes-title">{selectedSubject?.subjectCode ?? "审核节点"}</h2>
                <p>{centerLabel(selectedSubject?.centerCode ?? null, selectedSubject?.centerName ?? null)}</p>
              </div>
              {selectedProject !== null && (
                <div className="catalog-project-meta">
                  <strong>{selectedProject.projectName}</strong>
                  <span>{selectedProject.studyPhaseLabel} · 方案 {selectedProject.officialVersion}</span>
                </div>
              )}
            </header>
            {selectedSubject !== null && episodes.state.status === "loading" && <LoadingState />}
            {episodes.state.status === "error" && (
              <ErrorState message={episodes.state.message} onRetry={episodes.retry} />
            )}
            {episodes.state.status === "success" && episodeList.length === 0 && (
              <EmptyState message="尚未建立审核节点。" hint="请先确认方案解构中的审核节点。" />
            )}
            <div className="catalog-episode-list">
              {episodeList.map((episode) => (
                <article key={episode.reviewEpisodeId} className="catalog-episode">
                  <div>
                    <h3>{episode.workflowStageLabel ?? episode.stageLabel}</h3>
                    {episode.visitWindow !== null && (
                      <p className="catalog-episode__visit">访视窗口：{episode.visitWindow}</p>
                    )}
                    <p>{evidenceState(episode)}</p>
                  </div>
                  <RouteLink
                    to={`/subjects/${episode.subjectId}/evidence?episode=${encodeURIComponent(episode.reviewEpisodeId)}`}
                    className="button button--primary"
                    ariaLabel={`打开${episode.stageLabel}证据工作台`}
                  >
                    {episode.activeEvidenceProcessingRevisionId === null
                      ? "上传资料"
                      : `查看${episode.stageLabel}资料`}
                  </RouteLink>
                </article>
              ))}
            </div>
          </section>
        </div>
      )}

      {createOpen && (
        <div className="confirmation-scrim" onClick={createBusy ? undefined : () => setCreateOpen(false)}>
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="subject-create-title"
            className="confirmation-dialog"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 id="subject-create-title">新增受试者</h2>
            <p className="confirmation-dialog__note">
              {selectedProject?.projectName} · {selectedProject?.studyPhaseLabel} · 方案{" "}
              {selectedProject?.officialVersion}
            </p>
            <div className="subject-form">
              <label className="subject-form__field">
                <span>
                  受试者代号 <em className="subject-form__required">必填</em>
                </span>
                <input
                  value={createDraft.subjectCode}
                  maxLength={128}
                  placeholder="如 S-2026-001"
                  disabled={createBusy}
                  onChange={(event) =>
                    setCreateDraft((current) => ({ ...current, subjectCode: event.target.value }))
                  }
                />
              </label>
              <div className="subject-form__row">
                <label className="subject-form__field">
                  <span>中心编号</span>
                  <input
                    value={createDraft.centerCode}
                    maxLength={128}
                    disabled={createBusy}
                    onChange={(event) =>
                      setCreateDraft((current) => ({ ...current, centerCode: event.target.value }))
                    }
                  />
                </label>
                <label className="subject-form__field">
                  <span>中心名称</span>
                  <input
                    value={createDraft.centerName}
                    maxLength={256}
                    disabled={createBusy}
                    onChange={(event) =>
                      setCreateDraft((current) => ({ ...current, centerName: event.target.value }))
                    }
                  />
                </label>
              </div>
              <div className="subject-form__row">
                <label className="subject-form__field">
                  <span>性别</span>
                  <select
                    value={createDraft.sex}
                    disabled={createBusy}
                    onChange={(event) =>
                      setCreateDraft((current) => ({ ...current, sex: event.target.value }))
                    }
                  >
                    <option value="">不填写</option>
                    <option value="男">男</option>
                    <option value="女">女</option>
                  </select>
                </label>
                <label className="subject-form__field">
                  <span>年龄（岁）</span>
                  <input
                    type="number"
                    min={0}
                    step="any"
                    value={createDraft.ageYears}
                    disabled={createBusy}
                    onChange={(event) =>
                      setCreateDraft((current) => ({ ...current, ageYears: event.target.value }))
                    }
                  />
                </label>
              </div>
            </div>
            {(createFieldError !== null || createError !== null) && (
              <p className="subject-form__error" role="alert">
                {createFieldError ?? createError}
              </p>
            )}
            <p className="confirmation-dialog__note">
              新增后即可按审核节点上传资料；受试者代号在同一项目内不能重复，保存失败不会产生任何记录。
            </p>
            <div className="confirmation-dialog__actions">
              <button type="button" className="button" disabled={createBusy} onClick={() => setCreateOpen(false)}>
                先不要
              </button>
              <button
                type="button"
                className="button button--primary"
                disabled={createBusy}
                onClick={submitCreate}
              >
                {createBusy ? "正在保存…" : "确认新增"}
              </button>
            </div>
          </section>
        </div>
      )}

      {deleteTarget !== null && (
        <div className="confirmation-scrim" onClick={deleteBusy ? undefined : () => setDeleteTarget(null)}>
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="subject-delete-title"
            className="confirmation-dialog"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 id="subject-delete-title">确认删除受试者</h2>
            <dl className="confirmation-dialog__details">
              <div>
                <dt>受试者代号</dt>
                <dd>{deleteTarget.subjectCode}</dd>
              </div>
              <div>
                <dt>中心</dt>
                <dd>{centerLabel(deleteTarget.centerCode, deleteTarget.centerName)}</dd>
              </div>
            </dl>
            <p className="confirmation-dialog__note confirmation-dialog__note--warning">
              删除后该受试者将立即从本项目消失，且无法恢复。系统会同时删除尚未承载资料的空审核节点；已有资料或审核记录时将阻止删除，请核对后再操作。
            </p>
            {deleteError !== null && (
              <p className="subject-form__error" role="alert">
                {deleteError}
              </p>
            )}
            <div className="confirmation-dialog__actions">
              <button type="button" className="button" disabled={deleteBusy} onClick={() => setDeleteTarget(null)}>
                先不要
              </button>
              <button
                type="button"
                className="button button--primary"
                disabled={deleteBusy}
                onClick={confirmDelete}
              >
                {deleteBusy ? "正在删除…" : "确认删除"}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

export default SubjectsCatalogPage;
