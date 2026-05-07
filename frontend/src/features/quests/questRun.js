import { formatDateTime, formatMinutes, nowIso, todayKey } from "../../utils/dateTime";
import { parseNumber } from "../../utils/number";
import { readStoredJson, removeStoredJson, writeStoredJson } from "../../utils/storage";
import { sessionsForDay } from "../focus/focusSessions";
import { focusMinutesByTaskId, taskRewardDetails } from "../rewards/xpRewards";

export const QUEST_PLAN_STORAGE_KEY = "devquest.questPlan.v1";
export const QUEST_RUN_STORAGE_KEY = "devquest.questRun.v1";
export const skipReasons = ["Blocked", "Not today", "Too large"];

const questPriorityRank = { Critical: 4, High: 3, Medium: 2, Low: 1 };
const questStatusRank = { "In Progress": 4, "To Do": 3, Blocked: 2, Upcoming: 1, Done: 0 };

export const compareQuestTasks = (a, b) => {
  const statusDiff = (questStatusRank[b.status] ?? 1) - (questStatusRank[a.status] ?? 1);
  if (statusDiff) return statusDiff;
  const scoreDiff = (b.priorityScore || 0) - (a.priorityScore || 0);
  if (scoreDiff) return scoreDiff;
  const priorityDiff = (questPriorityRank[b.priority] || 0) - (questPriorityRank[a.priority] || 0);
  if (priorityDiff) return priorityDiff;
  const impactDiff = parseNumber(b.impact, 0) - parseNumber(a.impact, 0);
  if (impactDiff) return impactDiff;
  return parseNumber(a.time, 0) - parseNumber(b.time, 0);
};

export const workingTodayTasks = (tasks) => tasks.filter((task) => task.workingToday);

export const defaultQuestOrder = (tasks) => [...workingTodayTasks(tasks)].sort(compareQuestTasks);

const taskQuestKeys = (task) => [
  task?.taskId,
  task?.id,
  task?.externalId,
].filter((value) => value !== undefined && value !== null && String(value).trim() !== "").map((value) => String(value));

const primaryQuestKeyForTask = (task) => taskQuestKeys(task)[0] || "";

const sortedTaskIds = (tasks) => tasks.map((task) => primaryQuestKeyForTask(task)).filter(Boolean).sort();
const sortedStringIds = (ids) => ids.map((id) => String(id)).sort();

const includesAllTaskIds = (sourceIds, candidateIds) => {
  if (!sourceIds.length) return false;
  const candidateSet = new Set(candidateIds);
  return sourceIds.every((id) => candidateSet.has(id));
};

const questRank = (quest) => parseNumber(quest?.rank ?? quest?.rank_order, 0);

const effectiveSourceTaskIds = (questRun) => {
  if (!questRun) return [];
  if (Array.isArray(questRun.sourceTaskIds) && questRun.sourceTaskIds.length) {
    return sortedStringIds(questRun.sourceTaskIds);
  }
  if (Array.isArray(questRun.quests) && questRun.quests.length) {
    const activeQuestCount = questRun.quests.filter((quest) => questRank(quest) > 0 && questRank(quest) <= questRun.quests.length).length || questRun.quests.length;
    return sortedStringIds(
      questRun.quests
        .filter((quest) => questRank(quest) > 0 && questRank(quest) <= activeQuestCount)
        .map((quest) => quest?.taskId)
        .filter(Boolean),
    );
  }
  return [];
};

const questIdForTask = (taskId) => `quest-${taskId}`;

