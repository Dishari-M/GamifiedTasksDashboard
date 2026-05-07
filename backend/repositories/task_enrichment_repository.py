import json


TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "AUTH_REQUIRED", "CANCELLED"}
ACTIVE_STATUSES = {"QUEUED", "RUNNING"}

_SCHEMA_ENSURED = False


def ensure_schema(cur):
    global _SCHEMA_ENSURED
    if _SCHEMA_ENSURED:
        return

    _ensure_sequence(cur, "TASK_ENRICHMENT_JOBS_SEQ")
    _ensure_work_item_columns(cur)
    _ensure_jobs_table(cur)
    _ensure_index(cur, "TEJ_USER_STATUS_CREATED_IX", "CREATE INDEX TEJ_USER_STATUS_CREATED_IX ON TASK_ENRICHMENT_JOBS (USER_ID, STATUS, CREATED_AT)")
    _ensure_index(cur, "TEJ_USER_SOURCE_EXT_IX", "CREATE INDEX TEJ_USER_SOURCE_EXT_IX ON TASK_ENRICHMENT_JOBS (USER_ID, SOURCE, EXTERNAL_ID)")
    _SCHEMA_ENSURED = True


def insert_job(cur, user_id, payload):
    job_id = cur.var(int)
    source = str(payload.get("source") or payload.get("external_source") or "Jira").strip() or "Jira"
    external_id = str(payload.get("externalId") or payload.get("external_id") or "").strip().upper()
    code_base_path = str(payload.get("codeBaseLocation") or payload.get("code_base_path") or "").strip()
    task_id = _task_id_from_payload(payload)
    cur.execute(
        """
        INSERT INTO TASK_ENRICHMENT_JOBS (
            ENRICHMENT_JOB_ID,
            USER_ID,
            SOURCE,
            EXTERNAL_ID,
            CODE_BASE_PATH,
            STATUS,
            TASK_ID,
            REQUEST_JSON,
            CREATED_AT,
            UPDATED_AT
        )
        VALUES (
            TASK_ENRICHMENT_JOBS_SEQ.NEXTVAL,
            :user_id,
            :source,
            :external_id,
            :code_base_path,
            'QUEUED',
            :task_id,
            :request_json,
            SYSTIMESTAMP,
            SYSTIMESTAMP
        )
        RETURNING ENRICHMENT_JOB_ID INTO :job_id
        """,
        {
            "user_id": user_id,
            "source": source,
            "external_id": external_id,
            "code_base_path": code_base_path,
            "task_id": task_id,
            "request_json": _json_dump(payload),
            "job_id": job_id,
        },
    )
    return _returned_id(job_id)


def mark_running(cur, user_id, job_id, ai_run_id=None):
    cur.execute(
        """
        UPDATE TASK_ENRICHMENT_JOBS
        SET STATUS = 'RUNNING',
            AI_RUN_ID = COALESCE(:ai_run_id, AI_RUN_ID),
            STARTED_AT = COALESCE(STARTED_AT, SYSTIMESTAMP),
            UPDATED_AT = SYSTIMESTAMP
        WHERE ENRICHMENT_JOB_ID = :job_id
          AND USER_ID = :user_id
        """,
        {"job_id": job_id, "user_id": user_id, "ai_run_id": ai_run_id},
    )


def set_jira_fields(cur, user_id, job_id, fields):
    cur.execute(
        """
        UPDATE TASK_ENRICHMENT_JOBS
        SET JIRA_FIELDS_JSON = :jira_fields_json,
            UPDATED_AT = SYSTIMESTAMP
        WHERE ENRICHMENT_JOB_ID = :job_id
          AND USER_ID = :user_id
        """,
        {"job_id": job_id, "user_id": user_id, "jira_fields_json": _json_dump(fields)},
    )


def set_rca_result(cur, user_id, job_id, result):
    cur.execute(
        """
        UPDATE TASK_ENRICHMENT_JOBS
        SET RCA_RESULT_JSON = :rca_result_json,
            UPDATED_AT = SYSTIMESTAMP
        WHERE ENRICHMENT_JOB_ID = :job_id
          AND USER_ID = :user_id
        """,
        {"job_id": job_id, "user_id": user_id, "rca_result_json": _json_dump(result)},
    )


