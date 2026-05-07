import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const rootDir = process.cwd();
const artifactsDir = path.join(rootDir, "playwright-artifacts");
const reportPath = path.join(artifactsDir, "ui-review-report.json");
const baseUrl = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const userHomeDir = process.env.USERPROFILE
  || process.env.HOME
  || (process.env.HOMEDRIVE && process.env.HOMEPATH ? `${process.env.HOMEDRIVE}${process.env.HOMEPATH}` : "");

const pathExists = async (candidate) => {
  try {
    await fs.access(candidate);
    return true;
  } catch {
    return false;
  }
};

const resolveBrowserExecutable = async () => {
  if (process.env.PLAYWRIGHT_CHROME_PATH) {
    return process.env.PLAYWRIGHT_CHROME_PATH;
  }

  const playwrightRoot = path.join(userHomeDir, "AppData", "Local", "ms-playwright");
  const directCandidates = [
    path.join(playwrightRoot, "chromium-1217", "chrome-win64", "chrome.exe"),
    path.join(playwrightRoot, "chromium-1217", "chrome-win", "chrome.exe"),
    path.join(playwrightRoot, "chromium_headless_shell-1217", "chrome-win", "headless_shell.exe"),
    path.join(playwrightRoot, "chromium_headless_shell-1217", "chrome-win64", "headless_shell.exe"),
  ];

  for (const candidate of directCandidates) {
    if (await pathExists(candidate)) {
      return candidate;
    }
  }

  const browserDirs = await fs.readdir(playwrightRoot, { withFileTypes: true }).catch(() => []);
  const preferredDirs = browserDirs
    .filter((entry) => entry.isDirectory() && (entry.name.startsWith("chromium-") || entry.name.startsWith("chromium_headless_shell-")))
    .map((entry) => entry.name)
    .sort()
    .reverse();

  for (const dirName of preferredDirs) {
    const candidatePaths = [
      path.join(playwrightRoot, dirName, "chrome-win64", "chrome.exe"),
      path.join(playwrightRoot, dirName, "chrome-win", "chrome.exe"),
      path.join(playwrightRoot, dirName, "chrome-win64", "headless_shell.exe"),
      path.join(playwrightRoot, dirName, "chrome-win", "headless_shell.exe"),
    ];

    for (const candidate of candidatePaths) {
      if (await pathExists(candidate)) {
        return candidate;
      }
    }
  }

  const systemCandidates = [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  ];

  for (const candidate of systemCandidates) {
    if (await pathExists(candidate)) {
      return candidate;
    }
  }

  throw new Error("Could not find a Playwright Chromium executable. Run 'playwright install chromium' first.");
};

const currentUser = {
  user_id: "1",
  first_name: "Rahul",
  last_name: "Kulkarni",
};

const pages = [
  { name: "dashboard", path: "/" },
  { name: "quests", path: "/quests" },
  { name: "focus", path: "/focus" },
];

const viewports = [
  { name: "desktop", width: 1440, height: 1200 },
  { name: "mobile", width: 390, height: 844 },
];

await fs.mkdir(artifactsDir, { recursive: true });

const browserExecutable = await resolveBrowserExecutable();
const browser = await chromium.launch({ headless: true, executablePath: browserExecutable });
const findings = [];

for (const viewport of viewports) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const consoleMessages = [];
  const pageErrors = [];

  page.on("console", (message) => {
    const type = message.type();
    if (type === "error" || type === "warning") {
      consoleMessages.push({ type, text: message.text() });
    }
  });
  page.on("pageerror", (error) => {
    pageErrors.push(String(error));
  });

  await page.addInitScript((user) => {
    window.localStorage.setItem("devquest.currentUser", JSON.stringify(user));
  }, currentUser);

  for (const target of pages) {
    const url = `${baseUrl}${target.path}`;
    try {
      await page.goto(url, { waitUntil: "load", timeout: 45000 });
      await page.waitForTimeout(1500);
      await page.screenshot({
        path: path.join(artifactsDir, `${target.name}-${viewport.name}.png`),
        fullPage: true,
      });

      const metrics = await page.evaluate(() => {
        const doc = document.documentElement;
        const body = document.body;
        const overflowing = [];
        const candidates = Array.from(document.querySelectorAll("body *"));
        for (const node of candidates) {
          const rect = node.getBoundingClientRect();
          if (rect.width - window.innerWidth > 1 || rect.right - window.innerWidth > 1 || rect.left < -1) {
            overflowing.push({
              tag: node.tagName,
              testId: node.getAttribute("data-testid"),
              className: node.className,
              width: Math.round(rect.width),
              right: Math.round(rect.right),
              left: Math.round(rect.left),
            });
          }
        }
        return {
          path: window.location.pathname,
          title: document.title,
          bodyScrollWidth: body.scrollWidth,
          bodyClientWidth: body.clientWidth,
          docScrollWidth: doc.scrollWidth,
          docClientWidth: doc.clientWidth,
          horizontalOverflow: Math.max(body.scrollWidth - body.clientWidth, doc.scrollWidth - doc.clientWidth),
          overflowing: overflowing.slice(0, 25),
        };
      });

      findings.push({
        viewport: viewport.name,
        page: target.name,
        url,
        metrics,
        consoleMessages: [...consoleMessages],
        pageErrors: [...pageErrors],
      });
    } catch (error) {
      findings.push({
        viewport: viewport.name,
        page: target.name,
        url,
        error: String(error),
        consoleMessages: [...consoleMessages],
        pageErrors: [...pageErrors],
      });
    }
  }

  await context.close();
}

await browser.close();
await fs.writeFile(reportPath, JSON.stringify(findings, null, 2), "utf8");

console.log(`Playwright review complete. Report: ${reportPath}`);
