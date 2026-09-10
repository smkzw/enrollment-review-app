/**
 * 人工事实修订历史：默认作为可展开区，不干扰 Patient Profile 首屏重点。
 * 每条记录的 profileRevisionId 指向该次修订生成后的不可变 Patient Profile：
 * 标题、定位摘录、页码与原文入口都从该版本解析；定位 id 跨版本不可变，
 * 绝不回退到“当前/最新”档案，也绝不把同一 locator id 解析成另一页或摘录。
 */

import { useEffect, useMemo, useState } from "react";
import type {
  FactCorrectionHistoryView,
  FactCorrectionRecordView,
  ProfileItemView,
} from "../../api/patient-profile";
import {
  getPatientProfileRepository,
  PatientProfileApiError,
} from "../../api/patient-profile";
import {
  adaptPatientProfile,
  type PatientProfileModel,
} from "../../features/patient-profile/model";
import { UI_PHRASES } from "../../domain/labels";
import {
  CorrectionImpactSummary,
  CorrectionSnapshotPanel,
  correctionHistoryTime,
  correctionOperatorLabel,
} from "./factCorrectionDisplay";

export type ProfileCorrectionHistoryState =
  | { status: "loading" }
  | { status: "success"; data: FactCorrectionHistoryView }
  | { status: "error"; message: string };

export interface ProfileCorrectionHistoryProps {
  state: ProfileCorrectionHistoryState;
  subjectId: string;
  onOpenEvidence?: (item: ProfileItemView, model: PatientProfileModel) => void;
}

type HistoricalModelsState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; models: ReadonlyMap<string, PatientProfileModel> }
  | { status: "error"; message: string };

function profileErrorMessage(error: unknown): string {
  if (error instanceof PatientProfileApiError) {
    return error.recoveryAction.length > 0
      ? `${error.message} ${error.recoveryAction}`
      : error.message;
  }
  return UI_PHRASES.temporarilyUnavailable;
}

function distinctRevisionIds(items: readonly FactCorrectionRecordView[]): string[] {
  const seen = new Set<string>();
  const ids: string[] = [];
  for (const record of items) {
    if (seen.has(record.profileRevisionId)) continue;
    seen.add(record.profileRevisionId);
    ids.push(record.profileRevisionId);
  }
  return ids;
}

