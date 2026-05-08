# Gamified Tasks Dashboard Backend To Do List

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

- [ ] Enforce user ownership on every DB table mentioned in this checklist:
  - [ ] `APP_USERS.USER_ID` is the canonical user key.
  - [ ] Every other table must include a `USER_ID` column defined as a `NOT NULL` FK to `APP_USERS(USER_ID)`.
  - [ ] Repository queries, unique keys, and indexes must include `USER_ID` wherever rows are user-scoped.

- [ ] Create sequences:
  - [ ] `APP_USERS_SEQ`
  - [ ] `USER_STATS_SEQ`
  - [ ] `USER_INTEGRATIONS_SEQ`
  - [ ] `WORK_ITEMS_SEQ`
  - [ ] `WORK_ITEM_WORK_DATES_SEQ`
  - [ ] `WORK_ITEM_EVENTS_SEQ`
  - [ ] `CALENDAR_EVENTS_SEQ`
  - [ ] `FOCUS_SESSIONS_SEQ`
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
  - [ ] `USER_STATS`
  - [ ] `USER_INTEGRATIONS`
  - [ ] `WORK_ITEMS`
  - [ ] `WORK_ITEM_WORK_DATES`
  - [ ] `WORK_ITEM_EVENTS`
  - [ ] `CALENDAR_EVENTS`
  - [ ] `FOCUS_SESSIONS`
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

- [ ] Map UI surfaces to DB tables:

| UI surface | Primary tables |
| --- | --- |
| Sidebar profile, XP, streak, level | `APP_USERS`, `USER_STATS` |
| Dashboard stats and top missions | `WORK_ITEMS`, `CALENDAR_EVENTS`, `FOCUS_SESSIONS`, `USER_STATS`, `AI_RUNS` |
| My Tasks add/edit/table | `WORK_ITEMS`, `WORK_ITEM_EVENTS` |
| Working Today button | `WORK_ITEM_WORK_DATES`, `WORK_ITEM_EVENTS` |
| Missions | `WORK_ITEMS`, `CALENDAR_EVENTS`, `APP_USERS`, `AI_RUNS` |
| Quests | `WORK_ITEM_WORK_DATES`, `QUEST_PLANS`, `QUEST_ITEMS`, `AI_RUNS` |
| Calendar schedule | `CALENDAR_EVENTS` |
| Focus Mode | `FOCUS_SESSIONS`, optional `WORK_ITEMS` |
| AI Insights | `WORK_ITEMS`, `WORK_ITEM_WORK_DATES`, `CALENDAR_EVENTS`, `AI_RUNS`, `STANDUP_NOTES` |
| Standup Note Generator | `WORK_ITEMS`, `WORK_ITEM_WORK_DATES`, `STANDUP_NOTES`, `AI_RUNS` |
| Daily Overview | `DAILY_OVERVIEWS`, `WORK_ITEMS`, `WORK_ITEM_WORK_DATES`, `CALENDAR_EVENTS`, `FOCUS_SESSIONS`, `AI_RUNS` |
| Weekly Overview | `WEEKLY_OVERVIEWS`, `DAILY_OVERVIEWS`, `WORK_ITEMS`, `WORK_ITEM_WORK_DATES`, `CALENDAR_EVENTS`, `FOCUS_SESSIONS`, `AI_RUNS` |
| Sync Center | `USER_INTEGRATIONS`, `SYNC_RUNS`, `SYNC_RUN_ITEMS`, optional `EXTERNAL_OBJECTS` |
| Settings | `APP_USERS`, `USER_INTEGRATIONS` |

- [ ] Create `APP_USERS` for profile, login, settings, ownership, and timezone:

| Column | Type | Notes |
| --- | --- | --- |
| `USER_ID` | `NUMBER(19)` | PK, `APP_USERS_SEQ.NEXTVAL` |
| `FIRST_NAME` | `VARCHAR2(120)` | UI profile first name |
| `LAST_NAME` | `VARCHAR2(120)` | UI profile last name |
| `EMAIL` | `VARCHAR2(320)` | unique login/email |
| `USERNAME` | `VARCHAR2(120)` | optional login username |
| `ROLE_NAME` | `VARCHAR2(80)` | developer, QA, DevOps, manager |
| `TIMEZONE` | `VARCHAR2(80)` | default `Asia/Calcutta` |
| `WORKDAY_START_LOCAL` | `VARCHAR2(5)` | settings page, example `09:00` |
| `WORKDAY_END_LOCAL` | `VARCHAR2(5)` | settings page, example `17:00` |
| `FOCUS_XP_MULTIPLIER` | `NUMBER(5,2)` | settings page |
| `CREATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `UPDATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `ROW_VERSION` | `NUMBER` | optimistic locking |

- [ ] Create `USER_STATS` for sidebar XP, level, streak, and fast dashboard stats:

| Column | Type | Notes |
| --- | --- | --- |
| `USER_STATS_ID` | `NUMBER(19)` | PK, `USER_STATS_SEQ.NEXTVAL` |
| `USER_ID` | `NUMBER(19)` | FK to `APP_USERS`, unique |
| `TOTAL_XP` | `NUMBER(10)` | sidebar/dashboard total XP |
| `CURRENT_LEVEL` | `NUMBER(5)` | sidebar level |
| `CURRENT_STREAK_DAYS` | `NUMBER(6)` | sidebar streak |
| `LAST_ACTIVITY_DATE` | `DATE` | streak calculation |
| `CURRENT_LEVEL_XP` | `NUMBER(10)` | XP earned in current level |
| `NEXT_LEVEL_XP` | `NUMBER(10)` | XP required for next level |
| `CREATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `UPDATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `ROW_VERSION` | `NUMBER` | optimistic locking |

- [ ] Create `USER_INTEGRATIONS` for Jira, Outlook Calendar connector setup:

| Column | Type | Notes |
| --- | --- | --- |
| `USER_INTEGRATION_ID` | `NUMBER(19)` | PK, `USER_INTEGRATIONS_SEQ.NEXTVAL` |
| `USER_ID` | `NUMBER(19)` | FK to `APP_USERS` |
| `PROVIDER` | `VARCHAR2(60)` | `Jira`, `Outlook Calendar` |
| `ACCOUNT_IDENTIFIER` | `VARCHAR2(320)` | Jira email, Microsoft account, tenant user |
| `BASE_URL` | `VARCHAR2(500)` | Jira base URL when provider is Jira |
| `PROJECT_KEYS` | `VARCHAR2(1000)` | comma-separated Jira project keys |
| `SCOPES` | `VARCHAR2(1000)` | OAuth scopes if applicable |
| `SECRET_REF` | `VARCHAR2(500)` | OCI Vault ref or secret alias, never raw token |
| `REFRESH_SECRET_REF` | `VARCHAR2(500)` | refresh-token secret ref if delegated OAuth |
| `STATUS` | `VARCHAR2(30)` | `Connected`, `Disconnected`, `Error` |
| `LAST_SYNC_AT` | `TIMESTAMP WITH TIME ZONE` | sync center |
| `LAST_ERROR_MESSAGE` | `VARCHAR2(1000)` | safe error text |
| `CREATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `UPDATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `ROW_VERSION` | `NUMBER` | optimistic locking |

- [ ] Create `WORK_ITEMS` for My Tasks, Missions, Quests, AI insights, standup, and overviews:

