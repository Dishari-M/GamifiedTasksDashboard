import { Bug, FileText, GitPullRequest, RocketLaunch, UsersThree } from "@phosphor-icons/react";
import { addDaysKey, formatMinutes, formatTime, nowIso, todayKey } from "../../utils/dateTime";
import { parseNumber } from "../../utils/number";
import { readStoredJson } from "../../utils/storage";

export const TASKS_STORAGE_KEY = "devquest.tasks.v1";

export const taskTypes = ["Task", "Bug", "Epic", "Review", "Meeting"];
export const priorities = ["Critical", "High", "Medium", "Low"];
export const statuses = ["To Do", "In Progress", "Blocked", "Done", "Upcoming"];
export const sources = ["Custom", "Jira", "Outlook", "Microsoft To Do"];

export const iconForType = (type) => {
  if (type === "Bug") return Bug;
  if (type === "Epic") return RocketLaunch;
  if (type === "Review") return GitPullRequest;
  if (type === "Meeting") return UsersThree;
  return FileText;
};

export const accentForPriority = (priority) => {
  if (priority === "Critical" || priority === "High") return "red";
  if (priority === "Medium") return "gold";
  if (priority === "Low") return "green";
  return "blue";
};

export const buildAiFields = (task) => {
  const priorityWeight = { Critical: 10, High: 8, Medium: 5, Low: 3 }[task.priority] || 5;
  const effort = Math.max(15, parseNumber(task.time ?? task.estimatedMinutes, 60));
  const notesBoost = task.notes ? 0.4 : 0;
  const impact = Math.min(10, Math.max(1, parseNumber(task.impact, priorityWeight + notesBoost)));
  const priorityScore = Math.min(0.99, Math.round(((priorityWeight * 0.58 + impact * 0.32 + Math.min(effort / 60, 4) * 0.1) / 10) * 100) / 100);
  const xp = Math.max(10, parseNumber(task.xp, Math.round((effort * 0.75 + impact * 9 + priorityWeight * 5) / 10) * 10));
  const difficulty = effort >= 105 || priorityWeight >= 9 ? "Hard" : effort <= 35 && priorityWeight <= 5 ? "Easy" : "Medium";
  return {
    difficulty,
    impact,
    priorityScore,
    effort,
    xp,
    aiInsight: task.aiInsight || `${task.priority} priority ${task.type || "Task"} with ${formatMinutes(effort)} expected effort. ${task.notes ? "Use the notes as context for standup and overview summaries." : "Add notes as you learn more to improve the summary."}`,
  };
};

export const normalizeTask = (task) => {
  const ai = buildAiFields(task);
  return {
    ...task,
    source: task.source || "Custom",
    type: task.type || "Task",
    priority: task.priority || "Medium",
    status: task.status || "To Do",
    time: ai.effort,
    xp: ai.xp,
    difficulty: ai.difficulty,
    impact: ai.impact,
    priorityScore: ai.priorityScore,
    aiInsight: ai.aiInsight,
    notes: task.notes || "",
    labels: Array.isArray(task.labels) ? task.labels : String(task.labels || "").split(",").map((label) => label.trim()).filter(Boolean),
    workingToday: Boolean(task.workingToday),
    icon: iconForType(task.type || "Task"),
    accent: task.accent || accentForPriority(task.priority || "Medium"),
  };
};

export const makeTaskId = (source, externalId) => {
  if (externalId?.trim()) return externalId.trim();
  const prefix = source === "Jira" ? "JRA" : source === "Outlook" ? "OUT" : source === "Microsoft To Do" ? "TODO" : "CUS";
  return `${prefix}-${Math.floor(Math.random() * 9000 + 1000)}`;
};

export const initialTasks = [
  normalizeTask({
    id: "PAY-2301",
    externalId: "PAY-2301",
    projectKey: "PAY",
    title: "Fix payment gateway timeout issue",
    description: "Users face timeout while making payments on the checkout page.",
    source: "Jira",
    type: "Bug",
    priority: "High",
    status: "In Progress",
    impact: 9,
    time: 120,
    actualMinutes: 45,
    xp: 120,
    workingToday: true,
    dueDate: todayKey(),
    notes: "Retry policy may be too generous for the gateway sandbox. Validate timeout cap and add regression coverage.",
    labels: ["payments", "backend"],
  }),
  normalizeTask({
    id: "ORD-1587",
    externalId: "ORD-1587",
    projectKey: "ORD",
    title: "Implement order tracking API",
    description: "Create a REST API to fetch real-time order status.",
    source: "Jira",
    type: "Epic",
    priority: "Medium",
    status: "To Do",
    impact: 8,
    time: 90,
    xp: 90,
    workingToday: true,
    dueDate: addDaysKey(todayKey(), 1),
    notes: "Contract is clear; biggest risk is mapping courier status states cleanly.",
    labels: ["api"],
  }),
  normalizeTask({
    id: "DOC-047",
    externalId: "DOC-047",
    title: "Update deployment documentation",
    description: "Update deployment steps for the v2.3.0 release.",
    source: "Microsoft To Do",
    type: "Task",
    priority: "Low",
    status: "To Do",
    impact: 5,
    time: 30,
    xp: 30,
    workingToday: false,
    notes: "Add rollback screenshots and note the environment variable rename.",
    labels: ["docs"],
  }),
  normalizeTask({
    id: "PR-468",
    externalId: "PR-468",
    title: "Review PR #468",
    description: "Review caching updates and leave concise feedback.",
    source: "Jira",
    type: "Review",
    priority: "Low",
    status: "Done",
    impact: 4,
    time: 20,
    actualMinutes: 25,
    xp: 30,
    workingToday: false,
    completedAt: nowIso(),
    notes: "Cache invalidation looked good. Suggested a smaller TTL for the checkout path.",
    labels: ["review"],
  }),
  normalizeTask({
    id: "OUT-902",
    externalId: "OUT-902",
    title: "Team retrospective",
    description: "Capture action items from the sprint retrospective.",
    source: "Outlook",
    type: "Meeting",
    priority: "Medium",
    status: "Upcoming",
    impact: 6,
    time: 60,
    xp: 60,
    workingToday: true,
    startDate: todayKey(),
    notes: "Bring release readiness and CI stability as discussion topics.",
    labels: ["meeting"],
  }),
];

