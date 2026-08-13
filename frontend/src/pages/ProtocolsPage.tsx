/**
 * 方案工作台（合同 §3.1）：当前方案版本与新版草稿的差异比较（UAT-P1-03 语义）。
 * - 明确哪一版是当前使用版本；新内容为草稿，不覆盖当前规则版本。
 * - 变化类型分为新增 / 删除 / 逻辑或时间窗变化；来源标注可回方案原文定位。
 */

import { useState } from "react";
import { getDefaultRepository } from "../api";
import { useLoad } from "../app/useLoad";
import { useSessionState } from "../app/useSessionState";
import { UAT_KEY_PROTOCOL_DRAFT_SAVED } from "../app/uatTrialState";
import { EmptyState, ErrorState, LoadingState } from "../components/shell/Feedback";
import { ProtocolSourceDialog, type ProtocolSourceLocation } from "../components/protocols/ProtocolSourceDialog";
import { CheckIcon, OpenIcon, ProtocolFileIcon, ReportFileIcon } from "../components/shell/icons";
import type { ProtocolDiffView } from "../domain/viewModels";

interface SourceRefInfo {
  /** 中文来源标注 */
  label: string;
  /** 页码（如“第 10 页”） */
  page: string | null;
}

/** 解析来源标注：protocol-v1:p10 → 当前方案第 10 页；protocol-v2-draft:p12 → 新版本草稿第 12 页 */
function parseSourceRef(ref: string): SourceRefInfo {
  const [version, pagePart] = ref.split(":");
  const page =
    pagePart === undefined || pagePart === "" ? null : `第 ${pagePart.replace(/^p/, "")} 页`;
  const label =
    version === "protocol-v1"
      ? "当前方案"
      : version === "protocol-v2-draft"
        ? "新版本草稿"
        : "方案来源";
  return { label, page };
}

type ProtocolChangeKind = "added" | "deleted" | "changed";

interface ProtocolChangeMeta {
  groupLabel: string;
  badgeLabel: string;
  description: string;
  currentSummary: string;
  draftSummary: string;
}

const CHANGE_META: Readonly<Record<ProtocolChangeKind, ProtocolChangeMeta>> = {
  added: {
    groupLabel: "新增",
    badgeLabel: "新增",
    description: "新版本草稿新增了这一条要求，当前版本尚未包含。",
    currentSummary: "当前版本未包含此条目。",
    draftSummary: "新版本草稿新增此条目。",
  },
  deleted: {
    groupLabel: "删除",
    badgeLabel: "删除",
    description: "当前版本包含这一条要求，新版本草稿将其删除。",
    currentSummary: "当前版本仍包含此条目。",
    draftSummary: "新版本草稿删除此条目。",
  },
  changed: {
    groupLabel: "逻辑或时间范围变化",
    badgeLabel: "变化",
    description: "新版本草稿调整了这一条的逻辑或时间范围。",
    currentSummary: "当前版本保留原有逻辑或时间范围。",
    draftSummary: "新版本草稿的逻辑或时间范围发生变化。",
  },
};

interface ProtocolChangeItem {
  code: string;
  kind: ProtocolChangeKind;
  meta: ProtocolChangeMeta;
  sourceLocations: ReadonlyArray<ProtocolSourceLocation>;
}

function buildSourceLocations(
  code: string,
  kind: ProtocolChangeKind,
  sourceRefs: ReadonlyArray<string>,
): ReadonlyArray<ProtocolSourceLocation> {
  return sourceRefs.map((ref, index) => {
    const source = parseSourceRef(ref);
    return {
      id: `${kind}-${code}-${index}`,
      versionLabel: source.label,
      pageLabel: source.page,
      changeCode: code,
      changeLabel: CHANGE_META[kind].groupLabel,
    };
  });
}

function buildChanges(diff: ProtocolDiffView): ReadonlyArray<ProtocolChangeItem> {
  const create = (
    kind: ProtocolChangeKind,
    code: string,
  ): ProtocolChangeItem => ({
    code,
    kind,
    meta: CHANGE_META[kind],
    sourceLocations: buildSourceLocations(
      code,
      kind,
      diff.sourceRefsByRuleCode[code] ?? [],
    ),
  });

  return [
    ...diff.addedRuleCodes.map((code) => create("added", code)),
    ...diff.deletedRuleCodes.map((code) => create("deleted", code)),
    ...diff.changedRuleCodes.map((code) => create("changed", code)),
  ];
}

