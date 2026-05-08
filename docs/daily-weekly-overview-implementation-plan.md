# Daily And Weekly Overview Implementation Plan

## Goal

Daily and Weekly Overviews should give a developer evidence-based insight into what happened, what was learned, where time went, and what patterns are emerging. Totals are computed by backend code from Oracle tables. OCI Generative AI is used only for narrative insight, themes, and concise interpretation.

## UI Scope

- Add a date picker to Daily Overview.
- Add a week picker behavior to Weekly Overview by accepting any date and normalizing it to that Monday.
- Add `Generate` actions for both overview scopes.
- Display backend-generated summaries, themes, learnings, went-well, went-wrong, completed work, focus evidence, meeting time, focus time, and XP.
- Keep a local fallback so the React demo remains usable when the backend or Oracle DB is unavailable.

## Tables Used

Daily Overview reads:

- `WORK_ITEMS`: completed tasks, XP, actual minutes, notes, AI fields, task labels.
- `WORK_ITEM_WORK_DATES`: tasks planned or worked for the selected date.
- `CALENDAR_EVENTS`: meeting count and meeting minutes for the selected date.
- `FOCUS_SESSIONS`: actual focus minutes and focus-session notes for the selected date.
- `DAILY_OVERVIEWS`: cached/generated overview row for the selected user and date.
- `AI_RUNS`: prompt, model metadata, response, status, and failure tracking.

Weekly Overview reads:

- `DAILY_OVERVIEWS`: daily summaries when available.
- `WORK_ITEMS`: completed tasks for the week when daily rows are missing or incomplete.
- `WORK_ITEM_WORK_DATES`: worked/planned task evidence across the week.
- `CALENDAR_EVENTS`: weekly meeting load.
- `FOCUS_SESSIONS`: actual weekly focus minutes.
- `WEEKLY_OVERVIEWS`: cached/generated weekly row.
- `AI_RUNS`: generation audit trail.

## Backend API

- `GET /api/v1/overviews/daily?date=YYYY-MM-DD`
- `POST /api/v1/overviews/daily/generate`
- `GET /api/v1/overviews/weekly?week_start=YYYY-MM-DD`
- `POST /api/v1/overviews/weekly/generate`

Daily generation flow:

1. Resolve current user from auth context; current local implementation uses `DEFAULT_USER_ID = 1`.
2. Gather completed tasks, worked tasks, meetings, and focus sessions for the selected date.
3. Compute totals in code: `tasks_completed`, `xp_earned`, `meeting_minutes`, `focus_minutes`.
4. Insert `AI_RUNS` with `RUN_TYPE = DAILY_OVERVIEW`, request JSON, model ID, and `RUNNING`.
5. Call OCI GenAI in real mode, or deterministic mock AI in local mode.
6. Validate JSON shape.
7. Upsert `DAILY_OVERVIEWS`.
8. Mark `AI_RUNS` as `SUCCEEDED`, `FAILED`, or `VALIDATION_FAILED`.

Weekly generation follows the same pattern, with Monday-to-Sunday date range normalization and `RUN_TYPE = WEEKLY_OVERVIEW`.

## OCI Model Choice

Use OCI Generative AI Inference for structured generation.

Recommended environment:

```bash

DEVQUEST_AI_PROVIDER=oci_genai
OCI_GENAI_MODEL_ID=cohere.command-r-plus
OCI_GENAI_REQUEST_FORMAT=auto
OCI_GENAI_SERVING_MODE=on_demand
OCI_COMPARTMENT_ID=ocid1.compartment.oc1...
OCI_REGION=us-chicago-1
```

Use OCI Generative AI Agents only for later historical questions that require grounded SQL/tool access, such as recurring blocker analysis across many weeks. The overview generation path should stay direct GenAI because it needs strict JSON and predictable latency.

`oracledb` is the right database path for these endpoints. LangChain is not required for the implemented flow because the backend already gathers and bounds the context before calling OCI. If later agentic SQL exploration is added, use read-only DB views and a constrained OCI Agent/SQL tool instead of letting the model query base tables directly.

## Daily System Prompt

```text
You are Gamified Tasks Dashboard's productivity insight analyst for a developer.
Use only the supplied task, work-date, focus-session, and calendar evidence.
Do not calculate totals; the backend supplies numeric totals.
Do not invent task names, meetings, blockers, or accomplishments.
Return only valid JSON that matches this schema:
{
  "summary": "1-2 sentence evidence-based day summary",
  "new_learnings": ["specific learning inferred from notes or work"],
  "went_well": ["specific positive outcome"],
  "went_wrong": ["specific friction, risk, blocker, or empty array"],
  "themes": ["short theme labels"]
}
Keep every array to 1-5 concise strings.
```

## Weekly System Prompt

```text
You are Gamified Tasks Dashboard's weekly productivity analyst for a developer.
Use only the supplied daily summaries, completed tasks, work-date rows, focus sessions, and calendar evidence.
Do not calculate totals; the backend supplies numeric totals.
Separate evidence from interpretation, and avoid motivational filler.
Return only valid JSON that matches this schema:
{
  "summary": "2-3 sentence weekly insight",
  "top_accomplishments": ["specific completed outcome"],
  "new_learnings": ["learning or pattern from notes"],
  "themes": ["short theme labels"],
  "went_well": ["specific positive pattern"],
  "went_wrong": ["specific friction, risk, blocker, or empty array"]
}
Keep every array to 1-6 concise strings.
```

## User Prompt Shape

```text
Generate the daily|weekly overview from this JSON context.
Preserve exact task titles when mentioning tasks. If evidence is thin, say what is known instead of guessing.

{context_json}
```

The context JSON contains:

- `start_date`, `end_date`
- deterministic `metrics`
- `completed_tasks`
- `worked_tasks`
- `calendar_events`
- `focus_sessions`
- weekly-only `daily_overviews`

## Validation And Safety

- Never ask AI to calculate totals.
- Redact or omit secrets before sending notes to OCI.
- Validate model JSON before persisting.
- Reject unknown task IDs if future prompts return task references.
- Store request and response in `AI_RUNS` only if enterprise policy allows prompt retention.
- Keep row ownership enforced in every query.
- Add rate limiting before exposing real AI generation publicly.

## Verification

- Backend smoke checks:
  - `GET /api/v1/overviews/daily?date=2026-05-05`
  - `POST /api/v1/overviews/daily/generate`
  - `GET /api/v1/overviews/weekly?week_start=2026-05-04`
  - `POST /api/v1/overviews/weekly/generate`
- Frontend checks:
  - Overview loads the selected date.
  - Changing the daily date refreshes daily insight.
  - Changing the weekly date normalizes to that week.
  - Generate buttons show loading state and update summaries.
