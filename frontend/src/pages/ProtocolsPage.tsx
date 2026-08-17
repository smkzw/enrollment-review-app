/**
 * 方案工作台（Phase 3 Slice 5）：首次解构 / 重新解构分流与草稿审阅主路径。
 */

import { useCallback, useState } from "react";
import {
  getProtocolWorkbenchRepository,
  ProtocolWorkbenchApiError,
} from "../api/protocolWorkbenchRepository";
import { navigate, RouteLink, useHashRoute } from "../app/router";
import { EmptyState } from "../components/shell/Feedback";
import { ProtocolWorkbenchHome } from "../components/protocols/ProtocolWorkbenchHome";
import { ProtocolUploadPanel } from "../components/protocols/ProtocolUploadPanel";
import { ProtocolJobFlow } from "../components/protocols/ProtocolJobFlow";

export function ProtocolsPage() {
  const { params } = useHashRoute();
  const mode = params.get("mode");
  const jobId = params.get("job");

  const repo = getProtocolWorkbenchRepository();
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const handleUpload = useCallback(
    async (file: File) => {
      setUploadBusy(true);
      setUploadError(null);
      try {
        const result = await repo.startDeconstruction(file, `upload-${Date.now()}`);
        navigate("/protocols", { job: result.jobId });
      } catch (error) {
        setUploadError(
          error instanceof ProtocolWorkbenchApiError
            ? error.message
            : "文件登记失败，请稍后重试。",
        );
      } finally {
        setUploadBusy(false);
      }
    },
    [repo],
  );

  if (mode === null && jobId === null) {
    return <ProtocolWorkbenchHome />;
  }

  if (mode === "redo" && jobId === null) {
    return (
      <div className="protocol-redo-placeholder">
        <header className="page-head">
          <h1 className="page-head__title">重新解构已有项目</h1>
          <p className="page-head__note">
            在已发布项目上上传新版方案，并列比较八类结构化差异。完整交互将在切片 6 接入。
          </p>
        </header>
        <EmptyState
          message="重新解构流程尚未在本切片开放"
          hint="请先从项目看板进入已有项目，或返回首页选择「首次解构新方案」。"
        />
        <p className="protocol-redo-placeholder__back">
          <RouteLink to="/protocols" className="button button--primary">
            返回方案工作台首页
          </RouteLink>
        </p>
      </div>
    );
  }

  if (mode === "first" && jobId === null) {
    return (
      <ProtocolUploadPanel
        busy={uploadBusy}
        error={uploadError}
        onUpload={handleUpload}
        onInvalidFile={setUploadError}
      />
    );
  }

  if (jobId !== null) {
    return <ProtocolJobFlow jobId={jobId} componentParam={params.get("component")} />;
  }

  return <ProtocolWorkbenchHome />;
}

export default ProtocolsPage;
