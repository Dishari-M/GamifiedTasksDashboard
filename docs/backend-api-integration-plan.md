# DevQuest Backend API Integration Plan

This file is the implementation contract for replacing the current React-only hardcoded state with production-grade Python APIs, Oracle Autonomous Database persistence, and Oracle Cloud Infrastructure AI services.

## 1. Current Frontend Surfaces To Replace

The frontend currently keeps all domain data in `frontend/src/App.js`.

| Frontend surface | Current hardcoded source | Backend replacement |
| --- | --- | --- |
| Dashboard stats, top missions, task table | `initialTasks`, local React state | `GET /api/v1/dashboard/today` |
| My Tasks add form | Only title and priority are collected | `POST /api/v1/tasks` with all editable task fields |
| Task status advance and done button | Local state mutation | `PATCH /api/v1/tasks/{task_id}/status` and `POST /api/v1/tasks/{task_id}/complete` |
| Quests page | First 5 tasks from local state | `GET /api/v1/quests/today`, sourced from daily work table |
| AI Insights page | Static capacity and standup copy | `GET /api/v1/insights/today`, `POST /api/v1/standup-notes/generate` |
| Calendar and Weekly Overview | Static schedule and weekly stats | `GET /api/v1/calendar/events`, `GET /api/v1/overviews/daily`, `GET /api/v1/overviews/weekly` |
| Sync page | Static source readiness | `POST /api/v1/sync/run`, `GET /api/v1/sync/runs` |
| Leaderboard | Static list | Ignore for now |

## 2. Target Backend Architecture

Use FastAPI with a small layered structure:

```text
backend/
  app/
    main.py
    core/
      config.py
      db.py
      errors.py
      logging.py
      security.py
    api/
      routers/
        dashboard.py
        tasks.py
        daily_work.py
        quests.py
        calendar.py
        insights.py
        standup_notes.py
        overviews.py
        sync.py
        settings.py
    schemas/
      common.py
      tasks.py
      quests.py
      insights.py
      overviews.py
    repositories/
      tasks_repo.py
      daily_work_repo.py
      calendar_repo.py
      ai_repo.py
      overview_repo.py
    services/
      task_service.py
      quest_service.py
      capacity_service.py
      ai_service.py
      standup_service.py
      overview_service.py
      sync_service.py
    integrations/
      oci_genai.py
      oci_agents.py
      jira.py
      outlook.py
      microsoft_todo.py
    migrations/
      001_initial_schema.sql
```

Production defaults:

- Use `python-oracledb` async connection pooling against Oracle Autonomous DB.
- Use bind variables for every SQL statement.
- Wrap insert/update workflows in explicit transactions.
- Use Pydantic request and response models with strict enums.
- Add request IDs, structured logs, and error responses that do not leak SQL, wallet paths, keys, or raw model prompts.
- Add idempotency support for user-triggered write operations.
- Persist AI inputs, outputs, model metadata, and validation state in `AI_RUNS` and related tables so results can be audited and retried.

## 3. Environment Variables

```bash
APP_ENV=dev
API_PREFIX=/api/v1
CORS_ORIGINS=http://localhost:3000

ORACLE_DB_USER=DEVQUEST_APP
ORACLE_DB_PASSWORD=...
ORACLE_DB_DSN=devquest_high
ORACLE_DB_WALLET_DIR=/opt/secrets/wallet
ORACLE_DB_POOL_MIN=2
ORACLE_DB_POOL_MAX=10
ORACLE_DB_POOL_INCREMENT=1
ORACLE_DB_POOL_TIMEOUT_SECONDS=30

OCI_REGION=us-chicago-1
OCI_COMPARTMENT_ID=ocid1.compartment.oc1...
OCI_GENAI_MODEL_ID=cohere.command-r-plus
OCI_GENAI_ENDPOINT=https://inference.generativeai.us-chicago-1.oci.oraclecloud.com
OCI_AGENT_ENDPOINT_ID=ocid1.genaiagentendpoint.oc1...
OCI_AGENT_KNOWLEDGE_BASE_ID=ocid1.genaiagentkb.oc1...
OCI_USE_INSTANCE_PRINCIPAL=true

AI_CACHE_TTL_SECONDS=86400
AI_REQUEST_TIMEOUT_SECONDS=45
```

For local development, config-file authentication is acceptable. In OCI Compute, Functions, or Container Instances, prefer instance principals or workload identity over long-lived API keys.

## 4. Oracle Autonomous DB Schema

Use Oracle DB-generated numeric IDs for persisted entities. Each primary key should be a `NUMBER(19)` populated from an Oracle sequence, either through `DEFAULT <sequence_name>.NEXTVAL` or a `BEFORE INSERT` trigger if your Autonomous DB compatibility settings require it. API payloads expose these IDs as numbers. Store all datetimes as `TIMESTAMP WITH TIME ZONE`.

Recommended sequence setup:

```sql
CREATE SEQUENCE APP_USERS_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE;
CREATE SEQUENCE WORK_ITEMS_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE;
CREATE SEQUENCE WORK_ITEM_EVENTS_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE;
CREATE SEQUENCE DAILY_WORK_ITEMS_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE;
CREATE SEQUENCE CALENDAR_EVENTS_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE;
CREATE SEQUENCE AI_RUNS_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE;
CREATE SEQUENCE QUEST_PLANS_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE;
CREATE SEQUENCE QUEST_ITEMS_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE;
CREATE SEQUENCE STANDUP_NOTES_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE;
CREATE SEQUENCE DAILY_OVERVIEWS_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE;
CREATE SEQUENCE WEEKLY_OVERVIEWS_SEQ START WITH 1 INCREMENT BY 1 CACHE 100 NOCYCLE;
```

For inserts, omit the primary key column and fetch the generated ID with `RETURNING <ID_COLUMN> INTO :generated_id`. Never ask the frontend or API caller to supply internal primary keys. Keep `EXTERNAL_ID` for Jira, Outlook, Microsoft To Do, or SSO identifiers.

### 4.1 Users

```sql
CREATE TABLE APP_USERS (
  USER_ID NUMBER(19) DEFAULT APP_USERS_SEQ.NEXTVAL PRIMARY KEY,
  EXTERNAL_USER_ID VARCHAR2(200),
  DISPLAY_NAME VARCHAR2(200) NOT NULL,
  EMAIL VARCHAR2(320) NOT NULL UNIQUE,
  ROLE_NAME VARCHAR2(80),
  TIMEZONE VARCHAR2(80) DEFAULT 'Asia/Calcutta' NOT NULL,
  WORKDAY_START_LOCAL VARCHAR2(5) DEFAULT '09:00' NOT NULL,
  WORKDAY_END_LOCAL VARCHAR2(5) DEFAULT '17:00' NOT NULL,
  FOCUS_XP_MULTIPLIER NUMBER(5,2) DEFAULT 1.50 NOT NULL,
  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  UPDATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  ROW_VERSION NUMBER DEFAULT 1 NOT NULL
);
```

### 4.2 Work Items

This is the canonical task table for Jira, Microsoft To Do, Outlook-derived work, and custom tasks.

