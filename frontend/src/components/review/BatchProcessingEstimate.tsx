import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { readBatchProcessingEstimate, type BatchProcessingEstimate as Estimate, type BatchProcessingKind } from "../../api/batchProcessingEstimate";
import type { OcrBatchMember } from "../../api/evidence/reprocessingBatches";

function time(seconds: number): string {
  if (seconds < 60) return "不到1分钟";
  const minutes = Math.ceil(seconds / 60);
  return minutes < 60 ? `${minutes}分钟` : `${Math.floor(minutes / 60)}小时${minutes % 60 ? `${minutes % 60}分钟` : ""}`;
}
export function BatchProcessingEstimate({ projectId, kind, choices }: { projectId: string; kind: BatchProcessingKind; choices: OcrBatchMember[] }) {
  const signature = JSON.stringify([...choices].sort((a, b) => a.episodeId.localeCompare(b.episodeId)));
  const [result, setResult] = useState<{ identity: string; data?: Estimate; error?: string } | null>(null);
  const [refresh, setRefresh] = useState(0);
  const identity = JSON.stringify([projectId, kind, signature, refresh]);
  useEffect(() => {
    const controller = new AbortController();
    const members: OcrBatchMember[] = JSON.parse(signature);
    if (!members.length || members.length > 50) return;
    const timer = setTimeout(() => {
      void readBatchProcessingEstimate(projectId, kind, members, controller.signal).then(data => {
        if (!controller.signal.aborted) setResult({ identity, data });
      }).catch((cause: unknown) => {
        if (!controller.signal.aborted) setResult({ identity, error: cause instanceof Error ? cause.message : "暂时无法读取历史耗时。" });
      });
    }, 400);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [projectId, kind, signature, identity]);
  if (!choices.length || choices.length > 50) return null;
  const current = result?.identity === identity ? result : null;
  const data = current?.data;
  return <div className="prepared-review__estimate" aria-label={kind === "review" ? "批量审核耗时参考" : "批量识别耗时参考"}>
    <div className="prepared-review__actions"><p role="status">{current?.error ?? (!data ? "正在查询历史耗时…"
      : data.medianSeconds === null ? "暂无相同资料、相同处理方式的完整记录，暂不能估算耗时。"
      : data.samples < 3 ? `历史耗时参考：${time(data.medianSeconds)}（${data.samples}次记录，样本较少）。`
      : `历史耗时参考：中间一半记录为${time(data.lowerSeconds!)}至${time(data.upperSeconds!)}，中位${time(data.medianSeconds)}（${data.samples}次记录）。`)}</p>
      <button type="button" className="icon-button" title="刷新耗时参考" aria-label="刷新耗时参考" onClick={() => setRefresh(value => value + 1)}><RefreshCw size={16} /></button>
    </div>
    {data && data.samples > 0 && <p>仅参考相同资料的历史处理，当前排队与重试可能改变耗时。</p>}
    {data?.historyTruncated && <p>仅参考最近100批记录。</p>}
    <p>费用：暂无可核实的计价依据，未折算金额。</p>
  </div>;
}
