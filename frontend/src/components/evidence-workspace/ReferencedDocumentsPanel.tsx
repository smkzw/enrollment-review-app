import { useState } from "react";
import {
  clinicalLocatorPrecisionLabel,
  isReviewableLocator,
  conflictDifferenceRows,
  type EvidenceSnapshotMemberView,
  type LocatorView,
  type ReferencedDocumentListView,
  type ReferencedDocumentView,
  EvidenceApiError,
} from "../../api/evidence";

export interface ReferencedDocumentDraft {
  description: string;
  documentType: string;
  sourceParty: string;
  reason: string;
}

export interface ReferencedDocumentsPanelProps {
  data: ReferencedDocumentListView | null;
  currentMembers: EvidenceSnapshotMemberView[];
  locators: LocatorView[];
  conflict: EvidenceApiError | null;
  onCreate: (
    draft: ReferencedDocumentDraft,
    triggerLocatorId: string | null,
  ) => Promise<void>;
  onRevise: (
    item: ReferencedDocumentView,
    draft: ReferencedDocumentDraft,
  ) => Promise<void>;
  onConfirm: (
    item: ReferencedDocumentView,
    triggerLocatorId: string,
    reason: string,
  ) => Promise<void>;
  onDismiss: (item: ReferencedDocumentView, reason: string) => Promise<void>;
  onResolve: (
    item: ReferencedDocumentView,
    sourceDocumentVersionId: string,
  ) => Promise<void>;
  onUnresolve: (item: ReferencedDocumentView) => Promise<void>;
}

function defaultDraft(item?: ReferencedDocumentView): ReferencedDocumentDraft {
  return {
    description: item?.description ?? "",
    documentType: item?.documentType ?? "",
    sourceParty: item?.sourceParty ?? "",
    reason: "",
  };
}

