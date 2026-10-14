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
          {result.verificationOnly ? "验证用规则包已发布" : "发布完成"}
        </h1>
        <p className="page-head__note">
          {result.verificationOnly ? "规则包未经医学经理本人审定，仅供构建验证，不能用于正式审核。" : isRedo
            ? `规则第 ${result.ruleSetRevision} 版已保存，旧版保留。`
            : `已发布新项目及规则第 ${result.ruleSetRevision} 版。`}
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
              <dd>{session.targetProjectCode ?? "项目代号未填写"}</dd>
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
        {isRedo && session.targetProjectName && <details>
          <summary>研究完整名称</summary>
          <p>{session.targetProjectName}</p>
        </details>}
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
            params={{ mode: "redo", project: result.projectId }}
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
