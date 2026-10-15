import { expect, test } from "@playwright/test";
import { SUBJECT_ID, EPISODE_ID, registerEvidenceRoutes } from "./evidence-fixtures";
import { expectNoPageOverflow } from "./helpers";
import { PROFILE_HASH, registerProfileRoutes } from "./profile-evidence-fixtures";

// Controlled HTTP responses test the real product UI; no clinical/model acceptance is claimed.
for (const stopped of [false, true]) {
test(stopped ? "停止判读后刷新并继续原任务" : "资料判读失败后刷新恢复、局部重读并继续整理", async ({ page }, info) => {
  await registerEvidenceRoutes(page, { activeReview: true });
  const storageKey = `enrollment:page-review:${encodeURIComponent(SUBJECT_ID)}:${encodeURIComponent(EPISODE_ID)}`;
  await page.addInitScript((key) => {
    if (!localStorage.getItem("r3-browser-seeded")) {
      localStorage.setItem(key, "root");
      localStorage.setItem("r3-browser-seeded", "true");
    }
  }, storageKey);
  let recovered = false;
  const submissions: unknown[] = [];
  await page.route("**/api/v2/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const send = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path.endsWith("/patient-profile")) {
      return send({ error: { code: "NOT_FOUND", title: "档案尚未生成", detail: "档案尚未生成", recovery_action: "请整理资料" } }, 404);
    }
    if (path.endsWith("/fact-normalization-jobs")) {
      if (!recovered) return send({ error: { code: "PAGE_COVERAGE_NOT_READY", title: "资料判读尚未完成", detail: "请先完成资料判读", recovery_action: "请先完成资料判读" } }, 409);
      return send({ job_id: "normalize", run_id: "run", created: true, state: "queued", state_label: "等待处理", recovery_action: "正在准备" }, 201);
    }
    if (path.endsWith("/page-review-jobs")) {
      const body = request.postDataJSON();
      submissions.push(body);
      if (body.predecessor_job_id === "root") recovered = true;
      return send({ job_id: recovered ? "child" : "root", state: "completed", created: true }, 201);
    }
    if (path.endsWith("/page-review-jobs/root/resume")) {
      submissions.push({ resume: "root" });
      recovered = true;
      return send({ job_id: "root", state: "queued", changed: true, state_label: "等待处理" });
    }
    if (/\/page-review-jobs\/(root|child)$/.test(path)) {
      const success = path.endsWith("/child") || (stopped && recovered);
      return send({ job_id: path.endsWith("/child") ? "child" : "root", state: stopped && !success ? "cancelled" : "completed",
        review_status: success ? "ready" : stopped ? "stopped" : "needs_reread", status_label: "资料判读",
        total_pages: 2, accepted_pages: success ? 1 : 0, unrelated_pages: 1,
        failed_pages: success || stopped ? 0 : 1, pending_pages: stopped && !success ? 1 : 0, can_reread: !success && !stopped,
        coverage_id: success ? "new" : "old", predecessor_job_id: success ? "root" : null });
    }
    if (path.endsWith("/jobs/normalize")) {
      return send({ job_id: "normalize", state: "running", state_label: "正在整理",
        cancel_requested: false, progress_completed: 0, progress_total: 2,
        recovery_action: "正在整理", created_at: "2026-09-06T00:00:00Z", updated_at: "2026-09-06T00:00:00Z" });
    }
    return route.fallback();
  });
  await page.goto(`/#/subjects/${SUBJECT_ID}/evidence?episode=${EPISODE_ID}`);
  const status = page.getByLabel("资料判读进度");
  await expect(status.getByText("已读完 1 / 2 页")).toBeVisible();
  await expectNoPageOverflow(page);
  await page.screenshot({ path: info.outputPath("failed-page.png"), fullPage: true });
  await page.reload();
  await expect(status.getByText("已读完 1 / 2 页")).toBeVisible();
  const countBefore = submissions.length;
  await status.getByRole("button", { name: stopped ? "继续判读" : "重读未完成资料" }).click();
  await expect(page.getByLabel("个例档案整理状态")).toBeVisible();
  expect(submissions.slice(countBefore)).toEqual([stopped ? { resume: "root" } : { predecessor_job_id: "root" }]);
  await expectNoPageOverflow(page);
  await page.screenshot({ path: info.outputPath("organizing.png"), fullPage: true });
});
}

test("正式资料目录进入个例档案并回看原文，失效项目不替换为其他项目", async ({ page }, info) => {
  await registerProfileRoutes(page);
  let profileReads = 0;
  await page.route("**/patient-profile", async (route) => {
    profileReads += 1;
    return route.fallback();
  });
  await page.goto(`/${PROFILE_HASH}`);
  await expect(page.getByRole("region", { name: "个例全景" })).toBeVisible();
  await page.getByRole("button", { name: /查看.基线血压 120\/80 mmHg.的原文证据/ }).click();
  const panel = page.getByLabel("该条目的原文证据与定位");
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("img", { name: "第 1 页原始资料" })).toBeVisible();
  await expect(page.getByLabel(/^重点标注/)).toHaveCount(1);
  await expectNoPageOverflow(page);
  await page.screenshot({ path: info.outputPath("formal-profile.png"), fullPage: true });
  const before = profileReads;
  await page.goto("/#/profiles?project=missing&subject=missing&episode=missing");
  await expect(page.getByText("链接中的项目不存在，请重新选择。")).toBeVisible();
  expect(profileReads).toBe(before);
});
