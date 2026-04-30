# DevQuest Backend To Do List

Use this as the execution checklist for building the production backend. The detailed API contract lives in `docs/backend-api-integration-plan.md`; this file is the step-by-step work queue.

## Phase 1: Backend Project Foundation

- [ ] Replace the current sample MongoDB backend with a FastAPI application structure:
  - [ ] `app/main.py`
  - [ ] `app/core/config.py`
  - [ ] `app/core/db.py`
  - [ ] `app/core/errors.py`
  - [ ] `app/core/logging.py`
  - [ ] `app/api/routers/*`
  - [ ] `app/schemas/*`
  - [ ] `app/repositories/*`
  - [ ] `app/services/*`
  - [ ] `app/integrations/*`

- [ ] Update `backend/requirements.txt`:
  - [ ] Remove Mongo-only dependencies if no longer used.
  - [ ] Add `oracledb`.
  - [ ] Add `oci`.
  - [ ] Add `httpx`.
  - [ ] Add `tenacity`.
  - [ ] Add `structlog` or standard structured logging utilities.

- [ ] Implement environment-driven configuration:
  - [ ] Oracle Autonomous DB user/password/DSN.
  - [ ] Oracle wallet directory and wallet password if required.
  - [ ] OCI region, compartment ID, GenAI model ID, Agent endpoint ID.
  - [ ] Jira base URL, email/user, API token.
  - [ ] Microsoft tenant/client IDs and secret for Outlook.
  - [ ] CORS origins.
  - [ ] AI timeout and retry settings.

- [ ] Implement app startup/shutdown:
  - [ ] Create Oracle async connection pool on startup.
  - [ ] Close Oracle pool on shutdown.
  - [ ] Initialize OCI GenAI client.
  - [ ] Initialize OCI Agent runtime client.

- [ ] Implement common API behavior:
  - [ ] Response envelope.
  - [ ] Error envelope.
  - [ ] Request ID middleware.
  - [ ] Auth placeholder or user resolver.
  - [ ] CORS middleware.
  - [ ] Global exception handlers.

## Phase 2: Oracle Autonomous DB Schema

- [ ] Create migration folder under `backend/app/migrations`.

- [ ] Create sequences:
  - [ ] `APP_USERS_SEQ`
  - [ ] `WORK_ITEMS_SEQ`
  - [ ] `WORK_ITEM_EVENTS_SEQ`
  - [ ] `DAILY_WORK_ITEMS_SEQ`
  - [ ] `CALENDAR_EVENTS_SEQ`
  - [ ] `AI_RUNS_SEQ`
  - [ ] `QUEST_PLANS_SEQ`
  - [ ] `QUEST_ITEMS_SEQ`
  - [ ] `STANDUP_NOTES_SEQ`
  - [ ] `DAILY_OVERVIEWS_SEQ`
  - [ ] `WEEKLY_OVERVIEWS_SEQ`
  - [ ] `SYNC_RUNS_SEQ`
  - [ ] `SYNC_RUN_ITEMS_SEQ`

- [ ] Create core tables:
  - [ ] `APP_USERS`
  - [ ] `WORK_ITEMS`
  - [ ] `WORK_ITEM_EVENTS`
  - [ ] `DAILY_WORK_ITEMS`
  - [ ] `CALENDAR_EVENTS`
  - [ ] `AI_RUNS`
  - [ ] `QUEST_PLANS`
  - [ ] `QUEST_ITEMS`
  - [ ] `STANDUP_NOTES`
  - [ ] `DAILY_OVERVIEWS`
  - [ ] `WEEKLY_OVERVIEWS`
  - [ ] `IDEMPOTENCY_KEYS`
  - [ ] `SYNC_RUNS`
  - [ ] `SYNC_RUN_ITEMS`
  - [ ] Optional: `EXTERNAL_OBJECTS` for raw Jira/Outlook payload snapshots.

