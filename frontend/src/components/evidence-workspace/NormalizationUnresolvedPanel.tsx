import { useEffect, useRef, useState } from "react";
import { Eye, RefreshCw } from "lucide-react";
import { RouteLink } from "../../app/router";
import { getFactNormalizationRepository } from "../../api/fact-normalization";
import type { NormalizationUnresolvedPageView } from "../../api/fact-normalization/factNormalizationViewModels";

interface Props { subjectId: string; episodeId: string; jobId: string; onContinue?: (runId: string) => Promise<unknown>;
  onRevalidate?: (runId: string) => Promise<unknown> }

export function NormalizationUnresolvedPanel({ subjectId, episodeId, jobId, onContinue, onRevalidate }: Props) {
  return <ScopedNormalizationUnresolvedPanel key={`${subjectId}:${episodeId}:${jobId}`}
    subjectId={subjectId} episodeId={episodeId} jobId={jobId} onContinue={onContinue} onRevalidate={onRevalidate} />;
}

function ScopedNormalizationUnresolvedPanel({ subjectId, episodeId, jobId, onContinue, onRevalidate }: Props) {
  const [data, setData] = useState<NormalizationUnresolvedPageView | null>(null);
  const [offset, setOffset] = useState(0);
  const [retry, setRetry] = useState(0);
  const [busy, setBusy] = useState(true);
  const [failed, setFailed] = useState(false);
  const [continuing, setContinuing] = useState(false);
  const contentSha256 = useRef<string | undefined>(undefined);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setBusy(true); setFailed(false);
    const read = getFactNormalizationRepository().getNormalizationUnresolved;
    void (async () => {
      try {
        if (!read) throw new Error("资料核对读取暂不可用");
        const next = await read(subjectId, episodeId, jobId, offset, { signal: controller.signal,
          expectedContentSha256: offset > 0 ? contentSha256.current : undefined });
        if (!active) return;
        if (next.jobId !== jobId || next.offset !== offset) throw new Error("资料核对范围不一致");
        if (offset > 0 && contentSha256.current !== next.contentSha256)
          throw new Error("这份清单已经更新");
        contentSha256.current = next.contentSha256;
        setData((previous) => offset === 0 ? next : {
          ...next, items: [...(previous?.items ?? []), ...next.items],
        });
      } catch {
        if (active) setFailed(true);
      } finally { if (active) setBusy(false); }
    })();
    return () => { active = false; controller.abort(); };
  }, [subjectId, episodeId, jobId, offset, retry]);

  const questions = data?.items.filter((item) => item.kind === "reading_uncertainty") ?? [];
  const otherText = data?.items.filter((item) => item.kind === "unquoted_text") ?? [];
  function renderItem(item: NormalizationUnresolvedPageView["items"][number]) {
    return <li key={item.itemId}>
      <div><strong>{item.sourceExcerpt ?? item.message}</strong>
        <details className="normalization-unresolved__explanation"><summary>核对说明</summary><p>{item.reason}</p></details>
      </div>
      <div className="normalization-unresolved__sources">{item.sources.map((source) => <RouteLink
        key={source.pageArtifactId} to={`/subjects/${encodeURIComponent(subjectId)}/evidence`}
        params={{ episode: episodeId, ocrSnapshot: data!.evidenceSnapshotId,
          ocrRevision: data!.processingRevisionId, sourcePage: source.pageArtifactId }}
        className="button" title={`${source.fileName} · 第${source.pageNumber}页`}>
        <Eye size={16} />{source.fileName} · 第{source.pageNumber}页
      </RouteLink>)}</div>
    </li>;
  }

  return <section className="normalization-unresolved" aria-label="尚未整理清楚的资料">
    <h3>尚未整理清楚的资料{data ? `（${data.total}项）` : ""}</h3>
    {busy && <p role="status">正在读取…</p>}
    {failed && <p role="alert">暂时无法读取待核对内容。<button className="button" type="button"
      onClick={() => { setData(null); contentSha256.current = undefined; setOffset(0);
        setRetry((value) => value + 1); }}><RefreshCw size={16} />重新读取</button></p>}
    {data && <>
      {!data.isCurrent && <p>这是历史资料版本，不能代替当前审核结果。</p>}
      {!data.textAccountingApplied && <p>这次记录未逐段检查是否漏项。</p>}
      <p className="normalization-unresolved__caption">读取疑问不等于患者缺少检查，尚未核清的内容仍保留。</p>
      {data.isCurrent && data.runId && (data.failedPageCount ?? 0) > 0 && onContinue &&
        <button className="button" type="button" disabled={continuing} onClick={async () => {
          setContinuing(true);
          try { await onContinue(data.runId!); } finally { setContinuing(false); }
        }}><RefreshCw size={16} />{continuing ? "正在提交" : `继续整理未完成的${data.failedPageCount}页`}</button>}
      {data.total === 0 && <p>暂无待核对记录。入排结论仍以审核结果为准。</p>}
      {data.total > 0 && <details className="normalization-unresolved__other">
        <summary>查看原件读取提示</summary>
        {data.isCurrent && data.canRevalidateSaved && data.runId && onRevalidate &&
          <button className="button" type="button" disabled={continuing} onClick={async () => {
            setContinuing(true);
            try { await onRevalidate(data.revalidationSourceRunId ?? data.runId!); } finally { setContinuing(false); }
          }}><RefreshCw size={16} />{continuing ? "正在提交" : "重新核验已读记录（不重读原件）"}</button>}
        <ul>{questions.map(renderItem)}</ul>
        {otherText.length > 0 && <details className="normalization-unresolved__other">
          <summary>其他待核对文字（{data.hasMore ? "已加载" : ""}{otherText.length}项）</summary>
          <ul>{otherText.map(renderItem)}</ul>
        </details>}
        {data.hasMore && <button type="button" className="button" disabled={busy}
          onClick={() => setOffset(data.items.length)}>加载更多</button>}
      </details>}
    </>}
  </section>;
}