export const readStoredTasks = () => {
  const storedTasks = readStoredJson(TASKS_STORAGE_KEY, null);
  return Array.isArray(storedTasks) ? storedTasks.map(normalizeTask) : initialTasks;
};

export const schedule = [
  { time: "09:00 AM", title: "Daily Standup", duration: "30m", durationMinutes: 30, color: "purple" },
  { time: "10:00 AM", title: "Architecture Review", duration: "1h", durationMinutes: 60, color: "orange" },
  { time: "11:30 AM", title: "Client Sync", duration: "1h", durationMinutes: 60, color: "blue" },
  { time: "01:00 PM", title: "Focus Time Block", duration: "2h 45m available", durationMinutes: 165, color: "green", focus: true },
];

export const defaultOverview = {
  meetingMinutes: 190,
  focusMinutes: 155,
  newLearnings: "Gateway sandbox timeout thresholds differ from production.",
  wentWell: "Review feedback was concise and actionable.",
  wentWrong: "Timeout details were split across a few systems.",
};

export const normalizeApiTask = (task) =>
  normalizeTask({
    id: String(task.external_id || task.task_id),
    taskId: task.task_id,
    rowVersion: task.row_version,
    externalId: task.external_id || "",
    title: task.title,
    description: task.description,
    source: task.external_source || "Custom",
    type: task.task_type || "Task",
    priority: task.priority || "Medium",
    status: task.status || "To Do",
    time: task.estimated_minutes || task.ai?.effort_minutes || 60,
    actualMinutes: task.actual_minutes || 0,
    xp: task.xp_value || 0,
    workingToday: Boolean(task.working_today),
    completedAt: task.completed_at,
    impact: task.ai?.impact_score || 5,
    priorityScore: task.ai?.priority_score,
    difficulty: task.ai?.difficulty,
    aiInsight: task.ai?.insight,
    notes: task.notes || "",
    workedDates: task.worked_dates || [],
    labels: [],
  });

export const normalizeApiSchedule = (events = []) =>
  events.map((event) => ({
    time: formatTime(event.start_at),
    title: event.title,
    duration: event.is_focus_block ? `${formatMinutes(event.duration_minutes)} available` : formatMinutes(event.duration_minutes),
    durationMinutes: event.duration_minutes,
    color: event.is_focus_block ? "green" : "blue",
    focus: Boolean(event.is_focus_block),
  }));

export const emptyTaskForm = {
  title: "",
  description: "",
  source: "Custom",
  externalId: "",
  projectKey: "",
  type: "Task",
  priority: "Medium",
  status: "To Do",
  dueDate: "",
  startDate: "",
  estimatedMinutes: 60,
  actualMinutes: 0,
  xp: 60,
  labels: "",
  notes: "",
  workingToday: true,
  runAiEnrichment: true,
};

export const formFromTask = (task) => ({
  title: task.title || "",
  description: task.description || "",
  source: task.source || "Custom",
  externalId: task.externalId || task.id || "",
  projectKey: task.projectKey || "",
  type: task.type || "Task",
  priority: task.priority || "Medium",
  status: task.status || "To Do",
  dueDate: task.dueDate || "",
  startDate: task.startDate || "",
  estimatedMinutes: task.time || 60,
  actualMinutes: task.actualMinutes || 0,
  xp: task.xp || 60,
  labels: (task.labels || []).join(", "),
  notes: task.notes || "",
  workingToday: Boolean(task.workingToday),
  runAiEnrichment: true,
});

export const taskFromForm = (form, existingTask) => {
  const status = form.status || "To Do";
  const completedAt = status === "Done" ? existingTask?.completedAt || nowIso() : existingTask?.completedAt && existingTask.status === "Done" ? undefined : existingTask?.completedAt;
  return normalizeTask({
    ...(existingTask || {}),
    id: existingTask?.id || makeTaskId(form.source, form.externalId),
    externalId: form.externalId || existingTask?.externalId || "",
    projectKey: form.projectKey,
    title: form.title.trim(),
    description: form.description,
    source: form.source,
    type: form.type,
    priority: form.priority,
    status,
    dueDate: form.dueDate,
    startDate: form.startDate,
    time: parseNumber(form.estimatedMinutes, 60),
    actualMinutes: parseNumber(form.actualMinutes, 0),
    xp: parseNumber(form.xp, 60),
    labels: form.labels,
    notes: form.notes,
    workingToday: form.workingToday,
    completedAt,
    aiInsight: form.runAiEnrichment ? "" : existingTask?.aiInsight,
  });
};
