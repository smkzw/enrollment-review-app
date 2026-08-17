/**
 * 重新解构并列差异工作台：当前正式版本与新草稿三栏并列。
 * 中间栏按官方父规则编号逐条展示八类结构化差异（新增/删除/原文/逻辑/时间窗/
 * 例外/证据要求/应完成阶段）；保存/取消不改变正式版本，发布在同一项目追加新的不可变规则版本。
 */

import { useMemo, useState } from "react";
import { RouteLink } from "../../app/router";
import type {
  DraftComparisonView,
  ProtocolSessionView,
} from "../../api/protocolWorkbenchTypes";
import { mapProtocolDraftDiff } from "../../domain/protocolDiffMapper";
import type {
  ProtocolDraftDiffView,
  ProtocolRuleDiffView,
} from "../../domain/protocolDiffViewModels";
import { mapProtocolDraftRules } from "../../domain/protocolMappers";
import { EmptyState } from "../shell/Feedback";
import { ProtocolFileIcon } from "../shell/icons";
import { ProtocolRedoDiffPane } from "./ProtocolRedoDiffPane";
import { ProtocolRedoRuleColumn } from "./ProtocolRedoRuleColumn";

interface ProtocolComparisonWorkbenchProps {
  session: ProtocolSessionView;
  comparison: DraftComparisonView;
  saving: boolean;
  feedbackBusy: boolean;
  onSaveDraft: () => void;
  onOpenFeedback: () => void;
  onOpenManualEdit: () => void;
  onCancel: () => void;
  onPublish: () => void;
  actionError?: string;
}