const questReason = (task, index) => {
  if (task.status === "Blocked") return { label: "Unblock first", text: "Clear the dependency before adding more work on top." };
  if (task.status === "In Progress") return { label: "Continue", text: "This is already open, so finishing the thread protects momentum." };
  if (task.startDate === todayKey() || task.dueDate === todayKey()) return { label: "Scheduled", text: "It is tied to today, so it should stay visible in the route." };
  if (parseNumber(task.time, 0) <= 35) return { label: "Quick win", text: "Small enough to complete cleanly and bank progress." };
  if (parseNumber(task.impact, 0) >= 8 || task.priority === "Critical" || task.priority === "High") return { label: "High impact", text: "High priority and impact make it worth doing before lower leverage work." };
  return { label: index === 0 ? "Best next" : "Steady progress", text: `${task.priority} priority ${task.type.toLowerCase()} from ${task.source}, estimated at ${formatMinutes(task.time)}.` };
};

export const questActionLabel = (task) => {
  if (task.status === "Done") return "Completed";
  if (task.status === "Blocked") return "Resolve blocker";
  if (task.status === "In Progress") return "Continue";
  if (task.status === "Upcoming") return "Prepare";
  return "Start";
};

const questFocusTargetMinutes = (task) => {
  const effort = parseNumber(task.time, 60);
  if (effort <= 30) return effort;
  return Math.min(90, Math.max(25, Math.ceil((effort * 0.55) / 5) * 5));
};

const buildQuestForTask = (task, index) => {
  const reason = questReason(task, index);
  const reward = taskRewardDetails(task, 0);
  return {
    id: questIdForTask(task.id),
    taskId: task.id,
    rank: index + 1,
    state: task.status === "Done" ? "completed" : "queued",
    reason: `${reason.label}: ${reason.text}`,
    reasonLabel: reason.label,
    actionLabel: questActionLabel(task),
    baseXp: reward.baseXp,
    rewardXp: reward.rewardXp,
    focusBonusXp: reward.focusBonusXp,
    rewardMultiplier: reward.rewardMultiplier,
    hasFocusReward: reward.hasFocusReward,
    focusTargetMinutes: questFocusTargetMinutes(task),
    focusMinutes: 0,
    startedAt: null,
    completedAt: task.status === "Done" ? task.completedAt || nowIso() : null,
    skippedAt: null,
    skipReason: "",
  };
};

export const applyActiveQuest = (run) => {
  if (!run) return null;
  const openQuests = run.quests.filter((quest) => quest.state !== "completed" && quest.state !== "skipped");
  const activeQuestId = openQuests.find((quest) => quest.id === run.activeQuestId)?.id || openQuests[0]?.id || null;
  const quests = run.quests.map((quest) => {
    if (quest.state === "completed" || quest.state === "skipped") return quest;
    return {
      ...quest,
      state: quest.id === activeQuestId ? "active" : "queued",
      startedAt: quest.id === activeQuestId ? quest.startedAt || nowIso() : quest.startedAt,
    };
  });
  return {
    ...run,
    activeQuestId,
    status: openQuests.length ? run.status === "needs_update" ? "needs_update" : "active" : "completed",
    quests,
  };
};

export const isCurrentQuestRun = (questRun) => Boolean(questRun && questRun.workDate === todayKey());

export const isQuestRunSynced = (tasks, questRun) => {
  if (!isCurrentQuestRun(questRun)) return false;
  const sourceTaskIds = effectiveSourceTaskIds(questRun);
  if (!sourceTaskIds.length) return false;

  const currentWorkingIds = sortedStringIds(sortedTaskIds(workingTodayTasks(tasks)));
  const sourceSet = new Set(sourceTaskIds);
  const currentWorkingSet = new Set(currentWorkingIds);
  const unresolvedQuestIds = new Set(
    (questRun.quests || [])
      .filter((quest) => quest.state !== "completed" && quest.state !== "skipped")
      .map((quest) => String(quest.taskId)),
  );

  const hasNewWorkingTask = currentWorkingIds.some((taskId) => !sourceSet.has(taskId));
  if (hasNewWorkingTask) return false;

  const hasPendingQuestRemovedFromToday = [...unresolvedQuestIds].some((taskId) => !currentWorkingSet.has(taskId));
  if (hasPendingQuestRemovedFromToday) return false;

  return true;
};

