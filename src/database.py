import sqlite3

DB_NAME = "ai_radar.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS quota (
        id INTEGER PRIMARY KEY,
        platform TEXT,
        account TEXT,
        cycle TEXT,
        percent INTEGER,
        updated TEXT
    )
    """)
    conn.commit()
    conn.close()
