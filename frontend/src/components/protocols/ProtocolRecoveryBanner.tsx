/**
 * 任务恢复横幅：提示检查点与下一步操作（自然中文，不展示内部编号）。
 */

import type { ProtocolSessionView } from "../../api/protocolWorkbenchTypes";

interface ProtocolRecoveryBannerProps {
  session: ProtocolSessionView;
  onContinue: () => void;
}

export function ProtocolRecoveryBanner({ session, onContinue }: ProtocolRecoveryBannerProps) {
  return (
    <section className="protocol-recovery" aria-labelledby="protocol-recovery-banner-title">
      <h2 id="protocol-recovery-banner-title" className="protocol-recovery__title">
        可从中断处继续
      </h2>
      <p className="protocol-recovery__detail">
        {session.fileName !== null && <>已登记文件：{session.fileName}。</>}
        当前状态：{session.stateLabel}。
      </p>
      <p className="protocol-recovery__action-text">{session.nextAction}</p>
      <button type="button" className="button button--primary" onClick={onContinue}>
        继续任务
      </button>
    </section>
  );
}