| Column | Type | Notes |
| --- | --- | --- |
| `TASK_ID` | `NUMBER(19)` | PK, `WORK_ITEMS_SEQ.NEXTVAL` |
| `USER_ID` | `NUMBER(19)` | FK to `APP_USERS` |
| `EXTERNAL_SOURCE` | `VARCHAR2(60)` | `Custom`, `Jira`, `Outlook`|
| `EXTERNAL_ID` | `VARCHAR2(200)` | Jira key, Outlook event ID, To Do ID |
| `PROJECT_KEY` | `VARCHAR2(80)` | Jira/project code |
| `TITLE` | `VARCHAR2(300)` | task table/card title |
| `DESCRIPTION` | `CLOB` | task details |
| `TASK_TYPE` | `VARCHAR2(40)` | `Task`, `Bug`, `Epic`, `Review`, `Meeting` |
| `PRIORITY` | `VARCHAR2(20)` | `Critical`, `High`, `Medium`, `Low` |
| `STATUS` | `VARCHAR2(30)` | `To Do`, `In Progress`, `Blocked`, `Done`, `Upcoming`, `Cancelled` |
| `DUE_DATE` | `DATE` | task form due date |
| `START_DATE` | `DATE` | task form start date |
| `ESTIMATED_MINUTES` | `NUMBER(8)` | effort column |
| `ACTUAL_MINUTES` | `NUMBER(8)` | completion/overview |
| `RCA_TSHIRT_SIZE` | `VARCHAR2(20)` | RCA/Jira complexity estimate: `XS`, `S`, `M`, `L`, `XL`, or `NA` when not applicable |
| `RCA_FILE_CHANGE_COUNT` | `NUMBER(8)` | file-change count used by RCA tool |
| `RCA_COMPLEXITY_SOURCE` | `VARCHAR2(40)` | `RCA`, `Jira`, `Manual`, or similar source marker |
| `RCA_COMPLEXITY_AT` | `TIMESTAMP WITH TIME ZONE` | when RCA complexity was calculated |
| `XP_VALUE` | `NUMBER(8)` | task table, XP cards |
| `LABELS_JSON` | `CLOB` | JSON array for labels/themes |
| `NOTES` | `CLOB` | inline notes, AI context, standup, overview |
| `AI_DIFFICULTY` | `VARCHAR2(20)` | AI cell |
| `AI_IMPACT_SCORE` | `NUMBER(4,2)` | AI cell, mission ranking |
| `AI_PRIORITY_SCORE` | `NUMBER(8,4)` | mission/quest ranking |
| `AI_EFFORT_MINUTES` | `NUMBER(8)` | AI effort estimate |
| `AI_CATEGORY` | `VARCHAR2(60)` | task category |
| `AI_INSIGHT` | `CLOB` | AI insight text |
| `AI_SUGGESTED_ACTION` | `CLOB` | suggested next action |
| `AI_MODEL_VERSION` | `VARCHAR2(200)` | traceability |
| `AI_ENRICHED_AT` | `TIMESTAMP WITH TIME ZONE` | cache freshness |
| `COMPLETED_AT` | `TIMESTAMP WITH TIME ZONE` | completion date inserted on Done |
| `CREATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `UPDATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `ROW_VERSION` | `NUMBER` | optimistic locking |

- [ ] Create `WORK_ITEM_WORK_DATES` for per-day task work tracking and quest membership:

| Column | Type | Notes |
| --- | --- | --- |
| `WORK_ITEM_WORK_DATE_ID` | `NUMBER(19)` | PK, `WORK_ITEM_WORK_DATES_SEQ.NEXTVAL` |
| `USER_ID` | `NUMBER(19)` | FK to `APP_USERS`; owner and query partition |
| `TASK_ID` | `NUMBER(19)` | FK to `WORK_ITEMS` |
| `WORK_DATE` | `DATE` | UTC date user worked/planned the task for the current scope |
| `SOURCE` | `VARCHAR2(40)` | `USER`, `AI_QUEST`, `IMPORT`, `SYSTEM` |
| `PLANNED_MINUTES` | `NUMBER(8)` | optional planning/capacity snapshot |
| `ACTUAL_MINUTES` | `NUMBER(8)` | optional per-day actual effort |
| `NOTES` | `CLOB` | optional per-day work notes |
| `CREATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `UPDATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `ROW_VERSION` | `NUMBER` | optimistic locking |

- [ ] Add `WORK_ITEM_WORK_DATES` behavior:
  - [ ] Enforce `UNIQUE (USER_ID, TASK_ID, WORK_DATE)` so repeated Working Today clicks are idempotent.
  - [ ] On Working Today add, insert the row if absent.
  - [ ] On Working Today revert, delete the active row for that user/task/date.
  - [ ] Keep add/remove history in `WORK_ITEM_EVENTS`; the active table should contain only currently selected worked dates.
  - [ ] Use today's UTC date for writes and reads in the current scope; if the product later switches to user-local dates, update the API contract and tests together.
  - [ ] Use this table as the source of daily/weekly overview analysis and quest membership.

- [ ] Create `WORK_ITEM_EVENTS` for task audit history:

