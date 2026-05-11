import { isSameDay, todayKey } from "../../utils/dateTime";
import { parseNumber } from "../../utils/number";

export const FOCUS_SESSIONS_STORAGE_KEY = "devquest.focusSessions.v1";
export const ACTIVE_FOCUS_STORAGE_KEY = "devquest.activeFocusSession.v1";
export const focusOutcomes = ["Progress made", "Blocked", "Ready for review", "Completed"];

export const createFocusId = () => {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `focus-${Date.now()}-${Math.floor(Math.random() * 100000)}`;
};

export const secondsBetween = (start, end = new Date()) => Math.max(0, Math.floor((new Date(end).getTime() - new Date(start).getTime()) / 1000));

export const activeFocusSeconds = (session) => {
  if (!session) return 0;
  return Math.max(0, Math.floor((session.accumulatedSeconds || 0) + (session.isRunning && session.lastStartedAt ? secondsBetween(session.lastStartedAt) : 0)));
};

export const isSessionOnDay = (session, day = todayKey()) => session?.work_date === day || isSameDay(session?.started_at, day);

export const sessionsForDay = (sessions, day = todayKey()) => sessions.filter((session) => isSessionOnDay(session, day));

export const sessionSeconds = (session) => {
  const explicitSeconds = parseNumber(session?.duration_seconds, Number.NaN);
  if (!Number.isNaN(explicitSeconds)) return Math.max(0, explicitSeconds);
  const focusSeconds = parseNumber(session?.focus_seconds, Number.NaN);
  if (!Number.isNaN(focusSeconds)) return Math.max(0, focusSeconds);
  const actualMinutes = parseNumber(session?.actual_minutes, Number.NaN);
  if (!Number.isNaN(actualMinutes)) return Math.max(0, actualMinutes * 60);
  const durationMinutes = parseNumber(session?.duration_minutes, Number.NaN);
  if (!Number.isNaN(durationMinutes)) return Math.max(0, durationMinutes * 60);
  return 0;
};

export const sessionMinutes = (session) => Math.floor(sessionSeconds(session) / 60);

export const focusMinutesForSessions = (sessions) => sessions.reduce((sum, session) => sum + sessionMinutes(session), 0);

export const focusSecondsForSessions = (sessions) => sessions.reduce((sum, session) => sum + sessionSeconds(session), 0);

export const topFocusedTask = (sessions) => {
  const totals = sessions.reduce((acc, session) => {
    const key = session.task_id || "unassigned";
    acc[key] = acc[key] || { taskId: key, title: session.task_title || "Unassigned focus", seconds: 0, count: 0 };
    acc[key].seconds += sessionSeconds(session);
    acc[key].count += 1;
    return acc;
  }, {});
  return Object.values(totals).sort((a, b) => b.seconds - a.seconds)[0];
};

export const orderedFocusTasks = (tasks) => [
  ...tasks.filter((task) => task.workingToday && task.status !== "Done"),
  ...tasks.filter((task) => !task.workingToday && task.status !== "Done"),
];