/** 按修订记录上的 profileRevisionId（修订生成的档案）精确加载；缺失即失败，不回退最新版。 */
function useHistoricalProfileModels(
  subjectId: string,
  revisionIds: readonly string[],
  enabled: boolean,
): HistoricalModelsState {
  const key = revisionIds.join("\0");
  const [state, setState] = useState<HistoricalModelsState>({ status: "idle" });

  useEffect(() => {
    if (!enabled) {
      setState({ status: "idle" });
      return;
    }
    const ids = key.length === 0 ? [] : key.split("\0");
    if (ids.length === 0) {
      setState({ status: "success", models: new Map() });
      return;
    }
    const controller = new AbortController();
    let cancelled = false;
    setState({ status: "loading" });
    Promise.all(
      ids.map(async (revisionId) => {
        const revision = await getPatientProfileRepository().getPatientProfileRevision(
          subjectId,
          revisionId,
          { signal: controller.signal },
        );
        return [revisionId, adaptPatientProfile(revision)] as const;
      }),
    ).then(
      (entries) => {
        if (cancelled) return;
        setState({ status: "success", models: new Map(entries) });
      },
      (error: unknown) => {
        if (cancelled) return;
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState({ status: "error", message: profileErrorMessage(error) });
      },
    );
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [subjectId, key, enabled]);

  return state;
}

function sourceLines(
  record: FactCorrectionRecordView,
  model: PatientProfileModel,
): Array<{ id: string; text: string; item: ProfileItemView | null }> {
  const item =
    model.itemById.get(record.newEntityId) ??
    model.items.find((candidate) => candidate.sourceId === record.newEntityId) ??
    null;
  return record.locatorIds.map((locatorId) => {
    const locator = model.locatorById.get(locatorId);
    if (locator === undefined) {
      return { id: locatorId, text: "原文定位已保留，该历史档案未返回其页内详情。", item };
    }
    const excerpt = locator.excerpt === null ? "未提供页内摘录" : `“${locator.excerpt}”`;
    return {
      id: locatorId,
      text: `第 ${locator.pageNumber} 页 · ${locator.precisionLabel} · ${excerpt}`,
      item,
    };
  });
}

function CorrectionHistoryEntry({
  record,
  model,
  onOpenEvidence,
}: {
  record: FactCorrectionRecordView;
  model: PatientProfileModel;
  onOpenEvidence?: (item: ProfileItemView, model: PatientProfileModel) => void;
}) {
  const item =
    model.itemById.get(record.newEntityId) ??
    model.items.find((candidate) => candidate.sourceId === record.newEntityId);
  const source = sourceLines(record, model);
  return (
    <article className="profile-correction-history__entry">
      <header className="profile-correction-history__entry-head">
        <div>
          <h4>{item?.title ?? record.targetKindLabel}</h4>
          <p>
            {correctionHistoryTime(record.correctedAt)} · {correctionOperatorLabel(record.operatorId)}
          </p>
        </div>
        <span className="count-chip">已追加记录</span>
      </header>
      <dl className="profile-correction-history__meta">
        <div>
          <dt>修订理由</dt>
          <dd>{record.reason}</dd>
        </div>
        <div>
          <dt>来源</dt>
          <dd>
            <ul className="profile-correction-history__sources">
              {source.map((line) => (
                <li key={line.id}>
                  <span>{line.text}</span>
                  {line.item !== null && onOpenEvidence !== undefined && (
                    <button
                      type="button"
                      className="chip"
                      onClick={() => {
                        const sourceItem = line.item;
                        if (sourceItem !== null) onOpenEvidence(sourceItem, model);
                      }}
                    >
                      查看原文
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </dd>
        </div>
        <div>
          <dt>影响范围</dt>
          <dd>
            <p className="profile-correction-history__scope-label">
              {record.impact.scopeKindLabel}
            </p>
            {record.impact.fallbackReason !== null && (
              <p>{record.impact.fallbackReason}</p>
            )}
            <CorrectionImpactSummary impact={record.impact} />
          </dd>
        </div>
        <div>
          <dt>档案版本</dt>
          <dd>本次修订形成档案第 {record.profileRevision} 版。</dd>
        </div>
      </dl>
      <div className="profile-correction-history__comparison">
        <CorrectionSnapshotPanel
          label="修改前"
          snapshot={record.oldSnapshot}
          targetKind={record.targetKind}
          item={item ?? undefined}
        />
        <CorrectionSnapshotPanel
          label="修改后"
          snapshot={record.newSnapshot}
          targetKind={record.targetKind}
          item={item ?? undefined}
        />
      </div>
    </article>
  );
}

export function ProfileCorrectionHistory({
  state,
  subjectId,
  onOpenEvidence,
}: ProfileCorrectionHistoryProps) {
  const revisionIds = useMemo(
    () =>
      state.status === "success" ? distinctRevisionIds(state.data.items) : [],
    [state],
  );
  const historical = useHistoricalProfileModels(
    subjectId,
    revisionIds,
    state.status === "success",
  );

  if (state.status === "loading") {
    return <p className="profile-correction-history__muted">正在读取修订记录。</p>;
  }
  if (state.status === "error") {
    return (
      <p className="profile-correction-history__error" role="alert">
        {state.message}
      </p>
    );
  }
  if (state.data.items.length === 0) {
    return <p className="profile-correction-history__muted">当前审核节点还没有人工事实修订记录。</p>;
  }
  if (historical.status === "loading" || historical.status === "idle") {
    return <p className="profile-correction-history__muted">正在读取本次修订生成的档案版本。</p>;
  }
  if (historical.status === "error") {
    return (
      <p className="profile-correction-history__error" role="alert">
        {historical.message}
      </p>
    );
  }

  return (
    <div className="profile-correction-history__list">
      {state.data.items.map((record) => {
        const model = historical.models.get(record.profileRevisionId);
        if (model === undefined) {
          return (
            <p
              key={record.correctionId}
              className="profile-correction-history__error"
              role="alert"
            >
              未能载入本次修订生成的档案版本，已拒绝使用当前档案回退显示。
            </p>
          );
        }
        return (
          <CorrectionHistoryEntry
            key={record.correctionId}
            record={record}
            model={model}
            onOpenEvidence={onOpenEvidence}
          />
        );
      })}
    </div>
  );
}
