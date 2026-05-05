import { todayKey } from "../../utils/dateTime";
import { parseNumber } from "../../utils/number";
import { sessionsForDay, sessionMinutes } from "../focus/focusSessions";

export const FOCUS_XP_MULTIPLIER = 1.5;

export const formatFocusMultiplier = (multiplier = FOCUS_XP_MULTIPLIER) => `${multiplier}x`;

export const focusMinutesByTaskId = (focusSessions = [], day = null) => {
  const sessions = day ? sessionsForDay(focusSessions, day) : focusSessions;
  return sessions.reduce((acc, session) => {
    if (!session.task_id) return acc;
    acc[session.task_id] = (acc[session.task_id] || 0) + sessionMinutes(session);
    return acc;
  }, {});
};

export const taskRewardDetails = (task, focusMinutes = 0) => {
  const baseXp = parseNumber(task?.xp ?? task?.xp_value, 0);
  const hasFocusReward = parseNumber(focusMinutes, 0) > 0;
  const rewardMultiplier = hasFocusReward ? FOCUS_XP_MULTIPLIER : 1;
  const rewardXp = Math.round(baseXp * rewardMultiplier);
  return {
    baseXp,
    focusBonusXp: Math.max(0, rewardXp - baseXp),
    focusMinutes: parseNumber(focusMinutes, 0),
    hasFocusReward,
    rewardMultiplier,
    rewardXp,
  };
};

export const taskRewardDetailsFromSessions = (task, focusSessions = [], day = null) => {
  const focusByTask = focusMinutesByTaskId(focusSessions, day);
  return taskRewardDetails(task, focusByTask[task?.id] || 0);
};

export const earnedXpForTasks = (tasks = [], focusSessions = [], day = null) => {
  const focusByTask = focusMinutesByTaskId(focusSessions, day);
  return tasks.reduce((sum, task) => sum + taskRewardDetails(task, focusByTask[task.id] || 0).rewardXp, 0);
};

export const todaysEarnedXpForTasks = (tasks = [], focusSessions = []) => earnedXpForTasks(tasks, focusSessions, todayKey());
