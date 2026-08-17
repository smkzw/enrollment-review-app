/**
 * 解构任务进行中：展示文件名、临床状态、进度与下一步（不展示内部任务编号）。
 */

import type { ProtocolSessionView } from "../../api/protocolWorkbenchTypes";
import { RouteLink } from "../../app/router";

interface ProtocolJobProgressProps {
  session: ProtocolSessionView;
  onRefresh: () => void;
}

export function ProtocolJobProgress({ session, onRefresh }: ProtocolJobProgressProps) {
  const progressPercent =
    session.progressTotal > 0
      ? Math.round((session.progressCompleted / session.progressTotal) * 100)
      : 0;

  return (
    <div className="protocol-job-progress">
      <header className="page-head">
        <h1 className="page-head__title">方案解构进行中</h1>
        <p className="page-head__note">
          {session.fileName !== null ? (
            <>
              已登记文件：<strong>{session.fileName}</strong>
            </>
          ) : (
            "正在登记方案文件…"
          )}
        </p>
      </header>

      <section className="protocol-job-progress__panel" aria-labelledby="protocol-job-progress-title">
        <h2 id="protocol-job-progress-title" className="protocol-job-progress__state">
          {session.stateLabel}
        </h2>
        <div
          className="protocol-job-progress__bar"
          role="progressbar"
          aria-valuenow={session.progressCompleted}
          aria-valuemin={0}
          aria-valuemax={session.progressTotal}
          aria-label={`解构进度 ${session.progressCompleted} / ${session.progressTotal}`}
        >
          <div
            className="protocol-job-progress__bar-fill"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <p className="protocol-job-progress__counts">
          已完成 {session.progressCompleted} / {session.progressTotal} 项准备步骤
        </p>
        <p className="protocol-job-progress__next">{session.nextAction}</p>
        <div className="protocol-job-progress__actions">
          <button type="button" className="button button--primary" onClick={onRefresh}>
            刷新状态
          </button>
          <RouteLink to="/protocols" className="button button--quiet">
            返回首页
          </RouteLink>
        </div>
      </section>
    </div>
  );
}
