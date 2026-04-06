"""
Notes - Database initialization script.
Loads the SQL schema file and executes all CREATE statements using DATABASE_URL.
Used for setting up tables during local or containerized development.
"""

import os
from pathlib import Path

from sqlalchemy import create_engine, text


def get_database_url() -> str:
    """
    Get the DATABASE_URL from the environment.
    This is what you already exported in your shell.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    return db_url


def load_sql_script() -> str:
    """
    Load the SQL from app/db/init/01_create_db_and_tables.sql
    relative to this file.
    """
    base_dir = Path(__file__).resolve().parent  # .../backend/app
    sql_path = base_dir / "db" / "init" / "01_create_db_and_tables.sql"

    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found at: {sql_path}")

    return sql_path.read_text()


def init_db():
    db_url = get_database_url()
    print(f"[db_init] Using DATABASE_URL = {db_url}")

    sql_script = load_sql_script()

    engine = create_engine(db_url, future=True)

    # Execute the whole SQL script (multiple CREATE TABLE statements)
    with engine.begin() as conn:
        for statement in sql_script.split(";"):
            stmt = statement.strip()
            if not stmt:
                continue
            print(f"[db_init] Executing statement:\n{stmt[:80]}...")
            conn.execute(text(stmt))

    print("[db_init] Database initialization complete.")


if __name__ == "__main__":
    init_db()
