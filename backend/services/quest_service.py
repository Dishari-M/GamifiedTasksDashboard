from db import get_connection

def get_quests():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT TITLE, ESTIMATED_MINUTES, XP_VALUE FROM WORK_ITEMS WHERE STATUS='To Do' ORDER BY XP_VALUE DESC FETCH FIRST 3 ROWS ONLY")
    rows = cur.fetchall()
    conn.close()
    return [{"title":r[0],"time":r[1],"xp":r[2]} for r in rows]