export const deriveQuestProgress = (run, tasks, focusSessions = []) => {
  if (!isCurrentQuestRun(run)) return null;
  const taskById = new Map(tasks.map((task) => [task.id, task]));
  const todaySessions = sessionsForDay(focusSessions, run.workDate);
  const focusByTask = focusMinutesByTaskId(todaySessions);
  const synced = isQuestRunSynced(tasks, run);
  const quests = (run.quests || []).map((quest) => {
    const task = taskById.get(quest.taskId);
    const focusMinutes = focusByTask[quest.taskId] || 0;
    if (!task) return { ...quest, focusMinutes, state: quest.state === "active" ? "queued" : quest.state };
    const reward = taskRewardDetails(task, focusMinutes);
    if (quest.state === "skipped") return { ...quest, focusMinutes, baseXp: reward.baseXp, rewardXp: reward.rewardXp, focusBonusXp: reward.focusBonusXp, rewardMultiplier: reward.rewardMultiplier, hasFocusReward: reward.hasFocusReward, actionLabel: questActionLabel(task), focusTargetMinutes: quest.focusTargetMinutes || questFocusTargetMinutes(task) };
    const isCompleted = task.status === "Done";
    return {
      ...quest,
      focusMinutes,
      baseXp: reward.baseXp,
      rewardXp: reward.rewardXp,
      focusBonusXp: reward.focusBonusXp,
      rewardMultiplier: reward.rewardMultiplier,
      hasFocusReward: reward.hasFocusReward,
      actionLabel: questActionLabel(task),
      focusTargetMinutes: quest.focusTargetMinutes || questFocusTargetMinutes(task),
      state: isCompleted ? "completed" : quest.state,
      completedAt: isCompleted ? quest.completedAt || task.completedAt || nowIso() : quest.completedAt,
    };
  });
  return applyActiveQuest({ ...run, quests, status: synced ? run.status : "needs_update" });
};

export const generateQuestRun = (tasks, focusSessions = []) => {
  const orderedTasks = defaultQuestOrder(tasks);
  const run = {
    id: `quest-run-${todayKey()}-${Date.now()}`,
    workDate: todayKey(),
    generatedAt: nowIso(),
    sourceTaskIds: sortedTaskIds(workingTodayTasks(tasks)),
    activeQuestId: null,
    status: orderedTasks.length ? "active" : "not_generated",
    quests: orderedTasks.map(buildQuestForTask),
  };
  return deriveQuestProgress(applyActiveQuest(run), tasks, focusSessions);
};

const migrateQuestPlan = (questPlan, tasks, focusSessions = []) => {
  if (!questPlan || questPlan.workDate !== todayKey()) return null;
  const taskById = new Map(tasks.map((task) => [task.id, task]));
  const orderedTasks = (questPlan.orderedTaskIds || []).map((id) => taskById.get(id)).filter(Boolean);
  const run = {
    id: `quest-run-${questPlan.workDate}-${new Date(questPlan.generatedAt || nowIso()).getTime() || Date.now()}`,
    workDate: questPlan.workDate,
    generatedAt: questPlan.generatedAt || nowIso(),
    sourceTaskIds: questPlan.sourceTaskIds || sortedTaskIds(orderedTasks),
    activeQuestId: null,
    status: orderedTasks.length ? "active" : "not_generated",
    quests: orderedTasks.map(buildQuestForTask),
  };
  return deriveQuestProgress(applyActiveQuest(run), tasks, focusSessions);
};

export const readQuestRun = (tasks, focusSessions = []) => {
  const storedRun = readStoredJson(QUEST_RUN_STORAGE_KEY, null);
  if (storedRun?.workDate === todayKey() && Array.isArray(storedRun.quests)) return deriveQuestProgress(storedRun, tasks, focusSessions);
  return migrateQuestPlan(readStoredJson(QUEST_PLAN_STORAGE_KEY, null), tasks, focusSessions);
};

