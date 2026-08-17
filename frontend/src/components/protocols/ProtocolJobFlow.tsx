/**
 * 单个解构任务的状态机视图。
 */

import { useCallback, useEffect, useState } from "react";
import {
  getProtocolWorkbenchRepository,
  ProtocolWorkbenchApiError,
  PROTOCOL_DEMO_JOB_ID,
  PROTOCOL_RECOVERY_JOB_ID,
} from "../../api/protocolWorkbenchRepository";
import type { ConfirmIdentityInput } from "../../api/protocolWorkbenchTypes";
import { navigate, RouteLink, updateParams } from "../../app/router";
import { useLoad } from "../../app/useLoad";
import { useSessionState } from "../../app/useSessionState";
import { UAT_KEY_PROTOCOL_DRAFT_SAVED } from "../../app/uatTrialState";
import { ErrorState, LoadingState } from "../shell/Feedback";
import { ProtocolIdentityPanel } from "./ProtocolIdentityPanel";
import { ProtocolDraftWorkbench } from "./ProtocolDraftWorkbench";
import { ProtocolJobProgress } from "./ProtocolJobProgress";
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
  const [draftSaved, setDraftSaved, resetDraftSaved] = useSessionState(
    UAT_KEY_PROTOCOL_DRAFT_SAVED,
    false,
    (value) => (typeof value === "boolean" ? value : null),
  );

  const session = useLoad((signal) => repo.getSession(jobId, { signal }), [jobId, repo]);

  const sessionStatus = session.state.status;
  const sessionData = sessionStatus === "success" ? session.state.data : null;
  const jobState = sessionData?.state ?? null;

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
    { enabled: sessionData?.awaitingUser === "review" },
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
    [jobId, repo, session, draftBundle],
  );

  const handleSaveDraft = useCallback(async () => {
    if (draftBundle.state.status !== "success") return;
    setSaveBusy(true);
    setSaveError(null);
    try {
      await repo.saveDraft(jobId, draftBundle.state.data.draft.revisionId);
      if (isStubDemo) setDraftSaved(true);
      draftBundle.retry();
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
  }, [draftBundle, isStubDemo, jobId, repo, setDraftSaved]);

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