| Column | Type | Notes |
| --- | --- | --- |
| `EVENT_ID` | `NUMBER(19)` | PK, `WORK_ITEM_EVENTS_SEQ.NEXTVAL` |
| `TASK_ID` | `NUMBER(19)` | FK to `WORK_ITEMS` |
| `USER_ID` | `NUMBER(19)` | FK to `APP_USERS` |
| `EVENT_TYPE` | `VARCHAR2(60)` | `TASK_CREATED`, `TASK_UPDATED`, `TASK_COMPLETED`, `NOTES_UPDATED`, `WORKING_TODAY_UPDATED`, `AI_ENRICHED`, `SYNC_CREATED`, `SYNC_UPDATED` |
| `OLD_VALUE_JSON` | `CLOB` | JSON snapshot/diff before change |
| `NEW_VALUE_JSON` | `CLOB` | JSON snapshot/diff after change |
| `CREATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |

- [ ] Create `CALENDAR_EVENTS` for schedule, meetings, capacity, and overview meeting time:

| Column | Type | Notes |
| --- | --- | --- |
| `EVENT_ID` | `NUMBER(19)` | PK, `CALENDAR_EVENTS_SEQ.NEXTVAL` |
| `USER_ID` | `NUMBER(19)` | FK to `APP_USERS` |
| `EXTERNAL_SOURCE` | `VARCHAR2(60)` | usually `Outlook Calendar` |
| `EXTERNAL_ID` | `VARCHAR2(200)` | Outlook event ID |
| `TITLE` | `VARCHAR2(300)` | schedule card title |
| `DESCRIPTION` | `CLOB` | event body/preview |
| `START_AT` | `TIMESTAMP WITH TIME ZONE` | timeline |
| `END_AT` | `TIMESTAMP WITH TIME ZONE` | timeline |
| `DURATION_MINUTES` | `NUMBER(8)` | meeting/capacity metrics |
| `IS_MEETING` | `NUMBER(1)` | 1 for meetings |
| `IS_FOCUS_BLOCK` | `NUMBER(1)` | 1 for focus blocks |
| `ATTENDEE_COUNT` | `NUMBER(6)` | optional meeting signal |
| `COLOR_KEY` | `VARCHAR2(40)` | optional UI timeline color |
| `IS_CANCELLED` | `NUMBER(1)` | recurring/cancelled sync handling |
| `CREATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `UPDATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `ROW_VERSION` | `NUMBER` | optimistic locking |

- [ ] Create `FOCUS_SESSIONS` for Focus Mode and overview focus time:

| Column | Type | Notes |
| --- | --- | --- |
| `FOCUS_SESSION_ID` | `NUMBER(19)` | PK, `FOCUS_SESSIONS_SEQ.NEXTVAL` |
| `USER_ID` | `NUMBER(19)` | FK to `APP_USERS` |
| `TASK_ID` | `NUMBER(19)` | optional FK to `WORK_ITEMS` |
| `SESSION_DATE` | `DATE` | local date |
| `STARTED_AT` | `TIMESTAMP WITH TIME ZONE` | focus timer start |
| `ENDED_AT` | `TIMESTAMP WITH TIME ZONE` | focus timer end |
| `PLANNED_MINUTES` | `NUMBER(8)` | timer target |
| `ACTUAL_MINUTES` | `NUMBER(8)` | overview focus minutes |
| `STATUS` | `VARCHAR2(30)` | `Running`, `Paused`, `Completed`, `Cancelled` |
| `XP_MULTIPLIER` | `NUMBER(5,2)` | from settings |
| `XP_AWARDED` | `NUMBER(8)` | optional focus XP |
| `NOTES` | `CLOB` | optional session notes |
| `CREATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `UPDATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `ROW_VERSION` | `NUMBER` | optimistic locking |

- [ ] Create `AI_RUNS` for AI task enrichment, missions, quests, insights, standup, and overviews:

| Column | Type | Notes |
| --- | --- | --- |
| `AI_RUN_ID` | `NUMBER(19)` | PK, `AI_RUNS_SEQ.NEXTVAL` |
| `USER_ID` | `NUMBER(19)` | FK to `APP_USERS` |
| `RUN_TYPE` | `VARCHAR2(60)` | `TASK_ENRICHMENT`, `MISSION_GENERATION`, `QUEST_GENERATION`, `INSIGHT_GENERATION`, `STANDUP_GENERATION`, `DAILY_OVERVIEW`, `WEEKLY_OVERVIEW` |
| `STATUS` | `VARCHAR2(30)` | `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `VALIDATION_FAILED` |
| `PROVIDER` | `VARCHAR2(40)` | `OCI` |
| `MODEL_ID` | `VARCHAR2(200)` | OCI model ID |
| `AGENT_ENDPOINT_ID` | `VARCHAR2(255)` | when OCI Agent is used |
| `INPUT_HASH` | `VARCHAR2(128)` | cache key |
| `REQUEST_JSON` | `CLOB` | prompt/request JSON |
| `RESPONSE_JSON` | `CLOB` | model response JSON |
| `ERROR_CODE` | `VARCHAR2(100)` | safe error code |
| `ERROR_MESSAGE` | `VARCHAR2(1000)` | safe error message |
| `STARTED_AT` | `TIMESTAMP WITH TIME ZONE` | run timing |
| `COMPLETED_AT` | `TIMESTAMP WITH TIME ZONE` | run timing |
| `CREATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |

- [ ] Create `QUEST_PLANS` for generated quest board metadata:

| Column | Type | Notes |
| --- | --- | --- |
| `QUEST_PLAN_ID` | `NUMBER(19)` | PK, `QUEST_PLANS_SEQ.NEXTVAL` |
| `USER_ID` | `NUMBER(19)` | FK to `APP_USERS` |
| `QUEST_DATE` | `DATE` | date selected in Quests page |
| `SOURCE_AI_RUN_ID` | `NUMBER(19)` | FK to `AI_RUNS` |
| `CAPACITY_MINUTES` | `NUMBER(8)` | total work capacity |
| `MEETING_MINUTES` | `NUMBER(8)` | calendar meeting time |
| `FOCUS_MINUTES` | `NUMBER(8)` | available focus minutes |
| `SUMMARY` | `CLOB` | AI quest plan summary |
| `CREATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `UPDATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `ROW_VERSION` | `NUMBER` | optimistic locking |

- [ ] Create `QUEST_ITEMS` for generated quest ranks and reasons:

| Column | Type | Notes |
| --- | --- | --- |
| `QUEST_ITEM_ID` | `NUMBER(19)` | PK, `QUEST_ITEMS_SEQ.NEXTVAL` |
| `USER_ID` | `NUMBER(19)` | FK to `APP_USERS` |
| `QUEST_PLAN_ID` | `NUMBER(19)` | FK to `QUEST_PLANS` |
| `TASK_ID` | `NUMBER(19)` | FK to `WORK_ITEMS` |
| `RANK_ORDER` | `NUMBER(5)` | quest order |
| `REASON` | `CLOB` | AI reason |
| `SUGGESTED_START_AT` | `TIMESTAMP WITH TIME ZONE` | schedule suggestion |
| `SUGGESTED_END_AT` | `TIMESTAMP WITH TIME ZONE` | schedule suggestion |
| `XP_VALUE` | `NUMBER(8)` | XP snapshot |
| `CREATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |

- [ ] Create `STANDUP_NOTES` for generated standup copy:

| Column | Type | Notes |
| --- | --- | --- |
| `STANDUP_NOTE_ID` | `NUMBER(19)` | PK, `STANDUP_NOTES_SEQ.NEXTVAL` |
| `USER_ID` | `NUMBER(19)` | FK to `APP_USERS` |
| `NOTE_DATE` | `DATE` | standup date |
| `SOURCE_AI_RUN_ID` | `NUMBER(19)` | FK to `AI_RUNS` |
| `ACCOMPLISHED` | `CLOB` | structured JSON or text |
| `IN_PROGRESS` | `CLOB` | structured JSON or text |
| `BLOCKERS` | `CLOB` | structured JSON or text |
| `NEXT_STEPS` | `CLOB` | structured JSON or text |
| `FULL_NOTE` | `CLOB` | UI preformatted note |
| `CREATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `UPDATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `ROW_VERSION` | `NUMBER` | optimistic locking |

- [ ] Create `DAILY_OVERVIEWS` for Daily Overview page:

| Column | Type | Notes |
| --- | --- | --- |
| `DAILY_OVERVIEW_ID` | `NUMBER(19)` | PK, `DAILY_OVERVIEWS_SEQ.NEXTVAL` |
| `USER_ID` | `NUMBER(19)` | FK to `APP_USERS` |
| `OVERVIEW_DATE` | `DATE` | selected local date |
| `SOURCE_AI_RUN_ID` | `NUMBER(19)` | FK to `AI_RUNS` |
| `TASKS_COMPLETED` | `NUMBER(8)` | daily stat |
| `XP_EARNED` | `NUMBER(8)` | daily stat |
| `MEETING_MINUTES` | `NUMBER(8)` | editable/tracked daily stat |
| `FOCUS_MINUTES` | `NUMBER(8)` | editable/tracked daily stat |
| `NEW_LEARNINGS` | `CLOB` | overview form and AI summary |
| `WENT_WELL` | `CLOB` | overview form and AI summary |
| `WENT_WRONG` | `CLOB` | overview form and AI summary |
| `SUMMARY` | `CLOB` | AI daily summary |
| `CREATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `UPDATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `ROW_VERSION` | `NUMBER` | optimistic locking |

- [ ] Create `WEEKLY_OVERVIEWS` for Weekly Overview page:

| Column | Type | Notes |
| --- | --- | --- |
| `WEEKLY_OVERVIEW_ID` | `NUMBER(19)` | PK, `WEEKLY_OVERVIEWS_SEQ.NEXTVAL` |
| `USER_ID` | `NUMBER(19)` | FK to `APP_USERS` |
| `WEEK_START_DATE` | `DATE` | Monday/local start |
| `WEEK_END_DATE` | `DATE` | Sunday/local end |
| `SOURCE_AI_RUN_ID` | `NUMBER(19)` | FK to `AI_RUNS` |
| `TASKS_COMPLETED` | `NUMBER(8)` | weekly stat |
| `XP_EARNED` | `NUMBER(8)` | weekly stat |
| `MEETING_MINUTES` | `NUMBER(8)` | weekly stat |
| `FOCUS_MINUTES` | `NUMBER(8)` | weekly stat |
| `TOP_ACCOMPLISHMENTS` | `CLOB` | structured JSON or text |
| `NEW_LEARNINGS` | `CLOB` | weekly learnings |
| `THEMES` | `CLOB` | JSON array or text |
| `SUMMARY` | `CLOB` | AI weekly summary |
| `CREATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `UPDATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |
| `ROW_VERSION` | `NUMBER` | optimistic locking |

