import uuid
from db import get_connection

def calculate_xp(est, diff, impact):
    m={"easy":1,"medium":1.3,"hard":1.6}
    return int((est/2)*m.get(diff,1.3)*(1+impact/10))

def create_task(task, ai):
    conn=get_connection();cur=conn.cursor()
    tid=str(uuid.uuid4())
    xp=calculate_xp(ai["estimated"],ai["difficulty"],ai["impact"])
    cur.execute("INSERT INTO DEVQUEST_WORK_ITEMS (ID,TITLE,DESCRIPTION,PRIORITY,AI_ESTIMATED_MINUTES,XP_VALUE,STATUS) VALUES (:1,:2,:3,:4,:5,:6,'todo')",
    (tid,task["title"],task["description"],task["priority"],ai["estimated"],xp))
    conn.commit();conn.close()
    return {"id":tid,"xp":xp}

def get_tasks():
    conn=get_connection();cur=conn.cursor()
    cur.execute("SELECT ID,TITLE,DESCRIPTION,PRIORITY,AI_ESTIMATED_MINUTES,XP_VALUE,STATUS FROM DEVQUEST_WORK_ITEMS")
    rows=cur.fetchall();conn.close()
    return [{"id":r[0],"title":r[1],"desc":r[2],"priority":r[3],"time":r[4],"xp":r[5],"status":r[6]} for r in rows]