- [ ] Add indexes:
  - [ ] `WORK_ITEMS(USER_ID, STATUS)`
  - [ ] `WORK_ITEMS(USER_ID, COMPLETED_AT)`
  - [ ] `WORK_ITEMS(USER_ID, UPDATED_AT)`
  - [ ] `DAILY_WORK_ITEMS(USER_ID, WORK_DATE, IS_WORKING_TODAY)`
  - [ ] `CALENDAR_EVENTS(USER_ID, START_AT)`
  - [ ] `AI_RUNS(USER_ID, RUN_TYPE, CREATED_AT)`
  - [ ] `WORK_ITEM_EVENTS(TASK_ID, CREATED_AT)`

- [ ] Add constraints:
  - [ ] Work item status enum.
  - [ ] Work item priority enum.
  - [ ] Daily work boolean flag.
  - [ ] Unique external source keys for synced items.
  - [ ] Unique daily/weekly overview rows per user/date.

## Phase 3: Repository Layer

- [ ] Implement Oracle repository helpers:
  - [ ] `fetch_one`.
  - [ ] `fetch_all`.
  - [ ] `execute`.
  - [ ] `execute_returning_id`.
  - [ ] Transaction context helper.
  - [ ] CLOB read/write helpers.
  - [ ] JSON serialization helpers.

- [ ] Implement optimistic locking helper:
  - [ ] Require `row_version` for updates.
  - [ ] Use `WHERE ... ROW_VERSION = :row_version`.
  - [ ] Return `409 ROW_VERSION_CONFLICT` when stale.

- [ ] Implement idempotency helper:
  - [ ] Hash request body.
  - [ ] Save successful write response.
  - [ ] Return saved response on retry with same key/body.
  - [ ] Return conflict on same key/different body.

## Phase 4: Task Insert APIs

- [ ] Implement `POST /api/v1/tasks`.

- [ ] Request fields:
  - [ ] `external_source`
  - [ ] `external_id`
  - [ ] `title`
  - [ ] `description`
  - [ ] `task_type`
  - [ ] `priority`
  - [ ] `status`
  - [ ] `project_key`
  - [ ] `due_at`
  - [ ] `start_at`
  - [ ] `estimated_minutes`
  - [ ] `actual_minutes`
  - [ ] `xp_value`
  - [ ] `notes`
  - [ ] `labels`
  - [ ] `working_today`
  - [ ] `run_ai_enrichment`

- [ ] Insert steps:
  - [ ] Validate required fields and enums.
  - [ ] Insert into `WORK_ITEMS` without passing `TASK_ID`.
  - [ ] Fetch generated `TASK_ID` via `RETURNING TASK_ID INTO`.
  - [ ] Insert `WORK_ITEM_EVENTS` with `EVENT_TYPE = 'TASK_CREATED'`.
  - [ ] If `working_today = true`, insert/upsert `DAILY_WORK_ITEMS`.
  - [ ] If `run_ai_enrichment = true`, create an `AI_RUNS` row and trigger enrichment.
  - [ ] Commit transaction.
  - [ ] Return created task.

- [ ] Add validation tests:
  - [ ] Missing title.
  - [ ] Invalid priority.
  - [ ] Invalid status.
  - [ ] Negative minutes.
  - [ ] Duplicate external source/external ID.

## Phase 5: Task Read APIs

- [ ] Implement `GET /api/v1/tasks`.
  - [ ] Filter by status.
  - [ ] Filter by source.
  - [ ] Filter by priority.
  - [ ] Filter by `working_today`.
  - [ ] Filter by completion date.
  - [ ] Search title, description, and notes.
  - [ ] Add pagination.

- [ ] Implement `GET /api/v1/tasks/{task_id}`.
  - [ ] Return full task.
  - [ ] Return notes.
  - [ ] Return AI fields.
  - [ ] Return working-today state.
  - [ ] Return audit events.

## Phase 6: Task Update APIs

- [ ] Implement `PATCH /api/v1/tasks/{task_id}`.

- [ ] Updateable fields:
  - [ ] `title`
  - [ ] `description`
  - [ ] `task_type`
  - [ ] `priority`
  - [ ] `status`
  - [ ] `project_key`
  - [ ] `due_at`
  - [ ] `start_at`
  - [ ] `estimated_minutes`
  - [ ] `actual_minutes`
  - [ ] `xp_value`
  - [ ] `notes`
  - [ ] `labels`

