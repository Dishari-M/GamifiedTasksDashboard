import { parseNumber } from "../../utils/number";

export const DEFAULT_FOCUS_XP_CAP = 1.25;
export const FOCUS_UNLOCK_RATIO = 0.35;
export const FOCUS_UNLOCK_MIN = 10;
export const FOCUS_UNLOCK_MAX = 45;
export const XP_MIN = 20;
export const XP_MAX = 180;

const priorityScores = { Low: 5, Medium: 10, High: 18, Critical: 28 };
const difficultyScores = { Easy: 0, Medium: 6, Hard: 14 };
const typeModifiers = { Task: 6, Bug: 10, Epic: 16, Review: 5, Meeting: 3 };
const complexityModifiers = { NA: 0, XS: 0, S: 4, M: 8, L: 14, XL: 22 };

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const roundToNearestFive = (value) => Math.round(value / 5) * 5;

const normalizedDifficulty = (task = {}) => {
  const explicit = String(task.difficulty || task.ai?.difficulty || "").trim();
  if (difficultyScores[explicit] !== undefined) return explicit;
  const effort = estimatedMinutesForTask(task);
  const priorityScore = priorityScores[task.priority] || priorityScores.Medium;
  if (effort >= 120 || priorityScore >= priorityScores.Critical || String(task.type || "").trim() === "Epic") return "Hard";
  if (effort <= 30 && priorityScore <= priorityScores.Medium && String(task.type || "").trim() !== "Bug") return "Easy";
  return "Medium";
};

const normalizedComplexity = (task = {}) => {
  const raw = String(task.rcaTshirtSize || task.rca_tshirt_size || "NA").trim().toUpperCase();
  return complexityModifiers[raw] !== undefined ? raw : "NA";
};

export const estimatedMinutesForTask = (task = {}) => {
  const explicit = parseNumber(task.time ?? task.estimatedMinutes ?? task.estimated_minutes, 60);
  return clamp(Math.round(explicit), 15, 240);
};

export const deriveTaskXpBreakdown = (task = {}) => {
  const estimatedMinutes = estimatedMinutesForTask(task);
  const priorityScore = priorityScores[task.priority] || priorityScores.Medium;
  const impactScoreRaw = parseNumber(task.impact ?? task.ai?.impact_score ?? task.ai_impact_score, priorityScore / 2);
  const impactScore = clamp(Math.round(impactScoreRaw), 1, 10);
  const difficulty = normalizedDifficulty(task);
  const complexity = normalizedComplexity(task);
  const fileChangeCount = clamp(parseNumber(task.rcaFileChangeCount ?? task.rca_file_change_count, 0), 0, 40);
  const timeScore = clamp(roundToNearestFive((estimatedMinutes / 5) * 2), 10, 60);
  const impactXp = impactScore * 3;
  const fileChangeXp = fileChangeCount ? Math.min(12, roundToNearestFive(fileChangeCount / 2.5)) : 0;
  const rawXp = timeScore + priorityScore + impactXp + difficultyScores[difficulty] + (typeModifiers[task.type] || typeModifiers.Task) + complexityModifiers[complexity] + fileChangeXp;
  const xp = clamp(roundToNearestFive(rawXp), XP_MIN, XP_MAX);

  return {
    xp,
    estimatedMinutes,
    priorityScore,
    impactScore,
    difficulty,
    complexity,
    focusUnlockMinutes: focusUnlockThresholdMinutes(estimatedMinutes),
  };
};

export const deriveTaskXp = (task = {}) => {
  const explicit = task?.xp_value ?? task?.xp;
  if (explicit !== null && explicit !== undefined && String(explicit).trim() !== "") {
    const parsed = parseNumber(explicit, 0);
    if (parsed > 0) return Math.round(parsed);
  }
  return deriveTaskXpBreakdown(task).xp;
};

export const focusUnlockThresholdMinutes = (estimatedMinutes = 60) => {
  const effort = clamp(Math.round(parseNumber(estimatedMinutes, 60)), 15, 240);
  return clamp(Math.round(effort * FOCUS_UNLOCK_RATIO), FOCUS_UNLOCK_MIN, FOCUS_UNLOCK_MAX);
};

