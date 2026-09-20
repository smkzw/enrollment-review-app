/**
 * 重新解构并列差异工作台：当前正式版本与新草稿三栏并列。
 * 中间栏按官方父规则编号逐条展示八类结构化差异（新增/删除/原文/逻辑/时间窗/
 * 例外/证据要求/应完成阶段）；保存/取消不改变正式版本，发布在同一项目追加新的不可变规则版本。
 */

import { useMemo, useState, type ReactNode } from "react";
import { RouteLink } from "../../app/router";
import type {
  DraftComparisonView,
  IntegrityView,
  ProtocolSessionView,
  SourcesView,
} from "../../api/protocolWorkbenchTypes";
import {
  DIFF_CATEGORY_LABELS,
  mapProtocolDraftDiff,
} from "../../domain/protocolDiffMapper";
import type {
  DiffCategoryKey,
  ProtocolDraftDiffView,
  ProtocolRuleDiffView,
} from "../../domain/protocolDiffViewModels";
import {
  mapProtocolDraftRules,
  mapProtocolSourceLocators,
} from "../../domain/protocolMappers";
import { EmptyState } from "../shell/Feedback";
import { ProtocolFileIcon } from "../shell/icons";
import { ProtocolRedoDiffPane } from "./ProtocolRedoDiffPane";
import { ProtocolRedoRuleColumn } from "./ProtocolRedoRuleColumn";

interface ProtocolComparisonWorkbenchProps {
  session: ProtocolSessionView;
  comparison: DraftComparisonView;
  integrity: IntegrityView;
  sources: SourcesView;
  saving: boolean;
  feedbackBusy: boolean;
  onSaveDraft: () => void;
  onOpenFeedback: () => void;
  onOpenManualEdit: () => void;
  onCancel: () => void;
  onPublish: () => void;
  publicationBlocked?: boolean;
  supplementaryRequirements?: ReactNode;
  actionError?: string;
}

export function ProtocolComparisonWorkbench({
  session,
  comparison,
  integrity,
  sources,
  saving,
  feedbackBusy,
  onSaveDraft,
  onOpenFeedback,
  onOpenManualEdit,
  onCancel,
  onPublish,
  publicationBlocked = false,
  supplementaryRequirements,
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
  const [categoryFilter, setCategoryFilter] = useState<DiffCategoryKey | "all">("all");
  const [selectedRuleCode, setSelectedRuleCode] = useState(
    () => diff.modifiedRuleCodes[0] ?? diff.addedRuleCodes[0] ?? diff.removedRuleCodes[0] ?? candidateRules[0]?.officialCode ?? "",
  );

  const visibleRules: ProtocolRuleDiffView[] = useMemo(() => {
    return diff.ruleDiffs.filter((rule) => {
      if (filter === "changed" && !rule.hasChanges) return false;
      if (categoryFilter === "all") return true;
      if (categoryFilter === "added") {
        return rule.added || rule.addedComponentRefs.length > 0;
      }
      if (categoryFilter === "removed") {
        return rule.removed || rule.removedComponentRefs.length > 0;
      }
      return rule.changes.some((change) => change.category === categoryFilter);
    });
  }, [categoryFilter, diff.ruleDiffs, filter]);

  const totalChanges = diff.ruleDiffs.reduce(
    (sum, rule) => sum + rule.changes.length,
    0,
  );
  const changedRules = diff.ruleDiffs.filter((rule) => rule.hasChanges).length;
  const selectedCandidateRule = candidateRules.find(
    (rule) => rule.officialCode === selectedRuleCode,
  );
  const selectedSources = useMemo(
    () => mapProtocolSourceLocators(
      sources.sourceSpans,
      selectedCandidateRule?.sourceRefs ?? [],
    ),
    [selectedCandidateRule, sources.sourceSpans],
  );
  const categoryOptions: ReadonlyArray<DiffCategoryKey | "all"> = [
    "all",
    "added",
    "removed",
    "original_text",
    "logic",
    "time_window",
    "exception",
    "evidence",
    "due_stage",
  ];

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
          <span className="protocol-comparison__meta-label">规则变化</span>
          <strong>
            {changedRules} 条入排标准 · {totalChanges} 处变化
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
            disabled={feedbackBusy || saving || !integrity.publishable || publicationBlocked}
            onClick={onPublish}
            title={integrity.publishable ? "发布为新的正式规则版本" : "请先处理完整性检查中的问题"}
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

      {supplementaryRequirements}
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
        <div className="protocol-comparison__category-filters" aria-label="按变化内容筛选">
          {categoryOptions.map((category) => (
            <button
              key={category}
              type="button"
              className={`protocol-comparison__filter${categoryFilter === category ? " protocol-comparison__filter--active" : ""}`}
              aria-pressed={categoryFilter === category}
              onClick={() => setCategoryFilter(category)}
            >
              {category === "all" ? "全部变化" : DIFF_CATEGORY_LABELS[category]}
            </button>
          ))}
        </div>
      </section>

      <section className="protocol-comparison__review-strip" aria-label="发布检查与方案依据">
        <div className={`protocol-comparison__integrity${integrity.publishable ? " protocol-comparison__integrity--ready" : " protocol-comparison__integrity--blocked"}`}>
          <strong>{integrity.publishable && !publicationBlocked ? "可以发布" : "暂不能发布"}</strong>
          <span>{integrity.summary}</span>
          {!integrity.publishable && integrity.issues.length > 0 && (
            <ul>
              {integrity.issues.slice(0, 3).map((issue) => (
                <li key={`${issue.issueCode}-${issue.problem}`}>
                  {issue.problem}；{issue.nextAction}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="protocol-comparison__source-summary">
          <strong>{selectedRuleCode || "尚未选择规则"} 的方案依据</strong>
          {selectedSources.length === 0 ? (
            <span>当前所选规则没有可展示的原文定位，请在发布前核对来源完整性。</span>
          ) : (
            <ul>
              {selectedSources.slice(0, 3).map((source) => (
                <li key={source.sourceSpanId}>
                  <span>{source.pageLabel ?? "方案结构位置"} · {source.precisionLabel}</span>
                  <q>{source.excerpt}</q>
                </li>
              ))}
            </ul>
          )}
        </div>
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
              selectedRuleCode={selectedRuleCode}
              onSelectRule={setSelectedRuleCode}
            />
          </div>
          <div className="protocol-comparison__col protocol-comparison__col--diff">
            {visibleRules.length === 0 ? (
              <EmptyState
                message="所选范围内没有差异"
                hint="切换到「全部规则」可查看其他入排标准。"
              />
            ) : (
              <ol className="protocol-redo-diff-list">
                {visibleRules.map((rule) => (
                  <ProtocolRedoDiffPane
                    key={rule.officialCode}
                    rule={rule}
                    selected={selectedRuleCode === rule.officialCode}
                    onSelect={() => setSelectedRuleCode(rule.officialCode)}
                  />
                ))}
              </ol>
            )}
          </div>
          <div className="protocol-comparison__col protocol-comparison__col--candidate">
            <ProtocolRedoRuleColumn
              title="新草稿"
              subtitle={comparison.candidate.officialVersion ?? "—"}
              rules={candidateRules}
              selectedRuleCode={selectedRuleCode}
              onSelectRule={setSelectedRuleCode}
            />
          </div>
        </div>
      )}
    </div>
  );
}
