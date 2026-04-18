"""
reset_db.py — Clears ALL seed/fake data from TalentBridge.

Run this once to get a clean empty platform:
    cd backend
    python reset_db.py

It will:
  1. Drop all data from every table (except the admin user)
  2. Re-create a single admin user you can log in with
  3. Leave the schema intact so the app works normally

After running, the platform will be completely empty — no jobs, no
candidates, no applications, no screenings. You add everything manually
or through the public apply form.
"""

import os, sys
from pathlib import Path

# Ensure we can import the app package
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
from app.database import Base, DATABASE_URL
from app.models import User
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(bind=engine)

# ── Configurable admin credentials ─────────────────────────────────────────
ADMIN_EMAIL    = os.getenv("ADMIN_EMAIL",    "admin@talentbridge.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_NAME     = os.getenv("ADMIN_NAME",     "Admin User")
ADMIN_COMPANY  = os.getenv("ADMIN_COMPANY",  "TalentBridge")


def reset():
    db = SessionLocal()
    try:
        # Delete in order to respect FK constraints
        print("🗑  Clearing all data...")
        db.execute(text("DELETE FROM activity_logs"))
        db.execute(text("DELETE FROM support_requests"))
        db.execute(text("DELETE FROM screenings"))
        db.execute(text("DELETE FROM applications"))
        db.execute(text("DELETE FROM interview_questions"))
        db.execute(text("DELETE FROM candidates"))
        db.execute(text("DELETE FROM jobs"))
        db.execute(text("DELETE FROM settings"))
        db.execute(text("DELETE FROM users"))
        db.commit()
        print("✅  All tables cleared.")

        # Create admin user
        admin = User(
            email=ADMIN_EMAIL,
            hashed_password=pwd_context.hash(ADMIN_PASSWORD),
            full_name=ADMIN_NAME,
            company_name=ADMIN_COMPANY,
            role="admin",
            is_active=True,
            is_verified=True,
        )
        db.add(admin)
        db.commit()
        print(f"✅  Admin user created:")
        print(f"    Email:    {ADMIN_EMAIL}")
        print(f"    Password: {ADMIN_PASSWORD}")
        print(f"    Name:     {ADMIN_NAME}")
        print()
        print("🚀  Platform is now empty. Log in and start adding jobs!")

    except Exception as e:
        db.rollback()
        print(f"❌  Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    reset()
