/**
 * 发布成功结果页（重新解构 / 首次解构共用）。
 * 展示生成的新不可变规则版本；历史版本保留用于追溯。
 */

import { RouteLink } from "../../app/router";
import type { PublishResultView, ProtocolSessionView } from "../../api/protocolWorkbenchTypes";
import { CheckIcon, HistoryIcon } from "../shell/icons";

interface ProtocolPublishResultProps {
  session: ProtocolSessionView;
  result: PublishResultView;
}

export function ProtocolPublishResult({
  session,
  result,
}: ProtocolPublishResultProps) {
  const isRedo = session.sessionKind === "re_deconstruction";
  return (
    <div className="protocol-publish-result">
      <header className="page-head">
        <h1 className="page-head__title">
          <CheckIcon size={18} />
          发布完成
        </h1>
        <p className="page-head__note">
          {isRedo
            ? `已在目标项目 ${session.targetProjectName ?? ""} 下生成新的不可变规则版本。`
            : "已发布新的正式项目与规则版本。"}
        </p>
      </header>

      <section className="protocol-publish-result__card" aria-labelledby="protocol-publish-result-title">
        <h2 id="protocol-publish-result-title" className="protocol-publish-result__title">
          新规则版本
        </h2>
        <dl className="protocol-publish-result__fields">
          <div>
            <dt>规则版本号</dt>
            <dd>第 {result.ruleSetRevision} 版</dd>
          </div>
          {isRedo && (
            <div>
              <dt>目标项目</dt>
              <dd>{session.targetProjectName ?? result.projectId}</dd>
            </div>
          )}
          <div>
            <dt>方案编号</dt>
            <dd>{session.targetProtocolCode ?? session.protocolCode ?? "—"}</dd>
          </div>
          <div>
            <dt>研究期别</dt>
            <dd>{session.targetStudyPhaseLabel ?? session.selectedPhaseLabel ?? "—"}</dd>
          </div>
        </dl>
        <p className="protocol-publish-result__note">
          已发布的历史版本完整保留用于追溯；后续如需更新规则，请从「重新解构已有项目」继续上传新版方案。
        </p>
      </section>

      <div className="protocol-publish-result__actions">
        <RouteLink to="/protocols" className="button button--primary">
          返回方案工作台
        </RouteLink>
        <RouteLink
          to="/subjects"
          params={{ project: result.projectId }}
          className="button"
          ariaLabel="前往受试者与资料"
        >
          前往受试者与资料
        </RouteLink>
        {isRedo && (
          <RouteLink
            to="/protocols"
            params={{ mode: "redo" }}
            className="button"
          >
            <HistoryIcon size={14} />
            再次重新解构
          </RouteLink>
        )}
      </div>
    </div>
  );
}
