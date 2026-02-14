# backend/tests/database/test_alphavantage_api.pyimport os
#This file should be moved. Pushing in current location for now
'''To run from backend folder: docker exec -it stock_backend python test_alphavantage_api.py

Testing PostgreSQL directly:

# Connect to postgres
docker exec -it stock_postgres psql -U stock_user -d stock_db

# Then run these queries:
-- Count articles
SELECT COUNT(*) FROM articles;

-- See the latest 5 articles with their source and description
SELECT title, source, LEFT(description, 50) as description, published_at 
FROM articles 
ORDER BY published_at DESC 
LIMIT 5;

-- Count ticker sentiment pairs
SELECT COUNT(*) FROM article_ticker_sentiment;

-- See ticker sentiments
SELECT ticker, relevance_score, article_url 
FROM article_ticker_sentiment 
ORDER BY relevance_score DESC 
LIMIT 10;

-- See which tickers have the most articles
SELECT ticker, COUNT(*) as article_count 
FROM article_ticker_sentiment 
GROUP BY ticker 
ORDER BY article_count DESC;

-- Exit when done
\q


Some quick one-line checks: 
# Count articles
docker exec -it stock_postgres psql -U stock_user -d stock_db -c "SELECT COUNT(*) FROM articles;"

# Count ticker sentiments (not implemented as of 2/14/2026)
docker exec -it stock_postgres psql -U stock_user -d stock_db -c "SELECT COUNT(*) FROM article_ticker_sentiment;"

# See latest articles
docker exec -it stock_postgres psql -U stock_user -d stock_db -c "SELECT title, source, published_at FROM articles ORDER BY published_at DESC LIMIT 5;"
'''

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the app directory to Python path
sys.path.insert(0, '/app')

# Set environment variables (use values from .env if available)
os.environ["DATABASE_URL"] = os.getenv("DATABASE_URL", "postgresql://stock_user:stock_pass@postgres:5432/stock_db")
#!!! Set API key in .env file in project root
os.environ["ALPHAVANTAGE_API_KEY"] = os.getenv("ALPHAVANTAGE_API_KEY", "demo")

from app.services.api_article_ingest import AlphaVantageIngestor
def test_ingestion():
    print("=" * 60)
    print("Testing AlphaVantage Ingestion")
    print("=" * 60)
    
    # Create ingestor
    db_url = os.getenv("DATABASE_URL")
    print(f"\n1. Connecting to database: {db_url}")
    
    try:
        ingestor = AlphaVantageIngestor(db_url)
        print("Yes: Connected successfully!")
    except Exception as e:
        print(f"X : Connection failed: {e}")
        return
    
    # Test with a small query
    print("\n2. Fetching news for AAPL (limit 5 articles)...")
    try:
        ingestor.ingest_for_tickers(
            tickers=["AAPL"],
            time_from="20250101T0000",
            time_to="20250214T2359",
            limit=5,
            update_existing=False,
            save_to_csv=True,
        )
        print("Yes: Ingestion completed!")
    except Exception as e:
        print(f"X: Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n3. Checking what was stored in database...")
    
    # Query the database to see what we stored
    from sqlalchemy import text
    try:
        with ingestor.engine.connect() as conn:
            # Count articles
            result = conn.execute(text("SELECT COUNT(*) FROM articles"))
            article_count = result.scalar()
            print(f"   - Total articles in database: {article_count}")
            
            # Count ticker sentiments
            result = conn.execute(text("SELECT COUNT(*) FROM article_ticker_sentiment"))
            sentiment_count = result.scalar()
            print(f"   - Total ticker-article pairs: {sentiment_count}")
            
            # Show a sample article
            result = conn.execute(text("""
                SELECT title, source, description, published_at 
                FROM articles 
                LIMIT 1
            """))
            row = result.fetchone()
            if row:
                print(f"\n4. Sample article:")
                print(f"   Title: {row[0][:80] if row[0] else 'N/A'}...")
                print(f"   Source: {row[1] or 'N/A'}")
                if row[2]:
                    print(f"   Description: {row[2][:100]}...")
                else:
                    print(f"   Description: N/A")
                print(f"   Published: {row[3]}")
            else:
                print("\n4. No articles found in database")
            
            # Show ticker sentiment data
            result = conn.execute(text("""
                SELECT ticker, relevance_score, article_url
                FROM article_ticker_sentiment
                LIMIT 3
            """))
            rows = result.fetchall()
            if rows:
                print(f"\n5. Sample ticker sentiments:")
                for row in rows:
                    relevance = row[1] if row[1] is not None else 0.0
                    print(f"   - Ticker: {row[0]}, Relevance: {relevance:.3f}")
            else:
                print("\n5. No ticker sentiments found in database")
    except Exception as e:
        print(f"X : Database query failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 60)
    print("Yes: Test completed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    test_ingestion()
