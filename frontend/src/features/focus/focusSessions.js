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

export const sessionMinutes = (session) => parseNumber(session.duration_minutes, Math.ceil(parseNumber(session.duration_seconds, 0) / 60));

export const focusMinutesForSessions = (sessions) => sessions.reduce((sum, session) => sum + sessionMinutes(session), 0);

export const topFocusedTask = (sessions) => {
  const totals = sessions.reduce((acc, session) => {
    const key = session.task_id || "unassigned";
    acc[key] = acc[key] || { taskId: key, title: session.task_title || "Unassigned focus", minutes: 0, count: 0 };
    acc[key].minutes += sessionMinutes(session);
    acc[key].count += 1;
    return acc;
  }, {});
  return Object.values(totals).sort((a, b) => b.minutes - a.minutes)[0];
};

export const orderedFocusTasks = (tasks) => [
  ...tasks.filter((task) => task.workingToday && task.status !== "Done"),
  ...tasks.filter((task) => !task.workingToday && task.status !== "Done"),
];