- [ ] Create `SYNC_RUNS` for Sync Center:

| Column | Type | Notes |
| --- | --- | --- |
| `SYNC_RUN_ID` | `NUMBER(19)` | PK, `SYNC_RUNS_SEQ.NEXTVAL` |
| `USER_ID` | `NUMBER(19)` | FK to `APP_USERS` |
| `STATUS` | `VARCHAR2(30)` | `QUEUED`, `RUNNING`, `SUCCEEDED`, `PARTIAL`, `FAILED` |
| `REQUEST_JSON` | `CLOB` | sources/date range requested |
| `STARTED_AT` | `TIMESTAMP WITH TIME ZONE` | timing |
| `COMPLETED_AT` | `TIMESTAMP WITH TIME ZONE` | timing |
| `ERROR_MESSAGE` | `VARCHAR2(1000)` | safe error |
| `CREATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |

- [ ] Create `SYNC_RUN_ITEMS` for per-source sync status:

| Column | Type | Notes |
| --- | --- | --- |
| `SYNC_RUN_ITEM_ID` | `NUMBER(19)` | PK, `SYNC_RUN_ITEMS_SEQ.NEXTVAL` |
| `USER_ID` | `NUMBER(19)` | FK to `APP_USERS` |
| `SYNC_RUN_ID` | `NUMBER(19)` | FK to `SYNC_RUNS` |
| `SOURCE` | `VARCHAR2(60)` | `Jira`, `Outlook Calendar` |
| `STATUS` | `VARCHAR2(30)` | `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED` |
| `CREATED_COUNT` | `NUMBER(8)` | sync summary |
| `UPDATED_COUNT` | `NUMBER(8)` | sync summary |
| `FAILED_COUNT` | `NUMBER(8)` | sync summary |
| `ERROR_MESSAGE` | `VARCHAR2(1000)` | safe error |
| `STARTED_AT` | `TIMESTAMP WITH TIME ZONE` | timing |
| `COMPLETED_AT` | `TIMESTAMP WITH TIME ZONE` | timing |

- [ ] Create `IDEMPOTENCY_KEYS` for safe retries on create/generate/sync endpoints:

| Column | Type | Notes |
| --- | --- | --- |
| `IDEMPOTENCY_KEY` | `VARCHAR2(120)` | PK, client retry token |
| `USER_ID` | `NUMBER(19)` | FK to `APP_USERS` |
| `METHOD` | `VARCHAR2(10)` | request method |
| `PATH` | `VARCHAR2(500)` | request path |
| `REQUEST_HASH` | `VARCHAR2(128)` | body hash |
| `RESPONSE_JSON` | `CLOB` | cached response |
| `STATUS_CODE` | `NUMBER(3)` | cached status |
| `CREATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |

- [ ] Optional `EXTERNAL_OBJECTS` for raw connector payload snapshots:

| Column | Type | Notes |
| --- | --- | --- |
| `EXTERNAL_OBJECT_ID` | `NUMBER(19)` | PK, add sequence if implemented |
| `USER_ID` | `NUMBER(19)` | FK to `APP_USERS` |
| `SOURCE` | `VARCHAR2(60)` | external system |
| `EXTERNAL_ID` | `VARCHAR2(200)` | source object ID |
| `OBJECT_TYPE` | `VARCHAR2(60)` | issue, event, todo |
| `PAYLOAD_JSON` | `CLOB` | raw payload, redact secrets |
| `SYNC_RUN_ID` | `NUMBER(19)` | FK to `SYNC_RUNS` |
| `CREATED_AT` | `TIMESTAMP WITH TIME ZONE` | audit |

- [ ] Add indexes:
  - [ ] `APP_USERS(EMAIL)` unique.
  - [ ] `USER_STATS(USER_ID)` unique.
  - [ ] `USER_INTEGRATIONS(USER_ID, PROVIDER)` unique.
  - [ ] `WORK_ITEMS(USER_ID, STATUS)`
  - [ ] `WORK_ITEMS(USER_ID, COMPLETED_AT)`
  - [ ] `WORK_ITEMS(USER_ID, UPDATED_AT)`
  - [ ] `WORK_ITEMS` function-based unique index for non-null external IDs only, for example `WORK_ITEMS_SOURCE_EXT_UK` on `CASE WHEN EXTERNAL_ID IS NOT NULL THEN USER_ID/EXTERNAL_SOURCE/EXTERNAL_ID END`.
  - [ ] `WORK_ITEM_WORK_DATES(USER_ID, WORK_DATE)`
  - [ ] `WORK_ITEM_WORK_DATES(USER_ID, TASK_ID, WORK_DATE)` unique.
  - [ ] `CALENDAR_EVENTS(USER_ID, START_AT)`
  - [ ] `CALENDAR_EVENTS(USER_ID, EXTERNAL_SOURCE, EXTERNAL_ID)` unique for synced events.
  - [ ] `FOCUS_SESSIONS(USER_ID, SESSION_DATE)`
  - [ ] `AI_RUNS(USER_ID, RUN_TYPE, CREATED_AT)`
  - [ ] `QUEST_PLANS(USER_ID, QUEST_DATE)` unique.
  - [ ] `QUEST_ITEMS(USER_ID, QUEST_PLAN_ID, TASK_ID)` unique.
  - [ ] `STANDUP_NOTES(USER_ID, NOTE_DATE)` unique.
  - [ ] `DAILY_OVERVIEWS(USER_ID, OVERVIEW_DATE)` unique.
  - [ ] `WEEKLY_OVERVIEWS(USER_ID, WEEK_START_DATE)` unique.
  - [ ] `WORK_ITEM_EVENTS(USER_ID, TASK_ID, CREATED_AT)`
  - [ ] `SYNC_RUNS(USER_ID, CREATED_AT)`
  - [ ] `SYNC_RUN_ITEMS(USER_ID, SYNC_RUN_ID, SOURCE)`

- [ ] Add constraints:
  - [ ] Work item status enum.
  - [ ] Work item priority enum.
  - [ ] Work item source enum.
  - [ ] Work item task type enum.
  - [ ] AI run status enum.
  - [ ] Sync run status enum.
  - [ ] Connector provider enum.
  - [ ] Unique external source keys for synced items.
  - [ ] Unique work-date row per user/task/date.
  - [ ] Unique daily/weekly overview rows per user/date.

- [ ] Add normalized worked-date tracking:
  - [ ] Create one `WORK_ITEM_WORK_DATES` row per user/task/date that is currently selected as worked/planned.
  - [ ] Do not store comma-separated dates on `WORK_ITEMS`.
  - [ ] Treat `working_today` as a derived API field based on whether a row exists for the requested date.
  - [ ] Treat `worked_dates` response arrays as derived from `WORK_ITEM_WORK_DATES`, not stored on `WORK_ITEMS`.
  - [ ] Query daily and weekly overview inputs from `WORK_ITEM_WORK_DATES` using indexed date ranges.
  - [ ] Use `WORK_ITEM_EVENTS` for historical add/remove audit, especially when a user reverts a Working Today action.

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

- [ ] Implement `WORK_ITEM_WORK_DATES` repository helpers:
  - [ ] Insert work-date row if absent.
  - [ ] Delete work-date row if present.
  - [ ] List worked dates for a task.
  - [ ] List tasks for a day or date range.
  - [ ] Detect row existence for `working_today` derivation.

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
  - [ ] `worked_dates`
  - [ ] `run_ai_enrichment`