- [ ] Update steps:
  - [ ] Lock or update task by `TASK_ID`, `USER_ID`, and `ROW_VERSION`.
  - [ ] Validate ownership.
  - [ ] Apply only provided fields.
  - [ ] If status changes to `Done`, set `COMPLETED_AT`.
  - [ ] Increment `ROW_VERSION`.
  - [ ] Insert `WORK_ITEM_EVENTS` with `EVENT_TYPE = 'TASK_UPDATED'`.
  - [ ] Optionally trigger AI enrichment.
  - [ ] Commit transaction.

- [ ] Implement `PUT /api/v1/tasks/{task_id}/notes`.
  - [ ] Validate `row_version`.
  - [ ] Update `WORK_ITEMS.NOTES`.
  - [ ] Increment `ROW_VERSION`.
  - [ ] Insert `WORK_ITEM_EVENTS` with `EVENT_TYPE = 'NOTES_UPDATED'`.
  - [ ] Optionally trigger AI enrichment.

- [ ] Implement `PATCH /api/v1/tasks/{task_id}/status`.
  - [ ] Validate status transition.
  - [ ] Update status.
  - [ ] Update actual minutes if supplied.
  - [ ] Append notes if supplied.
  - [ ] Set `COMPLETED_AT` when status becomes `Done`.
  - [ ] Insert `WORK_ITEM_EVENTS` with `EVENT_TYPE = 'STATUS_CHANGED'`.

- [ ] Implement `POST /api/v1/tasks/{task_id}/complete`.
  - [ ] Validate `row_version`.
  - [ ] Set `STATUS = 'Done'`.
  - [ ] Set `COMPLETED_AT = request.completed_at OR SYSTIMESTAMP`.
  - [ ] Update `ACTUAL_MINUTES`.
  - [ ] Append completion notes, learnings, went well, and went wrong to `NOTES`.
  - [ ] Compute XP if missing.
  - [ ] Insert `WORK_ITEM_EVENTS` with `EVENT_TYPE = 'TASK_COMPLETED'`.
  - [ ] Mark daily/weekly generated summaries stale or regenerate on demand.

## Phase 7: Working Today And Quests Source Of Truth

- [ ] Implement `PUT /api/v1/tasks/{task_id}/today`.
  - [ ] Validate task belongs to current user.
  - [ ] Resolve local `work_date`.
  - [ ] Upsert `DAILY_WORK_ITEMS`.
  - [ ] Set `IS_WORKING_TODAY`.
  - [ ] Set `PLANNED_MINUTES`.
  - [ ] Set `RANK_ORDER`.
  - [ ] Set daily-work notes.
  - [ ] Insert `WORK_ITEM_EVENTS` with `EVENT_TYPE = 'WORKING_TODAY_UPDATED'`.

- [ ] Implement `GET /api/v1/daily-work`.
  - [ ] Return all daily work items for a date.
  - [ ] Join task details.
  - [ ] Include completion state.
  - [ ] Include notes and actual minutes.

- [ ] Implement `GET /api/v1/quests/today`.
  - [ ] Read from `DAILY_WORK_ITEMS`.
  - [ ] Include only `IS_WORKING_TODAY = 1`.
  - [ ] Join `WORK_ITEMS`.
  - [ ] Join latest quest plan if present.
  - [ ] Return ranked quest cards.

## Phase 8: Dashboard And Capacity APIs

- [ ] Implement `GET /api/v1/dashboard/today`.
  - [ ] Return stats.
  - [ ] Return top missions.
  - [ ] Return tasks.
  - [ ] Return schedule.
  - [ ] Return AI insight.
  - [ ] Avoid frontend request waterfalls.

- [ ] Implement `GET /api/v1/capacity`.
  - [ ] Read user workday settings.
  - [ ] Read calendar events.
  - [ ] Calculate meeting minutes.
  - [ ] Calculate available focus minutes.
  - [ ] Calculate suggested focus windows.

## Phase 9: Calendar And Meeting APIs

