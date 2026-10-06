import { useEffect, useRef, useState } from "react";
import { Eye, RefreshCw } from "lucide-react";
import { RouteLink } from "../../app/router";
import { getFactNormalizationRepository } from "../../api/fact-normalization";
import type { NormalizationUnresolvedPageView } from "../../api/fact-normalization/factNormalizationViewModels";

interface Props { subjectId: string; episodeId: string; jobId: string }

export function NormalizationUnresolvedPanel({ subjectId, episodeId, jobId }: Props) {
  return <ScopedNormalizationUnresolvedPanel key={`${subjectId}:${episodeId}:${jobId}`}
    subjectId={subjectId} episodeId={episodeId} jobId={jobId} />;
}

function ScopedNormalizationUnresolvedPanel({ subjectId, episodeId, jobId }: Props) {
  const [data, setData] = useState<NormalizationUnresolvedPageView | null>(null);
  const [offset, setOffset] = useState(0);
  const [retry, setRetry] = useState(0);
  const [busy, setBusy] = useState(true);
  const [failed, setFailed] = useState(false);
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

  return <section className="normalization-unresolved" aria-label="尚未整理清楚的资料">
    <h3>尚未整理清楚的资料{data ? `（${data.total}项）` : ""}</h3>
    {busy && <p role="status">正在读取…</p>}
    {failed && <p role="alert">暂时无法读取待核对内容。<button className="button" type="button"
      onClick={() => { setData(null); contentSha256.current = undefined; setOffset(0);
        setRetry((value) => value + 1); }}><RefreshCw size={16} />重新读取</button></p>}
    {data && <>
      {!data.isCurrent && <p>这是历史资料版本，不能代替当前审核结果。</p>}
      {!data.textAccountingApplied && <p>这次记录未逐段检查是否漏项。</p>}
      <p>这些记录不代表患者缺少检查，也不能证明图片、手写和每项临床含义已核清。</p>
      {data.total === 0 && <p>暂无待核对记录。入排结论仍以审核结果为准。</p>}
      <ul>{data.items.map((item) => <li key={item.itemId}>
        <div><span>{item.kind === "unquoted_text" ? "尚未整理的文字" : "读取时留下的疑问"}</span>
          <strong>{item.message}</strong><p>{item.reason}</p></div>
        <div className="normalization-unresolved__sources">{item.sources.map((source) => <RouteLink
          key={source.pageArtifactId} to={`/subjects/${encodeURIComponent(subjectId)}/evidence`}
          params={{ episode: episodeId, ocrSnapshot: data.evidenceSnapshotId,
            ocrRevision: data.processingRevisionId, sourcePage: source.pageArtifactId }}
          className="button" title={`${source.fileName} · 第${source.pageNumber}页`}>
          <Eye size={16} />{source.fileName} · 第{source.pageNumber}页
        </RouteLink>)}</div>
      </li>)}</ul>
      {data.hasMore && <button type="button" className="button" disabled={busy}
        onClick={() => setOffset(data.items.length)}>加载更多</button>}
    </>}
  </section>;
}