- [ ] Insert steps:
  - [ ] Validate required fields and enums.
  - [ ] Insert into `WORK_ITEMS` without passing `TASK_ID`.
  - [ ] Fetch generated `TASK_ID` via `RETURNING TASK_ID INTO`.
  - [ ] Insert `WORK_ITEM_EVENTS` with `EVENT_TYPE = 'TASK_CREATED'`.
  - [ ] If `working_today = true`, insert today's work-date row into `WORK_ITEM_WORK_DATES`.
  - [ ] If `worked_dates` is supplied, validate, deduplicate, and insert one `WORK_ITEM_WORK_DATES` row per date.
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
  - [ ] Filter by `working_today`, derived from whether a `WORK_ITEM_WORK_DATES` row exists for the requested date.
  - [ ] Filter by `worked_date`, using an indexed join to `WORK_ITEM_WORK_DATES`.
  - [ ] Filter by completion date.
  - [ ] Search title, description, and notes.
  - [ ] Add pagination.

- [ ] Implement `GET /api/v1/tasks/{task_id}`.
  - [ ] Return full task.
  - [ ] Return notes.
  - [ ] Return AI fields.
  - [ ] Return `worked_dates` as an array derived from `WORK_ITEM_WORK_DATES`.
  - [ ] Return working-today state derived from `WORK_ITEM_WORK_DATES`.
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
  - [ ] `worked_dates`

- [ ] Update steps:
  - [ ] Lock or update task by `TASK_ID`, `USER_ID`, and `ROW_VERSION`.
  - [ ] Validate ownership.
  - [ ] Apply only provided fields.
  - [ ] If status changes to `Done`, set `COMPLETED_AT`.
  - [ ] If `worked_dates` changes through an explicit bulk-edit path, replace that task's `WORK_ITEM_WORK_DATES` rows transactionally.
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

## Phase 7: Work Date Rows And Quests Source Of Truth

- [ ] Implement `PUT /api/v1/tasks/{task_id}/today`.
  - [ ] Validate task belongs to current user.
  - [ ] Resolve `work_date` as today's UTC date.
  - [ ] Accept `is_working_today`.
  - [ ] If `is_working_today = true`, insert into `WORK_ITEM_WORK_DATES` if the row is absent.
  - [ ] If `is_working_today = false`, delete the matching `WORK_ITEM_WORK_DATES` row if present.
  - [ ] Treat repeated add/remove requests as idempotent success.
  - [ ] Increment `WORK_ITEMS.ROW_VERSION` or return a work-date row version depending on final API contract.
  - [ ] Insert `WORK_ITEM_EVENTS` with `EVENT_TYPE = 'WORKING_TODAY_UPDATED'`.

- [ ] Implement `GET /api/v1/daily-work`.
  - [ ] Return all `WORK_ITEMS` joined to `WORK_ITEM_WORK_DATES` for the requested date.
  - [ ] Use indexed date lookup on `WORK_ITEM_WORK_DATES(USER_ID, WORK_DATE)`.
  - [ ] Include completion state.
  - [ ] Include notes and actual minutes.
  - [ ] Return `worked_dates` as an array derived from `WORK_ITEM_WORK_DATES`.
  - [ ] Return `working_today` derived from matching row existence.

- [ ] Implement `GET /api/v1/quests/today`.
  - [ ] Read from `WORK_ITEM_WORK_DATES` joined to `WORK_ITEMS`.
  - [ ] Include only tasks with a work-date row for the selected date.
  - [ ] Join latest quest plan if present.
  - [ ] Return ranked quest cards.
  - [ ] Order by quest plan rank when present, otherwise by AI priority score, priority, XP, and due date.

## Phase 7A: Missions Versus Quests

- [ ] Define product semantics in backend docs and API names:
  - [ ] Mission means AI/system-recommended task.
  - [ ] Quest means user-selected committed work for a specific date.
  - [ ] A task can appear as a mission without being a quest.
  - [ ] A task becomes a quest when a `WORK_ITEM_WORK_DATES` row exists for that task and date.

- [ ] Tables used for generating Missions:
  - [ ] `WORK_ITEMS` for open tasks, priority, status, due dates, notes, XP, and AI fields.
  - [ ] `WORK_ITEM_WORK_DATES` for whether a task is already selected for a mission/quest date.
  - [ ] `CALENDAR_EVENTS` for meeting load and available focus windows.
  - [ ] `APP_USERS` for timezone and workday settings.
  - [ ] `AI_RUNS` for cached mission-generation input/output and auditability.
  - [ ] Optional `WORK_ITEM_EVENTS` for recent activity signals.
  - [ ] Optional `QUEST_PLANS` and `QUEST_ITEMS` to avoid recommending tasks already committed as quests for the same date.

- [ ] Tables used for generating Quests:
  - [ ] `WORK_ITEM_WORK_DATES` as the source of committed quest membership.
  - [ ] `WORK_ITEMS` for task details and AI fields.
  - [ ] `QUEST_PLANS` for generated quest plan metadata, capacity summary, and AI summary.
  - [ ] `QUEST_ITEMS` for generated quest rank, reason, suggested start/end, and XP snapshot.
  - [ ] `CALENDAR_EVENTS` for scheduling quest suggestions around meetings.
  - [ ] `AI_RUNS` for quest-generation request/response tracking.

- [ ] Implement Mission ranking data query:
  - [ ] Read candidate tasks from `WORK_ITEMS`.
  - [ ] Exclude `STATUS IN ('Done','Cancelled')`.
  - [ ] Include task fields: `TASK_ID`, `TITLE`, `DESCRIPTION`, `PRIORITY`, `STATUS`, `TASK_TYPE`, `DUE_AT`, `ESTIMATED_MINUTES`, `XP_VALUE`, `NOTES`.
  - [ ] Include AI fields: `AI_DIFFICULTY`, `AI_IMPACT_SCORE`, `AI_PRIORITY_SCORE`, `AI_EFFORT_MINUTES`, `AI_CATEGORY`, `AI_INSIGHT`.
  - [ ] Include whether a `WORK_ITEM_WORK_DATES` row exists for the mission date.
  - [ ] Include available capacity from `CALENDAR_EVENTS` and `APP_USERS`.

- [ ] Implement `GET /api/v1/missions/today`.
  - [ ] Accept `date`.
  - [ ] Accept `limit`, default 3 or 5.
  - [ ] Read open candidate tasks from `WORK_ITEMS`.
  - [ ] Read capacity from `CALENDAR_EVENTS` and `APP_USERS`.
  - [ ] Rank using cached AI output when available.
  - [ ] Fall back to deterministic ranking if AI output is unavailable.
  - [ ] Return mission cards with `task_id`, title, priority, effort, XP, impact, rank, reason, and `is_quest_for_date`.
  - [ ] Do not mutate `WORK_ITEM_WORK_DATES`.

- [ ] Implement deterministic Mission fallback ranking:
  - [ ] Prefer higher `AI_PRIORITY_SCORE`.
  - [ ] Prefer higher `AI_IMPACT_SCORE`.
  - [ ] Prefer higher explicit priority.
  - [ ] Prefer due soon tasks.
  - [ ] Prefer tasks that fit available focus minutes.
  - [ ] Prefer not-done, not-cancelled tasks.
  - [ ] Deprioritize tasks already selected as quests for the same date unless the UI wants to show them with `is_quest_for_date = true`.

