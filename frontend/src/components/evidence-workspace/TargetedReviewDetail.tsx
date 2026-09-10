import { useEffect, useState } from "react";
import { RefreshCw, ZoomIn, ZoomOut } from "lucide-react";
import { getTargetedReviewDetail } from "../../api/page-review/targetedReviewHttp";
import { useLoad } from "../../app/useLoad";
import { RouteLink } from "../../app/router";
import { ErrorState, LoadingState } from "../shell/Feedback";
import "./targeted-review.css";

export function TargetedReviewDetail({ subjectId, episodeId, jobId }: {
  subjectId: string; episodeId: string; jobId: string;
}) {
  const detail = useLoad((signal) => getTargetedReviewDetail(subjectId, episodeId, jobId, signal), [subjectId, episodeId, jobId]);
  const [round, setRound] = useState(0);
  const [zoom, setZoom] = useState(100);
  const [imageFailed, setImageFailed] = useState(false);
  useEffect(() => {
    if (detail.state.status !== "success" || !["queued", "running", "recovering", "cancel_requested", "user_resumed"].includes(detail.state.data.state)) return;
    const timer = window.setTimeout(detail.retry, 2500);
    return () => window.clearTimeout(timer);
  }, [detail.state, detail.retry]);
  if (detail.state.status === "loading") return <LoadingState />;
  if (detail.state.status === "error") return <ErrorState message="暂时无法读取复核记录，原始资料和已有记录保留。" onRetry={detail.retry} />;
  const data = detail.state.data;
  return <section className="targeted-review" aria-label="原件内容复核">
    <header className="targeted-review__head">
      <div><h2>原件内容复核</h2><p role="status">{data.label}</p></div>
      <button className="button" title="刷新复核记录" aria-label="刷新复核记录" onClick={() => { setImageFailed(false); detail.retry(); }}><RefreshCw size={18} /></button>
    </header>
    <p className="targeted-review__notice">已有复核记录：{data.rounds} / 2 轮 · 正式事实未改动</p>
    <div className="targeted-review__columns">
      <section className="targeted-review__readings" aria-label="逐轮摘录">
        <div className="targeted-review__tabs" role="group" aria-label="选择复核轮次">
          {["最初读法", "第一轮", "第二轮"].map((label, index) => <button key={label} type="button" aria-pressed={round === index} onClick={() => setRound(index)}>{label}</button>)}
        </div>
        {[1, 2].map((reader) => {
          const items = data.excerpts.filter((item) => item.round === round && item.reader === reader);
          return <section className="targeted-review__reader" key={reader}>
            <h3>{reader === 1 ? "第一份读法" : "第二份读法"}</h3>
            {items.length === 0 && <p>本轮尚无可展示的摘录。</p>}
            {items.map((item, index) => <div className="targeted-review__excerpt" key={index}>
              <h4>{item.field}</h4><p className="targeted-review__value">{item.value}</p>
              {item.context.length > 0 && <p className="targeted-review__context">{item.context.join(" · ")}</p>}
              <blockquote>{item.excerpt}</blockquote>
            </div>)}
          </section>;
        })}
      </section>
      <section className="targeted-review__source" aria-label="原始资料">
        <header><div><strong>{data.fileName}</strong><span>第 {data.pageNumber} 页</span></div>
          <div className="targeted-review__zoom">
            <button className="button" aria-label="缩小原件" title="缩小原件" disabled={zoom <= 100} onClick={() => setZoom(zoom - 25)}><ZoomOut size={18} /></button>
            <span>{zoom}%</span>
            <button className="button" aria-label="放大原件" title="放大原件" disabled={zoom >= 200} onClick={() => setZoom(zoom + 25)}><ZoomIn size={18} /></button>
          </div>
        </header>
        <div className="targeted-review__image">
          {imageFailed ? <p role="alert">原件暂时无法显示，请刷新重试；摘录不能替代原件。</p>
            : <img src={data.imageUrl} alt={`${data.fileName}，第${data.pageNumber}页原件`} style={{ width: `${zoom}%` }} onError={() => setImageFailed(true)} />}
        </div>
      </section>
    </div>
    <RouteLink to={`/subjects/${subjectId}/evidence`} params={{ episode: episodeId }} className="button button--quiet">返回该受试者资料</RouteLink>
  </section>;
}
