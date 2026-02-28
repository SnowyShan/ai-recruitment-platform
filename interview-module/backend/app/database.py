import sqlite3, json, os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "./interview.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            job_description TEXT,
            resume_text TEXT,
            difficulty INTEGER,
            seniority_bar TEXT,
            time_limit INTEGER,
            questions TEXT,
            answers TEXT DEFAULT '{}',
            status TEXT DEFAULT 'active',
            report TEXT,
            created_at TEXT,
            completed_at TEXT
        )
    """)
    conn.commit()
    conn.close()
