import { chromium } from "playwright";

const [zoomLabel, cdpUrl = "http://127.0.0.1:9334"] = process.argv.slice(2);
const holdOpen = process.argv.includes("--hold");
const baselineWidth = readPositiveNumber("--baseline-width", 1440);
const baselineDpr = readPositiveNumber("--baseline-dpr", 2);

if (!zoomLabel) {
  throw new Error("请提供浏览器缩放标签，例如 100、150 或 200。");
}
const zoomPercent = Number(zoomLabel);
if (![100, 150, 200].includes(zoomPercent)) {
  throw new Error("浏览器缩放标签只能是 100、150 或 200。");
}

const browser = await chromium.connectOverCDP(cdpUrl);

try {
  const page = browser
    .contexts()
    .flatMap((context) => context.pages())
    .find((candidate) => candidate.url().includes("127.0.0.1:4173"));

  if (!page) {
    throw new Error("隔离浏览器中没有找到入排审核工作台页面。");
  }

  const runtimeErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") runtimeErrors.push(`控制台：${message.text()}`);
  });
  page.on("pageerror", (error) => runtimeErrors.push(`页面脚本：${error.message}`));

  await page.goto(
    "http://127.0.0.1:4173/#/subjects?subject=subject-uat-02-barrier&stage=screening",
  );
  await page.waitForLoadState("networkidle");
  await page.getByText("关键事件与风险").waitFor();

  const profileMetrics = await readMetrics(page);
  await page.getByRole("link", { name: /查看判断依据/ }).first().click();
  await page.waitForLoadState("networkidle");

  if (await page.locator(".workbench-tabs").isVisible()) {
    await page.getByRole("tab", { name: "证据" }).click();
  }

  await page.getByText("页内摘录").first().waitFor();
  const workbenchMetrics = await readMetrics(page);
  await page.getByRole("button", { name: /打开证据/ }).first().click();
  await page.getByRole("dialog", { name: "原始资料证据" }).waitFor();
  const evidenceMetrics = await readMetrics(page);

  assertZoomMetrics("个例首页", profileMetrics);
  assertZoomMetrics("审核工作台", workbenchMetrics);
  assertZoomMetrics("原始资料证据", evidenceMetrics);

  if (!holdOpen) {
    await page.getByRole("button", { name: "关闭证据" }).click();
    await page.goBack();
    await page.getByText("关键事件与风险").waitFor();
  }

  if (runtimeErrors.length > 0) {
    throw new Error(`真实浏览器运行错误：${runtimeErrors.join("；")}`);
  }

  const result = {
    zoomLabel,
    browser: `Google Chrome ${browser.version()}（隔离实例）`,
    routeReturnedToProfile: holdOpen ? null : page.url().includes("#/subjects"),
    heldOpenForSystemScreenshot: holdOpen,
    profile: profileMetrics,
    workbench: workbenchMetrics,
    evidenceDialog: evidenceMetrics,
    runtimeErrors,
    note: "真实缩放下的 CDP 页面截图会受滚动位置影响；视觉验收使用 macOS 系统级窗口截图。",
  };

  console.log(JSON.stringify(result));
} finally {
  await browser.close();
}

async function readMetrics(page) {
  return page.evaluate(() => {
    const root = document.documentElement;
    const viewport = window.visualViewport;
    const readRect = (element) => {
      if (!(element instanceof HTMLElement)) return null;
      const rect = element.getBoundingClientRect();
      return {
        top: Math.round(rect.top),
        right: Math.round(rect.right),
        bottom: Math.round(rect.bottom),
        left: Math.round(rect.left),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      };
    };
    return {
      innerWidth: window.innerWidth,
      innerHeight: window.innerHeight,
      devicePixelRatio: window.devicePixelRatio,
      visualViewportWidth: viewport?.width ?? null,
      visualViewportScale: viewport?.scale ?? null,
      documentClientWidth: root.clientWidth,
      documentScrollWidth: root.scrollWidth,
      hasPageOverflow: root.scrollWidth > root.clientWidth + 1,
      scrollX: window.scrollX,
      scrollY: window.scrollY,
      appShellRect: readRect(document.querySelector(".app-shell")),
      scrimRect: readRect(document.querySelector(".evidence-dialog-scrim")),
      dialogRect: readRect(document.querySelector(".evidence-dialog")),
    };
  });
}

function readPositiveNumber(name, fallback) {
  const prefix = `${name}=`;
  const raw = process.argv.find((item) => item.startsWith(prefix))?.slice(prefix.length);
  if (raw === undefined) return fallback;
  const value = Number(raw);
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error(`${name} 必须是大于 0 的数字。`);
  }
  return value;
}

function assertZoomMetrics(label, metrics) {
  const factor = zoomPercent / 100;
  const expectedWidth = Math.round(baselineWidth / factor);
  const expectedDpr = baselineDpr * factor;
  if (Math.abs(metrics.innerWidth - expectedWidth) > 2) {
    throw new Error(
      `${label} 的视口宽度与 ${zoomLabel}% 缩放不符：预期约 ${expectedWidth}，实际 ${metrics.innerWidth}。`,
    );
  }
  if (Math.abs(metrics.devicePixelRatio - expectedDpr) > 0.02) {
    throw new Error(
      `${label} 的屏幕倍率与 ${zoomLabel}% 缩放不符：预期约 ${expectedDpr}，实际 ${metrics.devicePixelRatio}。`,
    );
  }
  if (metrics.hasPageOverflow) {
    throw new Error(`${label} 在 ${zoomLabel}% 缩放下出现页面级横向滚动。`);
  }
  if (
    metrics.dialogRect !== null &&
    (metrics.dialogRect.left < 0 || metrics.dialogRect.right > metrics.innerWidth)
  ) {
    throw new Error(
      `${label} 在 ${zoomLabel}% 缩放下超出可视区：左侧 ${metrics.dialogRect.left}，右侧 ${metrics.dialogRect.right}，可视宽度 ${metrics.innerWidth}。`,
    );
  }
}
