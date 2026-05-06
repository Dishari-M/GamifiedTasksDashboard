# XP And Quest Streak Progress Implementation

This update makes XP and streak behave as one coherent progress system across Quests, Focus, the dashboard stats, and the sidebar card.

The main goal is that when a user completes quest-driven work, the progress UI updates immediately and uses the same reward math as the backend.

## Scope

| Area | Status | Notes |
| --- | --- | --- |
| Sidebar XP card | Implemented | Reads from a shared frontend progress model instead of stale dashboard-only totals. |
| Sidebar streak card | Implemented | No longer hardcoded. Uses a quest-based streak definition. |
| Quest completion XP sync | Implemented | Completing a quest updates local progress immediately, then refreshes backend-backed task and quest state. |
| Focus reward math | Implemented | Frontend reward logic now respects the persisted backend multiplier from saved focus sessions. |
| `GET /api/v1/quests/progress` | Implemented | Returns completed quest dates, completed quest count, and current streak for the selected date. |
| Unit and integration coverage | Implemented | Backend unit tests, frontend unit tests, and Playwright end-to-end verification were added or updated. |

## Streak Definition

Streak is now defined as:

> The number of consecutive calendar days, counting backward from the selected day, where the user completed at least one quest from that day's quest run.

Examples:

| Completed quest days | Reference date | Streak |
| --- | --- | --- |
| `2026-05-06` | `2026-05-06` | `1` |
| `2026-05-04`, `2026-05-05`, `2026-05-06` | `2026-05-06` | `3` |
| `2026-05-02`, `2026-05-04`, `2026-05-05`, `2026-05-06` | `2026-05-06` | `3` |
| `2026-05-03`, `2026-05-04`, `2026-05-05` | `2026-05-06` | `0` |

This keeps streak tied to meaningful quest completion rather than arbitrary page visits or focus-only activity.

## API Quick Reference

| Purpose | Method and path | Required header | Body | Persistence |
| --- | --- | --- | --- | --- |
| Read today’s quest run | `GET /api/v1/quests/today?date=YYYY-MM-DD` | `X-DevQuest-User-Id: user-1` | None | Reads Oracle `QUEST_PLANS` / `QUEST_ITEMS` for the selected day. |
| Generate quest run | `POST /api/v1/quests/generate` | `X-DevQuest-User-Id: user-1` | `quest_date`, optional `candidate_task_ids`, `max_quests` | Creates or regenerates the selected day’s quest plan/items. |
| Update quest state | `PATCH /api/v1/quests/{quest_item_id}` | `X-DevQuest-User-Id: user-1` | `action=activate|skip|complete` | Updates Oracle quest item state and advances the active quest. |
| Save focus session | `POST /api/v1/focus-sessions` | `X-DevQuest-User-Id: user-1` | Saved focus payload | Persists `FOCUS_SESSIONS` and syncs focus reward data back to `QUEST_ITEMS`. |
| Read quest progress summary | `GET /api/v1/quests/progress?date=YYYY-MM-DD` | `X-DevQuest-User-Id: user-1` | None | Reads historical completed quest dates/counts from Oracle for streak/progress. |

## Functional Workflow

### 1. User marks tasks as Working Today

1. Tasks are loaded from Oracle `WORK_ITEMS`.
2. Tasks selected for the day are tracked through `WORK_ITEM_WORK_DATES`.
3. The Quests page uses those Working Today tasks as the candidate set for quest generation.

### 2. User generates quests

1. Frontend calls `POST /api/v1/quests/generate`.
2. Backend creates or refreshes the quest plan in Oracle `QUEST_PLANS` and `QUEST_ITEMS`.
3. Frontend stores the returned run in `questRun`.
4. Frontend also refreshes `GET /api/v1/quests/progress` so the broader progress model stays aligned.

### 3. User starts focus from a quest

1. The timer starts immediately in the UI.
2. The linked quest is activated through `PATCH /api/v1/quests/{quest_item_id}` with `action=activate`.
3. The active session stays local until the user stops and saves it.

### 4. User saves the focus session

