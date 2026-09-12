/**
 * 受试者与 Patient Profile（Phase 5.6）：从正式项目目录选择项目/受试者/审核节点，
 * 经 Slice 5.5 PatientProfileRepository 严格解码读取真实档案，再经领域适配渲染。
 * - 首屏默认只展示后端 highlights（唯一首屏依据），"全部历时信息"展开 13 条泳道；
 * - 显式区分 生成中/失败/陈旧/已生成空态；
 * - 有定位的条目可打开原文证据面板（Phase 4 原件查看器联动，只画真实 bbox 单框）；
 * - 不展示任何 Phase 6/7 入排结论、行动数、负责方或通过/不通过语言；
 * - URL 契约：/subjects?project=&subject=&episode=&all=1。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { getCatalogRepository } from "../api";
import {
  getPatientProfileRepository,
  PatientProfileApiError,
} from "../api/patient-profile";
import type {
  FactCorrectionHistoryView,
  FactCorrectionTargetKind,
} from "../api/patient-profile";
import { updateParams, RouteLink, useHashRoute } from "../app/router";
import { useLoad } from "../app/useLoad";
import { EmptyState, ErrorState, LoadingState } from "../components/shell/Feedback";
import { ProfileStatusBanner } from "../components/profile/ProfileStatusBanner";
import { ProfileNormalizationStatus } from "../components/profile/ProfileNormalizationStatus";
import { ProfileHighlights } from "../components/profile/ProfileHighlights";
import {
  ProfileTodoSummaryCard,
  firstProfileTodoItemId,
  type ProfileTodoGroup,
} from "../components/profile/ProfileTodoSummaryCard";
import {
  JudgmentSearchCard,
  type JudgmentSearchCandidateSelection,
} from "../components/profile/JudgmentSearchCard";
import { ProfileLaneList } from "../components/profile/ProfileLaneList";
import { ProfileEvidencePanel } from "../components/profile/ProfileEvidencePanel";
import {
  ProfileFactCorrectionDialog,
  type ProfileFactCorrectionCompleted,
} from "../components/profile/ProfileFactCorrectionDialog";
import {
  ProfileCorrectionHistory,
  type ProfileCorrectionHistoryState,
} from "../components/profile/ProfileCorrectionHistory";
import {
  adaptPatientProfile,
  formatProfileDateTime,
  type PatientProfileModel,
} from "../features/patient-profile/model";
import { useFactNormalizationJob } from "../features/fact-normalization/useFactNormalizationJob";
import {
  factNormalizationPhaseTitle,
  factNormalizationRecoveryHint,
} from "../api/fact-normalization";
import { UI_PHRASES } from "../domain/labels";
import type {
  CatalogEpisodeView,
  CatalogProjectView,
  CatalogSubjectView,
} from "../api/catalog";
import type { ProfileItemView } from "../api/patient-profile";

type ProfileLoadState =
  | { status: "loading" }
  | { status: "success"; data: PatientProfileModel }
  | { status: "error"; message: string; retryable: boolean; missing: boolean };

/** 面向用户的档案错误说明：业务错误信封给中文说明 + 恢复动作；其余给统一恢复文案。 */
function profileErrorMessage(error: unknown): string {
  if (error instanceof PatientProfileApiError) {
    return error.recoveryAction.length > 0
      ? `${error.message} ${error.recoveryAction}`
      : error.message;
  }
  return UI_PHRASES.temporarilyUnavailable;
}

function isProfileMissingError(error: unknown): boolean {
  return error instanceof PatientProfileApiError && error.statusCode === 404;
}

