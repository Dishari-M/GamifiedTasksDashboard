import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const rootDir = process.cwd();
const artifactsDir = path.join(rootDir, "playwright-artifacts", "quests-focus-e2e");
const reportPath = path.join(artifactsDir, "report.json");
const baseUrl = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const apiBaseUrl = process.env.PLAYWRIGHT_API_BASE_URL || "http://127.0.0.1:8000/api/v1";
const userHomeDir = process.env.USERPROFILE
  || process.env.HOME
  || (process.env.HOMEDRIVE && process.env.HOMEPATH ? `${process.env.HOMEDRIVE}${process.env.HOMEPATH}` : "");

const resolveBrowserExecutable = async () => {
  if (process.env.PLAYWRIGHT_CHROME_PATH) {
    return process.env.PLAYWRIGHT_CHROME_PATH;
  }

  const playwrightRoot = path.join(userHomeDir, "AppData", "Local", "ms-playwright");
  const candidatePaths = [
    path.join(playwrightRoot, "chromium-1217", "chrome-win64", "chrome.exe"),
    path.join(playwrightRoot, "chromium-1217", "chrome-win", "chrome.exe"),
    path.join(playwrightRoot, "chromium_headless_shell-1217", "chrome-win", "headless_shell.exe"),
    path.join(playwrightRoot, "chromium_headless_shell-1217", "chrome-win64", "headless_shell.exe"),
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ];

  for (const candidate of candidatePaths) {
    try {
      await fs.access(candidate);
      return candidate;
    } catch {
      // Keep looking.
    }
  }

  throw new Error("Could not find a Playwright Chromium executable. Run 'playwright install chromium' first.");
};

const slug = (value) => String(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const parseLeadingInt = (value) => Number.parseInt(String(value || "").replace(/[^0-9].*$/, ""), 10) || 0;
const parseXpTotal = (value) => Number.parseInt(String(value || "").replace(/[^0-9]/g, ""), 10) || 0;

const buildTestAccount = () => {
  const stamp = Date.now();
  return {
    first_name: "Playwright",
    last_name: "Quest",
    username: `pwquests${stamp}`,
    email: `pwquests${stamp}@example.com`,
    password: "password",
    confirm_password: "password",
  };
};

const registerAndLogin = async (account) => {
  const registerResponse = await fetch(`${apiBaseUrl}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(account),
  });

  if (!registerResponse.ok) {
    throw new Error(`Test user registration failed with HTTP ${registerResponse.status()}.`);
  }

  const loginResponse = await fetch(`${apiBaseUrl}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      identifier: account.username,
      password: account.password,
    }),
  });

  if (!loginResponse.ok) {
    throw new Error(`Test user login failed with HTTP ${loginResponse.status()}.`);
  }

  return loginResponse.json();
};

const report = {
  baseUrl,
  apiBaseUrl,
  startedAt: new Date().toISOString(),
  taskTitle: `E2E Quest Focus ${Date.now()}`,
  steps: [],
  consoleMessages: [],
  pageErrors: [],
};

const addStep = (name, status, details = {}) => {
  report.steps.push({ name, status, at: new Date().toISOString(), ...details });
};

await fs.mkdir(artifactsDir, { recursive: true });

const testAccount = buildTestAccount();
const authPayload = await registerAndLogin(testAccount);
const currentUser = authPayload?.data ?? authPayload;
if (!currentUser?.user_id) {
  throw new Error("Test auth did not return a usable current user profile.");
}

const browserExecutable = await resolveBrowserExecutable();
const browser = await chromium.launch({ headless: true, executablePath: browserExecutable });
const context = await browser.newContext({ viewport: { width: 1440, height: 1200 }, deviceScaleFactor: 1 });
const page = await context.newPage();

page.on("console", (message) => {
  const type = message.type();
  if (type === "error" || type === "warning") {
    report.consoleMessages.push({ type, text: message.text() });
  }
});
page.on("pageerror", (error) => {
  report.pageErrors.push(String(error));
});
page.on("dialog", async (dialog) => {
  report.steps.push({
    name: "dialog",
    status: "info",
    at: new Date().toISOString(),
    type: dialog.type(),
    message: dialog.message(),
  });
  await dialog.accept();
});

