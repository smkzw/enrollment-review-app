import { useCallback, useEffect, useRef, useState } from "react";
import {
  getProtocolControlRequirements, getProtocolControlStatus, startProtocolControls, retryProtocolControls,
  type ProtocolControlStatus,
} from "../../api/protocolControlHttp";
import type { ProtocolControlRequirements } from "../../api/protocolControlView";
import { ProtocolWorkbenchApiError } from "../../api/protocolWorkbenchTypes";

type ControlState =
  | { sourceJobId: string; status: "loading" }
  | { sourceJobId: string; status: "processing" | "stopped"; job: ProtocolControlStatus }
  | { sourceJobId: string; status: "ready"; data: ProtocolControlRequirements }
  | { sourceJobId: string; status: "error"; message: string };

export function useProtocolControls(sourceJobId: string, enabled: boolean) {
  const [state, setState] = useState<ControlState>({ sourceJobId, status: "loading" });
  const [refresh, setRefresh] = useState(0);
  const activeController = useRef<AbortController | null>(null);
  const [retrying, setRetrying] = useState(false);
  const retry = useCallback(() => setRefresh((value) => value + 1), []);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    activeController.current = controller;
    setRetrying(false);
    let timer: ReturnType<typeof setTimeout> | undefined;
    setState({ sourceJobId, status: "loading" });
    function failure(error: unknown) {
      if (controller.signal.aborted) return;
      setState({ sourceJobId, status: "error", message: error instanceof ProtocolWorkbenchApiError
        ? `${error.message} ${error.recoveryAction}`
        : "暂时无法读取补充审核要求。请刷新查看，已保存的内容不会丢失。" });
    }
    async function poll(jobId: string) {
      try {
        const status = await getProtocolControlStatus(jobId, controller.signal);
        if (controller.signal.aborted) return;
        if (status.sourceJobId !== sourceJobId) throw new Error("Source job mismatch");
        if (status.status === "candidate_ready") {
          const data = await getProtocolControlRequirements(status, controller.signal);
          if (!controller.signal.aborted) setState({ sourceJobId, status: "ready", data });
        } else {
          setState({ sourceJobId, status: status.status, job: status });
          if (status.status === "processing") timer = setTimeout(() => { void poll(jobId); }, 5000);
        }
      } catch (error) { failure(error); }
    }
    // A stable command key resumes the same durable task after navigation;
    // aborting an HTTP request never cancels the server's work.
    void startProtocolControls(sourceJobId, controller.signal).then((jobId) => {
      if (!controller.signal.aborted) void poll(jobId);
    }).catch(failure);
    return () => { controller.abort(); if (timer !== undefined) clearTimeout(timer); };
  }, [sourceJobId, enabled, refresh]);
  const current: ControlState = state.sourceJobId === sourceJobId
    ? state : { sourceJobId, status: "loading" };
  const retryFailed = async () => {
    const controller = activeController.current;
    if (!controller || controller.signal.aborted || retrying || current.status !== "stopped" || current.job.state !== "failed_final") return;
    setRetrying(true);
    try {
      await retryProtocolControls(current.job.jobId, controller.signal);
      if (!controller.signal.aborted) retry();
    } catch (error) {
      if (!controller.signal.aborted) setState({ sourceJobId, status: "error", message: error instanceof ProtocolWorkbenchApiError
        ? `${error.message} ${error.recoveryAction}` : "本次未能继续整理，请刷新查看。已完成的内容仍保留。" });
    } finally {
      if (!controller.signal.aborted) setRetrying(false);
    }
  };
  return { state: current, retry, retryFailed, retrying };
}
