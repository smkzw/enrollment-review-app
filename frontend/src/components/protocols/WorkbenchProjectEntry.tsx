/**
 * 共享工作台来源入口（显式命名空间 `workbench:<shared_project_id>`）。
 *
 * 边界（与 WORKBENCH_ADAPTATION_20261007 的最小接入合同一致）：
 * - 来源只是元数据，不是本产品方案身份；本入口不创建项目，也不代替上传、
 *   方案信息核对与联合发布——这些仍沿现有正式流程执行。
 * - 已绑定的任务/正式项目由服务端按持久身份解析（任务 payload），
 *   localStorage 只保留既有“最近任务”便利，不作为来源映射的权威来源。
 * - 未绑定来源只展示真实 DOCX 上传入口，并如实说明尚未开始，不展示历史项目。
 * - 返回上下文只接受本产品内相对路由；绝对 returnUrl 一律丢弃，避免任意跳转。
 */

import { useEffect, useRef, useState } from "react";
import { RouteLink } from "../../app/router";
import { isProtocolWorkbenchStubMode } from "../../api/protocolApiConfig";
import { fetchWorkbenchProjectEntry } from "../../api/protocolWorkbenchHttp";
import { ProtocolWorkbenchApiError } from "../../api/protocolWorkbenchRepository";
import type { WorkbenchProjectEntryView } from "../../api/protocolWorkbenchTypes";
import { ProtocolUploadPanel } from "./ProtocolUploadPanel";

const INVALID_RETURN_MESSAGE =
  "返回位置暂不可用，请从当前项目继续。";

/**
 * 约束返回上下文：只接受本产品内的相对路由（`/today`、`/protocols?job=…`）。
 * 绝对 URL、协议相对地址（`//host`）、反斜杠、控制字符、`.`/`..` 段一律拒绝，
 * 避免把任意 returnUrl 变成跳转目标。
 */
export function sanitizeReturnRoute(raw: string | null): string | null {
  if (raw === null) return null;
  const value = raw.trim();
  if (value.length === 0) return null;
  if (!value.startsWith("/")) return null;
  if (value.startsWith("//") || value.startsWith("/\\")) return null;
  if (value.includes("\\") || value.includes(":")) return null;
  // eslint-disable-next-line no-control-regex
  if (/[\u0000-\u001f\u007f]/.test(value)) return null;
  if (value.split("/").some((segment) => segment === "." || segment === "..")) {
    return null;
  }
  return value;
}

export function isReturnRouteRejected(raw: string | null): boolean {
  return raw !== null && raw.trim().length > 0 && sanitizeReturnRoute(raw) === null;
}

type EntryResolution =
  | { kind: "loading" }
  | { kind: "ready"; entry: WorkbenchProjectEntryView }
  | { kind: "failed"; message: string };

interface WorkbenchProjectEntryProps {
  origin: string;
  /** 已约束的返回路由（非本产品相对路由时为 null）。 */
  returnRoute: string | null;
  returnRejected?: boolean;
  busy: boolean;
  error: string | null;
  onUpload: (file: File) => void;
  onInvalidFile?: (message: string) => void;
  /** 测试注入点；默认走真实 HTTP 来源查询。 */
  resolveEntry?: (origin: string) => Promise<WorkbenchProjectEntryView>;
}

function describeFailure(cause: unknown): string {
  if (cause instanceof ProtocolWorkbenchApiError) {
    return `${cause.message} ${cause.recoveryAction}`;
  }
  return "共享工作台来源暂时无法核对，请稍后重试。";
}