def mark_succeeded(cur, user_id, job_id, task_id, result):
    cur.execute(
        """
        UPDATE TASK_ENRICHMENT_JOBS
        SET STATUS = 'SUCCEEDED',
            TASK_ID = :task_id,
            RCA_RESULT_JSON = :rca_result_json,
            ERROR_CODE = NULL,
            ERROR_MESSAGE = NULL,
            COMPLETED_AT = SYSTIMESTAMP,
            UPDATED_AT = SYSTIMESTAMP
        WHERE ENRICHMENT_JOB_ID = :job_id
          AND USER_ID = :user_id
          AND STATUS IN ('QUEUED', 'RUNNING')
        """,
        {
            "job_id": job_id,
            "user_id": user_id,
            "task_id": task_id,
            "rca_result_json": _json_dump(result),
        },
    )


def mark_failed(cur, user_id, job_id, status, error_code, error_message):
    status = status if status in TERMINAL_STATUSES else "FAILED"
    cur.execute(
        """
        UPDATE TASK_ENRICHMENT_JOBS
        SET STATUS = :status,
            ERROR_CODE = :error_code,
            ERROR_MESSAGE = :error_message,
            COMPLETED_AT = SYSTIMESTAMP,
            UPDATED_AT = SYSTIMESTAMP
        WHERE ENRICHMENT_JOB_ID = :job_id
          AND USER_ID = :user_id
        """,
        {
            "job_id": job_id,
            "user_id": user_id,
            "status": status,
            "error_code": str(error_code or "")[:100],
            "error_message": str(error_message or ""),
        },
    )


def fetch_job(cur, user_id, job_id):
    cur.execute(
        """
        SELECT
            ENRICHMENT_JOB_ID,
            USER_ID,
            SOURCE,
            EXTERNAL_ID,
            CODE_BASE_PATH,
            STATUS,
            TASK_ID,
            AI_RUN_ID,
            REQUEST_JSON,
            JIRA_FIELDS_JSON,
            RCA_RESULT_JSON,
            ERROR_CODE,
            ERROR_MESSAGE,
            TO_CHAR(STARTED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(COMPLETED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(CREATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(UPDATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM')
        FROM TASK_ENRICHMENT_JOBS
        WHERE ENRICHMENT_JOB_ID = :job_id
          AND USER_ID = :user_id
        """,
        {"job_id": job_id, "user_id": user_id},
    )
    row = cur.fetchone()
    if not row:
        return None
    job = _job_row(row)
    job["logs"] = []
    return job


def list_jobs(cur, user_id, limit=20):
    cur.execute(
        """
        SELECT *
        FROM (
            SELECT
                ENRICHMENT_JOB_ID,
                USER_ID,
                SOURCE,
                EXTERNAL_ID,
                CODE_BASE_PATH,
                STATUS,
                TASK_ID,
                AI_RUN_ID,
                REQUEST_JSON,
                JIRA_FIELDS_JSON,
                RCA_RESULT_JSON,
                ERROR_CODE,
                ERROR_MESSAGE,
                TO_CHAR(STARTED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
                TO_CHAR(COMPLETED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
                TO_CHAR(CREATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
                TO_CHAR(UPDATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM')
            FROM TASK_ENRICHMENT_JOBS
            WHERE USER_ID = :user_id
            ORDER BY CASE WHEN STATUS IN ('QUEUED', 'RUNNING') THEN 0 ELSE 1 END,
                     CREATED_AT DESC,
                     ENRICHMENT_JOB_ID DESC
        )
        WHERE ROWNUM <= :limit
        """,
        {"user_id": user_id, "limit": int(limit or 20)},
    )
    return [_job_row(row) for row in cur.fetchall()]


