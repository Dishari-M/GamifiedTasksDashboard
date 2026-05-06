# Phase 13 AI Insights Implementation

Phase 13 adds opt-in AI insight generation for the existing AI Insights page. The page can load safely without calling an external model, and a user action can generate a fresh AI response when needed.

## Scope

| Area | Status | Notes |
| --- | --- | --- |
| `GET /api/v1/insights/today` | Implemented | Returns capacity, task insights, completed tasks, and the latest successful generated insight when available. |
| `POST /api/v1/insights/today/generate` | Implemented | Generates or reuses a daily insight and stores generated runs in local `AI_RUNS`. |
| AI Insights UI wiring | Implemented | Existing AI Insights page loads the GET endpoint and uses a small opt-in AI button for generation. |
| Standup summary | Pending | Phase 14 owns generated standup notes. |
| OCI Agent historical questions | Pending | Future scope for historical blocker/trend questions over DB-backed data. |

## API Quick Reference

| Purpose | Method and path | Required header | Body | Persistence |
| --- | --- | --- | --- | --- |
| Fetch today's AI insight | `GET /api/v1/insights/today?date=YYYY-MM-DD` | `X-DevQuest-User-Id: user-1` | None | Does not create a run. Returns the latest successful `TODAY_INSIGHT` from `AI_RUNS` for that user/date, or deterministic fallback content if no run exists. |
| Generate today's AI insight | `POST /api/v1/insights/today/generate` | `X-DevQuest-User-Id: user-1` | `date`, `include_tasks`, `include_calendar`, `include_notes`, `force` | Creates a local `AI_RUNS` row when generation runs. With `force=false`, reuses the latest successful run for that user/date when present. With `force=true`, creates a fresh run. |

## Generate Request

```json
{
  "date": "2026-05-05",
  "include_tasks": true,
  "include_calendar": true,
  "include_notes": true,
  "force": true
}
```

## Response Data

Both endpoints return the same top-level envelope:

```json
{
  "data": {},
  "meta": {
    "request_id": "uuid"
  }
}
```

The `data` object contains:

| Field | Notes |
| --- | --- |
| `date` | Selected work date in `YYYY-MM-DD`. |
| `capacity` | Workday minutes, meeting minutes, available focus minutes, and suggested focus windows. |
| `task_insights` | Working-today task context ranked for insight generation. |
| `completed_tasks` | Tasks completed on the selected date. |
| `stat_insights` | Dynamic card labels comparing selected date metrics against the previous date. Backend-calculated values; AI must not invent these numbers. |
| `daily_insight` | Generated or fallback daily summary. |
| `risks` | Concise risks from generated output, empty array when none. |
| `recommendations` | Concise next-action recommendations. |
| `themes` | Short labels/themes extracted by AI or fallback logic. |
| `generated_at` | Timestamp from generated AI output; `null` for fallback content. |
| `ai_run_id` | `AI_RUNS.ai_run_id` when backed by a stored successful run; `null` when using fallback content. |

## Data Flow

1. Resolve the requested work date.
2. Read tasks for the current user from local work item storage.
3. Derive `working_today` from worked dates for the selected date.
4. Build task insight context from working-today tasks, completed tasks, notes, labels, XP, effort, impact, and priority score.
5. Add capacity and calendar context.
6. Build `stat_insights` by comparing selected-date metrics against the previous date.
7. For `GET`, return the latest successful `TODAY_INSIGHT` run if one exists; otherwise return fallback content.
8. For `POST`, reuse the latest successful run when `force=false`; otherwise create a new `AI_RUNS` row, call AI/mock generation, and mark the row `SUCCEEDED` or `FAILED`.

## Dynamic Stat Labels

`stat_insights` drives the highlighted sub-labels below AI Insights cards.

```json
{
  "stat_insights": {
    "total_xp": {
      "label": "30 XP more vs yesterday",
      "direction": "up",
      "current_value": 30,
      "previous_value": 0,
      "value_change": 30,
      "percent_change": null
    },
    "focus_minutes": {
      "label": "Same as yesterday",
      "direction": "neutral",
      "current_value": 165,
      "previous_value": 165,
      "value_change": 0,
      "percent_change": 0
    }
  }
}
```

The backend calculates `label`, `direction`, and numeric changes. AI may explain the impact using these values, but should not calculate or invent the comparison.

## AI Execution Switches

| Setting | Behavior |
| --- | --- |
| `DEVQUEST_AI_MODE=mock` | Uses deterministic local output; no external AI call. Good default for teammates without OCI setup. |
| `DEVQUEST_AI_MODE=real` | Enables external AI calls. |
| `DEVQUEST_AI_PROVIDER=oci_genai` | Uses OCI GenAI as the real provider. |
| `OCI_GENAI_MODEL_ID` | Stored on new `AI_RUNS.model_id` and used for real OCI GenAI calls. |
| OCI auth/env values | See `docs/oci-genai-team-setup.md` for temporary local setup and required values. |

## Postman Test

Generate:

```http
POST http://127.0.0.1:8000/api/v1/insights/today/generate
Content-Type: application/json
X-DevQuest-User-Id: user-1
```

```json
{
  "date": "2026-05-05",
  "include_tasks": true,
  "include_calendar": true,
  "include_notes": true,
  "force": true
}
```

Fetch latest generated or fallback:

```http
GET http://127.0.0.1:8000/api/v1/insights/today?date=2026-05-05
X-DevQuest-User-Id: user-1
```

## Notes For AI Assistants

- Do not make Phase 13 generation automatic on dashboard load.
- Keep AI generation opt-in from the UI.
- Keep `DEVQUEST_AI_MODE=mock` as the default so teammates without OCI setup can run locally.
- Do not commit local generated `backend/data/ai_runs.json` data unless the team explicitly changes the data strategy.
- Phase 8 dashboard AI insight is separate: it returns inline `ai_insight` on the dashboard response and does not persist to `AI_RUNS`.
