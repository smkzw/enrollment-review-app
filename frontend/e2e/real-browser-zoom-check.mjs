import { chromium } from "playwright";
import {
  PROFILE_HASH,
  registerProfileRoutes,
} from "./profile-evidence-fixtures.ts";

const [zoomLabel, cdpUrl = "http://127.0.0.1:9334"] = process.argv.slice(2);
const holdOpen = process.argv.includes("--hold");
const baselineWidth = readPositiveNumber("--baseline-width", 1920);
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

  await registerProfileRoutes(page);
  await page.goto("about:blank");
  await page.goto(`http://127.0.0.1:4173/${PROFILE_HASH}`);
  await page.waitForLoadState("networkidle");
  await page.getByRole("heading", { name: "受试者与资料", level: 1 }).waitFor();
  await page.getByRole("heading", { name: /首屏重点/ }).waitFor();

  const profileMetrics = await readMetrics(page);
  await page.getByRole("button", { name: "全部历时信息" }).click();
  await page.getByRole("heading", { name: /人口学\/基线/ }).waitFor();
  const fullProfileMetrics = await readMetrics(page);
  await page
    .getByRole("button", { name: /查看.基线血压 120\/80 mmHg.的原文证据/ })
    .click();
  const evidencePanel = page.getByLabel("该条目的原文证据与定位");
  await evidencePanel.waitFor();
  const sourceImage = evidencePanel.getByRole("img", { name: "第 1 页原始资料" });
  await sourceImage.waitFor();
  await page.waitForFunction(
    (image) =>
      image instanceof HTMLImageElement && image.complete && image.naturalWidth > 0,
    await sourceImage.elementHandle(),
  );
  const evidenceMetrics = await readMetrics(page);

  assertZoomMetrics("个例首屏", profileMetrics);
  assertZoomMetrics("全部历时信息", fullProfileMetrics);
  assertZoomMetrics("原文证据面板", evidenceMetrics);
  await assertEvidencePlacement(page);

  if (!holdOpen) {
    await page.getByRole("button", { name: "关闭原文证据" }).click();
    await page.getByRole("button", { name: "返回首屏" }).click();
    await page.getByRole("heading", { name: /首屏重点/ }).waitFor();
  }

  if (runtimeErrors.length > 0) {
    throw new Error(`真实浏览器运行错误：${runtimeErrors.join("；")}`);
  }

  const result = {
    zoomLabel,
    browser: `Google Chrome ${browser.version()}（隔离实例）`,
    routeReturnedToProfile: holdOpen ? null : page.url().includes(PROFILE_HASH),
    heldOpenForSystemScreenshot: holdOpen,
    profile: profileMetrics,
    fullProfile: fullProfileMetrics,
    evidencePanel: evidenceMetrics,
    runtimeErrors,
    note: "使用浏览器自身缩放核对首屏、全部历时信息和原文证据面板；系统截图仍用于最终目视验收。",
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
      profileRect: readRect(document.querySelector(".profile")),
      evidencePanelRect: readRect(document.querySelector(".profile-evidence")),
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
    metrics.evidencePanelRect !== null &&
    (metrics.evidencePanelRect.left < 0 ||
      metrics.evidencePanelRect.right > metrics.innerWidth)
  ) {
    throw new Error(
      `${label} 在 ${zoomLabel}% 缩放下超出可视区：左侧 ${metrics.evidencePanelRect.left}，右侧 ${metrics.evidencePanelRect.right}，可视宽度 ${metrics.innerWidth}。`,
    );
  }
  if (
    metrics.profileRect !== null &&
    metrics.evidencePanelRect !== null &&
    metrics.evidencePanelRect.left <= metrics.profileRect.left
  ) {
    throw new Error(`${label} 在 ${zoomLabel}% 缩放下没有保留档案与原文的左右对照。`);
  }
}

async function assertEvidencePlacement(page) {
  const boxes = page.getByLabel(/^重点标注/);
  if ((await boxes.count()) !== 1) {
    throw new Error("原文证据面板必须且只能显示一个经过验证的重点框。");
  }
  const placement = await boxes.first().evaluate((box) => {
    const image = box.parentElement?.querySelector("img");
    if (!(image instanceof HTMLImageElement)) return null;
    const boxRect = box.getBoundingClientRect();
    const imageRect = image.getBoundingClientRect();
    return {
      centerX: (boxRect.left + boxRect.width / 2 - imageRect.left) / imageRect.width,
      centerY: (boxRect.top + boxRect.height / 2 - imageRect.top) / imageRect.height,
    };
  });
  if (
    placement === null ||
    placement.centerX <= 0.1 ||
    placement.centerX >= 0.35 ||
    placement.centerY <= 0.24 ||
    placement.centerY >= 0.32
  ) {
    throw new Error("重点框没有落在引用的原文内容上。");
  }
}
