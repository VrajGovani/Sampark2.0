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

    # Switch to pg8000 dialect (pure Python, works on Vercel serverless)
    # Replace postgresql:// or postgresql+psycopg2:// with postgresql+pg8000://
    if "postgresql+pg8000://" not in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg2://", "postgresql+pg8000://")
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+pg8000://")

    # pg8000 uses ssl=True query param instead of sslmode=require
    if "ssl=" not in DATABASE_URL and "sslmode=" not in DATABASE_URL:
        sep = "&" if "?" in DATABASE_URL else "?"
        DATABASE_URL = f"{DATABASE_URL}{sep}ssl=true"

    # Supabase transaction pooler (port 6543) requires NullPool — no persistent connections
    from sqlalchemy.pool import NullPool
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,
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
