import yfinance as yf
import pandas as pd
import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Table, Column, String, Float, Date, Integer, MetaData, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import insert
from typing import List, Optional
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PriceIngestor:
    
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        self.metadata = MetaData()
        self._create_table()
    
    def _create_table(self):
        self.stock_prices = Table(
            'stock_prices',
            self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('ticker', String(20), nullable=False),
            Column('date', Date, nullable=False),
            Column('open', Float),
            Column('high', Float),
            Column('low', Float),
            Column('close', Float),
            Column('adjusted_close', Float, nullable=False),
            Column('volume', Integer),
            Column('created_at', Date, default=datetime.utcnow),
            UniqueConstraint('ticker', 'date', name='unique_ticker_date')
        )
        
        self.metadata.create_all(self.engine)
        logger.info("Stock prices table created/verified")
    
    def fetch_stock_data(
        self, 
        ticker: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None,
        period: str = "1y"
    ) -> pd.DataFrame:
        try:
            logger.info(f"Fetching data for {ticker}")
            
            stock = yf.Ticker(ticker)
            
            if start_date and end_date:
                df = stock.history(start=start_date, end=end_date)
            else:
                df = stock.history(period=period)
            
            if df.empty:
                logger.warning(f"No data retrieved for {ticker}")
                return pd.DataFrame()
            
            df = df.reset_index()
            
            df = df.rename(columns={
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            df['adjusted_close'] = df['close']
            df['ticker'] = ticker
            
            columns = ['ticker', 'date', 'open', 'high', 'low', 'close', 'adjusted_close', 'volume']
            df = df[columns]
            
            df['date'] = pd.to_datetime(df['date']).dt.date
            
            logger.info(f"Retrieved {len(df)} records for {ticker}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {str(e)}")
            return pd.DataFrame()
    
    def store_prices(self, df: pd.DataFrame, update_existing: bool = False):
        if df.empty:
            logger.warning("No data to store")
            return
        
        try:
            records = df.to_dict('records')
            total_records = len(records)
            batch_size = 100
            records_processed = 0
            
            for i in range(0, total_records, batch_size):
                batch = records[i:i + batch_size]
                
                with self.engine.begin() as conn:
                    if update_existing:
                        stmt = insert(self.stock_prices).values(batch)
                        stmt = stmt.on_conflict_do_update(
                            constraint='unique_ticker_date',
                            set_={
                                'open': stmt.excluded.open,
                                'high': stmt.excluded.high,
                                'low': stmt.excluded.low,
                                'close': stmt.excluded.close,
                                'adjusted_close': stmt.excluded.adjusted_close,
                                'volume': stmt.excluded.volume
                            }
                        )
                    else:
                        stmt = insert(self.stock_prices).values(batch)
                        stmt = stmt.on_conflict_do_nothing(constraint='unique_ticker_date')
                    
                    conn.execute(stmt)
                    records_processed += len(batch)
                    logger.info(f"Processed {records_processed}/{total_records} records")
            
            logger.info(f"Successfully stored {total_records} records")
                
        except Exception as e:
            logger.error(f"Error storing prices: {str(e)}")
            raise
    
    def ingest_multiple_stocks(
        self, 
        tickers: List[str], 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "1y",
        update_existing: bool = False
    ):
        for ticker in tickers:
            logger.info(f"Processing {ticker}")
            df = self.fetch_stock_data(ticker, start_date, end_date, period)
            if not df.empty:
                self.store_prices(df, update_existing)
            else:
                logger.warning(f"Skipping {ticker} - no data retrieved")
    
    def get_latest_date(self, ticker: str) -> Optional[datetime]:
        try:
            with self.engine.connect() as conn:
                query = text("""
                    SELECT MAX(date) as latest_date 
                    FROM stock_prices 
                    WHERE ticker = :ticker
                """)
                result = conn.execute(query, {"ticker": ticker}).fetchone()
                return result[0] if result and result[0] else None
        except Exception as e:
            logger.error(f"Error getting latest date for {ticker}: {str(e)}")
            return None
    
    def backfill_missing_data(self, ticker: str, target_start_date: str):
        latest = self.get_latest_date(ticker)
        
        if latest:
            logger.info(f"Latest data for {ticker}: {latest}")
            df = self.fetch_stock_data(ticker, start_date=target_start_date, end_date=str(latest))
        else:
            logger.info(f"No existing data for {ticker}, fetching from {target_start_date}")
            df = self.fetch_stock_data(ticker, start_date=target_start_date)
        
        if not df.empty:
            self.store_prices(df, update_existing=False)


if __name__ == "__main__":
    DB_URL = os.getenv("DATABASE_URL")
    
    if not DB_URL:
        DB_USER = os.getenv("PG_USER", "stock_user")
        DB_PASSWORD = os.getenv("PG_PASS", "stock_pass")
        DB_HOST = os.getenv("PG_HOST", "postgres")
        DB_PORT = os.getenv("PG_PORT", "5432")
        DB_NAME = os.getenv("PG_DB", "stock_db")
        DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    logger.info("Connecting to database...")
    
    ingestor = PriceIngestor(DB_URL)
    
    STOCKS = [
        'BP',
        'RELIANCE.NS'
    ]
    
    logger.info("Starting price ingestion for all stocks")
    ingestor.ingest_multiple_stocks(
        tickers=STOCKS,
        start_date="2021-10-01",
        end_date = "2022-02-28",
        period = None,
        update_existing=False
    )
    
    logger.info("Price ingestion complete")
    
    logger.info("Verifying stored data...")
    try:
        with ingestor.engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("SELECT ticker, COUNT(*) as count FROM stock_prices GROUP BY ticker"))
            for row in result:
                logger.info(f"  {row[0]}: {row[1]} records")
    except Exception as e:
        logger.error(f"Error verifying data: {str(e)}")