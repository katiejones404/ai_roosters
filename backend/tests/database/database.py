"""
Notes - Utility script for inspecting the 'articles' table.
Connects to the database, counts non‑null values per column,
and prints a quick completeness report for debugging/data quality checks.
"""

import os
from sqlalchemy import create_engine, text


def get_engine():
    """
    Create a SQLAlchemy engine using DATABASE_URL from the environment,
    or fall back to the Docker Compose defaults.
    """
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://stock_user:stock_pass@postgres:5432/stock_db",
    )
    print(f"[INFO] Using DB URL: {db_url}")
    return create_engine(db_url)


def inspect_articles_columns():
    """
    Print how many rows each column in 'articles' has (non-null vs null).
    """
    columns = [
        "id",
        "title",
        "author",
        "published_at",
        "source",
        "url",
        "image",
        "category",
        "language",
        "country",
        "raw",
        "inserted_at",
    ]

    engine = get_engine()

    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM articles")).scalar_one()
        print(f"\n[INFO] Total rows in articles: {total}\n")

        if total == 0:
            print("[WARN] articles table is empty.")
            return

        for col in columns:
            non_null = conn.execute(
                text(f"SELECT COUNT({col}) FROM articles WHERE {col} IS NOT NULL")
            ).scalar_one()
            print(
                f"{col:12} | non_null={non_null:5d}  null={total - non_null:5d}"
            )


if __name__ == "__main__":
    print("[INFO] Starting articles column inspection...")
    inspect_articles_columns()
    print("\n[INFO] Inspection complete.")
