import json


TASK_SELECT = """
    SELECT
        w.TASK_ID,
        w.USER_ID,
        w.EXTERNAL_SOURCE,
        w.EXTERNAL_ID,
        w.TITLE,
        w.DESCRIPTION,
        w.TASK_TYPE,
        w.PRIORITY,
        w.STATUS,
        w.PROJECT_KEY,
        TO_CHAR(w.DUE_DATE, 'YYYY-MM-DD'),
        TO_CHAR(w.START_DATE, 'YYYY-MM-DD'),
        w.ESTIMATED_MINUTES,
        w.ACTUAL_MINUTES,
        w.RCA_TSHIRT_SIZE,
        w.RCA_FILE_CHANGE_COUNT,
        w.RCA_COMPLEXITY_SOURCE,
        TO_CHAR(w.RCA_COMPLEXITY_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
        w.XP_VALUE,
        w.NOTES,
        w.LABELS_JSON,
        w.AI_DIFFICULTY,
        w.AI_IMPACT_SCORE,
        w.AI_PRIORITY_SCORE,
        w.AI_EFFORT_MINUTES,
        w.AI_CATEGORY,
        w.AI_INSIGHT,
        w.AI_MODEL_VERSION,
        TO_CHAR(w.AI_ENRICHED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
        TO_CHAR(w.COMPLETED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
        TO_CHAR(w.CREATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
        TO_CHAR(w.UPDATED_AT, 'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'),
        w.ROW_VERSION,
        (
            SELECT LISTAGG(TO_CHAR(d.WORK_DATE, 'YYYY-MM-DD'), ',')
                   WITHIN GROUP (ORDER BY d.WORK_DATE)
            FROM WORK_ITEM_WORK_DATES d
            WHERE d.USER_ID = w.USER_ID
              AND d.TASK_ID = w.TASK_ID
        ) AS WORKED_DATES,
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM WORK_ITEM_WORK_DATES td
                WHERE td.USER_ID = w.USER_ID
                  AND td.TASK_ID = w.TASK_ID
                  AND td.WORK_DATE = TO_DATE(:work_date, 'YYYY-MM-DD')
            )
            THEN 1 ELSE 0
        END AS WORKING_TODAY
    FROM WORK_ITEMS w
"""


