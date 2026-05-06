from db import connection_scope

def get_quests():
    with connection_scope() as conn:
        cur = conn.cursor()
        cur.execute("SELECT TITLE, ESTIMATED_MINUTES, XP_VALUE FROM WORK_ITEMS WHERE STATUS='To Do' ORDER BY XP_VALUE DESC FETCH FIRST 3 ROWS ONLY")
        rows = cur.fetchall()
    return [{"title":r[0],"time":r[1],"xp":r[2]} for r in rows]
