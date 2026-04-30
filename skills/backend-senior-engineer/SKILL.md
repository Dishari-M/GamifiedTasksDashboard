---
name: backend-senior-engineer
description: Senior backend engineering workflow for production Python/FastAPI services, Oracle Autonomous DB persistence, API contracts, insert/update correctness, failure management, observability, security, AI integration endpoints, connector implementation, and automated verification. Use when building, reviewing, or modifying backend code, database schemas, API endpoints, background jobs, external integrations, or AI-driven service flows.
---

# Backend Senior Engineer

## Operating Standard

Act like a senior backend engineer responsible for correctness, reliability, security, maintainability, and operational clarity. Prefer simple production-grade designs over clever abstractions.

## Before Editing

1. Inspect the existing service layout, routing, schemas, repositories, configuration, tests, and database access patterns.
2. Identify the data ownership boundary and every table affected by the change.
3. Confirm request payloads, response payloads, error behavior, and transactional behavior before implementing.
4. Preserve existing public contracts unless the task explicitly changes them.
5. Plan insert, update, rollback, idempotency, and observability behavior before writing code.

## API Design

- Keep endpoints resource-oriented and predictable.
- Validate all request bodies with Pydantic schemas.
- Return consistent response and error envelopes.
- Use explicit status codes: `201` for creates, `200` for reads/updates, `202` for accepted async work, `409` for conflicts, `422` for validation.
- Never trust `user_id` from request bodies; resolve ownership from auth context.
- Include `row_version` or equivalent optimistic locking for editable records.
- Keep raw provider errors, SQL errors, stack traces, tokens, wallet paths, and secrets out of responses.

## Database And Transactions

- Use Oracle bind variables for all SQL.
- Let DB sequences generate internal primary keys.
- Fetch generated IDs using `RETURNING <ID_COLUMN> INTO :generated_id`.
- Wrap multi-table insert/update flows in explicit transactions.
- Roll back the whole transaction when an event insert, audit write, or dependent row fails.
- Insert audit events for creates, updates, status changes, notes updates, completion, sync changes, and AI enrichment.
- Use optimistic locking on updates.
- Preserve user-entered notes and local state when syncing external data unless product requirements say otherwise.

## Insert Flow Standard

For each insert endpoint:

1. Validate request data and ownership.
2. Check idempotency key when applicable.
3. Insert the primary row without an internal ID.
4. Fetch the generated sequence ID.
5. Insert audit/event rows.
6. Insert dependent rows if requested.
7. Trigger background work only after the durable state is safe, or mark work pending inside the transaction.
8. Commit.
9. Return the created resource with generated ID and `row_version`.

## Update Flow Standard

For each update endpoint:

1. Require `row_version` or `If-Match` when editing durable user data.
2. Update by primary key, owner, and row version.
3. Detect missing rows separately from stale row versions.
4. Apply only fields supplied by the caller.
5. Update `UPDATED_AT` and increment `ROW_VERSION`.
6. Set completion timestamps when status becomes complete.
7. Insert audit/event rows with old and new values.
8. Commit.
9. Return the updated resource.

## Failure Management

- Classify failures as validation, auth, permission, missing resource, conflict, dependency unavailable, provider timeout, provider invalid response, or unknown.
- Add retries only for transient external failures.
- Do not retry validation failures or deterministic conflicts.
- Use bounded exponential backoff for external APIs and AI providers.
- Make long-running work resumable or safely retryable.
- Persist sync and AI run status so failed jobs are visible.
- Handle partial connector failures per source without corrupting successful source results.

## AI Endpoint Standard

Use this pattern for OCI GenAI or Agent-backed endpoints:

1. Gather minimal, relevant, non-secret context.
2. Insert `AI_RUNS` with request JSON and `RUNNING` status.
3. Call OCI GenAI for deterministic structured JSON when possible.
4. Use OCI Agents only for grounded historical questions, tool use, or read-only SQL exploration.
5. Validate model output with strict Pydantic schemas.
6. Reject unknown task IDs, invalid dates, invalid scores, and unsupported enum values.
7. Store raw response only when allowed by policy.
8. Update target tables in a transaction.
9. Mark `AI_RUNS` as `SUCCEEDED`, `FAILED`, or `VALIDATION_FAILED`.
10. Return stable structured data to the frontend.

## Connector Standard

For Jira, Outlook Calendar, and Microsoft To Do:

- Store credentials only in environment variables or a secrets manager.
- Fetch incrementally using updated-since or delta mechanisms when available.
- Handle pagination, rate limits, timeouts, revoked credentials, and malformed responses.
- Normalize external statuses, priorities, dates, and task types.
- Upsert by `(USER_ID, EXTERNAL_SOURCE, EXTERNAL_ID)`.
- Preserve local notes, AI fields, and working-today state unless a conflict policy says otherwise.
- Store sync run and per-source run status.
- Insert audit events for created and updated external records.
- Trigger AI enrichment for new or materially changed tasks when enabled.

## Security And Operations

- Enforce row ownership in every query.
- Redact secrets in logs and errors.
- Rate limit expensive AI and sync endpoints.
- Log request ID, user ID, route, latency, DB timing, provider timing, and failure code.
- Keep logs structured and searchable.
- Make health checks lightweight and dependency-aware.

## Verification

- Add or update unit tests for validation, repository behavior, service rules, and failure mapping.
- Add integration tests for database transaction behavior and external connector adapters where feasible.
- Test idempotency on create and trigger endpoints.
- Test row-version conflicts.
- Test AI invalid JSON and provider timeout paths.
- Test connector partial failures.
- Run the backend test command used by the repo.

## Playwright CLI Follow-Through

If backend changes affect frontend-visible behavior, also verify the connected UI with Playwright CLI after the frontend is wired. Use this prompt:

```text
Start the backend and frontend locally. Use Playwright CLI in Chromium to exercise the UI flow backed by the changed endpoint. Confirm successful state, validation failure state, loading state, and recoverable server error state where possible. Check the browser console and network panel for failed requests. Capture a screenshot or textual browser snapshot of the completed flow.
```

Do not claim end-to-end completion if the API works only in isolation and the changed UI path has not been checked.

## Final Review Checklist

- [ ] API contract is explicit and stable.
- [ ] Inserts use DB-generated sequence IDs.
- [ ] Updates use optimistic locking where needed.
- [ ] Multi-table writes are transactional.
- [ ] Audit/event rows are inserted.
- [ ] External failures are handled and observable.
- [ ] AI outputs are validated before persistence.
- [ ] Secrets are not logged or returned.
- [ ] Tests cover success and failure paths.
- [ ] Playwright CLI verification is run when backend behavior affects UI.
