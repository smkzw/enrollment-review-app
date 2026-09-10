/**
 * 单个解构任务的状态机视图（首次解构 + 重新解构共用）。
 * 重新解构在等待审阅时切换到并列差异工作台，并提供基于反馈修订、保存、取消与发布。
 */

import { useCallback, useEffect, useState } from "react";
import {
  getProtocolWorkbenchRepository,
  ProtocolWorkbenchApiError,
  PROTOCOL_DEMO_JOB_ID,
  PROTOCOL_RECOVERY_JOB_ID,
} from "../../api/protocolWorkbenchRepository";
import type {
  ConfirmIdentityInput,
  PublishResultView,
} from "../../api/protocolWorkbenchTypes";
import { navigate, RouteLink, updateParams } from "../../app/router";
import { clearRememberedProtocolJob } from "../../app/lastProtocolJob";
import { useLoad } from "../../app/useLoad";
import { useSessionState } from "../../app/useSessionState";
import { UAT_KEY_PROTOCOL_DRAFT_SAVED } from "../../app/uatTrialState";
import { ErrorState, LoadingState } from "../shell/Feedback";
import { ProtocolIdentityPanel } from "./ProtocolIdentityPanel";
import { ProtocolDraftWorkbench } from "./ProtocolDraftWorkbench";
import { ProtocolComparisonWorkbench } from "./ProtocolComparisonWorkbench";
import {
  ProtocolConfirmCancelDialog,
  ProtocolConfirmPublishDialog,
  ProtocolFeedbackDialog,
  ProtocolManualEditDialog,
  type FeedbackDraftValues,
  type ManualEditValues,
} from "./ProtocolRedoDialogs";
import { ProtocolJobProgress } from "./ProtocolJobProgress";
import { ProtocolPublishResult } from "./ProtocolPublishResult";
import { ProtocolPublishedSummary } from "./ProtocolPublishedSummary";
import { ProtocolRecoveryBanner } from "./ProtocolRecoveryBanner";
import { patchComponentSemantics } from "../../domain/protocolManualEdit";

interface ProtocolJobFlowProps {
  jobId: string;
  componentParam: string | null;
}