def list_active_jobs(cur, user_id):
    cur.execute(
        """
        SELECT
            ENRICHMENT_JOB_ID,
            USER_ID,
            SOURCE,
            EXTERNAL_ID,
            CODE_BASE_PATH,
            STATUS,
            TASK_ID,
            AI_RUN_ID,
            REQUEST_JSON,
            JIRA_FIELDS_JSON,
            RCA_RESULT_JSON,
            ERROR_CODE,
            ERROR_MESSAGE,
            TO_CHAR(STARTED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(COMPLETED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(CREATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(UPDATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM')
        FROM TASK_ENRICHMENT_JOBS
        WHERE USER_ID = :user_id
          AND STATUS IN ('QUEUED', 'RUNNING')
        """,
        {"user_id": user_id},
    )
    return [_job_row(row) for row in cur.fetchall()]


def fetch_active_job_by_external_identity(cur, user_id, source, external_id):
    cur.execute(
        """
        SELECT
            ENRICHMENT_JOB_ID,
            USER_ID,
            SOURCE,
            EXTERNAL_ID,
            CODE_BASE_PATH,
            STATUS,
            TASK_ID,
            AI_RUN_ID,
            REQUEST_JSON,
            JIRA_FIELDS_JSON,
            RCA_RESULT_JSON,
            ERROR_CODE,
            ERROR_MESSAGE,
            TO_CHAR(STARTED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(COMPLETED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(CREATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
            TO_CHAR(UPDATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM')
        FROM TASK_ENRICHMENT_JOBS
        WHERE USER_ID = :user_id
          AND SOURCE = :source
          AND EXTERNAL_ID = :external_id
          AND STATUS IN ('QUEUED', 'RUNNING')
        ORDER BY CREATED_AT DESC, ENRICHMENT_JOB_ID DESC
        FETCH FIRST 1 ROW ONLY
        """,
        {
            "user_id": user_id,
            "source": source,
            "external_id": external_id,
        },
    )
    row = cur.fetchone()
    return _job_row(row) if row else None


def _ensure_work_item_columns(cur):
    columns = {
        "RCA_REASON": "ALTER TABLE WORK_ITEMS ADD RCA_REASON CLOB",
        "RCA_AFFECTED_FILES_JSON": "ALTER TABLE WORK_ITEMS ADD RCA_AFFECTED_FILES_JSON CLOB",
        "RCA_CODE_SUGGESTION": "ALTER TABLE WORK_ITEMS ADD RCA_CODE_SUGGESTION CLOB",
        "RCA_RAW_OUTPUT": "ALTER TABLE WORK_ITEMS ADD RCA_RAW_OUTPUT CLOB",
        "RCA_TSHIRT_JUSTIFICATION": "ALTER TABLE WORK_ITEMS ADD RCA_TSHIRT_JUSTIFICATION CLOB",
        "SOURCE_ENRICHMENT_JOB_ID": "ALTER TABLE WORK_ITEMS ADD SOURCE_ENRICHMENT_JOB_ID NUMBER(19)",
    }
    for column_name, ddl in columns.items():
        if not _column_exists(cur, "WORK_ITEMS", column_name):
            cur.execute(ddl)
    _ensure_constraint(
        cur,
        "WORK_ITEMS_RCA_FILES_JSON_CK",
        "ALTER TABLE WORK_ITEMS ADD CONSTRAINT WORK_ITEMS_RCA_FILES_JSON_CK CHECK (RCA_AFFECTED_FILES_JSON IS JSON)",
    )