```sql
CREATE TABLE WORK_ITEMS (
  TASK_ID NUMBER(19) DEFAULT WORK_ITEMS_SEQ.NEXTVAL PRIMARY KEY,
  USER_ID NUMBER(19) NOT NULL REFERENCES APP_USERS(USER_ID),
  EXTERNAL_SOURCE VARCHAR2(40) DEFAULT 'CUSTOM' NOT NULL,
  EXTERNAL_ID VARCHAR2(200),
  TITLE VARCHAR2(300) NOT NULL,
  DESCRIPTION CLOB,
  TASK_TYPE VARCHAR2(40) DEFAULT 'Task' NOT NULL,
  PRIORITY VARCHAR2(20) DEFAULT 'Medium' NOT NULL,
  STATUS VARCHAR2(30) DEFAULT 'To Do' NOT NULL,
  PROJECT_KEY VARCHAR2(80),
  DUE_AT TIMESTAMP WITH TIME ZONE,
  START_AT TIMESTAMP WITH TIME ZONE,
  ESTIMATED_MINUTES NUMBER(8),
  ACTUAL_MINUTES NUMBER(8),
  XP_VALUE NUMBER(8),
  NOTES CLOB,
  LABELS_JSON CLOB CHECK (LABELS_JSON IS JSON),
  AI_DIFFICULTY VARCHAR2(20),
  AI_IMPACT_SCORE NUMBER(4,2),
  AI_PRIORITY_SCORE NUMBER(8,4),
  AI_EFFORT_MINUTES NUMBER(8),
  AI_CATEGORY VARCHAR2(60),
  AI_INSIGHT CLOB,
  AI_MODEL_VERSION VARCHAR2(200),
  AI_ENRICHED_AT TIMESTAMP WITH TIME ZONE,
  COMPLETED_AT TIMESTAMP WITH TIME ZONE,
  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  UPDATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  ROW_VERSION NUMBER DEFAULT 1 NOT NULL,
  CONSTRAINT WORK_ITEMS_STATUS_CK CHECK (STATUS IN ('To Do','In Progress','Blocked','Done','Cancelled','Upcoming')),
  CONSTRAINT WORK_ITEMS_PRIORITY_CK CHECK (PRIORITY IN ('Low','Medium','High','Critical')),
  CONSTRAINT WORK_ITEMS_SOURCE_UK UNIQUE (USER_ID, EXTERNAL_SOURCE, EXTERNAL_ID)
);

CREATE INDEX WORK_ITEMS_USER_STATUS_IDX ON WORK_ITEMS(USER_ID, STATUS);
CREATE INDEX WORK_ITEMS_USER_COMPLETED_IDX ON WORK_ITEMS(USER_ID, COMPLETED_AT);
CREATE INDEX WORK_ITEMS_USER_UPDATED_IDX ON WORK_ITEMS(USER_ID, UPDATED_AT);
```

Rules:

- `COMPLETED_AT` is inserted when status becomes `Done`.
- If a completed task is reopened, do not delete historical completion from overviews. Set `STATUS = 'In Progress'`, clear `COMPLETED_AT` only if product wants "current completion date" semantics, and insert an audit event either way.
- `NOTES` is editable and should feed AI insights, standup generation, and daily/weekly overviews.
- Use `EXTERNAL_SOURCE = 'CUSTOM'` and `EXTERNAL_ID = NULL` for user-created tasks. Oracle allows multiple `NULL` values in a unique constraint, so custom tasks need only unique `TASK_ID`.

### 4.3 Work Item Audit Events

```sql
CREATE TABLE WORK_ITEM_EVENTS (
  EVENT_ID NUMBER(19) DEFAULT WORK_ITEM_EVENTS_SEQ.NEXTVAL PRIMARY KEY,
  TASK_ID NUMBER(19) NOT NULL REFERENCES WORK_ITEMS(TASK_ID),
  USER_ID NUMBER(19) NOT NULL REFERENCES APP_USERS(USER_ID),
  EVENT_TYPE VARCHAR2(60) NOT NULL,
  OLD_VALUE_JSON CLOB CHECK (OLD_VALUE_JSON IS JSON),
  NEW_VALUE_JSON CLOB CHECK (NEW_VALUE_JSON IS JSON),
  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL
);

CREATE INDEX WORK_ITEM_EVENTS_TASK_IDX ON WORK_ITEM_EVENTS(TASK_ID, CREATED_AT);
```

Insert an event for every create, update, status change, completion, today marker change, and AI enrichment.

### 4.4 Daily Work Items

This is the source of truth for the Quests page and the "working on this today" task button.

```sql
CREATE TABLE DAILY_WORK_ITEMS (
  DAILY_WORK_ID NUMBER(19) DEFAULT DAILY_WORK_ITEMS_SEQ.NEXTVAL PRIMARY KEY,
  USER_ID NUMBER(19) NOT NULL REFERENCES APP_USERS(USER_ID),
  TASK_ID NUMBER(19) NOT NULL REFERENCES WORK_ITEMS(TASK_ID),
  WORK_DATE DATE NOT NULL,
  IS_WORKING_TODAY NUMBER(1) DEFAULT 1 NOT NULL,
  SELECTED_BY VARCHAR2(40) DEFAULT 'USER' NOT NULL,
  RANK_ORDER NUMBER(5),
  PLANNED_MINUTES NUMBER(8),
  ACTUAL_MINUTES NUMBER(8),
  STARTED_AT TIMESTAMP WITH TIME ZONE,
  STOPPED_AT TIMESTAMP WITH TIME ZONE,
  NOTES CLOB,
  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  UPDATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  ROW_VERSION NUMBER DEFAULT 1 NOT NULL,
  CONSTRAINT DAILY_WORK_ITEMS_UK UNIQUE (USER_ID, TASK_ID, WORK_DATE),
  CONSTRAINT DAILY_WORK_FLAG_CK CHECK (IS_WORKING_TODAY IN (0,1))
);

CREATE INDEX DAILY_WORK_USER_DATE_IDX ON DAILY_WORK_ITEMS(USER_ID, WORK_DATE, IS_WORKING_TODAY);
```

Insert/update behavior:

- When the user turns on "working today", upsert `(USER_ID, TASK_ID, WORK_DATE)`.
- Set `IS_WORKING_TODAY = 1`.
- If task was previously removed from today, reuse the same row and update it.
- When the user turns off "working today", set `IS_WORKING_TODAY = 0`. Do not delete the row.
- The Quests page reads only rows where `IS_WORKING_TODAY = 1`, enriched with task and AI data.

### 4.5 Calendar Events And Meetings

```sql
CREATE TABLE CALENDAR_EVENTS (
  EVENT_ID NUMBER(19) DEFAULT CALENDAR_EVENTS_SEQ.NEXTVAL PRIMARY KEY,
  USER_ID NUMBER(19) NOT NULL REFERENCES APP_USERS(USER_ID),
  EXTERNAL_SOURCE VARCHAR2(40) DEFAULT 'OUTLOOK' NOT NULL,
  EXTERNAL_ID VARCHAR2(200),
  TITLE VARCHAR2(300) NOT NULL,
  DESCRIPTION CLOB,
  START_AT TIMESTAMP WITH TIME ZONE NOT NULL,
  END_AT TIMESTAMP WITH TIME ZONE NOT NULL,
  DURATION_MINUTES NUMBER(8) NOT NULL,
  IS_MEETING NUMBER(1) DEFAULT 1 NOT NULL,
  IS_FOCUS_BLOCK NUMBER(1) DEFAULT 0 NOT NULL,
  ATTENDEE_COUNT NUMBER(6),
  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  UPDATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  ROW_VERSION NUMBER DEFAULT 1 NOT NULL,
  CONSTRAINT CAL_EVENTS_SOURCE_UK UNIQUE (USER_ID, EXTERNAL_SOURCE, EXTERNAL_ID)
);

CREATE INDEX CAL_EVENTS_USER_START_IDX ON CALENDAR_EVENTS(USER_ID, START_AT);
```

Daily and weekly overviews calculate meeting time from this table.

### 4.6 AI Runs

```sql
CREATE TABLE AI_RUNS (
  AI_RUN_ID NUMBER(19) DEFAULT AI_RUNS_SEQ.NEXTVAL PRIMARY KEY,
  USER_ID NUMBER(19) NOT NULL REFERENCES APP_USERS(USER_ID),
  RUN_TYPE VARCHAR2(60) NOT NULL,
  STATUS VARCHAR2(30) DEFAULT 'PENDING' NOT NULL,
  PROVIDER VARCHAR2(40) DEFAULT 'OCI' NOT NULL,
  MODEL_ID VARCHAR2(200),
  AGENT_ENDPOINT_ID VARCHAR2(255),
  REQUEST_JSON CLOB CHECK (REQUEST_JSON IS JSON),
  RESPONSE_JSON CLOB CHECK (RESPONSE_JSON IS JSON),
  ERROR_CODE VARCHAR2(100),
  ERROR_MESSAGE VARCHAR2(1000),
  STARTED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  COMPLETED_AT TIMESTAMP WITH TIME ZONE,
  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  CONSTRAINT AI_RUNS_STATUS_CK CHECK (STATUS IN ('PENDING','RUNNING','SUCCEEDED','FAILED','VALIDATION_FAILED'))
);

CREATE INDEX AI_RUNS_USER_TYPE_IDX ON AI_RUNS(USER_ID, RUN_TYPE, CREATED_AT);
```

### 4.7 Quest Plans