export function ProtocolJobFlow({ jobId, componentParam }: ProtocolJobFlowProps) {
  const repo = getProtocolWorkbenchRepository();
  const isStubDemo = repo.kind === "stub" && jobId === PROTOCOL_DEMO_JOB_ID;
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [feedbackBusy, setFeedbackBusy] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [manualEditBusy, setManualEditBusy] = useState(false);
  const [manualEditError, setManualEditError] = useState<string | null>(null);
  const [manualEditOpen, setManualEditOpen] = useState(false);
  const [cancelBusy, setCancelBusy] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [publishBusy, setPublishBusy] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [publishResult, setPublishResult] = useState<PublishResultView | null>(null);
  const [retryBusy, setRetryBusy] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [draftSaved, setDraftSaved, resetDraftSaved] = useSessionState(
    UAT_KEY_PROTOCOL_DRAFT_SAVED,
    false,
    (value) => (typeof value === "boolean" ? value : null),
  );

  const session = useLoad((signal) => repo.getSession(jobId, { signal }), [jobId, repo]);

  const sessionStatus = session.state.status;
  const sessionData = sessionStatus === "success" ? session.state.data : null;
  const jobState = sessionData?.state ?? null;
  const isRedo = sessionData?.sessionKind === "re_deconstruction";

  const identity = useLoad(
    (signal) => repo.getIdentityReview(jobId, { signal }),
    [jobId, repo],
    { enabled: sessionData?.awaitingUser === "identity" },
  );

  const draftBundle = useLoad(
    async (signal) => {
      const [draft, integrity, sources] = await Promise.all([
        repo.getDraft(jobId, { signal }),
        repo.getIntegrity(jobId, { signal }),
        repo.getSources(jobId, { signal }),
      ]);
      return { draft, integrity, sources };
    },
    [jobId, repo],
    { enabled: sessionData?.awaitingUser === "review" && !isRedo },
  );

  const comparison = useLoad(
    (signal) => repo.getDraftComparison(jobId, { signal }),
    [jobId, repo],
    {
      enabled:
        (sessionData?.awaitingUser === "review" ||
          sessionData?.awaitingUser === "publish") &&
        isRedo,
    },
  );

  const publishedDraft = useLoad(
    (signal) => repo.getDraft(jobId, { signal }),
    [jobId, repo],
    {
      enabled:
        sessionData?.state === "completed" &&
        sessionData?.draftStatus === "published",
    },
  );

  const redoReview = useLoad(
    async (signal) => {
      const [integrity, sources] = await Promise.all([
        repo.getIntegrity(jobId, { signal }),
        repo.getSources(jobId, { signal }),
      ]);
      return { integrity, sources };
    },
    [jobId, repo],
    {
      enabled:
        (sessionData?.awaitingUser === "review" ||
          sessionData?.awaitingUser === "publish") &&
        isRedo,
    },
  );

  useEffect(() => {
    if (
      sessionStatus !== "success" ||
      !["queued", "running", "recovering", "failed_retryable"].includes(
        jobState ?? "",
      )
    ) {
      return;
    }
    const timer = window.setTimeout(session.retry, 1200);
    return () => window.clearTimeout(timer);
  }, [jobState, session.retry, sessionStatus]);

  useEffect(() => {
    if (sessionData?.state === "completed") clearRememberedProtocolJob();
  }, [sessionData?.state]);

  useEffect(() => {
    if (publishResult !== null) clearRememberedProtocolJob();
  }, [publishResult]);

  const handleConfirmIdentity = useCallback(
    async (input: ConfirmIdentityInput) => {
      setConfirmBusy(true);
      setConfirmError(null);
      try {
        await repo.confirmIdentity(jobId, input);
        session.retry();
        draftBundle.retry();
        comparison.retry();
        redoReview.retry();
      } catch (error) {
        if (error instanceof ProtocolWorkbenchApiError) {
          setConfirmError(`${error.message} ${error.recoveryAction}`);
        } else if (error instanceof Error) {
          setConfirmError(error.message);
        } else {
          setConfirmError("方案信息确认未能提交，请稍后重试。");
        }
      } finally {
        setConfirmBusy(false);
      }
    },
    [jobId, repo, session, draftBundle, comparison, redoReview],
  );

  const handleSaveDraft = useCallback(async () => {
    // 重新解构：以候选草稿当前 revision 保存；首次解构沿用草稿字节卡。
    const expectedRevisionId =
      isRedo && comparison.state.status === "success"
        ? comparison.state.data.candidate.revisionId
        : draftBundle.state.status === "success"
          ? draftBundle.state.data.draft.revisionId
          : null;
    if (expectedRevisionId === null) return;
    setSaveBusy(true);
    setSaveError(null);
    try {
      await repo.saveDraft(jobId, expectedRevisionId);
      if (isStubDemo) setDraftSaved(true);
      if (isRedo) {
        comparison.retry();
        redoReview.retry();
      }
      else draftBundle.retry();
    } catch (error) {
      if (error instanceof ProtocolWorkbenchApiError) {
        setSaveError(`${error.message} ${error.recoveryAction}`);
      } else if (error instanceof Error) {
        setSaveError(error.message);
      } else {
        setSaveError("草稿保存未能完成，请稍后重试。");
      }
    } finally {
      setSaveBusy(false);
    }
  }, [comparison, draftBundle, isRedo, isStubDemo, jobId, redoReview, repo, setDraftSaved]);

  const handleSubmitFeedback = useCallback(
    async (values: FeedbackDraftValues) => {
      if (comparison.state.status !== "success") return;
      setFeedbackBusy(true);
      setFeedbackError(null);
      const candidate = comparison.state.data.candidate;
      try {
        const next = await repo.submitFeedback(jobId, {
          expectedRevisionId: candidate.revisionId,
          feedbackKind: values.kind,
          targetRuleCode: values.targetRuleCode,
          feedbackNote: values.note,
        });
        setFeedbackOpen(false);
        comparison.retry();
        redoReview.retry();
        if (isStubDemo && next.revisionNumber > 1) setDraftSaved(true);
      } catch (error) {
        if (error instanceof ProtocolWorkbenchApiError) {
          setFeedbackError(`${error.message} ${error.recoveryAction}`);
        } else if (error instanceof Error) {
          setFeedbackError(error.message);
        } else {
          setFeedbackError("反馈修订未能提交，请稍后重试。");
        }
      } finally {
        setFeedbackBusy(false);
      }
    },
    [comparison, isStubDemo, jobId, redoReview, repo, setDraftSaved],
  );

  const handleSubmitManualEdit = useCallback(
    async (values: ManualEditValues) => {
      if (comparison.state.status !== "success") return;
      setManualEditBusy(true);
      setManualEditError(null);
      const candidate = comparison.state.data.candidate;
      const patched = patchComponentSemantics(
        candidate.content,
        values.componentId,
        values.patch,
      );
      try {
        const next = await repo.editDraft(jobId, {
          expectedRevisionId: candidate.revisionId,
          draft: patched,
        });
        setManualEditOpen(false);
        comparison.retry();
        redoReview.retry();
        if (isStubDemo && next.revisionNumber > 1) setDraftSaved(true);
      } catch (error) {
        if (error instanceof ProtocolWorkbenchApiError) {
          setManualEditError(`${error.message} ${error.recoveryAction}`);
        } else if (error instanceof Error) {
          setManualEditError(error.message);
        } else {
          setManualEditError("手工修订未能提交，请稍后重试。");
        }
      } finally {
        setManualEditBusy(false);
      }
    },
    [comparison, isStubDemo, jobId, redoReview, repo, setDraftSaved],
  );

  const handleCancelDraft = useCallback(async () => {
    const expectedRevisionId =
      isRedo && comparison.state.status === "success"
        ? comparison.state.data.candidate.revisionId
        : draftBundle.state.status === "success"
          ? draftBundle.state.data.draft.revisionId
          : null;
    if (expectedRevisionId === null) {
      setCancelOpen(false);
      navigate("/protocols");
      return;
    }
    setCancelBusy(true);
    setCancelError(null);
    try {
      await repo.cancelDraft(jobId, expectedRevisionId);
      setCancelOpen(false);
      navigate("/protocols");
    } catch (error) {
      if (error instanceof ProtocolWorkbenchApiError) {
        setCancelError(`${error.message} ${error.recoveryAction}`);
      } else if (error instanceof Error) {
        setCancelError(error.message);
      } else {
        setCancelError("取消未能完成，请稍后重试。");
      }
    } finally {
      setCancelBusy(false);
    }
  }, [comparison, draftBundle, isRedo, jobId, repo]);

  const handlePublish = useCallback(async () => {
    setPublishBusy(true);
    setPublishError(null);
    try {
      const result = await repo.publish(jobId, `publish-${Date.now()}`);
      setPublishOpen(false);
      setPublishResult(result);
    } catch (error) {
      if (error instanceof ProtocolWorkbenchApiError) {
        setPublishError(`${error.message} ${error.recoveryAction}`);
      } else if (error instanceof Error) {
        setPublishError(error.message);
      } else {
        setPublishError("发布未能完成，请稍后重试。");
      }
    } finally {
      setPublishBusy(false);
    }
  }, [jobId, repo]);

  const handleResetTrial = useCallback(() => {
    resetDraftSaved();
    updateParams({ component: null });
  }, [resetDraftSaved]);

  if (session.state.status === "loading") {
    return <LoadingState />;
  }
  if (session.state.status === "error") {
    return (
      <ErrorState
        message={
          session.state.message.includes("未找到")
            ? "未找到该解构任务，可能已过期。"
            : session.state.message
        }
        onRetry={() => navigate("/protocols")}
      />
    );
  }
  const currentSession = session.state.data;

  // 发布成功：无论任务状态如何，直接展示结果页。
  if (publishResult !== null) {
    return <ProtocolPublishResult session={currentSession} result={publishResult} />;
  }

  if (currentSession.state === "completed" && currentSession.draftStatus === "published") {
    if (publishedDraft.state.status === "loading") return <LoadingState />;
    if (publishedDraft.state.status === "error") {
      return <ErrorState message={publishedDraft.state.message} onRetry={publishedDraft.retry} />;
    }
    return (
      <ProtocolPublishedSummary
        session={currentSession}
        draft={publishedDraft.state.data}
      />
    );
  }

  if (
    currentSession.recoveryCheckpointId !== null &&
    ["resumable", "failed_final"].includes(currentSession.state) &&
    currentSession.awaitingUser !== "review" &&
    currentSession.awaitingUser !== "identity"
  ) {
    return (
      <div className="protocols">
        <ProtocolRecoveryBanner
          session={currentSession}
          busy={retryBusy}
          errorMessage={retryError ?? undefined}
          onContinue={async () => {
            if (repo.kind === "stub" && jobId === PROTOCOL_RECOVERY_JOB_ID) {
              navigate("/protocols", { job: PROTOCOL_DEMO_JOB_ID });
              return;
            }
            if (currentSession.state === "failed_final") {
              setRetryBusy(true);
              setRetryError(null);
              try {
                await repo.retryFailedStep(jobId);
              } catch (error) {
                if (error instanceof ProtocolWorkbenchApiError) {
                  setRetryError(`${error.message} ${error.recoveryAction}`);
                } else {
                  setRetryError("草稿未能重新开始，请稍后再试。");
                }
              } finally {
                setRetryBusy(false);
              }
            }
            session.retry();
          }}
        />
        <p className="protocol-recovery__home-link">
          <RouteLink to="/protocols" className="button button--quiet">
            返回首页
          </RouteLink>
        </p>
      </div>
    );
  }

  if (currentSession.awaitingUser === "identity") {
    if (identity.state.status === "loading") return <LoadingState />;
    if (identity.state.status === "error") {
      return <ErrorState message={identity.state.message} onRetry={identity.retry} />;
    }
    return (
      <ProtocolIdentityPanel
        review={identity.state.data}
        busy={confirmBusy}
        errorMessage={confirmError ?? undefined}
        onConfirm={handleConfirmIdentity}
        onCancel={() => navigate("/protocols")}
      />
    );
  }

  if (
    (currentSession.awaitingUser === "review" || currentSession.awaitingUser === "publish") &&
    isRedo
  ) {
    if (comparison.state.status === "loading") return <LoadingState />;
    if (comparison.state.status === "error") {
      return <ErrorState message={comparison.state.message} onRetry={comparison.retry} />;
    }
    if (redoReview.state.status === "loading") return <LoadingState />;
    if (redoReview.state.status === "error") {
      return <ErrorState message={redoReview.state.message} onRetry={redoReview.retry} />;
    }
    return (
      <div className="protocols">
        <ProtocolComparisonWorkbench
          session={currentSession}
          comparison={comparison.state.data}
          integrity={redoReview.state.data.integrity}
          sources={redoReview.state.data.sources}
          saving={saveBusy}
          feedbackBusy={feedbackBusy}
          onSaveDraft={handleSaveDraft}
          onOpenFeedback={() => {
            setFeedbackError(null);
            setFeedbackOpen(true);
          }}
          onOpenManualEdit={() => {
            setManualEditError(null);
            setManualEditOpen(true);
          }}
          onCancel={() => setCancelOpen(true)}
          onPublish={() => {
            setPublishError(null);
            setPublishOpen(true);
          }}
          actionError={saveError ?? publishError ?? undefined}
        />
        <ProtocolFeedbackDialog
          open={feedbackOpen}
          busy={feedbackBusy}
          errorMessage={feedbackError ?? undefined}
          candidateContent={comparison.state.data.candidate.content}
          onClose={() => {
            if (feedbackBusy) return;
            setFeedbackOpen(false);
          }}
          onSubmit={handleSubmitFeedback}
        />
        <ProtocolManualEditDialog
          open={manualEditOpen}
          busy={manualEditBusy}
          errorMessage={manualEditError ?? undefined}
          candidateContent={comparison.state.data.candidate.content}
          onClose={() => {
            if (manualEditBusy) return;
            setManualEditOpen(false);
          }}
          onSubmit={handleSubmitManualEdit}
        />
        <ProtocolConfirmCancelDialog
          open={cancelOpen}
          busy={cancelBusy}
          errorMessage={cancelError ?? undefined}
          onClose={() => {
            if (cancelBusy) return;
            setCancelError(null);
            setCancelOpen(false);
          }}
          onConfirm={handleCancelDraft}
        />
        <ProtocolConfirmPublishDialog
          open={publishOpen}
          busy={publishBusy}
          sessionLabel={`目标项目：${currentSession.targetProjectName ?? "—"} · 当前正式版本 ${currentSession.targetOfficialVersion ?? "—"}`}
          onClose={() => {
            if (publishBusy) return;
            setPublishOpen(false);
          }}
          onConfirm={handlePublish}
        />
      </div>
    );
  }

  if (currentSession.awaitingUser === "review" || currentSession.awaitingUser === "publish") {
    if (draftBundle.state.status === "loading") return <LoadingState />;
    if (draftBundle.state.status === "error") {
      return <ErrorState message={draftBundle.state.message} onRetry={draftBundle.retry} />;
    }
    const { draft, integrity, sources } = draftBundle.state.data;
    return (
      <>
        <ProtocolDraftWorkbench
          session={currentSession}
          draft={draft}
          integrity={integrity}
          sources={sources}
          componentParam={componentParam}
          onSaveDraft={handleSaveDraft}
          onCancel={() => setCancelOpen(true)}
          onPublish={() => {
            setPublishError(null);
            setPublishOpen(true);
          }}
          saving={saveBusy}
          publishing={publishBusy}
          saveError={saveError ?? publishError ?? undefined}
          uatDraftSaved={isStubDemo ? draftSaved : undefined}
          onUatReset={isStubDemo ? handleResetTrial : undefined}
        />
        <ProtocolConfirmCancelDialog
          open={cancelOpen}
          busy={cancelBusy}
          errorMessage={cancelError ?? undefined}
          isRedo={false}
          onClose={() => {
            if (cancelBusy) return;
            setCancelError(null);
            setCancelOpen(false);
          }}
          onConfirm={handleCancelDraft}
        />
        <ProtocolConfirmPublishDialog
          open={publishOpen}
          busy={publishBusy}
          isRedo={false}
          sessionLabel={`${currentSession.protocolCode ?? draft.protocolCode} · ${currentSession.selectedPhaseLabel ?? draft.studyPhaseLabel} · ${currentSession.officialVersion ?? "待核对版本"}`}
          onClose={() => {
            if (publishBusy) return;
            setPublishOpen(false);
          }}
          onConfirm={handlePublish}
        />
      </>
    );
  }

  return <ProtocolJobProgress session={currentSession} onRefresh={session.retry} />;
}