- [ ] Implement `POST /api/v1/missions/generate`.
  - [ ] Accept `date`, `limit`, `include_already_selected`, and optional candidate task IDs.
  - [ ] Insert `AI_RUNS` with `RUN_TYPE = 'MISSION_GENERATION'`.
  - [ ] Send compact task, notes, AI score, due-date, and capacity context to OCI GenAI.
  - [ ] Validate returned task IDs exist in the candidate set.
  - [ ] Store AI response in `AI_RUNS`.
  - [ ] Return mission recommendations.
  - [ ] Do not insert work-date rows.

- [ ] Mission response fields:
  - [ ] `date`
  - [ ] `missions[].task_id`
  - [ ] `missions[].rank_order`
  - [ ] `missions[].title`
  - [ ] `missions[].priority`
  - [ ] `missions[].status`
  - [ ] `missions[].estimated_minutes`
  - [ ] `missions[].xp_value`
  - [ ] `missions[].ai_impact_score`
  - [ ] `missions[].reason`
  - [ ] `missions[].suggested_action`
  - [ ] `missions[].is_quest_for_date`

- [ ] Implement Mission to Quest conversion endpoint behavior:
  - [ ] Use existing `PUT /api/v1/tasks/{task_id}/today`.
  - [ ] Frontend button label should be `Add to Today's Quests` or `Work Today`.
  - [ ] Backend inserts a row into `WORK_ITEM_WORK_DATES`.
  - [ ] Backend inserts `WORK_ITEM_EVENTS` with `EVENT_TYPE = 'WORKING_TODAY_UPDATED'`.
  - [ ] Response returns updated `worked_dates` and `working_today`.

- [ ] Implement Quest retrieval rules:
  - [ ] `GET /api/v1/quests/today` reads tasks joined through `WORK_ITEM_WORK_DATES` for the requested date.
  - [ ] Join `QUEST_ITEMS` when a generated plan exists.
  - [ ] If no generated plan exists, rank quests by priority, AI priority score, XP, and due date.
  - [ ] Return `source = 'WORK_ITEM_WORK_DATES'` in metadata.

- [ ] Implement Quest generation rules:
  - [ ] `POST /api/v1/quests/generate` can read from mission recommendations or open tasks.
  - [ ] When AI selects tasks as quests, insert one `WORK_ITEM_WORK_DATES` row for each selected task/date if absent.
  - [ ] Persist generated ranking in `QUEST_PLANS` and `QUEST_ITEMS`.
  - [ ] Keep `WORK_ITEM_WORK_DATES` as the source of truth for quest membership.

- [ ] UI flow expected by backend:
  - [ ] Dashboard calls `GET /api/v1/missions/today`.
  - [ ] Dashboard mission card shows `Add to Today's Quests` if `is_quest_for_date = false`.
  - [ ] Dashboard mission card shows `Added to Quests` if `is_quest_for_date = true`.
  - [ ] Clicking add calls `PUT /api/v1/tasks/{task_id}/today`.
  - [ ] Quests page calls `GET /api/v1/quests/today`.
  - [ ] Quests page date picker calls the same endpoint with selected date.

## Phase 8: Dashboard And Capacity APIs

- [x] Implement `GET /api/v1/dashboard/today`.
  - [x] Return stats.
  - [x] Return top missions.
  - [x] Return schedule.
  - [x] Return AI insight.
  - [x] Avoid frontend request waterfalls.
  - [x] Keep mock/real AI selection environment-driven so teammates without OCI GenAI can run locally.
  - [x] Wire the existing dashboard UI to consume the endpoint with fallback to local UI data.

- [x] Implement `GET /api/v1/capacity`.
  - [x] Read user workday settings.
  - [x] Read calendar events.
  - [x] Calculate meeting minutes.
  - [x] Calculate available focus minutes.
  - [x] Calculate suggested focus windows.

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
  - [ ] For XP, prefer applicable RCA T-shirt sizing (`XS`-`XL`) when present; treat `NA` as no RCA size; otherwise infer from AI difficulty/effort/impact; otherwise use deterministic default XP.
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

## Phase 12: AI Mission And Quest Generation Endpoints

- [ ] Implement `POST /api/v1/missions/generate`.
  - [ ] Read candidate tasks from `WORK_ITEMS`.
  - [ ] Include `RCA_TSHIRT_SIZE`, `RCA_FILE_CHANGE_COUNT`, and existing `XP_VALUE` in AI context.
  - [ ] Exclude completed and cancelled tasks.
  - [ ] Read calendar capacity from `CALENDAR_EVENTS`.
  - [ ] Use `APP_USERS` timezone and workday settings.
  - [ ] Call OCI GenAI for recommended mission ranking.
  - [ ] Validate returned task IDs exist in the candidate set.
  - [ ] Store request and response in `AI_RUNS`.
  - [ ] Return recommendations only; do not mutate `WORK_ITEM_WORK_DATES`.

- [ ] Implement `POST /api/v1/quests/generate`.
  - [ ] Read candidate tasks.
  - [ ] If `respect_working_today = true`, use tasks with a `WORK_ITEM_WORK_DATES` row for the quest date.
  - [ ] If `from_missions = true`, use mission recommendations as candidate tasks.
  - [ ] Read calendar capacity.
  - [ ] Call OCI GenAI for ranked quest plan.
  - [ ] Validate returned task IDs exist in candidate set.
  - [ ] Upsert `QUEST_PLANS`.
  - [ ] Delete/reinsert `QUEST_ITEMS`.
  - [ ] Insert one `WORK_ITEM_WORK_DATES` row for each selected task/date if absent.
  - [ ] Rely on `UNIQUE (USER_ID, TASK_ID, WORK_DATE)` for dedupe/idempotency.
  - [ ] Return quest plan and AI run ID.

- [ ] Mission prompt output fields:
  - [ ] `summary`
  - [ ] `missions[].task_id`
  - [ ] `missions[].rank_order`
  - [ ] `missions[].reason`
  - [ ] `missions[].suggested_action`
  - [ ] `missions[].is_quest_candidate`

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
  - [ ] Read tasks joined through `WORK_ITEM_WORK_DATES` for the selected date.
  - [ ] Include RCA T-shirt sizing and existing XP in task insight context.
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
  - [ ] Read in-progress tasks joined through `WORK_ITEM_WORK_DATES` for the selected date.
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
  - [ ] Read tasks joined through `WORK_ITEM_WORK_DATES` for the selected date.
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
  - [ ] Preserve local `WORK_ITEM_WORK_DATES` rows.
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

## Phase 19: Sync APIs

- [ ] Use the `SYNC_RUNS` and `SYNC_RUN_ITEMS` schemas defined in Phase 2.
  - [ ] Persist one `SYNC_RUNS` row per user-triggered sync.
  - [ ] Persist one `SYNC_RUN_ITEMS` row per source inside that sync.
  - [ ] Update created, updated, and failed counts per source.
  - [ ] Store safe error messages only.

- [ ] Implement `POST /api/v1/sync/run`.
  - [ ] Accept sources.
  - [ ] Create sync run.
  - [ ] Run Jira sync.
  - [ ] Run Outlook Calendar sync.
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
  - [ ] Working Today insert, delete, and idempotency in `WORK_ITEM_WORK_DATES`.
  - [ ] Working-today derivation from `WORK_ITEM_WORK_DATES`.
  - [ ] Mission generation does not mutate `WORK_ITEM_WORK_DATES`.
  - [ ] Mission to Quest conversion inserts selected date into `WORK_ITEM_WORK_DATES`.
  - [ ] Quest read from `WORK_ITEM_WORK_DATES`.
  - [ ] Capacity calculation.
  - [ ] AI response validation.
  - [ ] Idempotency.