export function WorkbenchProjectEntry({
  origin,
  returnRoute,
  returnRejected = false,
  busy,
  error,
  onUpload,
  onInvalidFile,
  resolveEntry,
}: WorkbenchProjectEntryProps) {
  const [resolution, setResolution] = useState<EntryResolution>({
    kind: "loading",
  });
  const resolverRef = useRef(resolveEntry);
  resolverRef.current = resolveEntry;

  useEffect(() => {
    let cancelled = false;
    setResolution({ kind: "loading" });
    if (isProtocolWorkbenchStubMode()) {
      setResolution({
        kind: "failed",
        message:
          "当前为界面试用构建，未连接共享工作台来源查询；请在正式构建中从医学经理工作台进入。",
      });
      return () => {
        cancelled = true;
      };
    }
    const resolver =
      resolverRef.current ??
      ((value: string) => fetchWorkbenchProjectEntry(value));
    resolver(origin)
      .then((entry) => {
        if (entry.origin !== origin) throw new Error("项目关联与入口不一致");
        if (!cancelled) setResolution({ kind: "ready", entry });
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setResolution({ kind: "failed", message: describeFailure(cause) });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [origin]);

  const contextParams = {
    workbench_origin: origin,
    ...(returnRoute !== null ? { return: returnRoute } : {}),
  };

  const returnLink =
    returnRoute !== null ? (
      <p className="protocol-upload__back">
        <RouteLink to={returnRoute} className="button button--quiet">
          返回上一级
        </RouteLink>
      </p>
    ) : null;
  const returnNotice = returnRejected ? (
    <div className="feedback feedback--error" role="alert">
      <p className="feedback__title">{INVALID_RETURN_MESSAGE}</p>
    </div>
  ) : null;

  if (resolution.kind === "loading") {
    return (
      <div className="protocol-upload">
        <header className="page-head">
          <h1 className="page-head__title">正在打开项目</h1>
          <p className="page-head__note">
            正在核对项目及方案处理进度…
          </p>
        </header>
        {returnNotice}
        {returnLink}
      </div>
    );
  }

  if (resolution.kind === "failed") {
    return (
      <div className="protocol-upload">
        <header className="page-head">
          <h1 className="page-head__title">暂时无法打开项目</h1>
          <p className="page-head__note">
            项目关联尚无法核对，请稍后重试。已有方案和处理记录不会被替换。
          </p>
        </header>
        <div className="feedback feedback--error" role="alert">
          <p className="feedback__title">{resolution.message}</p>
        </div>
        {returnNotice}
        {returnLink}
        <p className="protocol-upload__back">
          <RouteLink to="/protocols" className="button button--quiet">
            返回方案工作台首页
          </RouteLink>
        </p>
      </div>
    );
  }

  const { entry } = resolution;

  if (entry.entryState === "unbound") {
    return (
      <div className="protocol-upload">
        <div className="feedback" role="note">
          <p className="feedback__title">该项目尚未上传研究方案</p>
          <p>
            请上传正式 DOCX 方案，随后核对方案信息及审核要求。
          </p>
        </div>
        {returnNotice}
        <ProtocolUploadPanel
          busy={busy}
          error={error}
          onUpload={onUpload}
          onInvalidFile={onInvalidFile}
        />
        {returnLink}
      </div>
    );
  }

  if (entry.entryState === "job_in_progress" && entry.job !== null) {
    const job = entry.job;
    const stopped = job.state === "failed_final" || job.state === "cancelled";
    return (
      <div className="protocol-upload">
        <header className="page-head">
          <h1 className="page-head__title">方案处理记录</h1>
          <p className="page-head__note">
            {stopped ? "上次处理已结束，记录仍保留。可查看原因后重新上传。" : entry.project !== null
              ? "新版方案正在处理或待核对，已发布版本仍保留。"
              : "从已保存的进度查看方案，无需重复上传。"}
          </p>
        </header>
        {returnNotice}
        <section className="protocol-home-card protocol-workbench-entry" aria-labelledby="workbench-entry-job-title">
          <h2 id="workbench-entry-job-title" className="protocol-home-card__title">
            {job.fileName ?? "研究方案"}
          </h2>
          <ul className="protocol-home-card__steps">
            <li>当前状态：{job.stateLabel ?? "待核对"}</li>
            {job.awaitingUserLabel !== null && (
              <li>待处理：{job.awaitingUserLabel}</li>
            )}
            {job.fileName !== null && <li>方案文件：{job.fileName}</li>}
          </ul>
          <RouteLink
            to="/protocols"
            params={{ job: job.jobId, ...contextParams }}
            className="button button--primary"
          >
            查看处理进度
          </RouteLink>
        </section>
        {entry.project !== null && <p>
          已发布方案：{entry.project.projectName} · {entry.project.officialVersion}
          <RouteLink to="/board" params={{ project: entry.project.projectId, ...contextParams }}
            className="button button--quiet">查看项目与受试者</RouteLink>
          {stopped && <RouteLink to="/protocols" params={{ mode: "redo",
            project: entry.project.projectId, ...contextParams }}
            className="button button--primary">上传新版方案</RouteLink>}
        </p>}
        {stopped && entry.project === null && <ProtocolUploadPanel busy={busy} error={error}
          onUpload={onUpload} onInvalidFile={onInvalidFile} />}
        {returnLink}
      </div>
    );
  }

  if (entry.entryState === "project_published" && entry.project !== null) {
    const project = entry.project;
    return (
      <div className="protocol-upload">
        <header className="page-head">
          <h1 className="page-head__title">项目方案</h1>
          <p className="page-head__note">
            以下为已核对并发布的方案版本。
          </p>
        </header>
        {returnNotice}
        <section className="protocol-home-card protocol-workbench-entry" aria-labelledby="workbench-entry-project-title">
          <h2 id="workbench-entry-project-title" className="protocol-home-card__title">
            {project.projectName}（{project.projectCode}）
          </h2>
          <ul className="protocol-home-card__steps">
            <li>
              方案：{project.protocolCode} · {project.officialVersion}
            </li>
            <li>研究期别：{project.studyPhaseLabel}</li>
            <li>当前正式规则版本：{project.ruleSetRevision}</li>
          </ul>
          <RouteLink
            to="/board"
            params={{ project: project.projectId, ...contextParams }}
            className="button button--primary"
          >
            查看项目与受试者
          </RouteLink>
          <RouteLink
            to="/protocols"
            params={{
              mode: "redo",
              project: project.projectId,
              ...contextParams,
            }}
            className="button button--quiet"
          >
            上传新版方案
          </RouteLink>
        </section>
        {returnLink}
      </div>
    );
  }

  return (
    <div className="protocol-upload">
      <header className="page-head">
        <h1 className="page-head__title">共享工作台 · 来源状态不完整</h1>
        <p className="page-head__note">
          服务返回的来源状态缺少对应任务或项目，已停止推断；请返回方案工作台首页继续。
        </p>
      </header>
      {returnNotice}
      {returnLink}
      <p className="protocol-upload__back">
        <RouteLink to="/protocols" className="button button--quiet">
          返回方案工作台首页
        </RouteLink>
      </p>
    </div>
  );
}
