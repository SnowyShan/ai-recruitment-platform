from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./talentbridge.db")

# Handle SQLite specific configuration
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def run_migrations(engine):
    """Add new columns if they don't exist (safe to run on existing DBs)."""
    from sqlalchemy import text
    migrations = [
        "ALTER TABLE screenings ADD COLUMN interview_session_id TEXT",
        "ALTER TABLE screenings ADD COLUMN invite_token TEXT",
        "ALTER TABLE screenings ADD COLUMN invite_sent_at DATETIME",
        "ALTER TABLE screenings ADD COLUMN invite_expires_at DATETIME",
        "ALTER TABLE screenings ADD COLUMN invite_used BOOLEAN DEFAULT 0",
        "ALTER TABLE jobs ADD COLUMN interview_time_limit INTEGER DEFAULT 45",
        "ALTER TABLE jobs ADD COLUMN interview_num_questions INTEGER DEFAULT 8",
        "ALTER TABLE jobs ADD COLUMN interview_difficulty INTEGER DEFAULT 3",
        "ALTER TABLE jobs ADD COLUMN interview_seniority TEXT DEFAULT \'mid\'",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # Column already exists

