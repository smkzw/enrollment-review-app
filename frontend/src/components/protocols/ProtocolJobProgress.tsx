/**
 * 解构任务进行中：展示文件名、临床状态、进度与下一步（不展示内部任务编号）。
 * 生成及失败恢复期间保留只读内容，不可发布、不可替代正式草稿。
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

function SourceExcerpt({ excerpts }: { excerpts: string[] }) {
  const fullText = excerpts.filter((item) => item.length > 0).join(" … ");
  if (fullText.length === 0) return null;
  return (
    <div>
      <blockquote className="protocol-job-progress__preview-excerpt">
        {excerptText(excerpts)}
      </blockquote>
      {fullText.length > 240 && (
        <details>
          <summary>展开完整原文</summary>
          {excerpts.filter((item) => item.length > 0).map((excerpt, index) => (
            <blockquote key={index} className="protocol-job-progress__preview-excerpt">
              {excerpt}
            </blockquote>
          ))}
        </details>
      )}
    </div>
  );
}

export function ProtocolJobProgress({ session, preview, onRefresh }: ProtocolJobProgressProps) {
  const progressPercent =
    session.progressTotal > 0
      ? Math.round((session.progressCompleted / session.progressTotal) * 100)
      : 0;

  return (
    <div className="protocol-job-progress">
      <header className="page-head">
        <h1 className="page-head__title">{["queued", "running", "recovering"].includes(session.state)
          ? "方案解构进行中" : "方案读取记录"}</h1>
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

      <ProtocolCandidatePreview preview={preview} />
    </div>
  );
}

export function ProtocolCandidatePreview({ preview }: { preview: GenerationPreviewView | null }) {
  const previewRules = useMemo(
    () => (preview !== null && preview.available ? mapProtocolDraftRules(preview.content) : []),
    [preview],
  );
  return preview !== null && preview.available && previewRules.length > 0 ? (
        <section
          className="protocol-job-progress__preview"
          aria-labelledby="protocol-job-preview-title"
        >
          <header className="protocol-job-progress__preview-head">
            <h2 id="protocol-job-preview-title" className="protocol-job-progress__preview-title">
              已保存的方案读取内容（尚未采用）
            </h2>
            <p className="protocol-job-progress__preview-note">
              已读取 {previewRules.length} 条入选、排除标准
              {preview.pendingCodes.length > 0
                ? ` · 尚未读取 ${preview.pendingCodes.length} 条`
                : " · 条目已全部列出"}
              {preview.unresolvedCount > 0 ? ` · 未决 ${preview.unresolvedCount} 项` : ""}
            </p>
            <p className="protocol-job-progress__preview-note">
              以下内容仅供核对。条目已列出不代表含义已核清；尚不能用于受试者审核或发布。
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
                    <SourceExcerpt excerpts={component.sourceExcerpts} />
                  </div>
                ))}
                {rule.restrictedComponents.map((component) => (
                  <div key={component.componentId} className="protocol-job-progress__preview-component">
                    <p className="protocol-job-progress__preview-component-title">
                      {component.displayCode} · {component.title} · {component.limitationKind === "consumer_unavailable"
                        ? "审核方法待补齐" : "方案含义待核清"}
                    </p>
                    <SourceExcerpt excerpts={component.sourceExcerpts} />
                  </div>
                ))}
              </li>
            ))}
          </ul>
          {preview.pendingCodes.length > 0 && (
            <p className="protocol-job-progress__preview-pending">
              尚未读取的标准：{preview.pendingCodes.join("、")}
            </p>
          )}
        </section>
  ) : null;
}