def list_tasks(cur, user_id, filters, work_date):
    filters = filters or {}
    where, binds = _task_filters(user_id, filters, work_date)
    include_total = _truthy(filters.get("include_total"), default=True)
    total = None
    if include_total:
        total_sql = f"SELECT COUNT(*) FROM WORK_ITEMS w WHERE {' AND '.join(where)}"
        total_binds = _binds_used_by_sql(total_sql, binds)
        cur.execute(total_sql, total_binds)
        total = cur.fetchone()[0]

    page = max(1, int(filters.get("page") or 1))
    page_size = min(100, max(1, int(filters.get("page_size") or 50)))
    offset = (page - 1) * page_size
    fetch_size = page_size if include_total else page_size + 1
    rows_sql = f"""
        {TASK_SELECT}
        WHERE {' AND '.join(where)}
        ORDER BY w.UPDATED_AT DESC, w.CREATED_AT DESC, w.TASK_ID DESC
        OFFSET :offset ROWS FETCH NEXT :fetch_size ROWS ONLY
    """
    row_binds = {**binds, "offset": offset, "fetch_size": fetch_size}
    cur.execute(rows_sql, row_binds)
    rows = cur.fetchall()
    has_next = offset + page_size < total if include_total else len(rows) > page_size
    rows = rows[:page_size]
    return {
        "items": [_task_row(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": has_next,
    }


def _binds_used_by_sql(sql, binds):
    return {name: value for name, value in binds.items() if f":{name}" in sql}


def fetch_task(cur, user_id, task_id, work_date):
    cur.execute(
        f"{TASK_SELECT} WHERE w.USER_ID = :user_id AND w.TASK_ID = :task_id",
        {"user_id": user_id, "task_id": task_id, "work_date": work_date},
    )
    row = cur.fetchone()
    return _task_row(row) if row else None


def fetch_task_for_update(cur, user_id, task_id):
    cur.execute(
        """
        SELECT TASK_ID, USER_ID, STATUS, ROW_VERSION
        FROM WORK_ITEMS
        WHERE USER_ID = :user_id
          AND TASK_ID = :task_id
        FOR UPDATE
        """,
        {"user_id": user_id, "task_id": task_id},
    )
    row = cur.fetchone()
    if not row:
        return None
    return {"task_id": row[0], "user_id": row[1], "status": row[2], "row_version": row[3]}


def fetch_task_by_external_identity_for_update(cur, user_id, external_source, external_id):
    cur.execute(
        """
        SELECT TASK_ID, USER_ID, STATUS, ROW_VERSION
        FROM WORK_ITEMS
        WHERE USER_ID = :user_id
          AND EXTERNAL_SOURCE = :external_source
          AND EXTERNAL_ID = :external_id
        FOR UPDATE
        """,
        {
            "user_id": user_id,
            "external_source": external_source,
            "external_id": external_id,
        },
    )
    row = cur.fetchone()
    if not row:
        return None
    return {"task_id": row[0], "user_id": row[1], "status": row[2], "row_version": row[3]}


def insert_task(cur, user_id, task, ai):
    task_id = cur.var(int)
    cur.execute(
        """
        INSERT INTO WORK_ITEMS (
            TASK_ID,
            USER_ID,
            EXTERNAL_SOURCE,
            EXTERNAL_ID,
            TITLE,
            DESCRIPTION,
            TASK_TYPE,
            PRIORITY,
            STATUS,
            PROJECT_KEY,
            DUE_DATE,
            START_DATE,
            ESTIMATED_MINUTES,
            ACTUAL_MINUTES,
            RCA_TSHIRT_SIZE,
            RCA_FILE_CHANGE_COUNT,
            RCA_COMPLEXITY_SOURCE,
            RCA_COMPLEXITY_AT,
            XP_VALUE,
            NOTES,
            LABELS_JSON,
            AI_DIFFICULTY,
            AI_IMPACT_SCORE,
            AI_PRIORITY_SCORE,
            AI_EFFORT_MINUTES,
            AI_CATEGORY,
            AI_INSIGHT,
            AI_MODEL_VERSION,
            AI_ENRICHED_AT,
            COMPLETED_AT,
            CREATED_AT,
            UPDATED_AT,
            ROW_VERSION
        )
        VALUES (
            WORK_ITEMS_SEQ.NEXTVAL,
            :user_id,
            :external_source,
            :external_id,
            :title,
            :description,
            :task_type,
            :priority,
            :status,
            :project_key,
            :due_at,
            :start_at,
            :estimated_minutes,
            :actual_minutes,
            :rca_tshirt_size,
            :rca_file_change_count,
            :rca_complexity_source,
            :rca_complexity_at,
            :xp_value,
            :notes,
            :labels_json,
            :ai_difficulty,
            :ai_impact_score,
            :ai_priority_score,
            :ai_effort_minutes,
            :ai_category,
            :ai_insight,
            :ai_model_version,
            SYSTIMESTAMP,
            CASE WHEN :status = 'Done' THEN SYSTIMESTAMP ELSE NULL END,
            SYSTIMESTAMP,
            SYSTIMESTAMP,
            1
        )
        RETURNING TASK_ID INTO :task_id
        """,
        {
            **_task_binds(user_id, task, ai),
            "task_id": task_id,
        },
    )
    return _returned_id(task_id)


def update_task_fields(cur, user_id, task_id, fields, expected_row_version=None):
    if not fields:
        return True
    sets = [f"{column} = :{bind}" for column, bind, _ in fields]
    sets.extend(["UPDATED_AT = SYSTIMESTAMP", "ROW_VERSION = ROW_VERSION + 1"])
    binds = {bind: value for _, bind, value in fields}
    binds.update({"task_id": task_id, "user_id": user_id})
    where = "TASK_ID = :task_id AND USER_ID = :user_id"
    if expected_row_version is not None:
        where += " AND ROW_VERSION = :row_version"
        binds["row_version"] = expected_row_version
    cur.execute(f"UPDATE WORK_ITEMS SET {', '.join(sets)} WHERE {where}", binds)
    return cur.rowcount == 1


def touch_task(cur, user_id, task_id, expected_row_version=None):
    binds = {"task_id": task_id, "user_id": user_id}
    where = "TASK_ID = :task_id AND USER_ID = :user_id"
    if expected_row_version is not None:
        where += " AND ROW_VERSION = :row_version"
        binds["row_version"] = expected_row_version
    cur.execute(
        f"""
        UPDATE WORK_ITEMS
        SET UPDATED_AT = SYSTIMESTAMP,
            ROW_VERSION = ROW_VERSION + 1
        WHERE {where}
        """,
        binds,
    )
    return cur.rowcount == 1


def sync_task_work_dates(cur, user_id, task_id, worked_dates):
    cur.execute(
        """
        DELETE FROM WORK_ITEM_WORK_DATES
        WHERE USER_ID = :user_id
          AND TASK_ID = :task_id
        """,
        {"user_id": user_id, "task_id": task_id},
    )
    for work_date in worked_dates:
        insert_work_date(cur, user_id, task_id, work_date)


def insert_work_date(cur, user_id, task_id, work_date, planned_minutes=None):
    cur.execute(
        """
        INSERT INTO WORK_ITEM_WORK_DATES (
            WORK_ITEM_WORK_DATE_ID,
            USER_ID,
            TASK_ID,
            WORK_DATE,
            SOURCE,
            PLANNED_MINUTES,
            CREATED_AT,
            UPDATED_AT,
            ROW_VERSION
        )
        SELECT
            WORK_ITEM_WORK_DATES_SEQ.NEXTVAL,
            :user_id,
            :task_id,
            TO_DATE(:work_date, 'YYYY-MM-DD'),
            'USER',
            :planned_minutes,
            SYSTIMESTAMP,
            SYSTIMESTAMP,
            1
        FROM DUAL
        WHERE NOT EXISTS (
            SELECT 1
            FROM WORK_ITEM_WORK_DATES
            WHERE USER_ID = :user_id
              AND TASK_ID = :task_id
              AND WORK_DATE = TO_DATE(:work_date, 'YYYY-MM-DD')
        )
        """,
        {"user_id": user_id, "task_id": task_id, "work_date": work_date, "planned_minutes": planned_minutes},
    )
    return cur.rowcount == 1


def delete_work_date(cur, user_id, task_id, work_date):
    cur.execute(
        """
        DELETE FROM WORK_ITEM_WORK_DATES
        WHERE USER_ID = :user_id
          AND TASK_ID = :task_id
          AND WORK_DATE = TO_DATE(:work_date, 'YYYY-MM-DD')
        """,
        {"user_id": user_id, "task_id": task_id, "work_date": work_date},
    )
    return cur.rowcount == 1


def list_worked_dates(cur, user_id, task_id):
    cur.execute(
        """
        SELECT TO_CHAR(WORK_DATE, 'YYYY-MM-DD')
        FROM WORK_ITEM_WORK_DATES
        WHERE USER_ID = :user_id
          AND TASK_ID = :task_id
        ORDER BY WORK_DATE
        """,
        {"user_id": user_id, "task_id": task_id},
    )
    return [row[0] for row in cur.fetchall()]


def insert_task_event(cur, user_id, task_id, event_type, old_value=None, new_value=None):
    cur.execute(
        """
        INSERT INTO WORK_ITEM_EVENTS (
            EVENT_ID,
            TASK_ID,
            USER_ID,
            EVENT_TYPE,
            OLD_VALUE_JSON,
            NEW_VALUE_JSON,
            CREATED_AT
        )
        VALUES (
            WORK_ITEM_EVENTS_SEQ.NEXTVAL,
            :task_id,
            :user_id,
            :event_type,
            :old_value_json,
            :new_value_json,
            SYSTIMESTAMP
        )
        """,
        {
            "task_id": task_id,
            "user_id": user_id,
            "event_type": event_type,
            "old_value_json": _json_object(old_value),
            "new_value_json": _json_object(new_value),
        },
    )


def fetch_task_events(cur, user_id, task_id):
    cur.execute(
        """
        SELECT EVENT_ID, EVENT_TYPE, OLD_VALUE_JSON, NEW_VALUE_JSON, CREATED_AT
        FROM WORK_ITEM_EVENTS
        WHERE USER_ID = :user_id
          AND TASK_ID = :task_id
        ORDER BY CREATED_AT
        """,
        {"user_id": user_id, "task_id": task_id},
    )
    return [
        {
            "event_id": row[0],
            "task_id": task_id,
            "user_id": user_id,
            "event_type": row[1],
            "old_value": _json_value(row[2]),
            "new_value": _json_value(row[3]),
            "created_at": row[4].isoformat() if row[4] else None,
        }
        for row in cur.fetchall()
    ]


def _task_filters(user_id, filters, work_date):
    where = ["w.USER_ID = :user_id"]
    binds = {"user_id": user_id, "work_date": work_date}
    _add_in_filter(where, binds, "w.STATUS", "status", filters.get("status"))
    _add_in_filter(where, binds, "w.EXTERNAL_SOURCE", "source", filters.get("source") or filters.get("external_source"))
    _add_in_filter(where, binds, "w.PRIORITY", "priority", filters.get("priority"))
    if filters.get("worked_date"):
        where.append(
            """
            EXISTS (
                SELECT 1 FROM WORK_ITEM_WORK_DATES fd
                WHERE fd.USER_ID = w.USER_ID
                  AND fd.TASK_ID = w.TASK_ID
                  AND fd.WORK_DATE = TO_DATE(:worked_date, 'YYYY-MM-DD')
            )
            """
        )
        binds["worked_date"] = filters["worked_date"]
    if filters.get("working_today") is not None:
        operator = "EXISTS" if filters.get("working_today") else "NOT EXISTS"
        where.append(
            f"""
            {operator} (
                SELECT 1 FROM WORK_ITEM_WORK_DATES td
                WHERE td.USER_ID = w.USER_ID
                  AND td.TASK_ID = w.TASK_ID
                  AND td.WORK_DATE = TO_DATE(:work_date, 'YYYY-MM-DD')
            )
            """
        )
    if filters.get("completed_date"):
        where.append("TRUNC(CAST(w.COMPLETED_AT AS TIMESTAMP)) = TO_DATE(:completed_date, 'YYYY-MM-DD')")
        binds["completed_date"] = filters["completed_date"]
    if filters.get("completed_from"):
        where.append("w.COMPLETED_AT >= :completed_from")
        binds["completed_from"] = filters["completed_from"]
    if filters.get("completed_to"):
        where.append("w.COMPLETED_AT <= :completed_to")
        binds["completed_to"] = filters["completed_to"]
    search = filters.get("search") or filters.get("q")
    if search:
        where.append(
            """
            (
                LOWER(w.TITLE) LIKE :search
                OR DBMS_LOB.INSTR(LOWER(w.DESCRIPTION), :search_term) > 0
                OR DBMS_LOB.INSTR(LOWER(w.NOTES), :search_term) > 0
            )
            """
        )
        binds["search"] = f"%{str(search).lower()}%"
        binds["search_term"] = str(search).lower()
    return where, binds


def _add_in_filter(where, binds, column, prefix, value):
    values = _filter_values(value)
    if not values:
        return
    names = []
    for index, item in enumerate(values):
        name = f"{prefix}_{index}"
        binds[name] = item
        names.append(f":{name}")
    where.append(f"{column} IN ({', '.join(names)})")


def _filter_values(value):
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _truthy(value, default=False):
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _task_binds(user_id, task, ai):
    return {
        "user_id": user_id,
        "external_source": task.get("external_source") or "Custom",
        "external_id": task.get("external_id"),
        "title": task["title"],
        "description": task.get("description") or "",
        "task_type": task.get("task_type") or "Task",
        "priority": task.get("priority") or "Medium",
        "status": task.get("status") or "To Do",
        "project_key": task.get("project_key"),
        "due_at": task.get("due_at"),
        "start_at": task.get("start_at"),
        "estimated_minutes": task.get("estimated_minutes") or ai.get("effort_minutes"),
        "actual_minutes": task.get("actual_minutes") or 0,
        "rca_tshirt_size": task.get("rca_tshirt_size"),
        "rca_file_change_count": task.get("rca_file_change_count"),
        "rca_complexity_source": task.get("rca_complexity_source"),
        "rca_complexity_at": task.get("rca_complexity_at"),
        "xp_value": task.get("xp_value") or ai.get("xp_value"),
        "notes": task.get("notes") or "",
        "labels_json": _json_list(task.get("labels")),
        "ai_difficulty": ai.get("difficulty"),
        "ai_impact_score": ai.get("impact_score"),
        "ai_priority_score": ai.get("priority_score"),
        "ai_effort_minutes": ai.get("effort_minutes"),
        "ai_category": ai.get("category"),
        "ai_insight": ai.get("insight"),
        "ai_model_version": ai.get("model_id"),
    }


def _task_row(row):
    worked_dates = _json_dates(row[33])
    task = {
        "task_id": row[0],
        "id": str(row[0]),
        "user_id": row[1],
        "external_source": row[2] or "Custom",
        "external_id": row[3],
        "title": _text(row[4]),
        "description": _text(row[5]),
        "task_type": row[6] or "Task",
        "priority": row[7] or "Medium",
        "status": row[8] or "To Do",
        "project_key": row[9],
        "due_at": row[10],
        "start_at": row[11],
        "estimated_minutes": row[12] or row[24] or 0,
        "actual_minutes": row[13] or 0,
        "rca_tshirt_size": row[14],
        "rca_file_change_count": row[15],
        "rca_complexity_source": row[16],
        "rca_complexity_at": row[17],
        "xp_value": row[18] or 0,
        "notes": _text(row[19]),
        "labels": _json_array(row[20]),
        "ai": {
            "difficulty": row[21] or "Medium",
            "impact_score": row[22] or 0,
            "priority_score": row[23] or 0,
            "effort_minutes": row[24] or row[12] or 0,
            "category": row[25],
            "insight": _text(row[26]),
            "model_id": row[27],
            "enriched_at": row[28],
        },
        "completed_at": row[29],
        "created_at": row[30],
        "updated_at": row[31],
        "row_version": row[32] or 1,
        "worked_dates": worked_dates,
        "working_today": bool(row[34]),
    }
    task.update(
        {
            "source": task["external_source"],
            "externalId": task["external_id"] or "",
            "type": task["task_type"],
            "projectKey": task["project_key"] or "",
            "dueDate": _date_part(task["due_at"]),
            "startDate": _date_part(task["start_at"]),
            "time": task["estimated_minutes"],
            "actualMinutes": task["actual_minutes"],
            "xp": task["xp_value"],
            "rcaTshirtSize": task["rca_tshirt_size"],
            "rcaFileChangeCount": task["rca_file_change_count"],
            "rcaComplexitySource": task["rca_complexity_source"],
            "rcaComplexityAt": task["rca_complexity_at"],
            "workedDates": worked_dates,
            "workingToday": task["working_today"],
            "completedAt": task["completed_at"],
            "difficulty": task["ai"]["difficulty"],
            "impact": task["ai"]["impact_score"],
            "priorityScore": task["ai"]["priority_score"],
            "aiInsight": task["ai"]["insight"],
        }
    )
    return task


def _json_list(value):
    return json.dumps(value or [], separators=(",", ":"))


def _json_object(value):
    return json.dumps(value or {}, separators=(",", ":"), default=str)


def _json_value(value):
    text = _text(value)
    if not text:
        return {}
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return {}


def _json_array(value):
    parsed = _json_value(value)
    if isinstance(parsed, list):
        return parsed
    return []


def _json_dates(value):
    if not value:
        return []
    return [item for item in str(value).split(",") if item]


def _text(value):
    if value is None:
        return ""
    if hasattr(value, "read"):
        return value.read()
    return str(value)


def _date_part(value):
    return str(value or "")[:10]


def _returned_id(var):
    value = var.getvalue()
    return value[0] if isinstance(value, list) else value
