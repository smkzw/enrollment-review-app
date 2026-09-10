import { useEffect, useState } from "react";
import { createPageReviewHttp } from "../../api/page-review/pageReviewHttp";
import { getReviewConflicts, startTargetedReview } from "../../api/page-review/targetedReviewHttp";
import { useLoad } from "../../app/useLoad";
import { RouteLink } from "../../app/router";
import { ErrorState, LoadingState } from "../shell/Feedback";
import { TargetedReviewDetail } from "./TargetedReviewDetail";

export function PageReviewTaskDetail({ subjectId, episodeId, jobId }: { subjectId: string; episodeId: string; jobId: string }) {
  const detail = useLoad(async (signal) => ({
    status: await createPageReviewHttp().status(subjectId, episodeId, jobId, signal),
    conflicts: await getReviewConflicts(subjectId, episodeId, jobId, signal),
  }), [subjectId, episodeId, jobId]);
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [auxiliaryId, setAuxiliaryId] = useState<string | null>(null);
  useEffect(() => {
    if (detail.state.status !== "success" || detail.state.data.status.reviewStatus !== "processing") return;
    const timer = window.setTimeout(detail.retry, 2500);
    return () => window.clearTimeout(timer);
  }, [detail.state, detail.retry]);
  async function open(pageIndex: number) {
    if (opening) return;
    setOpening(true); setError(null);
    try { setAuxiliaryId(await startTargetedReview(subjectId, episodeId, jobId, pageIndex)); }
    catch { setError("复核暂未开始，请稍后重试。原有识别结果和资料保留。"); }
    finally { setOpening(false); }
  }
  if (auxiliaryId !== null) return <>
    <button className="button" onClick={() => setAuxiliaryId(null)}>返回页面识别概况</button>
    <TargetedReviewDetail key={auxiliaryId} subjectId={subjectId} episodeId={episodeId} jobId={auxiliaryId} />
  </>;
  if (detail.state.status === "loading") return <LoadingState />;
  if (detail.state.status === "error") return <ErrorState message="暂时无法读取资料识别记录。" onRetry={detail.retry} />;
  const { status, conflicts } = detail.state.data;
  return <section className="tasks-section">
    <h2>资料页识别</h2>
    <p>已读完 {status.acceptedPages + status.unrelatedPages} / {status.totalPages} 页 · 尚未读完 {status.pendingPages} 页 · 读取失败 {status.failedPages} 页</p>
    <h3>原件内容分歧</h3>
    {conflicts.length === 0 ? <p>{status.reviewStatus === "processing" ? "资料仍在识别中。"
      : status.reviewStatus !== "ready" ? "资料识别尚未完成，暂不能据此确认两次识别是否一致。"
      : "本次未发现需再次核对的数值、日期或手写内容。其他待核实事项仍保留。"}</p>
      : <ul className="persistent-task__files">{conflicts.map((item) => <li key={item.pageIndex}>
        <div><strong>{item.fileName} · 第 {item.pageNumber} 页</strong><span>{item.fieldCount} 项识别结果不同</span></div>
        <button className="button" disabled={opening} onClick={() => void open(item.pageIndex)}>复核原件</button>
      </li>)}</ul>}
    {error && <p role="alert">{error}</p>}
    <RouteLink to={`/subjects/${subjectId}/evidence`} params={{ episode: episodeId }} className="button button--quiet">返回该受试者资料</RouteLink>
  </section>;
}
