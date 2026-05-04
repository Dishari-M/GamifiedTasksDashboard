# Phase 8: Dashboard And Capacity API Spec

This is the implementation source of truth for Phase 8. Daily progress should be tracked in `docs/phase-8-dashboard-capacity-updates.md`.

## Goal

Implement mock-backed APIs for the dashboard and capacity views while keeping the response contract aligned with the future Oracle ADB-backed design.

## Team Coordination Note

This is a shared hackathon backend with multiple team members working in parallel. Some generic framework or utility layers may also be created by other members, such as:

- API response wrappers
- request ID helpers
- date/time helpers
- mock data loaders
- Oracle repository helpers
- router/package structure
- error handling utilities

For Phase 8, avoid doing a broad backend refactor unless the team agrees. If a generic helper is needed before the shared version exists, keep it small, local, and easy to replace. Prefer names that make temporary ownership clear, for example `phase8_mock_data.py` or `phase8_capacity_service.py`, instead of claiming a global utility namespace too early.

When a shared framework layer lands, Phase 8 should adapt to it rather than keeping duplicate implementations.

## Endpoints

### `GET /api/v1/capacity`

Query params:

- `date` optional, format `YYYY-MM-DD`

Response shape:

```json
{
  "data": {
    "date": "2026-05-01",
    "workday_minutes": 480,
    "meeting_minutes": 190,
    "focus_block_minutes": 165,
    "available_focus_minutes": 165,
    "suggested_focus_windows": [
      {
        "start_at": "2026-05-01T13:00:00+05:30",
        "end_at": "2026-05-01T15:45:00+05:30",
        "duration_minutes": 165
      }
    ]
  },
  "meta": {
    "request_id": "generated-request-id"
  }
}
```

### `GET /api/v1/dashboard/today`

Query params:

- `date` optional, format `YYYY-MM-DD`

Response shape:

```json
{
  "data": {
    "date": "2026-05-01",
    "stats": {
      "total_xp": 2590,
      "tasks_completed_today": 3,
      "tasks_planned_today": 7,
      "focus_minutes": 155,
      "meeting_minutes": 190,
      "available_focus_minutes": 165
    },
    "top_missions": [],
    "tasks": [],
    "schedule": [],
    "ai_insight": {
      "text": "You have 165 focus minutes after meetings. Start with the highest priority mission.",
      "capacity_minutes": 165,
      "impact_score": 8.7,
      "generated_at": "2026-05-01T09:20:00+05:30"
    }
  },
  "meta": {
    "request_id": "generated-request-id"
  }
}
```

## Mock Data Contract

Mock data should mirror future table concepts so it can be replaced with Oracle repository calls later.

## Shared Data Mode Switch

The mock-vs-real data mode is a shared backend concern, not a Phase 8-only concern. All backend work should use the same flag so UI and backend teams can switch the whole API surface consistently.

Environment variable:

```text
DEVQUEST_DATA_MODE=mock
```

Supported values:

- `mock`: use Phase 8 mock data. This is the default for local development.
- `oracle`: reserved for Oracle ADB-backed repositories. This currently returns `501 Not Implemented` until repository functions are added.

Current shared config file:

```text
backend/config.py
```

Phase 8 adapter file:

```text
backend/services/phase8_data_provider.py
```

Oracle repository placeholder:

```text
backend/repositories/phase8_oracle_repository.py
```

Phase 8 uses the shared `DEVQUEST_DATA_MODE` flag through `backend/config.py`. Other team members should reuse the same config helper instead of creating task-specific switches.

API endpoints should keep the same response shape when switching from mock to Oracle.

## Shared AI Mode Switch

Dashboard AI insight should be production-shaped now, with mock behavior only at the AI boundary.

Environment variables:

```text
DEVQUEST_AI_MODE=mock
DEVQUEST_AI_PROVIDER=oci_genai
OCI_GENAI_MODEL_ID=
OCI_COMPARTMENT_ID=
OCI_AUTH_TYPE=config_file
OCI_CONFIG_PROFILE=DEFAULT
```

Supported values:

- `DEVQUEST_AI_MODE=mock`: return deterministic local insight. This is the default for local development.
- `DEVQUEST_AI_MODE=real`: call the configured approved AI provider.
- `DEVQUEST_AI_PROVIDER=oci_genai`: use OCI Generative AI, specifically the Generative AI Service Inference API.
- `OCI_GENAI_MODEL_ID`: OCI GenAI model ID for on-demand serving, or endpoint OCID for dedicated serving.
- `OCI_COMPARTMENT_ID`: OCI compartment OCID used by the inference request.
- `OCI_AUTH_TYPE`: `config_file`, `instance_principal`, or `resource_principal`.
- `OCI_CONFIG_PROFILE`: local OCI config profile used when `OCI_AUTH_TYPE=config_file`.
- `OCI_CONFIG_FILE`: optional local OCI config path override.
- `OCI_GENAI_ENDPOINT`: optional service endpoint override if Oracle provides a specific endpoint.
- `OCI_GENAI_SERVING_MODE`: `on_demand` by default, or `dedicated` for dedicated endpoint usage.

