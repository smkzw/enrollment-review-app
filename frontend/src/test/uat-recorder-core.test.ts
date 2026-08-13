import { describe, expect, it } from "vitest";
import {
  TASKS,
  createEmptyBatch,
  createEmptyParticipant,
  generateBackupText,
  parseBackupText,
  summarizeBatch,
} from "../../public/uat-recorder-core.js";

function completedParticipant(code: string) {
  const participant = createEmptyParticipant({ code, pageVersion: "界面试用版 1.5.1" });
  for (const task of TASKS) {
    participant.taskRecords[task.id] = {
      ...participant.taskRecords[task.id],
      completed: true,
      assisted: false,
      layoutIssue: false,
      criticalEvidenceOperations: task.criticalEvidenceRequired ? 2 : null,
    };
  }
  return participant;
}

function summaryOf(participants: ReturnType<typeof createEmptyParticipant>[]) {
  const result = summarizeBatch(createEmptyBatch({ participants }));
  expect(result.ok).toBe(true);
  return result.value!;
}

describe("正式界面试用统计门槛", () => {
  it("没有有效运行时所有客观门槛均不得显示通过", () => {
    const summary = summaryOf([]);
    for (const gate of Object.values(summary.gates)) {
      if (gate.label === "主观评价") continue;
      expect(gate.passed, gate.label).not.toBe(true);
    }
    expect(summary.gates.errorConclusion.statusText).toBe("无法计算");
  });

  it("完全未测试的任务不能被逐任务完成率忽略", () => {
    const participants = Array.from({ length: 11 }, (_, index) =>
      completedParticipant(`P${String(index + 1).padStart(2, "0")}`),
    );
    for (const participant of participants) {
      participant.taskRecords["UAT-P1-14"] = {
        ...participant.taskRecords["UAT-P1-14"],
        completed: null,
        assisted: null,
        layoutIssue: null,
        criticalEvidenceOperations: null,
      };
    }
    const summary = summaryOf(participants);
    expect(summary.validRunCount).toBe(143);
    expect(summary.gates.perTaskUnassistedRate.passed).toBe(false);
    expect(summary.gates.perTaskUnassistedRate.tasksWithoutRuns).toContain(
      "UAT-P1-14 三档缩放",
    );
  });

  it("关键证据未填写时不能通过关键证据门槛", () => {
    const participant = completedParticipant("P01");
    participant.taskRecords["UAT-P1-08"].criticalEvidenceOperations = null;
    const summary = summaryOf([participant]);
    expect(summary.gates.criticalEvidenceOps.passed).toBe(false);
  });

  it("只检查一条布局记录不能代表整个有效运行矩阵", () => {
    const participant = completedParticipant("P01");
    for (const task of TASKS.slice(1)) {
      participant.taskRecords[task.id].layoutIssue = null;
    }
    const summary = summaryOf([participant]);
    expect(summary.layout.checkedRuns).toBe(1);
    expect(summary.gates.layoutKeyboard.passed).toBe(false);
  });

  it("含错误结论的运行即使被标记无效也必须保留错误历史", () => {
    const participant = completedParticipant("P01");
    participant.taskRecords["UAT-P1-03"] = {
      ...participant.taskRecords["UAT-P1-03"],
      isInvalid: true,
      invalidReason: "浏览器意外退出",
      errorCategories: ["E4"],
      notes: "参与者给出了相反结论",
    };
    const summary = summaryOf([participant]);
    expect(summary.invalidRunCount).toBe(1);
    expect(summary.e4Count).toBe(1);
    expect(summary.hasErrorConclusion).toBe(true);
    expect(summary.stopWarnings.join("\n")).toContain("立即暂停本轮试用");
  });

  it("备份预览只统计真正填写过的任务记录", () => {
    const participant = createEmptyParticipant({ code: "P01" });
    participant.taskRecords["UAT-P1-01"].durationSeconds = 12;
    const text = generateBackupText(createEmptyBatch({ participants: [participant] }));
    const restored = parseBackupText(text);
    expect(restored.ok).toBe(true);
    if (!restored.ok) return;
    expect(restored.meta.participantCount).toBe(1);
    expect(restored.meta.taskRecordCount).toBe(1);
  });
});
