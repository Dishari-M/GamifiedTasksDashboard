import uuid
from db import connection_scope

def calculate_xp(est, diff, impact):
    m={"easy":1,"medium":1.3,"hard":1.6}
    return int((est/2)*m.get(diff,1.3)*(1+impact/10))

def create_task(task, ai):
    xp=calculate_xp(ai["estimated"],ai["difficulty"],ai["impact"])
    with connection_scope() as conn:
        cur=conn.cursor()
        task_id = cur.var(int)
        cur.execute(
            """
            INSERT INTO WORK_ITEMS (
                TASK_ID, USER_ID, TITLE, DESCRIPTION, PRIORITY, ESTIMATED_MINUTES,
                XP_VALUE, STATUS, EXTERNAL_SOURCE, TASK_TYPE, CREATED_AT, UPDATED_AT,
                ROW_VERSION
            )
            VALUES (
                WORK_ITEMS_SEQ.NEXTVAL, 1, :title, :description, :priority,
                :estimated_minutes, :xp_value, 'To Do', 'Custom', 'Task',
                SYSTIMESTAMP, SYSTIMESTAMP, 1
            )
            RETURNING TASK_ID INTO :task_id
            """,
            {
                "title": task["title"],
                "description": task["description"],
                "priority": task["priority"],
                "estimated_minutes": ai["estimated"],
                "xp_value": xp,
                "task_id": task_id,
            },
        )
        conn.commit()
    value = task_id.getvalue()
    tid = value[0] if isinstance(value, list) else value
    return {"id":tid,"xp":xp}

def get_tasks():
    with connection_scope() as conn:
        cur=conn.cursor()
        cur.execute("SELECT TASK_ID,TITLE,DESCRIPTION,PRIORITY,ESTIMATED_MINUTES,XP_VALUE,STATUS FROM WORK_ITEMS")
        rows=cur.fetchall()
    return [{"id":r[0],"title":r[1],"desc":_text(r[2]),"priority":r[3],"time":r[4],"xp":r[5],"status":r[6]} for r in rows]

def complete_task(task_id):
    with connection_scope() as conn:
        cur=conn.cursor()
        cur.execute("UPDATE WORK_ITEMS SET STATUS='Done', UPDATED_AT=SYSTIMESTAMP, ROW_VERSION=ROW_VERSION+1 WHERE TASK_ID=:1", (task_id,))
        conn.commit()
        updated=cur.rowcount
    return {"id":task_id,"status":"done","updated":updated}

def _text(value):
    if value is None:
        return ""
    if hasattr(value, "read"):
        return value.read()
    return str(value)
