# Gamified Tasks Dashboard Agent Guide

## Repo Conventions
- Treat `dishari/main` as the shared upstream branch unless the user says otherwise.
- Do not rename runtime contracts casually: keep `DEVQUEST_*` env vars, `X-DevQuest-User-Id`, localStorage keys, and existing script names stable unless explicitly requested.
- Prefer small, demo-safe changes near demo time. Avoid schema, auth, or API contract changes unless the user explicitly approves them.

## Runtime Modes
- Always clarify or inspect the active mode before testing:
  - `DEVQUEST_DATA_MODE=oracle` vs mock/filesystem.
  - `DEVQUEST_AI_MODE=real` vs mock.
  - DB user/schema in use, currently usually `DEVQUEST_APP` for app runtime.
- Use `start-devquest.cmd` / `start-devquest.ps1` for local demo startup.
- Runtime logs are generated files; do not commit:
  - `backend/uvicorn.err.log`
  - `backend/uvicorn.out.log`
  - `frontend/static-server.out.log`

## Oracle And Cache Patterns
- Use the shared Oracle pool from `backend/db.py`; do not call `oracledb.connect()` directly in request paths.
- Use `connection_scope()` where possible, or close pooled connections in `finally`.
- Read-cache TTL is controlled by `DEVQUEST_API_CACHE_TTL_SECONDS`; local demo default is 300 seconds.
- Cache only read-style GET responses unless there is a deliberate reason.
- When adding or changing write paths, invalidate all affected read namespaces, especially:
  - `task_list`
  - `dashboard_today`
  - `insights_today`
  - `quests_today`
  - `quest_progress`
  - `focus_sessions`
  - `standup_note`
  - `daily_overview`
  - `weekly_overview`

## Testing And Validation
- Before committing, run:
  - `git status --short --untracked-files=all`
  - `git diff --check`
  - `python -m compileall backend\services backend\routes backend\repositories` for backend changes.
  - `npm run build` from `frontend` for frontend/CSS changes.
- Default smoke tests should be GET-only unless the user explicitly approves writes.
- For POST testing, state whether the endpoint mutates data, generates AI, or is safe with `force=false`.
- For demo performance checks, test both first-hit and immediate second-hit timings to verify cache behavior.

## PR Hygiene
- Pull latest upstream before final commit: `git pull dishari main`.
- Exclude generated logs and accidental local artifacts unless the user explicitly asks to include them.
- Use concise commits scoped to one concern.
- Include validation evidence in the PR body or final response.

## Frontend Gotchas
- Keep branding responsive in the sidebar; avoid text that can wrap mid-word or overflow.
- Verify visual fixes in both dark and light themes when touching shared styles.
- Prefer existing CSS files and component patterns; avoid broad restyling during demo hardening.
