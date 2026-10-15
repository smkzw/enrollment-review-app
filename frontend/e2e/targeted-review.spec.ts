/** Synthetic UI verification only; no model call or clinical acceptance. */
import { test, expect } from "@playwright/test";
import { registerProfileRoutes, SUBJECT_ID, EPISODE_ID } from "./profile-evidence-fixtures";

test.use({ channel: process.env.PLAYWRIGHT_CHANNEL || undefined });

test("辅助复核原件、轮次、缩放与非采信边界", async ({ page }, info) => {
  await registerProfileRoutes(page);
  await page.route("**/api/v2/jobs/original-ui", async (route) => route.fulfill({ json: {
    job_id: "original-ui", job_type: "r3_page_review", state: "completed", state_label: "已完成",
    cancel_requested: false, progress_completed: 3, progress_total: 3, recovery_action: "资料页已读完。",
    created_at: "2026-09-06T08:00:00Z", updated_at: "2026-09-06T08:01:00Z", steps: [], events: [],
  } }));
  await page.route("**/page-review-jobs/original-ui", async (route) => route.fulfill({ json: {
    job_id: "original-ui", state: "completed", review_status: "ready", total_pages: 1, accepted_pages: 1,
    unrelated_pages: 0, failed_pages: 0, pending_pages: 0, can_reread: false,
  } }));
  await page.route("**/page-review-jobs/original-ui/conflicts", async (route) => route.fulfill({ json: {
    job_id: "original-ui", pages: [{ page_index: 0, file_name: "合成检验报告.pdf", page_number: 1, field_count: 1 }],
  } }));
  await page.route("**/targeted-review-jobs", async (route) => {
    expect(route.request().method()).toBe("POST");
    expect(route.request().postDataJSON()).toEqual({ original_job_id: "original-ui", page_index: 0 });
    await route.fulfill({ json: { job_id: "auxiliary-ui" } });
  });
  await page.route("**/evidence-processing-revisions/processing-e2e-active/pages/entry-page-1/image", async (route) => route.fulfill({
    contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="1240" height="1754"><rect width="1240" height="1754" fill="white"/><g fill="#252525" font-family="sans-serif"><text x="120" y="180" font-size="42">合成检验报告（仅界面测试）</text><text x="120" y="320" font-size="28">采样日期：2026-08-01</text><text x="120" y="460" font-size="30">白细胞计数　3.2 ↓　10⁹/L</text><text x="120" y="580" font-size="24">本页不属于任何真实受试者资料。</text></g></svg>',
  }));
  await page.route("**/api/v2/jobs/auxiliary-ui", async (route) => route.fulfill({ json: {
    job_id: "auxiliary-ui", job_type: "r3_targeted_page_review", state: "completed", state_label: "已完成",
    cancel_requested: false, progress_completed: 6, progress_total: 6, recovery_action: "原分歧保留。",
    created_at: "2026-09-06T08:00:00Z", updated_at: "2026-09-06T08:01:00Z", steps: [], events: [],
  } }));
  await page.route("**/targeted-review-jobs/auxiliary-ui", async (route) => route.fulfill({ json: {
    job_id: "auxiliary-ui", state: "completed", status_label: "两轮复核后仍有分歧，请核对原件",
    round_budget: 2, rounds_with_receipts: 2, outcome: { candidate_auto_accept: false, clinical_findings_allowed: false },
  } }));
  await page.route("**/targeted-review-jobs/auxiliary-ui/evidence", async (route) => route.fulfill({ json: {
    job_id: "auxiliary-ui", file_name: "合成检验报告.pdf", page_number: 1, candidate_auto_accept: false,
    image_path: "/api/v2/evidence-processing-revisions/processing-e2e-active/pages/entry-page-1/image",
    excerpts: [0, 1, 2].flatMap((round) => [1, 2].map((reader) => ({
      round_number: round, read_number: reader, field_name: "白细胞计数", raw_value: reader === 1 ? "3.2 ↑" : "3.2 ↓",
      excerpt: `合成摘录：白细胞计数 3.2 ${reader === 1 ? "↑" : "↓"}`,
      target_text: null, time_text: "2026-08-01", location_text: "血常规报告",
    }))),
  } }));
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.addInitScript(({ subject, episode }) => {
    localStorage.setItem(`enrollment:page-review:${encodeURIComponent(subject)}:${encodeURIComponent(episode)}:completed`, "original-ui");
  }, { subject: SUBJECT_ID, episode: EPISODE_ID });
  const posts: string[] = [];
  page.on("request", (request) => { if (request.method() === "POST") posts.push(request.url()); });
  await page.goto(`/#/subjects?subject=${SUBJECT_ID}&episode=${EPISODE_ID}`);
  await expect(page.getByRole("link", { name: "查看最近一次资料判读" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("link", { name: "查看最近一次资料判读" })).toBeVisible();
  await page.screenshot({ path: `e2e/screenshots/completed-review-${info.project.name}.png`, fullPage: true });
  await page.getByRole("link", { name: "查看最近一次资料判读" }).click();
  expect(posts).toEqual([]);
  await page.getByRole("button", { name: "复核原件", exact: true }).click();
  await expect(page.getByRole("heading", { name: "原件内容复核" })).toBeVisible();
  await page.getByRole("button", { name: "第二轮", exact: true }).click();
  await expect(page.getByRole("button", { name: "第二轮", exact: true })).toHaveAttribute("aria-pressed", "true");
  const image = page.getByRole("img", { name: /合成检验报告/ });
  await expect(image).toBeVisible();
  expect(await image.evaluate((node: HTMLImageElement) => node.complete && node.naturalWidth > 0)).toBe(true);
  await page.getByRole("button", { name: "放大原件" }).click();
  await expect(page.getByText("125%", { exact: true })).toBeVisible();
  await expect(page.getByText(/正式事实未改动/)).toBeVisible();
  await expect(page.getByRole("button", { name: /采信|第三轮/ })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: `e2e/screenshots/targeted-review-${info.project.name}.png`, fullPage: true });
  expect(errors).toEqual([]);
});
