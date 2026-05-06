import { todayKey } from "../../utils/dateTime";
import { parseNumber } from "../../utils/number";
import { sessionsForDay, sessionMinutes } from "../focus/focusSessions";

export const FOCUS_XP_MULTIPLIER = 1.25;

export const formatFocusMultiplier = (multiplier = FOCUS_XP_MULTIPLIER) => `${multiplier}x`;

export const focusRewardsByTaskId = (focusSessions = [], day = null) => {
  const sessions = day ? sessionsForDay(focusSessions, day) : focusSessions;
  return sessions.reduce((acc, session) => {
    if (!session.task_id) return acc;
    const entry = acc[session.task_id] || { focusMinutes: 0, rewardMultiplier: FOCUS_XP_MULTIPLIER };
    entry.focusMinutes += sessionMinutes(session);
    entry.rewardMultiplier = Number(session.xp_multiplier || entry.rewardMultiplier || FOCUS_XP_MULTIPLIER);
    acc[session.task_id] = entry;
    return acc;
  }, {});
};

export const focusMinutesByTaskId = (focusSessions = [], day = null) => {
  const rewardsByTask = focusRewardsByTaskId(focusSessions, day);
  return Object.fromEntries(Object.entries(rewardsByTask).map(([taskId, entry]) => [taskId, entry.focusMinutes]));
};

export const taskRewardDetails = (task, focusMinutes = 0, rewardMultiplier = FOCUS_XP_MULTIPLIER) => {
  const baseXp = parseNumber(task?.xp ?? task?.xp_value, 0);
  const hasFocusReward = parseNumber(focusMinutes, 0) > 0;
  const appliedMultiplier = hasFocusReward ? Number(rewardMultiplier || FOCUS_XP_MULTIPLIER) : 1;
  const rewardXp = Math.round(baseXp * appliedMultiplier);
  return {
    baseXp,
    focusBonusXp: Math.max(0, rewardXp - baseXp),
    focusMinutes: parseNumber(focusMinutes, 0),
    hasFocusReward,
    rewardMultiplier: appliedMultiplier,
    rewardXp,
  };
};

export const taskRewardDetailsFromSessions = (task, focusSessions = [], day = null) => {
  const taskReward = focusRewardsByTaskId(focusSessions, day)[task?.id] || { focusMinutes: 0, rewardMultiplier: FOCUS_XP_MULTIPLIER };
  return taskRewardDetails(task, taskReward.focusMinutes, taskReward.rewardMultiplier);
};

export const earnedXpForTasks = (tasks = [], focusSessions = [], day = null) => {
  const rewardsByTask = focusRewardsByTaskId(focusSessions, day);
  return tasks.reduce((sum, task) => {
    const taskReward = rewardsByTask[task.id] || { focusMinutes: 0, rewardMultiplier: FOCUS_XP_MULTIPLIER };
    return sum + taskRewardDetails(task, taskReward.focusMinutes, taskReward.rewardMultiplier).rewardXp;
  }, 0);
};

export const todaysEarnedXpForTasks = (tasks = [], focusSessions = []) => earnedXpForTasks(tasks, focusSessions, todayKey());
