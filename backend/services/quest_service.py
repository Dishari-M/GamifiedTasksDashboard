from db import connection_scope

def get_quests(user_id):
    with connection_scope() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT TITLE, ESTIMATED_MINUTES, XP_VALUE FROM WORK_ITEMS WHERE USER_ID=:user_id AND STATUS='To Do' ORDER BY XP_VALUE DESC FETCH FIRST 3 ROWS ONLY",
            {"user_id": user_id},
        )
        rows = cur.fetchall()
    return [{"title":r[0],"time":r[1],"xp":r[2]} for r in rows]
