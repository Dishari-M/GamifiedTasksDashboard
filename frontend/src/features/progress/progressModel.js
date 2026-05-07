import { addDaysKey, todayKey } from "../../utils/dateTime";
import { earnedXpForTasks } from "../rewards/xpRewards";

const normalizeDateKey = (value) => {
  const text = String(value || "").trim();
  return /^\d{4}-\d{2}-\d{2}$/.test(text) ? text : "";
};

const uniqueSortedDates = (dates = []) => [...new Set(
  dates
    .map(normalizeDateKey)
    .filter(Boolean),
)].sort();

export const deriveTotalXp = (tasks = [], focusSessions = []) => (
  earnedXpForTasks(tasks.filter((task) => task.status === "Done"), focusSessions)
);

export const mergeMonotonicTotalXp = (derivedTotalXp = 0, persistedTotalXp = 0) => (
  Math.max(0, Number(derivedTotalXp || 0), Number(persistedTotalXp || 0))
);

export const mergeCompletedQuestDates = (completedQuestDates = [], questRun = null) => {
  const merged = uniqueSortedDates(completedQuestDates);
  if (!questRun?.workDate) return merged;
  const hasCompletedQuestToday = (questRun.quests || []).some((quest) => quest.state === "completed");
  if (!hasCompletedQuestToday) return merged;
  return uniqueSortedDates([...merged, questRun.workDate]);
};

export const deriveQuestStreak = ({ completedQuestDates = [], questRun = null, referenceDate = todayKey() } = {}) => {
  const dateSet = new Set(mergeCompletedQuestDates(completedQuestDates, questRun));
  let streak = 0;
  let cursor = normalizeDateKey(referenceDate) || todayKey();
  while (dateSet.has(cursor)) {
    streak += 1;
    cursor = addDaysKey(cursor, -1);
  }
  return streak;
};

export const buildProgressSnapshot = ({
  tasks = [],
  focusSessions = [],
  questProgress = null,
  questRun = null,
  referenceDate = todayKey(),
} = {}) => {
  const completedQuestDates = mergeCompletedQuestDates(questProgress?.completedQuestDates || [], questRun);
  return {
    totalXp: deriveTotalXp(tasks, focusSessions),
    streakDays: deriveQuestStreak({ completedQuestDates, referenceDate }),
    completedQuestDates,
    completedQuestDays: completedQuestDates.length,
    completedQuestCount: questProgress?.completedQuestCount || 0,
  };
};