Current shared config file:

```text
backend/config.py
```

Phase 8 AI orchestration:

```text
backend/services/phase8_ai_insight_service.py
```

OCI GenAI integration:

```text
backend/integrations/oci_genai_client.py
```

Approved-tool guidance:

- Category: OCI AI Services
- Runtime service for this use case: OCI Generative AI
- API family: Generative AI Service Inference API

The public dashboard response should keep the same `ai_insight` shape in mock and real mode.

In real mode, the service sends compact dashboard context to OCI GenAI and asks for JSON with:

- `text`
- `capacity_minutes`
- `impact_score`

The integration normalizes model output back to the same dashboard API contract used in mock mode.

### Mock User

Future table: `APP_USERS`

Required fields:

- `user_id`
- `display_name`
- `timezone`
- `workday_start_local`
- `workday_end_local`

Default values:

```json
{
  "user_id": 1,
  "display_name": "Aryan Verma",
  "timezone": "Asia/Calcutta",
  "workday_start_local": "09:00",
  "workday_end_local": "17:00"
}
```

### Mock Tasks

Future table: `WORK_ITEMS`

Required fields:

- `task_id`
- `title`
- `description`
- `external_source`
- `external_id`
- `task_type`
- `priority`
- `status`
- `estimated_minutes`
- `actual_minutes`
- `xp_value`
- `ai_difficulty`
- `ai_impact_score`
- `ai_priority_score`
- `ai_insight`
- `completed_at`

### Mock Daily Work

Future table: `DAILY_WORK_ITEMS`

Required fields:

- `daily_work_id`
- `task_id`
- `work_date`
- `is_working_today`
- `rank_order`
- `planned_minutes`

### Mock Calendar Events

Future table: `CALENDAR_EVENTS`

Required fields:

- `event_id`
- `title`
- `start_at`
- `end_at`
- `duration_minutes`
- `is_meeting`
- `is_focus_block`
- `external_source`

Suggested mock events:

- Daily Standup, `09:00-09:30`, meeting
- Architecture Review, `10:00-11:00`, meeting
- Client Sync, `11:30-12:30`, meeting
- Focus Time Block, `13:00-15:45`, focus block

## Service Responsibilities

### `capacity_service`

Responsibilities:

- Resolve requested date.
- Read mock user workday settings.
- Read mock calendar events.
- Calculate workday minutes.
- Calculate meeting minutes.
- Calculate focus block minutes.
- Calculate available focus minutes.
- Calculate suggested focus windows.

Rules:

- Use deterministic arithmetic.
- Do not use AI for basic capacity math.
- Treat focus blocks as suggested focus windows when present.
- If no focus blocks exist, compute free windows between meetings.
- Handle overlapping meetings by merging intervals before calculating occupied time.

### `dashboard_service`

Responsibilities:

- Resolve requested date.
- Read mock tasks.
- Read mock daily work items.
- Read mock calendar events.
- Reuse `capacity_service`.
- Compute stats.
- Select top missions from working-today tasks.
- Return tasks and schedule in frontend-friendly shape.
- Return fallback AI insight.

Rules:

- Return all dashboard data in one response.
- Avoid request waterfalls.
- Top missions should be ranked by `rank_order` first, then `ai_priority_score`, then `xp_value`.

## Routing

Add routes under `/api/v1`:

- `GET /api/v1/capacity`
- `GET /api/v1/dashboard/today`

Current backend is flat. For Phase 8, either:

- add routes directly in `backend/main.py`, or
- create a small router/service structure without doing a full backend refactor.

Prefer keeping the change scoped to Phase 8.

## Testing Checklist

- [ ] `GET /api/v1/capacity` returns `200`.
- [ ] `GET /api/v1/capacity?date=YYYY-MM-DD` returns that date.
- [ ] `GET /api/v1/dashboard/today` returns `200`.
- [ ] Dashboard response includes `stats`, `top_missions`, `tasks`, `schedule`, and `ai_insight`.
- [ ] Capacity math matches mock calendar events.
- [ ] Empty calendar fallback does not crash.
- [ ] Empty task fallback does not crash.
- [ ] Overlapping meetings do not double count occupied time.

## Later Oracle Replacement

When Oracle ADB is ready:

- Replace mock user with `APP_USERS`.
- Replace mock tasks with `WORK_ITEMS`.
- Replace mock daily work rows with `DAILY_WORK_ITEMS`.
- Replace mock calendar events with `CALENDAR_EVENTS`.
- Replace fallback AI insight with latest relevant `AI_RUNS` or generated insight.
- Keep the public API response shape stable.
