/**
 * 单个解构任务的状态机视图。
 */

import { useCallback, useEffect, useState } from "react";
import {
  getProtocolWorkbenchRepository,
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
  const [saveBusy, setSaveBusy] = useState(false);
  const [draftSaved, setDraftSaved, resetDraftSaved] = useSessionState(
    UAT_KEY_PROTOCOL_DRAFT_SAVED,
    false,
    (value) => (typeof value === "boolean" ? value : null),
  );

  const session = useLoad((signal) => repo.getSession(jobId, { signal }), [jobId, repo]);

  const identity = useLoad((signal) => repo.getIdentityReview(jobId, { signal }), [jobId, repo]);

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
  );

  const sessionStatus = session.state.status;
  const jobState = sessionStatus === "success" ? session.state.data.state : null;

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
      try {
        await repo.confirmIdentity(jobId, input);
        session.retry();
        draftBundle.retry();
      } finally {
        setConfirmBusy(false);
      }
    },
    [jobId, repo, session, draftBundle],
  );

  const handleSaveDraft = useCallback(async () => {
    if (draftBundle.state.status !== "success") return;
    setSaveBusy(true);
    try {
      await repo.saveDraft(jobId, draftBundle.state.data.draft.revisionId);
      if (isStubDemo) setDraftSaved(true);
      draftBundle.retry();
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

  const sessionData = session.state.data;

  if (
    sessionData.recoveryCheckpointId !== null &&
    sessionData.awaitingUser !== "review" &&
    sessionData.awaitingUser !== "identity"
  ) {
    return (
      <div className="protocols">
        <ProtocolRecoveryBanner
          session={sessionData}
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

  if (sessionData.awaitingUser === "identity") {
    if (identity.state.status === "loading") return <LoadingState />;
    if (identity.state.status === "error") {
      return (
        <ErrorState message="身份信息尚未就绪，请稍候再试。" onRetry={identity.retry} />
      );
    }
    return (
      <ProtocolIdentityPanel
        review={identity.state.data}
        busy={confirmBusy}
        onConfirm={handleConfirmIdentity}
        onCancel={() => navigate("/protocols")}
      />
    );
  }

  if (sessionData.awaitingUser === "review") {
    if (draftBundle.state.status === "loading") return <LoadingState />;
    if (draftBundle.state.status === "error") {
      return (
        <ErrorState message="草稿尚未生成或暂时无法打开。" onRetry={draftBundle.retry} />
      );
    }
    const { draft, integrity, sources } = draftBundle.state.data;
    return (
      <ProtocolDraftWorkbench
        session={sessionData}
        draft={draft}
        integrity={integrity}
        sources={sources}
        componentParam={componentParam}
        onSaveDraft={handleSaveDraft}
        saving={saveBusy}
        uatDraftSaved={isStubDemo ? draftSaved : undefined}
        onUatReset={isStubDemo ? handleResetTrial : undefined}
      />
    );
  }

  return <ProtocolJobProgress session={sessionData} onRefresh={session.retry} />;
}