- [ ] Integration tests:
  - [ ] Oracle insert transaction rollback.
  - [ ] Oracle update row-version conflict.
  - [ ] Jira issue upsert.
  - [ ] Outlook event upsert.

  - [ ] OCI GenAI success.
  - [ ] OCI GenAI timeout.
  - [ ] OCI Agent historical insight.

- [ ] API contract tests:
  - [ ] `POST /tasks`.
  - [ ] `PATCH /tasks/{task_id}`.
  - [ ] `POST /tasks/{task_id}/complete`.
  - [ ] `PUT /tasks/{task_id}/today`.
  - [ ] `GET /missions/today`.
  - [ ] `POST /missions/generate`.
  - [ ] `GET /quests/today`.
  - [ ] `POST /quests/generate`.
  - [ ] `POST /standup-notes/generate`.
  - [ ] `POST /overviews/daily/generate`.
  - [ ] `POST /sync/run`.

## Phase 23: Frontend Wiring Support

- [ ] Provide stable API response shapes for frontend.
- [ ] Return all IDs as numbers.
- [ ] Return `row_version` for editable records.
- [ ] Return `working_today` on task list rows.
- [ ] Return `worked_dates` as an array derived from `WORK_ITEM_WORK_DATES`.
- [ ] Return `completed_at` after done action.
- [ ] Return task `notes`.
- [ ] Return AI insight fields expected by task table and insights page.
- [ ] Keep leaderboard disabled or hidden for now.

## Recommended Build Order

1. Backend project structure and Oracle DB pool.
2. Schema migrations and sequences.
3. Task create/read/update/complete APIs.
4. Worked-date and working-today APIs.
5. Missions read API and deterministic ranking.
6. Dashboard and capacity APIs.
7. Calendar event APIs.
8. OCI GenAI client and task enrichment.
9. AI mission generation.
10. Mission to Quest conversion and quest read API.
11. AI quest generation.
12. Standup generator.
13. Daily and weekly overview generation.
14. Jira connector.
15. Outlook Calendar connector.
17. Sync orchestration APIs.
18. OCI Agent historical insights.
19. Security, rate limits, observability, and full tests.
20. A login screen for username, Email and jira access details.

DB scripts already run:
-- =========================================================
-- Sequences
-- =========================================================

CREATE SEQUENCE WORK_ITEMS_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE;
CREATE SEQUENCE WORK_ITEM_WORK_DATES_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE;
CREATE SEQUENCE WORK_ITEM_EVENTS_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE;
CREATE SEQUENCE DAILY_OVERVIEWS_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE;
CREATE SEQUENCE WEEKLY_OVERVIEWS_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE;

CREATE SEQUENCE APP_USERS_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE;

-- =========================================================
APP_USERS
-- =========================================================

CREATE TABLE APP_USERS (
  USER_ID NUMBER(19) DEFAULT APP_USERS_SEQ.NEXTVAL PRIMARY KEY,
  FIRST_NAME VARCHAR2(200) NOT NULL,
  LAST_NAME VARCHAR2(200) NOT NULL,
  EMAIL VARCHAR2(320) NOT NULL,
  USERNAME VARCHAR2(120),
  ROLE_NAME VARCHAR2(80) DEFAULT 'developer' NOT NULL,
  TIMEZONE VARCHAR2(80) DEFAULT 'Asia/Calcutta' NOT NULL,
  WORKDAY_START_LOCAL VARCHAR2(5) DEFAULT '09:00' NOT NULL,
  WORKDAY_END_LOCAL VARCHAR2(5) DEFAULT '17:00' NOT NULL,
  FOCUS_XP_MULTIPLIER NUMBER(5,2) DEFAULT 1.25 NOT NULL,
  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  UPDATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  ROW_VERSION NUMBER DEFAULT 1 NOT NULL,

  CONSTRAINT APP_USERS_EMAIL_UK UNIQUE (EMAIL),
  CONSTRAINT APP_USERS_USERNAME_UK UNIQUE (USERNAME),
  CONSTRAINT APP_USERS_ROLE_CK CHECK (ROLE_NAME IN ('developer', 'QA', 'DevOps', 'manager')),
  CONSTRAINT APP_USERS_WORKDAY_START_CK CHECK (REGEXP_LIKE(WORKDAY_START_LOCAL, '^\d{2}:\d{2}$')),
  CONSTRAINT APP_USERS_WORKDAY_END_CK CHECK (REGEXP_LIKE(WORKDAY_END_LOCAL, '^\d{2}:\d{2}$')),
  CONSTRAINT APP_USERS_FOCUS_MULTIPLIER_CK CHECK (FOCUS_XP_MULTIPLIER >= 0)
);

CREATE INDEX APP_USERS_USERNAME_IX ON APP_USERS (USERNAME);



-- =========================================================
-- WORK_ITEMS
-- =========================================================

CREATE TABLE WORK_ITEMS (
  TASK_ID NUMBER(19) DEFAULT WORK_ITEMS_SEQ.NEXTVAL PRIMARY KEY,
  USER_ID NUMBER(19) NOT NULL,
  EXTERNAL_SOURCE VARCHAR2(60) DEFAULT 'Custom' NOT NULL,
  EXTERNAL_ID VARCHAR2(200),
  PROJECT_KEY VARCHAR2(80),
  TITLE VARCHAR2(300) NOT NULL,
  DESCRIPTION CLOB,
  TASK_TYPE VARCHAR2(40) DEFAULT 'Task' NOT NULL,
  PRIORITY VARCHAR2(20) DEFAULT 'Medium' NOT NULL,
  STATUS VARCHAR2(30) DEFAULT 'To Do' NOT NULL,
  DUE_DATE DATE,
  START_DATE DATE,
  ESTIMATED_MINUTES NUMBER(8) DEFAULT 0 NOT NULL,
  ACTUAL_MINUTES NUMBER(8) DEFAULT 0 NOT NULL,
  XP_VALUE NUMBER(8) DEFAULT 0 NOT NULL,
  RCA_TSHIRT_SIZE VARCHAR2(20),
  RCA_FILE_CHANGE_COUNT NUMBER(8),
  RCA_COMPLEXITY_SOURCE VARCHAR2(40),
  RCA_COMPLEXITY_AT TIMESTAMP WITH TIME ZONE,
  LABELS_JSON CLOB,
  NOTES CLOB,
  AI_DIFFICULTY VARCHAR2(20),
  AI_IMPACT_SCORE NUMBER(4,2),
  AI_PRIORITY_SCORE NUMBER(8,4),
  AI_EFFORT_MINUTES NUMBER(8),
  AI_CATEGORY VARCHAR2(60),
  AI_INSIGHT CLOB,
  AI_SUGGESTED_ACTION CLOB,
  AI_MODEL_VERSION VARCHAR2(200),
  AI_ENRICHED_AT TIMESTAMP WITH TIME ZONE,
  COMPLETED_AT TIMESTAMP WITH TIME ZONE,
  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  UPDATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  ROW_VERSION NUMBER DEFAULT 1 NOT NULL,

  CONSTRAINT WORK_ITEMS_USER_FK FOREIGN KEY (USER_ID) REFERENCES APP_USERS(USER_ID),
  CONSTRAINT WORK_ITEMS_USER_TASK_UK UNIQUE (USER_ID, TASK_ID),
  CONSTRAINT WORK_ITEMS_STATUS_CK CHECK (STATUS IN ('To Do', 'In Progress', 'Blocked', 'Done', 'Upcoming', 'Cancelled')),
  CONSTRAINT WORK_ITEMS_PRIORITY_CK CHECK (PRIORITY IN ('Critical', 'High', 'Medium', 'Low')),
  CONSTRAINT WORK_ITEMS_TYPE_CK CHECK (TASK_TYPE IN ('Task', 'Bug', 'Epic', 'Review', 'Meeting')),
  CONSTRAINT WORK_ITEMS_SOURCE_CK CHECK (EXTERNAL_SOURCE IN ('Custom', 'Jira', 'Outlook')),
  CONSTRAINT WORK_ITEMS_RCA_TSHIRT_CK CHECK (RCA_TSHIRT_SIZE IS NULL OR RCA_TSHIRT_SIZE IN ('XS', 'S', 'M', 'L', 'XL', 'NA'))
);

