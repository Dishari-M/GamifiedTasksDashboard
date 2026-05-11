import { deriveTaskXp, focusMultiplierForMinutes, focusUnlockThresholdMinutes, levelProgressFromXp, streakHeat, taskRewardDetailsWithThreshold } from "./progressionMath";

test("task xp scales with multiple task factors", () => {
  expect(deriveTaskXp({
    title: "Tidy docs",
    type: "Task",
    priority: "Low",
    estimatedMinutes: 30,
    rcaTshirtSize: "NA",
  })).toBe(30);

  expect(deriveTaskXp({
    title: "Payments release hardening",
    type: "Epic",
    priority: "Critical",
    estimatedMinutes: 150,
    rcaTshirtSize: "L",
    impact: 9,
  })).toBe(160);
});

test("focus reward unlocks only after the threshold and scales toward the cap", () => {
  expect(focusUnlockThresholdMinutes(60)).toBe(21);
  expect(focusMultiplierForMinutes(60, 15, 1.25)).toBe(1);
  expect(focusMultiplierForMinutes(60, 25, 1.25)).toBe(1.1);
  expect(focusMultiplierForMinutes(60, 50, 1.25)).toBe(1.25);
});

test("reward details expose remaining minutes to unlock the focus bonus", () => {
  expect(taskRewardDetailsWithThreshold({ xp: 80, estimatedMinutes: 60 }, 15, null, 1.25)).toMatchObject({
    baseXp: 80,
    rewardXp: 80,
    hasFocusReward: false,
    nextFocusUnlockMinutes: 6,
  });

  expect(taskRewardDetailsWithThreshold({ xp: 80, estimatedMinutes: 60 }, 25, null, 1.25)).toMatchObject({
    rewardXp: 88,
    hasFocusReward: true,
  });
});

test("level progression slows down as total xp grows", () => {
  expect(levelProgressFromXp(0)).toMatchObject({ level: 1, xpForNextLevel: 100 });
  expect(levelProgressFromXp(260)).toMatchObject({ level: 3, xpForNextLevel: 228 });
});

test("streak heat becomes hotter at higher streak counts", () => {
  expect(streakHeat(0).tone).toBe("cool");
  expect(streakHeat(4).tone).toBe("steady");
  expect(streakHeat(12).tone).toBe("ember");
});

test("streak heat can surface when a streak is about to break", () => {
  expect(streakHeat(5, { atRisk: true })).toMatchObject({
    tone: "risk",
    label: "At risk",
  });
});
