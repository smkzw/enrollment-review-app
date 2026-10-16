// @vitest-environment jsdom
/**
 * 个例档案整理：刷新恢复、幂等复用、失败重试文案、陈旧档案行为。
 */

import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  factNormalizationJobStorageKey,
  setFactNormalizationRepository,
  type FactNormalizationRepository,
  type FactNormalizationJobStatusView,
} from "../../api/fact-normalization";
import { ProfileNormalizationStatus } from "../../components/profile/ProfileNormalizationStatus";
import { useFactNormalizationJob } from "../../features/fact-normalization/useFactNormalizationJob";

function status(
  overrides: Partial<FactNormalizationJobStatusView> &
    Pick<FactNormalizationJobStatusView, "state" | "stateLabel" | "recoveryAction">,
): FactNormalizationJobStatusView {
  return {
    jobId: "job-normalize-1",
    cancelRequested: false,
    progressCompleted: 0,
    progressTotal: 2,
    createdAt: "2026-08-23T10:00:00Z",
    updatedAt: "2026-08-23T10:00:00Z",
    ...overrides,
  };
}

function makeRepo(options: {
  current?: FactNormalizationRepository["getCurrentFactNormalizationJob"];
  start?: FactNormalizationRepository["startFactNormalization"];
  getStatus?: FactNormalizationRepository["getFactNormalizationJobStatus"];
  retry?: FactNormalizationRepository["retryFactNormalizationJob"];
  unresolved?: FactNormalizationRepository["getNormalizationUnresolved"];
}): FactNormalizationRepository {
  return {
    kind: "http",
    getCurrentFactNormalizationJob: options.current ?? vi.fn(async () => null),
    getNormalizationUnresolved: options.unresolved,
    startFactNormalization:
      options.start ??
      (vi.fn(async () => ({
        jobId: "job-normalize-1",
        runId: "run-normalize-1",
        created: true,
        state: "queued" as const,
        stateLabel: "等待处理",
        recoveryAction: "无需操作，正在等待开始。",
      })) as FactNormalizationRepository["startFactNormalization"]),
    getFactNormalizationJobStatus:
      options.getStatus ??
      (vi.fn(async () =>
        status({
          state: "queued",
          stateLabel: "等待处理",
          recoveryAction: "无需操作，正在等待开始。",
        }),
      ) as FactNormalizationRepository["getFactNormalizationJobStatus"]),
    retryFactNormalizationJob:
      options.retry ??
      (vi.fn(async () => ({
        jobId: "job-normalize-1",
        state: "queued" as const,
        stateLabel: "等待处理",
        changed: true,
      })) as FactNormalizationRepository["retryFactNormalizationJob"]),
  };
}

function Harness({
  profileStale = false,
  onSucceeded,
  sourceRevisionId = null,
  subjectId = "subject-1",
  reviewEpisodeId = "episode-1",
}: {
  profileStale?: boolean;
  onSucceeded?: (jobId: string) => void;
  sourceRevisionId?: string | null;
  subjectId?: string;
  reviewEpisodeId?: string;
}) {
  const job = useFactNormalizationJob({
    subjectId,
    reviewEpisodeId,
    profileStale,
    sourceRevisionId,
    onSucceeded,
    pollIntervalMs: 50,
  });
  return (
    <div>
      <span>{job.restoring ? "正在恢复状态" : "已恢复状态"}</span>
      <ProfileNormalizationStatus
        state={job.state}
        onRetry={() => void job.retry()}
      />
      <button type="button" onClick={() => void job.start("idem-shared")}>
        开始整理
      </button>
      <button type="button" onClick={() => void job.start("idem-shared")}>
        再次开始
      </button>
    </div>
  );
}

