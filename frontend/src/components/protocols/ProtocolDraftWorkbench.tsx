/**
 * 草稿审阅三区：规则树 / 编辑区 / 来源定位。
 * 1080P至4K桌面三列联动，共享 component URL 选择状态。
 */

import { useEffect, useMemo, useState } from "react";
import type { DraftRevisionView, IntegrityView, ProtocolSessionView, SourcesView } from "../../api/protocolWorkbenchTypes";
import { updateParams } from "../../app/router";
import { mapProtocolDraftRules, mapProtocolSourceLocators } from "../../domain/protocolMappers";
import type { RuleComponentId } from "../../domain/ids";
import { ProtocolDeconstructionRuleTree } from "./ProtocolDeconstructionRuleTree";
import { ProtocolDraftEditPane } from "./ProtocolDraftEditPane";
import { ProtocolDraftSourcePane } from "./ProtocolDraftSourcePane";
import { RouteLink } from "../../app/router";

type DraftTab = "tree" | "edit" | "source";

interface ProtocolDraftWorkbenchProps {
  session: ProtocolSessionView;
  draft: DraftRevisionView;
  integrity: IntegrityView;
  sources: SourcesView;
  componentParam: string | null;
  onSaveDraft: () => void;
  saving: boolean;
  saveError?: string;
  /** 界面试用：示例草稿保存状态（仅 stub 演示任务注入） */
  uatDraftSaved?: boolean;
  onUatReset?: () => void;
}

export function ProtocolDraftWorkbench({
  session,
  draft,
  integrity,
  sources,
  componentParam,
  onSaveDraft,
  saving,
  saveError,
  uatDraftSaved,
  onUatReset,
}: ProtocolDraftWorkbenchProps) {
  const draftSaved = uatDraftSaved === true;
  const rules = useMemo(() => mapProtocolDraftRules(draft.content), [draft.content]);
  const allComponents = useMemo(
    () => rules.flatMap((rule) => rule.components),
    [rules],
  );

  const selectedComponent = useMemo(() => {
    if (componentParam !== null) {
      return allComponents.find((c) => c.componentId === componentParam) ?? null;
    }
    return allComponents[0] ?? null;
  }, [allComponents, componentParam]);

  const [tab, setTab] = useState<DraftTab>("tree");

  useEffect(() => {
    if (selectedComponent !== null && componentParam === null) {
      updateParams({ component: selectedComponent.componentId });
    }
  }, [selectedComponent, componentParam]);

  const selectComponent = (componentId: RuleComponentId) => {
    updateParams({ component: componentId });
  };

  const locators = useMemo(() => {
    if (selectedComponent === null) return [];
    return mapProtocolSourceLocators(sources.sourceSpans, selectedComponent.sourceRefs);
  }, [selectedComponent, sources.sourceSpans]);

  const revisionLabel = `草稿第 ${draft.revisionNumber} 稿 · ${draft.statusLabel}`;

  const tabs: ReadonlyArray<{ id: DraftTab; label: string }> = [
    { id: "tree", label: "规则树" },
    { id: "edit", label: "编辑" },
    { id: "source", label: "来源定位" },
  ];

  return (
    <div className="protocol-draft-workbench">
      <header className="page-head">
        <h1 className="page-head__title">审阅解构草稿</h1>
        <p className="page-head__note">
          {session.protocolCode ?? draft.protocolCode} · {session.selectedPhaseLabel ?? draft.studyPhaseLabel} ·{" "}
          {revisionLabel}。{integrity.summary}
        </p>
      </header>

      <section className="protocol-draft-meta" aria-label="草稿摘要">
        <div className="protocol-draft-meta__item">
          <span className="protocol-draft-meta__label">规则条目</span>
          <strong>{draft.ruleCount}</strong>
        </div>
        <div className="protocol-draft-meta__item">
          <span className="protocol-draft-meta__label">流程节点</span>
          <strong>{draft.workflowStageCount}</strong>
        </div>
        <div className="protocol-draft-meta__item">
          <span className="protocol-draft-meta__label">完整性检查</span>
          <strong>{integrity.publishable ? "已通过" : "待修正"}</strong>
        </div>
        <div className="protocol-draft-meta__actions">
          <button
            type="button"
            className="button button--primary"
            disabled={saving || draftSaved}
            onClick={onSaveDraft}
          >
            {saving ? "正在保存…" : draftSaved ? "已保存草稿" : "保存草稿"}
          </button>
          {onUatReset !== undefined && (
            <button type="button" className="button button--quiet" onClick={onUatReset}>
              恢复试用初始状态
            </button>
          )}
          <RouteLink to="/protocols" className="button button--quiet">
            返回首页
          </RouteLink>
        </div>
        {draftSaved && (
          <p className="protocol-draft-actions__status" role="status">
            已保存草稿；尚未发布，当前正式规则版本没有被覆盖。
          </p>
        )}
        {saveError !== undefined && saveError.length > 0 && (
          <p className="protocol-draft-actions__error" role="alert">
            {saveError}
          </p>
        )}
      </section>

      <div className="protocol-draft-tabs" role="tablist" aria-label="草稿工作区切换">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`protocol-draft-tab-${item.id}`}
            aria-selected={tab === item.id}
            aria-controls={`protocol-draft-panel-${item.id}`}
            className={`protocol-draft-tabs__tab${tab === item.id ? " protocol-draft-tabs__tab--active" : ""}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="protocol-draft-panes">
        <div
          id="protocol-draft-panel-tree"
          role="tabpanel"
          aria-labelledby="protocol-draft-tab-tree"
          className={`protocol-draft-col protocol-draft-col--tree${tab === "tree" ? " protocol-draft-col--visible" : ""}`}
        >
          <div className="protocol-draft-pane">
            <header className="protocol-draft-pane__head">
              <h2 className="protocol-draft-pane__title">规则树</h2>
              <span className="protocol-draft-pane__subtitle">{revisionLabel}</span>
            </header>
            <ProtocolDeconstructionRuleTree
              rules={rules}
              selectedComponentId={selectedComponent?.componentId ?? null}
              onSelectComponent={selectComponent}
            />
          </div>
        </div>

        <div
          id="protocol-draft-panel-edit"
          role="tabpanel"
          aria-labelledby="protocol-draft-tab-edit"
          className={`protocol-draft-col protocol-draft-col--edit${tab === "edit" ? " protocol-draft-col--visible" : ""}`}
        >
          <div className="protocol-draft-pane">
            <ProtocolDraftEditPane
              component={selectedComponent}
              revisionLabel={revisionLabel}
              issues={integrity.issues}
            />
          </div>
        </div>

        <div
          id="protocol-draft-panel-source"
          role="tabpanel"
          aria-labelledby="protocol-draft-tab-source"
          className={`protocol-draft-col protocol-draft-col--source${tab === "source" ? " protocol-draft-col--visible" : ""}`}
        >
          <div className="protocol-draft-pane">
            <ProtocolDraftSourcePane
              component={selectedComponent}
              locators={locators}
              fileName={session.fileName}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