1. Frontend sends `POST /api/v1/focus-sessions`.
2. Backend persists the session to `FOCUS_SESSIONS`.
3. Backend syncs the related quest item’s:
   - `FOCUS_MINUTES`
   - `REWARD_MULTIPLIER`
   - `FOCUS_BONUS_XP`
   - `REWARD_XP`
4. Frontend stores the saved session locally and refreshes the quest run when needed.

### 5. User completes the quest

1. Frontend calls `PATCH /api/v1/quests/{quest_item_id}` with `action=complete`.
2. Backend:
   - marks the task `Done`
   - sets task completion metadata
   - marks the quest item `COMPLETED`
   - advances the active quest inside the same run
3. Frontend immediately updates:
   - local task status
   - local quest run
   - floating completion notice
   - shared XP/streak progress snapshot
4. Frontend then refreshes Oracle-backed task and quest-progress state in the background.

## XP Logic

XP is now calculated from one consistent rule:

1. Base XP comes from the completed task’s `xp` / `xp_value`.
2. If a saved focus session exists for that task on that day, the reward multiplier comes from the saved session’s persisted `xp_multiplier`.
3. Reward XP is:

```text
reward_xp = round(base_xp * reward_multiplier)
```

4. Focus bonus XP is:

```text
focus_bonus_xp = max(0, reward_xp - base_xp)
```

This means the following UI surfaces now agree:

- quest completion notice
- sidebar total XP card
- dashboard total XP stat
- focus analytics XP breakdown

## Frontend Progress Model

The sidebar and dashboard no longer depend on a stale dashboard-only XP number.

The frontend shared progress snapshot combines:

- current task completion state
- saved focus sessions and their real `xp_multiplier`
- quest progress summary from `GET /api/v1/quests/progress`
- current in-memory quest run for same-turn responsiveness

The model currently lives in:

- `frontend/src/features/progress/progressModel.js`

It is used to drive:

- total XP for the level card
- current quest streak for the streak card
- immediate progress updates right after quest completion

## Files Touched

Backend:

- `backend/repositories/quest_repository.py`
- `backend/routes/quests_routes.py`
- `backend/services/oracle_quest_service.py`

Frontend:

- `frontend/src/App.js`
- `frontend/src/api/client.js`
- `frontend/src/features/progress/progressModel.js`
- `frontend/src/features/rewards/xpRewards.js`
- `frontend/src/features/focusAnalytics/focusAnalytics.js`

Verification:

- `backend/tests/test_oracle_quest_progress.py`
- `frontend/src/features/progress/progressModel.test.js`
- `frontend/src/features/focusAnalytics/focusAnalytics.test.js`
- `frontend/scripts/playwright-quests-focus-e2e.mjs`

## Verification Performed

### Backend unit tests

```powershell
cd D:\Vibeathon\GamifiedTasksDashboard\backend
.\.venv\Scripts\python.exe -m unittest tests.test_oracle_quest_progress
```

### Frontend unit tests

```powershell
cd D:\Vibeathon\GamifiedTasksDashboard\frontend
npm test -- --watchAll=false --runInBand src/features/progress/progressModel.test.js src/features/focusAnalytics/focusAnalytics.test.js
```

### Frontend build

```powershell
cd D:\Vibeathon\GamifiedTasksDashboard\frontend
npm run build
```

### Playwright end-to-end flow

```powershell
cd D:\Vibeathon\GamifiedTasksDashboard\frontend
npm run ui:e2e:quests-focus
```

That browser flow verified:

1. create a Working Today task
2. generate quests
3. start focus from the quest
4. save focus session
5. complete the quest
6. confirm sidebar XP increases
7. confirm quest streak starts

## Notes For AI Assistants

- Do not reintroduce a hardcoded streak value in the sidebar.
- Do not derive XP from dashboard stats alone when quest/focus state can change locally before a dashboard refresh.
- Prefer the persisted session `xp_multiplier` over a hardcoded frontend multiplier when reward math is being shown to the user.
- When changing quest completion behavior, keep the immediate local progress update and the later backend refresh both intact.
