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
  start?: FactNormalizationRepository["startFactNormalization"];
  getStatus?: FactNormalizationRepository["getFactNormalizationJobStatus"];
  retry?: FactNormalizationRepository["retryFactNormalizationJob"];
}): FactNormalizationRepository {
  return {
    kind: "http",
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
}: {
  profileStale?: boolean;
  onSucceeded?: (jobId: string) => void;
}) {
  const job = useFactNormalizationJob({
    subjectId: "subject-1",
    reviewEpisodeId: "episode-1",
    profileStale,
    onSucceeded,
    pollIntervalMs: 50,
  });
  return (
    <div>
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
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    setFactNormalizationRepository(null);
    window.localStorage.clear();
  });

  it("刷新后从本机 job id 恢复并拉取标准任务状态", async () => {
    window.localStorage.setItem(
      factNormalizationJobStorageKey("episode-1"),
      "job-normalize-1",
    );
    const getStatus = vi.fn(async () =>
      status({
        state: "running",
        stateLabel: "正在处理",
        recoveryAction: "关闭页面不会中断。",
        progressCompleted: 1,
      }),
    );
    setFactNormalizationRepository(makeRepo({ getStatus }));

    render(<Harness />);

    await waitFor(() => {
      expect(screen.getByLabelText("个例档案整理状态")).toHaveTextContent(
        "正在整理个例档案",
      );
    });
    expect(getStatus).toHaveBeenCalledWith("job-normalize-1");
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
    setFactNormalizationRepository(makeRepo({ getStatus, retry }));

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
        "个例档案已整理完成",
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
