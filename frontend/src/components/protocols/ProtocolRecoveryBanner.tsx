/**
 * 任务恢复横幅：提示检查点与下一步操作。
 */

import type { ProtocolSessionView } from "../../api/protocolWorkbenchTypes";

const RECOVERY_STEP_LABELS: Readonly<Record<string, string>> = {
  register_file: "登记文件",
  extract_structure: "提取结构",
  render_and_align: "渲染并对齐",
  identify_identity_phase: "识别身份与期别",
  await_identity_confirm: "等待身份确认",
  generate_draft: "生成草稿",
  integrity_check: "完整性检查",
  await_review: "等待审阅",
  publish: "发布",
};

function recoveryStepLabel(stepId: string | null): string {
  if (stepId === null) return "未知";
  return RECOVERY_STEP_LABELS[stepId] ?? "后台处理";
}

interface ProtocolRecoveryBannerProps {
  session: ProtocolSessionView;
  onContinue: () => void;
}

export function ProtocolRecoveryBanner({ session, onContinue }: ProtocolRecoveryBannerProps) {
  const stepLabel = recoveryStepLabel(session.recoveryStepId);
  return (
    <section className="protocol-recovery" aria-labelledby="protocol-recovery-banner-title">
      <h2 id="protocol-recovery-banner-title" className="protocol-recovery__title">
        可从中断处继续
      </h2>
      <p className="protocol-recovery__detail">
        任务 {session.jobId} 在步骤「{stepLabel}」处暂停。
        {session.fileName !== null && <> 已登记文件：{session.fileName}。</>}
      </p>
      <p className="protocol-recovery__action-text">{session.nextAction}</p>
      <button type="button" className="button button--primary" onClick={onContinue}>
        继续任务
      </button>
    </section>
  );
}