- [ ] Implement `GET /api/v1/calendar/events`.
  - [ ] Filter by date range.
  - [ ] Return Outlook calendar events.
  - [ ] Return focus blocks.
  - [ ] Return meeting duration.

- [ ] Implement internal calendar upsert:
  - [ ] Upsert by `(USER_ID, EXTERNAL_SOURCE, EXTERNAL_ID)`.
  - [ ] Update title, description, start, end, duration, meeting flags.
  - [ ] Do not duplicate recurring instances.
  - [ ] Preserve local edits if any are later added.

## Phase 10: OCI AI Client Foundation

- [ ] Implement `integrations/oci_genai.py`.
  - [ ] Create GenAI inference client.
  - [ ] Add timeout handling.
  - [ ] Add retry policy for transient failures.
  - [ ] Pass request ID as OCI request metadata.
  - [ ] Parse JSON response.
  - [ ] Validate with Pydantic.

- [ ] Implement `integrations/oci_agents.py`.
  - [ ] Create Agent runtime client.
  - [ ] Create or reuse short-lived sessions.
  - [ ] Send chat requests.
  - [ ] Validate grounded response.
  - [ ] Reject unknown task IDs or dates.

- [ ] Implement AI run persistence:
  - [ ] Insert `AI_RUNS` before provider call.
  - [ ] Mark `RUNNING`.
  - [ ] Store request JSON.
  - [ ] Store response JSON.
  - [ ] Mark `SUCCEEDED`, `FAILED`, or `VALIDATION_FAILED`.

## Phase 11: AI Task Enrichment Endpoints

- [ ] Implement `POST /api/v1/tasks/{task_id}/ai/enrich`.
  - [ ] Fetch task and notes.
  - [ ] Use cache unless `force = true`.
  - [ ] Insert `AI_RUNS`.
  - [ ] Call OCI GenAI.
  - [ ] Validate difficulty, impact, priority score, effort, category, XP, insight.
  - [ ] Update `WORK_ITEMS` AI fields.
  - [ ] Update `XP_VALUE`.
  - [ ] Insert `WORK_ITEM_EVENTS` with `EVENT_TYPE = 'AI_ENRICHED'`.

- [ ] Implement `POST /api/v1/tasks/ai/enrich`.
  - [ ] Accept multiple task IDs.
  - [ ] Process in bounded batches.
  - [ ] Return partial success.
  - [ ] Store one AI run per task or one batch run plus per-task events.

- [ ] Prompt output fields:
  - [ ] `difficulty`
  - [ ] `impact_score`
  - [ ] `priority_score`
  - [ ] `effort_minutes`
  - [ ] `category`
  - [ ] `xp_value`
  - [ ] `insight`
  - [ ] `suggested_next_action`

## Phase 12: AI Quest Generation Endpoint

- [ ] Implement `POST /api/v1/quests/generate`.
  - [ ] Read candidate tasks.
  - [ ] If `respect_working_today = true`, use `DAILY_WORK_ITEMS`.
  - [ ] Read calendar capacity.
  - [ ] Call OCI GenAI for ranked quest plan.
  - [ ] Validate returned task IDs exist in candidate set.
  - [ ] Upsert `QUEST_PLANS`.
  - [ ] Delete/reinsert `QUEST_ITEMS`.
  - [ ] Upsert `DAILY_WORK_ITEMS` for selected quests.
  - [ ] Return quest plan and AI run ID.

- [ ] Quest prompt output fields:
  - [ ] `summary`
  - [ ] `quests[].task_id`
  - [ ] `quests[].rank_order`
  - [ ] `quests[].reason`
  - [ ] `quests[].suggested_start_at`
  - [ ] `quests[].suggested_end_at`
  - [ ] `quests[].xp_value`

## Phase 13: AI Insights Endpoints

- [ ] Implement `GET /api/v1/insights/today`.
  - [ ] Return capacity.
  - [ ] Return task insights.
  - [ ] Return latest daily AI insight.
  - [ ] Return latest standup summary if available.

- [ ] Implement `POST /api/v1/insights/today/generate`.
  - [ ] Read daily work items.
  - [ ] Read task notes.
  - [ ] Read completed tasks.
  - [ ] Read meeting schedule.
  - [ ] Call OCI GenAI.
  - [ ] Store in `AI_RUNS`.
  - [ ] Return risks and recommendations.