export const focusMultiplierForMinutes = (estimatedMinutes, focusMinutes, maxMultiplier = DEFAULT_FOCUS_XP_CAP) => {
  const effort = estimatedMinutesForTask({ estimatedMinutes });
  const minutes = Math.max(0, parseNumber(focusMinutes, 0));
  const rewardCap = Math.max(1, Number(maxMultiplier || DEFAULT_FOCUS_XP_CAP));
  const unlockMinutes = focusUnlockThresholdMinutes(effort);
  if (minutes < unlockMinutes || rewardCap <= 1) return 1;
  const focusRatio = minutes / Math.max(effort, 1);
  if (focusRatio >= 0.75) return rewardCap;
  if (focusRatio >= 0.5) return Math.min(rewardCap, 1.2);
  return Math.min(rewardCap, 1.1);
};

export const taskRewardDetailsWithThreshold = (task, focusMinutes = 0, persistedMultiplier = null, multiplierCap = DEFAULT_FOCUS_XP_CAP) => {
  const breakdown = deriveTaskXpBreakdown(task);
  const baseXp = deriveTaskXp(task);
  const minutes = Math.max(0, parseNumber(focusMinutes, 0));
  const unlockMinutes = breakdown.focusUnlockMinutes;
  const computedMultiplier = focusMultiplierForMinutes(breakdown.estimatedMinutes, minutes, multiplierCap);
  const savedMultiplier = Number(persistedMultiplier || 0);
  const rewardMultiplier = savedMultiplier > 1 ? savedMultiplier : computedMultiplier;
  const hasFocusReward = rewardMultiplier > 1;
  const rewardXp = Math.round(baseXp * rewardMultiplier);
  return {
    ...breakdown,
    baseXp,
    focusMinutes: minutes,
    unlockMinutes,
    hasFocusReward,
    rewardMultiplier,
    rewardXp,
    focusBonusXp: Math.max(0, rewardXp - baseXp),
    nextFocusUnlockMinutes: Math.max(0, unlockMinutes - minutes),
  };
};

export const xpRequiredForLevel = (level) => {
  const currentLevel = Math.max(1, Math.round(parseNumber(level, 1)));
  return 100 + 40 * (currentLevel - 1) + 12 * (currentLevel - 1) ** 2;
};

export const levelProgressFromXp = (xpValue) => {
  const totalXp = Math.max(0, parseNumber(xpValue, 0));
  let level = 1;
  let currentLevelStartXp = 0;
  let xpForNextLevel = xpRequiredForLevel(level);
  let nextLevelAtXp = xpForNextLevel;

  while (totalXp >= nextLevelAtXp) {
    level += 1;
    currentLevelStartXp = nextLevelAtXp;
    xpForNextLevel = xpRequiredForLevel(level);
    nextLevelAtXp += xpForNextLevel;
  }

  const currentLevelXp = totalXp - currentLevelStartXp;
  const progressPercent = Math.min(100, Math.round((currentLevelXp / Math.max(1, xpForNextLevel)) * 100));
  return {
    level,
    totalXp,
    currentLevelXp,
    xpForNextLevel,
    nextLevelAtXp,
    progressPercent,
  };
};

export const streakHeat = (streakDays = 0) => {
  const days = Math.max(0, parseNumber(streakDays, 0));
  if (days >= 15) return { tone: "blaze", label: "Blazing", description: "Legend-tier consistency." };
  if (days >= 10) return { tone: "ember", label: "On fire", description: "You are carrying serious heat." };
  if (days >= 6) return { tone: "spark", label: "Heating up", description: "Momentum is compounding." };
  if (days >= 3) return { tone: "steady", label: "Steady", description: "The routine is sticking." };
  if (days >= 1) return { tone: "warm", label: "Warming up", description: "Protect the streak tomorrow." };
  return { tone: "cool", label: "Cold start", description: "Complete a quest today to light the fuse." };
};
