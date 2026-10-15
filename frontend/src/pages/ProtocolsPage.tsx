/**
 * 方案工作台（Phase 3 Slice 6）：首次解构 / 重新解构分流与草稿审阅主路径。
 * 重新解构：选择目标正式项目 → 上传新版方案 → 并列比较规则变化 → 保存/取消/发布。
 */

import { useCallback, useEffect, useState } from "react";
import {
  getProtocolWorkbenchRepository,
  ProtocolWorkbenchApiError,
} from "../api/protocolWorkbenchRepository";
import { navigate, RouteLink, useHashRoute } from "../app/router";
import { rememberProtocolJob } from "../app/lastProtocolJob";
import { ProtocolWorkbenchHome } from "../components/protocols/ProtocolWorkbenchHome";
import { ProtocolUploadPanel } from "../components/protocols/ProtocolUploadPanel";
import { ProtocolRedoSelectPanel } from "../components/protocols/ProtocolRedoSelectPanel";
import { ProtocolJobFlow } from "../components/protocols/ProtocolJobFlow";
import {
  WorkbenchProjectEntry,
  isReturnRouteRejected,
  sanitizeReturnRoute,
} from "../components/protocols/WorkbenchProjectEntry";

export function ProtocolsPage() {
  const { params } = useHashRoute();
  const mode = params.get("mode");
  const jobId = params.get("job");
  // 共享工作台来源：显式命名空间元数据，只随上传持久保存；返回上下文仅接受
  // 本产品相对路由，绝对 returnUrl 一律丢弃并如实提示。
  const workbenchOrigin = params.get("workbench_origin");
  const rawReturnRoute = params.get("return");
  const workbenchReturnRoute = sanitizeReturnRoute(rawReturnRoute);
  const workbenchReturnRejected = isReturnRouteRejected(rawReturnRoute);

  const repo = getProtocolWorkbenchRepository();
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  useEffect(() => {
    if (jobId !== null) rememberProtocolJob(jobId);
  }, [jobId]);

  const handleUpload = useCallback(
    async (file: File, projectId: string | null = null) => {
      setUploadBusy(true);
      setUploadError(null);
      try {
        const result = await repo.startDeconstruction(file, `upload-${Date.now()}`, {
          projectId: projectId ?? undefined,
          workbenchOrigin: workbenchOrigin ?? undefined,
        });
        rememberProtocolJob(result.jobId);
        navigate("/protocols", {
          job: result.jobId,
          ...(workbenchOrigin !== null ? { workbench_origin: workbenchOrigin } : {}),
          ...(workbenchReturnRoute !== null ? { return: workbenchReturnRoute } : {}),
        });
      } catch (error) {
        setUploadError(
          error instanceof ProtocolWorkbenchApiError
            ? `${error.message} ${error.recoveryAction}`
            : "文件登记失败，请稍后重试。",
        );
      } finally {
        setUploadBusy(false);
      }
    },
    [repo, workbenchOrigin, workbenchReturnRoute],
  );

  const handleFirstUpload = useCallback(
    (file: File) => handleUpload(file, null),
    [handleUpload],
  );
  const handleRedoUpload = useCallback(
    (file: File, projectId: string) => handleUpload(file, projectId),
    [handleUpload],
  );
  const handleFeedbackRevision = useCallback(
    async (projectId: string) => {
      setUploadBusy(true);
      setUploadError(null);
      try {
        const result = await repo.startFeedbackRevision(
          projectId,
          `feedback-revision-${Date.now()}`,
          { workbenchOrigin: workbenchOrigin ?? undefined },
        );
        rememberProtocolJob(result.jobId);
        navigate("/protocols", { job: result.jobId,
          ...(workbenchOrigin !== null ? { workbench_origin: workbenchOrigin } : {}),
          ...(workbenchReturnRoute !== null ? { return: workbenchReturnRoute } : {}),
        });
      } catch (error) {
        setUploadError(
          error instanceof ProtocolWorkbenchApiError
            ? `${error.message} ${error.recoveryAction}`
            : "反馈修订稿准备失败，请稍后重试。",
        );
      } finally {
        setUploadBusy(false);
      }
    },
    [repo, workbenchOrigin, workbenchReturnRoute],
  );

  if (mode === null && jobId === null) {
    return <ProtocolWorkbenchHome />;
  }

  if (mode === "redo" && jobId === null) {
    return (
      <>
      {workbenchOrigin !== null && <p className="protocol-upload__back">
        <RouteLink to="/protocols" params={{ mode: "workbench", workbench_origin: workbenchOrigin,
          ...(workbenchReturnRoute !== null ? { return: workbenchReturnRoute } : {}) }}
          className="button button--quiet">返回项目入口</RouteLink>
      </p>}
      <ProtocolRedoSelectPanel
        initialProjectId={params.get("project")}
        busy={uploadBusy}
        error={uploadError}
        onUpload={handleRedoUpload}
        onStartFeedback={handleFeedbackRevision}
      />
      </>
    );
  }

  if (mode === "first" && jobId === null) {
    return (
      <ProtocolUploadPanel
        busy={uploadBusy}
        error={uploadError}
        onUpload={handleFirstUpload}
        onInvalidFile={setUploadError}
      />
    );
  }

  // 共享工作台来源入口：来源已绑定时按持久身份跳既有任务/项目流程；
  // 未绑定只提供真实 DOCX 上传。缺少 origin 的深链退回工作台首页。
  if (mode === "workbench" && jobId === null && workbenchOrigin !== null) {
    return (
      <WorkbenchProjectEntry
        origin={workbenchOrigin}
        returnRoute={workbenchReturnRoute}
        returnRejected={workbenchReturnRejected}
        busy={uploadBusy}
        error={uploadError}
        onUpload={handleFirstUpload}
        onInvalidFile={setUploadError}
      />
    );
  }

  if (jobId !== null) {
    return <>
      {workbenchOrigin !== null && <p className="protocol-upload__back">
        <RouteLink to="/protocols" params={{ mode: "workbench", workbench_origin: workbenchOrigin,
          ...(workbenchReturnRoute !== null ? { return: workbenchReturnRoute } : {}) }}
          className="button button--quiet">返回项目入口</RouteLink>
      </p>}
      <ProtocolJobFlow jobId={jobId} componentParam={params.get("component")} />
    </>;
  }

  return <ProtocolWorkbenchHome />;
}

export default ProtocolsPage;
