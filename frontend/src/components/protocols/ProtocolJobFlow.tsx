/**
 * 单个解构任务的状态机视图。
 */

import { useCallback, useState } from "react";
import {
  getProtocolWorkbenchRepository,
  PROTOCOL_DEMO_JOB_ID,
  PROTOCOL_RECOVERY_JOB_ID,
} from "../../api/protocolWorkbenchRepository";
import type { ConfirmIdentityInput } from "../../api/protocolWorkbenchTypes";
import { navigate, RouteLink } from "../../app/router";
import { useLoad } from "../../app/useLoad";
import { EmptyState, ErrorState, LoadingState } from "../shell/Feedback";
import { ProtocolIdentityPanel } from "./ProtocolIdentityPanel";
import { ProtocolDraftWorkbench } from "./ProtocolDraftWorkbench";
import { ProtocolRecoveryBanner } from "./ProtocolRecoveryBanner";

interface ProtocolJobFlowProps {
  jobId: string;
  componentParam: string | null;
}

export function ProtocolJobFlow({ jobId, componentParam }: ProtocolJobFlowProps) {
  const repo = getProtocolWorkbenchRepository();
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);

  const session = useLoad(() => repo.getSession(jobId), [jobId]);

  const identity = useLoad(() => repo.getIdentityReview(jobId), [jobId]);

  const draftBundle = useLoad(
    async () => {
      const [draft, integrity, sources] = await Promise.all([
        repo.getDraft(jobId),
        repo.getIntegrity(jobId),
        repo.getSources(jobId),
      ]);
      return { draft, integrity, sources };
    },
    [jobId],
  );

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
      draftBundle.retry();
    } finally {
      setSaveBusy(false);
    }
  }, [jobId, repo, draftBundle]);

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
            if (jobId === PROTOCOL_RECOVERY_JOB_ID) {
              navigate("/protocols", { job: PROTOCOL_DEMO_JOB_ID });
            } else {
              session.retry();
            }
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

  if (sessionData.awaitingUser === "review" || jobId === PROTOCOL_DEMO_JOB_ID) {
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
      />
    );
  }

  return (
    <EmptyState message={`任务状态：${sessionData.stateLabel}`} hint={sessionData.nextAction} />
  );
}