- [ ] Use OCI Agent for historical questions:
  - [ ] Create read-only SQL views.
  - [ ] Grant agent DB user read-only access.
  - [ ] Ask agent for historical blockers, recurring patterns, and trends.
  - [ ] Validate response before display.

## Phase 14: Standup Note Generator

- [ ] Implement `POST /api/v1/standup-notes/generate`.
  - [ ] Read completed tasks for selected date.
  - [ ] Read in-progress daily work.
  - [ ] Read blocked tasks.
  - [ ] Include task notes and learnings.
  - [ ] Insert `AI_RUNS`.
  - [ ] Call OCI GenAI.
  - [ ] Validate structured standup output.
  - [ ] Upsert `STANDUP_NOTES`.

- [ ] Implement `GET /api/v1/standup-notes`.
  - [ ] Fetch by date.
  - [ ] Return full note and structured sections.

- [ ] Standup output fields:
  - [ ] `accomplished`
  - [ ] `in_progress`
  - [ ] `blockers`
  - [ ] `next_steps`
  - [ ] `full_note`

## Phase 15: Daily And Weekly Overview Page APIs

- [ ] Implement `GET /api/v1/overviews/daily`.
  - [ ] Return tasks accomplished.
  - [ ] Return XP earned.
  - [ ] Return meeting minutes.
  - [ ] Return focus minutes.
  - [ ] Return new learnings.
  - [ ] Return went well.
  - [ ] Return went wrong.
  - [ ] Return generated summary.

- [ ] Implement `POST /api/v1/overviews/daily/generate`.
  - [ ] Read completed tasks.
  - [ ] Read task notes.
  - [ ] Read daily work rows.
  - [ ] Read calendar events.
  - [ ] Calculate totals without AI.
  - [ ] Call OCI GenAI for narrative summary and themes.
  - [ ] Upsert `DAILY_OVERVIEWS`.

- [ ] Implement `GET /api/v1/overviews/weekly`.
  - [ ] Return weekly task totals.
  - [ ] Return XP totals.
  - [ ] Return meeting totals.
  - [ ] Return focus totals.
  - [ ] Return top accomplishments.
  - [ ] Return learnings and themes.

- [ ] Implement `POST /api/v1/overviews/weekly/generate`.
  - [ ] Read daily overviews if present.
  - [ ] Read raw completed tasks if daily overviews are missing.
  - [ ] Calculate totals without AI.
  - [ ] Call OCI GenAI or OCI Agent for weekly themes.
  - [ ] Upsert `WEEKLY_OVERVIEWS`.

## Phase 16: Jira Connector

- [ ] Implement Jira configuration:
  - [ ] `JIRA_BASE_URL`
  - [ ] `JIRA_EMAIL`
  - [ ] `JIRA_API_TOKEN`
  - [ ] `JIRA_PROJECT_KEYS`
  - [ ] `JIRA_JQL`

- [ ] Implement Jira auth:
  - [ ] Basic auth or OAuth depending on tenant.
  - [ ] Secure secrets in environment or OCI Vault.

- [ ] Implement Jira fetch:
  - [ ] Query assigned issues.
  - [ ] Query issues updated since last sync.
  - [ ] Handle pagination.
  - [ ] Handle rate limits.
  - [ ] Handle retries.

- [ ] Map Jira issue fields to `WORK_ITEMS`:
  - [ ] `external_source = 'Jira'`
  - [ ] `external_id = issue.key`
  - [ ] `title = fields.summary`
  - [ ] `description = fields.description`
  - [ ] `task_type = fields.issuetype.name`
  - [ ] `priority = fields.priority.name`
  - [ ] `status = normalized fields.status.name`
  - [ ] `project_key = fields.project.key`
  - [ ] `due_at = fields.duedate`
  - [ ] `labels = fields.labels`

