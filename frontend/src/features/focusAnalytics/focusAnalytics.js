import { addDaysKey, formatMinutes, todayKey } from "../../utils/dateTime";
import { parseNumber } from "../../utils/number";
import { sessionMinutes } from "../focus/focusSessions";
import { FOCUS_XP_MULTIPLIER, focusRewardsByTaskId, taskRewardDetails } from "../rewards/xpRewards";

export const FOCUS_ANALYTICS_PERIODS = [
  { label: "7 days", value: 7 },
  { label: "30 days", value: 30 },
  { label: "90 days", value: 90 },
];

const DAY_LABEL_FORMATTER = new Intl.DateTimeFormat("en", { month: "short", day: "numeric" });
const WEEKDAY_FORMATTER = new Intl.DateTimeFormat("en", { weekday: "long" });

export const dateKeyFromValue = (value) => {
  if (!value) return "";
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("en-CA");
};

export const sessionDayKey = (session) => session?.work_date || dateKeyFromValue(session?.started_at);

export const dateKeysBetween = (startDate, endDate) => {
  const keys = [];
  let current = startDate;
  while (current <= endDate) {
    keys.push(current);
    current = addDaysKey(current, 1);
  }
  return keys;
};

export const periodRange = (periodDays = 30, referenceDate = todayKey()) => {
  const days = Math.max(1, parseNumber(periodDays, 30));
  const end = dateKeyFromValue(referenceDate) || todayKey();
  return { start: addDaysKey(end, -(days - 1)), end, days };
};

const isWithinRange = (dateKey, range) => Boolean(dateKey && dateKey >= range.start && dateKey <= range.end);

const sessionStartHour = (session) => {
  const date = new Date(session?.started_at);
  return Number.isNaN(date.getTime()) ? null : date.getHours();
};

const timeWindowLabel = (hour) => {
  if (hour === null) return "Unknown";
  if (hour < 10) return "Early";
  if (hour < 13) return "Morning";
  if (hour < 17) return "Afternoon";
  if (hour < 21) return "Evening";
  return "Late";
};

const makeDailyRows = (range) => dateKeysBetween(range.start, range.end).map((date) => ({
  date,
  label: DAY_LABEL_FORMATTER.format(new Date(`${date}T12:00:00`)),
  minutes: 0,
  sessions: 0,
  xp: 0,
}));

const buildSessionRows = (focusSessions, range) => {
  const rows = makeDailyRows(range);
  const rowByDate = Object.fromEntries(rows.map((row) => [row.date, row]));
  const sessions = focusSessions.filter((session) => isWithinRange(sessionDayKey(session), range));

  sessions.forEach((session) => {
    const day = sessionDayKey(session);
    if (!rowByDate[day]) return;
    rowByDate[day].minutes += sessionMinutes(session);
    rowByDate[day].sessions += 1;
  });

  return { rows, sessions };
};

const weekKeyForDate = (dateKey) => {
  const date = new Date(`${dateKey}T12:00:00`);
  const day = date.getDay() || 7;
  date.setDate(date.getDate() - day + 1);
  return date.toLocaleDateString("en-CA");
};

const buildWeeklyRows = (dailyRows) => {
  const weeks = dailyRows.reduce((acc, row) => {
    const key = weekKeyForDate(row.date);
    acc[key] = acc[key] || { week: key, label: `Week of ${DAY_LABEL_FORMATTER.format(new Date(`${key}T12:00:00`))}`, minutes: 0, sessions: 0, xp: 0 };
    acc[key].minutes += row.minutes;
    acc[key].sessions += row.sessions;
    acc[key].xp += row.xp;
    return acc;
  }, {});
  return Object.values(weeks);
};

const completedTasksForRange = (tasks, range) => tasks.filter((task) => task.status === "Done" && isWithinRange(dateKeyFromValue(task.completedAt || task.completed_at), range));

const xpForCompletedTasks = (tasks, focusSessions, range, dailyRows) => {
  const rowByDate = Object.fromEntries(dailyRows.map((row) => [row.date, row]));
  let baseXp = 0;
  let focusBonusXp = 0;
  const rewardsByTask = focusRewardsByTaskId(focusSessions);

  completedTasksForRange(tasks, range).forEach((task) => {
    const completedDay = dateKeyFromValue(task.completedAt || task.completed_at);
    const focusMinutes = focusSessions
      .filter((session) => session.task_id === task.id && sessionDayKey(session) === completedDay)
      .reduce((sum, session) => sum + sessionMinutes(session), 0);
    const taskReward = rewardsByTask[task.id] || { focusMinutes: 0, rewardMultiplier: FOCUS_XP_MULTIPLIER };
    const reward = taskRewardDetails(task, focusMinutes, taskReward.rewardMultiplier);
    baseXp += reward.baseXp;
    focusBonusXp += reward.focusBonusXp;
    if (rowByDate[completedDay]) rowByDate[completedDay].xp += reward.rewardXp;
  });

  return {
    baseXp,
    focusBonusXp,
    totalXp: baseXp + focusBonusXp,
    breakdown: [
      { name: "Base XP", value: baseXp },
      { name: `Focus bonus (thresholded, up to ${FOCUS_XP_MULTIPLIER}x)`, value: focusBonusXp },
    ].filter((item) => item.value > 0),
  };
};

