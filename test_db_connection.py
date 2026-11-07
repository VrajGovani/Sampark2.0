"""
Diagnostic script to test your database connection (SQLite or Supabase PostgreSQL).
Run with: python test_db_connection.py
"""
import sys
from app.database import engine, DATABASE_URL
from sqlalchemy import text

def test_connection():
    print("\n" + "=" * 60)
    print("🔍 Testing Sampark Database Connection...")
    print("=" * 60)

    # Sanitize URL for printing (mask password if PostgreSQL/Supabase)
    display_url = DATABASE_URL
    if "@" in display_url:
        prefix, rest = display_url.split("@", 1)
        scheme_user = prefix.split(":")[0] + "://" + prefix.split(":")[1].split("//")[1]
        display_url = f"{scheme_user}:****@{rest}"
    
    print(f"📍 Database Target: {display_url}")
    
    if "sqlite" in DATABASE_URL.lower():
        print("💾 Mode: Local SQLite Database (sampark.db)")
    else:
        print("☁️ Mode: Cloud PostgreSQL / Supabase Database")

    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar()
            assert result == 1
            print("✅ Connection Status: SUCCESSFUL!")

            # Check existing tables
            if "sqlite" in DATABASE_URL.lower():
                tables = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
            else:
                tables = connection.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).fetchall()
            
            table_names = [t[0] for t in tables if not t[0].startswith("alembic")]
            print(f"📋 Verified Tables: {table_names if table_names else 'No tables yet (will auto-create on first run)'}")
            
    except Exception as e:
        print("\n❌ Connection Failed!")
        print(f"Error details: {e}")
        print("\n💡 Troubleshooting Tips:")
        print("1. If using Supabase, make sure your password in .env does not contain unescaped special characters.")
        print("2. Check if your project is paused or still provisioning in the Supabase dashboard.")
        print("3. Try copying the 'Session Pooler' or 'Direct Connection' URI from Supabase.")
        sys.exit(1)

    print("=" * 60 + "\n")

if __name__ == "__main__":
    test_connection()