```sql
CREATE TABLE QUEST_PLANS (
  QUEST_PLAN_ID NUMBER(19) DEFAULT QUEST_PLANS_SEQ.NEXTVAL PRIMARY KEY,
  USER_ID NUMBER(19) NOT NULL REFERENCES APP_USERS(USER_ID),
  QUEST_DATE DATE NOT NULL,
  SOURCE_AI_RUN_ID NUMBER(19) REFERENCES AI_RUNS(AI_RUN_ID),
  CAPACITY_MINUTES NUMBER(8) NOT NULL,
  MEETING_MINUTES NUMBER(8) NOT NULL,
  FOCUS_MINUTES NUMBER(8) NOT NULL,
  SUMMARY CLOB,
  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  UPDATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  CONSTRAINT QUEST_PLANS_UK UNIQUE (USER_ID, QUEST_DATE)
);

CREATE TABLE QUEST_ITEMS (
  QUEST_ITEM_ID NUMBER(19) DEFAULT QUEST_ITEMS_SEQ.NEXTVAL PRIMARY KEY,
  QUEST_PLAN_ID NUMBER(19) NOT NULL REFERENCES QUEST_PLANS(QUEST_PLAN_ID),
  TASK_ID NUMBER(19) NOT NULL REFERENCES WORK_ITEMS(TASK_ID),
  RANK_ORDER NUMBER(5) NOT NULL,
  REASON CLOB,
  SUGGESTED_START_AT TIMESTAMP WITH TIME ZONE,
  SUGGESTED_END_AT TIMESTAMP WITH TIME ZONE,
  XP_VALUE NUMBER(8),
  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  CONSTRAINT QUEST_ITEMS_UK UNIQUE (QUEST_PLAN_ID, TASK_ID)
);
```

### 4.8 Generated Notes And Overviews

```sql
CREATE TABLE STANDUP_NOTES (
  STANDUP_NOTE_ID NUMBER(19) DEFAULT STANDUP_NOTES_SEQ.NEXTVAL PRIMARY KEY,
  USER_ID NUMBER(19) NOT NULL REFERENCES APP_USERS(USER_ID),
  NOTE_DATE DATE NOT NULL,
  SOURCE_AI_RUN_ID NUMBER(19) REFERENCES AI_RUNS(AI_RUN_ID),
  ACCOMPLISHED CLOB,
  IN_PROGRESS CLOB,
  BLOCKERS CLOB,
  NEXT_STEPS CLOB,
  FULL_NOTE CLOB NOT NULL,
  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  UPDATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  CONSTRAINT STANDUP_NOTES_UK UNIQUE (USER_ID, NOTE_DATE)
);

CREATE TABLE DAILY_OVERVIEWS (
  DAILY_OVERVIEW_ID NUMBER(19) DEFAULT DAILY_OVERVIEWS_SEQ.NEXTVAL PRIMARY KEY,
  USER_ID NUMBER(19) NOT NULL REFERENCES APP_USERS(USER_ID),
  OVERVIEW_DATE DATE NOT NULL,
  SOURCE_AI_RUN_ID NUMBER(19) REFERENCES AI_RUNS(AI_RUN_ID),
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
  CONSTRAINT DAILY_OVERVIEWS_UK UNIQUE (USER_ID, OVERVIEW_DATE)
);

CREATE TABLE WEEKLY_OVERVIEWS (
  WEEKLY_OVERVIEW_ID NUMBER(19) DEFAULT WEEKLY_OVERVIEWS_SEQ.NEXTVAL PRIMARY KEY,
  USER_ID NUMBER(19) NOT NULL REFERENCES APP_USERS(USER_ID),
  WEEK_START_DATE DATE NOT NULL,
  WEEK_END_DATE DATE NOT NULL,
  SOURCE_AI_RUN_ID NUMBER(19) REFERENCES AI_RUNS(AI_RUN_ID),
  TASKS_COMPLETED NUMBER(8) DEFAULT 0 NOT NULL,
  XP_EARNED NUMBER(8) DEFAULT 0 NOT NULL,
  MEETING_MINUTES NUMBER(8) DEFAULT 0 NOT NULL,
  FOCUS_MINUTES NUMBER(8) DEFAULT 0 NOT NULL,
  NEW_LEARNINGS CLOB,
  THEMES CLOB,
  SUMMARY CLOB,
  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  UPDATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  CONSTRAINT WEEKLY_OVERVIEWS_UK UNIQUE (USER_ID, WEEK_START_DATE)
);
```

## 5. API Conventions

Base path: `/api/v1`

Common headers:

```http
Authorization: Bearer <token>
X-Request-Id: <uuid>  # request tracing token, not a database primary key
Idempotency-Key: <uuid>  # client retry token, not a database primary key
If-Match: <row_version>  # required for optimistic updates where practical
```

Common response envelope:

