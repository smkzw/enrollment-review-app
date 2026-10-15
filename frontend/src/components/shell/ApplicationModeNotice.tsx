import { useApplicationMode } from "../../app/applicationMode";

export function ApplicationModeNotice() {
  const { canModify } = useApplicationMode();
  if (canModify) return null;
  return (
    <div className="feedback application-mode-notice" role="status">
      <span>仅查看已保存的审核报告及其原件。本次不会上传、修改资料或开始新的审核。</span>
    </div>
  );
}