const streakFromRows = (dailyRows, referenceDate = todayKey()) => {
  const activeDays = new Set(dailyRows.filter((row) => row.minutes > 0).map((row) => row.date));
  let streak = 0;
  let cursor = dateKeyFromValue(referenceDate) || todayKey();
  while (activeDays.has(cursor)) {
    streak += 1;
    cursor = addDaysKey(cursor, -1);
  }
  return streak;
};

const bestFocusWindow = (sessions) => {
  const windows = ["Early", "Morning", "Afternoon", "Evening", "Late", "Unknown"].map((label) => ({ label, minutes: 0, sessions: 0 }));
  const byLabel = Object.fromEntries(windows.map((item) => [item.label, item]));
  sessions.forEach((session) => {
    const label = timeWindowLabel(sessionStartHour(session));
    byLabel[label].minutes += sessionMinutes(session);
    byLabel[label].sessions += 1;
  });
  return windows;
};

const weekdayRows = (dailyRows) => {
  const rows = {};
  dailyRows.forEach((row) => {
    const label = WEEKDAY_FORMATTER.format(new Date(`${row.date}T12:00:00`));
    rows[label] = rows[label] || { label, activeDays: 0, minutes: 0 };
    if (row.minutes > 0) rows[label].activeDays += 1;
    rows[label].minutes += row.minutes;
  });
  return Object.values(rows);
};

const previousPeriodMinutes = (focusSessions, range) => {
  const previous = {
    start: addDaysKey(range.start, -range.days),
    end: addDaysKey(range.start, -1),
  };
  return focusSessions
    .filter((session) => isWithinRange(sessionDayKey(session), previous))
    .reduce((sum, session) => sum + sessionMinutes(session), 0);
};

const formatImprovement = (currentMinutes, previousMinutes) => {
  if (previousMinutes <= 0 && currentMinutes > 0) return "New focus activity this period.";
  if (previousMinutes <= 0) return "No previous period focus yet.";
  const delta = currentMinutes - previousMinutes;
  const percent = Math.round((delta / previousMinutes) * 100);
  if (percent === 0) return "Focus time is steady versus the previous period.";
  return `${Math.abs(percent)}% ${percent > 0 ? "higher" : "lower"} than the previous period.`;
};

export const buildFocusAnalytics = ({ focusSessions = [], tasks = [], periodDays = 30, referenceDate = todayKey() } = {}) => {
  const range = periodRange(periodDays, referenceDate);
  const { rows: dailyRows, sessions } = buildSessionRows(focusSessions, range);
  const xp = xpForCompletedTasks(tasks, focusSessions, range, dailyRows);
  const weeklyRows = buildWeeklyRows(dailyRows);
  const totalMinutes = dailyRows.reduce((sum, row) => sum + row.minutes, 0);
  const completedSessions = sessions.length;
  const activeDays = dailyRows.filter((row) => row.minutes > 0);
  const previousMinutes = previousPeriodMinutes(focusSessions, range);
  const deepMinutes = sessions.filter((session) => sessionMinutes(session) >= 25).reduce((sum, session) => sum + sessionMinutes(session), 0);
  const lightMinutes = Math.max(0, totalMinutes - deepMinutes);
  const bestDay = [...dailyRows].sort((a, b) => b.minutes - a.minutes)[0];
  const bestXpDay = [...dailyRows].sort((a, b) => b.xp - a.xp)[0];
  const consistentDay = weekdayRows(dailyRows).sort((a, b) => b.activeDays - a.activeDays || b.minutes - a.minutes)[0];
  const focusWindows = bestFocusWindow(sessions);
  const topWindow = [...focusWindows].sort((a, b) => b.minutes - a.minutes)[0];

  return {
    range,
    dailyRows,
    weeklyRows,
    focusWindows,
    xpBreakdown: xp.breakdown,
    focusDepth: [
      { name: "Deep work", value: deepMinutes },
      { name: "Light focus", value: lightMinutes },
    ].filter((item) => item.value > 0),
    stats: {
      totalMinutes,
      totalFocusLabel: formatMinutes(totalMinutes),
      completedSessions,
      averageSessionMinutes: completedSessions ? Math.round(totalMinutes / completedSessions) : 0,
      activeDays: activeDays.length,
      consistencyPercent: Math.round((activeDays.length / range.days) * 100),
      currentStreak: streakFromRows(dailyRows, referenceDate),
      totalXp: xp.totalXp,
      baseXp: xp.baseXp,
      focusBonusXp: xp.focusBonusXp,
      previousMinutes,
      improvementLabel: formatImprovement(totalMinutes, previousMinutes),
      insufficientData: activeDays.length < 2,
      isEmpty: completedSessions === 0 && xp.totalXp === 0,
    },
    insights: {
      bestDay: bestDay?.minutes > 0 ? `${bestDay.label} had the most focus: ${formatMinutes(bestDay.minutes)}.` : "No focus day stands out yet.",
      bestXpDay: bestXpDay?.xp > 0 ? `${bestXpDay.label} had the highest XP gain: ${bestXpDay.xp} XP.` : "Complete focused work to see XP gain patterns.",
      mostConsistentDay: consistentDay?.activeDays > 0 ? `${consistentDay.label} is your most consistent focus day.` : "Build a few focus days to identify consistency.",
      bestWindow: topWindow?.minutes > 0 ? `${topWindow.label} is your strongest focus window.` : "Save focus sessions to find your best time window.",
      improvement: formatImprovement(totalMinutes, previousMinutes),
    },
  };
};