function ConflictNotice({ error }: { error: EvidenceApiError }) {
  const rows = conflictDifferenceRows(error.conflictContext);
  return (
    <section
      className="evidence-conflict-notice"
      role="alert"
      aria-label="被提及资料已发生变化"
    >
      <h4>{error.title}</h4>
      <p>{error.message}</p>
      {rows.length > 0 && (
        <table className="evidence-conflict-notice__table">
          <caption>本次输入与系统当前记录的差异</caption>
          <thead>
            <tr>
              <th scope="col">项目</th>
              <th scope="col">本次输入</th>
              <th scope="col">系统当前记录</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.field}>
                <th scope="row">{row.field}</th>
                <td>{row.submitted}</td>
                <td>{row.current}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p>{error.recoveryAction}</p>
      <p className="evidence-conflict-notice__keep">当前输入和选择均已保留。</p>
    </section>
  );
}

function LocatorSelect({
  label,
  value,
  onChange,
  locators,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  locators: LocatorView[];
}) {
  const reviewableLocators = locators.filter(isReviewableLocator);
  return (
    <label>
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={reviewableLocators.length === 0}
      >
        <option value="">
          {reviewableLocators.length === 0 ? "当前没有真实定位" : "请选择页内定位"}
        </option>
        {reviewableLocators.map((locator) => (
          <option key={locator.locatorId} value={locator.locatorId}>
            第 {locator.pageNumber} 页 · {clinicalLocatorPrecisionLabel(locator.precision)}
            {locator.excerpt === null ? "" : ` · ${locator.excerpt}`}
          </option>
        ))}
      </select>
    </label>
  );
}

export function ReferencedDocumentsPanel({
  data,
  currentMembers,
  locators,
  conflict,
  onCreate,
  onRevise,
  onConfirm,
  onDismiss,
  onResolve,
  onUnresolve,
}: ReferencedDocumentsPanelProps) {
  const [createDraft, setCreateDraft] = useState<ReferencedDocumentDraft>(() =>
    defaultDraft(),
  );
  const [createLocatorId, setCreateLocatorId] = useState("");
  const [drafts, setDrafts] = useState<Record<string, ReferencedDocumentDraft>>(
    {},
  );
  const [locatorChoices, setLocatorChoices] = useState<Record<string, string>>(
    {},
  );
  const [busy, setBusy] = useState<string | null>(null);

  const items = data?.items ?? [];

  function draftFor(item: ReferencedDocumentView): ReferencedDocumentDraft {
    return drafts[item.referencedDocumentId] ?? defaultDraft(item);
  }

  function updateDraft(
    item: ReferencedDocumentView,
    patch: Partial<ReferencedDocumentDraft>,
  ) {
    setDrafts((current) => ({
      ...current,
      [item.referencedDocumentId]: { ...draftFor(item), ...patch },
    }));
  }

  async function run(
    key: string,
    action: () => Promise<void>,
    clear?: () => void,
  ) {
    if (busy !== null) return;
    setBusy(key);
    try {
      await action();
      clear?.();
    } catch {
      // 409 时不清理草稿或选择。
    } finally {
      setBusy(null);
    }
  }

  return (
    <section
      className="evidence-referenced-panel"
      aria-label="资料中提及但未提供"
    >
      {conflict !== null && <ConflictNotice error={conflict} />}
      <div className="evidence-panel-heading">
        <div>
          <p className="evidence-kicker">资料追踪</p>
          <h4>资料中提及但未提供</h4>
        </div>
        <span className="section-count">{items.length}</span>
      </div>
      <p className="evidence-subtle">
        候选资料必须经过确认或解除；已提供资料只能关联当前有效资料版本中的成员。
      </p>

      <details className="evidence-referenced-create-shell">
        <summary>登记一项被提及资料</summary>
        <form
          className="evidence-referenced-create"
          onSubmit={(event) => {
          event.preventDefault();
          if (createDraft.description.trim().length === 0) return;
          void run(
            "create",
            () => onCreate(createDraft, createLocatorId || null),
            () => {
              setCreateDraft(defaultDraft());
              setCreateLocatorId("");
            },
          );
          }}
        >
        <label className="evidence-field evidence-field--wide">
          资料说明
          <input
            value={createDraft.description}
            onChange={(event) =>
              setCreateDraft((current) => ({
                ...current,
                description: event.target.value,
              }))
            }
            placeholder="例如：既往影像报告"
          />
        </label>
        <div className="evidence-form-grid">
          <label>
            资料类型
            <input
              value={createDraft.documentType}
              onChange={(event) =>
                setCreateDraft((current) => ({
                  ...current,
                  documentType: event.target.value,
                }))
              }
              placeholder="可选"
            />
          </label>
          <label>
            资料来源方
            <input
              value={createDraft.sourceParty}
              onChange={(event) =>
                setCreateDraft((current) => ({
                  ...current,
                  sourceParty: event.target.value,
                }))
              }
              placeholder="可选"
            />
          </label>
        </div>
        <LocatorSelect
          label="提及位置（当前页，可选）"
          value={createLocatorId}
          onChange={setCreateLocatorId}
          locators={locators}
        />
        <button
          type="submit"
          className="button"
          disabled={
            busy !== null || createDraft.description.trim().length === 0
          }
        >
          {busy === "create" ? "正在登记…" : "登记为待确认"}
        </button>
        </form>
      </details>

      {data === null ? (
        <p className="evidence-subtle">正在读取被提及资料…</p>
      ) : items.length === 0 ? (
        <p className="evidence-subtle">当前审核节点没有已登记的被提及资料。</p>
      ) : (
        <ul className="evidence-referenced-list">
          {items.map((item) => {
            const draft = draftFor(item);
            const selectedLocatorId =
              locatorChoices[item.referencedDocumentId] ??
              item.triggerLocatorId ??
              "";
            const canConfirm =
              selectedLocatorId.length > 0 && draft.reason.trim().length > 0;
            const resolution = item.resolution;
            const canResolve = currentMembers.length > 0;
            return (
              <li
                key={item.referencedDocumentId}
                className="evidence-referenced-item"
              >
                <div className="evidence-referenced-item__head">
                  <div>
                    <strong>{item.description}</strong>
                    <span className="chip">{item.statusLabel}</span>
                  </div>
                  <span className="evidence-subtle">{item.originLabel}</span>
                </div>
                {(item.documentType !== null || item.sourceParty !== null) && (
                  <p className="evidence-subtle">
                    {item.documentType ?? "未注明类型"}
                    {item.sourceParty === null
                      ? ""
                      : ` · 来源：${item.sourceParty}`}
                  </p>
                )}
                {item.reason !== null && (
                  <p className="evidence-referenced-item__reason">
                    上次说明：{item.reason}
                  </p>
                )}
                <div className="evidence-form-grid">
                  <label>
                    资料说明
                    <input
                      value={draft.description}
                      onChange={(event) =>
                        updateDraft(item, { description: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    资料类型
                    <input
                      value={draft.documentType}
                      onChange={(event) =>
                        updateDraft(item, { documentType: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    资料来源方
                    <input
                      value={draft.sourceParty}
                      onChange={(event) =>
                        updateDraft(item, { sourceParty: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    本次操作说明
                    <input
                      value={draft.reason}
                      onChange={(event) =>
                        updateDraft(item, { reason: event.target.value })
                      }
                      placeholder="确认、解除或修改的理由"
                    />
                  </label>
                </div>
                <div className="evidence-referenced-item__actions">
                  <button
                    type="button"
                    className="button"
                    disabled={busy !== null || draft.reason.trim().length === 0}
                    onClick={() =>
                      void run(`revise:${item.referencedDocumentId}`, () =>
                        onRevise(item, draft),
                      )
                    }
                  >
                    保存修改
                  </button>
                  <LocatorSelect
                    label="确认提及位置（当前页）"
                    value={selectedLocatorId}
                    onChange={(value) =>
                      setLocatorChoices((current) => ({
                        ...current,
                        [item.referencedDocumentId]: value,
                      }))
                    }
                    locators={locators}
                  />
                  <button
                    type="button"
                    className="button button--primary"
                    disabled={busy !== null || !canConfirm}
                    onClick={() =>
                      void run(`confirm:${item.referencedDocumentId}`, () =>
                        onConfirm(item, selectedLocatorId, draft.reason),
                      )
                    }
                  >
                    确认提及
                  </button>
                  <button
                    type="button"
                    className="button"
                    disabled={busy !== null || draft.reason.trim().length === 0}
                    onClick={() =>
                      void run(`dismiss:${item.referencedDocumentId}`, () =>
                        onDismiss(item, draft.reason),
                      )
                    }
                  >
                    解除候选
                  </button>
                </div>
                <div className="evidence-referenced-item__resolution">
                  <div>
                    <span className="evidence-subtle">提供状态：</span>
                    <strong>{resolution?.statusLabel ?? "未提供"}</strong>
                    {resolution?.sourceDocumentVersionId !== null &&
                      resolution?.sourceDocumentVersionId !== undefined && (
                        <span className="evidence-subtle">
                          已关联当前资料版本成员
                        </span>
                      )}
                  </div>
                  <label>
                    关联当前有效资料
                    <select
                      value={resolution?.sourceDocumentVersionId ?? ""}
                      disabled={!canResolve || busy !== null}
                      onChange={(event) => {
                        const value = event.target.value;
                        if (value.length === 0) return;
                        void run(`resolve:${item.referencedDocumentId}`, () =>
                          onResolve(item, value),
                        );
                      }}
                    >
                      <option value="">
                        {canResolve
                          ? "请选择当前资料版本成员"
                          : "当前没有可关联的活动资料"}
                      </option>
                      {currentMembers.map((member) => (
                        <option
                          key={member.sourceDocumentVersionId}
                          value={member.sourceDocumentVersionId}
                        >
                          {member.fileName} · 第 {member.versionNumber} 版
                        </option>
                      ))}
                    </select>
                  </label>
                  {resolution?.status === "provided" && (
                    <button
                      type="button"
                      className="button"
                      disabled={busy !== null}
                      onClick={() =>
                        void run(`unresolve:${item.referencedDocumentId}`, () =>
                          onUnresolve(item),
                        )
                      }
                    >
                      解除资料关联
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
