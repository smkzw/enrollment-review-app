/** 已完成方案任务的正式版本摘要；历史任务直链不再误显示为中断恢复。 */

import type {
  DraftRevisionView,
  ProtocolSessionView,
} from "../../api/protocolWorkbenchTypes";
import { RouteLink } from "../../app/router";
import { CheckIcon, HistoryIcon } from "../shell/icons";
import { ProtocolReviewScope } from "./ProtocolReviewScope";

interface ProtocolPublishedSummaryProps {
  session: ProtocolSessionView;
  draft: DraftRevisionView;
}

function publishedProjectId(draft: DraftRevisionView): string | null {
  const value = draft.content.project_id;
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

export function ProtocolPublishedSummary({
  session,
  draft,
}: ProtocolPublishedSummaryProps) {
  const projectId = publishedProjectId(draft);

  return (
    <div className="protocol-publish-result">
      <header className="page-head">
        <h1 className="page-head__title">
          <CheckIcon size={18} />
          {session.verificationOnly ? "验证用规则包已发布" : "方案已发布"}
        </h1>
        {session.verificationOnly && <p className="page-head__note">
          规则包未经医学经理本人审定，仅供构建验证，不能用于正式审核。
        </p>}
      </header>

      <section
        className="protocol-publish-result__card"
        aria-labelledby="protocol-published-summary-title"
      >
        <h2 id="protocol-published-summary-title" className="protocol-publish-result__title">
          {session.verificationOnly ? "本次验证内容" : "本次发布内容"}
        </h2>
        <dl className="protocol-publish-result__fields">
          <div>
            <dt>方案编号</dt>
            <dd>{session.protocolCode ?? draft.protocolCode ?? "—"}</dd>
          </div>
          <div>
            <dt>研究期别</dt>
            <dd>{session.selectedPhaseLabel ?? draft.studyPhaseLabel}</dd>
          </div>
          <div>
            <dt>方案版本</dt>
            <dd>{session.officialVersion ?? draft.officialVersion ?? "—"}</dd>
          </div>
          <div>
            <dt>入排标准</dt>
            <dd>{draft.ruleCount} 条</dd>
          </div>
        </dl>
      </section>

      <ProtocolReviewScope key={draft.revisionId} jobId={session.jobId} revisionId={draft.revisionId} />

      <div className="protocol-publish-result__actions">
        <RouteLink to="/protocols" className="button button--primary">
          返回方案工作台
        </RouteLink>
        {projectId !== null && (
          <RouteLink
            to="/subjects"
            params={{ project: projectId }}
            className="button"
            ariaLabel="前往受试者与资料"
          >
            前往受试者与资料
          </RouteLink>
        )}
        {projectId !== null && (
          <RouteLink
            to="/protocols"
            params={{ mode: "redo", project: projectId }}
            className="button"
          >
            <HistoryIcon size={14} />
            重新解构此项目
          </RouteLink>
        )}
      </div>
    </div>
  );
}
