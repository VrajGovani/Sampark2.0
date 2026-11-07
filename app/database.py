import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Anchor to project root
BASE_DIR = Path(__file__).resolve().parent.parent

# Automatically load variables from .env file if present locally
if (BASE_DIR / ".env").exists():
    load_dotenv(BASE_DIR / ".env")

# On Vercel / Linux Lambda, fallback SQLite must use /tmp (writable), never /var/task (read-only)
if sys.platform != "win32":
    DEFAULT_DB_FILE = Path("/tmp/sampark.db")
else:
    DEFAULT_DB_FILE = BASE_DIR / "sampark.db"

# Check if environment provides Supabase / PostgreSQL DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Supabase provides 'postgres://...', but SQLAlchemy requires 'postgresql://'
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    # Ensure sslmode=require for cloud PostgreSQL (Supabase / Render / AWS)
    if "sslmode" not in DATABASE_URL and not DATABASE_URL.startswith("sqlite"):
        sep = "&" if "?" in DATABASE_URL else "?"
        DATABASE_URL = f"{DATABASE_URL}{sep}sslmode=require"

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10
    )
else:
    # Local SQLite persistent file fallback
    DATABASE_URL = f"sqlite:///{DEFAULT_DB_FILE}"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
