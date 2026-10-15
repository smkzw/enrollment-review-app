// @vitest-environment jsdom
/**
 * 中央界面试用状态清单：稳定中文页面版本、四个登记键、复位范围与保留范围。
 * 对应正式 UAT 成功条件 1（四调用点不再各自硬编码键名）与 3（只删除清单内键）。
 */

import { beforeEach, describe, expect, it } from "vitest";
import {
  resetUatTrialState,
  UAT_KEY_CREATED_PROJECT,
  UAT_KEY_LAST_WORKBENCH_EPISODE,
  UAT_KEY_MANUAL_ACTIONS,
  UAT_KEY_PROTOCOL_DRAFT_SAVED,
  UAT_KEY_TASK_PROGRESS,
  UAT_PAGE_VERSION,
  UAT_TRIAL_STATE_KEYS,
} from "./uatTrialState";

describe("界面试用中央清单", () => {
  beforeEach(() => window.sessionStorage.clear());

  it("导出稳定中文页面版本，可直接照录到任务卡与记录表", () => {
    expect(UAT_PAGE_VERSION).toBe("界面试用版 1.5.2");
    expect(UAT_PAGE_VERSION).toMatch(/^界面试用版 \d+\.\d+\.\d+$/);
  });

  it("清单登记五类示例状态且均为已登记键，不出现散落字面量", () => {
    expect(UAT_TRIAL_STATE_KEYS).toHaveLength(5);
    expect(UAT_TRIAL_STATE_KEYS).toContain(UAT_KEY_MANUAL_ACTIONS);
    expect(UAT_TRIAL_STATE_KEYS).toContain(UAT_KEY_CREATED_PROJECT);
    expect(UAT_TRIAL_STATE_KEYS).toContain(UAT_KEY_PROTOCOL_DRAFT_SAVED);
    expect(UAT_TRIAL_STATE_KEYS).toContain(UAT_KEY_TASK_PROGRESS);
    expect(UAT_TRIAL_STATE_KEYS).toContain(UAT_KEY_LAST_WORKBENCH_EPISODE);
    for (const key of UAT_TRIAL_STATE_KEYS) {
      expect(key).toMatch(/^eligibility-review:uat:/);
    }
  });

  it("复位只删除登记键，保留任何无关键", () => {
    window.sessionStorage.setItem(UAT_KEY_MANUAL_ACTIONS, "x");
    window.sessionStorage.setItem(UAT_KEY_CREATED_PROJECT, "y");
    window.sessionStorage.setItem(UAT_KEY_PROTOCOL_DRAFT_SAVED, "true");
    window.sessionStorage.setItem(UAT_KEY_TASK_PROGRESS, "z");
    window.sessionStorage.setItem("unrelated:preference", "keep");

    resetUatTrialState();

    for (const key of UAT_TRIAL_STATE_KEYS) {
      expect(window.sessionStorage.getItem(key)).toBeNull();
    }
    expect(window.sessionStorage.getItem("unrelated:preference")).toBe("keep");
  });

  it("未登记的会话数据原样保留", () => {
    window.sessionStorage.setItem("eligibility-review:other", "keep");
    window.sessionStorage.setItem("plain-key", "keep");

    resetUatTrialState();

    expect(window.sessionStorage.getItem("eligibility-review:other")).toBe("keep");
    expect(window.sessionStorage.getItem("plain-key")).toBe("keep");
  });

  it("空会话复位不报错", () => {
    expect(() => resetUatTrialState()).not.toThrow();
  });
});
