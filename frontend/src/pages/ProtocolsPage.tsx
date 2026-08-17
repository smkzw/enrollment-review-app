/**
 * 方案工作台（Phase 3 Slice 6）：首次解构 / 重新解构分流与草稿审阅主路径。
 * 重新解构：选择目标正式项目 → 上传新版方案 → 并列比较八类差异 → 保存/取消/发布。
 */

import { useCallback, useState } from "react";
import {
  getProtocolWorkbenchRepository,
  ProtocolWorkbenchApiError,
} from "../api/protocolWorkbenchRepository";
import { navigate, useHashRoute } from "../app/router";
import { ProtocolWorkbenchHome } from "../components/protocols/ProtocolWorkbenchHome";
import { ProtocolUploadPanel } from "../components/protocols/ProtocolUploadPanel";
import { ProtocolRedoSelectPanel } from "../components/protocols/ProtocolRedoSelectPanel";
import { ProtocolJobFlow } from "../components/protocols/ProtocolJobFlow";

export function ProtocolsPage() {
  const { params } = useHashRoute();
  const mode = params.get("mode");
  const jobId = params.get("job");

  const repo = getProtocolWorkbenchRepository();
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const handleUpload = useCallback(
    async (file: File, projectId: string | null = null) => {
      setUploadBusy(true);
      setUploadError(null);
      try {
        const result = await repo.startDeconstruction(file, `upload-${Date.now()}`, {
          projectId: projectId ?? undefined,
        });
        navigate("/protocols", { job: result.jobId });
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
    [repo],
  );

  const handleFirstUpload = useCallback(
    (file: File) => handleUpload(file, null),
    [handleUpload],
  );
  const handleRedoUpload = useCallback(
    (file: File, projectId: string) => handleUpload(file, projectId),
    [handleUpload],
  );

  if (mode === null && jobId === null) {
    return <ProtocolWorkbenchHome />;
  }

  if (mode === "redo" && jobId === null) {
    return (
      <ProtocolRedoSelectPanel
        busy={uploadBusy}
        error={uploadError}
        onUpload={handleRedoUpload}
      />
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

  if (jobId !== null) {
    return <ProtocolJobFlow jobId={jobId} componentParam={params.get("component")} />;
  }

  return <ProtocolWorkbenchHome />;
}

export default ProtocolsPage;
