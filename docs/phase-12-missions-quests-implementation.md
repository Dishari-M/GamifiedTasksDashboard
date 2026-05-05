# Phase 12 Missions And Quests Implementation

Phase 12 adds AI-assisted mission ranking and quest-plan generation. Missions are recommendations only. Quests are persisted locally so the Quests page/backend can return the generated plan for the selected date.

## Scope

| Area | Status | Notes |
| --- | --- | --- |
| `POST /api/v1/missions/generate` | Implemented | Generates ranked mission recommendations from candidate tasks and capacity context. Does not mutate Working Today data. |
| `GET /api/v1/quests/today` | Implemented | Returns the generated quest plan when present, otherwise returns a fallback view of Working Today tasks. |
| `POST /api/v1/quests/generate` | Implemented | Generates a ranked quest plan, stores local quest plan/items, and marks selected tasks as worked on the quest date. |
| Real OCI GenAI | Implemented behind switch | Uses `DEVQUEST_AI_MODE=real` and `DEVQUEST_AI_PROVIDER=oci_genai`. |
| Oracle table persistence | Pending | Current implementation uses local JSON stores for hackathon/local dev. Production target remains `QUEST_PLANS`, `QUEST_ITEMS`, and `AI_RUNS`. |

## API Quick Reference

| Purpose | Method and path | Required header | Body | Persistence |
| --- | --- | --- | --- | --- |
| Generate mission recommendations | `POST /api/v1/missions/generate` | `X-DevQuest-User-Id: user-1` | `date`, optional `candidate_task_ids`, `max_missions`, `include_ai_reasoning`, `force` | Creates an `AI_RUNS` row with `run_type=MISSION_RECOMMENDATIONS`. Does not update `WORK_ITEM_WORK_DATES` or task state. |
| Fetch today's quests | `GET /api/v1/quests/today?date=YYYY-MM-DD` | `X-DevQuest-User-Id: user-1` | None | Reads local `quest_plans.json` and `quest_items.json` when a plan exists. Otherwise derives a fallback from Working Today tasks. |
| Generate quest plan | `POST /api/v1/quests/generate` | `X-DevQuest-User-Id: user-1` | `quest_date`, optional `candidate_task_ids`, `max_quests`, `respect_working_today`, `from_missions`, `include_ai_reasoning`, `force` | Creates an `AI_RUNS` row with `run_type=QUEST_PLAN`, upserts local quest plan/items, and inserts the quest date into selected tasks' worked dates. |

## Mission Generate Request

```json
{
  "date": "2026-05-05",
  "candidate_task_ids": [1001, 1002],
  "max_missions": 5,
  "include_ai_reasoning": true,
  "force": true
}
```

Mission response `data`:

| Field | Notes |
| --- | --- |
| `date` | Selected mission date. |
| `summary` | Model/mock summary of the recommended mission path. |
| `missions[].task_id` | Validated against the candidate task set. |
| `missions[].rank_order` | Normalized rank starting at 1. |
| `missions[].reason` | Evidence-based reason. |
| `missions[].suggested_action` | Practical next action for the task. |
| `missions[].is_quest_candidate` | Whether the mission can feed quest generation. |
| `ai_run_id` | Stored AI run ID. |
| `generated_at` | Generation timestamp. |

## Quest Generate Request

```json
{
  "quest_date": "2026-05-05",
  "candidate_task_ids": [1001, 1002],
  "max_quests": 5,
  "respect_working_today": true,
  "from_missions": false,
  "include_ai_reasoning": true,
  "force": true
}
```

Quest response `data`:

| Field | Notes |
| --- | --- |
| `quest_plan_id` | Local quest plan ID. |
| `quest_date` | Selected quest date. |
| `summary` | Model/mock summary of the route. |
| `quests[].task_id` | Validated against the candidate task set. |
| `quests[].rank_order` | Normalized rank starting at 1. |
| `quests[].reason` | Evidence-based reason. |
| `quests[].suggested_start_at` | Optional focus-window start. |
| `quests[].suggested_end_at` | Optional focus-window end. |
| `quests[].xp_value` | XP snapshot for the quest item. |
| `ai_run_id` | Stored AI run ID. |
| `generated_at` | Generation timestamp. |

## Data Flow

1. Resolve the requested date.
2. Read current user's candidate tasks from local work item storage.
3. Exclude `Done` and `Cancelled` tasks.
4. Apply `candidate_task_ids` when supplied.
5. For quest generation with `respect_working_today=true`, only use tasks whose worked dates include the quest date.
6. Build capacity and calendar context.
7. Use deterministic mock output unless `DEVQUEST_AI_MODE=real`.
8. Validate all returned task IDs against the candidate set.
9. For mission generation, store only the AI run and return recommendations.
10. For quest generation, store the AI run, upsert the quest plan/items, and add the quest date to each selected task's worked dates when absent.

## AI Execution Switches

| Setting | Behavior |
| --- | --- |
| `DEVQUEST_AI_MODE=mock` | Uses deterministic local ranking. No external AI call. |
| `DEVQUEST_AI_MODE=real` | Calls the configured external provider. |
| `DEVQUEST_AI_PROVIDER=oci_genai` | Uses OCI GenAI. |
| `OCI_GENAI_MODEL_ID` | Stored on `AI_RUNS.model_id` and used by OCI GenAI. |
| OCI auth/env values | See `docs/oci-genai-team-setup.md`. |

## Postman Tests

Generate missions:

```http
POST http://127.0.0.1:8000/api/v1/missions/generate
Content-Type: application/json
X-DevQuest-User-Id: user-1
```

```json
{
  "date": "2026-05-05",
  "max_missions": 5,
  "include_ai_reasoning": true,
  "force": true
}
```

Generate quests:

```http
POST http://127.0.0.1:8000/api/v1/quests/generate
Content-Type: application/json
X-DevQuest-User-Id: user-1
```

```json
{
  "quest_date": "2026-05-05",
  "max_quests": 5,
  "respect_working_today": true,
  "from_missions": false,
  "include_ai_reasoning": true,
  "force": true
}
```

Fetch quests:

```http
GET http://127.0.0.1:8000/api/v1/quests/today?date=2026-05-05
X-DevQuest-User-Id: user-1
```

## Notes For AI Assistants

- Do not mark tasks Working Today from `POST /api/v1/missions/generate`.
- `POST /api/v1/quests/generate` may mark selected tasks as worked for the quest date because quest generation commits the selected quest plan.
- Keep mock mode as the safe default for teammates without OCI setup.
- Do not commit local generated `backend/data/quest_plans.json`, `backend/data/quest_items.json`, or `backend/data/ai_runs.json` unless the team explicitly changes the data strategy.
- Phase 12 quest generation and Phase 13 daily insights both use `AI_RUNS`, but with different `run_type` values.
