/**
 * 解构任务进行中：展示文件名、临床状态、进度与下一步（不展示内部任务编号）。
 * 生成期间若有已验证语义批次，附只读“有源候选预览”（不可发布、不可替代正式草稿）。
 */

import { useMemo } from "react";
import type {
  GenerationPreviewView,
  ProtocolSessionView,
} from "../../api/protocolWorkbenchTypes";
import { mapProtocolDraftRules } from "../../domain/protocolMappers";
import { RouteLink } from "../../app/router";

interface ProtocolJobProgressProps {
  session: ProtocolSessionView;
  preview: GenerationPreviewView | null;
  onRefresh: () => void;
}

function excerptText(excerpts: string[]): string {
  const joined = excerpts.filter((item) => item.length > 0).join(" … ");
  return joined.length > 240 ? `${joined.slice(0, 240)}…` : joined;
}

export function ProtocolJobProgress({ session, preview, onRefresh }: ProtocolJobProgressProps) {
  const progressPercent =
    session.progressTotal > 0
      ? Math.round((session.progressCompleted / session.progressTotal) * 100)
      : 0;

  const previewRules = useMemo(
    () => (preview !== null && preview.available ? mapProtocolDraftRules(preview.content) : []),
    [preview],
  );

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

      {preview !== null && preview.available && previewRules.length > 0 && (
        <section
          className="protocol-job-progress__preview"
          aria-labelledby="protocol-job-preview-title"
        >
          <header className="protocol-job-progress__preview-head">
            <h2 id="protocol-job-preview-title" className="protocol-job-progress__preview-title">
              有源候选预览（只读）
            </h2>
            <p className="protocol-job-progress__preview-note">
              语义批次 {preview.batchIndex}/{preview.batchTotal} · 已有候选 {previewRules.length} 条父规则
              {preview.pendingCodes.length > 0
                ? ` · 尚未生成 ${preview.pendingCodes.length} 条`
                : " · 父规则已全部生成"}
              {preview.unresolvedCount > 0 ? ` · 未决 ${preview.unresolvedCount} 项` : ""}
            </p>
            <p className="protocol-job-progress__preview-note">
              预览来自已验证批次，仅供尽早阅读；不能发布，正式判断以生成完成后的草稿审阅为准。
            </p>
          </header>
          <ul className="protocol-job-progress__preview-list">
            {previewRules.map((rule) => (
              <li key={rule.ruleId} className="protocol-job-progress__preview-rule">
                <header className="protocol-job-progress__preview-rule-head">
                  <strong>{rule.officialCode}</strong>
                  <span className="protocol-job-progress__preview-rule-kind">{rule.kindLabel}</span>
                </header>
                {rule.components.map((component) => (
                  <div
                    key={component.componentId}
                    className="protocol-job-progress__preview-component"
                  >
                    <p className="protocol-job-progress__preview-component-title">
                      {component.displayCode} · {component.title}
                    </p>
                    {component.sourceExcerpts.length > 0 && (
                      <blockquote className="protocol-job-progress__preview-excerpt">
                        {excerptText(component.sourceExcerpts)}
                      </blockquote>
                    )}
                  </div>
                ))}
              </li>
            ))}
          </ul>
          {preview.pendingCodes.length > 0 && (
            <p className="protocol-job-progress__preview-pending">
              待生成父规则：{preview.pendingCodes.join("、")}
            </p>
          )}
        </section>
      )}
    </div>
  );
}