```json
{
  "data": {},
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

Common error response:

```json
{
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "Task was not found.",
    "details": {
      "task_id": 1001
    }
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

Error mapping:

| Condition | HTTP | Code |
| --- | --- | --- |
| Validation failure | 422 | `VALIDATION_ERROR` |
| Missing task or event | 404 | `TASK_NOT_FOUND`, `EVENT_NOT_FOUND` |
| Optimistic lock mismatch | 409 | `ROW_VERSION_CONFLICT` |
| Duplicate external source row | 409 | `DUPLICATE_EXTERNAL_ITEM` |
| OCI model unavailable or timeout | 503 | `AI_PROVIDER_UNAVAILABLE` |
| AI response is invalid JSON or fails schema validation | 502 | `AI_RESPONSE_INVALID` |
| Oracle DB unavailable | 503 | `DATABASE_UNAVAILABLE` |

## 6. Shared API Models

### 6.1 Task Response

```json
{
  "task_id": 1001,
  "external_source": "Jira",
  "external_id": "PAY-2301",
  "title": "Fix payment gateway timeout issue",
  "description": "Users face timeout while making payments on the checkout page.",
  "task_type": "Bug",
  "priority": "High",
  "status": "In Progress",
  "project_key": "PAY",
  "due_at": "2026-04-30T18:00:00+05:30",
  "start_at": null,
  "estimated_minutes": 120,
  "actual_minutes": 45,
  "xp_value": 120,
  "notes": "Root cause may be retry policy plus gateway timeout mismatch.",
  "labels": ["backend", "payments"],
  "working_today": true,
  "completed_at": null,
  "ai": {
    "difficulty": "Hard",
    "impact_score": 9.0,
    "priority_score": 0.92,
    "effort_minutes": 120,
    "category": "Bug",
    "insight": "Handle before lunch because it is customer-facing and blocks checkout.",
    "enriched_at": "2026-04-30T09:15:00+05:30"
  },
  "created_at": "2026-04-30T09:00:00+05:30",
  "updated_at": "2026-04-30T09:20:00+05:30",
  "row_version": 4
}
```

### 6.2 Task Insert Fields

The add-task UI must collect all fields, not only priority.

Required:

- `title`
- `task_type`
- `priority`

Optional:

- `description`
- `external_source`
- `external_id`
- `project_key`
- `due_at`
- `start_at`
- `estimated_minutes`
- `actual_minutes`
- `xp_value`
- `status`
- `notes`
- `labels`
- `working_today`
- `run_ai_enrichment`

## 7. Task APIs

### 7.1 List Tasks

`GET /api/v1/tasks`

Query parameters:

| Name | Type | Notes |
| --- | --- | --- |
| `status` | string | Optional repeated enum |
| `source` | string | `Jira`, `Outlook`, `Microsoft To Do`, `CUSTOM` |
| `priority` | string | `Low`, `Medium`, `High`, `Critical` |
| `working_today` | boolean | Joins to `DAILY_WORK_ITEMS` |
| `completed_from` | datetime | Filter by `COMPLETED_AT` |
| `completed_to` | datetime | Filter by `COMPLETED_AT` |
| `q` | string | Search title, description, notes |
| `limit` | int | Default 50, max 200 |
| `cursor` | string | Opaque pagination cursor |

Response:

```json
{
  "data": [
    {
      "task_id": 1001,
      "title": "Fix payment gateway timeout issue",
      "external_source": "Jira",
      "external_id": "PAY-2301",
      "priority": "High",
      "status": "In Progress",
      "task_type": "Bug",
      "estimated_minutes": 120,
      "xp_value": 120,
      "notes": "Root cause notes...",
      "working_today": true,
      "completed_at": null,
      "ai": {
        "difficulty": "Hard",
        "impact_score": 9,
        "priority_score": 0.92,
        "effort_minutes": 120,
        "insight": "High impact checkout blocker."
      },
      "row_version": 4
    }
  ],
  "meta": {
    "next_cursor": null,
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

Implementation steps:

1. Authenticate user and resolve `user_id`.
2. Build a parameterized SQL query with optional filters.
3. Join `DAILY_WORK_ITEMS` on current local date if `working_today` is requested.
4. Return paginated rows, mapping CLOB values to strings and JSON columns to arrays.

### 7.2 Create Task

`POST /api/v1/tasks`

Request:

```json
{
  "external_source": "CUSTOM",
  "external_id": null,
  "title": "Investigate CI failure in payment service",
  "description": "Pipeline has failed twice on integration tests.",
  "task_type": "Bug",
  "priority": "High",
  "status": "To Do",
  "project_key": "PAY",
  "due_at": "2026-04-30T18:00:00+05:30",
  "start_at": null,
  "estimated_minutes": 90,
  "actual_minutes": 0,
  "xp_value": null,
  "notes": "Check flaky gateway mock and retry config.",
  "labels": ["ci", "payments"],
  "working_today": true,
  "run_ai_enrichment": true
}
```

Response: `201 Created`

```json
{
  "data": {
    "task": {
      "task_id": 1002,
      "title": "Investigate CI failure in payment service",
      "external_source": "CUSTOM",
      "external_id": null,
      "priority": "High",
      "status": "To Do",
      "task_type": "Bug",
      "estimated_minutes": 90,
      "xp_value": 110,
      "notes": "Check flaky gateway mock and retry config.",
      "working_today": true,
      "completed_at": null,
      "ai": {
        "difficulty": "Medium",
        "impact_score": 8,
        "priority_score": 0.86,
        "effort_minutes": 90,
        "insight": "Fixing CI restores deployment confidence for payment changes."
      },
      "row_version": 1
    }
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

Insert implementation:

1. Validate title length, enum fields, and positive minute values.
2. Insert into `WORK_ITEMS` without supplying `TASK_ID`; let `WORK_ITEMS_SEQ.NEXTVAL` populate the primary key.
3. Fetch the generated `TASK_ID` with `RETURNING TASK_ID INTO :task_id`.
4. If `run_ai_enrichment = true`, call task enrichment before insert or insert first with `PENDING` AI state and enrich after commit. Prefer insert-first for lower perceived latency.
5. Insert `WORK_ITEM_EVENTS` with `EVENT_TYPE = 'TASK_CREATED'`, letting `WORK_ITEM_EVENTS_SEQ.NEXTVAL` generate `EVENT_ID`.
6. If `working_today = true`, upsert into `DAILY_WORK_ITEMS`; let `DAILY_WORK_ITEMS_SEQ.NEXTVAL` generate `DAILY_WORK_ID` for a new row.
7. If AI was run synchronously, update AI columns and insert `AI_RUNS`; let `AI_RUNS_SEQ.NEXTVAL` generate `AI_RUN_ID`.
8. Commit. On any failure, roll back.
9. Return the task including `working_today`.

Production note: Use a background job for AI enrichment if request latency exceeds 1 to 2 seconds. Return `ai.status = "pending"` and expose `GET /api/v1/ai-runs/{ai_run_id}`.

### 7.3 Get Task

`GET /api/v1/tasks/{task_id}`

Response:

```json
{
  "data": {
    "task_id": 1002,
    "title": "Investigate CI failure in payment service",
    "description": "Pipeline has failed twice on integration tests.",
    "task_type": "Bug",
    "priority": "High",
    "status": "To Do",
    "notes": "Check flaky gateway mock and retry config.",
    "working_today": true,
    "events": [
      {
        "event_type": "TASK_CREATED",
        "created_at": "2026-04-30T09:03:00+05:30"
      }
    ],
    "row_version": 1
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

### 7.4 Update Task

`PATCH /api/v1/tasks/{task_id}`

Request:

```json
{
  "title": "Investigate CI failure in payment service",
  "description": "Integration tests fail after retry policy change.",
  "task_type": "Bug",
  "priority": "Critical",
  "status": "In Progress",
  "project_key": "PAY",
  "due_at": "2026-04-30T17:00:00+05:30",
  "estimated_minutes": 120,
  "actual_minutes": 30,
  "xp_value": 140,
  "notes": "The failure reproduces only with the gateway sandbox enabled.",
  "labels": ["ci", "payments", "release-blocker"],
  "row_version": 1,
  "run_ai_enrichment": true
}
```

Response:

```json
{
  "data": {
    "task_id": 1002,
    "priority": "Critical",
    "status": "In Progress",
    "estimated_minutes": 120,
    "actual_minutes": 30,
    "xp_value": 140,
    "notes": "The failure reproduces only with the gateway sandbox enabled.",
    "ai": {
      "difficulty": "Hard",
      "impact_score": 9.5,
      "priority_score": 0.96,
      "effort_minutes": 120,
      "insight": "Release-blocking CI failures should be handled before feature work."
    },
    "row_version": 2
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

Update implementation:

1. Require `row_version` or `If-Match`.
2. Read the existing task `FOR UPDATE`.
3. Validate the user owns the task.
4. Apply only provided fields.
5. If status transitions to `Done`, set `COMPLETED_AT = SYSTIMESTAMP` unless caller supplied a valid completion time.
6. If status transitions away from `Done`, keep an audit event. Decide product semantics before clearing `COMPLETED_AT`.
7. Increment `ROW_VERSION`.
8. Insert `WORK_ITEM_EVENTS` with old and new values.
9. If AI enrichment requested, call enrichment and update AI columns in the same transaction or queue a background AI run.
10. Commit and return the updated row.

### 7.5 Update Task Notes

`PUT /api/v1/tasks/{task_id}/notes`

Request:

```json
{
  "notes": "Learned that timeout retries multiply under gateway sandbox load. Need a circuit breaker test.",
  "row_version": 2,
  "run_ai_enrichment": true
}
```

Response:

```json
{
  "data": {
    "task_id": 1002,
    "notes": "Learned that timeout retries multiply under gateway sandbox load. Need a circuit breaker test.",
    "ai": {
      "insight": "Notes indicate a system-resilience learning and a follow-up test."
    },
    "row_version": 3
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

Insert/update behavior:

- Update `WORK_ITEMS.NOTES`.
- Insert `WORK_ITEM_EVENTS` with `EVENT_TYPE = 'NOTES_UPDATED'`.
- Include notes in subsequent AI prompts for task enrichment, standup notes, and overviews.

### 7.6 Change Task Status

`PATCH /api/v1/tasks/{task_id}/status`

Request:

```json
{
  "status": "In Progress",
  "actual_minutes": 30,
  "notes_append": "Started debugging the gateway retry path.",
  "row_version": 3
}
```

Response:

```json
{
  "data": {
    "task_id": 1002,
    "status": "In Progress",
    "completed_at": null,
    "actual_minutes": 30,
    "row_version": 4
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

Update implementation:

1. Lock row by `TASK_ID` and `USER_ID`.
2. Validate transition. For example, allow `To Do -> In Progress -> Done`, `Blocked -> In Progress`, and `In Progress -> Blocked`.
3. Update `STATUS`, `ACTUAL_MINUTES`, `NOTES`, `UPDATED_AT`, and `ROW_VERSION`.
4. If new status is `Done`, set `COMPLETED_AT`.
5. Insert audit event.
6. Commit.

### 7.7 Complete Task

`POST /api/v1/tasks/{task_id}/complete`

Request:

```json
{
  "completed_at": "2026-04-30T16:42:00+05:30",
  "actual_minutes": 115,
  "notes_append": "Fixed retry timeout and added regression coverage.",
  "learnings": "Gateway sandbox has lower timeout thresholds than production.",
  "went_well": "Existing integration tests caught the issue.",
  "went_wrong": "Retry policy lacked a cap.",
  "row_version": 4
}
```

Response:

```json
{
  "data": {
    "task_id": 1002,
    "status": "Done",
    "completed_at": "2026-04-30T16:42:00+05:30",
    "actual_minutes": 115,
    "xp_awarded": 140,
    "daily_overview_dirty": true,
    "standup_note_dirty": true,
    "row_version": 5
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

Insert/update behavior:

1. Lock task row.
2. Set `STATUS = 'Done'`.
3. Set `COMPLETED_AT = request.completed_at OR SYSTIMESTAMP`.
4. Update `ACTUAL_MINUTES`.
5. Append `notes_append`, `learnings`, `went_well`, and `went_wrong` to `NOTES` using clear headings.
6. If task has no `XP_VALUE`, compute it from AI difficulty, effort, and impact.
7. Insert `WORK_ITEM_EVENTS` with `EVENT_TYPE = 'TASK_COMPLETED'`.
8. Mark today's daily and weekly overview as dirty by either deleting cached generated rows or adding a dirty flag column if desired.
9. Commit.

## 8. Working Today And Daily Work APIs

### 8.1 Mark Task As Working Today

`PUT /api/v1/tasks/{task_id}/today`

Request:

```json
{
  "work_date": "2026-04-30",
  "is_working_today": true,
  "planned_minutes": 120,
  "rank_order": 1,
  "notes": "Primary quest for today."
}
```

Response:

```json
{
  "data": {
    "daily_work_id": 5001,
    "task_id": 1002,
    "work_date": "2026-04-30",
    "is_working_today": true,
    "planned_minutes": 120,
    "rank_order": 1,
    "notes": "Primary quest for today.",
    "row_version": 1
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

Upsert implementation:

1. Validate task exists and belongs to user.
2. Compute local `WORK_DATE` if omitted.
3. Try update existing `(USER_ID, TASK_ID, WORK_DATE)`.
4. If no row exists, insert a new `DAILY_WORK_ITEMS` row.
5. Set `IS_WORKING_TODAY`, `PLANNED_MINUTES`, `RANK_ORDER`, and `NOTES`.
6. Insert `WORK_ITEM_EVENTS` with `EVENT_TYPE = 'WORKING_TODAY_UPDATED'`.
7. Commit.

### 8.2 Get Today's Work Items

`GET /api/v1/daily-work?date=2026-04-30`

Response:

```json
{
  "data": {
    "work_date": "2026-04-30",
    "items": [
      {
        "daily_work_id": 5001,
        "rank_order": 1,
        "planned_minutes": 120,
        "actual_minutes": 115,
        "task": {
          "task_id": 1002,
          "title": "Investigate CI failure in payment service",
          "priority": "Critical",
          "status": "Done",
          "completed_at": "2026-04-30T16:42:00+05:30",
          "xp_value": 140,
          "notes": "Fixed retry timeout and added regression coverage."
        }
      }
    ]
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

## 9. Dashboard APIs

### 9.1 Today's Dashboard

`GET /api/v1/dashboard/today?date=2026-04-30`

Response:

```json
{
  "data": {
    "date": "2026-04-30",
    "stats": {
      "total_xp": 2590,
      "tasks_completed_today": 3,
      "tasks_planned_today": 7,
      "focus_minutes": 155,
      "meeting_minutes": 190,
      "available_focus_minutes": 165
    },
    "top_missions": [
      {
        "task_id": 1002,
        "title": "Investigate CI failure in payment service",
        "priority": "Critical",
        "rank_order": 1,
        "estimated_minutes": 120,
        "xp_value": 140,
        "ai_reason": "Release-blocking issue with high impact."
      }
    ],
    "tasks": [],
    "schedule": [],
    "ai_insight": {
      "text": "You have 165 focus minutes after meetings. Finish the payment CI blocker first, then use the remaining block for documentation.",
      "capacity_minutes": 165,
      "impact_score": 8.7,
      "generated_at": "2026-04-30T09:20:00+05:30"
    }
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

Implementation:

1. Read tasks, daily work rows, calendar events, and latest AI insight for the date.
2. Compute stats in SQL where possible.
3. Use cached insight if fresh. Otherwise call `POST /api/v1/insights/today/generate` asynchronously.
4. Return all data needed by the dashboard in one request to avoid frontend waterfalls.

## 10. Quest APIs

### 10.1 Get Today's Quests

`GET /api/v1/quests/today?date=2026-04-30`

The Quests page must use `DAILY_WORK_ITEMS` as source of truth.

Response:

```json
{
  "data": {
    "quest_date": "2026-04-30",
    "source": "DAILY_WORK_ITEMS",
    "capacity": {
      "workday_minutes": 480,
      "meeting_minutes": 190,
      "available_focus_minutes": 165
    },
    "quests": [
      {
        "rank_order": 1,
        "task_id": 1002,
        "title": "Investigate CI failure in payment service",
        "description": "Integration tests fail after retry policy change.",
        "priority": "Critical",
        "task_type": "Bug",
        "status": "In Progress",
        "estimated_minutes": 120,
        "xp_value": 140,
        "ai": {
          "difficulty": "Hard",
          "impact_score": 9.5,
          "reason": "Release-blocking and customer-facing."
        }
      }
    ],
    "summary": "Focus on the CI blocker first, then complete the documentation task if time remains."
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

### 10.2 Generate Or Regenerate Quests

`POST /api/v1/quests/generate`

Request:

```json
{
  "quest_date": "2026-04-30",
  "candidate_task_ids": [
    1002,
    1001
  ],
  "max_quests": 5,
  "respect_working_today": true,
  "include_ai_reasoning": true
}
```

Response:

```json
{
  "data": {
    "quest_plan_id": 7001,
    "quest_date": "2026-04-30",
    "quests": [
      {
        "rank_order": 1,
        "task_id": 1002,
        "reason": "Highest urgency and fits the available focus block.",
        "suggested_start_at": "2026-04-30T13:00:00+05:30",
        "suggested_end_at": "2026-04-30T15:00:00+05:30",
        "xp_value": 140
      }
    ],
    "ai_run_id": 9001
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

Insert/update behavior:

1. Read candidate tasks. If `respect_working_today = true`, candidates come from `DAILY_WORK_ITEMS`.
2. Compute capacity from settings and calendar events.
3. Call OCI GenAI with a strict JSON schema for ranked quests.
4. Validate every returned `task_id` exists in candidate set.
5. Upsert `QUEST_PLANS` for `(USER_ID, QUEST_DATE)`.
6. Delete and reinsert `QUEST_ITEMS` for that plan, or update rank rows in place. Prefer delete/reinsert inside one transaction for simplicity.
7. Upsert `DAILY_WORK_ITEMS` so generated quests remain visible on the Quests page.
8. Commit.

OCI AI steps:

1. Build compact input containing task title, priority, status, due date, estimated minutes, notes, AI scores, and available focus windows.
2. Use OCI Generative AI Inference for deterministic JSON ranking.
3. Temperature: `0.1` to `0.3`.
4. Validate output against `QuestPlanSchema`.
5. Store prompt and response in `AI_RUNS`.

## 11. Calendar And Capacity APIs

### 11.1 List Calendar Events

`GET /api/v1/calendar/events?from=2026-04-30T00:00:00+05:30&to=2026-04-30T23:59:59+05:30`

Response:

```json
{
  "data": [
    {
      "event_id": 4001,
      "title": "Daily Standup",
      "start_at": "2026-04-30T09:00:00+05:30",
      "end_at": "2026-04-30T09:30:00+05:30",
      "duration_minutes": 30,
      "is_meeting": true,
      "is_focus_block": false,
      "external_source": "Outlook"
    }
  ],
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

### 11.2 Get Capacity

`GET /api/v1/capacity?date=2026-04-30`

Response:

```json
{
  "data": {
    "date": "2026-04-30",
    "workday_minutes": 480,
    "meeting_minutes": 190,
    "focus_block_minutes": 165,
    "available_focus_minutes": 165,
    "suggested_focus_windows": [
      {
        "start_at": "2026-04-30T13:00:00+05:30",
        "end_at": "2026-04-30T15:45:00+05:30",
        "duration_minutes": 165
      }
    ]
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

Implementation:

1. Read user's workday settings and timezone.
2. Read calendar events for the local date.
3. Sum events where `IS_MEETING = 1`.
4. Compute free windows between workday start and end after subtracting meetings.
5. Return deterministic numbers. AI should explain capacity, not calculate basic arithmetic.

## 12. AI Task Insight APIs

### 12.1 Enrich One Task

`POST /api/v1/tasks/{task_id}/ai/enrich`

Request:

```json
{
  "force": false,
  "include_notes": true,
  "objectives": [
    "priority",
    "xp",
    "effort",
    "insight"
  ]
}
```

Response:

```json
{
  "data": {
    "task_id": 1002,
    "ai_run_id": 9002,
    "ai": {
      "difficulty": "Hard",
      "impact_score": 9.5,
      "priority_score": 0.96,
      "effort_minutes": 120,
      "category": "Bug",
      "xp_value": 140,
      "insight": "Release-blocking CI failures should be handled before feature work.",
      "suggested_next_action": "Reproduce with gateway sandbox enabled and cap retries."
    }
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

Update implementation:

1. Fetch task and notes.
2. If `force = false` and `AI_ENRICHED_AT` is recent, return cached values.
3. Insert `AI_RUNS` with `RUNNING`.
4. Call OCI GenAI with JSON response schema.
5. Validate:
   - `difficulty` in `Easy | Medium | Hard`
   - `impact_score` between 1 and 10
   - `priority_score` between 0 and 1
   - `effort_minutes` positive integer
   - `xp_value` positive integer
6. Update `WORK_ITEMS` AI columns and `XP_VALUE`.
7. Insert `WORK_ITEM_EVENTS` with `EVENT_TYPE = 'AI_ENRICHED'`.
8. Mark `AI_RUNS` as `SUCCEEDED`.
9. Commit.

OCI GenAI prompt contract:

```json
{
  "system": "You are an engineering productivity analyst. Return only valid JSON matching the provided schema. Do not invent external facts.",
  "input": {
    "task": {
      "title": "Investigate CI failure in payment service",
      "description": "Integration tests fail after retry policy change.",
      "priority": "Critical",
      "status": "In Progress",
      "task_type": "Bug",
      "notes": "Failure reproduces only with gateway sandbox enabled.",
      "due_at": "2026-04-30T17:00:00+05:30"
    },
    "schema": {
      "difficulty": "Easy|Medium|Hard",
      "impact_score": "number 1-10",
      "priority_score": "number 0-1",
      "effort_minutes": "integer",
      "category": "Bug|Feature|Research|Deployment|Review|Meeting|Documentation|Other",
      "xp_value": "integer",
      "insight": "string",
      "suggested_next_action": "string"
    }
  }
}
```

### 12.2 Bulk Enrich Tasks

`POST /api/v1/tasks/ai/enrich`

Request:

```json
{
  "task_ids": [
    1002
  ],
  "only_missing": true,
  "include_notes": true
}
```

Response:

```json
{
  "data": {
    "submitted": 1,
    "completed": 1,
    "failed": 0,
    "results": [
      {
        "task_id": 1002,
        "ai_run_id": 9002,
        "status": "SUCCEEDED"
      }
    ]
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

Implementation:

- Process in bounded batches, for example 5 to 10 tasks per model call or background worker batch.
- Use per-task validation and partial success.
- Never let one invalid model output roll back unrelated successful enrichments.

## 13. Insights APIs

### 13.1 Get Today's Insights

`GET /api/v1/insights/today?date=2026-04-30`

Response:

```json
{
  "data": {
    "date": "2026-04-30",
    "capacity": {
      "working_hours": "8h",
      "meeting_minutes": 190,
      "available_focus_minutes": 165
    },
    "task_insights": [
      {
        "task_id": 1002,
        "title": "Investigate CI failure in payment service",
        "priority_score": 0.96,
        "effort_minutes": 120,
        "xp_value": 140,
        "insight": "Release-blocking CI failure should be handled before feature work."
      }
    ],
    "daily_insight": "You have enough focus time for one hard task and one small follow-up.",
    "standup_summary": "Yesterday/today summary based on completed tasks is available."
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

### 13.2 Generate Today's Insights

`POST /api/v1/insights/today/generate`

Request:

```json
{
  "date": "2026-04-30",
  "include_tasks": true,
  "include_calendar": true,
  "include_notes": true,
  "force": false
}
```

Response:

```json
{
  "data": {
    "ai_run_id": 9003,
    "daily_insight": "You have 165 focus minutes after meetings. Complete the CI blocker first.",
    "risks": [
      "Critical task effort may exceed remaining focus time."
    ],
    "recommendations": [
      "Split the CI failure into reproduce, fix, and regression-test steps."
    ]
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

OCI AI steps:

1. Build context from daily work, task notes, completed tasks, and meeting schedule.
2. Use direct OCI GenAI for structured recommendations.
3. Use OCI Agent only if the insight needs database-grounded question answering over historical data, for example "compare with last three Fridays".
4. Store results in `AI_RUNS`.

## 14. Standup Note APIs

### 14.1 Generate Standup Note

`POST /api/v1/standup-notes/generate`

Request:

```json
{
  "date": "2026-04-30",
  "include_completed_today": true,
  "include_in_progress": true,
  "include_blockers": true,
  "include_notes": true,
  "tone": "concise",
  "force": false
}
```

Response:

```json
{
  "data": {
    "standup_note_id": 8001,
    "date": "2026-04-30",
    "accomplished": [
      "Fixed retry timeout in the payment gateway integration and added regression coverage."
    ],
    "in_progress": [
      "Continuing cleanup on order tracking API implementation."
    ],
    "blockers": [
      "Need confirmation on gateway sandbox timeout limits."
    ],
    "next_steps": [
      "Merge payment fix after CI passes.",
      "Complete order status endpoint contract."
    ],
    "full_note": "Completed payment gateway timeout fix and regression coverage. Continuing order tracking API work. Blocked on confirming sandbox timeout limits.",
    "ai_run_id": 9004
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

Data source:

- Completed tasks where `TRUNC(COMPLETED_AT AT LOCAL TIME ZONE) = date`
- In-progress tasks from `DAILY_WORK_ITEMS`
- Blocked tasks where `STATUS = 'Blocked'`
- Task `NOTES`, including learnings, what went right, and what went wrong
- Optional calendar events to mention meeting load only if useful

Insert/update behavior:

1. Read completed and in-progress tasks for the date.
2. Insert `AI_RUNS` as `RUNNING`.
3. Call OCI GenAI with the standup schema.
4. Validate arrays and `full_note`.
5. Upsert `STANDUP_NOTES` by `(USER_ID, NOTE_DATE)`.
6. Mark `AI_RUNS` as `SUCCEEDED`.
7. Commit.

OCI Agent option:

Use an OCI Agent with a SQL tool or function tool when the standup generator needs historical context, such as "include themes from the last week" or "find recurring blockers". Keep the normal daily standup path direct through GenAI for predictable JSON and lower latency.

### 14.2 Get Standup Note

`GET /api/v1/standup-notes?date=2026-04-30`

Response:

```json
{
  "data": {
    "standup_note_id": 8001,
    "date": "2026-04-30",
    "full_note": "Completed payment gateway timeout fix and regression coverage...",
    "updated_at": "2026-04-30T17:30:00+05:30"
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

## 15. Daily And Weekly Overview APIs

Add a new frontend page for Daily and Weekly Overview. This page should show accomplished tasks, meeting time, learnings, went well, went wrong, XP, and generated summaries.

### 15.1 Get Daily Overview

`GET /api/v1/overviews/daily?date=2026-04-30`

Response:

```json
{
  "data": {
    "date": "2026-04-30",
    "tasks_completed": 3,
    "xp_earned": 310,
    "meeting_minutes": 190,
    "focus_minutes": 155,
    "accomplished_tasks": [
      {
        "task_id": 1002,
        "title": "Investigate CI failure in payment service",
        "completed_at": "2026-04-30T16:42:00+05:30",
        "actual_minutes": 115,
        "xp_value": 140,
        "notes": "Fixed retry timeout and added regression coverage."
      }
    ],
    "meeting_summary": {
      "meeting_count": 3,
      "meeting_minutes": 190
    },
    "new_learnings": [
      "Gateway sandbox timeout thresholds differ from production."
    ],
    "went_well": [
      "Regression tests caught the timeout path."
    ],
    "went_wrong": [
      "Retry policy lacked a cap."
    ],
    "summary": "A high-impact backend day: payment reliability improved, with a clear follow-up around sandbox configuration."
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

### 15.2 Generate Daily Overview

`POST /api/v1/overviews/daily/generate`

Request:

```json
{
  "date": "2026-04-30",
  "include_task_notes": true,
  "include_meetings": true,
  "force": false
}
```

Response:

```json
{
  "data": {
    "daily_overview_id": 8101,
    "date": "2026-04-30",
    "summary": "A high-impact backend day focused on payment reliability.",
    "new_learnings": [
      "Gateway sandbox timeout thresholds differ from production."
    ],
    "went_well": [
      "Regression tests caught the timeout path."
    ],
    "went_wrong": [
      "Retry policy lacked a cap."
    ],
    "ai_run_id": 9005
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

Insert/update behavior:

1. Query completed tasks, task notes, daily work rows, and calendar events.
2. Calculate metrics in backend code or SQL.
3. Ask OCI GenAI to summarize learnings and themes. Do not ask AI to calculate totals.
4. Upsert `DAILY_OVERVIEWS`.
5. Commit.

### 15.3 Get Weekly Overview

`GET /api/v1/overviews/weekly?week_start=2026-04-27`

Response:

```json
{
  "data": {
    "week_start": "2026-04-27",
    "week_end": "2026-05-03",
    "tasks_completed": 18,
    "xp_earned": 1440,
    "meeting_minutes": 780,
    "focus_minutes": 920,
    "top_accomplishments": [
      "Stabilized payment gateway timeout behavior.",
      "Implemented order tracking API contract."
    ],
    "new_learnings": [
      "Timeout behavior varies between sandbox and production integrations."
    ],
    "themes": [
      "Reliability",
      "API delivery",
      "Release readiness"
    ],
    "summary": "The week leaned heavily toward backend reliability and API delivery, with meeting load still high."
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

### 15.4 Generate Weekly Overview

`POST /api/v1/overviews/weekly/generate`

Request:

```json
{
  "week_start": "2026-04-27",
  "include_daily_overviews": true,
  "include_task_notes": true,
  "force": false
}
```

Response:

```json
{
  "data": {
    "weekly_overview_id": 8201,
    "week_start": "2026-04-27",
    "week_end": "2026-05-03",
    "summary": "The week leaned heavily toward backend reliability and API delivery.",
    "ai_run_id": 9006
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

OCI AI steps:

1. Gather daily overviews if present.
2. If missing, gather raw completed tasks and notes for the week.
3. Calculate totals without AI.
4. Call OCI GenAI for themes, learnings, and narrative summary.
5. If using OCI Agent, restrict it to read-only SQL views over weekly productivity data.

## 16. Sync APIs

External integration can be implemented after the internal task model is stable. Keep the API contract now so the Sync page can be wired.

### 16.1 Run Sync

`POST /api/v1/sync/run`

Request:

```json
{
  "sources": ["Jira", "Outlook Calendar", "Microsoft To Do"],
  "from": "2026-04-30T00:00:00+05:30",
  "to": "2026-05-07T23:59:59+05:30",
  "run_ai_enrichment": true
}
```

Response:

```json
{
  "data": {
    "sync_run_id": 8301,
    "status": "RUNNING",
    "sources": [
      {
        "source": "Jira",
        "status": "QUEUED"
      },
      {
        "source": "Outlook Calendar",
        "status": "QUEUED"
      }
    ]
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

Implementation:

- Create a `SYNC_RUNS` and `SYNC_RUN_ITEMS` table if sync status must be persisted.
- Upsert external tasks into `WORK_ITEMS` by `(USER_ID, EXTERNAL_SOURCE, EXTERNAL_ID)`.
- Upsert calendar events into `CALENDAR_EVENTS`.
- Do not overwrite user-edited fields blindly. Keep external raw payloads in an optional CLOB column or separate `EXTERNAL_OBJECTS` table.

## 17. Settings APIs

`GET /api/v1/settings/productivity`

Response:

```json
{
  "data": {
    "timezone": "Asia/Calcutta",
    "workday_start_local": "09:00",
    "workday_end_local": "17:00",
    "focus_xp_multiplier": 1.5
  },
  "meta": {
    "request_id": "2f7bd7e7-8928-41c0-88c4-d8f1d4df0f6f"
  }
}
```

`PATCH /api/v1/settings/productivity`

Request:

```json
{
  "timezone": "Asia/Calcutta",
  "workday_start_local": "09:30",
  "workday_end_local": "18:00",
  "focus_xp_multiplier": 1.25,
  "row_version": 1
}
```

Update behavior:

1. Validate timezone and time strings.
2. Update `APP_USERS`.
3. Increment `ROW_VERSION`.
4. Capacity endpoints should reflect new values immediately.

## 18. Oracle OCI GenAI And Agent Integration

### 18.1 Use Direct OCI GenAI For Structured Work

Use direct OCI Generative AI Inference for:

- Task enrichment: difficulty, priority score, effort, XP, insight
- Quest ranking
- Daily insight copy
- Standup note generation
- Daily and weekly overview summaries

Use a JSON schema response where supported by the selected model and SDK. Always validate with Pydantic after the model responds.

Python service shape:

```python
class OciGenAiService:
    def __init__(self, client, compartment_id: str, model_id: str):
        self.client = client
        self.compartment_id = compartment_id
        self.model_id = model_id

    async def enrich_task(self, task: TaskAiInput) -> TaskAiOutput:
        # Insert AI_RUNS before this call in the service layer.
        # Use asyncio.to_thread if the OCI SDK call is synchronous.
        # Validate the parsed model output with Pydantic before returning.
        ...
```

Implementation notes:

- Configure OCI client timeout lower than the API gateway timeout.
- Use request IDs as `opc_request_id`.
- Retry transient failures with bounded exponential backoff.
- Do not retry validation failures.
- Store raw model response in `AI_RUNS.RESPONSE_JSON`.
- Keep prompts compact. Send only fields needed for the decision.
- Never send secrets, auth tokens, full external payloads, or unrelated personal data.

### 18.2 Use OCI Agents For Grounded Or Historical Questions

Use OCI Generative AI Agents when an answer needs governed access to a knowledge base, SQL data, or tool calls, for example:

- "What blockers keep recurring this week?"
- "Compare today's accomplishments with the last three weeks."
- "Which task categories are consuming the most meeting-heavy days?"
- "Generate a weekly manager summary from historical task and meeting data."

Recommended setup:

1. Create read-only DB views for agent access:

```sql
CREATE OR REPLACE VIEW V_AGENT_TASK_SUMMARY AS
SELECT
  USER_ID,
  TASK_ID,
  TITLE,
  TASK_TYPE,
  PRIORITY,
  STATUS,
  ESTIMATED_MINUTES,
  ACTUAL_MINUTES,
  XP_VALUE,
  AI_DIFFICULTY,
  AI_IMPACT_SCORE,
  COMPLETED_AT,
  CREATED_AT,
  UPDATED_AT
FROM WORK_ITEMS;

CREATE OR REPLACE VIEW V_AGENT_DAILY_SUMMARY AS
SELECT
  d.USER_ID,
  d.WORK_DATE,
  COUNT(CASE WHEN w.STATUS = 'Done' THEN 1 END) AS TASKS_DONE,
  SUM(NVL(w.XP_VALUE, 0)) AS XP_TOTAL,
  SUM(NVL(d.ACTUAL_MINUTES, 0)) AS ACTUAL_TASK_MINUTES
FROM DAILY_WORK_ITEMS d
JOIN WORK_ITEMS w ON w.TASK_ID = d.TASK_ID
GROUP BY d.USER_ID, d.WORK_DATE;
```

2. Grant the agent DB user read-only access to views, not base tables.
3. Configure the OCI Agent endpoint with a SQL tool or function tool.
4. In backend, create an agent session per user workflow when needed.
5. Call the agent runtime `chat` method with a concise question and context.
6. Store citations, traces, and SQL tool outputs if returned.
7. Validate that returned task IDs or dates exist before showing or persisting recommendations.

Python runtime shape:

```python
class OciAgentService:
    def __init__(self, runtime_client, agent_endpoint_id: str):
        self.runtime_client = runtime_client
        self.agent_endpoint_id = agent_endpoint_id

    async def ask_historical_insight(self, user_id: str, question: str) -> AgentInsight:
        # Create or reuse a short-lived session.
        # Call chat(agent_endpoint_id, chat_details, opc_request_id=...).
        # Validate and normalize the response.
        ...
```

### 18.3 AI Output Schemas

Task enrichment output:

```json
{
  "difficulty": "Hard",
  "impact_score": 9.5,
  "priority_score": 0.96,
  "effort_minutes": 120,
  "category": "Bug",
  "xp_value": 140,
  "insight": "Release-blocking CI failures should be handled before feature work.",
  "suggested_next_action": "Reproduce the failure with gateway sandbox enabled."
}
```

Quest plan output:

```json
{
  "summary": "Focus on one hard blocker and one short cleanup task.",
  "quests": [
    {
      "task_id": 1002,
      "rank_order": 1,
      "reason": "Highest impact and due today.",
      "suggested_start_at": "2026-04-30T13:00:00+05:30",
      "suggested_end_at": "2026-04-30T15:00:00+05:30",
      "xp_value": 140
    }
  ]
}
```

Standup note output:

```json
{
  "accomplished": ["Fixed retry timeout in the payment gateway integration."],
  "in_progress": ["Continuing order tracking API implementation."],
  "blockers": ["Need sandbox timeout confirmation."],
  "next_steps": ["Merge payment fix after CI passes."],
  "full_note": "Completed payment gateway timeout fix. Continuing order tracking API work. Blocked on sandbox timeout confirmation."
}
```

Daily overview output:

```json
{
  "summary": "A high-impact backend day focused on payment reliability.",
  "new_learnings": ["Gateway sandbox timeout thresholds differ from production."],
  "went_well": ["Regression tests caught the timeout path."],
  "went_wrong": ["Retry policy lacked a cap."],
  "themes": ["Reliability", "Testing"]
}
```

## 19. Python Production Implementation Requirements

### 19.1 Database Pool

Use `oracledb.create_pool_async()` at app startup:

```python
import oracledb

async def create_db_pool(settings):
    return oracledb.create_pool_async(
        user=settings.oracle_db_user,
        password=settings.oracle_db_password,
        dsn=settings.oracle_db_dsn,
        config_dir=settings.oracle_db_wallet_dir,
        wallet_location=settings.oracle_db_wallet_dir,
        wallet_password=settings.oracle_db_wallet_password,
        min=settings.oracle_db_pool_min,
        max=settings.oracle_db_pool_max,
        increment=settings.oracle_db_pool_increment,
        timeout=settings.oracle_db_pool_timeout_seconds,
    )
```

Repository pattern:

```python
async with pool.acquire() as conn:
    async with conn.cursor() as cur:
        await cur.execute(sql, binds)
        rows = await cur.fetchall()
```

Transaction pattern:

```python
async with pool.acquire() as conn:
    try:
        async with conn.cursor() as cur:
            await cur.execute(insert_sql, binds)
            await cur.execute(event_sql, event_binds)
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
```

### 19.2 Error Handling

Add one exception handler for domain errors and one for unknown errors.

```python
class DomainError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 400, details: dict | None = None):
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}
```

Rules:

- Convert Oracle unique constraint errors to `409`.
- Convert missing rows to `404`.
- Convert row version mismatch to `409`.
- Convert OCI timeout to `503`.
- Convert invalid AI response to `502`.
- Log stack traces server-side only.

### 19.3 Validation And Concurrency

- Every update request should include `row_version`.
- SQL update should include `WHERE TASK_ID = :task_id AND USER_ID = :user_id AND ROW_VERSION = :row_version`.
- If row count is zero, check whether task exists. Return `404` if missing, `409` if version mismatch.
- Increment `ROW_VERSION = ROW_VERSION + 1` on every update.

### 19.4 Idempotency

Create an `IDEMPOTENCY_KEYS` table for write endpoints:

```sql
CREATE TABLE IDEMPOTENCY_KEYS (
  IDEMPOTENCY_KEY VARCHAR2(120) PRIMARY KEY,
  USER_ID NUMBER(19) NOT NULL,
  METHOD VARCHAR2(10) NOT NULL,
  PATH VARCHAR2(500) NOT NULL,
  REQUEST_HASH VARCHAR2(128) NOT NULL,
  RESPONSE_JSON CLOB CHECK (RESPONSE_JSON IS JSON),
  STATUS_CODE NUMBER(3),
  CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL
);
```

Use it for:

- `POST /tasks`
- `POST /tasks/{task_id}/complete`
- `POST /quests/generate`
- `POST /standup-notes/generate`
- `POST /overviews/*/generate`
- `POST /sync/run`

### 19.5 Performance

- Dashboard endpoint should use bulk queries and avoid per-task database round trips.
- AI generation endpoints should cache by `(user_id, run_type, date, input_hash)`.
- Add indexes for `(USER_ID, STATUS)`, `(USER_ID, COMPLETED_AT)`, `(USER_ID, WORK_DATE)`, and calendar date ranges.
- For long sync and bulk AI jobs, return `202 Accepted` and process in a background worker.

### 19.6 Security

- Never trust `user_id` from request body. Resolve it from auth context.
- Enforce row ownership in every query.
- Keep Oracle wallet and OCI credentials outside repo.
- Limit CORS to the frontend origin.
- Rate limit AI generation endpoints per user.
- Redact notes if they can contain secrets before sending to AI, or add user-visible warning and enterprise data policy.

## 20. Frontend Integration Steps

1. Add API client module, for example `frontend/src/api/client.js`, using `axios`.
2. Replace `initialTasks` with `GET /api/v1/dashboard/today` on dashboard load.
3. Replace `TasksPage` form with fields for title, description, type, source, external ID, priority, status, due date, estimate, XP, labels, notes, and working-today checkbox.
4. Wire Add Task to `POST /api/v1/tasks`.
5. Add Edit Task dialog and wire to `PATCH /api/v1/tasks/{task_id}`.
6. Add Notes input or dialog and wire to `PUT /api/v1/tasks/{task_id}/notes`.
7. Add "Working Today" button or toggle per row and wire to `PUT /api/v1/tasks/{task_id}/today`.
8. Change Done button to `POST /api/v1/tasks/{task_id}/complete`.
9. Change Quests page to `GET /api/v1/quests/today`.
10. Wire Generate Quests button to `POST /api/v1/quests/generate`.
11. Wire AI Insights refresh to `POST /api/v1/insights/today/generate`.
12. Add Standup Note UI on AI Insights page or new sub-panel and wire to standup endpoints.
13. Add Daily/Weekly Overview nav item and page. Wire to overview endpoints.
14. Keep Leaderboard hidden or disabled until backend scope is restored.

## 21. Implementation Order

Recommended build order:

1. Replace MongoDB sample backend with FastAPI app structure and Oracle pool.
2. Add migrations and create schema.
3. Implement task CRUD, task notes, status, completion, and daily work APIs.
4. Wire frontend My Tasks and Dashboard to real task data.
5. Implement calendar event APIs and capacity calculation.
6. Implement Quest read API from `DAILY_WORK_ITEMS`.
7. Add OCI GenAI task enrichment.
8. Add quest generation and persist quest plans.
9. Add standup generator.
10. Add daily and weekly overview APIs and frontend page.
11. Add sync placeholders, then real Jira/Outlook/Microsoft To Do integrations.
12. Add OCI Agent for historical or SQL-grounded insights.

## 22. Test Plan

Backend unit tests:

- Create task with all fields.
- Create task with `working_today = true` inserts `DAILY_WORK_ITEMS`.
- Patch task updates only provided fields and increments row version.
- Row version conflict returns `409`.
- Complete task sets `STATUS = 'Done'` and `COMPLETED_AT`.
- Notes update changes `NOTES` and triggers AI enrichment when requested.
- Quests read from `DAILY_WORK_ITEMS`, not all tasks.
- Standup generator uses only completed/in-progress/blocked rows for the date.
- Daily overview totals are deterministic and do not rely on AI math.
- AI invalid JSON returns `502` and stores `AI_RUNS.STATUS = 'VALIDATION_FAILED'`.

Integration tests:

- Oracle insert/update transaction rolls back on event insert failure.
- Unique external source upsert works for Jira and Outlook rows.
- Calendar capacity calculation handles overlapping meetings.
- OCI GenAI timeout maps to `503`.
- Agent response with unknown task ID is rejected.

Frontend integration tests:

- Add full task fields, see persisted row after refresh.
- Edit task, refresh, verify update persists.
- Toggle Working Today, verify task appears on Quests page.
- Complete task, verify completion date appears in API and Daily Overview.
- Add notes, generate AI insight, verify notes influence output.

## 23. Oracle Documentation References

- OCI Generative AI Inference Python SDK: https://docs.oracle.com/en-us/iaas/tools/python/latest/api/generative_ai_inference/client/oci.generative_ai_inference.GenerativeAiInferenceClient.html
- OCI Generative AI Inference models: https://docs.oracle.com/en-us/iaas/tools/python/latest/api/generative_ai_inference.html
- OCI Generative AI Agent Runtime Python SDK: https://docs.oracle.com/en-us/iaas/tools/python/latest/api/generative_ai_agent_runtime/client/oci.generative_ai_agent_runtime.GenerativeAiAgentRuntimeClient.html
- OCI Generative AI Agent Runtime models: https://docs.oracle.com/en-us/iaas/tools/python/latest/api/generative_ai_agent_runtime.html
- python-oracledb connection handling and Autonomous DB wallet sections: https://python-oracledb.readthedocs.io/en/latest/user_guide/connection_handling.html
