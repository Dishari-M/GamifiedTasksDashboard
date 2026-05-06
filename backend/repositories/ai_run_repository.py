import json


def insert_ai_run(cur, user_id, run_type, model_id, request_payload):
    ai_run_id = cur.var(int)
    cur.execute(
        """
        INSERT INTO AI_RUNS (
            AI_RUN_ID,
            USER_ID,
            RUN_TYPE,
            STATUS,
            PROVIDER,
            MODEL_ID,
            REQUEST_JSON,
            STARTED_AT,
            CREATED_AT
        )
        VALUES (
            AI_RUNS_SEQ.NEXTVAL,
            :user_id,
            :run_type,
            'RUNNING',
            'OCI',
            :model_id,
            :request_json,
            SYSTIMESTAMP,
            SYSTIMESTAMP
        )
        RETURNING AI_RUN_ID INTO :ai_run_id
        """,
        {
            "user_id": user_id,
            "run_type": run_type,
            "model_id": model_id,
            "request_json": _json_dump(request_payload),
            "ai_run_id": ai_run_id,
        },
    )
    return _returned_id(ai_run_id)


def update_ai_run(cur, ai_run_id, status, response_payload=None, error_code=None, error_message=None):
    cur.execute(
        """
        UPDATE AI_RUNS
        SET STATUS = :status,
            RESPONSE_JSON = :response_json,
            ERROR_CODE = :error_code,
            ERROR_MESSAGE = :error_message,
            COMPLETED_AT = SYSTIMESTAMP
        WHERE AI_RUN_ID = :ai_run_id
        """,
        {
            "ai_run_id": ai_run_id,
            "status": status,
            "response_json": _json_dump(response_payload) if response_payload is not None else None,
            "error_code": error_code,
            "error_message": str(error_message)[:1000] if error_message else None,
        },
    )


def latest_successful_run(cur, user_id, run_type, work_date):
    cur.execute(
        """
        SELECT AI_RUN_ID, REQUEST_JSON, RESPONSE_JSON, CREATED_AT
        FROM AI_RUNS
        WHERE USER_ID = :user_id
          AND RUN_TYPE = :run_type
          AND STATUS = 'SUCCEEDED'
        ORDER BY CREATED_AT DESC, AI_RUN_ID DESC
        FETCH FIRST 50 ROWS ONLY
        """,
        {"user_id": user_id, "run_type": run_type},
    )
    for row in cur.fetchall():
        request_payload = _json_load(row[1])
        if _payload_date(request_payload) == work_date:
            return {
                "ai_run_id": row[0],
                "request_payload": request_payload,
                "response_payload": _json_load(row[2]),
                "created_at": row[3].isoformat() if row[3] else None,
            }
    return None


def _payload_date(payload):
    request = payload.get("request") if isinstance(payload.get("request"), dict) else {}
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    return request.get("date") or request.get("quest_date") or context.get("date")


def _json_dump(value):
    return json.dumps(value or {}, separators=(",", ":"), default=str)


def _json_load(value):
    if not value:
        return {}
    if hasattr(value, "read"):
        value = value.read()
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {}


def _returned_id(var):
    value = var.getvalue()
    return value[0] if isinstance(value, list) else value