export function ProtocolComparisonWorkbench({
  session,
  comparison,
  saving,
  feedbackBusy,
  onSaveDraft,
  onOpenFeedback,
  onOpenManualEdit,
  onCancel,
  onPublish,
  actionError,
}: ProtocolComparisonWorkbenchProps) {
  const baselineRules = useMemo(
    () => mapProtocolDraftRules(comparison.baseline.content),
    [comparison.baseline.content],
  );
  const candidateRules = useMemo(
    () => mapProtocolDraftRules(comparison.candidate.content),
    [comparison.candidate.content],
  );
  const diff: ProtocolDraftDiffView = useMemo(
    () => mapProtocolDraftDiff(comparison.diff),
    [comparison.diff],
  );

  const [filter, setFilter] = useState<"all" | "changed">("changed");

  const visibleRules: ProtocolRuleDiffView[] = useMemo(() => {
    if (filter === "all") return diff.ruleDiffs;
    return diff.ruleDiffs.filter((rule) => rule.hasChanges);
  }, [diff.ruleDiffs, filter]);

  const totalChanges = diff.ruleDiffs.reduce(
    (sum, rule) => sum + rule.changes.length,
    0,
  );
  const changedRules = diff.ruleDiffs.filter((rule) => rule.hasChanges).length;

  return (
    <div className="protocol-comparison">
      <header className="page-head">
        <h1 className="page-head__title">
          <ProtocolFileIcon size={18} />
          重新解构：并列比较差异
        </h1>
        <p className="page-head__note">
          {session.targetProjectName}（{session.targetProjectCode}）· {session.targetProtocolCode} ·{" "}
          {session.targetStudyPhaseLabel}
          ，当前正式版本 {session.targetOfficialVersion}，新草稿版本 {comparison.candidate.officialVersion ?? "—"}。
          逐条核对差异后再保存或发布。
        </p>
      </header>

      <section className="protocol-comparison__meta" aria-label="重新解构摘要">
        <div className="protocol-comparison__meta-item">
          <span className="protocol-comparison__meta-label">目标正式项目</span>
          <strong>{session.targetProjectName ?? "—"}</strong>
        </div>
        <div className="protocol-comparison__meta-item">
          <span className="protocol-comparison__meta-label">当前正式版本</span>
          <strong>{comparison.baseline.officialVersion ?? session.targetOfficialVersion ?? "—"}</strong>
          <small>{comparison.baseline.ruleCount} 条规则</small>
        </div>
        <div className="protocol-comparison__meta-item">
          <span className="protocol-comparison__meta-label">新草稿版本</span>
          <strong>{comparison.candidate.officialVersion ?? "—"}</strong>
          <small>{comparison.candidate.ruleCount} 条规则</small>
        </div>
        <div className="protocol-comparison__meta-item">
          <span className="protocol-comparison__meta-label">八类差异</span>
          <strong>
            {changedRules} 条父规则 · {totalChanges} 处变化
          </strong>
          <small>{comparison.sourceBound ? "差异已绑定方案原文定位" : "部分差异缺少来源定位"}</small>
        </div>
        <div className="protocol-comparison__meta-actions">
          <button
            type="button"
            className="button"
            disabled={saving || feedbackBusy}
            onClick={onSaveDraft}
          >
            {saving ? "正在保存…" : "保存草稿"}
          </button>
          <button
            type="button"
            className="button"
            disabled={feedbackBusy || saving}
            onClick={onOpenFeedback}
          >
            基于反馈修订
          </button>
          <button
            type="button"
            className="button"
            disabled={feedbackBusy || saving}
            onClick={onOpenManualEdit}
          >
            手工修订
          </button>
          <button
            type="button"
            className="button button--quiet"
            disabled={feedbackBusy || saving}
            onClick={onCancel}
          >
            取消
          </button>
          <button
            type="button"
            className="button button--primary"
            disabled={feedbackBusy || saving}
            onClick={onPublish}
          >
            发布
          </button>
          <RouteLink to="/protocols" className="button button--quiet">
            返回首页
          </RouteLink>
        </div>
      </section>
      {actionError !== undefined && actionError.length > 0 && (
        <p className="protocol-draft-actions__error" role="alert">
          {actionError}
        </p>
      )}

      <section className="protocol-comparison__toolbar" aria-label="差异范围筛选">
        <div className="protocol-comparison__filters">
          <button
            type="button"
            className={`protocol-comparison__filter${filter === "changed" ? " protocol-comparison__filter--active" : ""}`}
            aria-pressed={filter === "changed"}
            onClick={() => setFilter("changed")}
          >
            仅显示有变化的规则（{changedRules}）
          </button>
          <button
            type="button"
            className={`protocol-comparison__filter${filter === "all" ? " protocol-comparison__filter--active" : ""}`}
            aria-pressed={filter === "all"}
            onClick={() => setFilter("all")}
          >
            全部规则（{diff.ruleDiffs.length}）
          </button>
        </div>
        <p className="protocol-comparison__legend">
          左侧：当前正式版本；中间：八类结构化差异；右侧：新草稿。颜色标记为新增/删除/修改。
        </p>
      </section>

      {diff.ruleDiffs.length === 0 ? (
        <EmptyState
          message="当前没有可比对的规则差异"
          hint="请确认新草稿已生成后再比较；若新版本内容与当前正式版本一致，则无需重新发布。"
        />
      ) : (
        <div className="protocol-comparison__columns">
          <div className="protocol-comparison__col protocol-comparison__col--baseline">
            <ProtocolRedoRuleColumn
              title="当前正式版本"
              subtitle={comparison.baseline.officialVersion ?? "—"}
              rules={baselineRules}
            />
          </div>
          <div className="protocol-comparison__col protocol-comparison__col--diff">
            {visibleRules.length === 0 ? (
              <EmptyState
                message="所选范围内没有差异"
                hint="切换到「全部规则」可查看其他父规则。"
              />
            ) : (
              <ol className="protocol-redo-diff-list">
                {visibleRules.map((rule) => (
                  <ProtocolRedoDiffPane key={rule.officialCode} rule={rule} />
                ))}
              </ol>
            )}
          </div>
          <div className="protocol-comparison__col protocol-comparison__col--candidate">
            <ProtocolRedoRuleColumn
              title="新草稿"
              subtitle={comparison.candidate.officialVersion ?? "—"}
              rules={candidateRules}
            />
          </div>
        </div>
      )}
    </div>
  );
}