- [ ] Implement Jira upsert:
  - [ ] Upsert by `(USER_ID, EXTERNAL_SOURCE, EXTERNAL_ID)`.
  - [ ] Insert new Jira issues into `WORK_ITEMS`.
  - [ ] Update external fields on existing issues.
  - [ ] Preserve user-entered `NOTES`.
  - [ ] Preserve local `working_today`.
  - [ ] Insert `WORK_ITEM_EVENTS` for created/updated synced issues.
  - [ ] Optionally trigger AI enrichment for new or materially changed issues.

- [ ] Implement Jira error handling:
  - [ ] Invalid credentials.
  - [ ] Permission denied.
  - [ ] Rate limited.
  - [ ] Network timeout.
  - [ ] Malformed response.

## Phase 17: Outlook Calendar Connector

- [ ] Implement Microsoft Graph configuration:
  - [ ] `MS_TENANT_ID`
  - [ ] `MS_CLIENT_ID`
  - [ ] `MS_CLIENT_SECRET`
  - [ ] Required Graph scopes.

- [ ] Implement token flow:
  - [ ] OAuth authorization code for user delegated access, or client credentials if tenant policy allows.
  - [ ] Store refresh tokens securely if delegated.
  - [ ] Refresh expired access tokens.

- [ ] Implement calendar fetch:
  - [ ] Fetch events for date range.
  - [ ] Handle pagination.
  - [ ] Handle recurring instances.
  - [ ] Handle canceled events.
  - [ ] Handle timezone conversion.

- [ ] Map Outlook event fields to `CALENDAR_EVENTS`:
  - [ ] `external_source = 'Outlook Calendar'`
  - [ ] `external_id = event.id`
  - [ ] `title = event.subject`
  - [ ] `description = event.bodyPreview`
  - [ ] `start_at = event.start`
  - [ ] `end_at = event.end`
  - [ ] `duration_minutes`
  - [ ] `is_meeting`
  - [ ] `is_focus_block`
  - [ ] `attendee_count`

- [ ] Implement calendar upsert:
  - [ ] Upsert by `(USER_ID, EXTERNAL_SOURCE, EXTERNAL_ID)`.
  - [ ] Insert new events.
  - [ ] Update changed events.
  - [ ] Mark canceled events as inactive if an inactive flag is added.
  - [ ] Recalculate daily capacity after sync.

## Phase 18: Microsoft To Do Connector

- [ ] Implement To Do fetch through Microsoft Graph.
  - [ ] Fetch lists.
  - [ ] Fetch tasks.
  - [ ] Handle pagination.
  - [ ] Handle completed tasks.

- [ ] Map To Do fields to `WORK_ITEMS`:
  - [ ] `external_source = 'Microsoft To Do'`
  - [ ] `external_id = todo.id`
  - [ ] `title = todo.title`
  - [ ] `description = todo.body.content`
  - [ ] `priority = normalized todo.importance`
  - [ ] `status = normalized todo.status`
  - [ ] `due_at = todo.dueDateTime`
  - [ ] `completed_at = todo.completedDateTime`

- [ ] Implement To Do upsert:
  - [ ] Insert new tasks.
  - [ ] Update changed tasks.
  - [ ] Preserve notes and AI fields unless source data materially changes.
  - [ ] Trigger AI enrichment for new tasks.

## Phase 19: Sync APIs

- [ ] Create `SYNC_RUNS` table.
  - [ ] `SYNC_RUN_ID`
  - [ ] `USER_ID`
  - [ ] `STATUS`
  - [ ] `STARTED_AT`
  - [ ] `COMPLETED_AT`
  - [ ] `ERROR_MESSAGE`

- [ ] Create `SYNC_RUN_ITEMS` table.
  - [ ] `SYNC_RUN_ITEM_ID`
  - [ ] `SYNC_RUN_ID`
  - [ ] `SOURCE`
  - [ ] `STATUS`
  - [ ] `CREATED_COUNT`
  - [ ] `UPDATED_COUNT`
  - [ ] `FAILED_COUNT`
  - [ ] `ERROR_MESSAGE`

