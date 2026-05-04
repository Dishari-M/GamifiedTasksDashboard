# Phase 8: Dashboard And Capacity APIs

Progress log for Phase 8. Stable implementation details live in `docs/phase-8-dashboard-capacity-spec.md`.

## 2026-05-01

### Scope

Implement mock-backed versions of:

- `GET /api/v1/dashboard/today`
- `GET /api/v1/capacity`

Oracle Autonomous Database will be integrated later. For now, implementation should mirror the final table concepts from `backend-api-integration-plan.md` using mock data.

### Reference Docs

- `docs/phase-8-dashboard-capacity-spec.md`
- `docs/backend-api-integration-plan.md`
- `docs/backend-todo-list.md`

### Relevant Future Tables

- `APP_USERS`
- `WORK_ITEMS`
- `DAILY_WORK_ITEMS`
- `CALENDAR_EVENTS`
- `AI_RUNS`
- `QUEST_PLANS`
- `QUEST_ITEMS`

### Pending Infra

- [x] Add or organize backend route structure for `/api/v1`.
- [x] Add mock data source for Phase 8.
- [x] Add shared data-mode switch using `DEVQUEST_DATA_MODE`.
- [x] Add shared AI-mode switch using `DEVQUEST_AI_MODE`.
- [x] Add OCI Generative AI SDK dependency and real-mode client boundary.
- [x] Add capacity service.
- [x] Add dashboard service.
- [x] Keep response shapes aligned with `backend-api-integration-plan.md`.
- [ ] Later: replace mock data with Oracle repository calls.
- [ ] Later: apply Oracle ADB schema/migrations.

### Pending Mock Data

- [x] Mock `APP_USERS` data:
  - timezone
  - workday start
  - workday end
- [x] Mock `WORK_ITEMS` data:
  - tasks
  - status
  - priority
  - XP
  - AI fields
- [x] Mock `DAILY_WORK_ITEMS` data:
  - working-today state
  - rank order
  - planned minutes
- [x] Mock `CALENDAR_EVENTS` data:
  - meetings
  - focus blocks
  - start/end/duration
- [x] Mock/fallback AI insight.
- [x] Real AI path prepared for OCI Generative AI Inference.

### Pending API Implementation

#### `GET /api/v1/capacity`

- [x] Read mock user workday settings.
- [x] Read mock calendar events for requested date.
- [x] Calculate workday minutes.
- [x] Calculate meeting minutes.
- [x] Calculate focus block minutes.
- [x] Calculate available focus minutes.
- [x] Calculate suggested focus windows.
- [x] Return response with `data` and `meta`.

#### `GET /api/v1/dashboard/today`

- [x] Read mock tasks.
- [x] Read mock daily work rows.
- [x] Read mock calendar events.
- [x] Reuse capacity calculation.
- [x] Return stats.
- [x] Return top missions.
- [x] Return tasks.
- [x] Return schedule.
- [x] Return AI insight.
- [x] Return all dashboard data in one response to avoid frontend request waterfalls.

### Pending Tests / Smoke Checks

- [x] Smoke test `GET /api/v1/capacity`.
- [x] Smoke test `GET /api/v1/dashboard/today`.
- [x] Test default date behavior.
- [x] Test explicit `date=YYYY-MM-DD`.
- [ ] Test empty calendar fallback.
- [ ] Test empty task fallback.
- [x] Test overlapping meeting handling in service logic by merging meeting intervals before calculating meeting minutes.

### Notes

- Mock implementation should be deterministic.
- AI should explain capacity but should not calculate basic arithmetic.
- Keep Oracle table naming and response fields consistent with the integration plan so mock data can be replaced later.
- This is a shared 5-member project. Generic framework/util layers may be duplicated by other team members, so keep Phase 8 helpers scoped and easy to replace until shared backend structure is finalized.

### Implementation Update

- Added `backend/services/phase8_mock_data.py`.
- Added shared `backend/config.py` with `DEVQUEST_DATA_MODE=mock|oracle`.
- Added shared AI config in `backend/config.py` with `DEVQUEST_AI_MODE`, `DEVQUEST_AI_PROVIDER`, and `OCI_GENAI_MODEL_ID`.
- Added OCI config helpers in `backend/config.py` for compartment, auth type, profile, endpoint, and serving mode.
- Added `backend/services/phase8_data_provider.py` as the Phase 8 adapter that uses the shared switch.
- Added `backend/repositories/phase8_oracle_repository.py` as the future Oracle ADB repository contract.
- Added `backend/services/phase8_ai_insight_service.py` as the production-shaped AI insight boundary.
- Added `backend/integrations/oci_genai_client.py` with lazy OCI SDK loading and real-mode Generative AI Inference call.
- Added `backend/services/phase8_capacity_service.py`.
- Added `backend/services/phase8_dashboard_service.py`.
- Added `GET /api/v1/capacity` in `backend/main.py`.
- Added `GET /api/v1/dashboard/today` in `backend/main.py`.
- Updated the OCI GenAI real-mode boundary to support env-selected request formats:
  - `OCI_GENAI_REQUEST_FORMAT=generic` for OpenAI/Gemini/xAI-style chat models.
  - `OCI_GENAI_REQUEST_FORMAT=cohere` for Cohere chat payloads.
  - `OCI_GENAI_REQUEST_FORMAT=auto` to choose Cohere only for `cohere.*` model IDs.
- Added temporary local `OCI_AUTH_TYPE=api_key` support so Phase 8 can test real AI without requiring every teammate to create an OCI CLI profile. Mock mode remains the default.
- Added minimal frontend integration for Phase 8 dashboard data:
  - Added `dashboardApi.today()` and `capacityApi.get()` in `frontend/src/api/client.js`.
  - `frontend/src/App.js` now fetches `GET /api/v1/dashboard/today` on app shell mount.
  - Existing Dashboard sections consume Phase 8 stats, tasks, schedule, and AI insight when available.
  - Existing local demo data remains as fallback if the backend is down or AI is not configured.
  - No broad UI refactor was done; task mutations remain local for now.
- Restarted local backend and verified live responses for:
  - `http://127.0.0.1:8000/api/v1/capacity?date=2026-05-01`
  - `http://127.0.0.1:8000/api/v1/dashboard/today?date=2026-05-01`