describe("个例档案整理任务恢复与文案", () => {
  it.each(["failed_retryable", "failed_final", "cancelled"] as const)(
    "旧档案陈旧且当前任务%s时保留实际未完成状态及手动重建入口", async (state) => {
      const job = status({ state, stateLabel: "未完成", recoveryAction: "已有结果保留。" });
      const retry = vi.fn();
      const start = vi.fn(async () => ({ jobId: "new-job", runId: "new-run", created: true,
        state: "queued" as const, stateLabel: "等待处理", recoveryAction: "无需操作" }));
      setFactNormalizationRepository(makeRepo({ current: vi.fn(async () => job), start, retry,
        getStatus: vi.fn(async () => status({jobId: "new-job", state: "queued",
          stateLabel: "等待处理", recoveryAction: "无需操作"})) }));
      render(<Harness profileStale />);
      expect(await screen.findByLabelText("个例档案整理状态")).toHaveTextContent("个例档案整理未完成");
      expect(start).not.toHaveBeenCalled();
      await userEvent.setup().click(screen.getByRole("button", { name: "重新整理个例档案" }));
      await waitFor(() => expect(start).toHaveBeenCalledOnce());
      expect(retry).not.toHaveBeenCalled();
      expect(job.state).toBe(state);
      expect(await screen.findByLabelText("个例档案整理状态")).toHaveTextContent("个例档案整理排队中");
    });
  it.each(["queued", "running", "recovering", "cancel_requested"] as const)(
    "旧档案陈旧但当前任务%s时恢复真实进度，不提供重复启动动作", async (state) => {
      const job = status({ state, stateLabel: "正在处理", recoveryAction: "关闭页面不会中断。",
        progressCompleted: 1, progressTotal: 4 });
      const start = vi.fn();
      setFactNormalizationRepository(makeRepo({ current: vi.fn(async () => job),
        getStatus: vi.fn(async () => job), start }));
      render(<Harness profileStale />);
      const progress = await screen.findByLabelText("个例档案整理状态");
      expect(progress).toHaveTextContent(state === "queued" ? "个例档案整理排队中" : "正在整理个例档案");
      expect(progress).toHaveTextContent("已完成 1 / 4 项");
      expect(screen.queryByRole("button", { name: "重新整理个例档案" })).not.toBeInTheDocument();
      expect(start).not.toHaveBeenCalled();
    });
  it("命令尚未返回时显示准备中且合并重复点击，收到真实任务后才显示进度", async () => {
    let resolve!: (value: Awaited<ReturnType<FactNormalizationRepository["startFactNormalization"]>>) => void;
    const start = vi.fn(() => new Promise<Awaited<ReturnType<FactNormalizationRepository["startFactNormalization"]>>>(done => { resolve = done; }));
    setFactNormalizationRepository(makeRepo({ start }));
    const user = userEvent.setup();
    render(<Harness />);
    await screen.findByText("已恢复状态");
    await user.click(screen.getByRole("button", { name: "开始整理" }));
    expect(await screen.findByLabelText("准备资料整理")).toBeVisible();
    expect(screen.queryByText(/已完成.*项/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "再次开始" }));
    expect(start).toHaveBeenCalledOnce();
    await act(async () => resolve({jobId: "job-normalize-1", runId: "run-normalize-1", created: true,
      state: "queued", stateLabel: "等待处理", recoveryAction: "无需操作"}));
    expect(await screen.findByLabelText("个例档案整理状态")).toHaveTextContent("个例档案整理排队中");
    expect(screen.queryByLabelText("准备资料整理")).not.toBeInTheDocument();
  });
  it("刷新后重试已读核验仍回到原读取，不回退成新模型整理", async () => {
    const failed = status({state: "failed_final", stateLabel: "未完成", recoveryAction: "原记录保留"});
    const start = vi.fn(async () => ({jobId: "verified-new", runId: "verified-run", created: true,
      state: "queued" as const, stateLabel: "等待处理", recoveryAction: "无需操作"}));
    const retry = vi.fn();
    const unresolved = vi.fn(async () => ({jobId: failed.jobId, contentSha256: "a".repeat(64),
      runId: "failed-validation", revalidationSourceRunId: "original-reading", canRevalidateSaved: true,
      total: 0, offset: 0, hasMore: false, isCurrent: true, textAccountingApplied: true,
      evidenceSnapshotId: "snapshot", processingRevisionId: "revision", items: []}));
    setFactNormalizationRepository(makeRepo({current: vi.fn(async () => failed), start, retry, unresolved,
      getStatus: vi.fn(async () => status({jobId: "verified-new", state: "completed", stateLabel: "已完成", recoveryAction: ""}))}));
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(await screen.findByRole("button", {name: "重新整理个例档案"}));
    await waitFor(() => expect(start).toHaveBeenCalledOnce());
    expect(start).toHaveBeenCalledWith("subject-1", "episode-1", expect.objectContaining({revalidateFromRunId: "original-reading"}));
    expect(retry).not.toHaveBeenCalled();
  });

  it("重试入口失败不会自动新建完整模型读取", async () => {
    const failed = status({state: "failed_final", stateLabel: "未完成", recoveryAction: "原记录保留"});
    const start = vi.fn();
    setFactNormalizationRepository(makeRepo({current: vi.fn(async () => failed), start,
      retry: vi.fn(async () => {throw new Error("network");})}));
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(await screen.findByRole("button", {name: "重新整理个例档案"}));
    await screen.findByText("个例档案整理未完成");
    expect(start).not.toHaveBeenCalled();
  });

  it("核验问题尚未修复时保留失败，不反复提交或改作完整读取", async () => {
    const failed = status({state: "failed_final", stateLabel: "未完成", recoveryAction: "原记录保留"});
    const start = vi.fn(), retry = vi.fn();
    setFactNormalizationRepository(makeRepo({current: vi.fn(async () => failed), start, retry,
      unresolved: vi.fn(async () => ({jobId: failed.jobId, contentSha256: "a".repeat(64),
        runId: "failed-validation", revalidationSourceRunId: "original-reading", canRevalidateSaved: false,
        total: 0, offset: 0, hasMore: false, isCurrent: true, textAccountingApplied: true,
        evidenceSnapshotId: "snapshot", processingRevisionId: "revision", items: []}))}));
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(await screen.findByRole("button", {name: "重新整理个例档案"}));
    await screen.findByText("本次核验仍有未解决问题。");
    expect(start).not.toHaveBeenCalled();
    expect(retry).not.toHaveBeenCalled();
  });
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    setFactNormalizationRepository(null);
    window.localStorage.clear();
  });

  it("刷新以服务端当前任务恢复，不沿用浏览器的旧取消任务", async () => {
    window.localStorage.setItem(
      factNormalizationJobStorageKey("episode-1"),
      "old-cancelled-job",
    );
    const getStatus = vi.fn(async () =>
      status({
        state: "running",
        stateLabel: "正在处理",
        recoveryAction: "关闭页面不会中断。",
        progressCompleted: 1,
      }),
    );
    const current = vi.fn(getStatus);
    setFactNormalizationRepository(makeRepo({ current, getStatus }));

    render(<Harness />);

    await waitFor(() => {
      expect(screen.getByLabelText("个例档案整理状态")).toHaveTextContent(
        "正在整理个例档案",
      );
    });
    expect(current).toHaveBeenCalledWith("subject-1", "episode-1", expect.objectContaining({ signal: expect.any(AbortSignal) }));
    expect(getStatus).not.toHaveBeenCalledWith("old-cancelled-job");
    expect(localStorage.getItem(factNormalizationJobStorageKey("episode-1"))).toBe("job-normalize-1");
    expect(screen.getByText(/关闭页面不会中断/)).toBeInTheDocument();
  });

  it("重复启动同一幂等意图只创建一次命令", async () => {
    const start = vi.fn(async () => ({
      jobId: "job-normalize-1",
      runId: "run-normalize-1",
      created: false,
      state: "queued" as const,
      stateLabel: "等待处理",
      recoveryAction: "无需操作，正在等待开始。",
    }));
    const getStatus = vi.fn(async () =>
      status({
        state: "queued",
        stateLabel: "等待处理",
        recoveryAction: "无需操作，正在等待开始。",
      }),
    );
    setFactNormalizationRepository(makeRepo({ start, getStatus }));

    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: "开始整理" }));
    await waitFor(() => {
      expect(start).toHaveBeenCalled();
    });
    await user.click(screen.getByRole("button", { name: "再次开始" }));

    await waitFor(() => {
      expect(screen.getByLabelText("个例档案整理状态")).toHaveTextContent(
        "个例档案整理排队中",
      );
    });
    // 进行中的同键请求合并；完成后再次点击会幂等复用同一意图键。
    expect(start).toHaveBeenCalledWith("subject-1", "episode-1", {
      idempotencyKey: "idem-shared",
    });
    expect(
      start.mock.calls.every((call) => JSON.stringify(call).includes("idem-shared")),
    ).toBe(true);
    expect(window.localStorage.getItem(factNormalizationJobStorageKey("episode-1"))).toBe(
      "job-normalize-1",
    );
  });

  it("失败状态展示中文恢复动作并可重试", async () => {
    const getStatus = vi
      .fn()
      .mockResolvedValueOnce(
        status({
          state: "failed_retryable",
          stateLabel: "未完成，稍后重试",
          recoveryAction: "请点击「重新整理个例档案」。",
          progressCompleted: 1,
        }),
      )
      .mockResolvedValue(
        status({
          state: "running",
          stateLabel: "正在处理",
          recoveryAction: "关闭页面不会中断。",
          progressCompleted: 1,
        }),
      );
    const retry = vi.fn(async () => ({
      jobId: "job-normalize-1",
      state: "queued" as const,
      stateLabel: "等待处理",
      changed: true,
    }));
    window.localStorage.setItem(
      factNormalizationJobStorageKey("episode-1"),
      "job-normalize-1",
    );
    setFactNormalizationRepository(makeRepo({ getStatus, retry,
      current: async () => getStatus() }));

    const user = userEvent.setup();
    render(<Harness />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("个例档案整理未完成");
    });
    expect(screen.getByRole("button", { name: "重新整理个例档案" })).toBeInTheDocument();
    expect(screen.queryByText(/pipeline|schema|provider|Agent/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "重新整理个例档案" }));
    await waitFor(() => {
      expect(retry).toHaveBeenCalledWith("job-normalize-1");
    });
  });

  it("陈旧档案展示重新整理动作且保留上一版可读提示", async () => {
    window.localStorage.setItem(
      factNormalizationJobStorageKey("episode-1"),
      "job-normalize-1",
    );
    const getStatus = vi.fn(async () =>
      status({
        state: "completed",
        stateLabel: "已完成",
        recoveryAction: "本次处理已完成。",
        progressCompleted: 2,
        progressTotal: 2,
      }),
    );
    const start = vi.fn(async () => ({
      jobId: "job-normalize-2",
      runId: "run-normalize-2",
      created: true,
      state: "queued" as const,
      stateLabel: "等待处理",
      recoveryAction: "无需操作，正在等待开始。",
    }));
    setFactNormalizationRepository(
      makeRepo({
        current: async () => getStatus(),
        getStatus,
        start,
      }),
    );

    const user = userEvent.setup();
    render(<Harness profileStale />);

    await waitFor(() => {
      expect(screen.getByLabelText("个例档案整理状态")).toHaveTextContent(
        "资料已更新，需重新整理个例档案",
      );
    });
    expect(screen.getByText(/上一版内容仍可查阅|本次处理已完成/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "重新整理个例档案" }));
    await waitFor(() => {
      expect(start).toHaveBeenCalled();
    });
  });

  it("没有当前范围任务时清除旧缓存，不自动启动或读取旧任务", async () => {
    localStorage.setItem(factNormalizationJobStorageKey("episode-1"), "old-job");
    const start = vi.fn();
    const getStatus = vi.fn();
    const current = vi.fn(async () => null);
    setFactNormalizationRepository(makeRepo({ start, getStatus, current }));
    render(<Harness />);
    await waitFor(() => expect(localStorage.getItem(factNormalizationJobStorageKey("episode-1"))).toBeNull());
    expect(current).toHaveBeenCalledOnce();
    expect(start).not.toHaveBeenCalled();
    expect(getStatus).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("个例档案整理状态")).not.toBeInTheDocument();
  });

  it("资料版本切换后，旧恢复请求的迟到结果不能覆盖当前范围", async () => {
    let resolveOld: (value: FactNormalizationJobStatusView) => void = () => {};
    const current = vi.fn().mockImplementationOnce(() => new Promise(done => { resolveOld = done; }))
      .mockResolvedValue(null);
    const onSucceeded = vi.fn();
    const start = vi.fn();
    setFactNormalizationRepository(makeRepo({ current, start }));
    const view = render(<Harness sourceRevisionId="old" onSucceeded={onSucceeded} />);
    await waitFor(() => expect(current).toHaveBeenCalledOnce());
    view.rerender(<Harness sourceRevisionId="new" onSucceeded={onSucceeded} />);
    await screen.findByText("已恢复状态");
    await act(async () => resolveOld(status({ jobId: "old-job", state: "completed", stateLabel: "完成", recoveryAction: "" })));
    expect(onSucceeded).not.toHaveBeenCalled();
    expect(start).not.toHaveBeenCalled();
    expect(localStorage.getItem(factNormalizationJobStorageKey("episode-1"))).toBeNull();
    expect(screen.queryByLabelText("个例档案整理状态")).not.toBeInTheDocument();
  });

  it.each(["command", "status"])("启用刷新先于%s回包时，只读恢复新范围的实际任务，不再提交", async (latePhase) => {
    let resolveCommand!: (value: Awaited<ReturnType<FactNormalizationRepository["startFactNormalization"]>>) => void;
    let resolveStatus!: (value: FactNormalizationJobStatusView) => void;
    const started: Awaited<ReturnType<FactNormalizationRepository["startFactNormalization"]>> = {jobId: "old-command-job", runId: "run", created: true, state: "queued",
      stateLabel: "等待处理", recoveryAction: "无需操作"};
    const start = vi.fn(() => latePhase === "command" ? new Promise<typeof started>(done => {resolveCommand = done;}) : Promise.resolve(started));
    const getStatus = vi.fn((id: string) => id === "old-command-job"
      ? new Promise<FactNormalizationJobStatusView>(done => {resolveStatus = done;})
      : Promise.resolve(status({jobId: id, state: "running", stateLabel: "正在处理", recoveryAction: "关闭页面不会中断。"})));
    const current = vi.fn().mockResolvedValueOnce(null).mockResolvedValueOnce(null)
      .mockResolvedValue(status({jobId: "current-scope-job", state: "running", stateLabel: "正在处理", recoveryAction: "关闭页面不会中断。"}));
    const onSucceeded = vi.fn();
    setFactNormalizationRepository(makeRepo({start, getStatus, current}));
    const view = render(<Harness sourceRevisionId={null} onSucceeded={onSucceeded} />);
    await screen.findByText("已恢复状态");
    await userEvent.click(screen.getByRole("button", {name: "开始整理"}));
    await waitFor(() => expect(start).toHaveBeenCalledOnce());
    if (latePhase === "status") await waitFor(() => expect(getStatus).toHaveBeenCalledWith("old-command-job"));
    view.rerender(<Harness sourceRevisionId="activated-complete" onSucceeded={onSucceeded} />);
    await waitFor(() => expect(current).toHaveBeenCalledTimes(2));
    await screen.findByText("已恢复状态");
    await act(async () => {
      if (latePhase === "command") resolveCommand(started);
      else resolveStatus(status({jobId: "old-command-job", state: "completed", stateLabel: "已完成", recoveryAction: ""}));
    });
    await waitFor(() => expect(localStorage.getItem(factNormalizationJobStorageKey("episode-1"))).toBe("current-scope-job"));
    expect(screen.getByLabelText("个例档案整理状态")).toHaveTextContent("正在整理个例档案");
    expect(start).toHaveBeenCalledOnce();
    expect(onSucceeded).not.toHaveBeenCalled();
  });

  it("旧启动回包不能为另一受试者或节点恢复任务", async () => {
    let resolveCommand!: (value: Awaited<ReturnType<FactNormalizationRepository["startFactNormalization"]>>) => void;
    const start = vi.fn(() => new Promise<Awaited<ReturnType<FactNormalizationRepository["startFactNormalization"]>>>(done => {resolveCommand = done;}));
    const current = vi.fn(async () => null), getStatus = vi.fn();
    setFactNormalizationRepository(makeRepo({start, current, getStatus}));
    const view = render(<Harness sourceRevisionId="old" />);
    await screen.findByText("已恢复状态");
    await userEvent.click(screen.getByRole("button", {name: "开始整理"}));
    view.rerender(<Harness subjectId="subject-2" reviewEpisodeId="episode-2" sourceRevisionId="new" />);
    await waitFor(() => expect(current).toHaveBeenCalledTimes(2));
    await act(async () => resolveCommand({jobId: "old-job", runId: "old-run", created: true,
      state: "queued", stateLabel: "等待处理", recoveryAction: "无需操作"}));
    expect(current).toHaveBeenCalledTimes(2);
    expect(getStatus).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("个例档案整理状态")).not.toBeInTheDocument();
    expect(localStorage.getItem(factNormalizationJobStorageKey("episode-2"))).toBeNull();
  });

  it("恢复期间明确启动的新任务不被迟到的旧任务替换", async () => {
    let resolveOld: (value: FactNormalizationJobStatusView) => void = () => {};
    const current = vi.fn(() => new Promise<FactNormalizationJobStatusView>(done => { resolveOld = done; }));
    setFactNormalizationRepository(makeRepo({ current }));
    render(<Harness />);
    await waitFor(() => expect(current).toHaveBeenCalledOnce());
    await userEvent.click(screen.getByRole("button", { name: "开始整理" }));
    await screen.findByText("已恢复状态");
    await act(async () => resolveOld(status({ jobId: "old-job", state: "cancelled", stateLabel: "已停止", recoveryAction: "" })));
    expect(screen.getByLabelText("个例档案整理状态")).toHaveTextContent("个例档案整理排队中");
    expect(localStorage.getItem(factNormalizationJobStorageKey("episode-1"))).toBe("job-normalize-1");
  });

  it("服务端恢复失败不会回退旧缓存或自动付费重读", async () => {
    localStorage.setItem(factNormalizationJobStorageKey("episode-1"), "old-job");
    const start = vi.fn();
    const getStatus = vi.fn();
    setFactNormalizationRepository(makeRepo({ start, getStatus,
      current: async () => { throw new Error("connection unavailable"); } }));
    render(<Harness />);
    expect(await screen.findByRole("alert")).toHaveTextContent("暂时无法整理个例档案");
    expect(start).not.toHaveBeenCalled();
    expect(getStatus).not.toHaveBeenCalled();
  });

  it("成功终态触发回调且不把进度只留在内存", async () => {
    const onSucceeded = vi.fn();
    const getStatus = vi.fn(async () =>
      status({
        state: "completed",
        stateLabel: "已完成",
        recoveryAction: "可打开受试者档案查看整理结果。",
        progressCompleted: 2,
        progressTotal: 2,
      }),
    );
    const start = vi.fn(async () => ({
      jobId: "job-normalize-1",
      runId: "run-normalize-1",
      created: true,
      state: "completed" as const,
      stateLabel: "已完成",
      recoveryAction: "可打开受试者档案查看整理结果。",
    }));
    setFactNormalizationRepository(makeRepo({ start, getStatus }));

    const user = userEvent.setup();
    render(<Harness onSucceeded={onSucceeded} />);
    await user.click(screen.getByRole("button", { name: "开始整理" }));

    await waitFor(() => {
      expect(screen.getByLabelText("个例档案整理状态")).toHaveTextContent(
        "本次资料整理结果已保存",
      );
    });
    expect(onSucceeded).toHaveBeenCalledWith("job-normalize-1");
    expect(window.localStorage.getItem(factNormalizationJobStorageKey("episode-1"))).toBe(
      "job-normalize-1",
    );

    await act(async () => {
      // 无额外操作；确认成功态稳定。
    });
  });
});
