import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getProtocolApiBase } from "../api/protocolApiConfig";
import { ErrorState, LoadingState } from "../components/shell/Feedback";
import { isInterfaceTrialMode } from "./runtimeMode";

type ApplicationMode = "standard" | "browse_only";
const ModeContext = createContext<ApplicationMode>("standard");
export const BROWSE_ROUTES: ReadonlySet<string> = new Set(["/reports", "/help"]);

export function useApplicationMode() {
  const mode = useContext(ModeContext);
  return { mode, canModify: mode === "standard" };
}

export function ApplicationModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ApplicationMode | "loading" | "error">(
    isInterfaceTrialMode() ? "standard" : "loading",
  );
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (isInterfaceTrialMode()) return;
    const controller = new AbortController();
    setMode("loading");
    void fetch(`${getProtocolApiBase()}/api/v2/application-status`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Application status unavailable");
        const status: unknown = await response.json();
        if (status === null || typeof status !== "object" || !("mode" in status)
            || !("can_modify" in status) || !(
              (status.mode === "standard" && status.can_modify === true)
              || (status.mode === "browse_only" && status.can_modify === false)
            )) throw new Error("Application status invalid");
        if (!controller.signal.aborted) setMode(status.mode as ApplicationMode);
      })
      .catch(() => { if (!controller.signal.aborted) setMode("error"); });
    return () => controller.abort();
  }, [attempt]);

  if (mode === "loading") return <LoadingState />;
  if (mode === "error") return <ErrorState message="尚不能确认工作台的打开方式，请重新连接。"
    onRetry={() => setAttempt((value) => value + 1)} />;
  return <ModeContext.Provider value={mode}>{children}</ModeContext.Provider>;
}
