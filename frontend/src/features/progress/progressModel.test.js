import { buildProgressSnapshot, deriveQuestStreak, deriveTotalXp, mergeCompletedQuestDates, mergeMonotonicTotalXp } from "./progressModel";

const focusSessions = [
  {
    focus_session_id: "focus-1",
    task_id: "T-1",
    work_date: "2026-05-06",
    duration_minutes: 25,
  },
];

const tasks = [
  { id: "T-1", title: "Quest task", status: "Done", xp: 60, completedAt: "2026-05-06T10:00:00.000Z" },
  { id: "T-2", title: "Open task", status: "To Do", xp: 30 },
];

test("derives total xp from completed tasks plus focus reward rules", () => {
  expect(deriveTotalXp(tasks, focusSessions)).toBe(66);
});

test("keeps total xp monotonic when a stale reload computes a lower value", () => {
  expect(mergeMonotonicTotalXp(66, 0)).toBe(66);
  expect(mergeMonotonicTotalXp(0, 85)).toBe(85);
  expect(mergeMonotonicTotalXp(70, 85)).toBe(85);
});

test("merges today's completed quest from the active run into streak data", () => {
  const merged = mergeCompletedQuestDates(["2026-05-04", "2026-05-05"], {
    workDate: "2026-05-06",
    quests: [{ id: "quest-1", state: "completed" }],
  });
  expect(merged).toEqual(["2026-05-04", "2026-05-05", "2026-05-06"]);
});

test("calculates a consecutive quest streak from completed quest days", () => {
  expect(deriveQuestStreak({
    completedQuestDates: ["2026-05-03", "2026-05-04", "2026-05-06"],
    referenceDate: "2026-05-06",
  })).toBe(1);

  expect(deriveQuestStreak({
    completedQuestDates: ["2026-05-04", "2026-05-05", "2026-05-06"],
    referenceDate: "2026-05-06",
  })).toBe(3);
});

test("builds a cohesive sidebar progress snapshot", () => {
  const snapshot = buildProgressSnapshot({
    tasks,
    focusSessions,
    questProgress: { completedQuestDates: ["2026-05-05"], completedQuestCount: 4 },
    questRun: { workDate: "2026-05-06", quests: [{ id: "quest-1", state: "completed" }] },
    referenceDate: "2026-05-06",
  });

  expect(snapshot.totalXp).toBe(66);
  expect(snapshot.streakDays).toBe(2);
  expect(snapshot.completedQuestDates).toEqual(["2026-05-05", "2026-05-06"]);
  expect(snapshot.completedQuestCount).toBe(4);
});