CREATE INDEX WORK_ITEMS_USER_STATUS_IX ON WORK_ITEMS (USER_ID, STATUS);
CREATE INDEX WORK_ITEMS_USER_COMPLETED_IX ON WORK_ITEMS (USER_ID, COMPLETED_AT);
CREATE INDEX WORK_ITEMS_USER_UPDATED_IX ON WORK_ITEMS (USER_ID, UPDATED_AT);

CREATE UNIQUE INDEX WORK_ITEMS_EXTERNAL_UK
ON WORK_ITEMS (
  CASE WHEN EXTERNAL_ID IS NOT NULL THEN USER_ID END,
  CASE WHEN EXTERNAL_ID IS NOT NULL THEN EXTERNAL_SOURCE END,
  CASE WHEN EXTERNAL_ID IS NOT NULL THEN EXTERNAL_ID END
);


-- =========================================================
-- WORK_ITEM_WORK_DATES
-- =========================================================

CREATE TABLE WORK_ITEM_WORK_DATES (
  WORK_ITEM_WORK_DATE_ID NUMBER(19) DEFAULT WORK_ITEM_WORK_DATES_SEQ.NEXTVAL PRIMARY KEY,
  USER_ID NUMBER(19) NOT NULL,
  TASK_ID NUMBER(19) NOT NULL,
  WORK_DATE DATE NOT NULL,
  SOURCE VARCHAR2(40) DEFAULT 'USER' NOT NULL,
  PLANNED_MINUTES NUMBER(8),
  ACTUAL_MINUTES NUMBER(8),
  NOTES CLOB,
  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  UPDATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  ROW_VERSION NUMBER DEFAULT 1 NOT NULL,

  CONSTRAINT WIWD_USER_FK FOREIGN KEY (USER_ID) REFERENCES APP_USERS(USER_ID),
  CONSTRAINT WIWD_WORK_ITEM_FK FOREIGN KEY (USER_ID, TASK_ID) REFERENCES WORK_ITEMS(USER_ID, TASK_ID),
  CONSTRAINT WIWD_USER_TASK_DATE_UK UNIQUE (USER_ID, TASK_ID, WORK_DATE),
  CONSTRAINT WIWD_SOURCE_CK CHECK (SOURCE IN ('USER', 'AI_QUEST', 'IMPORT', 'SYSTEM'))
);

CREATE INDEX WIWD_USER_DATE_IX ON WORK_ITEM_WORK_DATES (USER_ID, WORK_DATE);


-- =========================================================
-- WORK_ITEM_EVENTS
-- =========================================================

CREATE TABLE WORK_ITEM_EVENTS (
  EVENT_ID NUMBER(19) DEFAULT WORK_ITEM_EVENTS_SEQ.NEXTVAL PRIMARY KEY,
  USER_ID NUMBER(19) NOT NULL,
  TASK_ID NUMBER(19) NOT NULL,
  EVENT_TYPE VARCHAR2(60) NOT NULL,
  OLD_VALUE_JSON CLOB,
  NEW_VALUE_JSON CLOB,
  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,

  CONSTRAINT WORK_ITEM_EVENTS_USER_FK FOREIGN KEY (USER_ID) REFERENCES APP_USERS(USER_ID),
  CONSTRAINT WORK_ITEM_EVENTS_TASK_FK FOREIGN KEY (USER_ID, TASK_ID) REFERENCES WORK_ITEMS(USER_ID, TASK_ID),
  CONSTRAINT WORK_ITEM_EVENTS_TYPE_CK CHECK (
    EVENT_TYPE IN (
      'TASK_CREATED',
      'TASK_UPDATED',
      'TASK_COMPLETED',
      'NOTES_UPDATED',
      'WORKING_TODAY_UPDATED',
      'AI_ENRICHED',
      'SYNC_CREATED',
      'SYNC_UPDATED'
    )
  )
);

CREATE INDEX WORK_ITEM_EVENTS_USER_TASK_CREATED_IX
ON WORK_ITEM_EVENTS (USER_ID, TASK_ID, CREATED_AT);


-- =========================================================
-- DAILY_OVERVIEWS
-- =========================================================

CREATE TABLE DAILY_OVERVIEWS (
  DAILY_OVERVIEW_ID NUMBER(19) DEFAULT DAILY_OVERVIEWS_SEQ.NEXTVAL PRIMARY KEY,
  USER_ID NUMBER(19) NOT NULL,
  OVERVIEW_DATE DATE NOT NULL,
  SOURCE_AI_RUN_ID NUMBER(19),
  TASKS_COMPLETED NUMBER(8) DEFAULT 0 NOT NULL,
  XP_EARNED NUMBER(8) DEFAULT 0 NOT NULL,
  MEETING_MINUTES NUMBER(8) DEFAULT 0 NOT NULL,
  FOCUS_MINUTES NUMBER(8) DEFAULT 0 NOT NULL,
  NEW_LEARNINGS CLOB,
  WENT_WELL CLOB,
  WENT_WRONG CLOB,
  SUMMARY CLOB,
  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  UPDATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  ROW_VERSION NUMBER DEFAULT 1 NOT NULL,

  CONSTRAINT DAILY_OVERVIEWS_USER_FK FOREIGN KEY (USER_ID) REFERENCES APP_USERS(USER_ID),
  CONSTRAINT DAILY_OVERVIEWS_USER_DATE_UK UNIQUE (USER_ID, OVERVIEW_DATE)
);


-- =========================================================
-- WEEKLY_OVERVIEWS
-- =========================================================

CREATE TABLE WEEKLY_OVERVIEWS (
  WEEKLY_OVERVIEW_ID NUMBER(19) DEFAULT WEEKLY_OVERVIEWS_SEQ.NEXTVAL PRIMARY KEY,
  USER_ID NUMBER(19) NOT NULL,
  WEEK_START_DATE DATE NOT NULL,
  WEEK_END_DATE DATE NOT NULL,
  SOURCE_AI_RUN_ID NUMBER(19),
  TASKS_COMPLETED NUMBER(8) DEFAULT 0 NOT NULL,
  XP_EARNED NUMBER(8) DEFAULT 0 NOT NULL,
  MEETING_MINUTES NUMBER(8) DEFAULT 0 NOT NULL,
  FOCUS_MINUTES NUMBER(8) DEFAULT 0 NOT NULL,
  TOP_ACCOMPLISHMENTS CLOB,
  NEW_LEARNINGS CLOB,
  THEMES CLOB,
  WENT_WELL CLOB,
  WENT_WRONG CLOB,
  SUMMARY CLOB,
  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  UPDATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  ROW_VERSION NUMBER DEFAULT 1 NOT NULL,

  CONSTRAINT WEEKLY_OVERVIEWS_USER_FK FOREIGN KEY (USER_ID) REFERENCES APP_USERS(USER_ID),
  CONSTRAINT WEEKLY_OVERVIEWS_USER_WEEK_UK UNIQUE (USER_ID, WEEK_START_DATE),
  CONSTRAINT WEEKLY_OVERVIEWS_DATE_CK CHECK (WEEK_END_DATE >= WEEK_START_DATE)
);

commit;
