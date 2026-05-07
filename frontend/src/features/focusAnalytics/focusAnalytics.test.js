import { buildFocusAnalytics, dateKeysBetween, periodRange } from "./focusAnalytics";

const sessions = [
  {
    focus_session_id: "s1",
    task_id: "T-1",
    task_title: "Build API",
    work_date: "2026-05-05",
    started_at: "2026-05-05T14:00:00.000Z",
    duration_minutes: 50,
  },
  {
    focus_session_id: "s2",
    task_id: "T-2",
    task_title: "Review PR",
    work_date: "2026-05-04",
    started_at: "2026-05-04T09:00:00.000Z",
    duration_seconds: 900,
  },
  {
    focus_session_id: "s3",
    task_id: "T-1",
    task_title: "Build API",
    work_date: "2026-04-28",
    started_at: "2026-04-28T15:00:00.000Z",
    duration_minutes: 30,
  },
];

const tasks = [
  { id: "T-1", title: "Build API", status: "Done", xp: 100, completedAt: "2026-05-05T16:00:00.000Z" },
  { id: "T-2", title: "Review PR", status: "Done", xp: 40, completedAt: "2026-05-04T11:00:00.000Z" },
  { id: "T-3", title: "Future task", status: "To Do", xp: 80 },
];

test("builds inclusive period ranges", () => {
  expect(periodRange(7, "2026-05-05")).toEqual({ start: "2026-04-29", end: "2026-05-05", days: 7 });
  expect(dateKeysBetween("2026-05-03", "2026-05-05")).toEqual(["2026-05-03", "2026-05-04", "2026-05-05"]);
});

test("summarizes focus time and average session length", () => {
  const analytics = buildFocusAnalytics({ focusSessions: sessions, tasks, periodDays: 7, referenceDate: "2026-05-05" });

  expect(analytics.stats.totalMinutes).toBe(65);
  expect(analytics.stats.completedSessions).toBe(2);
  expect(analytics.stats.averageSessionMinutes).toBe(33);
  expect(analytics.stats.currentStreak).toBe(2);
});

test("separates base XP from focus bonus XP", () => {
  const analytics = buildFocusAnalytics({ focusSessions: sessions, tasks, periodDays: 7, referenceDate: "2026-05-05" });

  expect(analytics.stats.baseXp).toBe(140);
  expect(analytics.stats.focusBonusXp).toBe(25);
  expect(analytics.stats.totalXp).toBe(165);
});

test("uses the configured focus multiplier in XP analytics", () => {
  const analytics = buildFocusAnalytics({ focusSessions: sessions, tasks, periodDays: 7, referenceDate: "2026-05-05", focusMultiplier: 2 });

  expect(analytics.stats.baseXp).toBe(140);
  expect(analytics.stats.focusBonusXp).toBe(100);
  expect(analytics.stats.totalXp).toBe(240);
  expect(analytics.xpBreakdown).toContainEqual({ name: "Focus bonus (thresholded, up to 2x)", value: 100 });
});

test("classifies deep and light focus minutes", () => {
  const analytics = buildFocusAnalytics({ focusSessions: sessions, tasks: [], periodDays: 7, referenceDate: "2026-05-05" });

  expect(analytics.focusDepth).toEqual([
    { name: "Deep work", value: 50 },
    { name: "Light focus", value: 15 },
  ]);
});

test("handles previous-period comparison without misleading percentages", () => {
  const analytics = buildFocusAnalytics({ focusSessions: sessions, tasks: [], periodDays: 7, referenceDate: "2026-05-05" });

  expect(analytics.stats.previousMinutes).toBe(30);
  expect(analytics.stats.improvementLabel).toBe("117% higher than the previous period.");
});