def _ensure_jobs_table(cur):
    if _table_exists(cur, "TASK_ENRICHMENT_JOBS"):
        return
    cur.execute(
        """
        CREATE TABLE TASK_ENRICHMENT_JOBS (
            ENRICHMENT_JOB_ID NUMBER(19) PRIMARY KEY,
            USER_ID NUMBER(19) NOT NULL,
            SOURCE VARCHAR2(40) NOT NULL,
            EXTERNAL_ID VARCHAR2(200) NOT NULL,
            CODE_BASE_PATH VARCHAR2(1000),
            STATUS VARCHAR2(30) NOT NULL,
            TASK_ID NUMBER(19),
            AI_RUN_ID NUMBER(19),
            REQUEST_JSON CLOB CHECK (REQUEST_JSON IS JSON),
            JIRA_FIELDS_JSON CLOB CHECK (JIRA_FIELDS_JSON IS JSON),
            RCA_RESULT_JSON CLOB CHECK (RCA_RESULT_JSON IS JSON),
            ERROR_CODE VARCHAR2(100),
            ERROR_MESSAGE CLOB,
            STARTED_AT TIMESTAMP WITH TIME ZONE,
            COMPLETED_AT TIMESTAMP WITH TIME ZONE,
            CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
            UPDATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
            CONSTRAINT TEJ_STATUS_CK CHECK (STATUS IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'AUTH_REQUIRED', 'CANCELLED'))
        )
        """
    )


def _ensure_sequence(cur, sequence_name):
    cur.execute("SELECT COUNT(*) FROM USER_SEQUENCES WHERE SEQUENCE_NAME = :name", {"name": sequence_name})
    if not cur.fetchone()[0]:
        cur.execute(f"CREATE SEQUENCE {sequence_name} START WITH 1 INCREMENT BY 1 CACHE 50 NOCYCLE")


def _ensure_index(cur, index_name, ddl):
    cur.execute("SELECT COUNT(*) FROM USER_INDEXES WHERE INDEX_NAME = :name", {"name": index_name})
    if not cur.fetchone()[0]:
        cur.execute(ddl)


def _ensure_constraint(cur, constraint_name, ddl):
    cur.execute("SELECT COUNT(*) FROM USER_CONSTRAINTS WHERE CONSTRAINT_NAME = :name", {"name": constraint_name})
    if not cur.fetchone()[0]:
        cur.execute(ddl)


def _table_exists(cur, table_name):
    cur.execute("SELECT COUNT(*) FROM USER_TABLES WHERE TABLE_NAME = :name", {"name": table_name})
    return bool(cur.fetchone()[0])


def _column_exists(cur, table_name, column_name):
    cur.execute(
        """
        SELECT COUNT(*)
        FROM USER_TAB_COLUMNS
        WHERE TABLE_NAME = :table_name
          AND COLUMN_NAME = :column_name
        """,
        {"table_name": table_name, "column_name": column_name},
    )
    return bool(cur.fetchone()[0])


def _job_row(row):
    request = _json_load(row[8])
    jira_fields = _json_load(row[9])
    rca_result = _json_load(row[10])
    error_message = _text(row[12])
    job = {
        "enrichment_job_id": row[0],
        "id": row[0],
        "user_id": row[1],
        "source": row[2] or "Jira",
        "external_id": row[3] or "",
        "externalId": row[3] or "",
        "code_base_path": row[4] or "",
        "codeBasePath": row[4] or "",
        "status": row[5] or "QUEUED",
        "task_id": row[6],
        "taskId": row[6],
        "ai_run_id": row[7],
        "aiRunId": row[7],
        "request": request,
        "jira_fields": jira_fields,
        "jiraFields": jira_fields,
        "rca_result": rca_result,
        "rcaResult": rca_result,
        "error_code": row[11] or "",
        "errorCode": row[11] or "",
        "error_message": error_message,
        "errorMessage": error_message,
        "started_at": row[13],
        "startedAt": row[13],
        "completed_at": row[14],
        "completedAt": row[14],
        "created_at": row[15],
        "createdAt": row[15],
        "updated_at": row[16],
        "updatedAt": row[16],
    }
    return job


def _json_dump(value):
    return json.dumps(value or {}, separators=(",", ":"), default=str)


def _json_load(value):
    if isinstance(value, dict):
        return value
    text = _text(value)
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _text(value):
    if value is None:
        return ""
    if hasattr(value, "read"):
        return value.read()
    return str(value)


def _returned_id(var):
    value = var.getvalue()
    return value[0] if isinstance(value, list) else value


def _task_id_from_payload(payload):
    value = (
        payload.get("existingTaskId")
        or payload.get("existing_task_id")
        or payload.get("taskId")
        or payload.get("task_id")
    )
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
