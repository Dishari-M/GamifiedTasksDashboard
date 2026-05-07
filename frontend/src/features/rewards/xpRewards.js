import { todayKey } from "../../utils/dateTime";
import { sessionsForDay, sessionMinutes } from "../focus/focusSessions";
import { DEFAULT_FOCUS_XP_CAP, focusMultiplierForMinutes, focusUnlockThresholdMinutes, taskRewardDetailsWithThreshold } from "../progress/progressionMath";

export const FOCUS_XP_MULTIPLIER = DEFAULT_FOCUS_XP_CAP;

export const formatFocusMultiplier = (multiplier = FOCUS_XP_MULTIPLIER) => `${multiplier}x`;

export const focusRewardsByTaskId = (focusSessions = [], day = null) => {
  const sessions = day ? sessionsForDay(focusSessions, day) : focusSessions;
  return sessions.reduce((acc, session) => {
    if (!session.task_id) return acc;
    const entry = acc[session.task_id] || { focusMinutes: 0, rewardMultiplier: 1 };
    entry.focusMinutes += sessionMinutes(session);
    entry.rewardMultiplier = Number(session.xp_multiplier || entry.rewardMultiplier || 1);
    acc[session.task_id] = entry;
    return acc;
  }, {});
};

export const focusMinutesByTaskId = (focusSessions = [], day = null) => {
  const rewardsByTask = focusRewardsByTaskId(focusSessions, day);
  return Object.fromEntries(Object.entries(rewardsByTask).map(([taskId, entry]) => [taskId, entry.focusMinutes]));
};

export const taskRewardDetails = (task, focusMinutes = 0, rewardMultiplier = FOCUS_XP_MULTIPLIER) => {
  return taskRewardDetailsWithThreshold(task, focusMinutes, rewardMultiplier, FOCUS_XP_MULTIPLIER);
};

export const taskRewardDetailsFromSessions = (task, focusSessions = [], day = null) => {
  const taskReward = focusRewardsByTaskId(focusSessions, day)[task?.id] || { focusMinutes: 0, rewardMultiplier: 1 };
  return taskRewardDetails(task, taskReward.focusMinutes, taskReward.rewardMultiplier);
};

export const earnedXpForTasks = (tasks = [], focusSessions = [], day = null) => {
  const rewardsByTask = focusRewardsByTaskId(focusSessions, day);
  return tasks.reduce((sum, task) => {
    const taskReward = rewardsByTask[task.id] || { focusMinutes: 0, rewardMultiplier: 1 };
    return sum + taskRewardDetails(task, taskReward.focusMinutes, taskReward.rewardMultiplier).rewardXp;
  }, 0);
};

export const todaysEarnedXpForTasks = (tasks = [], focusSessions = []) => earnedXpForTasks(tasks, focusSessions, todayKey());

export { focusMultiplierForMinutes, focusUnlockThresholdMinutes };