export const saveQuestRun = (run) => {
  if (!run || run.workDate !== todayKey()) return removeStoredJson(QUEST_RUN_STORAGE_KEY);
  writeStoredJson(QUEST_RUN_STORAGE_KEY, run);
  removeStoredJson(QUEST_PLAN_STORAGE_KEY);
};

export const clearQuestRun = () => {
  removeStoredJson(QUEST_RUN_STORAGE_KEY);
  removeStoredJson(QUEST_PLAN_STORAGE_KEY);
};

export const isUsableQuestRun = (tasks, questRun) => isCurrentQuestRun(questRun) && isQuestRunSynced(tasks, questRun) && questRun.status !== "not_generated";

export const hasGeneratedQuestRun = (questRun) => (
  isCurrentQuestRun(questRun)
  && Array.isArray(questRun?.quests)
  && questRun.quests.length > 0
  && questRun.status !== "not_generated"
);

export const getQuestOrderedTasks = (tasks, questRun) => {
  const todayTasks = workingTodayTasks(tasks);
  if (!isUsableQuestRun(tasks, questRun)) return defaultQuestOrder(tasks);
  const taskById = new Map(todayTasks.flatMap((task) => taskQuestKeys(task).map((key) => [key, task])));
  const ordered = (questRun.quests || []).map((quest) => taskById.get(String(quest.taskId))).filter(Boolean);
  const orderedIds = new Set(ordered.map((task) => task.id));
  const appended = todayTasks.filter((task) => !orderedIds.has(task.id)).sort(compareQuestTasks);
  return [...ordered, ...appended];
};

export const questRationale = (task, index) => {
  const reason = questReason(task, index);
  if (task.status === "Done") return "Completed today; it stays visible as earned progress.";
  return `${reason.label}: ${reason.text}`;
};

export const questGeneratedLabel = (tasks, questRun, taskCount) => {
  if (!isCurrentQuestRun(questRun)) return `${taskCount} Working Today task${taskCount === 1 ? "" : "s"} ready`;
  if (!isQuestRunSynced(tasks, questRun)) return `Working Today changed since ${formatDateTime(questRun.generatedAt)}. Update quests to refresh the route.`;
  if (questRun.status === "completed") return "Daily run completed. Review the summary or regenerate if the day changed.";
  return `Generated ${formatDateTime(questRun.generatedAt)} from ${taskCount} task${taskCount === 1 ? "" : "s"}`;
};

export const getQuestTask = (tasks, quest) => tasks.find((task) => taskQuestKeys(task).includes(String(quest?.taskId)));

export const getNextQuest = (questRun) => questRun?.quests?.find((quest) => quest.id === questRun.activeQuestId) || questRun?.quests?.find((quest) => quest.state === "queued");

export const getQuestById = (questRun, questId) => questRun?.quests?.find((quest) => String(quest.id) === String(questId));

export const getOpenQuestForTask = (questRun, taskId) => questRun?.quests?.find((quest) => String(quest.taskId) === String(taskId) && quest.state !== "completed" && quest.state !== "skipped");

export const questProgressSummary = (questRun) => {
  const quests = questRun?.quests || [];
  const completed = quests.filter((quest) => quest.state === "completed").length;
  const skipped = quests.filter((quest) => quest.state === "skipped").length;
  const earnedXp = quests.filter((quest) => quest.state === "completed").reduce((sum, quest) => sum + parseNumber(quest.rewardXp, 0), 0);
  const availableXp = quests.reduce((sum, quest) => sum + parseNumber(quest.rewardXp, 0), 0);
  const focusMinutes = quests.reduce((sum, quest) => sum + parseNumber(quest.focusMinutes, 0), 0);
  return { total: quests.length, completed, skipped, earnedXp, availableXp, focusMinutes };
};