await page.addInitScript((user) => {
  window.localStorage.setItem("devquest.currentUser", JSON.stringify(user));
}, currentUser);

const saveScreenshot = async (name) => {
  await page.screenshot({
    path: path.join(artifactsDir, `${name}.png`),
    fullPage: true,
  });
};

const expectVisible = async (locator, timeout, message) => {
  await locator.waitFor({ state: "visible", timeout });
  return locator;
};

try {
  await page.goto(`${baseUrl}/tasks`, { waitUntil: "load", timeout: 45000 });
  await expectVisible(page.getByTestId("tasks-page"), 15000, "Tasks page did not load.");
  addStep("open-tasks-page", "passed");

  report.initialXpTotal = parseXpTotal(await page.getByTestId("level-total-xp").textContent());
  report.initialStreakDays = parseLeadingInt(await page.getByTestId("streak-days-value").textContent());

  await page.getByTestId("create-task-title-input").fill(report.taskTitle);
  await page.getByTestId("create-task-description-input").fill("Playwright E2E validation for quests and focus integration.");
  await page.getByTestId("create-task-rca-size-select").selectOption("M");

  const createResponsePromise = page.waitForResponse((response) =>
    response.url().includes("/api/v1/tasks") && response.request().method() === "POST",
  { timeout: 45000 });
  await page.getByTestId("create-task-submit-button").click();
  const createResponse = await createResponsePromise;
  report.createTaskStatus = createResponse.status();
  report.createdTask = await createResponse.json().catch(() => null);
  if (!createResponse.ok()) {
    throw new Error(`UI task create failed with HTTP ${createResponse.status()}.`);
  }
  report.createdTask = report.createdTask?.data ?? report.createdTask;
  addStep("create-working-today-task-via-ui", "passed", {
    taskId: report.createdTask?.task_id ?? null,
    externalId: report.createdTask?.external_id ?? null,
  });

  const taskRow = page.getByTestId(`task-row-${slug(report.createdTask?.external_id || report.createdTask?.task_id || report.taskTitle)}`).first();
  const fallbackTaskCell = page.locator("tr", { hasText: report.taskTitle }).first();
  if (await taskRow.count()) {
    await expectVisible(taskRow, 15000);
  } else {
    await expectVisible(fallbackTaskCell, 15000);
  }
  addStep("have-working-today-task-ready", "passed", {
    taskId: report.createdTask?.task_id ?? null,
    externalId: report.createdTask?.external_id ?? null,
  });
  await saveScreenshot("01-task-created");

  await page.goto(`${baseUrl}/quests`, { waitUntil: "load", timeout: 45000 });
  await expectVisible(page.getByTestId("quests-page"), 15000);
  addStep("open-quests-page", "passed");

  const generateResponsePromise = page.waitForResponse((response) =>
    response.url().includes("/api/v1/quests/generate") && response.request().method() === "POST",
  { timeout: 60000 });
  await page.getByTestId("generate-quests-button").click();
  const generateResponse = await generateResponsePromise;
  report.generateQuestsStatus = generateResponse.status();
  report.generatedQuestRun = await generateResponse.json().catch(() => null);
  if (!generateResponse.ok()) {
    throw new Error(`Quest generation failed with HTTP ${generateResponse.status()}.`);
  }
  addStep("generate-quests", "passed", {
    questCount: Array.isArray(report.generatedQuestRun?.data?.quests)
      ? report.generatedQuestRun.data.quests.length
      : Array.isArray(report.generatedQuestRun?.quests)
        ? report.generatedQuestRun.quests.length
        : null,
  });

  const nextQuestCard = page.getByTestId("next-quest-card");
  await expectVisible(nextQuestCard, 15000);
  report.activeQuestTitle = (await page.getByTestId("next-quest-title").textContent())?.trim() || "";
  addStep("render-generated-quest-ui", "passed", {
    activeQuestTitle: report.activeQuestTitle,
  });
  await saveScreenshot("02-quests-generated");

  await page.getByTestId("quest-start-focus-button").click();
  await page.waitForURL(/\/focus$/, { timeout: 15000 });
  await expectVisible(page.getByTestId("focus-page"), 15000);
  await expectVisible(page.getByTestId("focus-stop-button"), 15000);
  addStep("start-focus-from-quest", "passed", {
    taskTitle: report.activeQuestTitle,
  });
  await saveScreenshot("03-focus-started");

  await wait(2000);
  const focusNote = `Playwright saved this session at ${new Date().toISOString()}`;
  const focusOutcomeNote = page.getByTestId("focus-outcome-note");
  if (await focusOutcomeNote.count()) {
    await focusOutcomeNote.fill(focusNote);
  }

  const focusSaveResponsePromise = page.waitForResponse((response) =>
    response.url().includes("/api/v1/focus-sessions") && response.request().method() === "POST",
  { timeout: 60000 });
  await page.getByTestId("focus-stop-button").click();
  const focusSaveResponse = await focusSaveResponsePromise;
  report.saveFocusStatus = focusSaveResponse.status();
  report.savedFocusSession = await focusSaveResponse.json().catch(() => null);
  if (!focusSaveResponse.ok()) {
    throw new Error(`Focus session save failed with HTTP ${focusSaveResponse.status()}.`);
  }

  const focusSavedPanel = page.getByTestId("focus-quest-saved");
  await expectVisible(focusSavedPanel, 15000);
  addStep("save-focus-session", "passed", {
    focusSessionId: report.savedFocusSession?.data?.focus_session_id
      ?? report.savedFocusSession?.focus_session_id
      ?? null,
  });
  await saveScreenshot("04-focus-saved");

  const returnToQuestButton = page.getByTestId("focus-return-quest-button");
  if (await returnToQuestButton.count()) {
    await returnToQuestButton.click();
    await page.waitForURL(/\/quests$/, { timeout: 15000 });
  } else {
    await page.goto(`${baseUrl}/quests`, { waitUntil: "load", timeout: 45000 });
  }
  await expectVisible(page.getByTestId("quests-page"), 15000);

  await expectVisible(page.getByTestId("quest-complete-button"), 10000);
  const completeResponsePromise = page.waitForResponse((response) =>
    /\/api\/v1\/quests\/[^/]+$/.test(response.url()) && response.request().method() === "PATCH",
  { timeout: 60000 });
  await page.getByTestId("quest-complete-button").click();
  const completeResponse = await completeResponsePromise;
  report.completeQuestStatus = completeResponse.status();
  report.completedQuestRun = await completeResponse.json().catch(() => null);
  if (!completeResponse.ok()) {
    throw new Error(`Quest completion failed with HTTP ${completeResponse.status()}.`);
  }

  await expectVisible(page.getByTestId("floating-notice"), 15000);
  const completionText = (await page.getByTestId("floating-notice").textContent())?.trim() || "";
  report.completionNotice = completionText;
  report.finalXpTotal = parseXpTotal(await page.getByTestId("level-total-xp").textContent());
  report.finalStreakDays = parseLeadingInt(await page.getByTestId("streak-days-value").textContent());
  if (report.finalXpTotal <= report.initialXpTotal) {
    throw new Error(`Expected total XP to increase after completing a quest. Before=${report.initialXpTotal}, after=${report.finalXpTotal}.`);
  }
  if (report.finalStreakDays < 1) {
    throw new Error(`Expected quest streak to start after completing a quest. Saw ${report.finalStreakDays}.`);
  }
  addStep("complete-quest", "passed", {
    completionNotice: completionText,
    initialXpTotal: report.initialXpTotal,
    finalXpTotal: report.finalXpTotal,
    initialStreakDays: report.initialStreakDays,
    finalStreakDays: report.finalStreakDays,
  });
  await saveScreenshot("05-quest-completed");
  report.result = "passed";
} catch (error) {
  report.result = "failed";
  report.failure = String(error);
  addStep("failure", "failed", { error: String(error) });
  await saveScreenshot("failure-state").catch(() => {});
  throw error;
} finally {
  report.finishedAt = new Date().toISOString();
  await fs.writeFile(reportPath, JSON.stringify(report, null, 2), "utf8");
  await context.close().catch(() => {});
  await browser.close().catch(() => {});
}

console.log(`Quests/focus E2E complete. Report: ${reportPath}`);
