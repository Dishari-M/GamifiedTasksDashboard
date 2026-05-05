import json


def fetch_work_item_for_update(cur, task_id, user_id):
    cur.execute(
        """
        SELECT TASK_ID, USER_ID, ROW_VERSION
        FROM WORK_ITEMS
        WHERE TASK_ID = :task_id
          AND USER_ID = :user_id
        FOR UPDATE
        """,
        {"task_id": task_id, "user_id": user_id},
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {"task_id": row[0], "user_id": row[1], "row_version": row[2]}


def insert_work_date_if_absent(cur, task_id, user_id, work_date):
    cur.execute(
        """
        INSERT INTO WORK_ITEM_WORK_DATES (
            WORK_ITEM_WORK_DATE_ID,
            USER_ID,
            TASK_ID,
            WORK_DATE,
            SOURCE,
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
        {"task_id": task_id, "user_id": user_id, "work_date": work_date},
    )
    return cur.rowcount == 1


def delete_work_date_if_present(cur, task_id, user_id, work_date):
    cur.execute(
        """
        DELETE FROM WORK_ITEM_WORK_DATES
        WHERE TASK_ID = :task_id
          AND USER_ID = :user_id
          AND WORK_DATE = TO_DATE(:work_date, 'YYYY-MM-DD')
        """,
        {"task_id": task_id, "user_id": user_id, "work_date": work_date},
    )
    return cur.rowcount == 1


def touch_work_item(cur, task_id, user_id, expected_row_version):
    new_row_version = cur.var(int)
    cur.execute(
        """
        UPDATE WORK_ITEMS
        SET UPDATED_AT = SYSTIMESTAMP,
            ROW_VERSION = ROW_VERSION + 1
        WHERE TASK_ID = :task_id
          AND USER_ID = :user_id
          AND ROW_VERSION = :row_version
        RETURNING ROW_VERSION INTO :new_row_version
        """,
        {
            "task_id": task_id,
            "user_id": user_id,
            "row_version": expected_row_version,
            "new_row_version": new_row_version,
        },
    )
    if cur.rowcount != 1:
        return None
    value = new_row_version.getvalue()
    return value[0] if isinstance(value, list) else value


def list_worked_dates(cur, task_id, user_id):
    cur.execute(
        """
        SELECT TO_CHAR(WORK_DATE, 'YYYY-MM-DD')
        FROM WORK_ITEM_WORK_DATES
        WHERE TASK_ID = :task_id
          AND USER_ID = :user_id
        ORDER BY WORK_DATE
        """,
        {"task_id": task_id, "user_id": user_id},
    )
    return [row[0] for row in cur.fetchall()]


def insert_working_today_event(cur, task_id, user_id, work_date, is_working_today):
    old_value = {"work_date": work_date, "working_today": not is_working_today}
    new_value = {"work_date": work_date, "working_today": is_working_today}
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
            'WORKING_TODAY_UPDATED',
            :old_value_json,
            :new_value_json,
            SYSTIMESTAMP
        )
        """,
        {
            "task_id": task_id,
            "user_id": user_id,
            "old_value_json": json.dumps(old_value, separators=(",", ":")),
            "new_value_json": json.dumps(new_value, separators=(",", ":")),
        },
    )