- [ ] Implement `POST /api/v1/sync/run`.
  - [ ] Accept sources.
  - [ ] Create sync run.
  - [ ] Run Jira sync.
  - [ ] Run Outlook Calendar sync.
  - [ ] Run Microsoft To Do sync.
  - [ ] Trigger optional AI enrichment.
  - [ ] Return sync run status.

- [ ] Implement `GET /api/v1/sync/runs`.
  - [ ] List recent sync runs.
  - [ ] Include per-source status.

- [ ] Implement `GET /api/v1/sync/runs/{sync_run_id}`.
  - [ ] Return detailed sync status.
  - [ ] Return created/updated/failed counts.

## Phase 20: Settings APIs

- [ ] Implement `GET /api/v1/settings/productivity`.
  - [ ] Return timezone.
  - [ ] Return workday start/end.
  - [ ] Return focus XP multiplier.

- [ ] Implement `PATCH /api/v1/settings/productivity`.
  - [ ] Validate timezone.
  - [ ] Validate time strings.
  - [ ] Validate XP multiplier.
  - [ ] Update `APP_USERS`.
  - [ ] Increment `ROW_VERSION`.

## Phase 21: Security And Operations

- [ ] Add authentication.
  - [ ] JWT validation or OCI IAM integration.
  - [ ] Resolve current user.
  - [ ] Enforce row ownership everywhere.

- [ ] Add secret handling.
  - [ ] Move credentials to environment or OCI Vault.
  - [ ] Do not log secrets.
  - [ ] Redact external API payloads where needed.

- [ ] Add AI data safety.
  - [ ] Redact obvious secrets from notes before sending to AI.
  - [ ] Store AI prompts and responses only if allowed by policy.
  - [ ] Add rate limits to AI endpoints.

- [ ] Add observability.
  - [ ] Structured logs.
  - [ ] Request IDs.
  - [ ] DB query timing.
  - [ ] OCI AI timing.
  - [ ] Connector timing and failure rates.

## Phase 22: Tests

- [ ] Unit tests:
  - [ ] Task create.
  - [ ] Task update.
  - [ ] Notes update.
  - [ ] Status transition.
  - [ ] Task completion date.
  - [ ] Working-today upsert.
  - [ ] Quest read from daily work.
  - [ ] Capacity calculation.
  - [ ] AI response validation.
  - [ ] Idempotency.

- [ ] Integration tests:
  - [ ] Oracle insert transaction rollback.
  - [ ] Oracle update row-version conflict.
  - [ ] Jira issue upsert.
  - [ ] Outlook event upsert.
  - [ ] Microsoft To Do task upsert.
  - [ ] OCI GenAI success.
  - [ ] OCI GenAI timeout.
  - [ ] OCI Agent historical insight.

- [ ] API contract tests:
  - [ ] `POST /tasks`.
  - [ ] `PATCH /tasks/{task_id}`.
  - [ ] `POST /tasks/{task_id}/complete`.
  - [ ] `PUT /tasks/{task_id}/today`.
  - [ ] `POST /quests/generate`.
  - [ ] `POST /standup-notes/generate`.
  - [ ] `POST /overviews/daily/generate`.
  - [ ] `POST /sync/run`.

## Phase 23: Frontend Wiring Support

- [ ] Provide stable API response shapes for frontend.
- [ ] Return all IDs as numbers.
- [ ] Return `row_version` for editable records.
- [ ] Return `working_today` on task list rows.
- [ ] Return `completed_at` after done action.
- [ ] Return task `notes`.
- [ ] Return AI insight fields expected by task table and insights page.
- [ ] Keep leaderboard disabled or hidden for now.

## Recommended Build Order

1. Backend project structure and Oracle DB pool.
2. Schema migrations and sequences.
3. Task create/read/update/complete APIs.
4. Working-today and daily work APIs.
5. Dashboard and capacity APIs.
6. Calendar event APIs.
7. OCI GenAI client and task enrichment.
8. Quest generation.
9. Standup generator.
10. Daily and weekly overview generation.
11. Jira connector.
12. Outlook Calendar connector.
13. Microsoft To Do connector.
14. Sync orchestration APIs.
15. OCI Agent historical insights.
16. Security, rate limits, observability, and full tests.
17. A login screen for username, Email and jira access details.