export function ProtocolsPage() {
  const { state, retry } = useLoad(
    () => getDefaultRepository().getProtocolDiff(),
    [],
  );
  const [draftSaved, setDraftSaved, resetDraftSaved] = useSessionState(
    UAT_KEY_PROTOCOL_DRAFT_SAVED,
    false,
    (value) => (typeof value === "boolean" ? value : null),
  );
  const [selectedSource, setSelectedSource] = useState<ProtocolSourceLocation | null>(null);

  if (state.status === "loading") {
    return <LoadingState />;
  }
  if (state.status === "error") {
    return <ErrorState message={state.message} onRetry={retry} />;
  }

  const diff = state.data;
  const sourceRefs = diff.sourceRefs.map(parseSourceRef);
  const changes = buildChanges(diff);
  const changeGroups: ReadonlyArray<{
    kind: ProtocolChangeKind;
    label: string;
    items: ReadonlyArray<ProtocolChangeItem>;
  }> = [
    {
      kind: "added",
      label: CHANGE_META.added.groupLabel,
      items: changes.filter((change) => change.kind === "added"),
    },
    {
      kind: "deleted",
      label: CHANGE_META.deleted.groupLabel,
      items: changes.filter((change) => change.kind === "deleted"),
    },
    {
      kind: "changed",
      label: CHANGE_META.changed.groupLabel,
      items: changes.filter((change) => change.kind === "changed"),
    },
  ];

  return (
    <div className="protocols">
      <header className="page-head">
        <h1 className="page-head__title">方案工作台</h1>
        <p className="page-head__note">
          本次试用数据仅用于体验操作，不会写入正式项目资料。并列核对当前使用版本与新版本草稿的规则差异。
        </p>
      </header>

      <div className="protocol-versions">
        <section className="protocol-version protocol-version--current">
          <h2 className="protocol-version__title">
            <ProtocolFileIcon size={15} />
            当前使用版本
          </h2>
          <p className="protocol-version__name">V1.0</p>
          <p className="protocol-version__meta">
            生效日期：2026-08-01 · 当前规则版本
          </p>
          <p className="protocol-version__note">
            当前审核均以此版本为准；新版草稿尚未发布，不会覆盖现有结论。
          </p>
        </section>
        <section className="protocol-version protocol-version--draft">
          <h2 className="protocol-version__title">
            <ReportFileIcon size={15} />
            新版本草稿
          </h2>
          <p className="protocol-version__name">V2.0（草稿）</p>
          <p className="protocol-version__meta">尚未生效 · 不改变当前审核结果</p>
          <p className="protocol-version__note">
            草稿中的变化仅作比较参考；正式发布前，现有审核不受影响。
          </p>
        </section>
      </div>

      <section className="protocol-draft-actions" aria-label="草稿操作">
        <div>
          <strong>当前使用版本仍为 V1.0</strong>
          <p>保存草稿只保留新版本的比较结果，不改变当前审核所依据的版本。</p>
        </div>
        <div className="protocol-draft-actions__buttons">
          <button
            type="button"
            className="button button--primary"
            onClick={() => setDraftSaved(true)}
          >
            <CheckIcon size={15} />
            {draftSaved ? "已保存为草稿" : "保存为草稿"}
          </button>
          <button
            type="button"
            className="button button--quiet"
            onClick={() => {
              resetDraftSaved();
              setSelectedSource(null);
            }}
          >
            恢复试用初始状态
          </button>
        </div>
        {draftSaved && (
          <p className="protocol-draft-actions__status" role="status">
            已保存为草稿；新内容仍未发布，当前规则版本没有被覆盖。
          </p>
        )}
      </section>

      <section className="protocol-changes" aria-labelledby="protocol-change-title">
        <h2 id="protocol-change-title" className="protocol-section__title">
          规则差异
        </h2>
        {changes.length === 0 ? (
          <EmptyState message="当前没有可比较的方案差异。" />
        ) : (
          <div className="protocol-change-groups">
            {changeGroups.map((group) => (
              <section
                key={group.kind}
                className="protocol-change-group"
                aria-labelledby={`protocol-change-group-${group.kind}`}
              >
                <h3 id={`protocol-change-group-${group.kind}`} className="protocol-change-group__title">
                  {group.label} <span>（{group.items.length}）</span>
                </h3>
                {group.items.length === 0 ? (
                  <p className="protocol-change-group__empty">当前没有这一类变化。</p>
                ) : (
                  <ul className="protocol-change-list">
                    {group.items.map((change) => (
                      <li key={`${change.kind}-${change.code}`} className={`protocol-change protocol-change--${change.kind}`}>
                        <div className="protocol-change__head">
                          <span className="protocol-change__badge">{change.meta.badgeLabel}</span>
                          <span className="protocol-change__code">{change.code}</span>
                          <span className="protocol-change__desc">{change.meta.description}</span>
                        </div>
                        <div className="protocol-change__compare">
                          <div>
                            <span className="protocol-change__side-label">当前版本</span>
                            <p>{change.meta.currentSummary}</p>
                          </div>
                          <div>
                            <span className="protocol-change__side-label">新版本草稿</span>
                            <p>{change.meta.draftSummary}</p>
                          </div>
                        </div>
                        <div className="protocol-change__sources" aria-label={`${change.code} 的方案原文定位`}>
                          {change.sourceLocations.length === 0 ? (
                            <span className="protocol-change__no-source">暂无版本定位</span>
                          ) : (
                            change.sourceLocations.map((source) => (
                              <button
                                key={source.id}
                                type="button"
                                className="button button--quiet protocol-source-button"
                                onClick={() => setSelectedSource(source)}
                              >
                                <OpenIcon size={14} />
                                查看{source.versionLabel}{source.pageLabel ?? "原文定位"}：{change.code}
                              </button>
                            ))
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            ))}
          </div>
        )}
      </section>

      <section className="protocol-changes" aria-labelledby="protocol-source-title">
        <h2 id="protocol-source-title" className="protocol-section__title">
          方案原文位置
        </h2>
        {sourceRefs.length === 0 ? (
          <EmptyState message="当前没有方案来源标注。" />
        ) : (
          <ul className="protocol-source-list">
            {sourceRefs.map((ref, index) => (
              <li key={index} className="protocol-source">
                <span className="protocol-source__label">{ref.label}</span>
                {ref.page !== null && (
                  <span className="protocol-source__page">{ref.page}</span>
                )}
              </li>
            ))}
          </ul>
        )}
        <p className="protocol-changes__note">
          新内容仍为草稿，当前规则版本未被覆盖；本页只保存草稿，不发布新版本。
        </p>
      </section>

      {selectedSource !== null && (
        <ProtocolSourceDialog
          source={selectedSource}
          onClose={() => setSelectedSource(null)}
        />
      )}
    </div>
  );
}

export default ProtocolsPage;
