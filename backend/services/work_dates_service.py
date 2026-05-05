from datetime import UTC, datetime

import oracledb

from db import get_connection
from repositories.work_dates_repository import (
    delete_work_date_if_present,
    fetch_work_item_for_update,
    insert_work_date_if_absent,
    insert_working_today_event,
    list_worked_dates,
    touch_work_item,
)


DEFAULT_USER_ID = 1


class TaskNotFoundError(Exception):
    pass


class RowVersionConflictError(Exception):
    pass


class WorkDateDatabaseError(Exception):
    pass


def get_today_utc_date():
    return datetime.now(UTC).date().isoformat()


def set_working_today(task_id, is_working_today, row_version, user_id=DEFAULT_USER_ID):
    work_date = get_today_utc_date()
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        task = fetch_work_item_for_update(cur, task_id, user_id)
        if task is None:
            raise TaskNotFoundError("Task not found")
        if task["row_version"] != row_version:
            raise RowVersionConflictError("Task row version is stale")

        changed = (
            insert_work_date_if_absent(cur, task_id, user_id, work_date)
            if is_working_today
            else delete_work_date_if_present(cur, task_id, user_id, work_date)
        )

        next_row_version = task["row_version"]
        if changed:
            next_row_version = touch_work_item(cur, task_id, user_id, row_version)
            if next_row_version is None:
                raise RowVersionConflictError("Task row version is stale")
            insert_working_today_event(cur, task_id, user_id, work_date, is_working_today)

        worked_dates = list_worked_dates(cur, task_id, user_id)
        conn.commit()
        return {
            "task_id": task_id,
            "work_date": work_date,
            "working_today": work_date in worked_dates,
            "worked_dates": worked_dates,
            "row_version": next_row_version,
        }
    except (TaskNotFoundError, RowVersionConflictError):
        if conn:
            conn.rollback()
        raise
    except oracledb.DatabaseError as exc:
        if conn:
            conn.rollback()
        raise WorkDateDatabaseError("Could not update working-today state") from exc
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()
