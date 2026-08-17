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
  type FeedbackDraftValues,
} from "./ProtocolRedoDialogs";
import { ProtocolJobProgress } from "./ProtocolJobProgress";
import { ProtocolPublishResult } from "./ProtocolPublishResult";
import { ProtocolRecoveryBanner } from "./ProtocolRecoveryBanner";

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
  const [cancelBusy, setCancelBusy] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [publishBusy, setPublishBusy] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [publishResult, setPublishResult] = useState<PublishResultView | null>(null);
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
    { enabled: sessionData?.awaitingUser === "review" && isRedo },
  );

  useEffect(() => {
    if (
      sessionStatus !== "success" ||
      !["queued", "running", "recovering"].includes(jobState ?? "")
    ) {
      return;
    }
    const timer = window.setTimeout(session.retry, 1200);
    return () => window.clearTimeout(timer);
  }, [jobState, session.retry, sessionStatus]);

  const handleConfirmIdentity = useCallback(
    async (input: ConfirmIdentityInput) => {
      setConfirmBusy(true);
      setConfirmError(null);
      try {
        await repo.confirmIdentity(jobId, input);
        session.retry();
        draftBundle.retry();
        comparison.retry();
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
    [jobId, repo, session, draftBundle, comparison],
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
      if (isRedo) comparison.retry();
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
  }, [comparison, draftBundle, isRedo, isStubDemo, jobId, repo, setDraftSaved]);

  const handleSubmitFeedback = useCallback(
    async (values: FeedbackDraftValues) => {
      if (comparison.state.status !== "success") return;
      setFeedbackBusy(true);
      setFeedbackError(null);
      const candidate = comparison.state.data.candidate;
      try {
        const next = await repo.submitFeedback(jobId, {
          expectedRevisionId: candidate.revisionId,
          draft: candidate.content,
          feedbackKind: values.kind,
          feedbackNote: values.note.length > 0 ? values.note : null,
        });
        setFeedbackOpen(false);
        comparison.retry();
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
    [comparison, isStubDemo, jobId, repo, setDraftSaved],
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

  if (
    currentSession.recoveryCheckpointId !== null &&
    currentSession.awaitingUser !== "review" &&
    currentSession.awaitingUser !== "identity"
  ) {
    return (
      <div className="protocols">
        <ProtocolRecoveryBanner
          session={currentSession}
          onContinue={() => {
            if (repo.kind === "stub" && jobId === PROTOCOL_RECOVERY_JOB_ID) {
              navigate("/protocols", { job: PROTOCOL_DEMO_JOB_ID });
              return;
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

  if (currentSession.awaitingUser === "review" && isRedo) {
    if (comparison.state.status === "loading") return <LoadingState />;
    if (comparison.state.status === "error") {
      return <ErrorState message={comparison.state.message} onRetry={comparison.retry} />;
    }
    return (
      <div className="protocols">
        <ProtocolComparisonWorkbench
          session={currentSession}
          comparison={comparison.state.data}
          saving={saveBusy}
          feedbackBusy={feedbackBusy}
          onSaveDraft={handleSaveDraft}
          onOpenFeedback={() => {
            setFeedbackError(null);
            setFeedbackOpen(true);
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
          onClose={() => {
            if (feedbackBusy) return;
            setFeedbackOpen(false);
          }}
          onSubmit={handleSubmitFeedback}
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

  if (currentSession.awaitingUser === "review") {
    if (draftBundle.state.status === "loading") return <LoadingState />;
    if (draftBundle.state.status === "error") {
      return <ErrorState message={draftBundle.state.message} onRetry={draftBundle.retry} />;
    }
    const { draft, integrity, sources } = draftBundle.state.data;
    return (
      <ProtocolDraftWorkbench
        session={currentSession}
        draft={draft}
        integrity={integrity}
        sources={sources}
        componentParam={componentParam}
        onSaveDraft={handleSaveDraft}
        saving={saveBusy}
        saveError={saveError ?? undefined}
        uatDraftSaved={isStubDemo ? draftSaved : undefined}
        onUatReset={isStubDemo ? handleResetTrial : undefined}
      />
    );
  }

  return <ProtocolJobProgress session={currentSession} onRefresh={session.retry} />;
}