/** 页面局部档案加载（严格解码已由仓储完成；此处只做错误文案与重试）。 */
function usePatientProfile(
  subjectId: string | null,
  reviewEpisodeId: string | null,
): { state: ProfileLoadState; retry: () => void } {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<ProfileLoadState>({ status: "loading" });

  useEffect(() => {
    if (subjectId === null || reviewEpisodeId === null) {
      setState({ status: "loading" });
      return;
    }
    const controller = new AbortController();
    let cancelled = false;
    setState({ status: "loading" });
    getPatientProfileRepository()
      .getLatestPatientProfile(subjectId, reviewEpisodeId, {
        signal: controller.signal,
      })
      .then(
        (revision) => {
          if (cancelled) return;
          setState({ status: "success", data: adaptPatientProfile(revision) });
        },
        (error: unknown) => {
          if (cancelled) return;
          if (error instanceof DOMException && error.name === "AbortError") return;
          setState({
            status: "error",
            message: profileErrorMessage(error),
            retryable: true,
            missing: isProfileMissingError(error),
          });
        },
      );
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [subjectId, reviewEpisodeId, attempt]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  return { state, retry };
}

function useFactCorrectionHistory(
  subjectId: string | null,
  reviewEpisodeId: string | null,
): { state: ProfileCorrectionHistoryState; retry: () => void } {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<ProfileCorrectionHistoryState>({ status: "loading" });

  useEffect(() => {
    if (subjectId === null || reviewEpisodeId === null) {
      setState({ status: "loading" });
      return;
    }
    const controller = new AbortController();
    let cancelled = false;
    setState({ status: "loading" });
    getPatientProfileRepository()
      .listFactCorrectionHistory(subjectId, reviewEpisodeId, { signal: controller.signal })
      .then(
        (data: FactCorrectionHistoryView) => {
          if (!cancelled) setState({ status: "success", data });
        },
        (error: unknown) => {
          if (cancelled) return;
          if (error instanceof DOMException && error.name === "AbortError") return;
          setState({ status: "error", message: profileErrorMessage(error) });
        },
      );
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [subjectId, reviewEpisodeId, attempt]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  return { state, retry };
}

function episodeLabel(episode: CatalogEpisodeView): string {
  return episode.workflowStageLabel ?? episode.stageLabel;
}

function centerLabel(subject: CatalogSubjectView): string {
  return [subject.centerCode, subject.centerName]
    .filter((part): part is string => part !== null)
    .join("｜");
}

function correctionTargetKind(item: ProfileItemView): FactCorrectionTargetKind | null {
  if (item.kind === "fact" || item.kind === "event" || item.kind === "exposure") {
    return item.kind;
  }
  return null;
}

export function SubjectsPage() {
  const { path, params } = useHashRoute();
  const projectParam = params.get("project");
  const subjectParam = params.get("subject");
  const episodeParam = params.get("episode");
  const showAll = params.get("all") === "1";
  const [evidenceItemId, setEvidenceItemId] = useState<string | null>(null);
  const [unlinkedCandidatePage, setUnlinkedCandidatePage] = useState<number | null>(null);
  const [evidenceModelSnapshot, setEvidenceModelSnapshot] = useState<PatientProfileModel | null>(null);
  const [evidencePageArtifactId, setEvidencePageArtifactId] = useState<string | null>(null);
  const evidenceTriggerRef = useRef<HTMLButtonElement | null>(null);
  const [correctionItemId, setCorrectionItemId] = useState<string | null>(null);
  const correctionTriggerRef = useRef<HTMLButtonElement | null>(null);
  const [correctionModelSnapshot, setCorrectionModelSnapshot] = useState<PatientProfileModel | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);

  const projects = useLoad(
    (signal) => getCatalogRepository().listProjects(signal),
    [],
  );
  const projectList = projects.state.status === "success" ? projects.state.data : [];
  const selectedProject =
    projectParam !== null ? projectList.find((project) => project.projectId === projectParam) ?? null : projectList[0] ?? null;

  const subjects = useLoad(
    (signal) => getCatalogRepository().listSubjects(selectedProject?.projectId ?? "", signal),
    [selectedProject?.projectId],
    { enabled: selectedProject !== null },
  );
  const subjectList = subjects.state.status === "success" ? subjects.state.data.filter((subject) => subject.projectId === selectedProject?.projectId) : [];
  const selectedSubject =
    subjectParam !== null ? subjectList.find((subject) => subject.subjectId === subjectParam) ?? null : subjectList[0] ?? null;

  const episodes = useLoad(
    (signal) => getCatalogRepository().listEpisodes(selectedSubject?.subjectId ?? "", signal),
    [selectedSubject?.subjectId],
    { enabled: selectedSubject !== null },
  );
  const episodeList = episodes.state.status === "success" ? episodes.state.data.filter((episode) => episode.subjectId === selectedSubject?.subjectId) : [];
  const selectedEpisode =
    episodeParam !== null ? episodeList.find((episode) => episode.reviewEpisodeId === episodeParam) ?? null : episodeList[0] ?? null;

  const profile = usePatientProfile(
    selectedSubject?.subjectId ?? null,
    selectedEpisode?.reviewEpisodeId ?? null,
  );
  const correctionHistory = useFactCorrectionHistory(
    selectedSubject?.subjectId ?? null,
    selectedEpisode?.reviewEpisodeId ?? null,
  );

  const profileStale =
    profile.state.status === "success" ? profile.state.data.isStale : false;
  const factNormalization = useFactNormalizationJob({
    subjectId: selectedSubject?.subjectId ?? null,
    reviewEpisodeId: selectedEpisode?.reviewEpisodeId ?? null,
    profileStale,
    onSucceeded: () => {
      profile.retry();
    },
  });
  const autoStartKeyRef = useRef<string | null>(null);
  const startNormalization = factNormalization.start;
  const normalizationStatus = factNormalization.state.status;

  // 资料已启用但档案尚未生成、且本机无进行中任务时，自动发起整理（幂等复用服务端任务）。
  useEffect(() => {
    if (selectedSubject === null || selectedEpisode === null) return;
    if (selectedEpisode.activeEvidenceSnapshotId === null) return;
    if (normalizationStatus === "active") return;
    const needsOrganize =
      (profile.state.status === "error" && profile.state.missing) ||
      (profile.state.status === "success" && profile.state.data.isGenerating);
    if (!needsOrganize) return;
    const key = selectedEpisode.reviewEpisodeId;
    if (autoStartKeyRef.current === key) return;
    autoStartKeyRef.current = key;
    void startNormalization(`profile-organize:subjects:${key}`);
  }, [
    normalizationStatus,
    profile.state,
    selectedEpisode,
    selectedSubject,
    startNormalization,
  ]);

  // 切换受试者/审核节点后关闭已打开的证据面板和修订工作区。
  useEffect(() => {
    setEvidenceItemId(null);
    setEvidencePageArtifactId(null);
    setEvidenceModelSnapshot(null);
    evidenceTriggerRef.current = null;
    setCorrectionItemId(null);
    setCorrectionModelSnapshot(null);
    correctionTriggerRef.current = null;
    setHistoryOpen(false);
    autoStartKeyRef.current = null;
  }, [selectedSubject?.subjectId, selectedEpisode?.reviewEpisodeId]);

  const openEvidence = useCallback((
    item: ProfileItemView,
    model: PatientProfileModel,
    pageArtifactId: string | null = null,
  ) => {
    evidenceTriggerRef.current =
      document.activeElement instanceof HTMLButtonElement
        ? document.activeElement
        : null;
    setEvidencePageArtifactId(pageArtifactId);
    setEvidenceModelSnapshot(model);
    setEvidenceItemId(item.itemId);
  }, []);

  const openLatestEvidence = useCallback(
    (item: ProfileItemView) => {
      if (profile.state.status !== "success") return;
      openEvidence(item, profile.state.data);
    },
    [openEvidence, profile.state],
  );
  const openJudgmentSearchCandidate = useCallback(
    (selection: JudgmentSearchCandidateSelection) => {
      if (profile.state.status !== "success") return;
      const model = profile.state.data;
      const item = model.items.find((candidate) =>
        candidate.locatorIds.some(
          (locatorId) =>
            model.locatorById.get(locatorId)?.pageArtifactId ===
            selection.page_artifact_id,
        ),
      );
      if (item !== undefined) {
        openEvidence(item, model, selection.page_artifact_id);
        return;
      }
      // 候选所在页尚未关联档案条目：明确提示，不再静默无响应（第三方测试 P1-1）。
      setUnlinkedCandidatePage(selection.page_number);
    },
    [openEvidence, profile.state],
  );

  const closeEvidence = useCallback(() => {
    const trigger = evidenceTriggerRef.current;
    setEvidencePageArtifactId(null);
    setEvidenceItemId(null);
    setEvidenceModelSnapshot(null);
    window.requestAnimationFrame(() => {
      trigger?.focus();
      evidenceTriggerRef.current = null;
    });
  }, []);

  const openCorrection = useCallback((item: ProfileItemView) => {
    if (profile.state.status !== "success" || correctionTargetKind(item) === null) return;
    setCorrectionModelSnapshot(profile.state.data);
    correctionTriggerRef.current =
      document.activeElement instanceof HTMLButtonElement
        ? document.activeElement
        : null;
    evidenceTriggerRef.current = null;
    setEvidenceItemId(null);
    setEvidencePageArtifactId(null);
    setEvidenceModelSnapshot(null);
    setCorrectionItemId(item.itemId);
  }, [profile.state]);

  const closeCorrection = useCallback(() => {
    const trigger = correctionTriggerRef.current;
    setCorrectionItemId(null);
    setCorrectionModelSnapshot(null);
    setEvidenceItemId(null);
    setEvidencePageArtifactId(null);
    setEvidenceModelSnapshot(null);
    evidenceTriggerRef.current = null;
    window.requestAnimationFrame(() => {
      trigger?.focus();
      correctionTriggerRef.current = null;
    });
  }, []);

  /** 查看原文时保留修订工作区挂载，避免草稿/预览/确认状态被卸载清空。 */
  const openCorrectionEvidence = useCallback((item: ProfileItemView) => {
    const model = correctionModelSnapshot;
    if (model === null) return;
    evidenceTriggerRef.current =
      document.activeElement instanceof HTMLButtonElement
        ? document.activeElement
        : null;
    setEvidenceModelSnapshot(model);
    setEvidencePageArtifactId(null);
    setEvidenceItemId(item.itemId);
  }, [correctionModelSnapshot]);

  const handleCorrectionCompleted = useCallback(
    (_completed: ProfileFactCorrectionCompleted) => {
      profile.retry();
      correctionHistory.retry();
    },
    [correctionHistory.retry, profile.retry],
  );

  const evidenceModel = evidenceModelSnapshot;
  const evidenceItem =
    evidenceModel?.itemById.get(evidenceItemId ?? "") ?? null;
  const correctionModel = correctionModelSnapshot;
  const correctionItem =
    correctionModel?.itemById.get(correctionItemId ?? "") ?? null;
  const correctionKind = correctionItem === null ? null : correctionTargetKind(correctionItem);

  const setProject = (projectId: string) =>
    updateParams({ project: projectId, subject: null, episode: null, all: null });
  const setSubject = (subjectId: string) =>
    updateParams({ subject: subjectId, episode: null, all: null });
  const setEpisode = (reviewEpisodeId: string) =>
    updateParams({ episode: reviewEpisodeId, all: null });

  if (projects.state.status === "loading") return <LoadingState />;
  if (projects.state.status === "error") {
    return <ErrorState message={projects.state.message} onRetry={projects.retry} />;
  }
  if (projectList.length === 0) {
    return (
      <EmptyState message="当前还没有已保存的项目。" hint="请先在方案工作台上传并确认研究方案。" />
    );
  }
  if (selectedProject === null) return <ErrorState message="链接中的项目不存在，请重新选择。" onRetry={() => updateParams({ project: null, subject: null, episode: null })} />;

  if (subjects.state.status === "loading") return <LoadingState />;
  if (subjects.state.status === "error") {
    return <ErrorState message={subjects.state.message} onRetry={subjects.retry} />;
  }
  if (subjectList.length === 0) {
    return <EmptyState message="这个项目还没有受试者。" hint="请先在正式资料目录中登记受试者。" />;
  }
  if (selectedSubject === null) return <ErrorState message="链接中的受试者不属于当前项目，请重新选择。" onRetry={() => updateParams({ subject: null, episode: null })} />;

  if (episodes.state.status === "loading") return <LoadingState />;
  if (episodes.state.status === "error") {
    return <ErrorState message={episodes.state.message} onRetry={episodes.retry} />;
  }
  if (episodeList.length === 0) {
    return <EmptyState message="该受试者还没有审核节点。" hint="请先在方案解构中确认审核节点。" />;
  }
  if (selectedEpisode === null || selectedSubject === null) {
    return (
      <ErrorState
        message="当前受试者或审核节点未能正确载入，请重试。"
        onRetry={() => updateParams({ subject: null, episode: null })}
      />
    );
  }

  return (
    <div className="subjects">
      <header className="page-head">
        <h1 className="page-head__title">{path === "/profiles" ? "个例档案" : "受试者与资料"}</h1>
        <p className="page-head__note">
          按项目和受试者选择审核节点，查看已生成的病历档案。首屏显示系统整理的重点条目，完整历时信息按需展开。
        </p>
      </header>

      <section className="catalog-selection" aria-labelledby="profile-project-title">
        <div className="catalog-selection__head">
          <div>
            <h2 id="profile-project-title">选择项目</h2>
            <p>方案中包含多个研究期别时，每个已选择期别都是独立项目。</p>
          </div>
          <select
            aria-label="选择项目"
            value={selectedProject?.projectId ?? ""}
            onChange={(event) => setProject(event.target.value)}
          >
            {projectList.map((project) => (
              <option key={project.projectId} value={project.projectId}>
                {project.projectName} · {project.studyPhaseLabel} · 方案 {project.officialVersion}
              </option>
            ))}
          </select>
        </div>
      </section>

      <div className={`subjects-layout${evidenceItem !== null ? " subjects-layout--with-evidence" : ""}`}>
        <aside className="subjects-list" aria-label="受试者列表">
          <h2 className="subjects-list__title">受试者</h2>
          <ul>
            {subjectList.map((subject: CatalogSubjectView) => {
              const isActive = subject.subjectId === selectedSubject?.subjectId;
              return (
                <li key={subject.subjectId}>
                  <button
                    type="button"
                    className={`subjects-list__item${isActive ? " subjects-list__item--active" : ""}`}
                    aria-pressed={isActive}
                    onClick={() => setSubject(subject.subjectId)}
                  >
                    <span className="subjects-list__code">{subject.subjectCode}</span>
                    <span className="subjects-list__center">{centerLabel(subject)}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </aside>

        <section className="profile" aria-label="个例全景">
          <div className="profile-nodes" role="group" aria-label="审核节点">
            {episodeList.map((episode) => {
              const isActive = episode.reviewEpisodeId === selectedEpisode?.reviewEpisodeId;
              return (
                <button
                  key={episode.reviewEpisodeId}
                  type="button"
                  className={`chip${isActive ? " is-active" : ""}`}
                  aria-pressed={isActive}
                  onClick={() => setEpisode(episode.reviewEpisodeId)}
                >
                  {episodeLabel(episode)}
                </button>
              );
            })}
          </div>

          {profile.state.status === "loading" && <LoadingState />}
          {factNormalization.completedReview && <RouteLink className="button" to="/tasks" params={{
            job: factNormalization.completedReview.jobId, subject: factNormalization.completedReview.subjectId,
            episode: factNormalization.completedReview.reviewEpisodeId,
          }}>查看最近一次资料识别</RouteLink>}
          <ProfileNormalizationStatus
            state={
              factNormalization.state.status !== "idle"
                ? factNormalization.state
                : profileStale
                  ? {
                      status: "active",
                      jobId: "",
                      phase: "stale",
                      title: factNormalizationPhaseTitle("stale"),
                      recoveryHint: factNormalizationRecoveryHint("stale"),
                      job: null,
                      canRetry: true,
                    }
                  : factNormalization.state
            }
            onRetry={() => void factNormalization.retry()}
          />
          {profile.state.status === "error" &&
            !(
              profile.state.missing &&
              (factNormalization.state.status === "active" ||
                factNormalization.state.status === "error")
            ) && (
            <ErrorState message={profile.state.message} onRetry={profile.retry} />
          )}
          {profile.state.status === "error" &&
            profile.state.missing &&
            factNormalization.state.status === "idle" &&
            selectedEpisode.activeEvidenceSnapshotId === null && (
              <EmptyState
                message="该审核节点尚未整理个例档案。"
                hint="请先在证据工作台完成资料核对并启用资料版本。"
              />
            )}
          {profile.state.status === "success" && (
            <ProfileBody
              model={profile.state.data}
              project={selectedProject}
              subjectCode={selectedSubject?.subjectCode ?? "受试者"}
              center={selectedSubject !== null ? centerLabel(selectedSubject) : ""}
              episode={selectedEpisode}
              subjectId={selectedSubject.subjectId}
              showAll={showAll}
              onToggleAll={() => updateParams({ all: showAll ? null : "1" })}
              onOpenEvidence={openLatestEvidence}
              onRequestCorrection={openCorrection}
              historyOpen={historyOpen}
              historyCount={
                correctionHistory.state.status === "success"
                  ? correctionHistory.state.data.items.length
                  : 0
              }
              onToggleHistory={() => setHistoryOpen((value) => !value)}
            />
          )}
          {profile.state.status === "success" && (
            <>
            {unlinkedCandidatePage !== null && (
              <div className="profile-status-banner" role="status">
                该候选所在页（第 {unlinkedCandidatePage} 页）尚未关联到档案条目，
                请到「受试者与资料」打开该页原件进行人工核对。
                <button
                  type="button"
                  className="chip"
                  onClick={() => setUnlinkedCandidatePage(null)}
                >
                  知道了
                </button>
              </div>
            )}
            <JudgmentSearchCard
              subjectId={selectedSubject.subjectId}
              reviewEpisodeId={selectedEpisode.reviewEpisodeId}
              evidenceNavigation={profile.state.data.evidenceNavigation}
              onSelectCandidate={openJudgmentSearchCandidate}
            />
            </>
          )}
          {historyOpen && (
            <section className="profile-section profile-correction-history-section" aria-labelledby="profile-correction-history-title">
              <header className="profile-section__heading">
                <h3 id="profile-correction-history-title" className="profile-section__title">
                  修订记录
                  <span className="section-count">
                    {correctionHistory.state.status === "success"
                      ? correctionHistory.state.data.items.length
                      : 0}
                  </span>
                </h3>
                <p className="profile-section__note">
                  每条记录都保留修改前后内容、来源定位和影响范围；既有档案版本不会被覆盖。
                </p>
              </header>
              <ProfileCorrectionHistory
                state={correctionHistory.state}
                subjectId={selectedSubject.subjectId}
                onOpenEvidence={openEvidence}
              />
            </section>
          )}
        </section>

        {evidenceItem !== null && evidenceModel !== null && (
          <ProfileEvidencePanel
            model={evidenceModel}
            item={evidenceItem}
            initialPageArtifactId={evidencePageArtifactId}
            onClose={closeEvidence}
          />
        )}
        {correctionItem !== null && correctionKind !== null && correctionModel !== null && (
          <ProfileFactCorrectionDialog
            model={correctionModel}
            item={correctionItem}
            targetKind={correctionKind}
            subjectId={selectedSubject.subjectId}
            reviewEpisodeId={selectedEpisode.reviewEpisodeId}
            onClose={closeCorrection}
            onOpenEvidence={openCorrectionEvidence}
            evidenceOpen={evidenceItem !== null}
            onCompleted={handleCorrectionCompleted}
          />
        )}
      </div>
    </div>
  );
}

function ProfileBody({
  model,
  project,
  subjectCode,
  center,
  episode,
  subjectId,
  showAll,
  onToggleAll,
  onOpenEvidence,
  onRequestCorrection,
  historyOpen,
  historyCount,
  onToggleHistory,
}: {
  model: PatientProfileModel;
  project: CatalogProjectView | null;
  subjectCode: string;
  center: string;
  episode: CatalogEpisodeView;
  subjectId: string;
  showAll: boolean;
  onToggleAll: () => void;
  onOpenEvidence: (item: ProfileItemView) => void;
  onRequestCorrection: (item: ProfileItemView) => void;
  historyOpen: boolean;
  historyCount: number;
  onToggleHistory: () => void;
}) {
  const pendingTodoGroupRef = useRef<ProfileTodoGroup | null>(null);
  const highlightTimerRef = useRef<number | null>(null);
  const highlightedTargetRef = useRef<HTMLElement | null>(null);

  const scrollToTodo = useCallback(
    (group: ProfileTodoGroup) => {
      const itemId = firstProfileTodoItemId(model, group);
      if (itemId === null) return;
      const item = model.itemById.get(itemId);
      if (item === undefined) return;
      const target = document.getElementById(`profile-item-${item.itemId}`);
      if (target === null) return;
      if (typeof target.scrollIntoView === "function") {
        target.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      if (highlightedTargetRef.current !== null && highlightedTargetRef.current !== target) {
        highlightedTargetRef.current.classList.remove("profile-item--highlighted");
      }
      highlightedTargetRef.current = target;
      target.classList.add("profile-item--highlighted");
      if (highlightTimerRef.current !== null) {
        window.clearTimeout(highlightTimerRef.current);
      }
      highlightTimerRef.current = window.setTimeout(() => {
        target.classList.remove("profile-item--highlighted");
        if (highlightedTargetRef.current === target) {
          highlightedTargetRef.current = null;
        }
        highlightTimerRef.current = null;
      }, 1800);
    },
    [model],
  );

  useEffect(() => {
    if (!showAll || pendingTodoGroupRef.current === null) return;
    const group = pendingTodoGroupRef.current;
    pendingTodoGroupRef.current = null;
    scrollToTodo(group);
  }, [scrollToTodo, showAll]);

  useEffect(
    () => () => {
      if (highlightTimerRef.current !== null) {
        window.clearTimeout(highlightTimerRef.current);
      }
      highlightedTargetRef.current?.classList.remove("profile-item--highlighted");
      highlightedTargetRef.current = null;
    },
    [],
  );

  const onNavigateTodo = useCallback(
    (group: ProfileTodoGroup) => {
      if (firstProfileTodoItemId(model, group) === null) return;
      if (!showAll) {
        pendingTodoGroupRef.current = group;
        onToggleAll();
        return;
      }
      scrollToTodo(group);
    },
    [model, onToggleAll, scrollToTodo, showAll],
  );

  return (
    <>
      <ProfileStatusBanner model={model} />

      <header className="profile-head">
        <div className="profile-head__identity">
          <h2 className="profile-head__subject">{subjectCode}</h2>
          <p className="profile-head__meta">
            {project !== null
              ? `${project.projectName} · ${project.studyPhaseLabel} · 方案 ${project.officialVersion}`
              : ""}
            {center !== "" ? ` · ${center}` : ""}
          </p>
        </div>
        <div className="profile-head__node">
          <span className="count-chip">档案第 {model.revision} 版</span>
          <span className="count-chip">资料版本 {episode.revision}</span>
          <span className="count-chip">生成时间 {formatProfileDateTime(model.generatedAt) ?? "未记录"}</span>
          <span className="count-chip">待核对 {model.pendingReviewCount} 项</span>
          <RouteLink
            to={`/subjects/${subjectId}/evidence`}
            params={{ episode: episode.reviewEpisodeId }}
            className="button button--primary profile-head__evidence"
            title="查看或补充该审核节点的资料"
          >
            查看/补充资料
          </RouteLink>
          <RouteLink
            to="/workbench"
            params={{
              project: project?.projectId ?? undefined,
              subject: subjectId,
              episode: episode.reviewEpisodeId,
            }}
            className="button button--primary profile-head__eligibility"
            title="打开该审核节点的入排审核工作台"
            ariaLabel={`打开 ${subjectCode} 的入排审核工作台`}
          >
            入排审核
          </RouteLink>
        </div>
      </header>

      {!model.isGenerating && !model.isFailed && (
        <ProfileTodoSummaryCard model={model} onNavigate={onNavigateTodo} />
      )}

      <div className="profile-toolbar">
        <div className="profile-toolbar__switch">
          {!model.isGenerating && !model.isFailed && (
            <button
              type="button"
              className="chip"
              aria-pressed={showAll}
              onClick={onToggleAll}
              title={showAll ? "返回首屏重点" : "展开完整历时信息"}
            >
              {showAll ? "返回首屏" : "全部历时信息"}
            </button>
          )}
          <button
            type="button"
            className="chip"
            aria-pressed={historyOpen}
            onClick={onToggleHistory}
            title={historyOpen ? "收起修订记录" : "查看当前审核节点的修订记录"}
          >
            {historyOpen ? "收起修订记录" : "修订记录"}
            <span className="section-count">{historyCount}</span>
          </button>
        </div>
      </div>

      {model.isEmpty ? (
        <EmptyState
          message="该审核节点已生成档案，但当前没有已整理的资料条目。"
          hint="是否存在资料缺漏，请以当前审核节点的资料核对结果为准。空记录不代表正常或否认。"
        />
      ) : model.isGenerating || model.isFailed ? null : showAll ? (
        <ProfileLaneList
          model={model}
          onOpenEvidence={onOpenEvidence}
          onRequestCorrection={onRequestCorrection}
        />
      ) : (
        <section className="profile-section" aria-labelledby="profile-highlights-title">
          <h3 id="profile-highlights-title" className="profile-section__title">
            首屏重点
            <span className="section-count">{model.highlights.length}</span>
          </h3>
          <ProfileHighlights
            model={model}
            onOpenEvidence={onOpenEvidence}
            onRequestCorrection={onRequestCorrection}
          />
        </section>
      )}
    </>
  );
}

export default SubjectsPage;
